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
    score_and_categorize_jobs,
    tailor_application,
    suggest_cv_keywords,
)
from utils.pdf_generator import generate_cv_pdf, generate_cover_letter_pdf
from utils.job_search import search_multiple_roles, COUNTRY_CODES
from utils.career_data import find_real_offers, find_career_paths, offers_summary_stats

load_dotenv()

st.set_page_config(page_title="Matchpoint", page_icon="◆", layout="wide")

# --- design system: modern tech/startup — near-black on off-white, one bold indigo accent, all sans-serif ---
CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

:root {
    --ink: #0F1115;
    --bg: #FAFAF9;
    --panel: #FFFFFF;
    --muted: #6B7280;
    --accent: #4F46E5;
    --accent-hover: #4338CA;
    --border: #E5E5E3;
}

html, body, [class*="css"] { font-family: 'Inter', -apple-system, sans-serif; }
.stApp { background-color: var(--bg); }

h1, h2, h3 {
    font-family: 'Inter', sans-serif !important;
    font-weight: 800 !important;
    color: var(--ink) !important;
    letter-spacing: -0.02em;
}
h1 { font-size: 2rem !important; margin-bottom: 0.3rem; }
h2 { font-size: 1.4rem !important; }
h3 { font-size: 1.1rem !important; }

p, li, span, label { color: var(--ink); }
.stCaption, [data-testid="stCaptionContainer"] { color: var(--muted) !important; font-size: 0.85rem; }

/* buttons: confident, slightly rounded, no border unless secondary */
.stButton>button {
    background-color: var(--panel);
    color: var(--ink);
    border: 1px solid var(--border);
    border-radius: 8px;
    font-weight: 600;
    padding: 0.55rem 1.3rem;
    transition: all 0.12s ease;
}
.stButton>button:hover { border-color: var(--ink); }
.stButton>button[kind="primary"] {
    background-color: var(--accent);
    color: white;
    border: none;
    box-shadow: 0 1px 2px rgba(79,70,229,0.25);
}
.stButton>button[kind="primary"]:hover { background-color: var(--accent-hover); }

/* bordered containers: subtle card, minimal shadow */
div[data-testid="stVerticalBlockBorderWrapper"] {
    border: 1px solid var(--border) !important;
    border-radius: 10px !important;
    padding: 1.1rem !important;
    box-shadow: 0 1px 2px rgba(0,0,0,0.03) !important;
    background: var(--panel) !important;
}

div[data-testid="stExpander"] {
    border: 1px solid var(--border) !important;
    border-radius: 10px !important;
    box-shadow: none !important;
    background: var(--panel) !important;
}

div[data-testid="stProgress"] > div > div > div { background-color: var(--accent) !important; }

div[data-testid="stMetric"] {
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 0.9rem 1rem;
}
div[data-testid="stMetricLabel"] { color: var(--muted) !important; font-size: 0.8rem; }
div[data-testid="stMetricValue"] { font-family: 'Inter', sans-serif !important; font-weight: 800 !important; color: var(--ink) !important; }

.stTextArea textarea, .stTextInput input {
    border: 1px solid var(--border) !important;
    border-radius: 8px !important;
    background: var(--panel) !important;
}
.stTextArea textarea:focus, .stTextInput input:focus { border-color: var(--accent) !important; }

div[data-testid="stDataFrame"] { border: 1px solid var(--border) !important; border-radius: 10px !important; }

.block-container { padding-top: 2.5rem; max-width: 900px; }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# --- session state init ---
if "step" not in st.session_state:
    st.session_state.step = 1
if "started" not in st.session_state:
    st.session_state.started = False
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
if "tailored_applications" not in st.session_state:
    st.session_state.tailored_applications = {}  # key: "title|||company" -> tailored dict
if "job_status" not in st.session_state:
    st.session_state.job_status = {}  # key -> {"interested": None/True/False, "cv_generated": bool, "applied": bool}
if "step4_phase" not in st.session_state:
    st.session_state.step4_phase = "review"  # "review" -> browse & mark interest | "selected" -> generate applications


def _job_key(job):
    # include adzuna_id when available (guaranteed unique), else fall back to
    # title+company+location — needed because the same role can legitimately
    # appear in multiple searched cities, which would otherwise collide.
    if job.get("adzuna_id"):
        return f"adzuna-{job['adzuna_id']}"
    return f"{job.get('title')}|||{job.get('company')}|||{job.get('location')}"


def _ensure_status(job_key):
    if job_key not in st.session_state.job_status:
        st.session_state.job_status[job_key] = {"interested": None, "cv_generated": False, "applied": False}
    return st.session_state.job_status[job_key]
if "tailored_application" not in st.session_state:
    st.session_state.tailored_application = None
if "application_log" not in st.session_state:
    st.session_state.application_log = []

st.title("Matchpoint")
st.caption("Your AI job-matching and application agent")

# --- landing screen: shown once, before the step flow starts ---
if not st.session_state.started:
    st.markdown(
        "<h2 style='margin-top:0.5rem;'>Stop guessing what fits. Start knowing.</h2>",
        unsafe_allow_html=True,
    )
    st.write(
        "Matchpoint gets to know you: your story, your strengths, what you value. "
        "Then it finds real roles that actually fit, and helps you apply."
    )
    st.write("")
    if st.button("Start →", type="primary"):
        st.session_state.started = True
        st.rerun()
    st.stop()

# --- step indicator: pill-style, colored for current/done ---
STEP_PILL_CSS = """
<style>
.mp-pill { display: inline-block; padding: 0.3rem 0.8rem; border-radius: 999px;
    font-size: 0.8rem; font-weight: 600; margin-right: 0.4rem; }
.mp-pill-current { background: var(--accent); color: white; }
.mp-pill-done { background: #EEF2FF; color: var(--accent); }
.mp-pill-todo { background: transparent; color: var(--muted); border: 1px solid var(--border); }
</style>
"""
st.markdown(STEP_PILL_CSS, unsafe_allow_html=True)

steps = ["Onboarding", "Your Story", "Strengths", "Values & Matches", "Dashboard"]
pills = []
for i, label in enumerate(steps, start=1):
    if i == st.session_state.step:
        pills.append(f'<span class="mp-pill mp-pill-current">{i}. {label}</span>')
    elif i < st.session_state.step:
        pills.append(f'<span class="mp-pill mp-pill-done">{i}. {label}</span>')
    else:
        pills.append(f'<span class="mp-pill mp-pill-todo">{i}. {label}</span>')
st.markdown(" ".join(pills), unsafe_allow_html=True)

st.divider()

# ============================================================
# STEP 1 — ONBOARDING
# ============================================================
if st.session_state.step == 1:
    st.header("Step 1: Tell us about yourself")
    st.write("Upload your documents so Matchpoint can build your profile.")

    col1, col2 = st.columns(2)
    with col1:
        cv_file = st.file_uploader("CV / Resume (required)", type=["pdf", "docx"])
        cover_letter_file = st.file_uploader(
            "Old cover letter (optional, used to capture your writing tone)",
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

        st.success("Profile built successfully")
        st.markdown(f"## {profile.get('name', 'Your profile')}")

        col_edu, col_exp = st.columns(2)
        with col_edu:
            st.markdown("**Education**")
            education = profile.get("education", [])
            if education:
                for edu in education:
                    st.markdown(f"**{edu.get('degree', '')}**")
                    st.caption(f"{edu.get('institution', '')} · {edu.get('dates', '')}")
            else:
                st.caption("Not found in documents")

        with col_exp:
            st.markdown("**Skills**")
            skills = profile.get("skills", [])
            st.write(", ".join(skills) if skills else "Not specified")
            st.markdown("**Certifications**")
            certs = profile.get("certifications", [])
            st.write(", ".join(certs) if certs else "None listed")

        st.markdown("**Experience**")
        experience = profile.get("experience", [])
        if experience:
            for exp in experience:
                with st.container(border=True):
                    st.markdown(f"**{exp.get('role', '')}**, {exp.get('company', '')}")
                    st.caption(exp.get("dates", ""))
                    for h in exp.get("highlights", []):
                        st.markdown(f"- {h}")
        else:
            st.caption("Not found in documents")

        with st.expander("Writing tone notes (used later to tailor cover letters)"):
            st.write(profile.get("writing_tone_notes", "Not enough data"))

        st.divider()

        # --- 1.b: always ask for interests — pre-fill from doc if already found ---
        if not profile.get("interests_clear", False):
            st.warning("Your documents don't clearly state what you're looking for next.")
        else:
            st.write("**We picked up on:**", ", ".join(profile.get("stated_interests", [])))

        interests_input = st.text_area(
            "Any industries, job titles, or preferences to add? (optional if we already found some above)",
            placeholder="e.g. strategy consulting, Business Analyst, sustainability, Product Manager, luxury retail...",
        )
        if st.button("Continue to Step 2 →", type="primary"):
            existing = profile.get("stated_interests", []) if profile.get("interests_clear") else []
            added = [i.strip() for i in interests_input.split(",") if i.strip()]
            st.session_state.profile["stated_interests"] = existing + added
            st.session_state.profile["interests_clear"] = True
            st.session_state.step = 2
            st.rerun()

# ============================================================
# STEP 2 — YOUR STORY
# ============================================================
elif st.session_state.step == 2:
    st.header("Step 2: Tell us about a moment you were at your best")
    st.write(
        "Think of a specific moment, at work, school, with friends, "
        "anywhere, when you felt genuinely proud of how you showed up."
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
            st.subheader("Let's find one together: answer what resonates")
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
            st.write(f"**Summary:** {analysis.get('summary', 'Not available')}")
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
    st.header("Step 3: Rate your strengths")

    default_strengths = ["Problem-solving", "Communication", "Leadership", "Adaptability", "Attention to detail"]
    strengths_list = st.session_state.story_analysis.get("suggested_strengths") or default_strengths

    if st.session_state.strengths_report is None:
        st.write("Rate yourself honestly on each, from 1 (not a strength) to 5 (clear strength).")

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

            st.subheader("Confirmed strengths")
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
                st.info("No major growth areas flagged from your ratings. Strong across the board.")

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
    st.header("Step 4: Your values, and your matches")

    VALUES_QUESTIONS = [
        "What matters most to you in your next role? (impact, learning, pay, flexibility, prestige...)",
        "What kind of work environment do you thrive in?",
        "Any industries or company types you'd love, or want to avoid?",
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

    # --- part B: show suggestions, allow override, then search REAL jobs via Adzuna ---
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

            # --- ground the suggestions in real LBS Career Centre outcomes data ---
            grounding_keywords = suggestions.get("suggested_industries", []) + suggestions.get("suggested_roles", [])
            real_offers = find_real_offers(grounding_keywords, limit=6)
            real_paths = find_career_paths(suggestions.get("suggested_industries", []), limit=3)
            stats = offers_summary_stats(grounding_keywords)

            if stats.get("count"):
                st.info(
                    f"Grounded in real outcomes: **{stats['count']} real LBS graduates (2023-2025)** "
                    f"went into similar roles — most often at "
                    f"{', '.join(stats.get('top_employers', [])[:3])}."
                )
                with st.expander("See real graduate placements & typical career paths"):
                    if real_offers:
                        st.write("**Real placements matching this profile:**")
                        for o in real_offers:
                            st.write(f"- {o.get('job_title') or 'Role'} at **{o.get('employer','')}**, {o.get('city','')} ({o.get('grad_year','')})")
                    if real_paths:
                        st.write("**Typical career path from here:**")
                        for p in real_paths:
                            st.write(f"- **{p.get('entry_role','')}** → {p.get('next_steps','')}")

            col_x, col_y = st.columns(2)
            with col_x:
                country_name = st.selectbox("Country to search in", list(COUNTRY_CODES.keys()))
            with col_y:
                cities_input = st.text_input(
                    "City or cities (optional, comma-separated)", placeholder="e.g. London, Paris"
                )
            cities = [c.strip() for c in cities_input.split(",") if c.strip()] or [""]

            col_a, col_b = st.columns([1, 1])
            with col_a:
                if st.button("This looks right → Find real matching jobs", type="primary"):
                    with st.spinner("Searching real job listings..."):
                        country_code = COUNTRY_CODES[country_name]
                        roles = suggestions.get("suggested_roles", []) or ["business analyst"]
                        # widen search with real employers who actually hired LBS grads
                        # into similar roles (grounds the search, not just the reasoning)
                        real_stats = offers_summary_stats(
                            suggestions.get("suggested_industries", []) + roles
                        )
                        roles = roles + real_stats.get("top_employers", [])[:3]
                        all_found, all_errors = [], []
                        seen_keys = set()

                        def _merge(found):
                            for job in found:
                                key = job.get("adzuna_id") or f"{job['title']}|||{job['company']}"
                                if key not in seen_keys:
                                    seen_keys.add(key)
                                    all_found.append(job)

                        for city in cities:
                            found, errs = search_multiple_roles(roles, country_code, where=city)
                            all_errors.extend(errs)
                            _merge(found)

                        # fallback: if specific role titles returned nothing, widen to
                        # the suggested industries, then to generic terms — a demo
                        # should never come back completely empty
                        if not all_found:
                            industries = suggestions.get("suggested_industries", [])
                            for city in cities:
                                found, errs = search_multiple_roles(industries, country_code, where=city)
                                all_errors.extend(errs)
                                _merge(found)
                        if not all_found:
                            for city in cities:
                                found, errs = search_multiple_roles(
                                    ["consultant", "analyst", "manager"], country_code, where=city
                                )
                                all_errors.extend(errs)
                                _merge(found)

                        if not all_found:
                            st.session_state.job_listings = []
                            st.session_state.last_search_errors = all_errors
                            st.warning("No real listings found for these roles/location. Try a broader city or fewer filters.")
                            if all_errors:
                                st.error(f"Adzuna error: {all_errors[0]}")
                        else:
                            st.session_state.job_listings = score_and_categorize_jobs(
                                all_found, st.session_state.profile, suggestions
                            )
                    st.rerun()
            with col_b:
                if st.button("I don't agree with this"):
                    st.session_state.override_mode = True

            if st.session_state.override_mode:
                st.divider()
                override_text = st.text_area(
                    "Tell us what you actually want instead, and we'll tailor the next steps for you.",
                    placeholder="e.g. I really want to do consulting, please focus there instead.",
                )
                if st.button("Update my suggestions →", type="primary", disabled=not override_text.strip()):
                    with st.spinner("Updating your suggestions..."):
                        st.session_state.suggestions = adjust_suggestions(
                            suggestions, override_text, st.session_state.profile
                        )
                        st.session_state.override_mode = False
                    st.rerun()

    # --- part C: two phases — review/select, then generate applications for selected only ---
    else:
        all_jobs = st.session_state.job_listings

        if not all_jobs:
            st.warning("No real listings found for that search.")
            errs = st.session_state.get("last_search_errors", [])
            if errs:
                st.error(f"Adzuna error: {errs[0]}")
            if st.button("← Try a different search"):
                st.session_state.job_listings = None
                st.rerun()

        # === PHASE 1: browse all jobs, mark interest only ===
        elif st.session_state.step4_phase == "review":
            st.subheader("Your matches")
            st.caption(f"{len(all_jobs)} jobs found. Mark what interests you, then move to the next step.")

            by_category = {}
            for job in all_jobs:
                by_category.setdefault(job.get("category", "Other"), []).append(job)

            category_order = ["Consulting", "Finance", "Tech", "Other"]
            ordered_cats = [c for c in category_order if c in by_category] + \
                           [c for c in by_category if c not in category_order]

            for cat in ordered_cats:
                jobs_in_cat = by_category[cat]
                with st.expander(f"**{cat}** ({len(jobs_in_cat)})", expanded=(cat == ordered_cats[0])):
                    for job in jobs_in_cat:
                        job_key = _job_key(job)
                        status = _ensure_status(job_key)
                        with st.container(border=True):
                            st.write(f"**{job.get('title')}**")
                            st.caption(f"{job.get('company')} · {job.get('location')}")
                            st.write(job.get("description", ""))
                            if job.get("apply_link") and job["apply_link"] != "#":
                                st.markdown(f"[View original listing]({job['apply_link']})")
                            st.progress(job.get("match_score", 0) / 100, text=f"Match: {job.get('match_score', 0)}%")
                            st.caption(job.get("match_reason", ""))

                            col_i1, col_i2 = st.columns([1, 1])
                            with col_i1:
                                if st.button(
                                    "Interested" if status["interested"] is not True else "Interested ✓",
                                    key=f"int_yes_{job_key}",
                                    type="primary" if status["interested"] is True else "secondary",
                                ):
                                    status["interested"] = True
                                    st.rerun()
                            with col_i2:
                                if st.button(
                                    "Not a fit" if status["interested"] is not False else "Not a fit ✓",
                                    key=f"int_no_{job_key}",
                                    type="primary" if status["interested"] is False else "secondary",
                                ):
                                    status["interested"] = False
                                    st.rerun()

            selected_count = sum(1 for j in all_jobs if st.session_state.job_status.get(_job_key(j), {}).get("interested") is True)
            st.divider()
            if selected_count > 0:
                if st.button(f"Continue with {selected_count} selected job(s)", type="primary"):
                    st.session_state.step4_phase = "selected"
                    st.rerun()
            else:
                st.info("Mark at least one job as Interested to continue.")

        # === PHASE 2: only selected jobs, generate CV & cover letter here ===
        else:
            selected_jobs = [j for j in all_jobs if st.session_state.job_status.get(_job_key(j), {}).get("interested") is True]

            st.subheader(f"Your {len(selected_jobs)} selected job(s)")
            if st.button("← Back to browse all jobs"):
                st.session_state.step4_phase = "review"
                st.rerun()

            for job in selected_jobs:
                job_key = _job_key(job)
                status = _ensure_status(job_key)
                with st.container(border=True):
                    st.write(f"**{job.get('title')}**")
                    st.caption(f"{job.get('company')} · {job.get('location')} · {job.get('category')}")
                    st.write(job.get("description", ""))
                    if job.get("apply_link") and job["apply_link"] != "#":
                        st.markdown(f"[View original listing]({job['apply_link']})")
                    st.progress(job.get("match_score", 0) / 100, text=f"Match: {job.get('match_score', 0)}%")

                    already_generated = job_key in st.session_state.tailored_applications

                    if not already_generated:
                        if st.button("Generate CV & Cover Letter →", key=f"gen_{job_key}"):
                            with st.spinner("Tailoring your CV and cover letter..."):
                                tailored = tailor_application(
                                    job, st.session_state.profile, st.session_state.story_analysis
                                )
                                entry = {"job": job, "tailored": tailored}
                                if "error" not in tailored:
                                    entry["cv_pdf"] = generate_cv_pdf(st.session_state.profile, tailored, job)
                                    entry["cl_pdf"] = generate_cover_letter_pdf(
                                        tailored.get("cover_letter", ""), st.session_state.profile, job
                                    )
                                    entry["keywords"] = suggest_cv_keywords(job, st.session_state.profile)
                                st.session_state.tailored_applications[job_key] = entry
                                status["cv_generated"] = True
                            st.rerun()
                    else:
                        entry = st.session_state.tailored_applications[job_key]
                        tailored = entry["tailored"]
                        st.success("Application generated")
                        if "error" in tailored:
                            st.error("Couldn't generate the tailored application automatically.")
                            st.code(tailored.get("raw_response", ""))
                        else:
                            col_a, col_b = st.columns(2)
                            with col_a:
                                st.write("**CV highlights**")
                                for h in tailored.get("cv_highlights", []):
                                    st.write(f"- {h}")
                                if "cv_pdf" in entry:
                                    st.download_button(
                                        "⬇ Download CV (PDF)", data=entry["cv_pdf"],
                                        file_name=f"CV_{job.get('company')}.pdf", mime="application/pdf",
                                        key=f"dl_cv_{job_key}",
                                    )
                            with col_b:
                                st.write("**Cover letter**")
                                st.text_area(
                                    "", value=tailored.get("cover_letter", ""),
                                    height=180, disabled=True, key=f"cl_{job_key}",
                                    label_visibility="collapsed",
                                )
                                if "cl_pdf" in entry:
                                    st.download_button(
                                        "⬇ Download Cover Letter (PDF)", data=entry["cl_pdf"],
                                        file_name=f"CoverLetter_{job.get('company')}.pdf", mime="application/pdf",
                                        key=f"dl_cl_{job_key}",
                                    )

                            kw_data = entry.get("keywords", {})
                            kw_list = kw_data.get("keywords", []) if "error" not in kw_data else []
                            if kw_list:
                                with st.expander("Keywords to work into your CV for this job"):
                                    for kw in kw_list:
                                        st.markdown(f"**{kw.get('keyword', '')}** (add to: {kw.get('where_to_place', '')})")
                                        syns = kw.get("synonyms", [])
                                        if syns:
                                            st.caption("Rephrasing ideas: " + ", ".join(syns))


                            if not status["applied"]:
                                if st.button("Mark as applied ✔", key=f"apply_{job_key}"):
                                    status["applied"] = True
                                    st.rerun()
                            else:
                                st.info("Marked as applied")

            st.divider()
            if st.button("Go to Dashboard →", type="primary"):
                st.session_state.step = 5
                st.rerun()

    if st.button("← Back to Step 3"):
        st.session_state.step = 3
        st.rerun()

# ============================================================
# STEP 5 — DASHBOARD
# ============================================================
elif st.session_state.step == 5:
    st.header("Your Dashboard")

    applications = st.session_state.tailored_applications
    all_jobs = st.session_state.job_listings or []

    interested_count = sum(1 for j in all_jobs if st.session_state.job_status.get(_job_key(j), {}).get("interested") is True)
    applied_count = sum(1 for s in st.session_state.job_status.values() if s.get("applied"))

    # --- top metrics ---
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Jobs reviewed", len(all_jobs))
    col2.metric("Interested", interested_count)
    col3.metric("CVs generated", len(applications))
    col4.metric("Applications sent", applied_count)

    st.divider()

    # --- match score chart, colored by category ---
    if all_jobs:
        df = pd.DataFrame(all_jobs)
        fig = px.bar(
            df, x="title", y="match_score", color="category",
            title="Match scores across reviewed jobs",
        )
        fig.update_layout(xaxis_title="", yaxis_title="Match %")
        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # --- full tracker table: every job reviewed, with its full status ---
    st.subheader("Application tracker")
    if all_jobs:
        def _status_icon(job):
            key = _job_key(job)
            s = st.session_state.job_status.get(key, {})
            interested = s.get("interested")
            interested_label = "Yes" if interested is True else ("No" if interested is False else "Not reviewed")
            return {
                "Title": job.get("title"),
                "Company": job.get("company"),
                "Category": job.get("category"),
                "Match": f"{job.get('match_score', 0)}%",
                "Interested": interested_label,
                "CV generated": "Yes" if s.get("cv_generated") else "Not yet",
                "Applied": "Sent" if s.get("applied") else "Not yet",
            }

        tracker_df = pd.DataFrame([_status_icon(j) for j in all_jobs])
        st.dataframe(tracker_df, use_container_width=True, hide_index=True)
    else:
        st.info("No jobs reviewed yet.")

    st.divider()

    # --- tailored CV + cover letter preview, one section per generated application ---
    if applications:
        st.subheader("Tailored applications")
        for job_key, entry in applications.items():
            job = entry["job"]
            tailored = entry["tailored"]
            applied = st.session_state.job_status.get(job_key, {}).get("applied", False)
            label = f"{job.get('title')}, {job.get('company')}{' (applied)' if applied else ''}"
            with st.expander(label):
                if job.get("apply_link") and job["apply_link"] != "#":
                    st.markdown(f"[View original listing]({job['apply_link']})")
                if "error" in tailored:
                    st.error("Couldn't generate the tailored application automatically.")
                    st.code(tailored.get("raw_response", ""))
                else:
                    col_a, col_b = st.columns(2)
                    with col_a:
                        st.write("**CV highlights**")
                        for h in tailored.get("cv_highlights", []):
                            st.write(f"- {h}")
                        if "cv_pdf" in entry:
                            st.download_button(
                                "⬇ Download CV (PDF)", data=entry["cv_pdf"],
                                file_name=f"CV_{job.get('company')}.pdf", mime="application/pdf",
                                key=f"dash_dl_cv_{job_key}",
                            )
                    with col_b:
                        st.write("**Cover letter**")
                        st.text_area(
                            "", value=tailored.get("cover_letter", ""), height=250,
                            disabled=True, key=f"dash_cl_{job_key}", label_visibility="collapsed",
                        )
                        if "cl_pdf" in entry:
                            st.download_button(
                                "⬇ Download Cover Letter (PDF)", data=entry["cl_pdf"],
                                file_name=f"CoverLetter_{job.get('company')}.pdf", mime="application/pdf",
                                key=f"dash_dl_cl_{job_key}",
                            )

                    kw_data = entry.get("keywords", {})
                    kw_list = kw_data.get("keywords", []) if "error" not in kw_data else []
                    if kw_list:
                        st.markdown("**Keywords to work into your CV**")
                        for kw in kw_list:
                            st.markdown(f"- **{kw.get('keyword', '')}** (add to: {kw.get('where_to_place', '')})")
                            syns = kw.get("synonyms", [])
                            if syns:
                                st.caption("Rephrasing ideas: " + ", ".join(syns))

    if st.button("← Back to Step 4"):
        st.session_state.step = 4
        st.rerun()
