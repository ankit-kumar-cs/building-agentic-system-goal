import re
from collections import Counter
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from src import storage

KEYWORDS = ["login", "database", "test", "payment", "user", "customer", "report", "api"]
STOP_WORDS = {"a", "an", "the", "to", "of", "and", "for", "in", "on", "is", "this", "with", "add", "create"}
CHART_PATH = Path(__file__).resolve().parent.parent / "data" / "keyword_chart.png"


def load_dataframe() -> pd.DataFrame:
    return pd.DataFrame(
        storage.load_requests(),
        columns=["id", "description", "client", "project", "timestamp"],
    )


def keyword_counts(df: pd.DataFrame) -> dict[str, int]:
    text = df["description"].str.lower()
    return {k: int(text.str.contains(rf"\b{k}", regex=True).sum()) for k in KEYWORDS}


def word_frequency(df: pd.DataFrame, top: int = 10) -> list[tuple[str, int]]:
    words = []
    for desc in df["description"]:
        words += [w for w in re.findall(r"[a-z]+", desc.lower()) if w not in STOP_WORDS and len(w) > 2]
    return Counter(words).most_common(top)


def compute_stats(df: pd.DataFrame) -> dict:
    lengths = df["description"].str.len()
    return {
        "total": len(df),
        "avg_length": round(float(lengths.mean()), 1) if len(df) else 0.0,
    }


def save_chart(counts: dict[str, int], path: Path = CHART_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(list(counts.keys()), list(counts.values()), color="steelblue")
    ax.set_title("Requests by Keyword")
    ax.set_ylabel("Count")
    ax.yaxis.get_major_locator().set_params(integer=True)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path


def run_analytics() -> None:
    df = load_dataframe()
    if df.empty:
        print("No requests to analyze.")
        return
    stats = compute_stats(df)
    counts = keyword_counts(df)
    print(f"\nTotal requests:        {stats['total']}")
    print(f"Average length (chars): {stats['avg_length']}")
    print("\nKeyword counts:")
    for k, v in counts.items():
        print(f"  {k:<10} {'#' * v} {v}")
    print("\nTop words:")
    for w, c in word_frequency(df):
        print(f"  {w:<12} {c}")
    print(f"\nChart saved to: {save_chart(counts)}")
