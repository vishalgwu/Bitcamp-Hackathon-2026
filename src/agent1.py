import os
import json
import sys
import tkinter as tk
from tkinter import filedialog, simpledialog, messagebox
from dotenv import load_dotenv

load_dotenv()

# Add helpers to path
sys.path.append(os.path.join(os.path.dirname(__file__), "helpers"))

from helper.resume_parser     import parse_resume
from helper.github_scraper    import scrape_github, get_profile
from helper.portfolio_scraper import scrape_portfolio
from helper.rag_extractor     import (
    build_vectorstore,
    query_github_url,
    query_linkedin_url,
    query_portfolio_url,
    extract_portfolio_from_github
)
from helper.db import get_db, create_collections, save_student_profile

# ─── Profile Merger ───────────────────────────────────────

def merge_profiles(resume_data, github_data, portfolio_data):

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
            "readme":        repo.get("readme_preview", ""),
            "topics":        repo.get("topics", []),
            "has_live_demo": repo.get("has_live_demo", False),
            "homepage":      repo.get("homepage", ""),
            "is_fork":       repo.get("is_fork", False),
            "code_samples":  repo.get("code_samples", {}),
            "code_insights": repo.get("code_insights", {})
        }
        for repo in github_data.get("repositories", [])
    ]

    return {
        "candidate": {
            "name":     (
                resume_data.get("name") or
                github_data.get("name")
            ),
            "email":    (
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
        "certifications": resume_data.get("certifications", []),
        "projects": {
            "from_resume":    resume_data.get("projects", []),
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
            "structured": portfolio_data.get("structured", {})
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

# ─── Link Prompt Helper ───────────────────────────────────

def prompt_for_link(link_type, description):
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)

    want_to_provide = messagebox.askyesno(
        title=f"{link_type} URL Not Found",
        message=(
            f"{description}\n\n"
            f"Would you like to provide your {link_type} URL?"
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
        print(f"  ✅ User provided {link_type} URL: {url}")
        return url

    print(f"  ⏭️  User did not enter a {link_type} URL — skipping")
    return None

# ─── GitHub Scraper Helper ────────────────────────────────

def scrape_github_profile(github_url):
    if not github_url:
        return {}

    username     = github_url.rstrip("/").split("/")[-1]
    _profile     = get_profile(username)
    public_repos = _profile.get("public_repos", 0)

    if public_repos > 200:
        print(
            f"\n  ⚠️  This account has {public_repos} repos "
            f"— looks like an org not a person"
        )
        confirm = input(
            "  Are you sure this is the right GitHub URL? (y/n): "
        ).strip().lower()
        if confirm != "y":
            print("  ⏭️  Skipping GitHub scraping.")
            return {}

    print(f"  🚀 Starting GitHub scraping + code analysis...")

    return scrape_github(
        github_url,
        analyze_code=True,
        max_repos_to_analyze=0
    )

# ─── Print Summary ────────────────────────────────────────

def print_summary(unified_profile, portfolio_url):

    print("\n" + "=" * 55)
    print("              AGENT 1 COMPLETE ✅")
    print("=" * 55)

    print("\n👤 CANDIDATE")
    print(f"  Name     : {unified_profile['candidate']['name']}")
    print(f"  Email    : {unified_profile['candidate']['email']}")
    print(f"  Phone    : {unified_profile['candidate']['phone']}")
    print(f"  Location : {unified_profile['candidate']['location']}")

    print("\n🛠️  SKILLS")
    print(f"  Total unique   : {len(unified_profile['skills']['all'])}")
    print(f"  From resume    : {len(unified_profile['skills']['from_resume'])} skills")
    print(f"  From GitHub    : {len(unified_profile['skills']['from_github'])} languages")
    print(f"  From portfolio : {len(unified_profile['skills']['from_portfolio'])} skills")
    print(f"  From code      : {len(unified_profile['skills']['from_code'])} skills")

    print("\n💼 EXPERIENCE")
    for exp in unified_profile.get("experience", []):
        print(f"  • {exp.get('role')} @ {exp.get('company')} ({exp.get('duration')})")

    print("\n🎓 EDUCATION")
    for edu in unified_profile.get("education", []):
        print(f"  • {edu.get('degree')} in {edu.get('field')} — {edu.get('institution')} ({edu.get('year')})")

    print("\n📜 CERTIFICATIONS")
    for cert in unified_profile.get("certifications", []):
        print(f"  • {cert}")

    print("\n📁 PROJECTS FROM RESUME")
    for proj in unified_profile["projects"].get("from_resume", []):
        print(f"  • {proj.get('name')}")

    print("\n🐙 GITHUB PROFILE")
    print(f"  Username     : {unified_profile['github_profile'].get('username')}")
    print(f"  Public repos : {unified_profile['github_profile'].get('public_repos')}")
    print(f"  Followers    : {unified_profile['github_profile'].get('followers')}")

    all_github = unified_profile["projects"].get("from_github", [])
    print(f"\n  All GitHub Repos ({len(all_github)} total):")
    for repo in all_github:
        insights = repo.get("code_insights", {})
        cq       = insights.get("code_quality", {})
        rating   = cq.get("rating", "")
        score    = cq.get("score", "")
        insight_str = f" → {rating} ({score}/10)" if rating else ""
        print(f"  • {repo['name']}{insight_str}")

    code_analysis  = unified_profile.get("code_analysis", {})
    repos_analyzed = code_analysis.get("repos_analyzed", 0)
    print("\n🔍 CODE ANALYSIS")
    if repos_analyzed == 0:
        print("  ⚠️  No code analysis was run")
    else:
        print(f"  Repos analyzed : {repos_analyzed}")

    print("\n🌐 PORTFOLIO")
    if unified_profile["portfolio"].get("url"):
        print(f"  URL : {unified_profile['portfolio']['url']}")
    else:
        print("  ❌ Not found")

    print("\n📊 SOURCES USED")
    for source, used in unified_profile["sources_used"].items():
        status = "✅" if used else "❌"
        print(f"  {status} {source.capitalize()}")

    print("\n🔗 LINKS")
    print(f"  GitHub    : {unified_profile['links'].get('github')    or 'Not found'}")
    print(f"  Portfolio : {unified_profile['links'].get('portfolio') or 'Not found'}")
    print(f"  LinkedIn  : {unified_profile['links'].get('linkedin')  or 'Not found'}")

    print("\n" + "=" * 55)
    print("  ✅ Saved → outputs/candidate_profile.json")
    print("  ✅ Saved → MongoDB student_profiles")
    print("  ✅ Ready for Agent 2")
    print("=" * 55)

# ─── Main Runner ──────────────────────────────────────────

def run_agent1():
    print("\n" + "=" * 55)
    print("          AGENT 1 — PROFILE AGGREGATOR")
    print("=" * 55)

    # ── Step 1: Resume Input ──────────────────────────────
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
        resume_data = parse_resume(file_bytes, filename=filename)

    elif choice == "2":
        print("\n  Paste resume text. Type 'END' when done:\n")
        lines = []
        while True:
            line = input()
            if line.strip() == "END":
                break
            lines.append(line)
        resume_data = parse_resume("\n".join(lines))

    else:
        print("  Invalid choice. Exiting.")
        return

    print(f"\n  ✅ Resume parsed: {resume_data.get('name')}")

    # ── Step 2: Build RAG + Extract Links ─────────────────
    print("\n🔍 STEP 2: Building RAG vector store...")
    collection   = build_vectorstore(resume_data)
    github_url   = query_github_url(collection, resume_data)
    linkedin_url = query_linkedin_url(collection, resume_data)

    # ── Step 3: GitHub — Auto or Prompt ───────────────────
    print("\n🐙 STEP 3: GitHub Sub-Agent")
    github_data = {}

    if github_url:
        # ✅ Found — proceed immediately
        print(f"  ✅ GitHub URL found: {github_url}")
        github_data = scrape_github_profile(github_url)

    else:
        # ❌ Not found — ask user
        print("  ⚠️  No GitHub URL found automatically")
        github_url = prompt_for_link(
            link_type="GitHub",
            description=(
                "No GitHub URL was found in your resume.\n"
                "This may be because your GitHub link is a hyperlink\n"
                "with display text only (e.g. 'GitHub' instead of the URL)."
            )
        )

        if github_url:
            github_data = scrape_github_profile(github_url)
        else:
            print("  ⏭️  Skipping GitHub scraping — no URL provided")

    # ── Step 4: Find Portfolio — Auto or Prompt ───────────
    print("\n🔍 STEP 4: Finding Portfolio URL...")
    portfolio_url = query_portfolio_url(collection, resume_data)

    if not portfolio_url:
        print("  Not found in resume — checking GitHub repos...")
        portfolio_url = extract_portfolio_from_github(github_data)

    if portfolio_url:
        # ✅ Found — proceed immediately
        print(f"  ✅ Portfolio URL found: {portfolio_url}")

    else:
        # ❌ Not found — ask user
        print("  ⚠️  No Portfolio URL found automatically")
        portfolio_url = prompt_for_link(
            link_type="Portfolio",
            description=(
                "No portfolio/personal website URL was found in your resume.\n"
                "This may be because your portfolio link is a hyperlink\n"
                "with display text only."
            )
        )

        if not portfolio_url:
            print("  ⏭️  Skipping portfolio scraping — no URL provided")

    # ── Step 5: Scrape Portfolio ──────────────────────────
    print("\n🌐 STEP 5: Portfolio Sub-Agent")
    portfolio_data = {}
    if portfolio_url:
        print(f"  🚀 Starting portfolio scraping...")
        portfolio_data = scrape_portfolio(portfolio_url)
    else:
        print("  ⏭️  No portfolio URL — skipping")

    # ── Step 6: Merge All Sources ─────────────────────────
    print("\n🔀 STEP 6: Merging all sources...")
    unified_profile = merge_profiles(
        resume_data,
        github_data,
        portfolio_data
    )
    print("  ✅ Profile merged!")

    # ── Step 7: Save to JSON + MongoDB ───────────────────
    print("\n💾 STEP 7: Saving outputs...")

    # Save JSON locally
    os.makedirs("outputs", exist_ok=True)
    with open("outputs/candidate_profile.json", "w") as f:
        json.dump(unified_profile, f, indent=2)
    print("  ✅ Saved → outputs/candidate_profile.json")

    # Save to MongoDB
    print("\n  📦 Saving to MongoDB...")
    try:
        db = get_db()
        create_collections(db)
        profile_id = save_student_profile(unified_profile)
        print(f"  ✅ Saved to MongoDB → profile ID: {profile_id}")
    except Exception as e:
        print(f"  ⚠️  MongoDB save failed: {e}")
        print(f"  ⚠️  Profile still saved locally as JSON")

    # ── Step 8: Print Summary ─────────────────────────────
    print_summary(unified_profile, portfolio_url)

    return unified_profile


if __name__ == "__main__":
    run_agent1()