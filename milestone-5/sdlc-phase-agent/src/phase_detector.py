import math
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from openai import OpenAIError

_SRC_DIR = Path(__file__).resolve().parent
load_dotenv(_SRC_DIR.parent / ".env")
load_dotenv(_SRC_DIR / ".env")

PHASES = ["requirements", "design", "implementation", "testing", "deployment"]
USE_LOGPROBS = os.getenv("USE_LOGPROBS", "true").lower() == "true"

_BASE_TEMPLATE = """Classify this feature request into one SDLC phase:

"{description}"

Phases: requirements, design, implementation, testing, deployment

Respond with just: phase_name"""

# Providers without logprobs support report confidence in the reply instead.
_SELF_REPORT = "\nThen add a comma and your confidence from 0 to 1, e.g.: testing, 0.9"

PHASE_PROMPT = PromptTemplate.from_template(_BASE_TEMPLATE + ("" if USE_LOGPROBS else _SELF_REPORT))


class PhaseDetectionError(Exception):
    pass


def build_phase_chain():
    if not os.getenv("OPENAI_API_KEY"):
        raise PhaseDetectionError("OPENAI_API_KEY is not set (see .env.example).")
    llm = ChatOpenAI(
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        base_url=os.getenv("OPENAI_BASE_URL") or None,
        temperature=0,
        max_tokens=512,  # reasoning models spend tokens thinking before answering
        timeout=30,
        max_retries=2,
        **({"logprobs": True, "top_logprobs": 5} if USE_LOGPROBS else {}),
    )
    return PHASE_PROMPT | llm


def parse_phase(text: str) -> str | None:
    text = text.strip().lower()
    return next((p for p in PHASES if p in text), None)


def _logprob_confidence(message, phase: str) -> float:
    try:
        first = message.response_metadata["logprobs"]["content"][0]
    except (KeyError, IndexError, TypeError):
        return 0.0
    total = sum(
        math.exp(t["logprob"])
        for t in first["top_logprobs"]
        if t["token"].strip() and phase.startswith(t["token"].strip().lower())
    )
    return round(min(total, 1.0), 2)


def _self_reported_confidence(text: str) -> float:
    match = re.search(r"\d*\.?\d+", text.split(",", 1)[1]) if "," in text else None
    return round(min(float(match.group()), 1.0), 2) if match else 0.0


def confidence_label(score: float) -> str:
    if score >= 0.8:
        return "high"
    if score >= 0.5:
        return "medium"
    return "low"


def detect_phase(description: str, chain=None) -> tuple[str, float]:
    chain = chain or build_phase_chain()
    try:
        message = chain.invoke({"description": description})
    except OpenAIError as e:
        raise PhaseDetectionError(f"LLM API error: {e}") from e

    text = message.content or ""
    phase = parse_phase(text)
    if phase is None:
        raise PhaseDetectionError(f"Unrecognized phase in response: {text!r}")
    confidence = _logprob_confidence(message, phase) if USE_LOGPROBS else _self_reported_confidence(text)
    return phase, confidence
