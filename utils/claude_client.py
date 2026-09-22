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
