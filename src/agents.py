import os
import json
import re
import sys
import time
import base64
import copy
import threading
import traceback
import concurrent.futures
import tkinter as tk
from tkinter import filedialog, simpledialog, messagebox
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

# ─── External Imports ─────────────────────────────────────
import requests
import fitz  # PyMuPDF
from google import genai
from pymongo import MongoClient, ASCENDING, DESCENDING
from bson import ObjectId
import chromadb
from chromadb.utils import embedding_functions
from bs4 import BeautifulSoup

# ══════════════════════════════════════════════════════════
#                        AGENT 1
# ══════════════════════════════════════════════════════════

class Agent1:
    """
    Agent 1 — Candidate Profile Aggregator

    Takes a resume (PDF/DOCX/text) and builds a unified
    candidate profile by:
      1. Parsing the resume with Gemini
      2. Scraping GitHub profile + code analysis
      3. Scraping portfolio website
      4. Merging all sources into unified JSON
      5. Saving to MongoDB + local JSON file
    """

    # ── Gemini Models ─────────────────────────────────────
    MODELS = [
        "models/gemini-2.0-flash",
        "models/gemini-2.5-flash",
        "models/gemini-2.0-flash-lite",
        "models/gemini-2.5-flash-lite"
    ]

    # ── GitHub Code File Extensions ───────────────────────
    CODE_EXTENSIONS = {
        ".py", ".js", ".ts", ".jsx", ".tsx",
        ".java", ".cpp", ".c", ".cs",
        ".go", ".rs", ".swift", ".kt", ".scala",
        ".r", ".R", ".sql", ".ipynb",
        ".php", ".rb", ".html", ".css",
        ".sh", ".bash"
    }

    SKIP_PATTERNS = [
        "package-lock.json", "yarn.lock", ".gitignore",
        "requirements.txt", "setup.py", "config.",
        "LICENSE", "CHANGELOG", ".env", "test_",
        "_test.", "spec.", ".min.js", "node_modules",
        "dist/", "build/", "__pycache__", ".min.css",
        "vendor/", "migrations/"
    ]

    # ── Non-portfolio domains to skip ─────────────────────
    SKIP_DOMAINS = [
        "medium.com", "twitter.com", "x.com",
        "facebook.com", "instagram.com", "youtube.com",
        "notion.so", "docs.google.com", "drive.google.com",
        "mailto:", "tel:", "wa.me", "t.me"
    ]

    # ── Empty resume structure fallback ───────────────────
    EMPTY_RESUME = {
        "name":          "",
        "email":         "",
        "phone":         "",
        "location":      "",
        "summary":       "",
        "linkedin_url":  "",
        "github_url":    "",
        "portfolio_url": "",
        "skills":        [],
        "experience":    [],
        "education":     [],
        "certifications": [],
        "projects":      []
    }

    # ── MongoDB Schema ────────────────────────────────────
    STUDENT_PROFILE_VALIDATOR = {
        "$jsonSchema": {
            "bsonType": "object",
            "required": [
                "user_id", "created_at", "updated_at",
                "candidate", "skills", "sources_used"
            ],
            "properties": {
                "user_id":       {"bsonType": "objectId"},
                "created_at":    {"bsonType": "date"},
                "updated_at":    {"bsonType": "date"},
                "agent_version": {"bsonType": "string"},
                "candidate": {
                    "bsonType": "object",
                    "required": ["name", "email"],
                    "properties": {
                        "name":     {"bsonType": "string"},
                        "email":    {"bsonType": "string"},
                        "phone":    {"bsonType": ["string", "null"]},
                        "location": {"bsonType": ["string", "null"]},
                        "summary":  {"bsonType": ["string", "null"]}
                    }
                },
                "skills": {
                    "bsonType": "object",
                    "properties": {
                        "all":            {"bsonType": "array"},
                        "from_resume":    {"bsonType": "array"},
                        "from_github":    {"bsonType": "array"},
                        "from_portfolio": {"bsonType": "array"},
                        "from_code":      {"bsonType": "array"}
                    }
                },
                "sources_used": {
                    "bsonType": "object",
                    "required": [
                        "resume", "github",
                        "portfolio", "code_analysis"
                    ],
                    "properties": {
                        "resume":        {"bsonType": "bool"},
                        "github":        {"bsonType": "bool"},
                        "portfolio":     {"bsonType": "bool"},
                        "code_analysis": {"bsonType": "bool"}
                    }
                }
            }
        }
    }

    # ══════════════════════════════════════════════════════
    #                     INIT
    # ══════════════════════════════════════════════════════

    def __init__(self):
        load_dotenv()

        # ── Gemini Clients ────────────────────────────────
        self.resume_client = genai.Client(
            api_key=os.environ.get("GEMINI_API_KEY")
        )
        self.code_client = genai.Client(
            api_key=(
                os.environ.get("GEMINI_CODE_KEY") or
                os.environ.get("GEMINI_API_KEY")
            )
        )

        # ── GitHub ────────────────────────────────────────
        self.github_token   = os.environ.get("GITHUB_TOKEN")
        self.github_headers = {
            "Authorization": f"token {self.github_token}",
            "Accept":        "application/vnd.github.v3+json"
        }

        # ── MongoDB ───────────────────────────────────────
        self.mongo_uri     = os.environ.get(
            "MONGODB_URI", "mongodb://localhost:27017"
        )
        self.mongo_db_name = os.environ.get(
            "MONGODB_DB", "hiring_platform"
        )
        self._mongo_client = None
        self._mongo_db     = None

        # ── Thread Safety ─────────────────────────────────
        self._print_lock = threading.Lock()
        self._cache      = {}
        self._cache_lock = threading.Lock()

        print("  ✅ Agent 1 initialized")

    # ══════════════════════════════════════════════════════
    #                   UTILITY METHODS
    # ══════════════════════════════════════════════════════

    def safe_print(self, msg):
        with self._print_lock:
            print(msg)

    def cached_get(self, url):
        with self._cache_lock:
            if url in self._cache:
                return self._cache[url]
        r = requests.get(url, headers=self.github_headers)
        with self._cache_lock:
            self._cache[url] = r
        return r

    def is_real_url(self, url):
        if not url:
            return False
        if not isinstance(url, str):
            return False
        if not url.startswith("http"):
            return False
        if url in ["https://github.com/github"]:
            return False
        return True

    def is_github_profile_url(self, url):
        """
        Returns True ONLY for github.com/username
        Returns False for github.com/username/repo
        """
        if not self.is_real_url(url):
            return False
        if "github.com" not in url:
            return False

        path = url.rstrip("/")
        for prefix in [
            "https://github.com/",
            "http://github.com/",
            "https://www.github.com/",
        ]:
            if path.startswith(prefix):
                path = path[len(prefix):]
                break

        parts = [p for p in path.split("/") if p]
        return len(parts) == 1

    def is_portfolio_url(self, url):
        """
        Returns True if URL looks like a portfolio website.
        Skips known non-portfolio domains.
        """
        if not self.is_real_url(url):
            return False
        for domain in self.SKIP_DOMAINS:
            if domain in url:
                return False
        if "github.com" in url:
            return False
        if "linkedin.com" in url:
            return False
        return True

    def clean_gemini_json(self, raw):
        """
        Cleans Gemini response to extract valid JSON.
        Handles:
          - markdown code blocks
          - extra text before/after JSON
          - trailing commas
          - comments inside JSON
        """
        # Remove markdown code blocks
        raw = raw.replace("```json", "")
        raw = raw.replace("```", "")
        raw = raw.strip()

        # Extract just the JSON object
        start = raw.find("{")
        end   = raw.rfind("}") + 1
        if start != -1 and end > start:
            raw = raw[start:end]

        # Try direct parse first
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass

        # Fix trailing commas before } or ]
        fixed = re.sub(r",\s*([}\]])", r"\1", raw)

        # Remove single-line comments
        fixed = re.sub(r"//.*?\n", "\n", fixed)

        # Remove multi-line comments
        fixed = re.sub(
            r"/\*.*?\*/", "", fixed, flags=re.DOTALL
        )

        # Try again after fixes
        try:
            return json.loads(fixed)
        except json.JSONDecodeError as e:
            raise e

    # ══════════════════════════════════════════════════════
    #                  RESUME PARSER
    # ══════════════════════════════════════════════════════

    def extract_hyperlinks(self, file_bytes, filename):
        """Extract actual URLs from PDF via PyMuPDF"""
        links = []
        try:
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            for page in doc:
                for link in page.get_links():
                    uri = link.get("uri", "")
                    if uri:
                        links.append(uri)
            doc.close()
        except Exception as e:
            print(f"  ⚠️  Hyperlink extraction failed: {e}")
        return links

    def classify_hyperlinks(self, hyperlinks):
        """
        Classifies hyperlinks into categories.
        GitHub: ONLY profile URL (1 path segment).
        Portfolio: skips Medium, Twitter etc.
        """
        github_url    = None
        linkedin_url  = None
        portfolio_url = None
        email         = None

        for link in hyperlinks:

            # ── Email ─────────────────────────────────────
            if link.startswith("mailto:"):
                email = link.replace("mailto:", "")
                print(f"  📧 Email found: {email}")

            # ── LinkedIn ──────────────────────────────────
            elif "linkedin.com" in link:
                linkedin_url = link
                print(f"  💼 LinkedIn URL found: {link}")

            # ── GitHub ────────────────────────────────────
            elif "github.com" in link:
                if self.is_github_profile_url(link):
                    if not github_url:
                        github_url = link
                        print(
                            f"  🐙 GitHub profile URL "
                            f"found: {link}"
                        )
                else:
                    print(
                        f"  ℹ️  Skipping GitHub repo URL: "
                        f"{link}"
                    )

            # ── Portfolio ─────────────────────────────────
            elif self.is_portfolio_url(link):
                if not portfolio_url:
                    portfolio_url = link
                    print(
                        f"  🌐 Portfolio URL found: {link}"
                    )
                else:
                    print(
                        f"  ℹ️  Skipping extra URL: {link}"
                    )

            # ── Skip ──────────────────────────────────────
            else:
                print(f"  ℹ️  Skipping URL: {link}")

        return github_url, linkedin_url, portfolio_url, email

    def extract_text_from_file(self, file_bytes, filename):
        """Extract plain text from PDF or DOCX"""
        text = ""
        try:
            if filename.lower().endswith(".pdf"):
                doc = fitz.open(
                    stream=file_bytes, filetype="pdf"
                )
                for page in doc:
                    text += page.get_text()
                doc.close()
            elif filename.lower().endswith(".docx"):
                import docx
                import io
                doc  = docx.Document(io.BytesIO(file_bytes))
                text = "\n".join(
                    [p.text for p in doc.paragraphs]
                )
        except Exception as e:
            print(f"  ⚠️  Text extraction failed: {e}")
        return text

    def parse_resume_with_gemini(self, text):
        """Parse resume text with Gemini → structured JSON"""
        prompt = f"""
You are an expert resume parser. Extract all information
from this resume and return ONLY a valid JSON object.

STRICT RULES:
- Return ONLY the JSON object, nothing else
- No markdown code blocks
- No trailing commas anywhere
- No comments inside JSON
- All strings must use double quotes
- If a field has no value use empty string "" or []
- Do not truncate any arrays

Return this exact structure:
{{
    "name": "",
    "email": "",
    "phone": "",
    "location": "",
    "summary": "",
    "linkedin_url": "",
    "github_url": "",
    "portfolio_url": "",
    "skills": [],
    "experience": [
        {{
            "company": "",
            "role": "",
            "duration": "",
            "location": "",
            "description": ""
        }}
    ],
    "education": [
        {{
            "institution": "",
            "degree": "",
            "field": "",
            "year": ""
        }}
    ],
    "certifications": [],
    "projects": [
        {{
            "name": "",
            "description": "",
            "technologies": []
        }}
    ]
}}

Resume text:
{text[:8000]}
"""

        for model_name in self.MODELS:
            for attempt in range(3):
                try:
                    print(
                        f"  Trying {model_name} "
                        f"(attempt {attempt + 1}/3)..."
                    )
                    response = (
                        self.resume_client.models.generate_content(
                            model=model_name,
                            contents=prompt
                        )
                    )
                    raw = response.text.strip()

                    # Try to clean and parse JSON
                    try:
                        result = self.clean_gemini_json(raw)
                        print(
                            f"  ✅ Resume parsed with "
                            f"{model_name}"
                        )
                        return result
                    except json.JSONDecodeError as je:
                        print(
                            f"  ⚠️  JSON parse failed: {je}"
                        )
                        print(
                            f"  ⚠️  Response preview: "
                            f"{raw[:300]}"
                        )
                        # Try next attempt
                        if attempt < 2:
                            print(
                                f"  🔄 Retrying same model..."
                            )
                            continue
                        else:
                            print(
                                f"  ❌ {model_name} failed — "
                                f"trying next model..."
                            )
                            break

                except Exception as e:
                    error_str = str(e)
                    if "429" in error_str:
                        print(
                            f"  ❌ Quota exhausted on "
                            f"{model_name} — waiting 15s..."
                        )
                        time.sleep(15)
                        break
                    elif "503" in error_str:
                        if attempt < 2:
                            wait = 30 * (attempt + 1)
                            print(
                                f"  ⚠️  {model_name} "
                                f"unavailable — "
                                f"waiting {wait}s..."
                            )
                            time.sleep(wait)
                        else:
                            break
                    elif "404" in error_str:
                        break
                    else:
                        print(
                            f"  ❌ Unexpected error on "
                            f"{model_name}: {e}"
                        )
                        break

        # All models failed — return empty structure
        print(
            "  ❌ All models failed — "
            "returning empty resume structure"
        )
        return copy.deepcopy(self.EMPTY_RESUME)

    def parse_resume(self, source, filename="resume.pdf"):
        """
        Main resume parser entry point.
        source: file bytes (PDF/DOCX) or plain text string
        """
        print(f"\n  Parsing uploaded file: {filename}")

        if isinstance(source, bytes):
            # ── Extract + classify hyperlinks ─────────────
            print("  Extracting hyperlinks from file...")
            hyperlinks = self.extract_hyperlinks(
                source, filename
            )
            print(f"  🔗 All hyperlinks: {hyperlinks}")

            github_url, linkedin_url, portfolio_url, email = \
                self.classify_hyperlinks(hyperlinks)

            # ── Extract text + parse ──────────────────────
            text        = self.extract_text_from_file(
                source, filename
            )
            resume_data = self.parse_resume_with_gemini(text)

            # ── Override with hyperlink data ──────────────
            # Hyperlinks are more reliable than Gemini parsing
            if github_url:
                resume_data["github_url"] = github_url
            if linkedin_url:
                resume_data["linkedin_url"] = linkedin_url
            if portfolio_url:
                resume_data["portfolio_url"] = portfolio_url
            if email and not resume_data.get("email"):
                resume_data["email"] = email

        else:
            resume_data = self.parse_resume_with_gemini(
                str(source)
            )

        return resume_data

    # ══════════════════════════════════════════════════════
    #                  RAG EXTRACTOR
    # ══════════════════════════════════════════════════════

    def build_vectorstore(self, resume_data):
        """Build ChromaDB vectorstore from resume data"""
        try:
            client = chromadb.Client()
            ef     = embedding_functions.DefaultEmbeddingFunction()

            collection = client.get_or_create_collection(
                name="resume_rag",
                embedding_function=ef
            )

            docs = []
            ids  = []

            if resume_data.get("summary"):
                docs.append(resume_data["summary"])
                ids.append("summary")

            for i, exp in enumerate(
                resume_data.get("experience", [])
            ):
                docs.append(
                    f"{exp.get('role')} at "
                    f"{exp.get('company')} — "
                    f"{exp.get('description', '')}"
                )
                ids.append(f"exp_{i}")

            for i, proj in enumerate(
                resume_data.get("projects", [])
            ):
                docs.append(
                    f"{proj.get('name')} — "
                    f"{proj.get('description', '')}"
                )
                ids.append(f"proj_{i}")

            skills_text = ", ".join(
                resume_data.get("skills", [])
            )
            if skills_text:
                docs.append(f"Skills: {skills_text}")
                ids.append("skills")

            if docs:
                collection.add(documents=docs, ids=ids)

            return collection

        except Exception as e:
            print(f"  ⚠️  RAG vectorstore failed: {e}")
            return None

    def query_github_url(self, collection, resume_data):
        """
        Get GitHub profile URL from resume data.
        Only returns profile URLs — never repo URLs.
        """
        github_url = resume_data.get("github_url")

        if not github_url:
            return None

        # Already a valid profile URL
        if self.is_github_profile_url(github_url):
            return github_url

        # Gemini returned a repo URL — extract username
        if "github.com" in str(github_url):
            try:
                path = github_url.rstrip("/")
                for prefix in [
                    "https://github.com/",
                    "http://github.com/"
                ]:
                    if path.startswith(prefix):
                        path = path[len(prefix):]
                        break
                parts    = [p for p in path.split("/") if p]
                username = parts[0] if parts else None
                if username:
                    profile_url = (
                        f"https://github.com/{username}"
                    )
                    print(
                        f"  🔧 Extracted profile URL: "
                        f"{profile_url}"
                    )
                    return profile_url
            except:
                pass

        return None

    def query_linkedin_url(self, collection, resume_data):
        """Get LinkedIn URL from resume data"""
        linkedin_url = resume_data.get("linkedin_url")
        if linkedin_url and "linkedin.com" in linkedin_url:
            return linkedin_url
        return None

    def query_portfolio_url(self, collection, resume_data):
        """
        Get portfolio URL from resume data.
        Skips Medium, Twitter, and other non-portfolio sites.
        """
        portfolio_url = resume_data.get("portfolio_url")
        if self.is_portfolio_url(portfolio_url):
            return portfolio_url
        return None

    def extract_portfolio_from_github(self, github_data):
        """Check GitHub profile website field for portfolio"""
        if not github_data:
            return None
        website = github_data.get("website", "")
        if self.is_portfolio_url(website):
            return website
        return None

    # ══════════════════════════════════════════════════════
    #                  GITHUB SCRAPER
    # ══════════════════════════════════════════════════════

    def get_github_profile(self, username):
        r = self.cached_get(
            f"https://api.github.com/users/{username}"
        )
        return r.json()

    def get_github_repos(self, username):
        r = self.cached_get(
            f"https://api.github.com/users/{username}/repos"
            f"?per_page=100&sort=updated"
        )
        return r.json() if r.status_code == 200 else []

    def get_default_branch(self, username, repo_name):
        r = self.cached_get(
            f"https://api.github.com/repos"
            f"/{username}/{repo_name}"
        )
        if r.status_code == 200:
            return r.json().get("default_branch", "main")
        return "main"

    def get_readme(self, username, repo_name):
        r = self.cached_get(
            f"https://api.github.com/repos"
            f"/{username}/{repo_name}/readme"
        )
        if r.status_code == 200:
            try:
                content = base64.b64decode(
                    r.json()["content"].replace("\n", "")
                ).decode("utf-8", errors="replace")
                return content[:1000]
            except:
                return ""
        return ""

    def get_languages(self, username, repo_name):
        r = self.cached_get(
            f"https://api.github.com/repos"
            f"/{username}/{repo_name}/languages"
        )
        return (
            list(r.json().keys())
            if r.status_code == 200 else []
        )

    def get_commit_count(self, username, repo_name):
        r = requests.get(
            f"https://api.github.com/repos/{username}"
            f"/{repo_name}/commits?per_page=1",
            headers=self.github_headers
        )
        if r.status_code == 200:
            if "Link" in r.headers:
                try:
                    last_page = r.headers["Link"].split(",")[-1]
                    count     = int(
                        last_page.split(
                            "page="
                        )[-1].split(">")[0]
                    )
                    return count
                except:
                    return len(r.json())
            return len(r.json())
        return 0

    def get_repo_files(self, username, repo_name, max_files=5):
        default_branch  = self.get_default_branch(
            username, repo_name
        )
        branches_to_try = list(dict.fromkeys(
            [default_branch, "main", "master", "HEAD"]
        ))

        tree = []
        for branch in branches_to_try:
            r = self.cached_get(
                f"https://api.github.com/repos/{username}"
                f"/{repo_name}/git/trees"
                f"/{branch}?recursive=1"
            )
            if r.status_code != 200:
                continue

            data = r.json()
            if data.get("truncated"):
                r2 = self.cached_get(
                    f"https://api.github.com/repos/{username}"
                    f"/{repo_name}/contents"
                )
                if r2.status_code == 200:
                    contents = r2.json()
                    if isinstance(contents, list):
                        tree = [
                            {
                                "type": "blob",
                                "path": item["path"],
                                "size": item.get("size", 0)
                            }
                            for item in contents
                            if item["type"] == "file"
                        ]
                        break
            else:
                tree = data.get("tree", [])
                break

        files = []
        for item in tree:
            if item.get("type") != "blob":
                continue
            path = item.get("path", "")
            if any(
                skip in path for skip in self.SKIP_PATTERNS
            ):
                continue
            ext = os.path.splitext(path)[1].lower()
            if ext not in self.CODE_EXTENSIONS:
                continue
            if item.get("size", 0) > 100000:
                continue
            files.append(path)
            if len(files) >= max_files:
                break

        return files

    def extract_ipynb_code(self, content):
        try:
            nb   = json.loads(content)
            code = []
            for cell in nb.get("cells", []):
                if cell.get("cell_type") == "code":
                    source = cell.get("source", [])
                    if isinstance(source, list):
                        code.append("".join(source))
                    elif isinstance(source, str):
                        code.append(source)
            return "\n\n".join(code[:10])
        except:
            return content

    def get_file_content(self, username, repo_name, file_path):
        content = ""
        r = self.cached_get(
            f"https://api.github.com/repos/{username}"
            f"/{repo_name}/contents/{file_path}"
        )

        if r.status_code == 200:
            data = r.json()
            if isinstance(data, dict):
                if data.get("encoding") == "base64":
                    try:
                        content = base64.b64decode(
                            data["content"].replace("\n", "")
                        ).decode("utf-8", errors="replace")
                    except:
                        pass
                elif data.get("content"):
                    content = data["content"]

        if not content:
            try:
                r2 = requests.get(
                    f"https://raw.githubusercontent.com/"
                    f"{username}/{repo_name}"
                    f"/HEAD/{file_path}",
                    headers={
                        "Authorization": (
                            f"token {self.github_token}"
                        )
                    },
                    timeout=10
                )
                if r2.status_code == 200:
                    content = r2.text
            except:
                pass

        if not content:
            return ""

        if file_path.endswith(".ipynb"):
            content = self.extract_ipynb_code(content)

        return content

    def fetch_repo_code(self, username, repo_name, max_files=5):
        self.safe_print(f"\n    📂 Fetching: {repo_name}")
        file_paths   = self.get_repo_files(
            username, repo_name, max_files
        )
        code_samples = {}

        for path in file_paths:
            content = self.get_file_content(
                username, repo_name, path
            )
            if content and content.strip():
                code_samples[path] = content
                self.safe_print(
                    f"    📥 {repo_name}: ✅ {path} "
                    f"({len(content)} chars)"
                )
            else:
                self.safe_print(
                    f"    📥 {repo_name}: ⚠️  {path} — empty"
                )

        return repo_name, code_samples

    def fetch_all_repos_parallel(
        self, username, repos, max_workers=5
    ):
        results   = {}
        num_repos = len(repos)
        workers   = min(num_repos, max_workers)

        print(
            f"\n  📦 Fetching code from {num_repos} repos "
            f"({workers} parallel workers)..."
        )

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=workers
        ) as executor:
            future_to_repo = {
                executor.submit(
                    self.fetch_repo_code,
                    username,
                    repo["name"]
                ): repo["name"]
                for repo in repos
            }

            completed = 0
            for future in concurrent.futures.as_completed(
                future_to_repo
            ):
                repo_name = future_to_repo[future]
                completed += 1
                try:
                    name, code_samples = future.result()
                    results[name]      = code_samples
                    status = (
                        f"{len(code_samples)} files"
                        if code_samples else "no code"
                    )
                    print(
                        f"  📥 Fetched "
                        f"({completed}/{num_repos}): "
                        f"{name} — {status}"
                    )
                except Exception as e:
                    print(
                        f"  ❌ Fetch failed "
                        f"({completed}/{num_repos}): "
                        f"{repo_name} — {e}"
                    )
                    results[repo_name] = {}

        repos_with_code = sum(
            1 for v in results.values() if v
        )
        print(
            f"  ✅ Fetch complete — "
            f"{repos_with_code}/{num_repos} repos had code"
        )
        return results

    def analyze_code_with_gemini(self, repo_name, code_samples):
        if not code_samples:
            return {}

        code_context = ""
        for file_path, content in code_samples.items():
            code_context += (
                f"\n\n--- File: {file_path} ---\n"
                f"{content[:1500]}"
            )

        prompt = f"""
You are a senior software engineer reviewing code from
a GitHub repository. Analyze the following code samples
from the repository "{repo_name}" and provide insights.

Return ONLY a valid JSON object — no markdown, no text:

{{
    "code_quality": {{
        "score": 0,
        "rating": "",
        "summary": ""
    }},
    "technical_complexity": {{
        "score": 0,
        "rating": "",
        "summary": ""
    }},
    "architecture_patterns": [],
    "skills_demonstrated": [],
    "best_practices_used": [],
    "areas_for_improvement": [],
    "overall_assessment": "",
    "notable_observations": []
}}

score is 1-10
rating is: Beginner | Intermediate | Advanced | Expert

Code samples:
{code_context}
"""

        for model_name in self.MODELS:
            for attempt in range(3):
                try:
                    self.safe_print(
                        f"    🤖 {repo_name}: trying "
                        f"{model_name} "
                        f"(attempt {attempt + 1}/3)..."
                    )
                    response = (
                        self.code_client.models.generate_content(
                            model=model_name,
                            contents=prompt
                        )
                    )
                    raw    = response.text.strip()
                    result = self.clean_gemini_json(raw)
                    self.safe_print(
                        f"    ✅ {repo_name}: analysis complete"
                    )
                    return result

                except json.JSONDecodeError as je:
                    self.safe_print(
                        f"    ⚠️  {repo_name}: JSON parse "
                        f"failed on {model_name}: {je}"
                    )
                    if attempt < 2:
                        continue
                    else:
                        break

                except Exception as e:
                    error_str = str(e)
                    if "429" in error_str:
                        self.safe_print(
                            f"    ❌ {repo_name}: quota "
                            f"exhausted on {model_name} "
                            f"— waiting 30s..."
                        )
                        time.sleep(30)
                        break
                    elif "503" in error_str:
                        if attempt < 2:
                            wait = 30 * (attempt + 1)
                            self.safe_print(
                                f"    ⚠️  {model_name} "
                                f"unavailable — "
                                f"waiting {wait}s..."
                            )
                            time.sleep(wait)
                        else:
                            break
                    elif "404" in error_str:
                        break
                    else:
                        raise e

        self.safe_print(
            f"    ⚠️  {repo_name}: all models failed"
        )
        return {}

    def analyze_all_repos_sequential(
        self, repos_with_code, delay_between_calls=3
    ):
        results   = {}
        num_repos = len(repos_with_code)
        completed = 0

        print(
            f"\n  🤖 Analyzing {num_repos} repos sequentially "
            f"({delay_between_calls}s delay)..."
        )

        for repo_name, code_samples in repos_with_code.items():
            completed += 1
            print(
                f"\n  🤖 Analyzing ({completed}/{num_repos}): "
                f"{repo_name}..."
            )

            try:
                insights           = self.analyze_code_with_gemini(
                    repo_name, code_samples
                )
                results[repo_name] = insights
                status = (
                    "got insights"
                    if insights else "empty insights"
                )
                print(
                    f"  ✅ Done ({completed}/{num_repos}): "
                    f"{repo_name} — {status}"
                )
            except Exception as e:
                print(
                    f"  ❌ Failed ({completed}/{num_repos}): "
                    f"{repo_name} — {e}"
                )
                results[repo_name] = {}

            if completed < num_repos:
                print(
                    f"  ⏳ Waiting {delay_between_calls}s..."
                )
                time.sleep(delay_between_calls)

        repos_with_insights = sum(
            1 for v in results.values() if v
        )
        print(
            f"\n  ✅ Analysis complete — "
            f"{repos_with_insights}/{num_repos} got insights"
        )
        return results

    def scrape_github(self, github_url, analyze_code=True):
        if not github_url:
            print("  ⚠️  No GitHub URL — skipping")
            return {}

        username = github_url.rstrip("/").split("/")[-1]
        print(f"  Scraping GitHub profile: {username}")

        if username.lower() == "github":
            print("  ❌ Detected org account — skipping")
            return {}

        profile = self.get_github_profile(username)
        if (
            "message" in profile
            and profile["message"] == "Not Found"
        ):
            print(f"  ❌ GitHub user '{username}' not found")
            return {}

        repos = self.get_github_repos(username)
        if not isinstance(repos, list):
            print(
                f"  ❌ Could not fetch repos for '{username}'"
            )
            return {}

        print(
            f"  Found {len(repos)} repositories — "
            f"scanning metadata..."
        )

        repo_details = []
        for i, repo in enumerate(repos):
            name = repo["name"]
            print(f"    [{i+1}/{len(repos)}] {name}")
            repo_details.append({
                "name":           name,
                "description":    repo.get("description"),
                "languages":      self.get_languages(
                    username, name
                ),
                "stars":          repo.get(
                    "stargazers_count", 0
                ),
                "forks":          repo.get("forks_count", 0),
                "commit_count":   self.get_commit_count(
                    username, name
                ),
                "last_updated":   repo.get("updated_at"),
                "readme_preview": self.get_readme(
                    username, name
                ),
                "topics":         repo.get("topics", []),
                "has_live_demo":  bool(repo.get("homepage")),
                "homepage":       repo.get("homepage", ""),
                "is_fork":        repo.get("fork", False),
                "code_samples":   {},
                "code_insights":  {}
            })
            time.sleep(0.2)

        repos_analyzed_count = 0

        if analyze_code:
            non_fork_repos = sorted(
                [r for r in repo_details if not r["is_fork"]],
                key=lambda x: x["commit_count"],
                reverse=True
            )

            print(
                f"\n  🔍 Analyzing ALL "
                f"{len(non_fork_repos)} non-fork repos"
            )

            if non_fork_repos:
                all_code = self.fetch_all_repos_parallel(
                    username, non_fork_repos, max_workers=5
                )

                repos_with_code = {
                    name: samples
                    for name, samples in all_code.items()
                    if samples
                }

                print(
                    f"\n  📊 {len(repos_with_code)}/"
                    f"{len(non_fork_repos)} repos have code"
                )

                if repos_with_code:
                    all_insights = (
                        self.analyze_all_repos_sequential(
                            repos_with_code,
                            delay_between_calls=3
                        )
                    )

                    for repo in repo_details:
                        name = repo["name"]
                        if name in all_code and all_code[name]:
                            repo["code_samples"] = {
                                path: content[:500]
                                for path, content
                                in all_code[name].items()
                            }
                        if (
                            name in all_insights
                            and all_insights[name]
                        ):
                            repo["code_insights"] = (
                                all_insights[name]
                            )
                            repos_analyzed_count += 1

        all_languages = list(set(
            lang
            for repo in repo_details
            for lang in repo["languages"]
        ))

        top_repos = sorted(
            repo_details,
            key=lambda x: x["stars"],
            reverse=True
        )[:5]

        all_skills    = []
        all_patterns  = []
        all_practices = []

        for repo in repo_details:
            insights = repo.get("code_insights", {})
            if insights:
                all_skills.extend(
                    insights.get("skills_demonstrated", [])
                )
                all_patterns.extend(
                    insights.get("architecture_patterns", [])
                )
                all_practices.extend(
                    insights.get("best_practices_used", [])
                )

        result = {
            "username":      username,
            "name":          profile.get("name"),
            "bio":           profile.get("bio"),
            "location":      profile.get("location"),
            "email":         profile.get("email"),
            "website":       profile.get("blog"),
            "followers":     profile.get("followers"),
            "following":     profile.get("following"),
            "public_repos":  profile.get("public_repos"),
            "github_url":    f"https://github.com/{username}",
            "all_languages": all_languages,
            "top_repos":     top_repos,
            "repositories":  repo_details,
            "code_analysis": {
                "repos_analyzed":        repos_analyzed_count,
                "skills_from_code":      list(set(all_skills)),
                "architecture_patterns": list(set(all_patterns)),
                "best_practices":        list(set(all_practices))
            }
        }

        print(f"\n  ✅ GitHub scraping complete")
        print(f"     Username    : {username}")
        print(f"     Repos       : {len(repo_details)}")
        print(
            f"     Languages   : "
            f"{', '.join(all_languages[:8])}"
        )
        print(
            f"     Analyzed    : {repos_analyzed_count} repos"
        )

        return result

    # ══════════════════════════════════════════════════════
    #                 PORTFOLIO SCRAPER
    # ══════════════════════════════════════════════════════

    def scrape_portfolio(self, portfolio_url):
        if not portfolio_url:
            return {}

        print(f"  Scraping portfolio: {portfolio_url}")

        try:
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X "
                    "10_15_7) AppleWebKit/537.36 (KHTML, like "
                    "Gecko) Chrome/120.0.0.0 Safari/537.36"
                )
            }
            r = requests.get(
                portfolio_url, timeout=15, headers=headers
            )

            if r.status_code == 403:
                print(
                    f"  ⚠️  Portfolio returned 403 — "
                    f"site blocks scrapers"
                )
                return {}

            if r.status_code != 200:
                print(
                    f"  ⚠️  Portfolio returned {r.status_code}"
                )
                return {}

            soup     = BeautifulSoup(r.text, "html.parser")
            headings = [
                h.get_text(strip=True)
                for h in soup.find_all(["h1", "h2", "h3"])
            ]
            text = soup.get_text(separator="\n", strip=True)

            structured = self.parse_portfolio_with_gemini(
                text[:6000], portfolio_url
            )

            print(f"  ✅ Portfolio scraped successfully")
            return {
                "url":        portfolio_url,
                "headings":   headings,
                "structured": structured
            }

        except Exception as e:
            print(f"  ⚠️  Portfolio scraping failed: {e}")
            return {}

    def parse_portfolio_with_gemini(self, text, url):
        prompt = f"""
Extract information from this portfolio website content
and return ONLY a valid JSON object. No markdown.

{{
    "name": "",
    "title": "",
    "about": "",
    "skills": [],
    "projects": [
        {{
            "name": "",
            "description": "",
            "technologies": [],
            "link": ""
        }}
    ],
    "experience": [],
    "education": [],
    "contact": {{
        "email": "",
        "linkedin": "",
        "github": ""
    }}
}}

Portfolio URL: {url}
Content:
{text}
"""

        for model_name in self.MODELS:
            try:
                response = (
                    self.resume_client.models.generate_content(
                        model=model_name,
                        contents=prompt
                    )
                )
                raw = response.text.strip()
                return self.clean_gemini_json(raw)
            except Exception as e:
                if "429" in str(e):
                    time.sleep(15)
                    continue
                continue

        return {}

    # ══════════════════════════════════════════════════════
    #                  PROFILE MERGER
    # ══════════════════════════════════════════════════════

    def merge_profiles(
        self, resume_data, github_data, portfolio_data
    ):
        resume_skills    = resume_data.get("skills", [])
        github_languages = github_data.get("all_languages", [])
        portfolio_skills = portfolio_data.get(
            "structured", {}
        ).get("skills", [])
        code_skills      = github_data.get(
            "code_analysis", {}
        ).get("skills_from_code", [])

        all_skills = list(set(
            [s.lower() for s in resume_skills]    +
            [l.lower() for l in github_languages] +
            [s.lower() for s in portfolio_skills] +
            [s.lower() for s in code_skills]
        ))

        github_repos = [
            {
                "name":          repo["name"],
                "description":   repo.get("description", ""),
                "technologies":  repo.get("languages", []),
                "source":        "github",
                "stars":         repo.get("stars", 0),
                "forks":         repo.get("forks", 0),
                "commit_count":  repo.get("commit_count", 0),
                "last_updated":  repo.get("last_updated", ""),
                "readme":        repo.get(
                    "readme_preview", ""
                ),
                "topics":        repo.get("topics", []),
                "has_live_demo": repo.get(
                    "has_live_demo", False
                ),
                "homepage":      repo.get("homepage", ""),
                "is_fork":       repo.get("is_fork", False),
                "code_samples":  repo.get("code_samples", {}),
                "code_insights": repo.get("code_insights", {})
            }
            for repo in github_data.get("repositories", [])
        ]

        return {
            "candidate": {
                "name": (
                    resume_data.get("name") or
                    github_data.get("name")
                ),
                "email": (
                    resume_data.get("email") or
                    github_data.get("email")
                ),
                "phone":    resume_data.get("phone"),
                "location": (
                    resume_data.get("location") or
                    github_data.get("location")
                ),
                "summary":  resume_data.get("summary")
            },
            "skills": {
                "all":            all_skills,
                "from_resume":    resume_skills,
                "from_github":    github_languages,
                "from_portfolio": portfolio_skills,
                "from_code":      code_skills
            },
            "experience":     resume_data.get("experience", []),
            "education":      resume_data.get("education", []),
            "certifications": resume_data.get(
                "certifications", []
            ),
            "projects": {
                "from_resume":    resume_data.get(
                    "projects", []
                ),
                "from_github":    github_repos,
                "from_portfolio": portfolio_data.get(
                    "structured", {}
                ).get("projects", [])
            },
            "github_profile": {
                "username":     github_data.get("username"),
                "bio":          github_data.get("bio"),
                "website":      github_data.get("website"),
                "followers":    github_data.get("followers"),
                "following":    github_data.get("following"),
                "public_repos": github_data.get("public_repos"),
                "github_url":   github_data.get("github_url"),
                "top_repos":    github_data.get("top_repos", [])
            },
            "code_analysis": github_data.get("code_analysis", {
                "repos_analyzed":        0,
                "skills_from_code":      [],
                "architecture_patterns": [],
                "best_practices":        []
            }),
            "portfolio": {
                "url":        portfolio_data.get("url"),
                "headings":   portfolio_data.get("headings", []),
                "structured": portfolio_data.get(
                    "structured", {}
                )
            },
            "links": {
                "github":    github_data.get("github_url"),
                "portfolio": portfolio_data.get("url"),
                "linkedin":  resume_data.get("linkedin_url")
            },
            "sources_used": {
                "resume":        bool(resume_data),
                "github":        bool(github_data),
                "portfolio":     bool(portfolio_data),
                "code_analysis": github_data.get(
                    "code_analysis", {}
                ).get("repos_analyzed", 0) > 0
            }
        }

    # ══════════════════════════════════════════════════════
    #                   MONGODB METHODS
    # ══════════════════════════════════════════════════════

    def get_db(self):
        if self._mongo_db is not None:
            return self._mongo_db

        self._mongo_client = MongoClient(
            self.mongo_uri,
            serverSelectionTimeoutMS=5000
        )
        self._mongo_db = self._mongo_client[self.mongo_db_name]
        self._mongo_client.admin.command("ping")
        print(
            f"  ✅ Connected to MongoDB: {self.mongo_db_name}"
        )
        return self._mongo_db

    def test_mongodb_connection(self):
        """Quick test to verify MongoDB is working"""
        try:
            db       = self.get_db()
            test_col = db["_connection_test"]
            result   = test_col.insert_one({"test": True})
            test_col.delete_one({"_id": result.inserted_id})
            print("  ✅ MongoDB read/write test passed")
            return True
        except Exception as e:
            print(f"  ❌ MongoDB test failed: {e}")
            return False

    def setup_collections(self):
        db       = self.get_db()
        existing = db.list_collection_names()

        print(f"\n  📦 Setting up MongoDB collections...")

        if "student_profiles" not in existing:
            db.create_collection(
                "student_profiles",
                validator=self.STUDENT_PROFILE_VALIDATOR,
                validationLevel="moderate",
                validationAction="warn"
            )
            print("  ✅ Created: student_profiles")
        else:
            print("  ℹ️  Exists:  student_profiles")

        for col in ["users", "resumes", "agent_logs"]:
            if col not in existing:
                db.create_collection(col)
                print(f"  ✅ Created: {col}")
            else:
                print(f"  ℹ️  Exists:  {col}")

        self._create_indexes(db)
        print("  ✅ MongoDB setup complete\n")

    def _create_indexes(self, db):
        """Creates indexes safely — skips if already exists"""

        try:
            existing_sp = [
                idx["name"]
                for idx in db.student_profiles.list_indexes()
            ]
        except:
            existing_sp = []

        try:
            existing_al = [
                idx["name"]
                for idx in db.agent_logs.list_indexes()
            ]
        except:
            existing_al = []

        def make_sp_index(keys, name, **kwargs):
            if name not in existing_sp:
                try:
                    db.student_profiles.create_index(
                        keys, name=name, **kwargs
                    )
                except Exception as e:
                    print(f"  ⚠️  Index {name} skipped: {e}")

        def make_al_index(keys, name, **kwargs):
            if name not in existing_al:
                try:
                    db.agent_logs.create_index(
                        keys, name=name, **kwargs
                    )
                except Exception as e:
                    print(f"  ⚠️  Index {name} skipped: {e}")

        make_sp_index(
            [("user_id", ASCENDING)],
            "idx_user_id_unique",
            unique=True
        )
        make_sp_index(
            [("candidate.email", ASCENDING)],
            "idx_candidate_email"
        )
        make_sp_index(
            [("candidate.name", ASCENDING)],
            "idx_candidate_name"
        )
        make_sp_index(
            [("skills.all", ASCENDING)],
            "idx_skills_all"
        )
        make_sp_index(
            [("skills.from_resume", ASCENDING)],
            "idx_skills_from_resume"
        )
        make_sp_index(
            [("candidate.location", ASCENDING)],
            "idx_location"
        )
        make_sp_index(
            [("created_at", DESCENDING)],
            "idx_created_at"
        )
        make_sp_index(
            [("github_profile.username", ASCENDING)],
            "idx_github_username",
            sparse=True
        )
        make_sp_index(
            [("code_analysis.repos_analyzed", DESCENDING)],
            "idx_repos_analyzed"
        )
        make_al_index(
            [("user_id", ASCENDING)],
            "idx_log_user_id"
        )
        make_al_index(
            [("created_at", DESCENDING)],
            "idx_log_created_at"
        )

        print("  ✅ Indexes ready")

    def _convert_dates(self, profile):
        """Convert ISO date strings to datetime objects"""
        profile = copy.deepcopy(profile)

        def parse_date(val):
            if (
                isinstance(val, str)
                and "T" in val
                and val.endswith("Z")
            ):
                try:
                    return datetime.fromisoformat(
                        val.replace("Z", "+00:00")
                    )
                except:
                    return val
            return val

        def convert_obj(obj):
            if isinstance(obj, dict):
                return {
                    k: convert_obj(v)
                    for k, v in obj.items()
                }
            elif isinstance(obj, list):
                return [convert_obj(i) for i in obj]
            else:
                return parse_date(obj)

        return convert_obj(profile)

    def save_to_mongodb(self, unified_profile, user_id=None):
        """
        Saves unified profile to MongoDB.
        Upserts by user_id.
        Logs agent run to agent_logs.
        """
        db  = self.get_db()
        now = datetime.now(timezone.utc)

        if user_id is None:
            user_id = ObjectId()
        else:
            user_id = ObjectId(user_id)

        profile                  = self._convert_dates(
            unified_profile
        )
        profile["user_id"]       = user_id
        profile["updated_at"]    = now
        profile["agent_version"] = "1.0"

        existing = db.student_profiles.find_one(
            {"user_id": user_id}
        )

        if existing:
            db.student_profiles.update_one(
                {"user_id": user_id},
                {"$set": profile}
            )
            profile_id = existing["_id"]
            print(
                f"  ✅ Updated profile in MongoDB: {profile_id}"
            )
        else:
            profile["created_at"] = now
            result     = db.student_profiles.insert_one(profile)
            profile_id = result.inserted_id
            print(
                f"  ✅ Inserted profile in MongoDB: {profile_id}"
            )

        # Log the agent run
        try:
            db.agent_logs.insert_one({
                "user_id":      user_id,
                "profile_id":   profile_id,
                "agent":        "agent1",
                "status":       "success",
                "created_at":   now,
                "completed_at": now,
                "input": {
                    "candidate_name": unified_profile.get(
                        "candidate", {}
                    ).get("name"),
                    "candidate_email": unified_profile.get(
                        "candidate", {}
                    ).get("email")
                },
                "sources_used": unified_profile.get(
                    "sources_used", {}
                ),
                "stats": {
                    "total_skills":   len(
                        unified_profile.get(
                            "skills", {}
                        ).get("all", [])
                    ),
                    "total_repos":    len(
                        unified_profile.get(
                            "projects", {}
                        ).get("from_github", [])
                    ),
                    "repos_analyzed": unified_profile.get(
                        "code_analysis", {}
                    ).get("repos_analyzed", 0),
                    "experience":     len(
                        unified_profile.get("experience", [])
                    ),
                    "certifications": len(
                        unified_profile.get(
                            "certifications", []
                        )
                    )
                }
            })
            print("  ✅ Agent run logged to agent_logs")
        except Exception as e:
            print(f"  ⚠️  agent_logs insert failed: {e}")

        return profile_id

    # ══════════════════════════════════════════════════════
    #                   UI HELPERS
    # ══════════════════════════════════════════════════════

    def prompt_for_link(self, link_type, description):
        """GUI popup asking user to paste a link or skip"""
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)

        want_to_provide = messagebox.askyesno(
            title=f"{link_type} URL Not Found",
            message=(
                f"{description}\n\n"
                f"Would you like to provide your "
                f"{link_type} URL?"
            )
        )

        if not want_to_provide:
            root.destroy()
            print(f"  ⏭️  User skipped {link_type} URL")
            return None

        url = simpledialog.askstring(
            title=f"Enter {link_type} URL",
            prompt=f"Paste your {link_type} URL below:",
            parent=root
        )
        root.destroy()

        if url and url.strip():
            url = url.strip()
            print(
                f"  ✅ User provided {link_type} URL: {url}"
            )
            return url

        print(
            f"  ⏭️  No {link_type} URL entered — skipping"
        )
        return None

    def scrape_github_profile(self, github_url):
        """
        Validates GitHub URL then runs full scrape
        + code analysis.
        """
        if not github_url:
            return {}

        # Correct repo URL to profile URL if needed
        if not self.is_github_profile_url(github_url):
            try:
                path = github_url.rstrip("/")
                for prefix in [
                    "https://github.com/",
                    "http://github.com/"
                ]:
                    if path.startswith(prefix):
                        path = path[len(prefix):]
                        break
                parts    = [p for p in path.split("/") if p]
                username = parts[0] if parts else None
                if username:
                    github_url = (
                        f"https://github.com/{username}"
                    )
                    print(
                        f"  🔧 Corrected to profile URL: "
                        f"{github_url}"
                    )
            except:
                pass

        username     = github_url.rstrip("/").split("/")[-1]
        _profile     = self.get_github_profile(username)
        public_repos = _profile.get("public_repos", 0)

        if public_repos > 200:
            print(
                f"\n  ⚠️  This account has {public_repos} "
                f"repos — looks like an org"
            )
            confirm = input(
                "  Are you sure this is the right URL? "
                "(y/n): "
            ).strip().lower()
            if confirm != "y":
                print("  ⏭️  Skipping GitHub scraping.")
                return {}

        print(
            f"  🚀 Starting GitHub scraping "
            f"+ code analysis..."
        )
        return self.scrape_github(github_url, analyze_code=True)

    # ══════════════════════════════════════════════════════
    #                  PRINT SUMMARY
    # ══════════════════════════════════════════════════════

    def print_summary(self, unified_profile):
        print("\n" + "=" * 55)
        print("              AGENT 1 COMPLETE ✅")
        print("=" * 55)

        c = unified_profile["candidate"]
        print(f"\n👤 CANDIDATE")
        print(f"  Name     : {c.get('name', 'N/A')}")
        print(f"  Email    : {c.get('email', 'N/A')}")
        print(f"  Phone    : {c.get('phone', 'N/A')}")
        print(f"  Location : {c.get('location', 'N/A')}")

        s = unified_profile["skills"]
        print(f"\n🛠️  SKILLS")
        print(f"  Total unique   : {len(s['all'])}")
        print(
            f"  From resume    : "
            f"{len(s['from_resume'])} skills"
        )
        print(
            f"  From GitHub    : "
            f"{len(s['from_github'])} languages"
        )
        print(
            f"  From portfolio : "
            f"{len(s['from_portfolio'])} skills"
        )
        print(
            f"  From code      : "
            f"{len(s['from_code'])} skills"
        )

        print(f"\n💼 EXPERIENCE")
        for exp in unified_profile.get("experience", []):
            print(
                f"  • {exp.get('role')} @ "
                f"{exp.get('company')} "
                f"({exp.get('duration')})"
            )

        print(f"\n🎓 EDUCATION")
        for edu in unified_profile.get("education", []):
            print(
                f"  • {edu.get('degree')} in "
                f"{edu.get('field')} — "
                f"{edu.get('institution')} "
                f"({edu.get('year')})"
            )

        print(f"\n📜 CERTIFICATIONS")
        for cert in unified_profile.get("certifications", []):
            print(f"  • {cert}")

        print(f"\n📁 PROJECTS FROM RESUME")
        for proj in unified_profile["projects"].get(
            "from_resume", []
        ):
            print(f"  • {proj.get('name')}")

        gh = unified_profile["github_profile"]
        print(f"\n🐙 GITHUB PROFILE")
        print(f"  Username     : {gh.get('username', 'N/A')}")
        print(
            f"  Public repos : "
            f"{gh.get('public_repos', 'N/A')}"
        )
        print(
            f"  Followers    : {gh.get('followers', 'N/A')}"
        )

        all_github = unified_profile["projects"].get(
            "from_github", []
        )
        print(f"\n  All Repos ({len(all_github)} total):")
        for repo in all_github:
            insights = repo.get("code_insights", {})
            cq       = insights.get("code_quality", {})
            rating   = cq.get("rating", "")
            score    = cq.get("score", "")
            suffix   = (
                f" → {rating} ({score}/10)"
                if rating else ""
            )
            print(f"  • {repo['name']}{suffix}")

        ca       = unified_profile.get("code_analysis", {})
        analyzed = ca.get("repos_analyzed", 0)
        print(f"\n🔍 CODE ANALYSIS")
        if analyzed == 0:
            print("  ⚠️  No code analysis was run")
        else:
            print(f"  Repos analyzed : {analyzed}")

        print(f"\n🌐 PORTFOLIO")
        port_url = unified_profile["portfolio"].get("url")
        print(f"  URL : {port_url or '❌ Not found'}")

        print(f"\n📊 SOURCES USED")
        for source, used in unified_profile[
            "sources_used"
        ].items():
            print(
                f"  {'✅' if used else '❌'} "
                f"{source.capitalize()}"
            )

        print(f"\n🔗 LINKS")
        links = unified_profile["links"]
        print(
            f"  GitHub    : "
            f"{links.get('github')    or 'Not found'}"
        )
        print(
            f"  Portfolio : "
            f"{links.get('portfolio') or 'Not found'}"
        )
        print(
            f"  LinkedIn  : "
            f"{links.get('linkedin')  or 'Not found'}"
        )

        print("\n" + "=" * 55)
        print("  ✅ Saved → outputs/candidate_profile.json")
        print("  ✅ Saved → MongoDB student_profiles")
        print("  ✅ Ready for Agent 2")
        print("=" * 55)

    # ══════════════════════════════════════════════════════
    #                     MAIN RUNNER
    # ══════════════════════════════════════════════════════

    def run(self):
        print("\n" + "=" * 55)
        print("          AGENT 1 — PROFILE AGGREGATOR")
        print("=" * 55)

        # ── Test MongoDB first ────────────────────────────
        print("\n🔌 Testing MongoDB connection...")
        mongo_ok = self.test_mongodb_connection()
        if not mongo_ok:
            print(
                "  ⚠️  MongoDB not available — "
                "will save to JSON only"
            )

        # ── Step 1: Resume Input ──────────────────────────
        print("\n📄 STEP 1: Resume Input")
        print("  1. Upload resume file (PDF/DOCX)")
        print("  2. Paste resume text")
        choice = input("\n  Enter 1 or 2: ").strip()

        if choice == "1":
            root = tk.Tk()
            root.withdraw()
            file_path = filedialog.askopenfilename(
                title="Select Resume",
                filetypes=[
                    ("PDF files",  "*.pdf"),
                    ("Word files", "*.docx")
                ]
            )
            if not file_path:
                print("  No file selected. Exiting.")
                return

            filename = os.path.basename(file_path)
            with open(file_path, "rb") as f:
                file_bytes = f.read()
            resume_data = self.parse_resume(
                file_bytes, filename
            )

        elif choice == "2":
            print(
                "\n  Paste resume text. "
                "Type 'END' on a new line when done:\n"
            )
            lines = []
            while True:
                line = input()
                if line.strip() == "END":
                    break
                lines.append(line)
            resume_data = self.parse_resume(
                "\n".join(lines)
            )
        else:
            print("  Invalid choice. Exiting.")
            return

        print(
            f"\n  ✅ Resume parsed: {resume_data.get('name')}"
        )

        # ── Step 2: Build RAG + Extract Links ─────────────
        print(
            "\n🔍 STEP 2: Building RAG + Extracting links..."
        )
        collection   = self.build_vectorstore(resume_data)
        github_url   = self.query_github_url(
            collection, resume_data
        )
        linkedin_url = self.query_linkedin_url(
            collection, resume_data
        )

        # ── Step 3: GitHub ────────────────────────────────
        print("\n🐙 STEP 3: GitHub Sub-Agent")
        github_data = {}

        if github_url:
            # ✅ Found — proceed immediately
            print(f"  ✅ GitHub URL found: {github_url}")
            github_data = self.scrape_github_profile(
                github_url
            )
        else:
            # ❌ Not found — ask user
            print("  ⚠️  No GitHub URL found automatically")
            github_url = self.prompt_for_link(
                link_type="GitHub",
                description=(
                    "No GitHub URL was found in your resume.\n"
                    "This may be because your GitHub link is "
                    "a hyperlink with display text only.\n"
                    "(e.g. 'GitHub' instead of the actual URL)"
                )
            )
            if github_url:
                github_data = self.scrape_github_profile(
                    github_url
                )
            else:
                print(
                    "  ⏭️  Skipping GitHub — no URL provided"
                )

        # ── Step 4: Portfolio ─────────────────────────────
        print("\n🔍 STEP 4: Finding Portfolio URL...")
        portfolio_url = self.query_portfolio_url(
            collection, resume_data
        )

        if not portfolio_url:
            print(
                "  Not found in resume — checking GitHub..."
            )
            portfolio_url = self.extract_portfolio_from_github(
                github_data
            )

        if portfolio_url:
            # ✅ Found — proceed immediately
            print(
                f"  ✅ Portfolio URL found: {portfolio_url}"
            )
        else:
            # ❌ Not found — ask user
            print(
                "  ⚠️  No Portfolio URL found automatically"
            )
            portfolio_url = self.prompt_for_link(
                link_type="Portfolio",
                description=(
                    "No portfolio URL was found in your "
                    "resume.\nThis may be because your "
                    "portfolio link is a hyperlink with "
                    "display text only."
                )
            )
            if not portfolio_url:
                print(
                    "  ⏭️  Skipping portfolio — no URL provided"
                )

        # ── Step 5: Scrape Portfolio ──────────────────────
        print("\n🌐 STEP 5: Portfolio Sub-Agent")
        portfolio_data = {}
        if portfolio_url:
            print(f"  🚀 Starting portfolio scraping...")
            portfolio_data = self.scrape_portfolio(
                portfolio_url
            )
        else:
            print("  ⏭️  No portfolio URL — skipping")

        # ── Step 6: Merge ─────────────────────────────────
        print("\n🔀 STEP 6: Merging all sources...")
        unified_profile = self.merge_profiles(
            resume_data, github_data, portfolio_data
        )
        print("  ✅ Profile merged!")

        # ── Step 7: Save ──────────────────────────────────
        print("\n💾 STEP 7: Saving outputs...")

        # Save JSON locally always
        os.makedirs("outputs", exist_ok=True)
        with open("outputs/candidate_profile.json", "w") as f:
            json.dump(unified_profile, f, indent=2)
        print("  ✅ Saved → outputs/candidate_profile.json")

        # Save to MongoDB if connection is available
        if mongo_ok:
            print("\n  📦 Saving to MongoDB...")
            try:
                self.setup_collections()
                profile_id = self.save_to_mongodb(
                    unified_profile
                )
                print(
                    f"  ✅ Saved to MongoDB → "
                    f"profile ID: {profile_id}"
                )
            except Exception as e:
                print(f"  ❌ MongoDB save failed!")
                print(f"  Error: {e}")
                traceback.print_exc()
                print(
                    "  ⚠️  Profile still saved "
                    "locally as JSON"
                )
        else:
            print(
                "\n  ⚠️  Skipping MongoDB — "
                "connection not available"
            )

        # ── Step 8: Summary ───────────────────────────────
        self.print_summary(unified_profile)

        return unified_profile


# ══════════════════════════════════════════════════════════
#                        ENTRY POINT
# ══════════════════════════════════════════════════════════

if __name__ == "__main__":
    agent = Agent1()
    agent.run()