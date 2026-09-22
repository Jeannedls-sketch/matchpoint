"""
Wrapper around the Anthropic API for Matchpoint's onboarding step.

Step 1 job: read the candidate's documents (CV, cover letter, transcripts,
recommendation letter, certifications) and produce a structured profile.
If interests aren't clear from the documents, flag it so the app can ask
the user directly (step 1.b in the project plan).
"""

import os
import json
from anthropic import Anthropic

MODEL = "claude-sonnet-4-5"

_client = None


def get_client():
    global _client
    if _client is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY not set. Add it to your .env file or environment."
            )
        _client = Anthropic(api_key=api_key)
    return _client


def build_profile_from_documents(documents: dict, writing_sample: str = "") -> dict:
    """
    documents: dict of {doc_type: extracted_text}, e.g.
        {"cv": "...", "transcripts": "...", "recommendation_letter": "...", "certifications": "..."}
    writing_sample: text of an old cover letter, used only to capture tone,
        not content (per the project plan).

    Returns a dict with keys:
        - name, education, experience, skills, certifications (structured facts)
        - interests_clear (bool)
        - stated_interests (list[str] or empty)
        - writing_tone_notes (str) - short description of the candidate's
          writing style, to reuse later when tailoring cover letters
    """
    client = get_client()

    docs_block = "\n\n".join(
        f"### {doc_type.upper()}\n{text}" for doc_type, text in documents.items()
    )

    system_prompt = """You are an onboarding assistant for Matchpoint, a career-matching tool.
Read the candidate's uploaded documents and extract a structured profile.

Respond ONLY with valid JSON (no markdown fences, no preamble), matching this schema:
{
  "name": string,
  "education": [{"institution": string, "degree": string, "dates": string}],
  "experience": [{"company": string, "role": string, "dates": string, "highlights": [string]}],
  "skills": [string],
  "certifications": [string],
  "interests_clear": boolean,
  "stated_interests": [string],
  "writing_tone_notes": string
}

"interests_clear" should be false if the documents don't explicitly state what
industries, roles, or types of work the candidate is interested in pursuing next
(a CV listing past jobs is NOT the same as stated interest in future roles).
"writing_tone_notes" should briefly describe tone/style (e.g. "concise, formal,
avoids first-person adjectives") based on the writing sample if provided, else
based on the cover letter in the documents if present, else "not enough data"."""

    user_content = f"# CANDIDATE DOCUMENTS\n\n{docs_block}"
    if writing_sample:
        user_content += f"\n\n### WRITING SAMPLE (for tone only, ignore content)\n{writing_sample}"

    response = client.messages.create(
        model=MODEL,
        max_tokens=2000,
        system=system_prompt,
        messages=[{"role": "user", "content": user_content}],
    )

    raw_text = response.content[0].text.strip()
    # defensive: strip accidental markdown fences
    if raw_text.startswith("```"):
        raw_text = raw_text.strip("`")
        if raw_text.startswith("json"):
            raw_text = raw_text[4:]

    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        return {
            "error": "Could not parse model response as JSON",
            "raw_response": raw_text,
        }


def _call_json(system_prompt: str, user_content: str, max_tokens: int = 1500) -> dict:
    """Shared helper: call Claude, expect JSON back, parse it defensively."""
    client = get_client()
    response = client.messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        system=system_prompt,
        messages=[{"role": "user", "content": user_content}],
    )
    raw_text = response.content[0].text.strip()
    if raw_text.startswith("```"):
        raw_text = raw_text.strip("`")
        if raw_text.startswith("json"):
            raw_text = raw_text[4:]
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        return {"error": "Could not parse model response as JSON", "raw_response": raw_text}


def generate_backup_questions(profile: dict) -> list:
    """
    Step 2 (when the user can't think of a 'best self' story on their own):
    generate 4-5 guided backup questions, personalized using their profile,
    to help them find a moment to talk about.

    Returns a list of question strings.
    """
    system_prompt = """You help candidates who are stuck finding a "moment when I was at my best"
to tell for a career-matching tool. Generate 4-5 short, warm, guided backup
questions that help them locate a specific memory - not generic prompts, but
questions that nudge toward concrete moments (a project, a challenge overcome,
a time they helped someone, a skill they used well).

Personalize lightly using their background (education/experience) if relevant,
but keep questions broadly answerable even if they draw a blank on work life
(e.g. school, sports, family, volunteering all count).

Respond ONLY with valid JSON: {"questions": [string, string, ...]}"""

    user_content = f"Candidate background:\n{json.dumps(profile, ensure_ascii=False)}"
    result = _call_json(system_prompt, user_content)
    return result.get("questions", []) if "error" not in result else []


def analyze_story(story_text: str, profile: dict) -> dict:
    """
    Step 2 output: analyze the candidate's "best self" story (whether they
    wrote it directly or answered backup questions) and extract traits/strengths
    to carry into Step 3.

    Returns a dict:
        {
            "summary": short paraphrase of the story,
            "traits": [string],       # e.g. "resilience", "attention to detail"
            "suggested_strengths": [string]  # to pre-fill step 3's rating list
        }
    """
    system_prompt = """You are a career coach analyzing a candidate's story about a moment
they were at their best, for a career-matching tool.

Read the story and extract:
- a short (1-2 sentence) neutral summary of what happened
- a list of underlying traits/soft skills demonstrated (e.g. "resilience",
  "collaborative leadership", "analytical thinking") - 3 to 6 traits
- a list of concrete strengths worth rating in the next step (short labels,
  e.g. "Problem-solving", "Communication", "Initiative") - 4 to 8 items

Respond ONLY with valid JSON:
{"summary": string, "traits": [string], "suggested_strengths": [string]}"""

    user_content = f"Candidate background:\n{json.dumps(profile, ensure_ascii=False)}\n\nTheir story:\n{story_text}"
    return _call_json(system_prompt, user_content)


def generate_strengths_report(ratings: dict, profile: dict, story_analysis: dict) -> dict:
    """
    Step 3: given the candidate's 1-5 self-ratings on a list of strengths,
    generate a short report. Low ratings (<=2) become candidate "growth areas"
    (framed constructively, not as "weaknesses" bluntly); high ratings (>=4)
    are confirmed as core strengths. If everything is rated high, growth_areas
    can be an empty list - that's a valid outcome, not an error.

    ratings: dict of {strength_label: int (1-5)}

    Returns:
        {
            "confirmed_strengths": [string],
            "growth_areas": [{"area": string, "note": string}],
            "narrative": string   # 2-3 sentence overview tying it together
        }
    """
    system_prompt = """You are a career coach reviewing a candidate's self-ratings (1-5 scale,
5 = very strong) on a set of strengths, in the context of their background and
a story they told about a moment they were at their best.

Produce:
- "confirmed_strengths": labels rated 4-5, framed as genuine strengths
- "growth_areas": labels rated 1-2, each with a short constructive "note"
  (never harsh, framed as development opportunities, not deficiencies).
  If nothing was rated 1-2, return an empty list - do not invent weaknesses.
- "narrative": 2-3 warm, honest sentences tying the ratings together in the
  context of their story and background.

Respond ONLY with valid JSON:
{"confirmed_strengths": [string], "growth_areas": [{"area": string, "note": string}], "narrative": string}"""

    user_content = (
        f"Candidate background:\n{json.dumps(profile, ensure_ascii=False)}\n\n"
        f"Their story summary: {story_analysis.get('summary', '')}\n\n"
        f"Self-ratings (1-5):\n{json.dumps(ratings, ensure_ascii=False)}"
    )
    return _call_json(system_prompt, user_content)
