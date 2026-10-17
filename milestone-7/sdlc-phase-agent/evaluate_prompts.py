"""Compare the legacy and improved phase-detection prompts on a labeled sample set.

Usage: python3 evaluate_prompts.py   (writes a report to data/prompt_evaluation.txt)
"""
import json
from collections import Counter
from pathlib import Path

from src.phase_detector import PhaseDetectionError, build_phase_chain, detect_phase_detailed

ROOT = Path(__file__).resolve().parent
DATASET = ROOT / "data" / "labeled_requests.json"
REPORT = ROOT / "data" / "prompt_evaluation.txt"


def evaluate(version: str, samples: list[dict]) -> dict:
    chain = build_phase_chain(version)
    rows = []
    for s in samples:
        try:
            result = detect_phase_detailed(s["description"], chain)
        except PhaseDetectionError as e:
            result = {"phase": None, "confidence": 0.0, "structured": False, "raw": str(e)}
        rows.append({**s, **{f"pred_{k}": v for k, v in result.items()}})

    correct = [r for r in rows if r["pred_phase"] == r["phase"]]
    wrong = [r for r in rows if r["pred_phase"] != r["phase"]]

    def avg(items):
        return sum(r["pred_confidence"] for r in items) / len(items) if items else 0.0

    return {
        "rows": rows,
        "accuracy": len(correct) / len(rows),
        "structured_rate": sum(r["pred_structured"] for r in rows) / len(rows),
        "avg_conf_correct": avg(correct),
        "avg_conf_wrong": avg(wrong),
        "mistakes": Counter(f"{r['phase']} -> {r['pred_phase']}" for r in wrong),
    }


def format_report(results: dict[str, dict]) -> str:
    lines = ["Prompt evaluation", "=" * 60]
    lines.append(f"{'metric':<32}{'legacy':>12}{'improved':>12}")
    for key, label in [
        ("accuracy", "Accuracy"),
        ("structured_rate", "Structured output rate"),
        ("avg_conf_correct", "Avg confidence when correct"),
        ("avg_conf_wrong", "Avg confidence when wrong"),
    ]:
        lines.append(f"{label:<32}{results['legacy'][key]:>12.0%}{results['improved'][key]:>12.0%}")

    for version, res in results.items():
        lines.append(f"\nMistakes ({version}):")
        if not res["mistakes"]:
            lines.append("  none")
        for pattern, n in res["mistakes"].most_common():
            lines.append(f"  {pattern}: {n}")

    lines.append("\nPer-request results (expected | legacy | improved):")
    for old, new in zip(results["legacy"]["rows"], results["improved"]["rows"]):
        mark = lambda r: f"{r['pred_phase'] or 'error'} ({r['pred_confidence']:.2f})"
        lines.append(f"  {old['description'][:55]:<55} | {old['phase']:<14} | {mark(old):<22} | {mark(new)}")
    return "\n".join(lines)


def main() -> None:
    samples = json.loads(DATASET.read_text(encoding="utf-8"))
    results = {}
    for version in ("legacy", "improved"):
        print(f"Evaluating {version} prompt on {len(samples)} requests...")
        results[version] = evaluate(version, samples)
    report = format_report(results)
    REPORT.write_text(report + "\n", encoding="utf-8")
    print("\n" + report + f"\n\nReport saved to {REPORT}")


if __name__ == "__main__":
    main()
