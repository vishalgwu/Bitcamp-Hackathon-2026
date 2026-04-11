import requests
import base64
import os
import time
import json
import threading
import concurrent.futures
from google import genai
from dotenv import load_dotenv

load_dotenv()

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")

# ─── Separate API Keys ────────────────────────────────────
# GEMINI_API_KEY     → resume parsing + portfolio scraping
# GEMINI_CODE_KEY    → github code analysis only
# Falls back to GEMINI_API_KEY if CODE_KEY not set

_code_api_key = (
    os.environ.get("GEMINI_CODE_KEY") or
    os.environ.get("GEMINI_API_KEY")
)
client = genai.Client(api_key=_code_api_key)

HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept":        "application/vnd.github.v3+json"
}

# ─── Thread Safety ────────────────────────────────────────

_print_lock = threading.Lock()
_cache      = {}
_cache_lock = threading.Lock()

def safe_print(msg):
    with _print_lock:
        print(msg)

# ─── Cached GitHub API ────────────────────────────────────

def cached_get(url):
    with _cache_lock:
        if url in _cache:
            return _cache[url]

    r = requests.get(url, headers=HEADERS)

    with _cache_lock:
        _cache[url] = r

    return r

# ─── Code File Config ─────────────────────────────────────

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

# ─── Profile + Repo Fetchers ──────────────────────────────

def get_profile(username):
    r = cached_get(f"https://api.github.com/users/{username}")
    return r.json()

def get_repos(username):
    r = cached_get(
        f"https://api.github.com/users/{username}/repos"
        f"?per_page=100&sort=updated"
    )
    return r.json() if r.status_code == 200 else []

def get_default_branch(username, repo_name):
    r = cached_get(
        f"https://api.github.com/repos/{username}/{repo_name}"
    )
    if r.status_code == 200:
        return r.json().get("default_branch", "main")
    return "main"

def get_readme(username, repo_name):
    r = cached_get(
        f"https://api.github.com/repos/{username}/{repo_name}/readme"
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

def get_languages(username, repo_name):
    r = cached_get(
        f"https://api.github.com/repos/{username}/{repo_name}/languages"
    )
    return list(r.json().keys()) if r.status_code == 200 else []

def get_commit_count(username, repo_name):
    r = requests.get(
        f"https://api.github.com/repos/{username}/{repo_name}"
        f"/commits?per_page=1",
        headers=HEADERS
    )
    if r.status_code == 200:
        if "Link" in r.headers:
            try:
                last_page = r.headers["Link"].split(",")[-1]
                count     = int(
                    last_page.split("page=")[-1].split(">")[0]
                )
                return count
            except:
                return len(r.json())
        return len(r.json())
    return 0

# ─── Code File Fetcher ────────────────────────────────────

def get_repo_files(username, repo_name, max_files=5):
    default_branch = get_default_branch(username, repo_name)

    branches_to_try = list(dict.fromkeys(
        [default_branch, "main", "master", "HEAD"]
    ))

    tree = []
    for branch in branches_to_try:
        r = cached_get(
            f"https://api.github.com/repos/{username}/{repo_name}"
            f"/git/trees/{branch}?recursive=1"
        )

        if r.status_code != 200:
            safe_print(
                f"    ⚠️  {repo_name}: branch '{branch}' "
                f"returned {r.status_code}, trying next..."
            )
            continue

        data = r.json()

        if data.get("truncated"):
            safe_print(
                f"    ⚠️  {repo_name}: file tree truncated "
                f"— falling back to contents API"
            )
            r2 = cached_get(
                f"https://api.github.com/repos/{username}/{repo_name}/contents"
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
                    safe_print(
                        f"    📂 {repo_name}: got {len(tree)} "
                        f"top-level files via contents API"
                    )
                    break
        else:
            tree = data.get("tree", [])
            safe_print(
                f"    📂 {repo_name}: got {len(tree)} items "
                f"on branch '{branch}'"
            )
            break

    if not tree:
        safe_print(
            f"    ❌ {repo_name}: could not fetch "
            f"file tree from any branch"
        )
        return []

    files = []
    for item in tree:
        if item.get("type") != "blob":
            continue

        path = item.get("path", "")

        if any(skip in path for skip in SKIP_PATTERNS):
            continue

        ext = os.path.splitext(path)[1].lower()
        if ext not in CODE_EXTENSIONS:
            continue

        if item.get("size", 0) > 100000:
            continue

        files.append(path)

        if len(files) >= max_files:
            break

    safe_print(
        f"    📄 {repo_name}: selected {len(files)} "
        f"code files → {files}"
    )
    return files

def extract_ipynb_code(content):
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

def get_file_content(username, repo_name, file_path):
    content = ""

    r = cached_get(
        f"https://api.github.com/repos/{username}/{repo_name}"
        f"/contents/{file_path}"
    )

    if r.status_code == 200:
        data = r.json()
        if isinstance(data, dict):
            if data.get("encoding") == "base64":
                try:
                    content = base64.b64decode(
                        data["content"].replace("\n", "")
                    ).decode("utf-8", errors="replace")
                except Exception as e:
                    safe_print(
                        f"    ⚠️  {file_path}: base64 decode "
                        f"failed — {e}"
                    )
            elif data.get("content"):
                content = data["content"]

    if not content:
        raw_url = (
            f"https://raw.githubusercontent.com/"
            f"{username}/{repo_name}/HEAD/{file_path}"
        )
        try:
            r2 = requests.get(
                raw_url,
                headers={"Authorization": f"token {GITHUB_TOKEN}"},
                timeout=10
            )
            if r2.status_code == 200:
                content = r2.text
                safe_print(
                    f"    🔄 {file_path}: fetched via raw URL"
                )
        except Exception as e:
            safe_print(
                f"    ⚠️  raw URL failed for {file_path}: {e}"
            )

    if not content:
        safe_print(f"    ❌ Could not fetch: {file_path}")
        return ""

    if file_path.endswith(".ipynb"):
        safe_print(
            f"    📓 {file_path}: extracting code cells..."
        )
        content = extract_ipynb_code(content)

    return content

# ─── Gemini Code Analyzer ─────────────────────────────────

def analyze_code_with_gemini(repo_name, code_samples):
    """
    Uses GEMINI_CODE_KEY (separate from resume parsing key)
    to analyze code samples and return structured insights.
    """
    if not code_samples:
        return {}

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
                safe_print(
                    f"    🤖 {repo_name}: trying {model_name} "
                    f"(attempt {attempt + 1}/3)..."
                )

                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt
                )

                usage = response.usage_metadata
                safe_print(
                    f"    📊 {repo_name}: tokens used = "
                    f"{usage.total_token_count}"
                )

                raw = response.text.strip()
                raw = raw.replace("```json", "").replace("```", "").strip()
                result = json.loads(raw)

                safe_print(f"    ✅ {repo_name}: analysis complete")
                return result

            except Exception as e:
                error_str = str(e)

                if "429" in error_str:
                    safe_print(
                        f"    ❌ {repo_name}: quota exhausted on "
                        f"{model_name} — waiting 30s before next model..."
                    )
                    time.sleep(30)
                    break

                elif "503" in error_str or "UNAVAILABLE" in error_str:
                    if attempt < 2:
                        wait = 30 * (attempt + 1)
                        safe_print(
                            f"    ⚠️  {repo_name}: {model_name} unavailable, "
                            f"waiting {wait}s..."
                        )
                        time.sleep(wait)
                    else:
                        safe_print(
                            f"    ❌ {repo_name}: {model_name} still "
                            f"unavailable, trying next..."
                        )
                        break

                elif "404" in error_str or "NOT_FOUND" in error_str:
                    safe_print(
                        f"    ❌ {repo_name}: {model_name} not found, "
                        f"trying next..."
                    )
                    break

                else:
                    safe_print(
                        f"    ❌ {repo_name}: unexpected error — {e}"
                    )
                    raise e

    safe_print(
        f"    ⚠️  {repo_name}: all models failed — "
        f"returning empty insights"
    )
    return {}

# ─── Phase 1: Fetch All Repo Code in Parallel ────────────

def fetch_repo_code(username, repo_name, max_files=5):
    safe_print(f"\n    📂 Fetching: {repo_name}")

    file_paths = get_repo_files(username, repo_name, max_files)

    if not file_paths:
        safe_print(f"    ⚠️  {repo_name}: no code files found")
        return repo_name, {}

    code_samples = {}
    for path in file_paths:
        content = get_file_content(username, repo_name, path)
        if content and content.strip():
            code_samples[path] = content
            safe_print(
                f"    📥 {repo_name}: ✅ {path} "
                f"({len(content)} chars)"
            )
        else:
            safe_print(
                f"    📥 {repo_name}: ⚠️  {path} — empty"
            )

    if not code_samples:
        safe_print(f"    ⚠️  {repo_name}: all files empty")

    return repo_name, code_samples


def fetch_all_repos_parallel(username, repos, max_workers=5):
    """
    Fetches code from ALL repos in parallel.
    No Gemini calls — just GitHub API.
    Returns dict of repo_name → code_samples
    """
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
                fetch_repo_code,
                username,
                repo["name"]
            ): repo["name"]
            for repo in repos
        }

        completed = 0
        for future in concurrent.futures.as_completed(future_to_repo):
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
                    f"  📥 Fetched ({completed}/{num_repos}): "
                    f"{name} — {status}"
                )
            except Exception as e:
                print(
                    f"  ❌ Fetch failed ({completed}/{num_repos}): "
                    f"{repo_name} — {e}"
                )
                results[repo_name] = {}

    repos_with_code = sum(1 for v in results.values() if v)
    print(
        f"  ✅ Fetch complete — "
        f"{repos_with_code}/{num_repos} repos had code"
    )
    return results

# ─── Phase 2: Analyze Sequentially with Rate Limiting ────

def analyze_all_repos_sequential(repos_with_code, delay_between_calls=3):
    """
    Analyzes repos SEQUENTIALLY using GEMINI_CODE_KEY.
    Small delay between each call to avoid quota exhaustion.
    Returns dict of repo_name → insights
    """
    results   = {}
    num_repos = len(repos_with_code)
    completed = 0

    print(
        f"\n  🤖 Analyzing {num_repos} repos with Gemini "
        f"(sequential, {delay_between_calls}s delay between calls)..."
    )
    print(
        f"  ⏱️  Estimated: ~{num_repos * (30 + delay_between_calls)}s"
    )
    print(
        f"  🔑 Using GEMINI_CODE_KEY "
        f"(separate from resume parsing key)"
    )

    for repo_name, code_samples in repos_with_code.items():
        completed += 1
        print(
            f"\n  🤖 Analyzing ({completed}/{num_repos}): {repo_name}..."
        )

        try:
            insights           = analyze_code_with_gemini(
                repo_name, code_samples
            )
            results[repo_name] = insights

            if insights:
                print(
                    f"  ✅ Done ({completed}/{num_repos}): "
                    f"{repo_name} — got insights"
                )
            else:
                print(
                    f"  ⚠️  Done ({completed}/{num_repos}): "
                    f"{repo_name} — empty insights"
                )

        except Exception as e:
            print(
                f"  ❌ Failed ({completed}/{num_repos}): "
                f"{repo_name} — {e}"
            )
            results[repo_name] = {}

        # Delay between calls to respect rate limits
        if completed < num_repos:
            print(
                f"  ⏳ Waiting {delay_between_calls}s "
                f"before next analysis..."
            )
            time.sleep(delay_between_calls)

    repos_with_insights = sum(1 for v in results.values() if v)
    print(
        f"\n  ✅ Analysis complete — "
        f"{repos_with_insights}/{num_repos} repos got insights"
    )
    return results

# ─── Main Scraper ─────────────────────────────────────────

def scrape_github(github_url, analyze_code=True, max_repos_to_analyze=0):
    """
    Scrapes a GitHub profile.

    Two phase approach:
      Phase 1 — fetch all repo code in parallel
                 (GitHub API only, 5 workers, fast)
      Phase 2 — analyze all code sequentially
                 (GEMINI_CODE_KEY, with delays, reliable)

    max_repos_to_analyze:
      0 = analyze ALL non-fork repos (default)
      N = analyze top N repos by commit count
    """
    if not github_url:
        print("  ⚠️  No GitHub URL provided — skipping")
        return {}

    username = github_url.rstrip("/").split("/")[-1]
    print(f"  Scraping GitHub profile: {username}")

    # Show which key is being used
    if os.environ.get("GEMINI_CODE_KEY"):
        print(f"  🔑 Using dedicated GEMINI_CODE_KEY for code analysis")
    else:
        print(f"  🔑 Using GEMINI_API_KEY for code analysis (no CODE_KEY set)")

    # ── Profile ───────────────────────────────────────────
    profile = get_profile(username)

    if "message" in profile and profile["message"] == "Not Found":
        print(f"  ❌ GitHub user '{username}' not found")
        return {}

    # ── Repos ─────────────────────────────────────────────
    repos = get_repos(username)

    if not isinstance(repos, list):
        print(f"  ❌ Could not fetch repos for '{username}'")
        return {}

    print(f"  Found {len(repos)} repositories — scanning metadata...")

    # ── Repo Details ──────────────────────────────────────
    repo_details = []
    for i, repo in enumerate(repos):
        name = repo["name"]
        print(f"    [{i+1}/{len(repos)}] {name}")

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

        time.sleep(0.2)

    # ── Code Analysis ─────────────────────────────────────
    repos_analyzed_count = 0

    if analyze_code:
        non_fork_repos = sorted(
            [r for r in repo_details if not r["is_fork"]],
            key=lambda x: x["commit_count"],
            reverse=True
        )

        if max_repos_to_analyze and max_repos_to_analyze > 0:
            repos_to_process = non_fork_repos[:max_repos_to_analyze]
            print(
                f"\n  🔍 Analyzing top {len(repos_to_process)} "
                f"repos by commit count"
            )
        else:
            repos_to_process = non_fork_repos
            print(
                f"\n  🔍 Analyzing ALL {len(repos_to_process)} "
                f"non-fork repos"
            )

        if repos_to_process:

            # ── Phase 1: Fetch all code in parallel ───────
            all_code = fetch_all_repos_parallel(
                username,
                repos_to_process,
                max_workers=5
            )

            # Filter only repos that have code
            repos_with_code = {
                name: samples
                for name, samples in all_code.items()
                if samples
            }

            print(
                f"\n  📊 {len(repos_with_code)}/{len(repos_to_process)} "
                f"repos have analyzable code"
            )

            # ── Phase 2: Analyze sequentially ─────────────
            if repos_with_code:
                all_insights = analyze_all_repos_sequential(
                    repos_with_code,
                    delay_between_calls=3
                )

                # Store results back into repo_details
                for repo in repo_details:
                    name = repo["name"]

                    if name in all_code and all_code[name]:
                        repo["code_samples"] = {
                            path: content[:500]
                            for path, content
                            in all_code[name].items()
                        }

                    if name in all_insights and all_insights[name]:
                        repo["code_insights"]  = all_insights[name]
                        repos_analyzed_count  += 1
            else:
                print("  ⚠️  No repos had analyzable code")
        else:
            print("  ⚠️  No non-fork repos found")

    # ── Aggregate Results ─────────────────────────────────
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

    # ── Final Result ──────────────────────────────────────
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
            "skills_from_code":      list(set(all_skills_from_code)),
            "architecture_patterns": list(set(all_patterns)),
            "best_practices":        list(set(all_best_practices))
        }
    }

    print(f"\n  ✅ GitHub scraping complete")
    print(f"     Username    : {username}")
    print(f"     Repos       : {len(repo_details)}")
    print(f"     Languages   : {', '.join(all_languages[:8])}")
    print(f"     Followers   : {profile.get('followers')}")
    if analyze_code:
        print(
            f"     Analyzed    : {repos_analyzed_count} repos with insights"
        )
        if all_skills_from_code:
            print(
                f"     Code skills : "
                f"{', '.join(list(set(all_skills_from_code))[:5])}"
            )

    return result