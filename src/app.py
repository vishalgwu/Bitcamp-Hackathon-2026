import streamlit as st
import streamlit.components.v1 as components
import base64
import bcrypt
import json
import os
import math
from pymongo import MongoClient
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="hire.ai", layout="wide", initial_sidebar_state="collapsed")

# ─────────────────────────────────────────
# MONGODB
# ─────────────────────────────────────────
@st.cache_resource
def get_db():
    uri = os.environ.get("MONGODB_URI", "mongodb://localhost:27017")
    client = MongoClient(uri)
    return client["hireai"]

db = get_db()
employers_col = db["employers"]
candidates_col = db["candidates"]

def check_password(password, hashed):
    return bcrypt.checkpw(password.encode('utf-8'), hashed)

def hash_password(password):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

def login_employer(email, password):
    user = employers_col.find_one({"email": email})
    if not user: return False, "No account found with this email."
    if not check_password(password, user["password"]): return False, "Incorrect password."
    return True, user

def login_candidate(email, password):
    user = candidates_col.find_one({"email": email})
    if not user: return False, "No account found with this email."
    if not check_password(password, user["password"]): return False, "Incorrect password."
    return True, user

def register_candidate(full_name, email, password, github_url, skills):
    if candidates_col.find_one({"email": email}): return False, "Email already registered."
    candidates_col.insert_one({
        "full_name": full_name, "email": email,
        "password": hash_password(password),
        "github_url": github_url,
        "skills": [s.strip() for s in skills.split(",") if s.strip()],
        "created_at": datetime.now(timezone.utc)
    })
    return True, "Account created!"

# ─────────────────────────────────────────
# SESSION STATE
# ─────────────────────────────────────────
for key, val in {
    'view': 'home', 'user': None, 'role': None,
    'employer_auth_mode': 'login', 'candidate_auth_mode': 'login',
    'agent1_result': None, 'agent2_result': None,
    'interview_results': None
}.items():
    if key not in st.session_state:
        st.session_state[key] = val

# ─────────────────────────────────────────
# VIDEO
# ─────────────────────────────────────────
@st.cache_resource
def get_video_b64():
    with open("7647680-hd_1920_1080_30fps.mp4", "rb") as f:
        return base64.b64encode(f.read()).decode()

# ─────────────────────────────────────────
# SHARED CSS
# ─────────────────────────────────────────
DARK_CSS = """<style>
#MainMenu, header, footer { visibility: hidden; }
.stApp { background: #080812 !important; }
[data-testid="stAppViewContainer"] { background: #080812 !important; }
[data-testid="stMain"] { background: transparent !important; }
.block-container { padding: 2rem 3rem !important; max-width: 100% !important; }
* { color: #e8e8f0; }
hr { border-color: rgba(255,255,255,0.06) !important; margin: 0 0 2rem 0 !important; }
.nav-logo { font-size: 26px; font-weight: 900; color: white; letter-spacing: -1px; font-family: 'Arial Black', sans-serif; line-height: 1; }
.nav-logo span { color: #7c6fff; }
.nav-tag { font-size: 11px; color: rgba(255,255,255,0.3); font-weight: 400; letter-spacing: 3px; text-transform: uppercase; margin-top: 4px; }
.stTextInput input, .stTextArea textarea {
    background: #13132a !important; border: 1px solid rgba(255,255,255,0.08) !important;
    border-radius: 10px !important; color: #ffffff !important; font-size: 14px !important;
}
.stTextInput input:focus, .stTextArea textarea:focus {
    border: 1px solid #7c6fff !important; box-shadow: 0 0 0 3px rgba(124,111,255,0.15) !important;
}
.stTextInput input::placeholder, .stTextArea textarea::placeholder { color: rgba(255,255,255,0.2) !important; }
label[data-testid="stWidgetLabel"] p {
    color: rgba(255,255,255,0.5) !important; font-size: 12px !important;
    font-weight: 500 !important; letter-spacing: 1px !important; text-transform: uppercase !important;
}
.stSelectbox > div > div { background: #13132a !important; border: 1px solid rgba(255,255,255,0.08) !important; border-radius: 10px !important; color: white !important; }
[data-testid="stFileUploader"] { background: #13132a !important; border: 1px dashed rgba(255,255,255,0.1) !important; border-radius: 12px !important; padding: 1rem !important; }
.stButton > button {
    background: linear-gradient(135deg, #7c6fff 0%, #4f8fff 100%) !important;
    color: white !important; border: none !important; border-radius: 10px !important;
    font-weight: 700 !important; font-size: 14px !important; letter-spacing: 0.5px !important;
    padding: 14px 28px !important; width: 100% !important; transition: all 0.2s ease !important;
    box-shadow: 0 4px 20px rgba(124,111,255,0.3) !important;
}
.stButton > button:hover { transform: translateY(-2px) !important; box-shadow: 0 8px 30px rgba(124,111,255,0.5) !important; }
.ghost-btn > button {
    background: transparent !important; border: 1px solid rgba(255,255,255,0.1) !important;
    color: rgba(255,255,255,0.5) !important; width: auto !important; box-shadow: none !important; padding: 8px 18px !important;
}
.ghost-btn > button:hover { background: rgba(255,255,255,0.05) !important; transform: none !important; box-shadow: none !important; color: white !important; }
.link-btn > button { background: transparent !important; border: 1px solid rgba(124,111,255,0.3) !important; color: #7c6fff !important; box-shadow: none !important; font-weight: 600 !important; }
.link-btn > button:hover { background: rgba(124,111,255,0.08) !important; transform: none !important; box-shadow: none !important; }
[data-testid="stTabs"] button { color: rgba(255,255,255,0.35) !important; font-size: 14px !important; font-weight: 600 !important; padding: 12px 24px !important; border-radius: 0 !important; border-bottom: 2px solid transparent !important; background: transparent !important; }
[data-testid="stTabs"] button[aria-selected="true"] { color: white !important; border-bottom: 2px solid #7c6fff !important; }
[data-testid="stTabsContent"] { padding-top: 2rem !important; }
.label { font-size: 10px; letter-spacing: 3px; text-transform: uppercase; color: rgba(255,255,255,0.35) !important; font-weight: 600; margin-bottom: 8px; display: block; }
.auth-card { background: #0e0e20; border: 1px solid rgba(255,255,255,0.06); border-radius: 20px; padding: 3rem 2.5rem; }
.auth-title { font-size: 32px; font-weight: 900; color: white !important; font-family: 'Arial Black', sans-serif; letter-spacing: -1px; margin-bottom: 6px; }
.auth-sub { font-size: 14px; color: rgba(255,255,255,0.35) !important; margin-bottom: 2.5rem; line-height: 1.5; }
.divider-text { text-align: center; font-size: 12px; color: rgba(255,255,255,0.2) !important; margin: 1rem 0; }
</style>"""

# ─────────────────────────────────────────
# SLIM AGENT1 RESULT FOR AGENT2
# ─────────────────────────────────────────
def slim_agent1_result(result):
    """Remove heavy repo data before sending to agent2 to avoid JSON truncation."""
    slimmed = {"resume": result.get("resume", {})}
    github = result.get("github", {})
    if github:
        slimmed["github"] = {
            "candidate_profile": github.get("candidate_profile", {}),
            "skills_summary":    github.get("skills_summary", {}),
            "repository_summary": github.get("repository_summary", {}),
            "final_assessment":  github.get("final_assessment", {}),
        }
    return slimmed

# ─────────────────────────────────────────
# AGENT2 VISUALIZATION
# ─────────────────────────────────────────
def render_agent2_results(result):
    score        = result.get("match_score", 0)
    verdict      = result.get("recommendation", {}).get("overall_verdict", "moderate_match")
    summary      = result.get("match_summary", "")
    strengths    = result.get("strengths", [])
    gaps         = result.get("gaps", [])
    skill_coverage  = result.get("skill_coverage", {})
    matched_skills  = skill_coverage.get("matched_skills", [])
    missing_skills  = skill_coverage.get("missing_or_weak_skills", [])
    visual_data  = result.get("visual_data", {})
    categories   = visual_data.get("categories", [])
    experience   = result.get("experience_alignment", {})
    improvement  = result.get("recommendation", {}).get("improvement_suggestions", [])

    verdict_map = {
        "strong_match":   ("#22c55e", "STRONG MATCH"),
        "moderate_match": ("#f59e0b", "MODERATE MATCH"),
        "weak_match":     ("#ef4444", "WEAK MATCH"),
        "very_strong":    ("#22c55e", "VERY STRONG MATCH"),
        "strong":         ("#22c55e", "STRONG MATCH"),
        "good":           ("#6c63ff", "GOOD MATCH"),
        "moderate":       ("#f59e0b", "MODERATE MATCH"),
        "poor":           ("#ef4444", "POOR MATCH"),
        "very_poor":      ("#ef4444", "VERY POOR MATCH"),
    }
    verdict_color, verdict_label = verdict_map.get(verdict, ("#f59e0b", "MODERATE MATCH"))
    score_color = "#22c55e" if score >= 75 else "#f59e0b" if score >= 45 else "#ef4444"

    # Build radar SVG parts
    n = len(categories)
    radar_points = ""
    radar_labels_html = ""
    grid_rings = ""
    axis_lines = ""
    dot_circles = ""
    cx, cy, r_outer = 200, 200, 150

    if n > 0:
        for pct in [25, 50, 75, 100]:
            ring_pts = " ".join([
                f"{cx + (r_outer*pct/100)*math.cos((2*math.pi*i/n)-math.pi/2):.1f},"
                f"{cy + (r_outer*pct/100)*math.sin((2*math.pi*i/n)-math.pi/2):.1f}"
                for i in range(n)
            ])
            grid_rings += f'<polygon points="{ring_pts}" fill="none" stroke="rgba(255,255,255,0.06)" stroke-width="1"/>'

        for i in range(n):
            angle = (2*math.pi*i/n) - math.pi/2
            ex = cx + r_outer*math.cos(angle)
            ey = cy + r_outer*math.sin(angle)
            axis_lines += f'<line x1="{cx}" y1="{cy}" x2="{ex:.1f}" y2="{ey:.1f}" stroke="rgba(255,255,255,0.06)" stroke-width="1"/>'

        for i, cat in enumerate(categories):
            angle = (2*math.pi*i/n) - math.pi/2
            s = cat["score"]
            rx = cx + (r_outer*s/100)*math.cos(angle)
            ry = cy + (r_outer*s/100)*math.sin(angle)
            radar_points += f"{rx:.1f},{ry:.1f} "
            dot_circles += f'<circle cx="{rx:.1f}" cy="{ry:.1f}" r="4" fill="#7c6fff" stroke="white" stroke-width="1.5"/>'
            lx = cx + (r_outer+28)*math.cos(angle)
            ly = cy + (r_outer+28)*math.sin(angle)
            anchor = "middle"
            if lx < cx-10: anchor = "end"
            elif lx > cx+10: anchor = "start"
            short = cat["name"][:12]
            radar_labels_html += f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="{anchor}" fill="rgba(255,255,255,0.5)" font-size="9" font-family="Arial">{short}</text>'

    circ   = 2*math.pi*65
    dash   = circ*score/100
    offset = circ*0.25

    # ── Score ring + Radar ──
    col_ring, col_radar = st.columns([1, 2])
    with col_ring:
        st.markdown(f"""
        <div style="background:#0e0e20;border:1px solid rgba(255,255,255,0.06);border-radius:16px;padding:2rem;display:flex;flex-direction:column;align-items:center;justify-content:center;">
            <div style="font-size:10px;letter-spacing:3px;color:rgba(255,255,255,0.3);text-transform:uppercase;margin-bottom:1rem;">Match Score</div>
            <svg width="160" height="160" viewBox="0 0 160 160">
                <circle cx="80" cy="80" r="65" fill="none" stroke="rgba(255,255,255,0.06)" stroke-width="12"/>
                <circle cx="80" cy="80" r="65" fill="none" stroke="{score_color}" stroke-width="12"
                    stroke-dasharray="{dash:.1f} {circ:.1f}"
                    stroke-dashoffset="{offset:.1f}"
                    stroke-linecap="round"
                    style="filter:drop-shadow(0 0 8px {score_color});"/>
                <text x="80" y="75" text-anchor="middle" fill="white" font-size="32" font-weight="900" font-family="Arial Black">{score}</text>
                <text x="80" y="95" text-anchor="middle" fill="rgba(255,255,255,0.4)" font-size="11" font-family="Arial">/100</text>
            </svg>
            <div style="display:inline-block;padding:6px 16px;background:{verdict_color}22;border:1px solid {verdict_color};border-radius:20px;margin-top:1rem;">
                <span style="color:{verdict_color};font-weight:700;font-size:10px;letter-spacing:2px;">{verdict_label}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col_radar:
        st.markdown(f"""
        <div style="background:#0e0e20;border:1px solid rgba(255,255,255,0.06);border-radius:16px;padding:2rem;">
            <div style="font-size:10px;letter-spacing:3px;color:rgba(255,255,255,0.3);text-transform:uppercase;margin-bottom:1rem;">Skill Radar</div>
            <svg width="100%" viewBox="0 0 400 400" style="max-height:280px;">
                {grid_rings}{axis_lines}
                <polygon points="{radar_points.strip()}" fill="rgba(124,111,255,0.2)" stroke="#7c6fff" stroke-width="2"/>
                {dot_circles}{radar_labels_html}
            </svg>
        </div>
        """, unsafe_allow_html=True)

    # ── Summary ──
    st.markdown(f"""
    <div style="background:#0e0e20;border:1px solid rgba(255,255,255,0.06);border-radius:14px;padding:1.5rem;margin-top:1rem;margin-bottom:1.5rem;">
        <div style="font-size:10px;letter-spacing:3px;color:rgba(255,255,255,0.3);text-transform:uppercase;margin-bottom:8px;">Match Summary</div>
        <p style="color:rgba(255,255,255,0.7);font-size:14px;line-height:1.8;margin:0;">{summary}</p>
    </div>
    """, unsafe_allow_html=True)

    # ── Bar chart ──
    bar_rows = ""
    for c in categories:
        bc = "#22c55e" if c["score"]>=75 else "#f59e0b" if c["score"]>=45 else "#ef4444"
        bar_rows += f"""
        <div style="margin-bottom:14px;">
            <div style="display:flex;justify-content:space-between;margin-bottom:4px;">
                <span style="font-size:12px;color:rgba(255,255,255,0.6);">{c['name']}</span>
                <span style="font-size:12px;font-weight:700;color:{bc};">{c['score']}</span>
            </div>
            <div style="background:rgba(255,255,255,0.05);border-radius:4px;height:6px;">
                <div style="background:{bc};width:{c['score']}%;height:6px;border-radius:4px;box-shadow:0 0 8px {bc}55;"></div>
            </div>
        </div>"""

   
    st.markdown("""
    <div style="background:#0e0e20;border:1px solid rgba(255,255,255,0.06);border-radius:14px;padding:1.5rem;margin-bottom:1.5rem;">
        <div style="font-size:10px;letter-spacing:3px;color:rgba(255,255,255,0.3);text-transform:uppercase;margin-bottom:1.5rem;">Category Breakdown</div>
    """, unsafe_allow_html=True)

    for c in categories:
        bc = "#22c55e" if c["score"] >= 75 else "#f59e0b" if c["score"] >= 45 else "#ef4444"
        st.markdown(f"""
        <div style="margin-bottom:14px;">
            <div style="display:flex;justify-content:space-between;margin-bottom:4px;">
                <span style="font-size:12px;color:rgba(255,255,255,0.6);">{c['name']}</span>
                <span style="font-size:12px;font-weight:700;color:{bc};">{c['score']}</span>
            </div>
            <div style="background:rgba(255,255,255,0.05);border-radius:4px;height:6px;">
                <div style="background:{bc};width:{c['score']}%;height:6px;border-radius:4px;box-shadow:0 0 8px {bc}55;"></div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

    # ── Strengths & Gaps ──
    col1, col2 = st.columns(2)
    strengths_html = "".join([f"""
        <div style="background:#0a1a12;border:1px solid rgba(34,197,94,0.15);border-radius:10px;padding:1rem;margin-bottom:0.75rem;">
            <div style="font-size:11px;font-weight:700;color:#22c55e;margin-bottom:4px;">{s.get('area','')}</div>
            <div style="font-size:12px;color:rgba(255,255,255,0.6);margin-bottom:4px;">{s.get('evidence','')}</div>
            <div style="font-size:11px;color:rgba(34,197,94,0.6);font-style:italic;">{s.get('relevance_to_job','')}</div>
        </div>""" for s in strengths])

    gaps_html = "".join([f"""
        <div style="background:#1a0a0a;border:1px solid rgba(239,68,68,0.15);border-radius:10px;padding:1rem;margin-bottom:0.75rem;">
            <div style="font-size:11px;font-weight:700;color:#ef4444;margin-bottom:4px;">{g.get('area','')}</div>
            <div style="font-size:12px;color:rgba(255,255,255,0.6);margin-bottom:4px;">{g.get('gap_detail','')}</div>
            <div style="font-size:11px;color:rgba(239,68,68,0.6);font-style:italic;">{g.get('impact_on_match','')}</div>
        </div>""" for g in gaps])

    with col1:
        st.markdown("<div style='font-size:10px;letter-spacing:3px;color:rgba(255,255,255,0.3);text-transform:uppercase;margin-bottom:1rem;'>Strengths</div>", unsafe_allow_html=True)
        for s in strengths:
            st.markdown(f"""
            <div style="background:#0a1a12;border:1px solid rgba(34,197,94,0.15);border-radius:10px;padding:1rem;margin-bottom:0.75rem;">
                <div style="font-size:11px;font-weight:700;color:#22c55e;margin-bottom:4px;">{s.get('area','')}</div>
                <div style="font-size:12px;color:rgba(255,255,255,0.6);margin-bottom:4px;">{s.get('evidence','')}</div>
                <div style="font-size:11px;color:rgba(34,197,94,0.6);font-style:italic;">{s.get('relevance_to_job','')}</div>
            </div>
            """, unsafe_allow_html=True)

    with col2:
        st.markdown("<div style='font-size:10px;letter-spacing:3px;color:rgba(255,255,255,0.3);text-transform:uppercase;margin-bottom:1rem;'>Gaps</div>", unsafe_allow_html=True)
        for g in gaps:
            st.markdown(f"""
            <div style="background:#1a0a0a;border:1px solid rgba(239,68,68,0.15);border-radius:10px;padding:1rem;margin-bottom:0.75rem;">
                <div style="font-size:11px;font-weight:700;color:#ef4444;margin-bottom:4px;">{g.get('area','')}</div>
                <div style="font-size:12px;color:rgba(255,255,255,0.6);margin-bottom:4px;">{g.get('gap_detail','')}</div>
                <div style="font-size:11px;color:rgba(239,68,68,0.6);font-style:italic;">{g.get('impact_on_match','')}</div>
            </div>
            """, unsafe_allow_html=True)

    # ── Skill Coverage ──
    matched_html = "".join([
        f'<span style="background:{"#22c55e" if s.get("evidence_level")=="strong" else "#f59e0b"}22;border:1px solid {"#22c55e" if s.get("evidence_level")=="strong" else "#f59e0b"}55;color:{"#22c55e" if s.get("evidence_level")=="strong" else "#f59e0b"};padding:4px 10px;border-radius:20px;font-size:11px;font-weight:600;margin:3px;display:inline-block;">{s.get("skill","")}</span>'
        for s in matched_skills])
    missing_html = "".join([
        f'<span style="background:{"#ef4444" if s.get("status")=="missing" else "#f59e0b"}22;border:1px solid {"#ef4444" if s.get("status")=="missing" else "#f59e0b"}55;color:{"#ef4444" if s.get("status")=="missing" else "#f59e0b"};padding:4px 10px;border-radius:20px;font-size:11px;font-weight:600;margin:3px;display:inline-block;">{s.get("skill","")}</span>'
        for s in missing_skills])
    
    st.markdown("""
    <div style="background:#0e0e20;border:1px solid rgba(255,255,255,0.06);border-radius:14px;padding:1.5rem;margin-bottom:1.5rem;">
        <div style="font-size:10px;letter-spacing:3px;color:rgba(255,255,255,0.3);text-transform:uppercase;margin-bottom:1rem;">Skill Coverage</div>
        <div style="font-size:11px;color:rgba(255,255,255,0.4);margin-bottom:8px;">Matched Skills</div>
    """, unsafe_allow_html=True)

    for s in matched_skills:
        bc = "#22c55e" if s.get("evidence_level") == "strong" else "#f59e0b"
        st.markdown(f'<span style="background:{bc}22;border:1px solid {bc}55;color:{bc};padding:4px 10px;border-radius:20px;font-size:11px;font-weight:600;margin:3px;display:inline-block;">{s.get("skill","")}</span>', unsafe_allow_html=True)

    st.markdown('<div style="font-size:11px;color:rgba(255,255,255,0.4);margin:12px 0 8px 0;">Missing / Weak Skills</div>', unsafe_allow_html=True)

    for s in missing_skills:
        bc = "#ef4444" if s.get("status") == "missing" else "#f59e0b"
        st.markdown(f'<span style="background:{bc}22;border:1px solid {bc}55;color:{bc};padding:4px 10px;border-radius:20px;font-size:11px;font-weight:600;margin:3px;display:inline-block;">{s.get("skill","")}</span>', unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

    # ── Experience Alignment ──
    if experience:
        st.markdown(f"""
        <div style="background:#0e0e20;border:1px solid rgba(255,255,255,0.06);border-radius:14px;padding:1.5rem;margin-bottom:1.5rem;">
            <div style="font-size:10px;letter-spacing:3px;color:rgba(255,255,255,0.3);text-transform:uppercase;margin-bottom:1rem;">Experience Alignment</div>
            <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:1rem;margin-bottom:1rem;">
                <div style="text-align:center;">
                    <div style="font-size:10px;color:rgba(255,255,255,0.3);margin-bottom:4px;">Years</div>
                    <div style="font-size:13px;font-weight:600;color:white;">{experience.get('years_alignment','—')}</div>
                </div>
                <div style="text-align:center;">
                    <div style="font-size:10px;color:rgba(255,255,255,0.3);margin-bottom:4px;">Domain</div>
                    <div style="font-size:13px;font-weight:600;color:white;">{experience.get('domain_alignment','—')}</div>
                </div>
                <div style="text-align:center;">
                    <div style="font-size:10px;color:rgba(255,255,255,0.3);margin-bottom:4px;">Seniority</div>
                    <div style="font-size:13px;font-weight:600;color:white;">{experience.get('seniority_alignment','—')}</div>
                </div>
            </div>
            <p style="color:rgba(255,255,255,0.6);font-size:13px;line-height:1.7;margin:0;">{experience.get('relevant_experience_summary','')}</p>
        </div>
        """, unsafe_allow_html=True)

    # ── Improvement Suggestions ──
    if improvement:
        st.markdown("""
        <div style="background:#0e0e20;border:1px solid rgba(124,111,255,0.15);border-radius:14px;padding:1.5rem;">
            <div style="font-size:10px;letter-spacing:3px;color:rgba(255,255,255,0.3);text-transform:uppercase;margin-bottom:1rem;">Improvement Suggestions</div>
        """, unsafe_allow_html=True)

        for s in improvement:
            st.markdown(f"""
            <div style="display:flex;align-items:flex-start;gap:10px;margin-bottom:10px;">
                <span style="color:#7c6fff;font-size:16px;margin-top:2px;">→</span>
                <span style="font-size:13px;color:rgba(255,255,255,0.6);line-height:1.6;">{s}</span>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("</div>", unsafe_allow_html=True)


# ─────────────────────────────────────────
# HOME
# ─────────────────────────────────────────
if st.session_state.view == 'home':

    params = st.query_params
    if params.get("view") == "employer_auth":
        st.session_state.view = 'employer_auth'; st.query_params.clear(); st.rerun()
    elif params.get("view") == "candidate_auth":
        st.session_state.view = 'candidate_auth'; st.query_params.clear(); st.rerun()

    st.markdown("""<style>
        #MainMenu, header, footer { visibility: hidden; }
        .stApp,[data-testid="stAppViewContainer"],[data-testid="stMain"] { background: #080812 !important; }
        .block-container { padding: 0 !important; margin: 0 !important; max-width: 100% !important; }
        [data-testid="stVerticalBlock"] { gap: 0 !important; }
        html, body { overflow: hidden !important; }
        iframe { display: block; border: none; }
    </style>""", unsafe_allow_html=True)

    video_b64 = get_video_b64()

    components.html(f"""<!DOCTYPE html><html><head><style>
        *{{margin:0;padding:0;box-sizing:border-box;}}
        html,body{{width:100%;height:100%;overflow:hidden;font-family:'Arial Black',sans-serif;background:#080812;}}
        .bg-video{{position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);min-width:100%;min-height:100%;object-fit:cover;z-index:0;}}
        .overlay{{position:absolute;inset:0;background:rgba(8,8,18,0.75);z-index:1;}}
        .hero{{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;z-index:10;text-align:center;padding:0 20px;}}
        .title{{font-size:clamp(52px,10vw,110px);font-weight:900;color:white;letter-spacing:-3px;line-height:1;margin-bottom:12px;opacity:0;animation:fadeUp 0.8s ease forwards;text-shadow:0 0 80px rgba(124,111,255,0.6);}}
        .subtitle{{font-size:clamp(11px,1.5vw,16px);color:rgba(255,255,255,0.4);letter-spacing:6px;text-transform:uppercase;font-family:Arial,sans-serif;font-weight:400;margin-bottom:56px;opacity:0;animation:fadeUp 0.8s ease 0.2s forwards;}}
        .btn-group{{display:flex;flex-direction:column;gap:12px;width:280px;opacity:0;animation:fadeUp 0.8s ease 0.4s forwards;}}
        .btn{{display:block;padding:15px 32px;font-size:12px;font-weight:700;letter-spacing:2.5px;text-transform:uppercase;border-radius:8px;border:1px solid rgba(255,255,255,0.15);background:rgba(255,255,255,0.05);backdrop-filter:blur(20px);color:white;text-decoration:none;text-align:center;transition:all 0.25s ease;}}
        .btn:hover{{background:rgba(124,111,255,0.2);border-color:rgba(124,111,255,0.6);transform:translateY(-2px);box-shadow:0 12px 40px rgba(124,111,255,0.25);color:white;}}
        @keyframes fadeUp{{from{{opacity:0;transform:translateY(20px)}}to{{opacity:1;transform:translateY(0)}}}}
    </style></head><body>
        <video class="bg-video" autoplay loop muted playsinline>
            <source src="data:video/mp4;base64,{video_b64}" type="video/mp4">
        </video>
        <div class="overlay"></div>
        <div class="hero">
            <h1 class="title">hire.ai</h1>
            <p class="subtitle">Beyond the Resume. The full picture.</p>
            <div class="btn-group">
                <a class="btn" href="?view=employer_auth">🚀 Enter as Employer</a>
                <a class="btn" href="?view=candidate_auth">👤 Enter as Candidate</a>
            </div>
        </div>
    </body></html>""", height=800, scrolling=False)


# ─────────────────────────────────────────
# EMPLOYER AUTH
# ─────────────────────────────────────────
elif st.session_state.view == 'employer_auth':
    st.markdown(DARK_CSS, unsafe_allow_html=True)
    col_logo, col_back = st.columns([6, 1])
    with col_logo:
        st.markdown("<div class='nav-logo'>hire<span>.</span>ai<div class='nav-tag'>Employer Portal</div></div>", unsafe_allow_html=True)
    with col_back:
        st.markdown("<div class='ghost-btn'>", unsafe_allow_html=True)
        if st.button("← Back"): st.session_state.view = 'home'; st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("<hr>", unsafe_allow_html=True)

    _, col, _ = st.columns([1, 1, 1])
    with col:
        st.markdown("<div class='auth-card'>", unsafe_allow_html=True)
        st.markdown("<p class='auth-title'>Sign in</p>", unsafe_allow_html=True)
        st.markdown("<p class='auth-sub'>Access your employer dashboard to analyze candidates and score interviews.</p>", unsafe_allow_html=True)
        email = st.text_input("Email", placeholder="you@company.com", key="emp_email")
        password = st.text_input("Password", placeholder="••••••••", type="password", key="emp_pass")
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Sign In →", key="emp_signin"):
            if not email or not password:
                st.warning("Please fill in all fields.")
            else:
                success, result = login_employer(email, password)
                if success:
                    st.session_state.user = result
                    st.session_state.role = 'employer'
                    st.session_state.view = 'employer'
                    st.rerun()
                else:
                    st.error(result)
        st.markdown("</div>", unsafe_allow_html=True)


# ─────────────────────────────────────────
# CANDIDATE AUTH
# ─────────────────────────────────────────
elif st.session_state.view == 'candidate_auth':
    st.markdown(DARK_CSS, unsafe_allow_html=True)
    col_logo, col_back = st.columns([6, 1])
    with col_logo:
        st.markdown("<div class='nav-logo'>hire<span>.</span>ai<div class='nav-tag'>Candidate Portal</div></div>", unsafe_allow_html=True)
    with col_back:
        st.markdown("<div class='ghost-btn'>", unsafe_allow_html=True)
        if st.button("← Back"): st.session_state.view = 'home'; st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("<hr>", unsafe_allow_html=True)

    _, col, _ = st.columns([1, 1, 1])
    with col:
        st.markdown("<div class='auth-card'>", unsafe_allow_html=True)
        if st.session_state.candidate_auth_mode == 'login':
            st.markdown("<p class='auth-title'>Welcome back</p>", unsafe_allow_html=True)
            st.markdown("<p class='auth-sub'>Sign in to check your profile score and match with top roles.</p>", unsafe_allow_html=True)
            email = st.text_input("Email", placeholder="you@email.com", key="can_email")
            password = st.text_input("Password", placeholder="••••••••", type="password", key="can_pass")
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("Sign In →", key="can_signin"):
                if not email or not password:
                    st.warning("Please fill in all fields.")
                else:
                    success, result = login_candidate(email, password)
                    if success:
                        st.session_state.user = result
                        st.session_state.role = 'candidate'
                        st.session_state.view = 'candidate'
                        st.rerun()
                    else:
                        st.error(result)
            st.markdown("<div class='divider-text'>— or —</div>", unsafe_allow_html=True)
            st.markdown("<div class='link-btn'>", unsafe_allow_html=True)
            if st.button("Create an account", key="can_to_register"):
                st.session_state.candidate_auth_mode = 'register'; st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
        else:
            st.markdown("<p class='auth-title'>Get started</p>", unsafe_allow_html=True)
            st.markdown("<p class='auth-sub'>Create your candidate profile and discover how you stack up.</p>", unsafe_allow_html=True)
            col_a, col_b = st.columns(2)
            with col_a: full_name = st.text_input("Full Name", placeholder="Jane Smith", key="can_name")
            with col_b: email = st.text_input("Email", placeholder="you@email.com", key="can_reg_email")
            password = st.text_input("Password", placeholder="Min 6 characters", type="password", key="can_reg_pass")
            github_url = st.text_input("GitHub / Portfolio", placeholder="https://github.com/username", key="can_github")
            skills = st.text_input("Skills", placeholder="Python, React, Machine Learning...", key="can_skills")
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("Create Account →", key="can_register"):
                if not all([full_name, email, password]):
                    st.warning("Please fill in all required fields.")
                elif len(password) < 6:
                    st.warning("Password must be at least 6 characters.")
                else:
                    success, msg = register_candidate(full_name, email, password, github_url, skills)
                    if success:
                        st.success("Account created! Please sign in.")
                        st.session_state.candidate_auth_mode = 'login'; st.rerun()
                    else:
                        st.error(msg)
            st.markdown("<div class='divider-text'>— or —</div>", unsafe_allow_html=True)
            st.markdown("<div class='link-btn'>", unsafe_allow_html=True)
            if st.button("Sign in instead", key="can_to_login"):
                st.session_state.candidate_auth_mode = 'login'; st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)


# ─────────────────────────────────────────
# EMPLOYER DASHBOARD
# ─────────────────────────────────────────
elif st.session_state.view == 'employer':

    if not st.session_state.user:
        st.session_state.view = 'employer_auth'; st.rerun()

    from agent1 import Agent1
    from agent2 import evaluate
    from interview_agent import run_interview_agent

    st.markdown(DARK_CSS, unsafe_allow_html=True)
    user = st.session_state.user

    col_logo, col_back = st.columns([6, 1])
    with col_logo:
        st.markdown(f"<div class='nav-logo'>hire<span>.</span>ai<div class='nav-tag'>{user.get('company_name','')}</div></div>", unsafe_allow_html=True)
    with col_back:
        st.markdown("<div class='ghost-btn'>", unsafe_allow_html=True)
        if st.button("Sign Out"):
            st.session_state.user = None
            st.session_state.role = None
            st.session_state.agent1_result = None
            st.session_state.agent2_result = None
            st.session_state.interview_results = None
            st.session_state.pop("github_summary", None)
            st.session_state.view = 'home'
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<hr>", unsafe_allow_html=True)
    tab1, tab2 = st.tabs(["📄  Resume Analyzer", "🎙️  Interview Scorer"])

    # ── TAB 1: RESUME ANALYZER ──
    with tab1:
        st.markdown("<span class='label'>Step 1 — Upload Resume</span>", unsafe_allow_html=True)
        resume_file = st.file_uploader("Upload Candidate Resume (PDF or DOCX)", type=["pdf", "docx"])

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("<span class='label'>Step 2 — Job Details</span>", unsafe_allow_html=True)
        job_role = st.text_input("Job Role", placeholder="e.g. Senior ML Engineer", key="emp_job_role")
        job_description = st.text_area(
            label="jd", placeholder="Paste the full job description here...",
            height=160, label_visibility="collapsed"
        )
        st.markdown("<br>", unsafe_allow_html=True)

        if st.button("🔍  Parse Resume", use_container_width=True):
            if not resume_file:
                st.warning("Please upload a resume.")
            elif not job_role or not job_description:
                st.warning("Please enter the job role and description.")
            else:
                with st.spinner("Parsing resume and GitHub profile..."):
                    agent1_result = Agent1().run(resume_file.read(), resume_file.name)
                    st.session_state.agent1_result = agent1_result
                    st.session_state.agent2_result = None
                    st.session_state.pop("github_summary", None)

        # GitHub prompt if not found
        if st.session_state.agent1_result:
            github_found = st.session_state.agent1_result.get("resume", {}).get("github_url", "")
            github_data  = st.session_state.agent1_result.get("github", {})

            if not github_found or not github_data:
                st.markdown("<br>", unsafe_allow_html=True)
                st.warning("No GitHub URL found in resume. Add one manually or skip.")
                col_gh, col_skip = st.columns([3, 1])
                with col_gh:
                    manual_github = st.text_input(
                        "GitHub URL (optional)",
                        placeholder="https://github.com/username",
                        key="manual_github"
                    )
                    # Save to session state immediately
                    if manual_github:
                        st.session_state['pending_github'] = manual_github
                with col_skip:
                    st.markdown("<br>", unsafe_allow_html=True)
                    st.button("Skip GitHub", key="skip_gh")

                col_analyze, _ = st.columns([1, 2])
                with col_analyze:
                    if st.button("📊  Analyze Match", use_container_width=True, key="analyze_match"):
                        
                        # Read directly from the text input's session state key
                        pending_gh = st.session_state.get('manual_github', '').strip()
                        
                        if pending_gh:
                            with st.spinner("Scraping GitHub profile — this may take a few minutes..."):
                                a1 = Agent1()
                                scraped = a1.scrape_github(pending_gh)
                                updated_result = dict(st.session_state.agent1_result)
                                updated_result["github"] = scraped
                                updated_result["resume"] = dict(st.session_state.agent1_result["resume"])
                                updated_result["resume"]["github_url"] = pending_gh
                                st.session_state.agent1_result = updated_result
                                st.session_state['pending_github'] = ''  # clear after use

                        with st.spinner("Evaluating candidate match..."):
                            agent2_result = evaluate(
                                candidate_json=json.dumps(slim_agent1_result(st.session_state.agent1_result)),
                                job_role=st.session_state.get('saved_job_role', job_role),
                                job_description=st.session_state.get('saved_job_description', job_description),
                            )
                            st.session_state.agent2_result = agent2_result
            else:
                st.markdown("<br>", unsafe_allow_html=True)
                st.success(f"GitHub found: {github_found}")
                if st.button("📊  Analyze Match", use_container_width=True, key="analyze_match_auto"):
                    with st.spinner("Evaluating candidate match..."):
                        agent2_result = evaluate(
                            candidate_json=json.dumps(slim_agent1_result(st.session_state.agent1_result)),
                            job_role=job_role,
                            job_description=job_description,
                        )
                        st.session_state.agent2_result = agent2_result

        # Show results
        if st.session_state.agent2_result:
            st.markdown("<br>", unsafe_allow_html=True)
            render_agent2_results(st.session_state.agent2_result)

            if st.session_state.agent1_result:
                with st.expander("📄 Raw Resume Data"):
                    st.json(st.session_state.agent1_result.get("resume", {}))
                github = st.session_state.agent1_result.get("github", {})
                if github:
                    # ── Generate GitHub summary on demand ──
                    if "github_summary" not in st.session_state:
                        with st.spinner("Summarizing GitHub profile..."):
                            from agent2 import summarize_github
                            saved_role = st.session_state.get("saved_job_role", job_role)
                            saved_jd   = st.session_state.get("saved_job_description", job_description)
                            st.session_state.github_summary = summarize_github(
                                github, saved_role, saved_jd
                            )

                    gs = st.session_state.github_summary
                    cp = github.get("candidate_profile", {}).get("github", {})

                    with st.expander("🐙 GitHub Profile"):
                        st.markdown(f"""
                        <div style='background:#0e0e20;border:1px solid rgba(255,255,255,0.06);border-radius:14px;padding:1.5rem;'>
                            <div style='font-size:10px;letter-spacing:3px;color:rgba(255,255,255,0.3);text-transform:uppercase;margin-bottom:12px;'>Developer Profile</div>
                            <p style='color:rgba(255,255,255,0.75);font-size:14px;line-height:1.8;margin:0 0 1rem 0;'>{gs.get("profile_summary","")}</p>
                            <p style='color:rgba(255,255,255,0.55);font-size:13px;line-height:1.7;margin:0;'>{gs.get("skills_narrative","")}</p>
                            <div style='display:flex;gap:2rem;margin-top:1.2rem;padding-top:1rem;border-top:1px solid rgba(255,255,255,0.06);'>
                                <div><div style='font-size:10px;color:rgba(255,255,255,0.3);'>Repos</div><div style='font-size:18px;font-weight:700;color:white;'>{cp.get("public_repos",0)}</div></div>
                                <div><div style='font-size:10px;color:rgba(255,255,255,0.3);'>Followers</div><div style='font-size:18px;font-weight:700;color:white;'>{cp.get("followers",0)}</div></div>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

                    with st.expander("🛠️ Skills Summary"):
                        skills_data = github.get("skills_summary", {})
                        langs = skills_data.get("all_languages", [])
                        st.markdown(f"""
                        <div style='background:#0e0e20;border:1px solid rgba(255,255,255,0.06);border-radius:14px;padding:1.5rem;'>
                            <div style='font-size:10px;letter-spacing:3px;color:rgba(255,255,255,0.3);text-transform:uppercase;margin-bottom:12px;'>Technical Skills</div>
                            <p style='color:rgba(255,255,255,0.75);font-size:14px;line-height:1.8;margin:0 0 1rem 0;'>{gs.get("assessment_narrative","")}</p>
                            <div style='font-size:11px;color:rgba(255,255,255,0.35);margin-bottom:8px;text-transform:uppercase;letter-spacing:2px;'>Languages</div>
                            <div style='margin-bottom:1rem;'>{"".join([f"<span style='background:rgba(124,111,255,0.15);border:1px solid rgba(124,111,255,0.3);color:#a78bfa;padding:3px 10px;border-radius:20px;font-size:11px;font-weight:600;margin:3px;display:inline-block;'>{l}</span>" for l in langs])}</div>
                        </div>
                        """, unsafe_allow_html=True)

                    with st.expander("📁 Matched Repositories"):
                        matched = gs.get("matched_repos", [])
                        unmatched = gs.get("unmatched_count", 0)
                        match_note = gs.get("match_note", "")
                        if not matched:
                            st.info("No repositories matched the job description.")
                        else:
                            st.markdown(f"<p style='color:rgba(255,255,255,0.4);font-size:12px;margin-bottom:1rem;'>{match_note} ({unmatched} repos excluded)</p>", unsafe_allow_html=True)
                            for r in matched:
                                qcolor = {"Advanced":"#22c55e","Expert":"#00e676","Intermediate":"#f59e0b","Beginner":"#ef4444"}.get(r.get("quality_rating",""), "#94a3b8")
                                lang_pills = "".join([f"<span style='background:rgba(79,142,247,0.15);border:1px solid rgba(79,142,247,0.3);color:#4f8ef7;padding:2px 8px;border-radius:12px;font-size:10px;margin:2px;display:inline-block;'>{l}</span>" for l in r.get("languages",[])])
                                skill_pills = "".join([f"<span style='background:rgba(167,139,250,0.12);border:1px solid rgba(167,139,250,0.25);color:#a78bfa;padding:2px 8px;border-radius:12px;font-size:10px;margin:2px;display:inline-block;'>{s}</span>" for s in r.get("key_skills",[])])
                                st.markdown(f"""
                                <div style='background:#0e0e20;border:1px solid rgba(255,255,255,0.06);border-radius:12px;padding:1.25rem;margin-bottom:0.75rem;'>
                                    <div style='display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:8px;'>
                                        <div style='font-size:14px;font-weight:700;color:white;'>{r.get("name","")}</div>
                                        <div style='display:flex;gap:8px;align-items:center;'>
                                            {"<span style='font-size:10px;font-weight:700;color:"+qcolor+";background:"+qcolor+"22;padding:2px 8px;border-radius:10px;'>"+r.get("quality_rating","")+"</span>" if r.get("quality_rating") else ""}
                                            <span style='font-size:11px;color:rgba(255,255,255,0.3);'>⭐ {r.get("stars",0)}  📝 {r.get("commits",0)} commits</span>
                                        </div>
                                    </div>
                                    <p style='color:rgba(255,255,255,0.5);font-size:12px;line-height:1.6;margin:0 0 10px 0;font-style:italic;'>{r.get("relevance_reason","")}</p>
                                    <div>{lang_pills}</div>
                                    <div style='margin-top:6px;'>{skill_pills}</div>
                                </div>
                                """, unsafe_allow_html=True)

                    with st.expander("🏆 Developer Assessment"):
                        assessment = github.get("final_assessment", {})
                        level       = assessment.get("developer_level", "")
                        strengths   = assessment.get("strengths", [])
                        weaknesses  = assessment.get("weaknesses", [])
                        confidence  = assessment.get("confidence_score", 0)
                        level_color = {"Expert":"#00e676","Advanced":"#22c55e","Intermediate":"#f59e0b","Beginner":"#ef4444"}.get(level, "#94a3b8")
                        st.markdown(f"""
                        <div style='background:#0e0e20;border:1px solid rgba(255,255,255,0.06);border-radius:14px;padding:1.5rem;'>
                            <div style='display:flex;align-items:center;gap:1rem;margin-bottom:1rem;'>
                                <span style='font-size:22px;font-weight:900;color:{level_color};font-family:Arial Black;'>{level}</span>
                                <span style='font-size:12px;color:rgba(255,255,255,0.3);'>Confidence: {int(float(confidence)*100) if confidence else 0}%</span>
                            </div>
                            <p style='color:rgba(255,255,255,0.65);font-size:13px;line-height:1.7;margin:0 0 1rem 0;'>{gs.get("assessment_narrative","")}</p>
                            <div style='display:grid;grid-template-columns:1fr 1fr;gap:1rem;'>
                                <div>
                                    <div style='font-size:10px;color:#22c55e;letter-spacing:2px;text-transform:uppercase;margin-bottom:8px;'>Strengths</div>
                                    {"".join([f"<div style='font-size:12px;color:rgba(255,255,255,0.6);margin-bottom:5px;'>✓ {s}</div>" for s in strengths])}
                                </div>
                                <div>
                                    <div style='font-size:10px;color:#ef4444;letter-spacing:2px;text-transform:uppercase;margin-bottom:8px;'>Areas to Improve</div>
                                    {"".join([f"<div style='font-size:12px;color:rgba(255,255,255,0.6);margin-bottom:5px;'>→ {w}</div>" for w in weaknesses])}
                                </div>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                else:
                    st.info("No GitHub data available.")

    # ── TAB 2: INTERVIEW SCORER ──
    with tab2:
        st.markdown("<span class='label'>Role being interviewed for</span>", unsafe_allow_html=True)
        candidate_role = st.text_input(
            label="role", placeholder="e.g. Senior ML Engineer",
            label_visibility="collapsed"
        )
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("<span class='label'>Interview Recording</span>", unsafe_allow_html=True)

        col_upload, col_path = st.columns([1, 1])
        with col_upload:
            interview_file = st.file_uploader("Upload (under 100MB)", type=["mp4", "mov", "webm"])
        with col_path:
            local_path = st.text_input(
                "Or paste local file path (large files)",
                placeholder=r"C:\Users\...\interview.mov"
            )

        st.markdown("<br>", unsafe_allow_html=True)

        if st.button("🎯  Score Interview", use_container_width=True):
            if not candidate_role:
                st.warning("Please enter the role.")
            elif not interview_file and not local_path:
                st.warning("Please upload a file or enter a local file path.")
            else:
                with st.spinner("Analyzing interview — this may take a few minutes for large files..."):
                    try:
                        if local_path:
                            if not os.path.exists(local_path):
                                st.error(f"File not found: {local_path}")
                                st.stop()
                            # Pass path directly — no memory load for large files
                            results = run_interview_agent(
                                role=candidate_role,
                                local_path=local_path
                            )
                        else:
                            file_ext   = "." + interview_file.name.split(".")[-1]
                            video_bytes = interview_file.read()
                            results = run_interview_agent(
                                video_bytes=video_bytes,
                                role=candidate_role,
                                file_extension=file_ext
                            )
                        st.session_state.interview_results = results
                    except Exception as e:
                        st.error(f"Error: {str(e)}")
                        st.stop()

        if st.session_state.interview_results:
            results = st.session_state.interview_results
            st.markdown("<br>", unsafe_allow_html=True)

            rec = results.get("RECOMMENDATION", "CONSIDER")
            rec_color = {"HIRE": "#22c55e", "CONSIDER": "#f59e0b", "REJECT": "#ef4444"}.get(rec, "#888")

            st.markdown(f"""
                <div style='display:inline-block;padding:6px 24px;background:{rec_color}22;
                border:1px solid {rec_color};border-radius:20px;margin-bottom:1.5rem;'>
                    <span style='color:{rec_color};font-weight:700;font-size:12px;letter-spacing:3px;'>{rec}</span>
                </div>
            """, unsafe_allow_html=True)

            overall = results.get("OVERALL_SCORE", 0)
            score_color = "#22c55e" if overall >= 70 else "#f59e0b" if overall >= 40 else "#ef4444"

            st.markdown(f"""
                <div style='margin-bottom:1.5rem;'>
                    <div style='font-size:10px;letter-spacing:3px;color:rgba(255,255,255,0.3);
                    text-transform:uppercase;margin-bottom:8px;'>Overall Score</div>
                    <div style='font-size:72px;font-weight:900;color:{score_color};
                    font-family:Arial Black;line-height:1;'>{overall}
                        <span style='font-size:24px;color:rgba(255,255,255,0.25);'>/100</span>
                    </div>
                </div>
            """, unsafe_allow_html=True)

            st.markdown(f"""
                <div style='background:#13132a;border:1px solid rgba(255,255,255,0.06);
                border-radius:12px;padding:1.25rem 1.5rem;margin-bottom:2rem;'>
                    <div style='font-size:10px;letter-spacing:3px;color:rgba(255,255,255,0.3);
                    text-transform:uppercase;margin-bottom:8px;'>Summary</div>
                    <p style='color:rgba(255,255,255,0.7);font-size:14px;line-height:1.8;margin:0;'>
                        {results.get("SUMMARY","")}</p>
                </div>
            """, unsafe_allow_html=True)

            interview_categories = [
                ("Technicality",    "TECHNICALITY",    "TECHNICALITY_FEEDBACK"),
                ("Problem Solving", "PROBLEM_SOLVING",  "PROBLEM_SOLVING_FEEDBACK"),
                ("Communication",   "COMMUNICATION",    "COMMUNICATION_FEEDBACK"),
                ("Personality",     "PERSONALITY",      "PERSONALITY_FEEDBACK"),
                ("Confidence",      "CONFIDENCE",       "CONFIDENCE_FEEDBACK"),
            ]

            st.markdown("<span class='label'>Score Breakdown</span>", unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)

            left_cards = ""
            right_cards = ""
            for i, (label, score_key, feedback_key) in enumerate(interview_categories):
                score = results.get(score_key, 0)
                feedback = results.get(feedback_key, "No feedback available.")
                bar_color = "#22c55e" if score >= 70 else "#f59e0b" if score >= 40 else "#ef4444"
                card = f"""
                <div style='background:#0e0e20;border:1px solid rgba(255,255,255,0.06);
                border-radius:14px;padding:1.5rem;margin-bottom:1rem;'>
                    <div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;'>
                        <span style='font-size:11px;font-weight:700;color:rgba(255,255,255,0.4);
                        text-transform:uppercase;letter-spacing:2px;'>{label}</span>
                        <span style='font-size:28px;font-weight:900;color:{bar_color};
                        font-family:Arial Black;line-height:1;'>{score}</span>
                    </div>
                    <div style='background:rgba(255,255,255,0.06);border-radius:4px;height:3px;margin-bottom:16px;'>
                        <div style='background:{bar_color};width:{score}%;height:3px;border-radius:4px;
                        box-shadow:0 0 10px {bar_color}88;'></div>
                    </div>
                    <p style='font-size:13px;color:rgba(255,255,255,0.6);margin:0;line-height:1.8;'>{feedback}</p>
                </div>"""
                if i % 2 == 0: left_cards += card
                else: right_cards += card

            col1, col2 = st.columns(2)
            with col1: st.markdown(left_cards, unsafe_allow_html=True)
            with col2: st.markdown(right_cards, unsafe_allow_html=True)

            with st.expander("📄 View Full Transcript"):
                transcript = results.get("TRANSCRIPT", "")
                if transcript:
                    formatted = ""
                    for line in transcript.split("\n"):
                        line = line.strip()
                        if not line: continue
                        if line.startswith("Speaker 1"):
                            formatted += f"<div style='margin-bottom:12px;'><span style='font-size:10px;letter-spacing:2px;text-transform:uppercase;color:#7c6fff;font-weight:700;'>Interviewer</span><p style='color:rgba(255,255,255,0.7);font-size:13px;line-height:1.7;margin:4px 0 0 0;'>{line.partition(':')[2].strip()}</p></div>"
                        elif line.startswith("Speaker 2"):
                            formatted += f"<div style='margin-bottom:12px;padding-left:1rem;border-left:2px solid rgba(255,255,255,0.08);'><span style='font-size:10px;letter-spacing:2px;text-transform:uppercase;color:rgba(255,255,255,0.3);font-weight:700;'>Candidate</span><p style='color:rgba(255,255,255,0.55);font-size:13px;line-height:1.7;margin:4px 0 0 0;'>{line.partition(':')[2].strip()}</p></div>"
                        else:
                            formatted += f"<p style='color:rgba(255,255,255,0.4);font-size:13px;'>{line}</p>"
                    st.markdown(f"<div style='background:#13132a;border-radius:12px;padding:1.5rem;max-height:400px;overflow-y:auto;'>{formatted}</div>", unsafe_allow_html=True)
                else:
                    st.markdown("<p style='color:rgba(255,255,255,0.4);'>Transcript not available.</p>", unsafe_allow_html=True)


# ─────────────────────────────────────────
# CANDIDATE PORTAL
# ─────────────────────────────────────────
elif st.session_state.view == 'candidate':

    if not st.session_state.user:
        st.session_state.view = 'candidate_auth'; st.rerun()

    from agent1 import Agent1
    from agent2 import evaluate

    st.markdown(DARK_CSS, unsafe_allow_html=True)
    user = st.session_state.user

    col_logo, col_back = st.columns([6, 1])
    with col_logo:
        st.markdown(f"<div class='nav-logo'>hire<span>.</span>ai<div class='nav-tag'>{user.get('full_name','')}</div></div>", unsafe_allow_html=True)
    with col_back:
        st.markdown("<div class='ghost-btn'>", unsafe_allow_html=True)
        if st.button("Sign Out"):
            st.session_state.user = None
            st.session_state.role = None
            st.session_state.agent1_result = None
            st.session_state.agent2_result = None
            st.session_state.pop("github_summary", None)
            st.session_state.view = 'home'
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<hr>", unsafe_allow_html=True)

    st.markdown("<span class='label'>Step 1 — Upload Your Resume</span>", unsafe_allow_html=True)
    resume_file = st.file_uploader("Upload Your Resume (PDF or DOCX)", type=["pdf", "docx"])

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("<span class='label'>Step 2 — Target Role</span>", unsafe_allow_html=True)
    job_role = st.text_input("Job Role you're applying for", placeholder="e.g. ML Engineer, Frontend Developer", key="can_job_role")
    job_description = st.text_area(
        label="jd_can", placeholder="Paste the job description you're targeting...",
        height=160, label_visibility="collapsed"
    )
    st.markdown("<br>", unsafe_allow_html=True)

    if st.button("✨  Analyze My Profile", use_container_width=True):
        if not resume_file:
            st.warning("Please upload your resume.")
        elif not job_role or not job_description:
            st.warning("Please enter the job role and description.")
        else:
            with st.spinner("Parsing your resume and GitHub profile..."):
                agent1_result = Agent1().run(resume_file.read(), resume_file.name)
                st.session_state.agent1_result = agent1_result
                st.session_state.agent2_result = None

            # Check if GitHub was found
            github_found = agent1_result.get("resume", {}).get("github_url", "")
            github_data  = agent1_result.get("github", {})

            if github_found and github_data:
                with st.spinner("Analyzing your match..."):
                    agent2_result = evaluate(
                        candidate_json=json.dumps(slim_agent1_result(agent1_result)),
                        job_role=job_role,
                        job_description=job_description,
                    )
                    st.session_state.agent2_result = agent2_result

    # GitHub prompt for candidate if not found
    if st.session_state.agent1_result and not st.session_state.agent2_result:
        github_found = st.session_state.agent1_result.get("resume", {}).get("github_url", "")
        github_data  = st.session_state.agent1_result.get("github", {})

        if not github_found or not github_data:
            st.markdown("<br>", unsafe_allow_html=True)
            st.warning("No GitHub URL found in your resume. Add one or skip.")
            col_gh, col_skip = st.columns([3, 1])
            with col_gh:
                manual_github = st.text_input(
                    "GitHub URL (optional)",
                    placeholder="https://github.com/username",
                    key="manual_github"
                )
                # Save immediately on every render
                st.session_state['pending_github'] = st.session_state.get('manual_github', '')
            with col_skip:
                st.markdown("<br>", unsafe_allow_html=True)
                st.button("Skip", key="can_skip_gh")

            if st.button("✨  Analyze Match", use_container_width=True, key="can_analyze_match"):
                if manual_github and manual_github.strip():
                    with st.spinner("Scraping your GitHub..."):
                        a1 = Agent1()
                        github_data = a1.scrape_github(manual_github.strip())
                        st.session_state.agent1_result["github"] = github_data
                        st.session_state.agent1_result["resume"]["github_url"] = manual_github.strip()

                with st.spinner("Analyzing your match..."):
                    agent2_result = evaluate(
                        candidate_json=json.dumps(slim_agent1_result(st.session_state.agent1_result)),
                        job_role=job_role,
                        job_description=job_description,
                    )
                    st.session_state.agent2_result = agent2_result

    if st.session_state.agent2_result:
        st.markdown("<br>", unsafe_allow_html=True)
        render_agent2_results(st.session_state.agent2_result)

        if st.session_state.agent1_result:
            with st.expander("📄 Your Parsed Resume"):
                st.json(st.session_state.agent1_result.get("resume", {}))
            github = st.session_state.agent1_result.get("github", {})
            if github:
                # ── Generate GitHub summary on demand ──
                if "github_summary" not in st.session_state:
                    with st.spinner("Summarizing your GitHub profile..."):
                        from agent2 import summarize_github
                        st.session_state.github_summary = summarize_github(
                            github, job_role, job_description
                        )

                gs = st.session_state.github_summary
                cp = github.get("candidate_profile", {}).get("github", {})

                with st.expander("🐙 Your GitHub Profile"):
                    st.markdown(f"""
                    <div style='background:#0e0e20;border:1px solid rgba(255,255,255,0.06);border-radius:14px;padding:1.5rem;'>
                        <div style='font-size:10px;letter-spacing:3px;color:rgba(255,255,255,0.3);text-transform:uppercase;margin-bottom:12px;'>Developer Profile</div>
                        <p style='color:rgba(255,255,255,0.75);font-size:14px;line-height:1.8;margin:0 0 1rem 0;'>{gs.get("profile_summary","")}</p>
                        <p style='color:rgba(255,255,255,0.55);font-size:13px;line-height:1.7;margin:0;'>{gs.get("skills_narrative","")}</p>
                        <div style='display:flex;gap:2rem;margin-top:1.2rem;padding-top:1rem;border-top:1px solid rgba(255,255,255,0.06);'>
                            <div><div style='font-size:10px;color:rgba(255,255,255,0.3);'>Repos</div><div style='font-size:18px;font-weight:700;color:white;'>{cp.get("public_repos",0)}</div></div>
                            <div><div style='font-size:10px;color:rgba(255,255,255,0.3);'>Followers</div><div style='font-size:18px;font-weight:700;color:white;'>{cp.get("followers",0)}</div></div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                with st.expander("🛠️ Your Skills Summary"):
                    skills_data = github.get("skills_summary", {})
                    langs = skills_data.get("all_languages", [])
                    st.markdown(f"""
                    <div style='background:#0e0e20;border:1px solid rgba(255,255,255,0.06);border-radius:14px;padding:1.5rem;'>
                        <div style='font-size:10px;letter-spacing:3px;color:rgba(255,255,255,0.3);text-transform:uppercase;margin-bottom:12px;'>Technical Skills</div>
                        <p style='color:rgba(255,255,255,0.75);font-size:14px;line-height:1.8;margin:0 0 1rem 0;'>{gs.get("assessment_narrative","")}</p>
                        <div style='font-size:11px;color:rgba(255,255,255,0.35);margin-bottom:8px;text-transform:uppercase;letter-spacing:2px;'>Languages</div>
                        <div style='margin-bottom:1rem;'>{"".join([f"<span style='background:rgba(124,111,255,0.15);border:1px solid rgba(124,111,255,0.3);color:#a78bfa;padding:3px 10px;border-radius:20px;font-size:11px;font-weight:600;margin:3px;display:inline-block;'>{l}</span>" for l in langs])}</div>
                    </div>
                    """, unsafe_allow_html=True)

                with st.expander("🏆 Developer Assessment"):
                    assessment = github.get("final_assessment", {})
                    level      = assessment.get("developer_level", "")
                    strengths  = assessment.get("strengths", [])
                    weaknesses = assessment.get("weaknesses", [])
                    confidence = assessment.get("confidence_score", 0)
                    level_color = {"Expert":"#00e676","Advanced":"#22c55e","Intermediate":"#f59e0b","Beginner":"#ef4444"}.get(level, "#94a3b8")
                    st.markdown(f"""
                    <div style='background:#0e0e20;border:1px solid rgba(255,255,255,0.06);border-radius:14px;padding:1.5rem;'>
                        <div style='display:flex;align-items:center;gap:1rem;margin-bottom:1rem;'>
                            <span style='font-size:22px;font-weight:900;color:{level_color};font-family:Arial Black;'>{level}</span>
                            <span style='font-size:12px;color:rgba(255,255,255,0.3);'>Confidence: {int(float(confidence)*100) if confidence else 0}%</span>
                        </div>
                        <p style='color:rgba(255,255,255,0.65);font-size:13px;line-height:1.7;margin:0 0 1rem 0;'>{gs.get("assessment_narrative","")}</p>
                        <div style='display:grid;grid-template-columns:1fr 1fr;gap:1rem;'>
                            <div>
                                <div style='font-size:10px;color:#22c55e;letter-spacing:2px;text-transform:uppercase;margin-bottom:8px;'>Strengths</div>
                                {"".join([f"<div style='font-size:12px;color:rgba(255,255,255,0.6);margin-bottom:5px;'>✓ {s}</div>" for s in strengths])}
                            </div>
                            <div>
                                <div style='font-size:10px;color:#ef4444;letter-spacing:2px;text-transform:uppercase;margin-bottom:8px;'>Areas to Improve</div>
                                {"".join([f"<div style='font-size:12px;color:rgba(255,255,255,0.6);margin-bottom:5px;'>→ {w}</div>" for w in weaknesses])}
                            </div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)