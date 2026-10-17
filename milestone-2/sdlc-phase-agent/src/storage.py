import json
import os
from pathlib import Path

from src.request_handler import FeatureRequest

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "data" / "requests.json"


def _path() -> Path:
    return Path(os.getenv("REQUESTS_FILE", DEFAULT_PATH))


def load_requests() -> list[dict]:
    path = _path()
    if not path.exists() or path.stat().st_size == 0:
        return []
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Storage file {path} is corrupted: {e}") from e
    if not isinstance(data, list):
        raise RuntimeError(f"Storage file {path} has unexpected format.")
    return data


def next_id() -> int:
    return max((r["id"] for r in load_requests()), default=0) + 1


def append_request(request: FeatureRequest) -> None:
    requests = load_requests()
    requests.append(request.to_dict())
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(requests, f, indent=2)
