import chromadb
import json
import re
import os
from chromadb.utils import embedding_functions
from dotenv import load_dotenv

load_dotenv()

# ─── Build Vector Store ───────────────────────────────────

def build_vectorstore(resume_data):
    print("  Building RAG vector store from resume chunks...")

    embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
    )

    client = chromadb.Client()

    collection = client.create_collection(
        name="resume_chunks",
        embedding_function=embedding_fn,
        metadata={"hnsw:space": "cosine"}
    )

    chunks    = []
    metadatas = []
    ids       = []
    chunk_id  = 0

    # Contact + links
    contact_text = f"""
    Name: {resume_data.get('name', '')}
    Email: {resume_data.get('email', '')}
    Phone: {resume_data.get('phone', '')}
    Location: {resume_data.get('location', '')}
    GitHub: {resume_data.get('github_url', '')}
    LinkedIn: {resume_data.get('linkedin_url', '')}
    Portfolio: {resume_data.get('portfolio_url', '')}
    """.strip()
    chunks.append(contact_text)
    metadatas.append({"section": "contact"})
    ids.append(f"chunk_{chunk_id}")
    chunk_id += 1

    # Summary
    if resume_data.get("summary"):
        chunks.append(f"Summary: {resume_data['summary']}")
        metadatas.append({"section": "summary"})
        ids.append(f"chunk_{chunk_id}")
        chunk_id += 1

    # Skills
    if resume_data.get("skills"):
        chunks.append("Skills: " + ", ".join(resume_data["skills"]))
        metadatas.append({"section": "skills"})
        ids.append(f"chunk_{chunk_id}")
        chunk_id += 1

    # Experience
    for i, exp in enumerate(resume_data.get("experience", [])):
        text = f"""
        Company: {exp.get('company', '')}
        Role: {exp.get('role', '')}
        Duration: {exp.get('duration', '')}
        Location: {exp.get('location', '')}
        Description: {exp.get('description', '')}
        """.strip()
        chunks.append(text)
        metadatas.append({"section": "experience", "index": str(i)})
        ids.append(f"chunk_{chunk_id}")
        chunk_id += 1

    # Projects
    for i, proj in enumerate(resume_data.get("projects", [])):
        text = f"""
        Project: {proj.get('name', '')}
        Description: {proj.get('description', '')}
        Technologies: {', '.join(proj.get('technologies', []))}
        """.strip()
        chunks.append(text)
        metadatas.append({"section": "projects", "index": str(i)})
        ids.append(f"chunk_{chunk_id}")
        chunk_id += 1

    # Education
    for i, edu in enumerate(resume_data.get("education", [])):
        text = f"""
        Institution: {edu.get('institution', '')}
        Degree: {edu.get('degree', '')}
        Field: {edu.get('field', '')}
        Year: {edu.get('year', '')}
        """.strip()
        chunks.append(text)
        metadatas.append({"section": "education", "index": str(i)})
        ids.append(f"chunk_{chunk_id}")
        chunk_id += 1

    # Certifications
    if resume_data.get("certifications"):
        chunks.append(
            "Certifications: " + ", ".join(resume_data["certifications"])
        )
        metadatas.append({"section": "certifications"})
        ids.append(f"chunk_{chunk_id}")
        chunk_id += 1

    collection.add(
        documents=chunks,
        metadatas=metadatas,
        ids=ids
    )

    print(f"  ✅ Vector store built with {len(chunks)} chunks")
    return collection

# ─── URL Helper ───────────────────────────────────────────

def find_url(text, pattern):
    match = re.search(pattern, text)
    return match.group(0) if match else None

def is_real_url(value):
    """Check if a value is actually a URL not just display text"""
    if not value:
        return False
    return value.strip().startswith("http")

# ─── Individual Link Queries ──────────────────────────────

def query_github_url(collection, resume_data):
    raw = resume_data.get("github_url", "")

    # Validate — must be a real URL with github.com and a username
    if is_real_url(raw) and "github.com/" in raw:
        username = raw.rstrip("/").split("/")[-1]
        # Reject if username is empty or the GitHub org itself
        if username.lower() not in ["github", "github.com", ""]:
            print(f"  ✅ GitHub URL from resume: {raw}")
            return raw

    if raw:
        print(f"  ⚠️  Rejected invalid GitHub value: '{raw}' — not a real URL")

    # Query RAG
    print("  🔍 RAG querying for GitHub URL...")
    results = collection.query(
        query_texts=["github profile link url repository code"],
        n_results=3
    )

    pattern = r'https?://(?:www\.)?github\.com/([a-zA-Z0-9_-]+)'

    for docs in results["documents"]:
        for doc in docs:
            url = find_url(doc, pattern)
            if url:
                parts    = url.split("/")
                clean    = "/".join(parts[:4])
                username = parts[3] if len(parts) > 3 else ""
                # Reject the GitHub org account
                if username.lower() in ["github", ""]:
                    continue
                print(f"  ✅ RAG found GitHub URL: {clean}")
                return clean

    print("  ⚠️  GitHub URL not found in resume")
    return None

def query_linkedin_url(collection, resume_data):
    raw = resume_data.get("linkedin_url", "")

    # Validate — must be a real URL with linkedin.com/in/
    if is_real_url(raw) and "linkedin.com/in/" in raw:
        print(f"  ✅ LinkedIn URL from resume: {raw}")
        return raw

    if raw:
        print(f"  ⚠️  Rejected invalid LinkedIn value: '{raw}' — not a real URL")

    # Query RAG
    print("  🔍 RAG querying for LinkedIn URL...")
    results = collection.query(
        query_texts=["linkedin profile link professional network"],
        n_results=3
    )

    pattern = r'https?://(?:www\.)?linkedin\.com/in/([a-zA-Z0-9_-]+)'

    for docs in results["documents"]:
        for doc in docs:
            url = find_url(doc, pattern)
            if url:
                print(f"  ✅ RAG found LinkedIn URL: {url}")
                return url

    print("  ⚠️  LinkedIn URL not found in resume")
    return None

def query_portfolio_url(collection, resume_data):
    raw = resume_data.get("portfolio_url", "")

    # Validate — must be a real URL, not github or linkedin
    if (
        is_real_url(raw) and
        "github.com" not in raw and
        "linkedin.com" not in raw
    ):
        print(f"  ✅ Portfolio URL from resume: {raw}")
        return raw

    if raw:
        print(f"  ⚠️  Rejected invalid portfolio value: '{raw}' — not a real URL")

    # Query RAG
    print("  🔍 RAG querying for portfolio URL...")
    results = collection.query(
        query_texts=["personal website portfolio link url showcase"],
        n_results=3
    )

    pattern = (
        r'https?://'
        r'(?!(?:www\.)?github\.com)'
        r'(?!(?:www\.)?linkedin\.com)'
        r'[^\s,<>"\'()]+'
    )

    for docs in results["documents"]:
        for doc in docs:
            url = find_url(doc, pattern)
            if url:
                print(f"  ✅ RAG found portfolio URL: {url}")
                return url

    print("  ⚠️  Portfolio URL not found in resume")
    return None

# ─── GitHub Portfolio Fallback ────────────────────────────

def extract_portfolio_from_github(github_data):
    """
    If portfolio not found in resume, check GitHub for:
    1. Profile website field
    2. username.github.io repo
    3. Any repo with a homepage/live demo link
    """
    if not github_data:
        return None

    print("  🔍 Checking GitHub for portfolio link...")

    # Check profile website field
    if github_data.get("website") and is_real_url(github_data["website"]):
        print(f"  ✅ Found in GitHub profile website: {github_data['website']}")
        return github_data["website"]

    # Check for GitHub Pages repo (username.github.io)
    username = github_data.get("username", "")
    for repo in github_data.get("repositories", []):
        if repo["name"].lower() == f"{username}.github.io":
            portfolio_url = f"https://{username}.github.io"
            print(f"  ✅ Found GitHub Pages site: {portfolio_url}")
            return portfolio_url

    # Check repos with live demo homepage links
    for repo in github_data.get("repositories", []):
        if repo.get("has_live_demo"):
            homepage = repo.get("homepage", "")
            if homepage and is_real_url(homepage):
                print(f"  ✅ Found live demo in repo '{repo['name']}': {homepage}")
                return homepage

    print("  ⚠️  No portfolio found in GitHub either")
    return None

# ─── Main Extraction Function ─────────────────────────────

def extract_links_with_rag(resume_data, github_data=None):
    """
    Priority order:
    1. Check resume data directly (Gemini extracted + hyperlinks)
       — validated to be real URLs not display text
    2. Query RAG vector store semantically
    3. For portfolio only: fallback to GitHub repos
    """
    collection = build_vectorstore(resume_data)

    print("\n  Extracting profile links...")

    github_url   = query_github_url(collection, resume_data)
    linkedin_url = query_linkedin_url(collection, resume_data)

    # Portfolio: resume → RAG → GitHub fallback
    portfolio_url = query_portfolio_url(collection, resume_data)

    if not portfolio_url:
        print("  Portfolio not found in resume — checking GitHub...")
        portfolio_url = extract_portfolio_from_github(github_data)

    links = {
        "github_url":    github_url,
        "portfolio_url": portfolio_url,
        "linkedin_url":  linkedin_url
    }

    print("\n  📋 Links extracted:")
    print(f"     GitHub    : {github_url    or 'Not found'}")
    print(f"     Portfolio : {portfolio_url or 'Not found'}")
    print(f"     LinkedIn  : {linkedin_url  or 'Not found'}")

    return links