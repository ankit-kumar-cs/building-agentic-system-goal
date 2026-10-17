from dataclasses import dataclass, asdict
from datetime import datetime

MIN_LEN = 10
MAX_LEN = 500


@dataclass
class FeatureRequest:
    id: int
    description: str
    client: str
    project: str
    timestamp: str

    def to_dict(self) -> dict:
        return asdict(self)


def validate_description(description: str) -> str:
    description = description.strip()
    if not MIN_LEN <= len(description) <= MAX_LEN:
        raise ValueError(
            f"Description must be {MIN_LEN}-{MAX_LEN} characters (got {len(description)})."
        )
    return description


def validate_required(value: str, field: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError(f"{field} cannot be empty.")
    return value


def create_request(next_id: int, description: str, client: str, project: str) -> FeatureRequest:
    return FeatureRequest(
        id=next_id,
        description=validate_description(description),
        client=validate_required(client, "Client"),
        project=validate_required(project, "Project"),
        timestamp=datetime.now().isoformat(timespec="seconds"),
    )
