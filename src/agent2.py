"""
agent2.py — AI Match Evaluator for Hire.AI
Uses Gemini API to evaluate candidate JSON against job role + description.
"""

import os
os.environ["GRPC_VERBOSITY"] = "ERROR"
os.environ["GLOG_minloglevel"] = "2"

import json
import re
from google import genai
from google.genai import types
import time
from dotenv import load_dotenv

load_dotenv()

# ── Gemini API Key ────────────────────────────────────────────────────────────
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# ── System Prompt ─────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are an expert AI hiring-match evaluator. Compare candidate_json against job_role and job_description. Return ONLY valid JSON, no markdown, no backticks, no explanation.
Scoring: 90-100=Excellent, 75-89=Good, 60-74=Moderate, 40-59=Weak, 0-39=Poor.
Rules: no score inflation, prefer evidence from experience/projects over skill lists, reduce score for missing must-haves.
Return this exact JSON structure:
{"candidate_name":"","job_role":"","match_score":0,"match_summary":"","strengths":[{"area":"","evidence":"","relevance_to_job":""}],"gaps":[{"area":"","gap_detail":"","impact_on_match":""}],"skill_coverage":{"matched_skills":[{"skill":"","evidence_level":"strong|partial","evidence":""}],"missing_or_weak_skills":[{"skill":"","status":"missing|weak","reason":""}]},"experience_alignment":{"relevant_experience_summary":"","years_alignment":"","domain_alignment":"","seniority_alignment":""},"visual_data":{"chart_type":"radar_or_bar","categories":[{"name":"","score":0}]},"recommendation":{"overall_verdict":"strong_match|moderate_match|weak_match","why":"","improvement_suggestions":[""]}}
For visual_data categories use 6-8 of: Programming, Machine Learning/AI, NLP/LLM, Cloud/Deployment, Data Engineering, MLOps/Production, Domain Alignment, Overall Experience Relevance. Scores must reflect actual evidence.
Return ONLY the JSON object. No markdown. No explanation. No backticks."""

# ── Model fallback chain ──────────────────────────────────────────────────────
MODELS_TO_TRY = [
    "gemini-2.5-flash",
    "gemini-2.5-pro",
    "gemini-2.0-flash",
    "gemini-2.0-flash-001",
    "gemini-2.0-flash-lite",
    "gemini-2.5-flash-lite",
]


def score_to_verdict(score: int) -> str:
    if score >= 90:   return "very_strong"
    elif score >= 75: return "strong"
    elif score >= 60: return "good"
    elif score >= 45: return "moderate"
    elif score >= 25: return "poor"
    else:             return "very_poor"

def get_score_color(score: int) -> str:
    if score >= 90:   return "#00e676"
    elif score >= 75: return "#43e97b"
    elif score >= 60: return "#6c63ff"
    elif score >= 45: return "#ffc400"
    elif score >= 25: return "#ff6b6b"
    else:             return "#b41e1e"

def get_verdict_emoji(verdict: str) -> str:
    return {
        "very_strong": "🏆",
        "strong":      "✅",
        "good":        "⚡",
        "moderate":    "🔶",
        "poor":        "⚠️",
        "very_poor":   "❌",
    }.get(verdict, "⚠️")

def get_verdict_label(verdict: str) -> str:
    return {
        "very_strong": "VERY STRONG MATCH",
        "strong":      "STRONG MATCH",
        "good":        "GOOD MATCH",
        "moderate":    "MODERATE MATCH",
        "poor":        "POOR MATCH",
        "very_poor":   "VERY POOR MATCH",
    }.get(verdict, "POOR MATCH")

# ── JSON cleaner ──────────────────────────────────────────────────────────────

def clean_json(text: str) -> str:
    text = text.strip()
    text = re.sub(r'^```json\s*', '', text)
    text = re.sub(r'^```\s*',     '', text)
    text = re.sub(r'\s*```$',     '', text)
    return text.strip()

# ── Core evaluate function ────────────────────────────────────────────────────

def evaluate(
    candidate_json: str,
    job_role: str,
    job_description: str,
    status_fn=None,
) -> dict:

    def log(msg):
        if status_fn:
            status_fn(msg)
        else:
            print(msg)

    def repair_json(text: str) -> str:
        text = text.strip()
        last_valid = max(text.rfind(','), text.rfind('}'), text.rfind(']'))
        if last_valid > 0:
            text = text[:last_valid]
        open_braces   = text.count('{') - text.count('}')
        open_brackets = text.count('[') - text.count(']')
        text += ']' * open_brackets
        text += '}' * open_braces
        return text

    client = genai.Client(api_key=GEMINI_API_KEY)
    prompt = (
        f"candidate_json:\n{candidate_json}\n\n"
        f"job_role: {job_role}\n\n"
        f"job_description:\n{job_description}"
    )

    last_error = None
    for model_name in MODELS_TO_TRY:
        try:
            log(f"Trying model: {model_name}...")
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    temperature=0,
                )
            )

            raw = clean_json(response.text)

            try:
                result = json.loads(raw)
            except json.JSONDecodeError:
                log(f"JSON truncated from {model_name}, attempting repair...")
                result = json.loads(repair_json(raw))

            log(f"Success with {model_name} — score: {result.get('match_score', '?')}")
            return result

        except json.JSONDecodeError as e:
            log(f"JSON parse error from {model_name} even after repair: {e}")
            last_error = e
            time.sleep(3)
            continue
        except Exception as e:
            last_error = e
            err_str = str(e)
            if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                log(f"{model_name} quota hit — waiting 45s...")
                time.sleep(45)
            else:
                log(f"{model_name} failed — trying next...")
                time.sleep(3)
            continue

    raise last_error

# ─── GitHub Summarizer ────────────────────────────────────────────────────────

def summarize_github(github_data: dict, job_role: str, job_description: str) -> dict:
    """
    Takes raw github_data from agent1, job role + JD.
    Returns:
      - profile_summary: 2-3 sentence narrative about the developer
      - skills_narrative: readable paragraph about their skills
      - matched_repos: list of repos relevant to the JD with stats
      - assessment_narrative: readable developer level summary
    """

    client = genai.Client(api_key=GEMINI_API_KEY)

    # ── Build repo context ────────────────────────────────────────────────────
    candidate_profile = github_data.get("candidate_profile", {}).get("github", {})
    skills_summary    = github_data.get("skills_summary", {})
    repositories      = github_data.get("repositories", [])
    final_assessment  = github_data.get("final_assessment", {})

    # Summarise all repos for Gemini — name, languages, description, stars,
    # commits, and skills_demonstrated from code_insights
    repos_context = []
    for r in repositories:
        insights   = r.get("code_insights", {})
        skills_dem = insights.get("skills_demonstrated", [])
        repos_context.append({
            "name":        r["name"],
            "description": r.get("description", ""),
            "languages":   r.get("languages", []),
            "stars":       r.get("stars", 0),
            "forks":       r.get("forks", 0),
            "commits":     r.get("commit_count", 0),
            "topics":      r.get("topics", []),
            "skills":      skills_dem[:8],
            "has_code":    bool(r.get("code_samples")),
            "quality":     insights.get("code_quality", {}).get("rating", ""),
            "assessment":  insights.get("overall_assessment", ""),
        })

    prompt = f"""
You are a strict technical hiring analyst. Your job is to identify ONLY repos that directly demonstrate
skills required for the specific job below. Be conservative — if in doubt, exclude the repo.

Job Role: {job_role}
Job Description (excerpt): {job_description[:800]}

Candidate GitHub username: {candidate_profile.get("username", "")}
Bio: {candidate_profile.get("bio", "")}
Public repos: {candidate_profile.get("public_repos", 0)}
Followers: {candidate_profile.get("followers", 0)}

Languages across all repos: {", ".join(skills_summary.get("all_languages", [])[:15])}
Skills from code analysis: {", ".join(skills_summary.get("skills_from_code", [])[:20])}
Architecture patterns: {", ".join(skills_summary.get("architecture_patterns", [])[:10])}

Developer Assessment: {json.dumps(final_assessment)}

All Repositories ({len(repos_context)} total):
{json.dumps(repos_context, indent=2)[:3000]}

MATCHING RULES:
1. Read the Job Description above carefully. Extract the CORE required skills and technologies from it.
2. A repo QUALIFIES only if it contains DIRECT evidence of those core skills — actual code, not just
   tangential or "could be related" connections.
3. A repo does NOT qualify just because:
   - It uses the same programming language as the JD
   - It "demonstrates foundational skills" or "could be useful for" the role
   - It is a general-purpose tool that happens to overlap loosely
   - The description sounds adjacent but has no real technical overlap with the JD
4. If the JD is for a backend role, only include repos with real backend/API/system work.
   If ML/AI, only repos with actual models or pipelines. If frontend, real UI work. And so on.
5. If no repos genuinely match the JD requirements, return matched_repos as an empty list.
   Do NOT stretch to fill the list.
6. Exclude repos with no code, forks with no original work, and placeholder/empty repos.

Return ONLY valid JSON — no markdown, no extra text:
{{
    "profile_summary": "2-3 sentences describing the developer's background and style based on their GitHub",
    "skills_narrative": "2-3 sentences summarizing their technical skills, languages, and what they build",
    "assessment_narrative": "2 sentences about their developer level and fit for this specific role",
    "matched_repos": [
        {{
            "name": "",
            "relevance_reason": "1 sentence citing SPECIFIC evidence in this repo that maps to the JD requirements",
            "languages": [],
            "stars": 0,
            "commits": 0,
            "quality_rating": "",
            "key_skills": []
        }}
    ],
    "unmatched_count": 0,
    "match_note": "1 sentence honestly describing what was excluded and why"
}}

Sort matched_repos by relevance (most relevant first).
unmatched_count: total repos NOT in matched_repos.
"""

    last_error = None
    for model_name in MODELS_TO_TRY:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0)
            )
            raw = clean_json(response.text)

            # Strip any stray HTML tags Gemini may have included inside JSON strings
            raw = re.sub(r'<[^>]+>', '', raw)

            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                # Attempt basic bracket repair
                fixed = re.sub(r',\s*([}\]])', r'\1', raw)
                try:
                    return json.loads(fixed)
                except:
                    last_error = Exception("JSON parse failed after repair")
                    time.sleep(3)
                    continue
        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                time.sleep(45)
            else:
                time.sleep(3)
            last_error = e
            continue

    # Fallback — return basic structure if all models fail
    return {
        "profile_summary":      "GitHub profile analysis unavailable.",
        "skills_narrative":     ", ".join(skills_summary.get("all_languages", [])),
        "assessment_narrative": str(final_assessment),
        "matched_repos":        [],
        "unmatched_count":      len(repositories),
        "match_note":           "Could not analyze repositories."
    }


# ─── CLI entry point ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys

    profile_path = "outputs/candidate_profile.json"
    if not os.path.exists(profile_path):
        print(f"❌ No profile found at {profile_path}. Run agent1 first.")
        sys.exit(1)

    with open(profile_path) as f:
        candidate_json = f.read()

    job_role = input("Job Role: ").strip()
    print("Job Description (type END to finish):")
    lines = []
    while True:
        line = input()
        if line.strip() == "END":
            break
        lines.append(line)
    job_description = "\n".join(lines)

    result = evaluate(candidate_json, job_role, job_description)
    print(json.dumps(result, indent=2))