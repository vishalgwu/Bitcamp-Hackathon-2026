import requests
import base64
import os
import time
import json
from google import genai
from dotenv import load_dotenv

load_dotenv()

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
client       = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

headers = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept":        "application/vnd.github.v3+json"
}

# ─── Individual Fetchers ──────────────────────────────────

def get_profile(username):
    r = requests.get(
        f"https://api.github.com/users/{username}",
        headers=headers
    )
    return r.json()

def get_repos(username):
    r = requests.get(
        f"https://api.github.com/users/{username}/repos?per_page=100",
        headers=headers
    )
    return r.json()

def get_readme(username, repo_name):
    r = requests.get(
        f"https://api.github.com/repos/{username}/{repo_name}/readme",
        headers=headers
    )
    if r.status_code == 200:
        content = base64.b64decode(r.json()["content"]).decode("utf-8")
        return content[:1000]
    return ""

def get_languages(username, repo_name):
    r = requests.get(
        f"https://api.github.com/repos/{username}/{repo_name}/languages",
        headers=headers
    )
    return list(r.json().keys()) if r.status_code == 200 else []

def get_commit_count(username, repo_name):
    r = requests.get(
        f"https://api.github.com/repos/{username}/{repo_name}/commits?per_page=1",
        headers=headers
    )
    if r.status_code == 200 and "Link" in r.headers:
        try:
            last_page = r.headers["Link"].split(",")[-1]
            count     = int(last_page.split("page=")[-1].split(">")[0])
            return count
        except:
            return len(r.json())
    return len(r.json()) if r.status_code == 200 else 0

# ─── Code Fetcher ─────────────────────────────────────────

def get_repo_files(username, repo_name, max_files=5):
    """
    Fetches actual source code files from the repo.
    Focuses on meaningful code files — skips configs,
    lock files, images, notebooks etc.
    Limits to max_files to stay within token budget.
    """

    # Extensions we care about for code analysis
    code_extensions = {
        ".py", ".js", ".ts", ".jsx", ".tsx",
        ".java", ".cpp", ".c", ".cs", ".go",
        ".r", ".R", ".sql", ".php", ".rb",
        ".swift", ".kt", ".scala", ".rs"
    }

    # Files to skip
    skip_patterns = [
        "package-lock.json", "yarn.lock", ".gitignore",
        "requirements.txt", "setup.py", "config.",
        "LICENSE", "CHANGELOG", ".env", "test_",
        "_test.", "spec.", ".min.js"
    ]

    # Get file tree
    r = requests.get(
        f"https://api.github.com/repos/{username}/{repo_name}/git/trees/HEAD?recursive=1",
        headers=headers
    )

    if r.status_code != 200:
        return []

    tree  = r.json().get("tree", [])
    files = []

    for item in tree:
        if item["type"] != "blob":
            continue

        path = item["path"]

        # Skip unwanted files
        if any(skip in path for skip in skip_patterns):
            continue

        # Only include code files
        ext = os.path.splitext(path)[1].lower()
        if ext not in code_extensions:
            continue

        # Skip files that are too large (> 100KB)
        if item.get("size", 0) > 100000:
            continue

        files.append(path)

        if len(files) >= max_files:
            break

    return files

def get_file_content(username, repo_name, file_path):
    """Fetch content of a specific file"""
    r = requests.get(
        f"https://api.github.com/repos/{username}/{repo_name}/contents/{file_path}",
        headers=headers
    )
    if r.status_code == 200:
        data = r.json()
        if data.get("encoding") == "base64":
            try:
                return base64.b64decode(data["content"]).decode("utf-8")
            except:
                return ""
    return ""

# ─── Code Analyzer ────────────────────────────────────────

def analyze_code_with_gemini(repo_name, code_samples):
    """
    Uses Gemini to analyze code samples from a repo
    and extract insights about:
    - Code quality
    - Patterns and architecture
    - Technical complexity
    - Skills demonstrated
    """

    if not code_samples:
        return {}

    # Build code context string
    code_context = ""
    for file_path, content in code_samples.items():
        code_context += f"\n\n--- File: {file_path} ---\n{content[:1500]}"

    prompt = f"""
    You are a senior software engineer reviewing code from a GitHub repository.
    Analyze the following code samples from the repository "{repo_name}" and 
    provide insights.
    
    Return ONLY a valid JSON object — no markdown, no extra text:
    
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
    
    Scoring guide:
    - score is 1-10
    - rating is one of: Beginner, Intermediate, Advanced, Expert
    
    Code samples:
    {code_context}
    """

    models_to_try = [
        "models/gemini-2.0-flash",
        "models/gemini-2.5-flash",
        "models/gemini-2.0-flash-lite",
        "models/gemini-2.5-flash-lite"
    ]

    for model_name in models_to_try:
        for attempt in range(3):
            try:
                print(f"    Analyzing code with {model_name}...")
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt
                )

                # Token usage
                usage = response.usage_metadata
                print(f"    Tokens used: {usage.total_token_count}")

                raw = response.text.strip()
                raw = raw.replace("```json", "").replace("```", "").strip()
                result = json.loads(raw)
                print(f"    ✅ Code analysis complete")
                return result

            except Exception as e:
                error_str = str(e)
                if "429" in error_str:
                    print(f"    ❌ Quota exhausted on {model_name}, trying next...")
                    break
                elif "503" in error_str or "UNAVAILABLE" in error_str:
                    if attempt < 2:
                        wait = 30 * (attempt + 1)
                        print(f"    ⚠️  {model_name} unavailable. Waiting {wait}s...")
                        time.sleep(wait)
                    else:
                        print(f"    ❌ {model_name} still unavailable, trying next...")
                        break
                elif "404" in error_str or "NOT_FOUND" in error_str:
                    print(f"    ❌ {model_name} not found, trying next...")
                    break
                else:
                    raise e

    return {}

def fetch_and_analyze_repo(username, repo_name, max_files=5):
    """
    Fetches code files from a repo and
    runs Gemini analysis on them.
    Returns code samples + insights.
    """
    print(f"    Fetching code files from: {repo_name}")

    # Get list of code files
    file_paths = get_repo_files(username, repo_name, max_files)

    if not file_paths:
        print(f"    ⚠️  No code files found in {repo_name}")
        return {}, {}

    print(f"    Found {len(file_paths)} code files: {file_paths}")

    # Fetch content of each file
    code_samples = {}
    for path in file_paths:
        content = get_file_content(username, repo_name, path)
        if content:
            code_samples[path] = content
            print(f"    ✅ Fetched: {path} ({len(content)} chars)")
        time.sleep(0.2)  # rate limit safety

    if not code_samples:
        print(f"    ⚠️  Could not fetch any code content")
        return {}, {}

    # Analyze with Gemini
    insights = analyze_code_with_gemini(repo_name, code_samples)

    return code_samples, insights

# ─── Main Scraper ─────────────────────────────────────────

def scrape_github(github_url, analyze_code=True, max_repos_to_analyze=3):
    """
    Scrapes a GitHub profile.
    If analyze_code=True, fetches and analyzes code
    from the top repos using Gemini.

    max_repos_to_analyze: how many repos to run code
    analysis on (to manage API quota)
    """
    if not github_url:
        print("  ⚠️  No GitHub URL provided — skipping")
        return {}

    username = github_url.rstrip("/").split("/")[-1]
    print(f"  Scraping GitHub profile: {username}")

    # Profile
    profile = get_profile(username)

    if "message" in profile and profile["message"] == "Not Found":
        print(f"  ❌ GitHub user '{username}' not found")
        return {}

    # Repos
    repos = get_repos(username)
    print(f"  Found {len(repos)} repositories")

    repo_details = []
    for i, repo in enumerate(repos):
        name = repo["name"]
        print(f"    Scanning {i+1}/{len(repos)}: {name}")
        time.sleep(0.3)

        repo_details.append({
            "name":           name,
            "description":    repo.get("description"),
            "languages":      get_languages(username, name),
            "stars":          repo.get("stargazers_count", 0),
            "forks":          repo.get("forks_count", 0),
            "commit_count":   get_commit_count(username, name),
            "last_updated":   repo.get("updated_at"),
            "readme_preview": get_readme(username, name),
            "topics":         repo.get("topics", []),
            "has_live_demo":  bool(repo.get("homepage")),
            "homepage":       repo.get("homepage", ""),
            "is_fork":        repo.get("fork", False),
            "code_samples":   {},
            "code_insights":  {}
        })

    # Code analysis on top repos
    if analyze_code:
        # Sort by commit count — most active repos first
        repos_to_analyze = sorted(
            [r for r in repo_details if not r["is_fork"]],
            key=lambda x: x["commit_count"],
            reverse=True
        )[:max_repos_to_analyze]

        print(f"\n  🔍 Analyzing code from top {len(repos_to_analyze)} repos...")

        for repo in repos_to_analyze:
            name = repo["name"]
            print(f"\n  Analyzing repo: {name}")

            code_samples, insights = fetch_and_analyze_repo(
                username, name
            )

            # Store in repo_details
            for r in repo_details:
                if r["name"] == name:
                    r["code_samples"] = {
                        path: content[:500]  # store preview only
                        for path, content in code_samples.items()
                    }
                    r["code_insights"] = insights
                    break

    # Collect all unique languages
    all_languages = list(set(
        lang
        for repo in repo_details
        for lang in repo["languages"]
    ))

    # Top repos by stars
    top_repos = sorted(
        repo_details,
        key=lambda x: x["stars"],
        reverse=True
    )[:5]

    # Aggregate code insights across all analyzed repos
    all_skills_from_code = []
    all_patterns         = []
    all_best_practices   = []

    for repo in repo_details:
        insights = repo.get("code_insights", {})
        if insights:
            all_skills_from_code.extend(
                insights.get("skills_demonstrated", [])
            )
            all_patterns.extend(
                insights.get("architecture_patterns", [])
            )
            all_best_practices.extend(
                insights.get("best_practices_used", [])
            )

    result = {
        "username":          username,
        "name":              profile.get("name"),
        "bio":               profile.get("bio"),
        "location":          profile.get("location"),
        "email":             profile.get("email"),
        "website":           profile.get("blog"),
        "followers":         profile.get("followers"),
        "following":         profile.get("following"),
        "public_repos":      profile.get("public_repos"),
        "github_url":        f"https://github.com/{username}",
        "all_languages":     all_languages,
        "top_repos":         top_repos,
        "repositories":      repo_details,
        "code_analysis": {
            "repos_analyzed":      len(repos_to_analyze) if analyze_code else 0,
            "skills_from_code":    list(set(all_skills_from_code)),
            "architecture_patterns": list(set(all_patterns)),
            "best_practices":      list(set(all_best_practices))
        }
    }

    print(f"\n  ✅ GitHub scraping complete")
    print(f"     Repos     : {len(repo_details)}")
    print(f"     Languages : {', '.join(all_languages)}")
    print(f"     Followers : {profile.get('followers')}")
    if analyze_code:
        print(f"     Code analyzed : {len(repos_to_analyze)} repos")
        print(f"     Skills from code: {', '.join(list(set(all_skills_from_code))[:5])}")

    return result