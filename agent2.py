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

# ── Hardcoded Gemini API Key ──────────────────────────────────────────────────
GEMINI_API_KEY = "AIzaSyAijf1IwOqIHMXezTVnSYZNLn8_X76jetQ"   # <-- paste your key here

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
    "gemini-2.0-flash-lite",
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
    status_fn=None,          # optional callable(str) for live UI status updates
) -> dict:
    """
    Sends candidate profile JSON + job details to Gemini.
    Tries each model in MODELS_TO_TRY, returns parsed result dict.
    Raises last exception if all models fail.

    Args:
        candidate_json   : JSON string from agent1 run_agent1()
        job_role         : e.g. "Software Engineer"
        job_description  : full job description text
        status_fn        : optional callable for status messages (e.g. st.toast)

    Returns:
        result dict with keys: match_score, strengths, gaps, skill_coverage, etc.
    """

    def log(msg):
        if status_fn:
            status_fn(msg)
        else:
            print(msg)

    client = genai.Client(api_key=GEMINI_API_KEY)
    prompt = (
        f"candidate_json:\n{candidate_json}\n\n"
        f"job_role: {job_role}\n\n"
        f"job_description:\n{job_description}"
    )

    last_error = None
    for model_name in MODELS_TO_TRY:
        try:
            log(f"🤖 Trying model: {model_name}...")
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    temperature=0.1,
                )
            )
            result = json.loads(clean_json(response.text))
            log(f"✅ Success with {model_name}")
            return result

        except json.JSONDecodeError as e:
            log(f"❌ JSON parse error from {model_name}: {e}")
            raise e
        except Exception as e:
            last_error = e
            log(f"⚠️ {model_name} failed — trying next...")
            continue

    raise last_error


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