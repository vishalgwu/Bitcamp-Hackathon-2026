import streamlit as st
import json

st.set_page_config(page_title="Hire.AI", page_icon="🤖")

if "page" not in st.session_state:
    st.session_state.page = "home"

def go(page):
    st.session_state.page = page
    st.rerun()

# ── Page 1: Home ──────────────────────────────────────────────────────────────
def home():
    st.title("🤖 Hire.AI")
    st.caption("Smart Hiring. Smarter Careers.")
    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🏢 Employer Login", use_container_width=True):
            go("employer_login")
    with col2:
        if st.button("🎓 Student Login", use_container_width=True):
            go("candidate_login")

# ── Page 2: Employer Login ────────────────────────────────────────────────────
def employer_login():
    st.title("🏢 Employer Login")
    if st.button("← Back"): go("home")
    st.divider()
    email    = st.text_input("Mail ID")
    password = st.text_input("Password", type="password")
    if st.button("Login", use_container_width=True):
        if email and password:
            st.session_state.employer_email = email
            go("employer_logged_in")
        else:
            st.error("Enter mail ID and password.")

# ── Page 3: Candidate Login ───────────────────────────────────────────────────
def candidate_login():
    st.title("🎓 Student Login")
    if st.button("← Back"): go("home")
    st.divider()
    email    = st.text_input("Mail ID")
    password = st.text_input("Password", type="password")
    if st.button("Login", use_container_width=True):
        if email and password:
            st.session_state.candidate_email = email
            go("candidate_logged_in")
        else:
            st.error("Enter mail ID and password.")
    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        if st.button("No account? Sign Up", use_container_width=True): go("candidate_sign_up")
    with col2:
        if st.button("Forgot Password?", use_container_width=True): go("candidate_reset")

# ── Page 3a: Sign Up ──────────────────────────────────────────────────────────
def candidate_sign_up():
    st.title("📝 Student Sign Up")
    if st.button("← Back"): go("candidate_login")
    st.divider()
    name     = st.text_input("Full Name")
    email    = st.text_input("Mail ID")
    password = st.text_input("Password", type="password")
    confirm  = st.text_input("Confirm Password", type="password")
    if st.button("Create Account", use_container_width=True):
        if not (name and email and password and confirm):
            st.warning("Fill all fields.")
        elif password != confirm:
            st.error("Passwords do not match.")
        else:
            st.session_state.candidate_email = email
            go("candidate_logged_in")

# ── Page 3b: Reset Password ───────────────────────────────────────────────────
def candidate_reset():
    st.title("🔑 Reset Password")
    if st.button("← Back"): go("candidate_login")
    st.divider()
    email = st.text_input("Registered Mail ID")
    if st.button("Send Reset Link", use_container_width=True):
        if email: st.success(f"Reset link sent to {email}")
        else: st.error("Enter your mail ID.")

# ── Page 3c: Candidate Dashboard ─────────────────────────────────────────────
def candidate_logged_in():
    st.title("✅ Student Dashboard")
    st.write(f"Welcome, {st.session_state.get('candidate_email', '')}")

# ── Page 4: Employer Dashboard ────────────────────────────────────────────────
def employer_logged_in():
    st.title("✅ Employer Dashboard")
    st.write(f"Welcome, {st.session_state.get('employer_email', '')}")
    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        if st.button("📄 Candidate Parser", use_container_width=True): go("candidate_parser")
    with col2:
        if st.button("🎤 Interview Evaluator", use_container_width=True): go("interview_evaluator")

# ── Page 4a: Candidate Parser ─────────────────────────────────────────────────
def candidate_parser():
    from agent1 import Agent1

    st.title("📄 Candidate Parser")
    if st.button("← Back"): go("employer_logged_in")
    st.divider()

    resume = st.file_uploader("Upload Resume", type=["pdf", "docx"])

    if st.button("🔍 Parse Resume", use_container_width=True):
        if not resume:
            st.warning("Please upload a resume.")
        else:
            with st.spinner("Parsing resume + GitHub..."):
                result = Agent1().run(resume.read(), resume.name)
            st.session_state.result = result
            st.success("✅ Done!")

    if "result" in st.session_state and st.session_state.result:
        result = st.session_state.result

        # ── Resume ────────────────────────────────────────────────────────────
        with st.expander("📄 Resume", expanded=True):
            st.json(result.get("resume", {}))

        # ── GitHub ────────────────────────────────────────────────────────────
        github = result.get("github", {})
        if github:
            with st.expander("🐙 GitHub Profile"):
                st.json(github.get("candidate_profile", {}))

            with st.expander("🛠️ Skills Summary"):
                st.json(github.get("skills_summary", {}))

            with st.expander("📁 Repository Summary"):
                st.json(github.get("repository_summary", {}))

            with st.expander("🔍 All Repositories"):
                st.json(github.get("repositories", []))

            with st.expander("🏆 Final Assessment"):
                st.json(github.get("final_assessment", {}))
        else:
            st.info("No GitHub URL found in resume — GitHub scraping skipped.")

        # ── Evaluate Match ────────────────────────────────────────────────────
        st.divider()
        job_position = st.text_input("Job Position", placeholder="e.g. Software Engineer")
        job_desc = st.text_area("Job Description", placeholder="Paste job description here...", height=150)

        if st.button("📊 Evaluate Match", use_container_width=True):
            if not job_position or not job_desc:
                st.warning("Please enter Job Position and Job Description.")
            else:
                from agent2 import evaluate, score_to_verdict, get_verdict_emoji, get_verdict_label
                import json
                with st.spinner("Evaluating match..."):
                    eval_result = evaluate(
                        candidate_json=json.dumps(result),
                        job_role=job_position,
                        job_description=job_desc,
                    )
                st.divider()
                st.subheader("📊 Evaluation Result")
                st.json(eval_result)
# ── Page 4b: Interview Evaluator ──────────────────────────────────────────────
def interview_evaluator():
    pass

# ── Router ────────────────────────────────────────────────────────────────────
pages = {
    "home":                home,
    "employer_login":      employer_login,
    "candidate_login":     candidate_login,
    "candidate_sign_up":   candidate_sign_up,
    "candidate_reset":     candidate_reset,
    "candidate_logged_in": candidate_logged_in,
    "employer_logged_in":  employer_logged_in,
    "candidate_parser":    candidate_parser,
    "interview_evaluator": interview_evaluator,
}

pages[st.session_state.page]()