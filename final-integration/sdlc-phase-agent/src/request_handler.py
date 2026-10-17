from dataclasses import asdict, dataclass
from datetime import datetime

from src.security import validate_description, validate_field


@dataclass
class FeatureRequest:
    id: int
    description: str
    client: str
    project: str
    timestamp: str
    phase: str = ""
    confidence: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


def create_request(next_id: int, description: str, client: str, project: str) -> FeatureRequest:
    """Validates and sanitizes user input; raises ValidationError (a ValueError) on bad input."""
    return FeatureRequest(
        id=next_id,
        description=validate_description(description),
        client=validate_field(client, "Client"),
        project=validate_field(project, "Project"),
        timestamp=datetime.now().isoformat(timespec="seconds"),
    )
