import os
import json
import sys
import tkinter as tk
from tkinter import filedialog
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

# ─── Print Summary ────────────────────────────────────────

def print_summary(unified_profile, portfolio_url):

    print("\n" + "=" * 55)
    print("              AGENT 1 COMPLETE ✅")
    print("=" * 55)

    # ── Candidate ─────────────────────────────────────────
    print("\n👤 CANDIDATE")
    print(f"  Name     : {unified_profile['candidate']['name']}")
    print(f"  Email    : {unified_profile['candidate']['email']}")
    print(f"  Phone    : {unified_profile['candidate']['phone']}")
    print(f"  Location : {unified_profile['candidate']['location']}")
    print(f"  Summary  :")
    summary = unified_profile['candidate'].get('summary', 'N/A')
    for line in summary.split(". "):
        line = line.strip()
        if line:
            print(f"    {line}.")

    # ── Skills ────────────────────────────────────────────
    print("\n🛠️  SKILLS")
    print(f"  Total unique   : {len(unified_profile['skills']['all'])}")
    print(f"  From resume    : {', '.join(unified_profile['skills']['from_resume'])}")
    print(f"  From GitHub    : {', '.join(unified_profile['skills']['from_github'])}")
    port_skills = unified_profile['skills']['from_portfolio']
    print(f"  From portfolio : {', '.join(port_skills) if port_skills else 'None'}")
    code_skills = unified_profile['skills']['from_code']
    print(
        f"  From code      : "
        f"{', '.join(code_skills) if code_skills else 'None (no code analysis run)'}"
    )

    # ── Experience ────────────────────────────────────────
    print("\n💼 EXPERIENCE")
    for exp in unified_profile.get("experience", []):
        print(f"  ┌─────────────────────────────────────────────────")
        print(f"  │ Role        : {exp.get('role')}")
        print(f"  │ Company     : {exp.get('company')}")
        print(f"  │ Duration    : {exp.get('duration')}")
        print(f"  │ Location    : {exp.get('location', 'N/A')}")
        print(f"  │ Description :")
        desc = exp.get('description', 'N/A')
        for line in desc.split("\n"):
            line = line.strip()
            if line:
                print(f"  │   {line}")
        print(f"  └─────────────────────────────────────────────────")

    # ── Education ─────────────────────────────────────────
    print("\n🎓 EDUCATION")
    for edu in unified_profile.get("education", []):
        print(f"  ┌─────────────────────────────────────────────────")
        print(f"  │ Degree      : {edu.get('degree')}")
        print(f"  │ Field       : {edu.get('field')}")
        print(f"  │ Institution : {edu.get('institution')}")
        print(f"  │ Year        : {edu.get('year')}")
        print(f"  └─────────────────────────────────────────────────")

    # ── Certifications ────────────────────────────────────
    print("\n📜 CERTIFICATIONS")
    certs = unified_profile.get("certifications", [])
    if certs:
        for cert in certs:
            print(f"  • {cert}")
    else:
        print("  None")

    # ── Projects from Resume ──────────────────────────────
    print("\n📁 PROJECTS FROM RESUME")
    for proj in unified_profile["projects"].get("from_resume", []):
        techs = ", ".join(proj.get("technologies", [])) or "N/A"
        print(f"  ┌─────────────────────────────────────────────────")
        print(f"  │ Name         : {proj.get('name')}")
        print(f"  │ Technologies : {techs}")
        print(f"  │ Description  :")
        desc = proj.get("description", "N/A")
        for line in desc.split("\n"):
            line = line.strip()
            if line:
                print(f"  │   {line}")
        print(f"  └─────────────────────────────────────────────────")

    # ── GitHub Profile ────────────────────────────────────
    print("\n🐙 GITHUB PROFILE")
    print(f"  Username     : {unified_profile['github_profile'].get('username')}")
    print(f"  Bio          : {unified_profile['github_profile'].get('bio') or 'N/A'}")
    print(f"  Website      : {unified_profile['github_profile'].get('website') or 'N/A'}")
    print(f"  Followers    : {unified_profile['github_profile'].get('followers')}")
    print(f"  Following    : {unified_profile['github_profile'].get('following', 'N/A')}")
    print(f"  Public repos : {unified_profile['github_profile'].get('public_repos')}")
    print(f"  Languages    : {', '.join(unified_profile['skills']['from_github'])}")

    # Top Repos
    print("\n  📂 Top Repos:")
    for repo in unified_profile["github_profile"].get("top_repos", [])[:5]:
        langs  = ", ".join(repo.get("languages", [])) or "N/A"
        desc   = repo.get("description") or "No description"
        readme = (repo.get("readme_preview", "") or "")[:200]
        print(f"  ┌─────────────────────────────────────────────────")
        print(f"  │ Repo         : {repo['name']}")
        print(f"  │ Languages    : {langs}")
        print(f"  │ Commits      : {repo.get('commit_count', 0)}")
        print(f"  │ Stars        : {repo.get('stars', 0)}")
        print(f"  │ Forks        : {repo.get('forks', 0)}")
        print(f"  │ Last Updated : {repo.get('last_updated', 'N/A')}")
        print(f"  │ Has Demo     : {repo.get('has_live_demo', False)}")
        print(f"  │ Is Fork      : {repo.get('is_fork', False)}")
        print(f"  │ Description  : {desc}")
        if readme:
            print(f"  │ README Preview:")
            for line in readme.split("\n"):
                line = line.strip()
                if line:
                    print(f"  │   {line}")
        print(f"  └─────────────────────────────────────────────────")

    # All GitHub Repos
    all_github = unified_profile["projects"].get("from_github", [])
    print(f"\n  📂 All GitHub Repos ({len(all_github)} total):")
    for repo in all_github:
        langs = ", ".join(repo.get("technologies", [])) or "N/A"
        desc  = repo.get("description") or "No description"
        print(f"  • {repo['name']}")
        print(f"    Languages    : {langs}")
        print(f"    Commits      : {repo.get('commit_count', 0)}")
        print(f"    Stars        : {repo.get('stars', 0)}")
        print(f"    Forks        : {repo.get('forks', 0)}")
        print(f"    Last Updated : {repo.get('last_updated', 'N/A')}")
        print(f"    Description  : {desc}")
        print(f"    Is Fork      : {repo.get('is_fork', False)}")
        print(f"    Has Demo     : {repo.get('has_live_demo', False)}")

    # ── Code Analysis ─────────────────────────────────────
    code_analysis  = unified_profile.get("code_analysis", {})
    repos_analyzed = code_analysis.get("repos_analyzed", 0)

    print("\n🔍 CODE ANALYSIS")
    if repos_analyzed == 0:
        print("  ⚠️  No code analysis was run")
        print("  (Run agent1.py again and choose 'y' for code analysis)")
    else:
        print(f"  Repos analyzed       : {repos_analyzed}")

        skills_from_code = code_analysis.get("skills_from_code", [])
        if skills_from_code:
            print(f"  Skills from code     :")
            for s in skills_from_code:
                print(f"    • {s}")

        patterns = code_analysis.get("architecture_patterns", [])
        if patterns:
            print(f"  Architecture patterns:")
            for p in patterns:
                print(f"    • {p}")

        best_practices = code_analysis.get("best_practices", [])
        if best_practices:
            print(f"  Best practices       :")
            for b in best_practices:
                print(f"    • {b}")

        # Per repo insights
        print("\n  Per Repo Code Insights:")
        for repo in unified_profile["projects"].get("from_github", []):
            insights = repo.get("code_insights", {})
            if not insights:
                continue

            cq = insights.get("code_quality", {})
            tc = insights.get("technical_complexity", {})

            print(f"  ┌─────────────────────────────────────────────────")
            print(f"  │ Repo              : {repo['name']}")
            print(f"  │ Code Quality      : {cq.get('rating', 'N/A')} ({cq.get('score', 'N/A')}/10)")
            print(f"  │ Quality Summary   : {cq.get('summary', 'N/A')}")
            print(f"  │ Complexity        : {tc.get('rating', 'N/A')} ({tc.get('score', 'N/A')}/10)")
            print(f"  │ Complexity Summary: {tc.get('summary', 'N/A')}")
            print(f"  │ Overall           : {insights.get('overall_assessment', 'N/A')}")

            skills = insights.get("skills_demonstrated", [])
            if skills:
                print(f"  │ Skills shown      :")
                for s in skills:
                    print(f"  │   • {s}")

            arch = insights.get("architecture_patterns", [])
            if arch:
                print(f"  │ Patterns          :")
                for a in arch:
                    print(f"  │   • {a}")

            bp = insights.get("best_practices_used", [])
            if bp:
                print(f"  │ Best practices    :")
                for b in bp:
                    print(f"  │   • {b}")

            improvements = insights.get("areas_for_improvement", [])
            if improvements:
                print(f"  │ Improvements      :")
                for item in improvements:
                    print(f"  │   • {item}")

            observations = insights.get("notable_observations", [])
            if observations:
                print(f"  │ Observations      :")
                for obs in observations:
                    print(f"  │   • {obs}")

            samples = repo.get("code_samples", {})
            if samples:
                print(f"  │ Code files analyzed:")
                for path in samples.keys():
                    print(f"  │   • {path}")

            print(f"  └─────────────────────────────────────────────────")

    # ── Portfolio ─────────────────────────────────────────
    print("\n🌐 PORTFOLIO")
    if unified_profile["portfolio"].get("url"):
        print(f"  URL : {unified_profile['portfolio']['url']}")
        structured = unified_profile["portfolio"].get("structured", {})
        if structured:
            print(f"  Name   : {structured.get('name', 'N/A')}")
            print(f"  Title  : {structured.get('title', 'N/A')}")
            print(f"  About  : {structured.get('about', 'N/A')}")
            port_skills = structured.get("skills", [])
            if port_skills:
                print(f"  Skills : {', '.join(port_skills)}")
            port_projects = structured.get("projects", [])
            if port_projects:
                print(f"  Projects:")
                for proj in port_projects:
                    techs = ", ".join(proj.get("technologies", [])) or "N/A"
                    print(f"    ┌──────────────────────────────────────")
                    print(f"    │ Name : {proj.get('name', 'N/A')}")
                    print(f"    │ Tech : {techs}")
                    print(f"    │ Desc : {proj.get('description', 'N/A')}")
                    print(f"    │ Link : {proj.get('link', 'N/A')}")
                    print(f"    └──────────────────────────────────────")
            port_exp = structured.get("experience", [])
            if port_exp:
                print(f"  Experience:")
                for exp in port_exp:
                    print(f"    • {exp}")
            contact = structured.get("contact", {})
            if contact:
                print(f"  Contact:")
                print(f"    Email    : {contact.get('email', 'N/A')}")
                print(f"    LinkedIn : {contact.get('linkedin', 'N/A')}")
                print(f"    GitHub   : {contact.get('github', 'N/A')}")
        headings = unified_profile["portfolio"].get("headings", [])
        if headings:
            print(f"  Page Headings : {', '.join(headings[:10])}")
    else:
        print("  ❌ Not found")

    # ── Sources Used ──────────────────────────────────────
    print("\n📊 SOURCES USED")
    for source, used in unified_profile["sources_used"].items():
        status = "✅" if used else "❌"
        print(f"  {status} {source.capitalize()}")

    # ── Links ─────────────────────────────────────────────
    print("\n🔗 LINKS")
    print(f"  Email     : {unified_profile['candidate'].get('email')    or 'Not found'}")
    print(f"  GitHub    : {unified_profile['links'].get('github')       or 'Not found'}")
    print(f"  Portfolio : {unified_profile['links'].get('portfolio')    or 'Not found'}")
    print(f"  LinkedIn  : {unified_profile['links'].get('linkedin')     or 'Not found'}")

    print("\n" + "=" * 55)
    print("  ✅ Saved → outputs/candidate_profile.json")
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

    # GitHub URL — auto detected or manual input
    if github_url:
        print(f"\n  ✅ GitHub URL detected: {github_url}")
        github_input = input(
            "  Press Enter to use this or paste the correct one: "
        ).strip()
    else:
        print("\n  ⚠️  No GitHub URL found automatically")
        print("  (This happens when resume is pasted as text or links are hyperlinked)")
        github_input = input(
            "  Paste GitHub URL (e.g. https://github.com/username) or Enter to skip: "
        ).strip()

    if github_input:
        github_url = github_input

    # ── Step 3: Scrape GitHub + Analyze Code ─────────────
    print("\n🐙 STEP 3: GitHub Sub-Agent")
    github_data = {}

    if github_url:
        # Safety check for large org accounts
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
                print("  Skipping GitHub scraping.")
                github_url  = None
                github_data = {}

        if github_url:
            analyze = input(
                "\n  Run code analysis on repos? (y/n) [y]: "
            ).strip().lower()
            analyze_code = analyze != "n"

            github_data = scrape_github(
                github_url,
                analyze_code=analyze_code,
                max_repos_to_analyze=0  # 0 = analyze ALL non-fork repos
            )
    else:
        print("  ⚠️  No GitHub URL — skipping GitHub scraping")

    # ── Step 4: Find Portfolio ────────────────────────────
    print("\n🔍 STEP 4: Finding Portfolio URL...")
    portfolio_url = query_portfolio_url(collection, resume_data)

    if not portfolio_url:
        print("  Not found in resume — checking GitHub repos...")
        portfolio_url = extract_portfolio_from_github(github_data)

    # Portfolio URL — auto detected or manual input
    if portfolio_url:
        print(f"\n  ✅ Portfolio URL detected: {portfolio_url}")
        portfolio_input = input(
            "  Press Enter to use this or paste the correct one: "
        ).strip()
    else:
        print("\n  ⚠️  No Portfolio URL found automatically")
        print("  (This happens when resume is pasted as text or links are hyperlinked)")
        portfolio_input = input(
            "  Paste Portfolio URL or Enter to skip: "
        ).strip()

    if portfolio_input:
        portfolio_url = portfolio_input

    # ── Step 5: Scrape Portfolio ──────────────────────────
    print("\n🌐 STEP 5: Portfolio Sub-Agent")
    portfolio_data = {}
    if portfolio_url:
        portfolio_data = scrape_portfolio(portfolio_url)
    else:
        print("  ⚠️  No portfolio URL found anywhere — skipping")

    # ── Step 6: Merge All Sources ─────────────────────────
    print("\n🔀 STEP 6: Merging all sources...")
    unified_profile = merge_profiles(
        resume_data,
        github_data,
        portfolio_data
    )
    print("  ✅ Profile merged!")

    # ── Step 7: Save Output ───────────────────────────────
    os.makedirs("outputs", exist_ok=True)
    with open("outputs/candidate_profile.json", "w") as f:
        json.dump(unified_profile, f, indent=2)

    # ── Step 8: Print Full Summary ────────────────────────
    print_summary(unified_profile, portfolio_url)

    return unified_profile


if __name__ == "__main__":
    run_agent1()