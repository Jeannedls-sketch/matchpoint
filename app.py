import streamlit as st
from dotenv import load_dotenv

from utils.document_parser import extract_all
from utils.claude_client import build_profile_from_documents

load_dotenv()

st.set_page_config(page_title="Matchpoint", page_icon="🎯", layout="wide")

# --- session state init ---
if "step" not in st.session_state:
    st.session_state.step = 1
if "profile" not in st.session_state:
    st.session_state.profile = None

st.title("🎯 Matchpoint")
st.caption("Your AI job-matching and application agent")

# --- step indicator ---
steps = ["1. Onboarding", "2. Your Story", "3. Strengths", "4. Values & Matches", "Dashboard"]
cols = st.columns(len(steps))
for i, (col, label) in enumerate(zip(cols, steps), start=1):
    with col:
        if i == st.session_state.step:
            st.markdown(f"**➡️ {label}**")
        elif i < st.session_state.step:
            st.markdown(f"✅ {label}")
        else:
            st.markdown(f"{label}")

st.divider()

# ============================================================
# STEP 1 — ONBOARDING
# ============================================================
if st.session_state.step == 1:
    st.header("Step 1 — Tell us about yourself")
    st.write("Upload your documents so Matchpoint can build your profile.")

    col1, col2 = st.columns(2)
    with col1:
        cv_file = st.file_uploader("CV / Resume (required)", type=["pdf", "docx"])
        cover_letter_file = st.file_uploader(
            "Old cover letter (optional — used to capture your writing tone)",
            type=["pdf", "docx"],
        )
    with col2:
        transcripts_file = st.file_uploader("Transcripts (optional)", type=["pdf", "docx"])
        recommendation_file = st.file_uploader(
            "Recommendation letter (optional)", type=["pdf", "docx"]
        )
        certifications_file = st.file_uploader(
            "Certifications (optional)", type=["pdf", "docx"]
        )

    if st.button("Build my profile →", type="primary", disabled=(cv_file is None)):
        with st.spinner("Reading your documents..."):
            uploaded = {
                "cv": cv_file,
                "transcripts": transcripts_file,
                "recommendation_letter": recommendation_file,
                "certifications": certifications_file,
            }
            documents = extract_all(uploaded)

            writing_sample = ""
            if cover_letter_file is not None:
                extracted = extract_all({"cover_letter": cover_letter_file})
                writing_sample = extracted.get("cover_letter", "")

            profile = build_profile_from_documents(documents, writing_sample)
            st.session_state.profile = profile

        if "error" in profile:
            st.error("Couldn't parse your profile automatically. Raw response below:")
            st.code(profile.get("raw_response", ""))
        else:
            st.success("Profile built!")
            st.rerun()

    if not cv_file:
        st.info("A CV is required to continue. Other documents are optional but improve accuracy.")

    # if profile already built, show it and let user proceed / clarify interests
    if st.session_state.profile and "error" not in st.session_state.profile:
        profile = st.session_state.profile
        st.subheader("Here's what we found")

        with st.expander("Extracted profile", expanded=True):
            st.write(f"**Name:** {profile.get('name', '—')}")

            st.write("**Education:**")
            for edu in profile.get("education", []):
                st.write(f"- {edu.get('degree', '')}, {edu.get('institution', '')} ({edu.get('dates', '')})")

            st.write("**Experience:**")
            for exp in profile.get("experience", []):
                st.write(f"- **{exp.get('role', '')}**, {exp.get('company', '')} ({exp.get('dates', '')})")
                for h in exp.get("highlights", []):
                    st.write(f"  - {h}")

            st.write("**Skills:**", ", ".join(profile.get("skills", [])) or "—")
            st.write("**Certifications:**", ", ".join(profile.get("certifications", [])) or "—")
            st.write("**Writing tone notes:**", profile.get("writing_tone_notes", "—"))

        # --- 1.b: if interests unclear, ask directly ---
        if not profile.get("interests_clear", False):
            st.warning("Your documents don't clearly state what you're looking for next.")
            interests_input = st.text_area(
                "What are you actually interested in? (industries, roles, anything on your mind)",
                placeholder="e.g. strategy consulting, sustainability, luxury retail...",
            )
            if st.button("Save my interests and continue →"):
                st.session_state.profile["stated_interests"] = [
                    i.strip() for i in interests_input.split(",") if i.strip()
                ]
                st.session_state.profile["interests_clear"] = True
                st.session_state.step = 2
                st.rerun()
        else:
            st.write("**Stated interests:**", ", ".join(profile.get("stated_interests", [])))
            if st.button("Continue to Step 2 →", type="primary"):
                st.session_state.step = 2
                st.rerun()

# ============================================================
# STEPS 2-5 — placeholders for now
# ============================================================
else:
    st.header(f"Step {st.session_state.step} — coming next")
    st.info("This step isn't built yet — we'll add it next.")
    if st.button("← Back"):
        st.session_state.step -= 1
        st.rerun()
