import json
import logging
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = ROOT / "logs"
INTERACTIONS_LOG = LOG_DIR / "interactions.log"
ERRORS_LOG = LOG_DIR / "errors.log"
EVAL_SUMMARY = ROOT / "data" / "prompt_evaluation.json"

LOG_DIR.mkdir(exist_ok=True)

_error_logger = logging.getLogger("sdlc_agent.errors")
if not _error_logger.handlers:
    _handler = logging.FileHandler(ERRORS_LOG, encoding="utf-8")
    _handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s"))
    _error_logger.addHandler(_handler)
    _error_logger.setLevel(logging.WARNING)
    _error_logger.propagate = False


def log_error(source: str, message: str) -> None:
    _error_logger.error("%s: %s", source, message)


def log_interaction(interaction, duration_ms: float) -> None:
    """Append one interaction as a JSON line to logs/interactions.log."""
    obs, reasoning, response = interaction.observations, interaction.reasoning, interaction.response
    record = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "request_id": obs.get("id"),
        "project": obs.get("project"),
        "description": obs["description"][:200],
        "success": reasoning["phase"] is not None,
        "phase": reasoning["phase"],
        "confidence": reasoning["confidence"],
        "structured_output": reasoning.get("structured"),
        "llm_ms": reasoning.get("llm_ms"),
        "duration_ms": round(duration_ms),
        "artifact_path": response.get("artifact_path"),
        "error": reasoning.get("error") or response.get("artifact_error"),
    }
    with INTERACTIONS_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
    if record["error"]:
        log_error("agent", f"request {record['request_id']}: {record['error']}")


def load_interactions() -> list[dict]:
    if not INTERACTIONS_LOG.exists():
        return []
    records = []
    for line in INTERACTIONS_LOG.read_text(encoding="utf-8").splitlines():
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue  # skip a partially written line rather than failing the dashboard
    return records


def compute_metrics(records: list[dict]) -> dict:
    successes = [r for r in records if r["success"]]
    confidences = [r["confidence"] for r in successes]
    durations = [r["duration_ms"] for r in records if r.get("duration_ms") is not None]
    structured = [r for r in successes if r.get("structured_output") is not None]
    eval_accuracy = None
    if EVAL_SUMMARY.exists():
        eval_accuracy = json.loads(EVAL_SUMMARY.read_text(encoding="utf-8")).get("improved_accuracy")
    return {
        "total": len(records),
        "successes": len(successes),
        "failures": len(records) - len(successes),
        "success_rate": len(successes) / len(records) if records else 0.0,
        "phase_counts": Counter(r["phase"] for r in successes).most_common(),
        "avg_duration_ms": sum(durations) / len(durations) if durations else 0.0,
        "avg_confidence": sum(confidences) / len(confidences) if confidences else 0.0,
        "low_confidence": sum(c < 0.5 for c in confidences),
        "structured_rate": sum(r["structured_output"] for r in structured) / len(structured) if structured else None,
        "eval_accuracy": eval_accuracy,
        "recent_errors": [r for r in records if r.get("error")][-5:],
    }


def format_dashboard(m: dict) -> str:
    if not m["total"]:
        return "No interactions logged yet."
    lines = [
        "=== Agent Statistics ===",
        f"Total interactions:     {m['total']}",
        f"Successful / failed:    {m['successes']} / {m['failures']}",
        f"Success rate:           {m['success_rate']:.0%}",
        f"Average response time:  {m['avg_duration_ms'] / 1000:.2f}s",
        "",
        "Most detected phases:",
    ]
    lines += [f"  {phase:<15} {'#' * n} {n}" for phase, n in m["phase_counts"]] or ["  none"]
    lines += ["", "Accuracy estimation:"]
    lines.append(f"  Average confidence:   {m['avg_confidence']:.0%}")
    lines.append(f"  Low-confidence (<50%): {m['low_confidence']}")
    if m["structured_rate"] is not None:
        lines.append(f"  Structured replies:   {m['structured_rate']:.0%}")
    if m["eval_accuracy"] is not None:
        lines.append(f"  Labeled-set accuracy: {m['eval_accuracy']:.0%} (from evaluate_prompts.py)")
    lines += ["", "Recent errors:"]
    lines += [f"  [{r['timestamp']}] #{r['request_id']}: {r['error'][:100]}" for r in m["recent_errors"]] or ["  none"]
    lines.append(f"\nLogs: {INTERACTIONS_LOG}  |  {ERRORS_LOG}")
    return "\n".join(lines)
