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

# Milestone 3-6 prompt, kept so evaluate_prompts.py can compare old vs new.
LEGACY_TEMPLATE = """Classify this feature request into one SDLC phase:

"{description}"

Phases: requirements, design, implementation, testing, deployment

Respond with just: phase_name
Then add a comma and your confidence from 0 to 1, e.g.: testing, 0.9"""

IMPROVED_TEMPLATE = """You are an SDLC analyst. Classify the feature request into exactly ONE phase:
the phase the team should work on NEXT for this request.

Phases:
- requirements: a new need or idea that still has to be defined (what users need, scope, acceptance criteria). Wishes like "we need X" or "add X" with no detail belong here.
- design: planning HOW to build something before coding: architecture, data models, database schemas, UI mockups, API contracts.
- implementation: writing, changing, or fixing code for something already defined; bug fixes and refactoring.
- testing: verifying behaviour: test cases, QA, load/performance tests, security audits, UAT.
- deployment: releasing or operating software: production releases, CI/CD pipelines, servers, rollbacks, migrations to new infrastructure.

Examples:
- "We need user login" -> requirements,0.9
- "Customers want to export their invoices" -> requirements,0.85
- "Plan the database structure for orders" -> design,0.9
- "Create wireframes for the checkout page" -> design,0.85
- "Write the REST API endpoint for user signup" -> implementation,0.9
- "Fix the bug where the cart total is wrong" -> implementation,0.9
- "Write unit tests for the payment module" -> testing,0.95
- "Run a load test with 10k concurrent users" -> testing,0.9
- "Release version 2.1 to production" -> deployment,0.95
- "Set up a CI/CD pipeline for the backend" -> deployment,0.85

Rules:
- If the request is vague or only states a need, choose requirements.
- Confidence is a number from 0 to 1: lower it when the request could fit several phases.

Request: "{description}"

Respond with exactly one line in the format: phase_name,confidence"""

PROMPTS = {
    "legacy": PromptTemplate.from_template(LEGACY_TEMPLATE),
    "improved": PromptTemplate.from_template(IMPROVED_TEMPLATE),
}

_STRUCTURED = re.compile(rf"^\s*({'|'.join(PHASES)})\s*,\s*(\d*\.?\d+)\s*$", re.IGNORECASE)


class PhaseDetectionError(Exception):
    pass


def build_llm(max_tokens: int = 512, **kwargs) -> ChatOpenAI:
    if not os.getenv("OPENAI_API_KEY"):
        raise PhaseDetectionError("OPENAI_API_KEY is not set (see .env.example).")
    return ChatOpenAI(
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        base_url=os.getenv("OPENAI_BASE_URL") or None,
        temperature=0,
        max_tokens=max_tokens,  # reasoning models spend tokens thinking before answering
        timeout=60,
        max_retries=2,
        **kwargs,
    )


def build_phase_chain(version: str = "improved"):
    extra = {"logprobs": True, "top_logprobs": 5} if USE_LOGPROBS else {}
    return PROMPTS[version] | build_llm(**extra)


def parse_response(text: str) -> tuple[str | None, float | None, bool]:
    """Returns (phase, self-reported confidence, whether the reply matched the structured format)."""
    match = _STRUCTURED.match(text)
    if match:
        return match.group(1).lower(), round(min(float(match.group(2)), 1.0), 2), True
    # Fallback for free-form replies: earliest phase name mentioned wins.
    lowered = text.lower()
    found = sorted((lowered.find(p), p) for p in PHASES if p in lowered)
    number = re.search(r"\b(0?\.\d+|1(?:\.0+)?)\b", lowered)
    return (found[0][1] if found else None), (float(number.group()) if number else None), False


def _logprob_confidence(message, phase: str) -> float | None:
    try:
        first = message.response_metadata["logprobs"]["content"][0]
    except (KeyError, IndexError, TypeError):
        return None
    total = sum(
        math.exp(t["logprob"])
        for t in first["top_logprobs"]
        if t["token"].strip() and phase.startswith(t["token"].strip().lower())
    )
    return round(min(total, 1.0), 2)


def confidence_label(score: float) -> str:
    if score >= 0.8:
        return "high"
    if score >= 0.5:
        return "medium"
    return "low"


def detect_phase_detailed(description: str, chain=None) -> dict:
    chain = chain or build_phase_chain()
    try:
        message = chain.invoke({"description": description})
    except OpenAIError as e:
        raise PhaseDetectionError(f"LLM API error: {e}") from e

    text = (message.content or "").strip()
    phase, reported, structured = parse_response(text)
    if phase is None:
        raise PhaseDetectionError(f"Unrecognized phase in response: {text!r}")
    confidence = (_logprob_confidence(message, phase) if USE_LOGPROBS else None) or reported or 0.0
    return {"phase": phase, "confidence": confidence, "structured": structured, "raw": text}


def detect_phase(description: str, chain=None) -> tuple[str, float]:
    result = detect_phase_detailed(description, chain)
    return result["phase"], result["confidence"]
