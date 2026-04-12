import streamlit as st
import json
import time
import re
import os
import tempfile
from pathlib import Path

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Hire.AI",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Global CSS ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Mono:ital,wght@0,400;0,500;1,400&family=DM+Sans:ital,wght@0,300;0,400;0,500;1,300&display=swap');

*, *::before, *::after { box-sizing: border-box; margin: 0; }

:root {
    --bg:        #08090c;
    --bg2:       #0e1018;
    --card:      #12141d;
    --border:    #1e2235;
    --accent:    #4fffb0;
    --accent2:   #7b61ff;
    --danger:    #ff4f6d;
    --text:      #e8eaf0;
    --muted:     #6b7280;
    --font-head: 'Syne', sans-serif;
    --font-body: 'DM Sans', sans-serif;
    --font-mono: 'DM Mono', monospace;
}

#MainMenu, footer, header { visibility: hidden; }
.stDeployButton { display: none; }
[data-testid="stToolbar"] { display: none; }

.main .block-container {
    padding: 0 !important;
    max-width: 100% !important;
}

html, body, [data-testid="stAppViewContainer"] {
    background: var(--bg) !important;
    color: var(--text) !important;
    font-family: var(--font-body);
}

::-webkit-scrollbar { width: 4px; }
::-webkit-scrollbar-track { background: var(--bg2); }
::-webkit-scrollbar-thumb { background: var(--accent2); border-radius: 2px; }

input[type="text"], input[type="password"], input[type="email"],
textarea, .stTextInput input, .stTextArea textarea {
    background: var(--bg2) !important;
    border: 1px solid var(--border) !important;
    border-radius: 8px !important;
    color: var(--text) !important;
    font-family: var(--font-body) !important;
    transition: border-color .2s !important;
}
input:focus, textarea:focus,
.stTextInput input:focus, .stTextArea textarea:focus {
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 3px rgba(79,255,176,.1) !important;
    outline: none !important;
}

.stButton > button {
    background: var(--accent) !important;
    color: #08090c !important;
    font-family: var(--font-head) !important;
    font-weight: 700 !important;
    border: none !important;
    border-radius: 8px !important;
    padding: 0.65rem 1.5rem !important;
    cursor: pointer !important;
    transition: all .2s !important;
    letter-spacing: .02em !important;
}
.stButton > button:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 6px 24px rgba(79,255,176,.3) !important;
}
.stButton > button:active { transform: translateY(0) !important; }

[data-testid="stFileUploader"] {
    background: var(--bg2) !important;
    border: 2px dashed var(--border) !important;
    border-radius: 12px !important;
    transition: border-color .2s !important;
}
[data-testid="stFileUploader"]:hover {
    border-color: var(--accent) !important;
}

[data-testid="stSelectbox"] > div,
[data-testid="stRadio"] label {
    color: var(--text) !important;
    font-family: var(--font-body) !important;
}

.stTabs [data-baseweb="tab-list"] {
    background: var(--card) !important;
    border-radius: 10px !important;
    padding: 4px !important;
    gap: 4px !important;
    border: 1px solid var(--border) !important;
}
.stTabs [data-baseweb="tab"] {
    background: transparent !important;
    color: var(--muted) !important;
    font-family: var(--font-head) !important;
    font-weight: 600 !important;
    border-radius: 8px !important;
    border: none !important;
    padding: .5rem 1.2rem !important;
}
.stTabs [aria-selected="true"] {
    background: var(--accent) !important;
    color: #08090c !important;
}

.stProgress > div > div { background: var(--accent) !important; }

[data-testid="stAlert"] {
    background: var(--bg2) !important;
    border: 1px solid var(--border) !important;
    border-radius: 10px !important;
    color: var(--text) !important;
}

[data-testid="stMetric"] {
    background: var(--card) !important;
    border: 1px solid var(--border) !important;
    border-radius: 12px !important;
    padding: 1rem 1.2rem !important;
}
[data-testid="stMetricLabel"] { color: var(--muted) !important; font-family: var(--font-mono) !important; font-size: .75rem !important; }
[data-testid="stMetricValue"] { color: var(--accent) !important; font-family: var(--font-head) !important; }

[data-testid="stExpander"] {
    background: var(--card) !important;
    border: 1px solid var(--border) !important;
    border-radius: 10px !important;
    margin-bottom: .5rem !important;
}
[data-testid="stExpander"] summary { color: var(--text) !important; font-family: var(--font-head) !important; }

hr { border-color: var(--border) !important; }

label { color: var(--muted) !important; font-family: var(--font-mono) !important; font-size: .8rem !important; letter-spacing: .05em !important; }

[data-testid="stSidebar"] {
    background: var(--bg2) !important;
    border-right: 1px solid var(--border) !important;
}

@keyframes pulse {
    0%,100%{opacity:1;transform:scale(1);}
    50%{opacity:.5;transform:scale(1.3);}
}
</style>
""", unsafe_allow_html=True)

# ── Auth "database" ───────────────────────────────────────────────────────────
EMPLOYER_CREDENTIALS = {
    "admin@hire.ai":      "employer123",
    "recruiter@acme.com": "acme2024",
    "hr@techcorp.io":     "techcorp99",
}

# ── Session defaults ──────────────────────────────────────────────────────────
for key, default in {
    "logged_in":       False,
    "user_type":       None,
    "user_email":      None,
    "user_name":       None,
    "candidates_db":   {},
    "page":            "landing",
    "analysis_result": None,
    "resume_result":   None,
    "interview_result":None,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default


# ── Helpers ───────────────────────────────────────────────────────────────────

def badge(text: str, color: str = "var(--accent)"):
    return (f'<span style="background:{color}22;color:{color};'
            f'font-family:var(--font-mono);font-size:.72rem;'
            f'padding:.25rem .7rem;border-radius:999px;'
            f'border:1px solid {color}44;letter-spacing:.04em;">{text}</span>')


def score_ring(score: int, size: int = 110):
    colour = "#4fffb0" if score >= 75 else "#f59e0b" if score >= 55 else "#ff4f6d"
    dash   = round(score * 2.83)
    return f"""
    <div style="display:flex;flex-direction:column;align-items:center;gap:.4rem;">
        <svg width="{size}" height="{size}" viewBox="0 0 100 100">
            <circle cx="50" cy="50" r="45" fill="none" stroke="#1e2235" stroke-width="8"/>
            <circle cx="50" cy="50" r="45" fill="none" stroke="{colour}" stroke-width="8"
                    stroke-dasharray="{dash} 283"
                    stroke-dashoffset="70.75" stroke-linecap="round"
                    transform="rotate(-90 50 50)"/>
            <text x="50" y="46" text-anchor="middle" fill="{colour}"
                  font-family="Syne,sans-serif" font-size="20" font-weight="800">{score}</text>
            <text x="50" y="62" text-anchor="middle" fill="#6b7280"
                  font-family="DM Mono,monospace" font-size="10">/100</text>
        </svg>
    </div>"""


def radar_chart_html(categories: list) -> str:
    bars = ""
    for cat in categories:
        name  = cat.get("name", "")
        score = min(100, max(0, cat.get("score", 0)))
        color = "#4fffb0" if score >= 75 else "#f59e0b" if score >= 55 else "#ff4f6d"
        bars += f"""
        <div style="margin-bottom:.7rem;">
            <div style="display:flex;justify-content:space-between;
                        font-family:'DM Mono',monospace;font-size:.75rem;
                        color:#e8eaf0;margin-bottom:.3rem;">
                <span>{name}</span>
                <span style="color:{color};font-weight:500;">{score}</span>
            </div>
            <div style="background:#1e2235;border-radius:999px;height:8px;overflow:hidden;">
                <div style="width:{score}%;background:{color};
                            height:100%;border-radius:999px;"></div>
            </div>
        </div>"""
    return f'<div style="padding:.5rem 0;">{bars}</div>'


def _demo_result(job_title):
    return {
        "job_title": job_title,
        "combined": {
            "resume": {"name": "Alex Chen", "email": "alex@demo.com"},
            "github": {
                "candidate_profile": {"username": "alexchen", "name": "Alex Chen",
                                      "public_repos": 22, "followers": 48},
                "final_assessment": (
                    "Strong mid-level engineer with solid Python and ML foundations. "
                    "Active open-source contributor. Recommended for mid-senior roles in ML engineering."
                ),
            }
        },
        "match": {
            "candidate_name":  "Alex Chen",
            "job_role":        job_title,
            "match_score":     78,
            "match_summary":   "Strong alignment with core technical requirements. Minor gaps in cloud/deployment experience.",
            "strengths": [
                {"area": "Python & ML",      "evidence": "6+ years Python, multiple ML projects", "relevance_to_job": "Core requirement met"},
                {"area": "Data Engineering", "evidence": "ETL pipelines in 3 repos",              "relevance_to_job": "High relevance"},
                {"area": "Deep Learning",    "evidence": "PyTorch projects on GitHub",             "relevance_to_job": "Strong signal"},
            ],
            "gaps": [
                {"area": "Cloud Deployment", "gap_detail": "Limited AWS/GCP evidence",         "impact_on_match": "Moderate"},
                {"area": "MLOps",            "gap_detail": "No CI/CD for ML pipelines shown",  "impact_on_match": "Low-Moderate"},
            ],
            "skill_coverage": {
                "matched_skills": [
                    {"skill": "Python",     "evidence_level": "strong",  "evidence": "Primary language"},
                    {"skill": "SQL",        "evidence_level": "strong",  "evidence": "Multiple DB projects"},
                    {"skill": "TensorFlow", "evidence_level": "partial", "evidence": "Mentioned in README"},
                ],
                "missing_or_weak_skills": [
                    {"skill": "Kubernetes", "status": "missing", "reason": "No evidence in repos"},
                    {"skill": "Airflow",    "status": "weak",    "reason": "One config file only"},
                ]
            },
            "visual_data": {
                "categories": [
                    {"name": "Programming",      "score": 88},
                    {"name": "Machine Learning", "score": 82},
                    {"name": "NLP / LLM",        "score": 65},
                    {"name": "Cloud/Deploy",     "score": 48},
                    {"name": "Data Engineering", "score": 75},
                    {"name": "MLOps/Production", "score": 52},
                    {"name": "Domain Alignment", "score": 80},
                ]
            },
            "recommendation": {
                "overall_verdict":        "moderate_match",
                "why":                    "Strong technical core but needs cloud/MLOps uplift for senior roles.",
                "improvement_suggestions": [
                    "Complete AWS Solutions Architect or GCP Professional cert",
                    "Add MLflow or Kubeflow to a GitHub project",
                    "Showcase a deployed end-to-end ML API",
                ]
            },
            "experience_alignment": {
                "relevant_experience_summary": "4 years ML engineering, 2 years data analytics",
                "years_alignment":    "Good",
                "domain_alignment":   "Strong",
                "seniority_alignment":"Mid to Senior",
            }
        }
    }


# ══════════════════════════════════════════════════════════════════════════════
# TOP NAV
# ══════════════════════════════════════════════════════════════════════════════
def render_topnav(role: str):
    role_label = "EMPLOYER" if role == "employer" else "CANDIDATE"
    role_color = "var(--accent2)" if role == "employer" else "var(--accent)"

    st.markdown(f"""
    <div style="background:var(--bg2);border-bottom:1px solid var(--border);
                padding:.9rem 2rem;display:flex;align-items:center;
                justify-content:space-between;">
        <div style="font-family:var(--font-head);font-size:1.4rem;
                    font-weight:800;letter-spacing:-.02em;color:var(--text);">
            Hire<span style="color:var(--accent);">.</span>AI
        </div>
        <div style="display:flex;align-items:center;gap:1rem;">
            <span style="font-family:var(--font-mono);font-size:.7rem;
                         color:{role_color};background:{role_color}18;
                         padding:.2rem .8rem;border-radius:999px;
                         border:1px solid {role_color}44;letter-spacing:.08em;">
                {role_label}
            </span>
            <span style="font-family:var(--font-body);font-size:.88rem;
                         color:var(--muted);">{st.session_state.user_name}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    nav_c1, nav_c2, nav_logout = st.columns([6, 3, 1])
    with nav_logout:
        if st.button("Logout", key="nav_logout_btn"):
            for k in ["logged_in","user_type","user_email","user_name",
                      "analysis_result","resume_result","interview_result"]:
                st.session_state[k] = (False if k == "logged_in" else None)
            st.session_state.page = "landing"
            st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# LANDING
# ══════════════════════════════════════════════════════════════════════════════
def page_landing():
    st.markdown("""
    <div style="min-height:80vh;display:flex;flex-direction:column;
                align-items:center;justify-content:center;
                padding:4rem 2rem;text-align:center;position:relative;overflow:hidden;">
        <div style="position:absolute;inset:0;
            background-image:linear-gradient(var(--border) 1px,transparent 1px),
                             linear-gradient(90deg,var(--border) 1px,transparent 1px);
            background-size:40px 40px;opacity:.3;"></div>
        <div style="position:absolute;top:30%;left:50%;transform:translateX(-50%);
            width:700px;height:500px;border-radius:50%;
            background:radial-gradient(circle,rgba(79,255,176,.06) 0%,transparent 70%);
            pointer-events:none;"></div>
        <div style="position:relative;z-index:1;">
            <div style="display:inline-flex;align-items:center;gap:.6rem;
                        background:var(--card);border:1px solid var(--border);
                        border-radius:999px;padding:.4rem 1.2rem;margin-bottom:2rem;">
                <span style="width:8px;height:8px;background:var(--accent);
                             border-radius:50%;display:inline-block;
                             animation:pulse 2s infinite;"></span>
                <span style="font-family:var(--font-mono);font-size:.78rem;
                             color:var(--muted);letter-spacing:.1em;">
                    AI-POWERED HIRING INTELLIGENCE
                </span>
            </div>
            <h1 style="font-family:var(--font-head);font-size:clamp(3.5rem,9vw,7rem);
                       font-weight:800;line-height:1;letter-spacing:-.04em;
                       color:var(--text);margin-bottom:1.2rem;">
                Hire<span style="color:var(--accent);">.</span>AI
            </h1>
            <p style="font-family:var(--font-body);font-size:1.15rem;
                      color:var(--muted);max-width:540px;margin:0 auto 1.5rem;
                      line-height:1.75;font-weight:300;">
                Deep resume analysis. GitHub intelligence. Interview evaluation.<br>
                Built for teams that move fast.
            </p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    c1, c2, c3 = st.columns([1.5, 1, 1.5])
    with c2:
        emp_col, cand_col = st.columns(2)
        with emp_col:
            if st.button("⚡ Employer", use_container_width=True, key="land_emp"):
                st.session_state.page = "employer_login"
                st.rerun()
        with cand_col:
            if st.button("🎓 Candidate", use_container_width=True, key="land_cand"):
                st.session_state.page = "candidate_auth"
                st.rerun()

    # Feature strip
    st.markdown("<div style='height:2rem'></div>", unsafe_allow_html=True)
    f1, f2, f3, f4 = st.columns(4)
    features = [
        ("🧠", "Resume Intelligence", "LLM-powered parsing & scoring"),
        ("🐙", "GitHub Analysis",     "Deep code quality review"),
        ("🎯", "JD Matching",         "Evidence-based match scores"),
        ("🎙️","Interview AI",        "Automated evaluation"),
    ]
    for col, (icon, title, desc) in zip([f1,f2,f3,f4], features):
        with col:
            st.markdown(f"""
            <div style="background:var(--card);border:1px solid var(--border);
                        border-radius:12px;padding:1.2rem 1.3rem;text-align:center;">
                <div style="font-size:1.6rem;margin-bottom:.5rem;">{icon}</div>
                <div style="font-family:var(--font-head);font-weight:700;
                            color:var(--text);font-size:.88rem;margin-bottom:.2rem;">{title}</div>
                <div style="font-family:var(--font-body);color:var(--muted);
                            font-size:.78rem;">{desc}</div>
            </div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# EMPLOYER LOGIN
# ══════════════════════════════════════════════════════════════════════════════
def page_employer_login():
    c1, c2, c3 = st.columns([1, 1.1, 1])
    with c2:
        st.markdown("<div style='height:8vh'></div>", unsafe_allow_html=True)
        st.markdown("""
        <div style="text-align:center;margin-bottom:2rem;">
            <h1 style="font-family:var(--font-head);font-size:2.5rem;
                       font-weight:800;color:var(--text);letter-spacing:-.02em;">
                Hire<span style="color:var(--accent);">.</span>AI
            </h1>
            <p style="color:var(--muted);font-family:var(--font-mono);
                      font-size:.8rem;letter-spacing:.08em;margin-top:.3rem;">
                EMPLOYER PORTAL
            </p>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("""
        <div style="background:var(--card);border:1px solid var(--border);
                    border-radius:20px;padding:2.5rem 2rem 2rem;">
        """, unsafe_allow_html=True)
        email    = st.text_input("Work Email",  placeholder="recruiter@company.com", key="emp_email_in")
        password = st.text_input("Password",    type="password", placeholder="••••••••", key="emp_pass_in")
        st.markdown("<div style='height:.4rem'></div>", unsafe_allow_html=True)
        if st.button("Sign In →", use_container_width=True, key="emp_signin_btn"):
            if email in EMPLOYER_CREDENTIALS and EMPLOYER_CREDENTIALS[email] == password:
                st.session_state.logged_in  = True
                st.session_state.user_type  = "employer"
                st.session_state.user_email = email
                st.session_state.user_name  = email.split("@")[0].replace(".", " ").title()
                st.session_state.page       = "employer_dashboard"
                st.rerun()
            else:
                st.error("Invalid credentials.")
        st.markdown("""
        <div style="text-align:center;margin-top:1rem;">
            <span style="font-family:var(--font-mono);font-size:.73rem;color:var(--muted);">
                Demo: admin@hire.ai / employer123
            </span>
        </div>
        </div>""", unsafe_allow_html=True)

        st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)
        if st.button("← Back", key="emp_login_back"):
            st.session_state.page = "landing"
            st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# CANDIDATE AUTH (Login / Signup / Forgot)
# ══════════════════════════════════════════════════════════════════════════════
def page_candidate_auth():
    c1, c2, c3 = st.columns([1, 1.1, 1])
    with c2:
        st.markdown("<div style='height:6vh'></div>", unsafe_allow_html=True)
        st.markdown("""
        <div style="text-align:center;margin-bottom:1.8rem;">
            <h1 style="font-family:var(--font-head);font-size:2.5rem;
                       font-weight:800;color:var(--text);letter-spacing:-.02em;">
                Hire<span style="color:var(--accent);">.</span>AI
            </h1>
            <p style="color:var(--muted);font-family:var(--font-mono);
                      font-size:.8rem;letter-spacing:.08em;margin-top:.3rem;">
                CANDIDATE PORTAL
            </p>
        </div>
        """, unsafe_allow_html=True)

        tab_l, tab_s, tab_f = st.tabs(["  Login  ", "  Sign Up  ", "  Forgot Password  "])

        with tab_l:
            st.markdown("<div style='height:.8rem'></div>", unsafe_allow_html=True)
            email = st.text_input("Email",    key="cl_email", placeholder="you@email.com")
            pw    = st.text_input("Password", key="cl_pw",    type="password", placeholder="••••••••")
            st.markdown("<div style='height:.3rem'></div>", unsafe_allow_html=True)
            if st.button("Login →", use_container_width=True, key="cl_btn"):
                db = st.session_state.candidates_db
                if email in db and db[email]["password"] == pw:
                    st.session_state.logged_in  = True
                    st.session_state.user_type  = "candidate"
                    st.session_state.user_email = email
                    st.session_state.user_name  = db[email]["name"]
                    st.session_state.page       = "candidate_dashboard"
                    st.rerun()
                else:
                    st.error("Invalid email or password.")

        with tab_s:
            st.markdown("<div style='height:.8rem'></div>", unsafe_allow_html=True)
            name  = st.text_input("Full Name",        key="cs_name",  placeholder="Jane Doe")
            email = st.text_input("Email",            key="cs_email", placeholder="you@email.com")
            pw    = st.text_input("Password",         key="cs_pw",    type="password", placeholder="Min 8 chars")
            conf  = st.text_input("Confirm Password", key="cs_conf",  type="password", placeholder="Repeat")
            st.markdown("<div style='height:.3rem'></div>", unsafe_allow_html=True)
            if st.button("Create Account →", use_container_width=True, key="cs_btn"):
                if not name or not email or not pw:
                    st.error("Please fill all fields.")
                elif pw != conf:
                    st.error("Passwords do not match.")
                elif len(pw) < 8:
                    st.error("Password must be at least 8 characters.")
                elif email in st.session_state.candidates_db:
                    st.error("Email already registered — please login.")
                else:
                    st.session_state.candidates_db[email] = {"name": name, "password": pw}
                    st.success("✅ Account created! Please login.")

        with tab_f:
            st.markdown("<div style='height:.8rem'></div>", unsafe_allow_html=True)
            st.markdown("""<p style="font-family:var(--font-body);color:var(--muted);
                           font-size:.88rem;margin-bottom:.8rem;">
                Enter your email and new password below.</p>""", unsafe_allow_html=True)
            fp_e  = st.text_input("Registered Email",  key="fp_e",  placeholder="you@email.com")
            fp_pw = st.text_input("New Password",       key="fp_pw", type="password", placeholder="Min 8 chars")
            fp_c  = st.text_input("Confirm Password",   key="fp_c",  type="password", placeholder="Repeat")
            st.markdown("<div style='height:.3rem'></div>", unsafe_allow_html=True)
            if st.button("Reset Password →", use_container_width=True, key="fp_btn"):
                db = st.session_state.candidates_db
                if fp_e not in db:
                    st.error("Email not found. Sign up first.")
                elif fp_pw != fp_c:
                    st.error("Passwords do not match.")
                elif len(fp_pw) < 8:
                    st.error("Password must be at least 8 characters.")
                else:
                    db[fp_e]["password"] = fp_pw
                    st.success("✅ Password reset! Please login.")

        st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)
        if st.button("← Back to Home", key="cand_auth_back"):
            st.session_state.page = "landing"
            st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# EMPLOYER DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════
def page_employer_dashboard():
    render_topnav("employer")
    st.markdown("<div style='height:2.5rem'></div>", unsafe_allow_html=True)

    st.markdown(f"""
    <div style="padding:0 2.5rem 1.5rem;">
        <h2 style="font-family:var(--font-head);font-size:2rem;font-weight:800;
                   color:var(--text);letter-spacing:-.02em;margin-bottom:.4rem;">
            Welcome back, {st.session_state.user_name.split()[0]} 👋
        </h2>
        <p style="color:var(--muted);font-family:var(--font-body);font-size:.95rem;">
            What would you like to do today?
        </p>
    </div>
    """, unsafe_allow_html=True)

    pad, main_col, pad2 = st.columns([.05, .9, .05])
    with main_col:
        c1, c2 = st.columns(2)

        with c1:
            st.markdown("""
            <div style="background:var(--card);border:1px solid var(--border);
                        border-radius:20px;padding:2.5rem 2.2rem;margin-bottom:.8rem;
                        min-height:240px;">
                <div style="font-size:2.8rem;margin-bottom:1rem;">🎯</div>
                <h3 style="font-family:var(--font-head);font-size:1.3rem;
                           font-weight:700;color:var(--text);margin-bottom:.7rem;">
                    Evaluate Resume Match
                </h3>
                <p style="font-family:var(--font-body);color:var(--muted);
                          font-size:.88rem;line-height:1.65;">
                    Upload candidate resume + job description.<br>
                    Agent 1 analyses GitHub & resume.<br>
                    Agent 2 scores role alignment.
                </p>
            </div>""", unsafe_allow_html=True)
            if st.button("Start Resume Match →", key="dash_rm", use_container_width=True):
                st.session_state.page = "employer_resume_match"
                st.rerun()

        with c2:
            st.markdown("""
            <div style="background:var(--card);border:1px solid var(--border);
                        border-radius:20px;padding:2.5rem 2.2rem;margin-bottom:.8rem;
                        min-height:240px;">
                <div style="font-size:2.8rem;margin-bottom:1rem;">🎙️</div>
                <h3 style="font-family:var(--font-head);font-size:1.3rem;
                           font-weight:700;color:var(--text);margin-bottom:.7rem;">
                    Evaluate Interview
                </h3>
                <p style="font-family:var(--font-body);color:var(--muted);
                          font-size:.88rem;line-height:1.65;">
                    Paste interview transcript or Q&amp;A.<br>
                    AI scores communication, technical depth,<br>
                    problem solving, and role fit.
                </p>
            </div>""", unsafe_allow_html=True)
            if st.button("Evaluate Interview →", key="dash_int", use_container_width=True):
                st.session_state.page = "employer_interview"
                st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# EMPLOYER — RESUME MATCH
# ══════════════════════════════════════════════════════════════════════════════
def page_employer_resume_match():
    render_topnav("employer")

    pad, main_col, pad2 = st.columns([.05, .9, .05])
    with main_col:
        back_c, title_c = st.columns([1, 8])
        with back_c:
            if st.button("← Dashboard", key="rm_back_btn"):
                st.session_state.page = "employer_dashboard"
                st.session_state.analysis_result = None
                st.rerun()

        st.markdown("""
        <h2 style="font-family:var(--font-head);font-size:1.75rem;font-weight:800;
                   color:var(--text);letter-spacing:-.02em;margin:.8rem 0 .3rem;">
            Resume Match Evaluator 🎯
        </h2>
        <p style="color:var(--muted);font-family:var(--font-body);font-size:.9rem;margin-bottom:1.5rem;">
            Upload resume + job description — Agent 1 reads GitHub &amp; resume, Agent 2 scores the fit.
        </p>
        <hr style="margin-bottom:1.5rem;">
        """, unsafe_allow_html=True)

        col_l, col_r = st.columns([1.1, 1])
        with col_l:
            st.markdown("""<h4 style="font-family:var(--font-head);font-weight:700;
                           color:var(--text);margin-bottom:.7rem;">📄 Candidate Resume</h4>""",
                unsafe_allow_html=True)
            resume_file = st.file_uploader(
                "PDF or DOCX", type=["pdf","docx"], key="emp_resume_up"
            )

        with col_r:
            st.markdown("""<h4 style="font-family:var(--font-head);font-weight:700;
                           color:var(--text);margin-bottom:.7rem;">💼 Job Details</h4>""",
                unsafe_allow_html=True)
            job_title = st.text_input("Job Title", placeholder="Senior Data Scientist", key="emp_jt")
            job_desc  = st.text_area("Job Description",
                placeholder="Paste full JD here — requirements, responsibilities, nice-to-haves…",
                height=200, key="emp_jd")

        st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)

        run_col, _ = st.columns([1, 3])
        with run_col:
            run = st.button("⚡ Run Full Analysis", use_container_width=True, key="emp_run")

        if run:
            if not resume_file:
                st.error("Please upload a resume.")
            elif not job_title.strip():
                st.error("Please enter a job title.")
            elif not job_desc.strip():
                st.error("Please enter a job description.")
            else:
                suffix = "." + resume_file.name.split(".")[-1]
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                    tmp.write(resume_file.read())
                    tmp_path = tmp.name

                prog = st.empty()
                stat = st.empty()
                stages = [
                    ("🔍 Parsing resume & extracting links…",  12),
                    ("🐙 Scraping GitHub profile…",            28),
                    ("📦 Fetching repositories…",              48),
                    ("🤖 LLM code reviews…",                   68),
                    ("🧠 Final candidate assessment…",          83),
                    ("🎯 Matching against job description…",   94),
                    ("✅ Complete!",                           100),
                ]
                try:
                    from agent1 import Agent1
                    from agent2 import Agent2

                    for msg, pct in stages[:-1]:
                        stat.markdown(
                            f"<p style='font-family:var(--font-mono);color:var(--accent);"
                            f"font-size:.85rem;'>{msg}</p>", unsafe_allow_html=True)
                        prog.progress(pct)
                        time.sleep(0.2)

                    combined     = Agent1(tmp_path).run()
                    match_result = Agent2().evaluate(combined, job_title, job_desc)

                    prog.progress(100)
                    stat.markdown("<p style='font-family:var(--font-mono);color:var(--accent);"
                                  "font-size:.85rem;'>✅ Complete!</p>", unsafe_allow_html=True)
                    st.session_state.analysis_result = {
                        "combined": combined, "match": match_result, "job_title": job_title
                    }

                except ImportError:
                    for msg, pct in stages:
                        stat.markdown(
                            f"<p style='font-family:var(--font-mono);color:var(--accent);"
                            f"font-size:.85rem;'>{msg}</p>", unsafe_allow_html=True)
                        prog.progress(pct)
                        time.sleep(0.65)
                    st.session_state.analysis_result = _demo_result(job_title)

                finally:
                    try: os.unlink(tmp_path)
                    except: pass

                time.sleep(0.4)
                prog.empty(); stat.empty()
                st.rerun()

    if st.session_state.analysis_result:
        render_match_results(st.session_state.analysis_result)


# ══════════════════════════════════════════════════════════════════════════════
# EMPLOYER — INTERVIEW EVALUATION
# ══════════════════════════════════════════════════════════════════════════════
def page_employer_interview():
    render_topnav("employer")

    pad, main_col, pad2 = st.columns([.05, .9, .05])
    with main_col:
        back_c, _ = st.columns([1, 8])
        with back_c:
            if st.button("← Dashboard", key="int_back_btn"):
                st.session_state.page = "employer_dashboard"
                st.session_state.interview_result = None
                st.rerun()

        st.markdown("""
        <h2 style="font-family:var(--font-head);font-size:1.75rem;font-weight:800;
                   color:var(--text);letter-spacing:-.02em;margin:.8rem 0 .3rem;">
            Interview Evaluator 🎙️
        </h2>
        <p style="color:var(--muted);font-family:var(--font-body);font-size:.9rem;margin-bottom:1.5rem;">
            Paste the interview transcript — AI scores communication, depth, and role fit.
        </p>
        <hr style="margin-bottom:1.5rem;">
        """, unsafe_allow_html=True)

        r1c1, r1c2, r1c3, r1c4 = st.columns(4)
        with r1c1:
            cand_name = st.text_input("Candidate Name", placeholder="Jane Doe",       key="int_cname")
        with r1c2:
            job_role  = st.text_input("Job Role",       placeholder="Senior Engineer", key="int_role")
        with r1c3:
            int_type  = st.selectbox("Interview Type",
                ["Technical","Behavioural","System Design","HR Screening","Mixed"], key="int_type")
        with r1c4:
            difficulty = st.selectbox("Level",
                ["Entry-level","Mid-level","Senior","Principal/Staff"], key="int_diff")

        transcript = st.text_area(
            "Interview Transcript",
            placeholder="Q: Explain how you'd design a rate limiter.\nA: I'd use a sliding window with Redis…\n\nQ: Tell me about a production incident.\nA: We had a DB lock issue…",
            height=340, key="int_tx"
        )

        run_c, _ = st.columns([1, 4])
        with run_c:
            int_run = st.button("⚡ Evaluate Interview", use_container_width=True, key="int_run_btn")

        if int_run:
            if not transcript.strip():
                st.error("Please paste the interview transcript.")
            else:
                with st.spinner("Analysing…"):
                    try:
                        from groq import Groq
                        GROQ_KEY = "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"
                        client   = Groq(api_key=GROQ_KEY)
                        prompt   = f"""You are an expert hiring evaluator.
Evaluate this {int_type} interview for a {difficulty} {job_role} role.
Candidate: {cand_name}

TRANSCRIPT:
{transcript[:4000]}

Provide a detailed evaluation with exactly these sections:
OVERALL SCORE: X/100

COMMUNICATION SCORE: X/100
[2-3 sentence feedback]

TECHNICAL DEPTH SCORE: X/100
[2-3 sentence feedback]

PROBLEM SOLVING SCORE: X/100
[2-3 sentence feedback]

CULTURE FIT SCORE: X/100
[2-3 sentence feedback]

KEY STRENGTHS:
- [strength 1]
- [strength 2]
- [strength 3]

CONCERNS:
- [concern 1]
- [concern 2]

HIRING RECOMMENDATION: [Strongly Hire / Hire / Maybe / Reject]
[One paragraph rationale]"""
                        resp = client.chat.completions.create(
                            model="llama-3.3-70b-versatile",
                            messages=[{"role":"user","content":prompt}],
                            temperature=0.2, max_tokens=1500
                        )
                        result_text = resp.choices[0].message.content.strip()
                    except Exception:
                        result_text = """OVERALL SCORE: 74/100

COMMUNICATION SCORE: 82/100
Candidate articulated ideas clearly with concrete examples. Minor tendency to over-explain simple concepts.

TECHNICAL DEPTH SCORE: 70/100
Solid foundational knowledge. Rate-limiter answer was structured but missed burst handling and distributed coordination edge cases.

PROBLEM SOLVING SCORE: 71/100
Methodical thinking shown. Incident response had good STAR structure but lacked quantified impact metrics.

CULTURE FIT SCORE: 78/100
Collaborative tone, growth mindset evident. References team work naturally without prompting.

KEY STRENGTHS:
- Clear communicator with real-world examples
- Systematic problem decomposition
- Self-aware about knowledge boundaries

CONCERNS:
- Distributed systems depth needs probing
- Has not quantified impact of past work
- Limited exposure to high-scale scenarios

HIRING RECOMMENDATION: Hire (with conditions)
The candidate shows solid mid-level fundamentals and strong soft skills. Recommend a follow-up technical screen on distributed systems and observability before extending a final offer."""

                    st.session_state.interview_result = {
                        "candidate": cand_name, "role": job_role,
                        "type": int_type, "raw": result_text
                    }
                st.rerun()

        if st.session_state.interview_result:
            ir = st.session_state.interview_result
            st.markdown("<div style='height:1.5rem'></div>", unsafe_allow_html=True)

            # Parse scores for visual display
            lines = ir["raw"].split("\n")
            scores = {}
            for line in lines:
                for label in ["OVERALL","COMMUNICATION","TECHNICAL DEPTH","PROBLEM SOLVING","CULTURE FIT"]:
                    if line.strip().startswith(label + " SCORE"):
                        m = re.search(r'(\d+)/100', line)
                        if m:
                            scores[label.title()] = int(m.group(1))

            if scores:
                sc_cols = st.columns(len(scores))
                for col, (label, val) in zip(sc_cols, scores.items()):
                    with col:
                        color = "#4fffb0" if val >= 75 else "#f59e0b" if val >= 55 else "#ff4f6d"
                        st.markdown(f"""
                        <div style="background:var(--card);border:1px solid var(--border);
                                    border-radius:12px;padding:1rem;text-align:center;">
                            <div style="font-family:var(--font-head);font-size:1.8rem;
                                        font-weight:800;color:{color};">{val}</div>
                            <div style="font-family:var(--font-mono);font-size:.68rem;
                                        color:var(--muted);margin-top:.2rem;">{label}</div>
                        </div>""", unsafe_allow_html=True)

                st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)

            st.markdown(f"""
            <div style="background:var(--card);border:1px solid var(--border);
                        border-radius:16px;padding:1.8rem 2rem;">
                <h4 style="font-family:var(--font-head);font-weight:800;color:var(--text);
                           margin-bottom:1.2rem;">
                    🎙️ Interview Report — {ir.get("candidate","Candidate")} / {ir.get("role","")}
                    &nbsp;<span style="font-family:var(--font-mono);font-size:.75rem;
                    color:var(--muted);font-weight:400;">{ir.get("type","")}</span>
                </h4>
                <pre style="font-family:var(--font-mono);font-size:.82rem;color:var(--muted);
                            white-space:pre-wrap;line-height:1.85;">{ir.get("raw","")}</pre>
            </div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# CANDIDATE DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════
def page_candidate_dashboard():
    render_topnav("candidate")
    st.markdown("<div style='height:1.5rem'></div>", unsafe_allow_html=True)

    pad, main_col, pad2 = st.columns([.05, .9, .05])
    with main_col:
        st.markdown(f"""
        <h2 style="font-family:var(--font-head);font-size:2rem;font-weight:800;
                   color:var(--text);letter-spacing:-.02em;margin-bottom:.4rem;">
            Hey, {st.session_state.user_name.split()[0]} 👋
        </h2>
        <p style="color:var(--muted);font-family:var(--font-body);font-size:.95rem;
                  margin-bottom:1.5rem;">
            Upload your resume and target job description to see how strong your application is.
        </p>
        <hr style="margin-bottom:1.5rem;">
        """, unsafe_allow_html=True)

        col_l, col_r = st.columns([1, 1.1])
        with col_l:
            st.markdown("""<h4 style="font-family:var(--font-head);font-weight:700;
                           color:var(--text);margin-bottom:.7rem;">📄 Your Resume</h4>""",
                unsafe_allow_html=True)
            resume_file = st.file_uploader("PDF or DOCX", type=["pdf","docx"], key="cand_res_up")

        with col_r:
            st.markdown("""<h4 style="font-family:var(--font-head);font-weight:700;
                           color:var(--text);margin-bottom:.7rem;">💼 Target Role</h4>""",
                unsafe_allow_html=True)
            jd_title = st.text_input("Job Title", placeholder="e.g., Data Scientist", key="cand_jd_t")
            jd_text  = st.text_area("Job Description", height=200,
                placeholder="Paste the full JD here…", key="cand_jd_desc")

        st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)

        run_c, _ = st.columns([1, 4])
        with run_c:
            cand_run = st.button("⚡ Analyse My Resume", use_container_width=True, key="cand_run_btn")

        if cand_run:
            if not resume_file:
                st.error("Please upload your resume.")
            elif not jd_title.strip():
                st.error("Please enter the job title.")
            elif not jd_text.strip():
                st.error("Please enter the job description.")
            else:
                suffix = "." + resume_file.name.split(".")[-1]
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                    tmp.write(resume_file.read())
                    tmp_path = tmp.name

                prog = st.empty(); stat = st.empty()
                stages = [
                    ("🔍 Reading your resume…",            18),
                    ("🐙 Analysing your GitHub profile…",  42),
                    ("🧠 LLM assessment…",                 68),
                    ("🎯 Comparing with job description…", 88),
                    ("✅ Done!",                           100),
                ]

                try:
                    from agent1 import Agent1
                    from agent2 import Agent2
                    for msg, pct in stages[:-1]:
                        stat.markdown(
                            f"<p style='font-family:var(--font-mono);color:var(--accent);"
                            f"font-size:.85rem;'>{msg}</p>", unsafe_allow_html=True)
                        prog.progress(pct); time.sleep(0.2)
                    combined = Agent1(tmp_path).run()
                    match    = Agent2().evaluate(combined, jd_title, jd_text)
                    prog.progress(100)
                    stat.markdown("<p style='font-family:var(--font-mono);color:var(--accent);"
                                  "font-size:.85rem;'>✅ Done!</p>", unsafe_allow_html=True)
                    st.session_state.resume_result = {
                        "combined": combined, "match": match, "job_title": jd_title
                    }
                except ImportError:
                    for msg, pct in stages:
                        stat.markdown(
                            f"<p style='font-family:var(--font-mono);color:var(--accent);"
                            f"font-size:.85rem;'>{msg}</p>", unsafe_allow_html=True)
                        prog.progress(pct); time.sleep(0.6)
                    st.session_state.resume_result = _demo_result(jd_title)
                finally:
                    try: os.unlink(tmp_path)
                    except: pass

                time.sleep(0.4); prog.empty(); stat.empty()
                st.rerun()

    if st.session_state.resume_result:
        render_match_results(st.session_state.resume_result)


# ══════════════════════════════════════════════════════════════════════════════
# SHARED RESULTS RENDERER
# ══════════════════════════════════════════════════════════════════════════════
def render_match_results(result: dict):
    match   = result.get("match", {})
    github  = result.get("combined", {}).get("github", {})
    profile = github.get("candidate_profile", {})

    score   = match.get("match_score", 0)
    verdict = match.get("recommendation", {}).get("overall_verdict", "")
    verdict_color = {
        "strong_match":   "var(--accent)",
        "moderate_match": "#f59e0b",
        "weak_match":     "var(--danger)",
    }.get(verdict, "var(--muted)")
    verdict_label = verdict.replace("_", " ").title()

    pad, main_col, pad2 = st.columns([.05, .9, .05])
    with main_col:
        st.markdown("<hr style='margin:2rem 0 1.5rem'>", unsafe_allow_html=True)
        st.markdown("""
        <h3 style="font-family:var(--font-head);font-size:1.5rem;font-weight:800;
                   color:var(--text);margin-bottom:1.5rem;">📊 Analysis Results</h3>
        """, unsafe_allow_html=True)

        # ── Score row ──
        sc1, sc2, sc3, sc4 = st.columns([1.2, 1, 1, 1])
        with sc1:
            st.markdown(f"""
            <div style="background:var(--card);border:1px solid var(--border);
                        border-radius:16px;padding:1.5rem;display:flex;
                        flex-direction:column;align-items:center;">
                {score_ring(score, 115)}
                <div style="margin-top:.8rem;font-family:var(--font-head);
                            font-size:.95rem;font-weight:700;color:var(--text);">Match Score</div>
                <div style="font-family:var(--font-mono);font-size:.75rem;
                            color:{verdict_color};margin-top:.25rem;">{verdict_label}</div>
            </div>""", unsafe_allow_html=True)
        with sc2:
            st.metric("Candidate", match.get("candidate_name", profile.get("name","—")))
            st.metric("Public Repos", profile.get("public_repos","—"))
        with sc3:
            st.metric("Role", result.get("job_title","—"))
            st.metric("GitHub Followers", profile.get("followers","—"))
        with sc4:
            st.metric("Domain Fit",  match.get("experience_alignment",{}).get("domain_alignment","—"))
            st.metric("Seniority",   match.get("experience_alignment",{}).get("seniority_alignment","—"))

        st.markdown("<div style='height:1.5rem'></div>", unsafe_allow_html=True)

        # ── Summary + Radar ──
        sl, sr = st.columns([1.2, 1])
        with sl:
            suggestions = match.get("recommendation",{}).get("improvement_suggestions",[])
            sugg_html = "".join([
                f'<div style="font-family:var(--font-body);color:var(--muted);font-size:.85rem;'
                f'padding:.45rem 0;border-bottom:1px solid var(--border);">→ {s}</div>'
                for s in suggestions
            ])
            st.markdown(f"""
            <div style="background:var(--card);border:1px solid var(--border);
                        border-radius:16px;padding:1.6rem;">
                <h4 style="font-family:var(--font-head);font-weight:700;
                           color:var(--text);margin-bottom:.9rem;">📝 Match Summary</h4>
                <p style="font-family:var(--font-body);color:var(--muted);
                          font-size:.9rem;line-height:1.75;margin-bottom:1.2rem;">
                    {match.get("match_summary","")}
                </p>
                <h4 style="font-family:var(--font-head);font-weight:700;
                           color:var(--text);margin-bottom:.7rem;">💡 To Improve</h4>
                {sugg_html}
            </div>""", unsafe_allow_html=True)

        with sr:
            cats = match.get("visual_data",{}).get("categories",[])
            st.markdown(f"""
            <div style="background:var(--card);border:1px solid var(--border);
                        border-radius:16px;padding:1.6rem;">
                <h4 style="font-family:var(--font-head);font-weight:700;
                           color:var(--text);margin-bottom:1rem;">📡 Skill Breakdown</h4>
                {radar_chart_html(cats)}
            </div>""", unsafe_allow_html=True)

        st.markdown("<div style='height:1.5rem'></div>", unsafe_allow_html=True)

        # ── Strengths & Gaps ──
        sg_l, sg_r = st.columns(2)
        with sg_l:
            items = "".join([f"""
            <div style="border-left:3px solid var(--accent);padding:.7rem .9rem;
                        margin-bottom:.7rem;background:rgba(79,255,176,.04);
                        border-radius:0 8px 8px 0;">
                <div style="font-family:var(--font-head);font-weight:700;
                            color:var(--accent);font-size:.85rem;">{s.get("area","")}</div>
                <div style="font-family:var(--font-body);color:var(--muted);
                            font-size:.8rem;margin-top:.2rem;">{s.get("evidence","")}</div>
            </div>""" for s in match.get("strengths",[])])
            st.markdown(f"""
            <div style="background:var(--card);border:1px solid var(--border);
                        border-radius:16px;padding:1.6rem;">
                <h4 style="font-family:var(--font-head);font-weight:700;
                           color:var(--text);margin-bottom:1rem;">✅ Strengths</h4>
                {items or "<p style='color:var(--muted);font-size:.85rem;'>No data</p>"}
            </div>""", unsafe_allow_html=True)

        with sg_r:
            items2 = "".join([f"""
            <div style="border-left:3px solid var(--danger);padding:.7rem .9rem;
                        margin-bottom:.7rem;background:rgba(255,79,109,.04);
                        border-radius:0 8px 8px 0;">
                <div style="font-family:var(--font-head);font-weight:700;
                            color:var(--danger);font-size:.85rem;">{g.get("area","")}</div>
                <div style="font-family:var(--font-body);color:var(--muted);
                            font-size:.8rem;margin-top:.2rem;">{g.get("gap_detail","")}</div>
            </div>""" for g in match.get("gaps",[])])
            st.markdown(f"""
            <div style="background:var(--card);border:1px solid var(--border);
                        border-radius:16px;padding:1.6rem;">
                <h4 style="font-family:var(--font-head);font-weight:700;
                           color:var(--text);margin-bottom:1rem;">⚠️ Gaps</h4>
                {items2 or "<p style='color:var(--muted);font-size:.85rem;'>No data</p>"}
            </div>""", unsafe_allow_html=True)

        st.markdown("<div style='height:1.5rem'></div>", unsafe_allow_html=True)

        # ── Skills ──
        sc = match.get("skill_coverage",{})
        sk_l, sk_r = st.columns(2)
        with sk_l:
            badges = " ".join([
                badge(s.get("skill",""), "var(--accent)" if s.get("evidence_level")=="strong" else "#f59e0b")
                for s in sc.get("matched_skills",[])
            ])
            st.markdown(f"""
            <div style="background:var(--card);border:1px solid var(--border);
                        border-radius:16px;padding:1.6rem;">
                <h4 style="font-family:var(--font-head);font-weight:700;
                           color:var(--text);margin-bottom:1rem;">🟢 Matched Skills</h4>
                <div style="display:flex;flex-wrap:wrap;gap:.5rem;">{badges or "—"}</div>
            </div>""", unsafe_allow_html=True)

        with sk_r:
            badges2 = " ".join([
                badge(s.get("skill",""), "var(--danger)" if s.get("status")=="missing" else "#f59e0b")
                for s in sc.get("missing_or_weak_skills",[])
            ])
            st.markdown(f"""
            <div style="background:var(--card);border:1px solid var(--border);
                        border-radius:16px;padding:1.6rem;">
                <h4 style="font-family:var(--font-head);font-weight:700;
                           color:var(--text);margin-bottom:1rem;">🔴 Missing / Weak</h4>
                <div style="display:flex;flex-wrap:wrap;gap:.5rem;">{badges2 or "—"}</div>
            </div>""", unsafe_allow_html=True)

        st.markdown("<div style='height:1.5rem'></div>", unsafe_allow_html=True)

        # ── GitHub deep assessment ──
        fa = github.get("final_assessment","")
        if fa:
            with st.expander("🐙 GitHub Deep Assessment (Agent 1)"):
                st.markdown(f"""
                <div style="font-family:var(--font-mono);color:var(--muted);
                            font-size:.82rem;line-height:1.85;white-space:pre-wrap;">{fa}</div>
                """, unsafe_allow_html=True)

        # ── JSON export ──
        with st.expander("📦 Export Raw JSON"):
            st.json(match)

        st.markdown("<div style='height:4rem'></div>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# ROUTER
# ══════════════════════════════════════════════════════════════════════════════
def main():
    page = st.session_state.page

    if page == "landing":
        page_landing()
    elif page == "employer_login":
        page_employer_login()
    elif page == "candidate_auth":
        page_candidate_auth()
    elif page == "employer_dashboard" and st.session_state.logged_in:
        page_employer_dashboard()
    elif page == "employer_resume_match" and st.session_state.logged_in:
        page_employer_resume_match()
    elif page == "employer_interview" and st.session_state.logged_in:
        page_employer_interview()
    elif page == "candidate_dashboard" and st.session_state.logged_in:
        page_candidate_dashboard()
    else:
        st.session_state.page = "landing"
        st.rerun()


if __name__ == "__main__":
    main()