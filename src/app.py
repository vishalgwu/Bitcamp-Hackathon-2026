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
    return client["hiring_platform"]

db = get_db()
employers_col  = db["employers"]
candidates_col = db["candidates"]
profiles_col   = db["candidate_profiles"]  # cache of agent1 results

# ─────────────────────────────────────────
# PROFILE CACHE HELPERS
# ─────────────────────────────────────────
def get_cached_profile(email: str):
    """Look up a previously parsed candidate profile by email."""
    if not email:
        return None
    doc = profiles_col.find_one({"email": email.lower().strip()})
    if doc:
        doc.pop("_id", None)
        return doc
    return None

def save_profile_cache(agent1_result: dict):
    """Save agent1 result to MongoDB keyed by candidate email."""
    email = agent1_result.get("resume", {}).get("email", "")
    if not email:
        return
    email = email.lower().strip()
    profiles_col.update_one(
        {"email": email},
        {"$set": {
            **agent1_result,
            "email":      email,
            "cached_at":  datetime.now(timezone.utc)
        }},
        upsert=True
    )
    print(f"  ✅ Profile cached for {email}")

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
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:ital,wght@0,300;0,400;0,500;0,600;0,700;1,300&family=DM+Serif+Display:ital@0;1&family=JetBrains+Mono:wght@400;500&display=swap');

:root {
    --bg:        #050508;
    --surface:   #0c0c12;
    --surface2:  #111118;
    --surface3:  #17171f;
    --border:    rgba(255,255,255,0.07);
    --border2:   rgba(255,255,255,0.12);
    --accent:    #e8c547;
    --accent2:   #f5d76e;
    --accentdim: rgba(232,197,71,0.12);
    --accentglow:rgba(232,197,71,0.25);
    --teal:      #3ecfb2;
    --tealdim:   rgba(62,207,178,0.12);
    --red:       #ff5f57;
    --reddim:    rgba(255,95,87,0.12);
    --white:     #f0f0f5;
    --muted:     rgba(240,240,245,0.45);
    --faint:     rgba(240,240,245,0.2);
    --serif:     'DM Serif Display', Georgia, serif;
    --sans:      'DM Sans', system-ui, sans-serif;
    --mono:      'JetBrains Mono', monospace;
}

#MainMenu, header, footer { visibility: hidden; }

.stApp,
[data-testid="stAppViewContainer"],
[data-testid="stMain"] {
    background: var(--bg) !important;
    font-family: var(--sans) !important;
}

.block-container {
    padding: 2.5rem 3.5rem !important;
    max-width: 100% !important;
}

* { color: var(--white); font-family: var(--sans); }

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 4px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 2px; }

/* ── Divider ── */
hr {
    border: none !important;
    border-top: 1px solid var(--border) !important;
    margin: 0 0 2.5rem 0 !important;
}

/* ── Nav Logo ── */
.nav-logo {
    font-family: var(--serif) !important;
    font-size: 28px;
    font-weight: 400;
    color: var(--white);
    letter-spacing: -0.5px;
    line-height: 1;
    font-style: italic;
}
.nav-logo span { color: var(--accent); font-style: normal; }
.nav-tag {
    font-family: var(--sans);
    font-size: 10px;
    color: var(--faint);
    font-weight: 500;
    letter-spacing: 3px;
    text-transform: uppercase;
    margin-top: 5px;
}

/* ── Section label ── */
.label {
    font-size: 10px;
    letter-spacing: 3.5px;
    text-transform: uppercase;
    color: var(--muted) !important;
    font-weight: 600;
    margin-bottom: 10px;
    display: block;
    font-family: var(--sans);
}

/* ── Text inputs ── */
.stTextInput input,
.stTextArea textarea {
    background: var(--surface2) !important;
    border: 1px solid var(--border) !important;
    border-radius: 8px !important;
    color: var(--white) !important;
    font-size: 14px !important;
    font-family: var(--sans) !important;
    transition: border-color 0.2s ease, box-shadow 0.2s ease !important;
}
.stTextInput input:focus,
.stTextArea textarea:focus {
    border: 1px solid var(--accent) !important;
    box-shadow: 0 0 0 3px var(--accentdim) !important;
    outline: none !important;
}
.stTextInput input::placeholder,
.stTextArea textarea::placeholder {
    color: var(--faint) !important;
}

/* ── Widget labels ── */
label[data-testid="stWidgetLabel"] p {
    color: var(--muted) !important;
    font-size: 11px !important;
    font-weight: 600 !important;
    letter-spacing: 2px !important;
    text-transform: uppercase !important;
    font-family: var(--sans) !important;
}

/* ── File uploader ── */
[data-testid="stFileUploader"] {
    background: var(--surface2) !important;
    border: 1px dashed rgba(232,197,71,0.2) !important;
    border-radius: 10px !important;
    padding: 1.25rem !important;
    transition: border-color 0.2s ease !important;
}
[data-testid="stFileUploader"]:hover {
    border-color: rgba(232,197,71,0.45) !important;
}

/* ── Primary button ── */
.stButton > button {
    background: var(--accent) !important;
    color: #0a0a0a !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 700 !important;
    font-size: 13px !important;
    letter-spacing: 1px !important;
    text-transform: uppercase !important;
    padding: 14px 28px !important;
    width: 100% !important;
    transition: all 0.2s ease !important;
    box-shadow: 0 0 0 0 var(--accentglow) !important;
    font-family: var(--sans) !important;
}
.stButton > button:hover {
    background: var(--accent2) !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 6px 24px var(--accentglow) !important;
}
.stButton > button:active {
    transform: translateY(0) !important;
}

/* ── Ghost button ── */
.ghost-btn > button {
    background: transparent !important;
    border: 1px solid var(--border2) !important;
    color: var(--muted) !important;
    width: auto !important;
    box-shadow: none !important;
    padding: 8px 18px !important;
    text-transform: none !important;
    letter-spacing: 0 !important;
    font-weight: 500 !important;
    border-radius: 7px !important;
}
.ghost-btn > button:hover {
    background: var(--surface3) !important;
    color: var(--white) !important;
    transform: none !important;
    box-shadow: none !important;
    border-color: var(--border2) !important;
}

/* ── Link button ── */
.link-btn > button {
    background: transparent !important;
    border: 1px solid rgba(232,197,71,0.25) !important;
    color: var(--accent) !important;
    box-shadow: none !important;
    font-weight: 600 !important;
    text-transform: none !important;
    letter-spacing: 0 !important;
    border-radius: 7px !important;
}
.link-btn > button:hover {
    background: var(--accentdim) !important;
    transform: none !important;
    box-shadow: none !important;
    border-color: rgba(232,197,71,0.45) !important;
}

/* ── Tabs ── */
[data-testid="stTabs"] button {
    color: var(--faint) !important;
    font-size: 13px !important;
    font-weight: 600 !important;
    padding: 12px 28px !important;
    border-radius: 0 !important;
    border-bottom: 2px solid transparent !important;
    background: transparent !important;
    letter-spacing: 0.5px !important;
    text-transform: uppercase !important;
    font-family: var(--sans) !important;
    transition: color 0.2s ease !important;
}
[data-testid="stTabs"] button[aria-selected="true"] {
    color: var(--accent) !important;
    border-bottom: 2px solid var(--accent) !important;
}
[data-testid="stTabs"] button:hover {
    color: var(--white) !important;
}
[data-testid="stTabsContent"] { padding-top: 2.5rem !important; }

/* ── Expander ── */
[data-testid="stExpander"] {
    background: var(--surface2) !important;
    border: 1px solid var(--border) !important;
    border-radius: 10px !important;
    margin-bottom: 0.75rem !important;
    overflow: hidden !important;
}
[data-testid="stExpander"] summary {
    padding: 1rem 1.25rem !important;
    font-size: 13px !important;
    font-weight: 600 !important;
    color: var(--muted) !important;
    letter-spacing: 0.5px !important;
}
[data-testid="stExpander"] summary:hover { color: var(--white) !important; }
[data-testid="stExpander"] > div > div {
    padding: 0 1.25rem 1.25rem !important;
}

/* ── Auth card ── */
.auth-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 3rem 2.5rem;
    position: relative;
    overflow: hidden;
}
.auth-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 1px;
    background: linear-gradient(90deg, transparent, var(--accent), transparent);
    opacity: 0.5;
}
.auth-title {
    font-family: var(--serif) !important;
    font-size: 34px;
    font-weight: 400;
    font-style: italic;
    color: var(--white) !important;
    letter-spacing: -0.5px;
    margin-bottom: 6px;
    line-height: 1.1;
}
.auth-sub {
    font-size: 14px;
    color: var(--muted) !important;
    margin-bottom: 2.5rem;
    line-height: 1.6;
    font-weight: 300;
}
.divider-text {
    text-align: center;
    font-size: 11px;
    color: var(--faint) !important;
    margin: 1.25rem 0;
    letter-spacing: 2px;
    text-transform: uppercase;
}

/* ── Alerts / warnings ── */
[data-testid="stAlert"] {
    border-radius: 8px !important;
    border-left: 3px solid var(--accent) !important;
    background: var(--accentdim) !important;
}

/* ── Spinner ── */
[data-testid="stSpinner"] { color: var(--accent) !important; }

/* ── Selectbox ── */
.stSelectbox > div > div {
    background: var(--surface2) !important;
    border: 1px solid var(--border) !important;
    border-radius: 8px !important;
    color: var(--white) !important;
}
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
        <div style="background:#0c0c12;border:1px solid rgba(255,255,255,0.07);border-radius:14px;padding:2rem;display:flex;flex-direction:column;align-items:center;justify-content:center;position:relative;overflow:hidden;">
            <div style="position:absolute;top:0;left:0;right:0;height:1px;background:linear-gradient(90deg,transparent,{score_color},transparent);opacity:0.5;"></div>
            <div style="font-size:9px;letter-spacing:3.5px;color:rgba(240,240,245,0.35);text-transform:uppercase;margin-bottom:1.25rem;font-weight:600;">Match Score</div>
            <svg width="160" height="160" viewBox="0 0 160 160">
                <circle cx="80" cy="80" r="65" fill="none" stroke="rgba(255,255,255,0.05)" stroke-width="10"/>
                <circle cx="80" cy="80" r="65" fill="none" stroke="{score_color}" stroke-width="10"
                    stroke-dasharray="{dash:.1f} {circ:.1f}"
                    stroke-dashoffset="{offset:.1f}"
                    stroke-linecap="round"
                    style="filter:drop-shadow(0 0 10px {score_color});transition:stroke-dasharray 1s ease;"/>
                <text x="80" y="72" text-anchor="middle" fill="white" font-size="36" font-weight="700" font-family="DM Sans,sans-serif">{score}</text>
                <text x="80" y="92" text-anchor="middle" fill="rgba(240,240,245,0.35)" font-size="11" font-family="DM Sans,sans-serif">out of 100</text>
            </svg>
            <div style="display:inline-block;padding:5px 16px;background:{verdict_color}18;border:1px solid {verdict_color}55;border-radius:6px;margin-top:1.25rem;">
                <span style="color:{verdict_color};font-weight:700;font-size:10px;letter-spacing:2.5px;">{verdict_label}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col_radar:
        st.markdown(f"""
        <div style="background:#0c0c12;border:1px solid rgba(255,255,255,0.07);border-radius:14px;padding:2rem;">
            <div style="font-size:9px;letter-spacing:3.5px;color:rgba(240,240,245,0.35);text-transform:uppercase;margin-bottom:1.25rem;font-weight:600;">Skill Radar</div>
            <svg width="100%" viewBox="0 0 400 400" style="max-height:280px;">
                {grid_rings}{axis_lines}
                <polygon points="{radar_points.strip()}" fill="rgba(232,197,71,0.1)" stroke="#e8c547" stroke-width="1.5"/>
                {dot_circles}{radar_labels_html}
            </svg>
        </div>
        """, unsafe_allow_html=True)

    # ── Summary ──
    st.markdown(f"""
    <div style="background:#0c0c12;border:1px solid rgba(255,255,255,0.07);border-radius:12px;padding:1.75rem;margin-top:1rem;margin-bottom:1.5rem;position:relative;overflow:hidden;">
        <div style="position:absolute;left:0;top:0;bottom:0;width:3px;background:linear-gradient(180deg,#e8c547,rgba(232,197,71,0.2));border-radius:2px 0 0 2px;"></div>
        <div style="font-size:9px;letter-spacing:3.5px;color:rgba(240,240,245,0.35);text-transform:uppercase;margin-bottom:10px;font-weight:600;">Match Summary</div>
        <p style="color:rgba(240,240,245,0.75);font-size:14px;line-height:1.9;margin:0;font-weight:300;">{summary}</p>
    </div>
    """, unsafe_allow_html=True)

    # ── Bar chart ──
    st.markdown("""
    <div style="background:#0c0c12;border:1px solid rgba(255,255,255,0.07);border-radius:12px;padding:1.75rem;margin-bottom:1.5rem;">
        <div style="font-size:9px;letter-spacing:3.5px;color:rgba(240,240,245,0.35);text-transform:uppercase;margin-bottom:1.5rem;font-weight:600;">Category Breakdown</div>
    """, unsafe_allow_html=True)

    for c in categories:
        bc = "#3ecfb2" if c["score"] >= 75 else "#e8c547" if c["score"] >= 45 else "#ff5f57"
        st.markdown(f"""
        <div style="margin-bottom:18px;">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
                <span style="font-size:12px;color:rgba(240,240,245,0.55);font-weight:500;letter-spacing:0.5px;">{c['name']}</span>
                <span style="font-size:13px;font-weight:700;color:{bc};font-variant-numeric:tabular-nums;">{c['score']}</span>
            </div>
            <div style="background:rgba(255,255,255,0.04);border-radius:3px;height:4px;">
                <div style="background:{bc};width:{c['score']}%;height:4px;border-radius:3px;box-shadow:0 0 8px {bc}66;transition:width 0.8s ease;"></div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

    # ── Strengths & Gaps ──
    col1, col2 = st.columns(2)
    strengths_html = ""
    gaps_html      = ""

    with col1:
        st.markdown("<div style='font-size:9px;letter-spacing:3.5px;color:rgba(240,240,245,0.35);text-transform:uppercase;margin-bottom:1rem;font-weight:600;'>Strengths</div>", unsafe_allow_html=True)
        for s in strengths:
            st.markdown(f"""
            <div style="background:#080f0a;border:1px solid rgba(62,207,178,0.15);border-radius:10px;padding:1rem;margin-bottom:0.6rem;border-left:3px solid rgba(62,207,178,0.4);">
                <div style="font-size:11px;font-weight:700;color:#3ecfb2;margin-bottom:5px;letter-spacing:0.5px;">{s.get('area','')}</div>
                <div style="font-size:12px;color:rgba(240,240,245,0.55);margin-bottom:4px;line-height:1.6;">{s.get('evidence','')}</div>
                <div style="font-size:11px;color:rgba(62,207,178,0.5);font-style:italic;">{s.get('relevance_to_job','')}</div>
            </div>
            """, unsafe_allow_html=True)

    with col2:
        st.markdown("<div style='font-size:9px;letter-spacing:3.5px;color:rgba(240,240,245,0.35);text-transform:uppercase;margin-bottom:1rem;font-weight:600;'>Gaps</div>", unsafe_allow_html=True)
        for g in gaps:
            st.markdown(f"""
            <div style="background:#0f0808;border:1px solid rgba(255,95,87,0.15);border-radius:10px;padding:1rem;margin-bottom:0.6rem;border-left:3px solid rgba(255,95,87,0.4);">
                <div style="font-size:11px;font-weight:700;color:#ff5f57;margin-bottom:5px;letter-spacing:0.5px;">{g.get('area','')}</div>
                <div style="font-size:12px;color:rgba(240,240,245,0.55);margin-bottom:4px;line-height:1.6;">{g.get('gap_detail','')}</div>
                <div style="font-size:11px;color:rgba(255,95,87,0.5);font-style:italic;">{g.get('impact_on_match','')}</div>
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
        .stApp,[data-testid="stAppViewContainer"],[data-testid="stMain"] { background: #050508 !important; }
        .block-container { padding: 0 !important; margin: 0 !important; max-width: 100% !important; }
        [data-testid="stVerticalBlock"] { gap: 0 !important; }
        html, body { overflow: hidden !important; }
        iframe { display: block; border: none; }
    </style>""", unsafe_allow_html=True)

    video_b64 = get_video_b64()

    components.html(f"""<!DOCTYPE html><html><head>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=DM+Sans:wght@300;400;500;600&display=swap" rel="stylesheet">
    <style>
        *{{margin:0;padding:0;box-sizing:border-box;}}
        html,body{{width:100%;height:100%;overflow:hidden;background:#050508;}}
        .bg-video{{position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);min-width:100%;min-height:100%;object-fit:cover;z-index:0;}}
        .overlay{{position:absolute;inset:0;background:linear-gradient(180deg,rgba(5,5,8,0.6) 0%,rgba(5,5,8,0.85) 60%,rgba(5,5,8,0.98) 100%);z-index:1;}}
        .grain{{position:absolute;inset:0;z-index:2;opacity:0.03;background-image:url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)'/%3E%3C/svg%3E");background-size:128px;}}
        .hero{{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;z-index:10;text-align:center;padding:0 20px;}}
        .tag{{font-family:'DM Sans',sans-serif;font-size:11px;color:rgba(232,197,71,0.7);letter-spacing:5px;text-transform:uppercase;font-weight:500;margin-bottom:28px;opacity:0;animation:fadeUp 0.6s ease 0.1s forwards;}}
        .title{{font-family:'DM Serif Display',Georgia,serif;font-size:clamp(64px,11vw,128px);font-weight:400;font-style:italic;color:#f0f0f5;letter-spacing:-2px;line-height:0.95;margin-bottom:24px;opacity:0;animation:fadeUp 0.7s ease 0.2s forwards;}}
        .title em{{color:#e8c547;font-style:normal;}}
        .subtitle{{font-family:'DM Sans',sans-serif;font-size:clamp(13px,1.4vw,16px);color:rgba(240,240,245,0.4);letter-spacing:0.5px;font-weight:300;margin-bottom:60px;opacity:0;animation:fadeUp 0.7s ease 0.35s forwards;max-width:480px;line-height:1.7;}}
        .btn-group{{display:flex;flex-direction:column;gap:10px;width:300px;opacity:0;animation:fadeUp 0.7s ease 0.5s forwards;}}
        .btn{{display:block;padding:16px 32px;font-family:'DM Sans',sans-serif;font-size:11px;font-weight:600;letter-spacing:2.5px;text-transform:uppercase;border-radius:7px;border:1px solid rgba(255,255,255,0.1);background:rgba(255,255,255,0.04);backdrop-filter:blur(16px);-webkit-backdrop-filter:blur(16px);color:rgba(240,240,245,0.8);text-decoration:none;text-align:center;transition:all 0.25s ease;}}
        .btn:hover{{color:#0a0a0a;background:#e8c547;border-color:#e8c547;transform:translateY(-2px);box-shadow:0 16px 40px rgba(232,197,71,0.25);}}
        .btn.primary{{background:rgba(232,197,71,0.1);border-color:rgba(232,197,71,0.3);color:#e8c547;}}
        .btn.primary:hover{{background:#e8c547;color:#0a0a0a;border-color:#e8c547;}}
        .corner{{position:absolute;width:60px;height:60px;z-index:5;opacity:0.3;}}
        .corner-tl{{top:28px;left:28px;border-top:1px solid #e8c547;border-left:1px solid #e8c547;}}
        .corner-br{{bottom:28px;right:28px;border-bottom:1px solid #e8c547;border-right:1px solid #e8c547;}}
        @keyframes fadeUp{{from{{opacity:0;transform:translateY(24px)}}to{{opacity:1;transform:translateY(0)}}}}
    </style></head><body>
        <video class="bg-video" autoplay loop muted playsinline>
            <source src="data:video/mp4;base64,{video_b64}" type="video/mp4">
        </video>
        <div class="overlay"></div>
        <div class="grain"></div>
        <div class="corner corner-tl"></div>
        <div class="corner corner-br"></div>
        <div class="hero">
            <p class="tag">AI-Powered Hiring Intelligence</p>
            <h1 class="title">hire<em>.</em>ai</h1>
            <p class="subtitle">Beyond the resume. Deep candidate intelligence from GitHub, skills, and live interviews — all in one pipeline.</p>
            <div class="btn-group">
                <a class="btn primary" href="?view=employer_auth">Enter as Employer</a>
                <a class="btn" href="?view=candidate_auth">Enter as Candidate</a>
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
        st.markdown("<p class='auth-title'>Welcome back</p>", unsafe_allow_html=True)
        st.markdown("<p class='auth-sub'>Sign in to your employer dashboard to analyze candidates, score interviews, and make better hiring decisions.</p>", unsafe_allow_html=True)
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
            st.session_state.pop("profile_from_cache", None)
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
                st.session_state['saved_job_role']        = job_role
                st.session_state['saved_job_description'] = job_description
                st.session_state.agent2_result            = None
                st.session_state.pop("github_summary", None)
                st.session_state['profile_from_cache']    = False

                file_bytes = resume_file.read()

                # ── Step 1: Extract email from raw text — no Gemini needed ────
                with st.spinner("Reading resume..."):
                    a1       = Agent1()
                    raw_text = a1._extract_text(file_bytes, resume_file.name)
                    import re as _re
                    email_match     = _re.search(r'[\w.\-+]+@[\w\-]+\.[a-zA-Z]{2,}', raw_text)
                    candidate_email = email_match.group(0).lower().strip() if email_match else ""

                # ── Step 2: MongoDB cache check ───────────────────────────────
                cached = get_cached_profile(candidate_email) if candidate_email else None

                if cached:
                    st.session_state.agent1_result         = cached
                    st.session_state['profile_from_cache'] = True
                    name = cached.get("resume", {}).get("name", candidate_email)
                    # Auto-run Agent 2 immediately with cached profile + new JD
                    with st.spinner(f"Profile found for {name} — analyzing match..."):
                        agent2_result = evaluate(
                            candidate_json=json.dumps(slim_agent1_result(cached)),
                            job_role=job_role,
                            job_description=job_description,
                        )
                        st.session_state.agent2_result = agent2_result
                else:
                    # ── Step 3: Full parse + scrape ───────────────────────────
                    with st.spinner("Parsing resume and scraping GitHub..."):
                        quick_data    = a1.parse_resume(file_bytes, resume_file.name)
                        github_url    = quick_data.get("github_url", "")
                        github_data   = a1.scrape_github(github_url) if github_url else {}
                        agent1_result = {"resume": quick_data, "github": github_data}
                        st.session_state.agent1_result         = agent1_result
                        st.session_state['profile_from_cache'] = False
                        save_profile_cache(agent1_result)

        # ── Show cache hit notice ─────────────────────────────────────────────
        if st.session_state.get('profile_from_cache') and st.session_state.agent1_result:
            name  = st.session_state.agent1_result.get("resume", {}).get("name", "this candidate")
            email = st.session_state.agent1_result.get("resume", {}).get("email", "")
            st.markdown(f"""
            <div style='background:rgba(62,207,178,0.08);border:1px solid rgba(62,207,178,0.2);border-radius:8px;padding:0.9rem 1.2rem;margin-bottom:1rem;display:flex;align-items:center;gap:10px;'>
                <span style='color:#3ecfb2;font-size:14px;'>✓</span>
                <span style='font-size:13px;color:rgba(240,240,245,0.7);'>Profile loaded from database for <strong style='color:#f0f0f5;'>{name}</strong> ({email}) — GitHub scraping skipped.</span>
            </div>
            """, unsafe_allow_html=True)

        # ── GitHub prompt only if NOT from cache and github scrape failed ─────
        if st.session_state.agent1_result and not st.session_state.agent2_result \
                and not st.session_state.get('profile_from_cache'):

            github_url  = st.session_state.agent1_result.get("resume", {}).get("github_url", "")
            github_data = st.session_state.agent1_result.get("github", {})
            github_ok   = bool(github_url and github_data
                               and github_data.get("candidate_profile"))

            if not github_ok:
                st.markdown("<br>", unsafe_allow_html=True)
                if github_url and not github_ok:
                    st.warning(f"GitHub URL found ({github_url}) but scraping failed. Enter manually or skip.")
                else:
                    st.warning("No GitHub URL found in resume. Add one manually or skip.")
                col_gh, col_skip = st.columns([3, 1])
                with col_gh:
                    manual_github = st.text_input(
                        "GitHub URL (optional)",
                        placeholder="https://github.com/username",
                        key="manual_github"
                    )
                with col_skip:
                    st.markdown("<br>", unsafe_allow_html=True)
                    st.button("Skip GitHub", key="skip_gh")

                col_analyze, _ = st.columns([1, 2])
                with col_analyze:
                    if st.button("📊  Analyze Match", use_container_width=True, key="analyze_match"):
                        pending_gh = st.session_state.get('manual_github', '').strip()
                        if pending_gh:
                            with st.spinner("Scraping GitHub profile..."):
                                a1      = Agent1()
                                scraped = a1.scrape_github(pending_gh)
                                updated = dict(st.session_state.agent1_result)
                                updated["github"] = scraped
                                updated["resume"] = dict(st.session_state.agent1_result["resume"])
                                updated["resume"]["github_url"] = pending_gh
                                st.session_state.agent1_result  = updated
                                save_profile_cache(updated)

                        with st.spinner("Evaluating candidate match..."):
                            saved_role = st.session_state.get('saved_job_role', job_role)
                            saved_jd   = st.session_state.get('saved_job_description', job_description)
                            agent2_result = evaluate(
                                candidate_json=json.dumps(slim_agent1_result(st.session_state.agent1_result)),
                                job_role=saved_role,
                                job_description=saved_jd,
                            )
                            st.session_state.agent2_result = agent2_result
            else:
                st.markdown("<br>", unsafe_allow_html=True)
                st.success(f"GitHub found: {github_url}")
                if st.button("📊  Analyze Match", use_container_width=True, key="analyze_match_auto"):
                    with st.spinner("Evaluating candidate match..."):
                        saved_role = st.session_state.get('saved_job_role', job_role)
                        saved_jd   = st.session_state.get('saved_job_description', job_description)
                        agent2_result = evaluate(
                            candidate_json=json.dumps(slim_agent1_result(st.session_state.agent1_result)),
                            job_role=saved_role,
                            job_description=saved_jd,
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
                        matched    = gs.get("matched_repos", [])
                        unmatched  = gs.get("unmatched_count", 0)
                        match_note = gs.get("match_note", "")

                        import re as _re
                        def sanitize(text):
                            """Strip any HTML tags that Gemini may have included in text fields."""
                            if not isinstance(text, str):
                                return str(text)
                            return _re.sub(r'<[^>]+>', '', text).strip()

                        if not matched:
                            st.markdown(f"""
                            <div style='background:#0c0c12;border:1px solid rgba(255,95,87,0.15);border-radius:10px;padding:1.5rem;border-left:3px solid rgba(255,95,87,0.4);'>
                                <div style='font-size:10px;font-weight:700;color:#ff5f57;letter-spacing:2px;text-transform:uppercase;margin-bottom:8px;'>No Matching Repositories</div>
                                <p style='color:rgba(240,240,245,0.55);font-size:13px;line-height:1.7;margin:0;'>{sanitize(match_note) or "None of the candidate's repositories directly demonstrate skills required for this role."}</p>
                                <p style='color:rgba(240,240,245,0.3);font-size:12px;margin:10px 0 0 0;'>{unmatched} repo(s) reviewed and excluded.</p>
                            </div>
                            """, unsafe_allow_html=True)
                        else:
                            st.markdown(f"<p style='color:rgba(240,240,245,0.35);font-size:12px;margin-bottom:1rem;font-style:italic;'>{sanitize(match_note)} ({unmatched} repos excluded)</p>", unsafe_allow_html=True)
                            for r in matched:
                                # Sanitize all text fields — Gemini sometimes bleeds HTML into JSON values
                                repo_name   = sanitize(r.get("name", ""))
                                repo_reason = sanitize(r.get("relevance_reason", ""))
                                repo_rating = sanitize(r.get("quality_rating", ""))
                                repo_langs  = [sanitize(l) for l in r.get("languages", []) if sanitize(l)]
                                repo_skills = [sanitize(s) for s in r.get("key_skills", []) if sanitize(s)]
                                repo_stars  = r.get("stars", 0)
                                repo_commits= r.get("commits", 0)

                                qcolor       = {"Advanced":"#3ecfb2","Expert":"#3ecfb2","Intermediate":"#e8c547","Beginner":"#ff5f57"}.get(repo_rating, "#94a3b8")
                                lang_pills   = "".join([f"<span style='background:rgba(62,207,178,0.1);border:1px solid rgba(62,207,178,0.25);color:#3ecfb2;padding:2px 9px;border-radius:5px;font-size:10px;margin:2px;display:inline-block;font-weight:500;'>{l}</span>" for l in repo_langs])
                                skill_pills  = "".join([f"<span style='background:rgba(232,197,71,0.08);border:1px solid rgba(232,197,71,0.2);color:#e8c547;padding:2px 9px;border-radius:5px;font-size:10px;margin:2px;display:inline-block;font-weight:500;'>{s}</span>" for s in repo_skills])
                                quality_badge = f"<span style='font-size:10px;font-weight:700;color:{qcolor};background:{qcolor}18;padding:2px 9px;border-radius:5px;border:1px solid {qcolor}44;'>{repo_rating}</span>" if repo_rating else ""

                                st.markdown(f"""
                                <div style='background:#0c0c12;border:1px solid rgba(255,255,255,0.07);border-radius:10px;padding:1.25rem;margin-bottom:0.6rem;'>
                                    <div style='display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:8px;'>
                                        <div style='font-size:14px;font-weight:600;color:#f0f0f5;'>{repo_name}</div>
                                        <div style='display:flex;gap:8px;align-items:center;flex-shrink:0;margin-left:12px;'>
                                            {quality_badge}
                                            <span style='font-size:11px;color:rgba(240,240,245,0.3);white-space:nowrap;'>⭐ {repo_stars} · {repo_commits} commits</span>
                                        </div>
                                    </div>
                                    <p style='color:rgba(240,240,245,0.45);font-size:12px;line-height:1.6;margin:0 0 10px 0;font-style:italic;'>{repo_reason}</p>
                                    <div>{lang_pills}</div>
                                    <div style='margin-top:5px;'>{skill_pills}</div>
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
            rec_color = {"HIRE": "#3ecfb2", "CONSIDER": "#e8c547", "REJECT": "#ff5f57"}.get(rec, "#888")
            rec_bg    = {"HIRE": "rgba(62,207,178,0.1)", "CONSIDER": "rgba(232,197,71,0.1)", "REJECT": "rgba(255,95,87,0.1)"}.get(rec, "rgba(255,255,255,0.05)")

            overall     = results.get("OVERALL_SCORE", 0)
            score_color = "#3ecfb2" if overall >= 70 else "#e8c547" if overall >= 40 else "#ff5f57"

            # Header row
            col_score, col_verdict = st.columns([1, 2])
            with col_score:
                st.markdown(f"""
                <div style='background:#0c0c12;border:1px solid rgba(255,255,255,0.07);border-radius:12px;padding:1.75rem;text-align:center;position:relative;overflow:hidden;'>
                    <div style='position:absolute;top:0;left:0;right:0;height:1px;background:linear-gradient(90deg,transparent,{score_color},transparent);opacity:0.6;'></div>
                    <div style='font-size:9px;letter-spacing:3.5px;color:rgba(240,240,245,0.35);text-transform:uppercase;margin-bottom:12px;font-weight:600;'>Interview Score</div>
                    <div style='font-size:64px;font-weight:700;color:{score_color};line-height:1;font-variant-numeric:tabular-nums;'>{overall}</div>
                    <div style='font-size:12px;color:rgba(240,240,245,0.3);margin-top:4px;'>out of 100</div>
                    <div style='display:inline-block;padding:5px 16px;background:{rec_bg};border:1px solid {rec_color}55;border-radius:6px;margin-top:1rem;'>
                        <span style='color:{rec_color};font-weight:700;font-size:10px;letter-spacing:2.5px;'>{rec}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)

            with col_verdict:
                st.markdown(f"""
                <div style='background:#0c0c12;border:1px solid rgba(255,255,255,0.07);border-radius:12px;padding:1.75rem;height:100%;position:relative;overflow:hidden;'>
                    <div style='position:absolute;left:0;top:0;bottom:0;width:3px;background:linear-gradient(180deg,#e8c547,rgba(232,197,71,0.2));border-radius:2px 0 0 2px;'></div>
                    <div style='font-size:9px;letter-spacing:3.5px;color:rgba(240,240,245,0.35);text-transform:uppercase;margin-bottom:10px;font-weight:600;'>Summary</div>
                    <p style='color:rgba(240,240,245,0.75);font-size:14px;line-height:1.9;margin:0;font-weight:300;'>{results.get("SUMMARY","")}</p>
                </div>
                """, unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown("<span class='label'>Score Breakdown</span>", unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)

            interview_categories = [
                ("Technicality",    "TECHNICALITY",    "TECHNICALITY_FEEDBACK"),
                ("Problem Solving", "PROBLEM_SOLVING",  "PROBLEM_SOLVING_FEEDBACK"),
                ("Communication",   "COMMUNICATION",    "COMMUNICATION_FEEDBACK"),
                ("Personality",     "PERSONALITY",      "PERSONALITY_FEEDBACK"),
                ("Confidence",      "CONFIDENCE",       "CONFIDENCE_FEEDBACK"),
            ]

            left_cards  = ""
            right_cards = ""
            for i, (label, score_key, feedback_key) in enumerate(interview_categories):
                score    = results.get(score_key, 0)
                feedback = results.get(feedback_key, "No feedback available.")
                bc       = "#3ecfb2" if score >= 70 else "#e8c547" if score >= 40 else "#ff5f57"
                card     = f"""
                <div style='background:#0c0c12;border:1px solid rgba(255,255,255,0.07);border-radius:12px;padding:1.5rem;margin-bottom:0.75rem;'>
                    <div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;'>
                        <span style='font-size:10px;font-weight:600;color:rgba(240,240,245,0.4);text-transform:uppercase;letter-spacing:2.5px;'>{label}</span>
                        <span style='font-size:26px;font-weight:700;color:{bc};line-height:1;font-variant-numeric:tabular-nums;'>{score}</span>
                    </div>
                    <div style='background:rgba(255,255,255,0.04);border-radius:3px;height:3px;margin-bottom:14px;'>
                        <div style='background:{bc};width:{score}%;height:3px;border-radius:3px;box-shadow:0 0 8px {bc}66;'></div>
                    </div>
                    <p style='font-size:13px;color:rgba(240,240,245,0.55);margin:0;line-height:1.8;font-weight:300;'>{feedback}</p>
                </div>"""
                if i % 2 == 0: left_cards += card
                else:          right_cards += card

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
            st.session_state.pop("profile_from_cache", None)
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
            st.session_state['saved_job_role']        = job_role
            st.session_state['saved_job_description'] = job_description
            st.session_state.agent2_result            = None
            st.session_state.pop("github_summary", None)
            st.session_state['profile_from_cache']    = False

            file_bytes = resume_file.read()

            # ── Step 1: Extract email from raw text (no Gemini needed) ────────
            with st.spinner("Reading your resume..."):
                a1         = Agent1()
                raw_text   = a1._extract_text(file_bytes, resume_file.name)
                # Fast regex email extraction — no API call
                import re as _re
                email_match    = _re.search(r'[\w.\-+]+@[\w\-]+\.[a-zA-Z]{2,}', raw_text)
                candidate_email = email_match.group(0).lower().strip() if email_match else ""

            # ── Step 2: MongoDB cache check ───────────────────────────────────
            cached = get_cached_profile(candidate_email) if candidate_email else None

            if cached:
                st.session_state.agent1_result         = cached
                st.session_state['profile_from_cache'] = True
                # Auto-run Agent 2 immediately — no Gemini parsing needed
                with st.spinner("Profile found — analyzing your match..."):
                    agent2_result = evaluate(
                        candidate_json=json.dumps(slim_agent1_result(cached)),
                        job_role=job_role,
                        job_description=job_description,
                    )
                    st.session_state.agent2_result = agent2_result
            else:
                # ── Step 3: Full parse + scrape ───────────────────────────────
                with st.spinner("Parsing your resume and scraping GitHub..."):
                    quick_data  = a1.parse_resume(file_bytes, resume_file.name)
                    github_url  = quick_data.get("github_url", "")
                    github_data = a1.scrape_github(github_url) if github_url else {}
                    agent1_result = {"resume": quick_data, "github": github_data}
                    st.session_state.agent1_result         = agent1_result
                    st.session_state['profile_from_cache'] = False
                    save_profile_cache(agent1_result)

                # If GitHub scrape succeeded, auto-run Agent 2
                github_ok = bool(
                    agent1_result.get("resume", {}).get("github_url") and
                    agent1_result.get("github", {}).get("candidate_profile")
                )
                if github_ok:
                    with st.spinner("Analyzing your match..."):
                        agent2_result = evaluate(
                            candidate_json=json.dumps(slim_agent1_result(agent1_result)),
                            job_role=job_role,
                            job_description=job_description,
                        )
                        st.session_state.agent2_result = agent2_result

    # ── Show cache hit notice ─────────────────────────────────────────────────
    if st.session_state.get('profile_from_cache') and st.session_state.agent1_result:
        name  = st.session_state.agent1_result.get("resume", {}).get("name", "your profile")
        email = st.session_state.agent1_result.get("resume", {}).get("email", "")
        st.markdown(f"""
        <div style='background:rgba(62,207,178,0.08);border:1px solid rgba(62,207,178,0.2);border-radius:8px;padding:0.9rem 1.2rem;margin-bottom:1rem;display:flex;align-items:center;gap:10px;'>
            <span style='color:#3ecfb2;font-size:14px;'>✓</span>
            <span style='font-size:13px;color:rgba(240,240,245,0.7);'>Existing profile found for <strong style='color:#f0f0f5;'>{name}</strong> — analysis ran instantly without re-scraping.</span>
        </div>
        """, unsafe_allow_html=True)

    # ── GitHub manual entry — only if NOT cache hit and scrape failed ─────────
    if st.session_state.agent1_result and not st.session_state.agent2_result \
            and not st.session_state.get('profile_from_cache'):

        github_url  = st.session_state.agent1_result.get("resume", {}).get("github_url", "")
        github_data = st.session_state.agent1_result.get("github", {})
        github_ok   = bool(github_url and github_data
                           and github_data.get("candidate_profile"))

        if not github_ok:
            st.markdown("<br>", unsafe_allow_html=True)
            if github_url and not github_ok:
                st.warning(f"GitHub URL found ({github_url}) but scraping failed. Enter it manually or skip.")
            else:
                st.warning("No GitHub URL found in your resume. Add one or skip.")

            col_gh, col_skip = st.columns([3, 1])
            with col_gh:
                manual_github = st.text_input(
                    "GitHub URL (optional)",
                    placeholder="https://github.com/username",
                    key="manual_github_can"
                )
            with col_skip:
                st.markdown("<br>", unsafe_allow_html=True)
                st.button("Skip", key="can_skip_gh")

            if st.button("✨  Analyze Match", use_container_width=True, key="can_analyze_match"):
                saved_role = st.session_state.get('saved_job_role', '')
                saved_jd   = st.session_state.get('saved_job_description', '')

                if manual_github and manual_github.strip():
                    with st.spinner("Scraping your GitHub..."):
                        a1          = Agent1()
                        github_data = a1.scrape_github(manual_github.strip())
                        st.session_state.agent1_result["github"]               = github_data
                        st.session_state.agent1_result["resume"]["github_url"] = manual_github.strip()
                        save_profile_cache(st.session_state.agent1_result)
                        st.session_state.pop("github_summary", None)

                with st.spinner("Analyzing your match..."):
                    agent2_result = evaluate(
                        candidate_json=json.dumps(slim_agent1_result(st.session_state.agent1_result)),
                        job_role=saved_role,
                        job_description=saved_jd,
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