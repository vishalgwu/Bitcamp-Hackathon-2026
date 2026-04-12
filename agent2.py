import json
import re
from google import genai
from google.genai import types

from agent1 import Agent1

GEMINI_API_KEY = "AIzaSyDLRgjn9OBl4PAfQTlyrXf6LRPy0pPWmro"

SYSTEM_PROMPT = """You are an expert AI hiring-match evaluator. Compare candidate_json against job_role and job_description. Return ONLY valid JSON, no markdown, no backticks, no explanation.
Scoring: 90-100=Excellent, 75-89=Good, 60-74=Moderate, 40-59=Weak, 0-39=Poor.
Rules: no score inflation, prefer evidence from experience/projects over skill lists, reduce score for missing must-haves.
Return this exact JSON structure:
{"candidate_name":"","job_role":"","match_score":0,"match_summary":"","strengths":[{"area":"","evidence":"","relevance_to_job":""}],"gaps":[{"area":"","gap_detail":"","impact_on_match":""}],"skill_coverage":{"matched_skills":[{"skill":"","evidence_level":"strong|partial","evidence":""}],"missing_or_weak_skills":[{"skill":"","status":"missing|weak","reason":""}]},"experience_alignment":{"relevant_experience_summary":"","years_alignment":"","domain_alignment":"","seniority_alignment":""},"visual_data":{"chart_type":"radar_or_bar","categories":[{"name":"","score":0}]},"recommendation":{"overall_verdict":"strong_match|moderate_match|weak_match","why":"","improvement_suggestions":[""]}}
For visual_data categories use 6-8 of: Programming, Machine Learning/AI, NLP/LLM, Cloud/Deployment, Data Engineering, MLOps/Production, Domain Alignment, Overall Experience Relevance. Scores must reflect actual evidence.
Return ONLY the JSON object. No markdown. No explanation. No backticks."""

MODELS = [
    "gemini-2.5-flash",
    "gemini-2.5-pro",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
]


class Agent2:

    def __init__(self):
        self.client = genai.Client(api_key=GEMINI_API_KEY)

    def evaluate(self, candidate_json: dict, job_role: str, job_description: str) -> dict:
        prompt = (
            f"candidate_json:\n{json.dumps(candidate_json, indent=2)}\n\n"
            f"job_role: {job_role}\n\n"
            f"job_description:\n{job_description}"
        )
        for model in MODELS:
            try:
                print(f"  🤖 Trying {model}...")
                response = self.client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_PROMPT,
                        temperature=0.1,
                    )
                )
                raw = response.text.strip()
                raw = re.sub(r'^```json\s*', '', raw)
                raw = re.sub(r'^```\s*',     '', raw)
                raw = re.sub(r'\s*```$',     '', raw)
                print(f"  ✅ Done with {model}")
                return json.loads(raw)

            except json.JSONDecodeError as e:
                print(f"  ❌ JSON parse error: {e}")
                raise
            except Exception as e:
                print(f"  ⚠️ {model} failed: {e}")
                continue

        return {"error": "All models failed."}



if __name__ == "__main__":

    job_role        = "Data Scientist"
    job_description = "MINIMUM REQUIREMENTS: Bachelor’s degree in Data Science, Statistics, Computer Science, Information Systems, or related quantitative field. 5+ years of progressive experience performing advanced data analytics in audit, investigation, fraud detection, or compliance environments. Expert proficiency with Python, R, SQL, Power BI, Alteryx, ACL, and cloud‑based analytics platforms. 3+ years of experience developing analytical solutions using cloud native tools and APIs for ETL, storage, and analysis. PREFERRED: Master’s degree in Data Science, Data Analytics, Statistics, Computer Science, Information Systems, or other fields related to data analysis, machine learning, artificial intelligence, business information management, or forensic accounting. Professional certifications such as CFE, CIA, CISA, or equivalent. Advanced proficiency performing statistical analysis using data analytics software packages, or cloud native tools. Strong analytic skills related to working with unstructured datasets. Knowledge of working with JSON format data, including parsing and stringifying. Experience designing and implementing Artificial Intelligence strategy. Experience presenting analytic evidence in criminal, civil, or administrative proceedings. Investigative experience with an emphasis on complex white-collar crimes involving contracts, procurement, vendors, finance, human resources, public corruption, revenue, and health care. Broad knowledge of the laws, practices, and procedures of federal Offices of Inspector General. Familiarity with passenger rail or transportation operations"

    with open("output.json") as f:
        candidate_json = json.load(f)

    result = Agent2().evaluate(candidate_json, job_role, job_description)
    print(json.dumps(result, indent=2))
    with open("output1.json", "w") as f:
        json.dump(result, f, indent=2)
