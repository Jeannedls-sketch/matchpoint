import streamlit as st
import pandas as pd
import plotly.express as px
from dotenv import load_dotenv

from utils.document_parser import extract_all
from utils.claude_client import (
    build_profile_from_documents,
    generate_backup_questions,
    analyze_story,
    generate_strengths_report,
    suggest_industries_and_roles,
    adjust_suggestions,
    generate_mock_job_listings,
    tailor_application,
)

load_dotenv()

st.set_page_config(page_title="Matchpoint", page_icon="🎯", layout="wide")

# --- session state init ---
if "step" not in st.session_state:
    st.session_state.step = 1
if "profile" not in st.session_state:
    st.session_state.profile = None
if "backup_questions" not in st.session_state:
    st.session_state.backup_questions = None
if "backup_answers" not in st.session_state:
    st.session_state.backup_answers = {}
if "story_analysis" not in st.session_state:
    st.session_state.story_analysis = None
if "strengths_ratings" not in st.session_state:
    st.session_state.strengths_ratings = {}
if "strengths_report" not in st.session_state:
    st.session_state.strengths_report = None
if "selected_growth_areas" not in st.session_state:
    st.session_state.selected_growth_areas = []
if "values_answers" not in st.session_state:
    st.session_state.values_answers = {}
if "suggestions" not in st.session_state:
    st.session_state.suggestions = None
if "override_mode" not in st.session_state:
    st.session_state.override_mode = False
if "job_listings" not in st.session_state:
    st.session_state.job_listings = None
if "approved_job" not in st.session_state:
    st.session_state.approved_job = None
if "tailored_application" not in st.session_state:
    st.session_state.tailored_application = None
if "application_log" not in st.session_state:
    st.session_state.application_log = []

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
# STEP 2 — YOUR STORY
# ============================================================
elif st.session_state.step == 2:
    st.header("Step 2 — Tell us about a moment you were at your best")
    st.write(
        "Think of a specific moment — at work, school, with friends, "
        "anywhere — when you felt genuinely proud of how you showed up."
    )

    if st.session_state.story_analysis is None:
        story_text = st.text_area(
            "Your story",
            height=180,
            placeholder="Take your time. What happened, what did you do, and why did it matter to you?",
            key="story_input",
        )

        col_a, col_b = st.columns([1, 1])
        with col_a:
            submit_story = st.button("Continue →", type="primary", disabled=not story_text.strip())
        with col_b:
            stuck = st.button("I can't think of anything...")

        # --- backup questions flow if user is stuck ---
        if stuck:
            with st.spinner("Generating some questions to help..."):
                st.session_state.backup_questions = generate_backup_questions(
                    st.session_state.profile
                )
            st.rerun()

        if st.session_state.backup_questions:
            st.divider()
            st.subheader("Let's find one together — answer what resonates")
            for i, q in enumerate(st.session_state.backup_questions):
                st.session_state.backup_answers[i] = st.text_area(
                    q, value=st.session_state.backup_answers.get(i, ""), key=f"backup_{i}"
                )

            if st.button("Build my story from these answers →", type="primary"):
                combined = "\n\n".join(
                    f"Q: {q}\nA: {st.session_state.backup_answers.get(i, '')}"
                    for i, q in enumerate(st.session_state.backup_questions)
                    if st.session_state.backup_answers.get(i, "").strip()
                )
                if combined:
                    with st.spinner("Analyzing your story..."):
                        st.session_state.story_analysis = analyze_story(
                            combined, st.session_state.profile
                        )
                    st.rerun()
                else:
                    st.warning("Answer at least one question to continue.")

        if submit_story:
            with st.spinner("Analyzing your story..."):
                st.session_state.story_analysis = analyze_story(
                    story_text, st.session_state.profile
                )
            st.rerun()

    # --- show analysis once available ---
    else:
        analysis = st.session_state.story_analysis
        if "error" in analysis:
            st.error("Couldn't analyze your story automatically.")
            st.code(analysis.get("raw_response", ""))
        else:
            st.success("Here's what your story shows")
            st.write(f"**Summary:** {analysis.get('summary', '—')}")
            st.write("**Traits it reveals:**")
            for t in analysis.get("traits", []):
                st.write(f"- {t}")

            if st.button("Continue to Step 3 →", type="primary"):
                st.session_state.step = 3
                st.rerun()

    if st.button("← Back to Step 1"):
        st.session_state.step = 1
        st.rerun()

# ============================================================
# STEP 3 — STRENGTHS
# ============================================================
elif st.session_state.step == 3:
    st.header("Step 3 — Rate your strengths")

    default_strengths = ["Problem-solving", "Communication", "Leadership", "Adaptability", "Attention to detail"]
    strengths_list = st.session_state.story_analysis.get("suggested_strengths") or default_strengths

    if st.session_state.strengths_report is None:
        st.write("Rate yourself honestly on each — 1 (not a strength) to 5 (clear strength).")

        for s in strengths_list:
            st.session_state.strengths_ratings[s] = st.slider(
                s, 1, 5, st.session_state.strengths_ratings.get(s, 3), key=f"rate_{s}"
            )

        if st.button("Generate my report →", type="primary"):
            with st.spinner("Building your strengths report..."):
                report = generate_strengths_report(
                    st.session_state.strengths_ratings,
                    st.session_state.profile,
                    st.session_state.story_analysis,
                )
                st.session_state.strengths_report = report
            st.rerun()

    else:
        report = st.session_state.strengths_report
        if "error" in report:
            st.error("Couldn't generate the report automatically.")
            st.code(report.get("raw_response", ""))
        else:
            st.success("Here's your strengths report")
            st.write(report.get("narrative", ""))

            st.subheader("✅ Confirmed strengths")
            for s in report.get("confirmed_strengths", []):
                st.write(f"- {s}")

            growth_areas = report.get("growth_areas", [])
            if growth_areas:
                st.subheader("🌱 Growth areas")
                st.write("Pick the ones that matter most to you right now:")
                labels = [g["area"] for g in growth_areas]
                notes_by_label = {g["area"]: g.get("note", "") for g in growth_areas}
                selected = st.multiselect("Select growth areas", labels, default=st.session_state.selected_growth_areas)
                st.session_state.selected_growth_areas = selected
                for s in selected:
                    st.caption(f"**{s}:** {notes_by_label.get(s, '')}")
            else:
                st.info("No major growth areas flagged from your ratings — strong across the board!")

            if st.button("Continue to Step 4 →", type="primary"):
                st.session_state.step = 4
                st.rerun()

    if st.button("← Back to Step 2"):
        st.session_state.step = 2
        st.rerun()

# ============================================================
# STEP 4 — VALUES & MATCHES
# ============================================================
elif st.session_state.step == 4:
    st.header("Step 4 — Your values, and your matches")

    VALUES_QUESTIONS = [
        "What matters most to you in your next role? (impact, learning, pay, flexibility, prestige...)",
        "What kind of work environment do you thrive in?",
        "Any industries or company types you'd love — or want to avoid?",
        "Anything else about what you're looking for?",
    ]

    # --- part A: values Q&A + suggestions ---
    if st.session_state.suggestions is None:
        st.subheader("A few questions about what you value")
        for i, q in enumerate(VALUES_QUESTIONS):
            st.session_state.values_answers[q] = st.text_area(
                q, value=st.session_state.values_answers.get(q, ""), key=f"values_{i}"
            )

        if st.button("Get my suggestions →", type="primary"):
            with st.spinner("Thinking about what could fit you..."):
                st.session_state.suggestions = suggest_industries_and_roles(
                    st.session_state.profile,
                    st.session_state.story_analysis,
                    st.session_state.strengths_report,
                    st.session_state.values_answers,
                )
            st.rerun()

    # --- part B: show suggestions, allow override, then generate matches ---
    elif st.session_state.job_listings is None:
        suggestions = st.session_state.suggestions
        if "error" in suggestions:
            st.error("Couldn't generate suggestions automatically.")
            st.code(suggestions.get("raw_response", ""))
        else:
            st.subheader("Suggested for you")
            st.write(suggestions.get("reasoning", ""))
            st.write("**Industries:** " + ", ".join(suggestions.get("suggested_industries", [])))
            st.write("**Roles:** " + ", ".join(suggestions.get("suggested_roles", [])))

            col_a, col_b = st.columns([1, 1])
            with col_a:
                if st.button("This looks right → Find matching jobs", type="primary"):
                    with st.spinner("Searching for matching roles..."):
                        st.session_state.job_listings = generate_mock_job_listings(
                            suggestions, st.session_state.profile
                        )
                    st.rerun()
            with col_b:
                if st.button("I don't agree with this"):
                    st.session_state.override_mode = True

            if st.session_state.override_mode:
                st.divider()
                override_text = st.text_area(
                    "Tell us what you actually want instead — we'll tailor the next steps for you.",
                    placeholder="e.g. I really want to do consulting, please focus there instead.",
                )
                if st.button("Update my suggestions →", type="primary", disabled=not override_text.strip()):
                    with st.spinner("Updating your suggestions..."):
                        st.session_state.suggestions = adjust_suggestions(
                            suggestions, override_text, st.session_state.profile
                        )
                        st.session_state.override_mode = False
                    st.rerun()

    # --- part C: job listings, approve one ---
    else:
        st.subheader("Your matches")
        for i, job in enumerate(st.session_state.job_listings):
            with st.container(border=True):
                st.write(f"**{job.get('title')}** — {job.get('company')} · {job.get('location')}")
                st.write(job.get("description", ""))
                st.progress(job.get("match_score", 0) / 100, text=f"Match: {job.get('match_score', 0)}%")
                st.caption(job.get("match_reason", ""))
                if st.button("Approve this one →", key=f"approve_{i}"):
                    st.session_state.approved_job = job
                    st.session_state.step = 5
                    st.rerun()

    if st.button("← Back to Step 3"):
        st.session_state.step = 3
        st.rerun()

# ============================================================
# STEP 5 — DASHBOARD
# ============================================================
elif st.session_state.step == 5:
    st.header("🎯 Your Dashboard")

    job = st.session_state.approved_job

    # generate tailored CV/cover letter once, on first arrival
    if st.session_state.tailored_application is None and job is not None:
        with st.spinner("Tailoring your CV and cover letter for this role..."):
            st.session_state.tailored_application = tailor_application(
                job, st.session_state.profile, st.session_state.story_analysis
            )
            st.session_state.application_log.append(
                {"title": job.get("title"), "company": job.get("company"), "status": "Submitted"}
            )

    # --- top metrics ---
    col1, col2, col3 = st.columns(3)
    col1.metric("Jobs reviewed", len(st.session_state.job_listings or []))
    col2.metric("Applications submitted", len(st.session_state.application_log))
    col3.metric(
        "Best match score",
        f"{max((j.get('match_score', 0) for j in st.session_state.job_listings or [{'match_score': 0}]), default=0)}%",
    )

    st.divider()

    # --- match score chart ---
    if st.session_state.job_listings:
        df = pd.DataFrame(st.session_state.job_listings)
        fig = px.bar(
            df, x="title", y="match_score", color="match_score",
            color_continuous_scale="Blues", title="Match scores across reviewed jobs",
        )
        fig.update_layout(xaxis_title="", yaxis_title="Match %", showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # --- application tracking table ---
    st.subheader("Application tracking")
    if st.session_state.application_log:
        st.dataframe(pd.DataFrame(st.session_state.application_log), use_container_width=True, hide_index=True)

    st.divider()

    # --- tailored CV + cover letter preview ---
    tailored = st.session_state.tailored_application
    if tailored and "error" not in tailored:
        st.subheader(f"Tailored for: {job.get('title')} at {job.get('company')}")

        col_a, col_b = st.columns(2)
        with col_a:
            st.write("**CV highlights**")
            for h in tailored.get("cv_highlights", []):
                st.write(f"- {h}")
        with col_b:
            st.write("**Cover letter**")
            st.text_area("", value=tailored.get("cover_letter", ""), height=280, disabled=True, label_visibility="collapsed")
    elif tailored:
        st.error("Couldn't generate the tailored application automatically.")
        st.code(tailored.get("raw_response", ""))

    if st.button("← Back to Step 4"):
        st.session_state.step = 4
        st.rerun()
