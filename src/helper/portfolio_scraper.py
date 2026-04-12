import requests
from bs4 import BeautifulSoup
import json
import os
import re
import time
from google import genai
from dotenv import load_dotenv

load_dotenv()

client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

# ─── URL Validation ───────────────────────────────────────

def is_valid_portfolio_url(url):
    """
    Returns False if URL is:
    - None or empty
    - mailto: link
    - plain email address
    - github URL
    - linkedin URL
    - does not start with http
    """
    if not url:
        return False
    if url.startswith("mailto:"):
        return False
    if re.match(r'^[^@]+@[^@]+\.[^@]+$', url):
        return False
    if "github.com" in url:
        return False
    if "linkedin.com" in url:
        return False
    if not url.startswith("http"):
        return False
    return True

def extract_email_from_url(url):
    """Extract email address from mailto: link"""
    if url and url.startswith("mailto:"):
        return url.replace("mailto:", "").strip()
    return None

# ─── Main Scraper ─────────────────────────────────────────

def scrape_portfolio(portfolio_url):
    """
    Validates URL first — rejects mailto/email/github/linkedin.
    Checks if accessible, then scrapes and structures content.
    """

    if not portfolio_url:
        print("  ⚠️  No portfolio URL provided — skipping")
        return {}

    # Reject mailto
    if portfolio_url.startswith("mailto:"):
        email = extract_email_from_url(portfolio_url)
        print(f"  ⚠️  URL is a mailto link (email: {email}) — not a portfolio, skipping")
        return {
            "url":         None,
            "email_found": email,
            "structured":  {}
        }

    # Reject plain email address
    if re.match(r'^[^@]+@[^@]+\.[^@]+$', portfolio_url):
        print(f"  ⚠️  URL is an email address ({portfolio_url}) — not a portfolio, skipping")
        return {
            "url":         None,
            "email_found": portfolio_url,
            "structured":  {}
        }

    # Reject other invalid URLs
    if not is_valid_portfolio_url(portfolio_url):
        print(f"  ⚠️  Invalid portfolio URL: {portfolio_url} — skipping")
        return {}

    print(f"  Checking portfolio URL: {portfolio_url}")

    # ── Check if accessible ───────────────────────────────
    try:
        check = requests.head(
            portfolio_url,
            timeout=10,
            headers={"User-Agent": "Mozilla/5.0"},
            allow_redirects=True
        )
        if check.status_code >= 400:
            print(f"  ❌ Portfolio returned {check.status_code} — skipping")
            return {}
        print(f"  ✅ Portfolio accessible (status {check.status_code})")

    except requests.exceptions.ConnectionError:
        print(f"  ❌ Could not connect to portfolio — skipping")
        return {}
    except requests.exceptions.Timeout:
        print(f"  ❌ Portfolio timed out — skipping")
        return {}
    except Exception as e:
        print(f"  ❌ Portfolio check failed: {e} — skipping")
        return {}

    # ── Scrape Content ────────────────────────────────────
    print(f"  Scraping portfolio content...")

    try:
        response = requests.get(
            portfolio_url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
            timeout=15
        )
        soup = BeautifulSoup(response.text, "html.parser")

        # Remove noise
        for tag in soup(["script", "style", "nav", "footer", "meta"]):
            tag.decompose()

        text     = soup.get_text(separator=" ", strip=True)
        headings = [h.text.strip() for h in soup.find_all(["h1", "h2", "h3"])]

        # Filter out mailto from links
        links = [
            a.get("href", "")
            for a in soup.find_all("a", href=True)
            if not a.get("href", "").startswith("mailto:")
            and a.get("href", "").startswith("http")
        ]

        print(f"  Extracted {len(text)} characters of content")

        # Structure with Gemini
        structured = extract_with_gemini(text[:3000])

        print("  ✅ Portfolio scraped and structured successfully")

        return {
            "url":        portfolio_url,
            "headings":   headings,
            "links":      links,
            "structured": structured
        }

    except Exception as e:
        print(f"  ❌ Portfolio scraping failed: {e}")
        return {"url": portfolio_url, "error": str(e), "structured": {}}

# ─── Gemini Structuring ───────────────────────────────────

def extract_with_gemini(text):
    prompt = f"""
    Extract structured information from this portfolio website text.
    Return ONLY valid JSON — no markdown, no extra text:
    
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
    
    Portfolio text:
    {text}
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
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt
                )
                raw = response.text.strip()
                raw = raw.replace("```json", "").replace("```", "").strip()
                return json.loads(raw)

            except Exception as e:
                error_str = str(e)
                if "429" in error_str:
                    print(f"  ❌ Quota exhausted on {model_name}, trying next...")
                    break
                elif "503" in error_str or "UNAVAILABLE" in error_str:
                    if attempt < 2:
                        wait = 30 * (attempt + 1)
                        print(f"  ⚠️  {model_name} unavailable. Waiting {wait}s...")
                        time.sleep(wait)
                    else:
                        print(f"  ❌ {model_name} still unavailable, trying next...")
                        break
                elif "404" in error_str or "NOT_FOUND" in error_str:
                    print(f"  ❌ {model_name} not found, trying next...")
                    break
                else:
                    raise e

    return {}