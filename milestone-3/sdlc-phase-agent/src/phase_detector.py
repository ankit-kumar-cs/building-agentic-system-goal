import math
import os
import re

from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI, OpenAIError

_SRC_DIR = Path(__file__).resolve().parent
load_dotenv(_SRC_DIR.parent / ".env")
load_dotenv(_SRC_DIR / ".env")

PHASES = ["requirements", "design", "implementation", "testing", "deployment"]
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
USE_LOGPROBS = os.getenv("USE_LOGPROBS", "true").lower() == "true"

PROMPT_TEMPLATE = """Classify this feature request into one SDLC phase:

"{description}"

Phases: requirements, design, implementation, testing, deployment

Respond with just: phase_name"""

# Used when the provider has no logprobs support.
SELF_REPORT_SUFFIX = "\nThen add a comma and your confidence from 0 to 1, e.g.: testing, 0.9"


class PhaseDetectionError(Exception):
    pass


def _get_client() -> OpenAI:
    if not os.getenv("OPENAI_API_KEY"):
        raise PhaseDetectionError("OPENAI_API_KEY is not set (see .env.example).")
    return OpenAI(timeout=30, max_retries=2)


def parse_phase(text: str) -> str | None:
    text = text.strip().lower()
    return next((p for p in PHASES if p in text), None)


def _estimate_confidence(choice, phase: str) -> float:
    """Probability mass on the first token(s) of the chosen phase, from logprobs."""
    try:
        first = choice.logprobs.content[0]
    except (AttributeError, IndexError, TypeError):
        return 0.0
    total = sum(
        math.exp(t.logprob)
        for t in first.top_logprobs
        if t.token.strip().lower() and phase.startswith(t.token.strip().lower())
    )
    return round(min(total, 1.0), 2)


def _parse_self_reported(text: str) -> float:
    match = re.search(r"\d*\.?\d+", text.split(",", 1)[1]) if "," in text else None
    return round(min(float(match.group()), 1.0), 2) if match else 0.0


def confidence_label(score: float) -> str:
    if score >= 0.8:
        return "high"
    if score >= 0.5:
        return "medium"
    return "low"


def detect_phase(description: str, client: OpenAI | None = None) -> tuple[str, float]:
    client = client or _get_client()
    prompt = PROMPT_TEMPLATE.format(description=description)
    extra = {"logprobs": True, "top_logprobs": 5} if USE_LOGPROBS else {}
    if not USE_LOGPROBS:
        prompt += SELF_REPORT_SUFFIX
    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=512,  # reasoning models spend tokens thinking before answering
            **extra,
        )
    except OpenAIError as e:
        raise PhaseDetectionError(f"OpenAI API error: {e}") from e

    choice = response.choices[0]
    phase = parse_phase(choice.message.content or "")
    if phase is None:
        raise PhaseDetectionError(f"Unrecognized phase in response: {choice.message.content!r}")
    confidence = (
        _estimate_confidence(choice, phase)
        if USE_LOGPROBS
        else _parse_self_reported(choice.message.content or "")
    )
    return phase, confidence
