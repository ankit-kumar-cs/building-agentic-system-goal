"""Adapt step: user corrections are stored and fed back into the prompt as extra examples."""
import json
from datetime import datetime
from pathlib import Path

CORRECTIONS_FILE = Path(__file__).resolve().parent.parent / "data" / "corrections.json"
MAX_LEARNED_EXAMPLES = 5


def load_corrections() -> list[dict]:
    if not CORRECTIONS_FILE.exists():
        return []
    try:
        data = json.loads(CORRECTIONS_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


def add_correction(description: str, predicted: str | None, corrected: str) -> None:
    corrections = load_corrections()
    corrections.append({
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "description": description,
        "predicted": predicted,
        "corrected": corrected,
    })
    CORRECTIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    CORRECTIONS_FILE.write_text(json.dumps(corrections, indent=2), encoding="utf-8")


def learned_examples_text() -> str:
    """Most recent corrections formatted as extra few-shot examples (empty string if none)."""
    recent = load_corrections()[-MAX_LEARNED_EXAMPLES:]
    return "".join(f'- "{c["description"]}" -> {c["corrected"]},0.9\n' for c in recent)
