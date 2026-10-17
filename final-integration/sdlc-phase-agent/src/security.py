"""Input validation, sanitization, rate limiting and simple abuse prevention."""
import os
import re
import threading
import time
import unicodedata
from collections import deque

MAX_RAW_INPUT_CHARS = 2000  # anything longer is rejected before any processing
DESCRIPTION_MIN, DESCRIPTION_MAX = 10, 500
FIELD_MAX = 100  # client / project names

RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "20"))
MAX_REQUESTS_PER_SESSION = int(os.getenv("MAX_REQUESTS_PER_SESSION", "50"))

_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b-\x1f\x7f\u200b-\u200f\u2028-\u202e]")
# Markup/templating characters that have no place in a feature description.
_UNSAFE_CHARS = re.compile(r"[<>{}`\\|$]")
_FIELD_ALLOWED = re.compile(r"[^\w\s.\-&()']")
_INJECTION_PATTERNS = re.compile(
    r"ignore (all |the )?(previous|above|prior) (instructions|prompts?)"
    r"|disregard (all |the )?(previous|above|prior)"
    r"|you are now|system prompt|reveal (your|the) (prompt|instructions)",
    re.IGNORECASE,
)


class ValidationError(ValueError):
    pass


class RateLimitError(RuntimeError):
    pass


def sanitize_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = _CONTROL_CHARS.sub(" ", text)
    text = _UNSAFE_CHARS.sub("", text)
    text = text.replace('"', "'")  # keeps the quoted request boundary in the LLM prompt intact
    return re.sub(r"\s+", " ", text).strip()


def validate_description(raw: str) -> str:
    if len(raw) > MAX_RAW_INPUT_CHARS:
        raise ValidationError(f"Input is too long ({len(raw)} characters; limit is {DESCRIPTION_MAX}).")
    if _INJECTION_PATTERNS.search(raw):
        raise ValidationError("Description looks like an instruction to the AI rather than a feature request.")
    text = sanitize_text(raw)
    if not DESCRIPTION_MIN <= len(text) <= DESCRIPTION_MAX:
        raise ValidationError(
            f"Description must be {DESCRIPTION_MIN}-{DESCRIPTION_MAX} characters after cleanup (got {len(text)})."
        )
    if not re.search(r"[A-Za-z]{2,}", text):
        raise ValidationError("Description must contain words.")
    return text


def validate_field(raw: str, name: str) -> str:
    if len(raw) > MAX_RAW_INPUT_CHARS:
        raise ValidationError(f"{name} is too long.")
    text = re.sub(r"\s+", " ", _FIELD_ALLOWED.sub("", sanitize_text(raw))).strip()
    if not text:
        raise ValidationError(f"{name} cannot be empty.")
    if len(text) > FIELD_MAX:
        raise ValidationError(f"{name} must be at most {FIELD_MAX} characters.")
    return text


class RateLimiter:
    """Sliding-window limiter: at most `max_calls` within `period` seconds."""

    def __init__(self, max_calls: int, period: float = 60.0) -> None:
        self.max_calls, self.period = max_calls, period
        self._calls: deque[float] = deque()
        self._lock = threading.Lock()

    def acquire(self) -> None:
        with self._lock:
            now = time.monotonic()
            while self._calls and now - self._calls[0] > self.period:
                self._calls.popleft()
            if len(self._calls) >= self.max_calls:
                wait = self.period - (now - self._calls[0])
                raise RateLimitError(f"Rate limit reached ({self.max_calls} AI calls/min). Try again in {wait:.0f}s.")
            self._calls.append(now)


# Shared by every LLM call in the process (phase detection and artifact generation).
llm_rate_limiter = RateLimiter(RATE_LIMIT_PER_MINUTE)


class SessionGuard:
    """Caps submissions per CLI session and blocks exact duplicates."""

    def __init__(self, max_requests: int = MAX_REQUESTS_PER_SESSION) -> None:
        self.max_requests = max_requests
        self.count = 0

    def check(self, description: str, existing_descriptions: list[str]) -> None:
        if self.count >= self.max_requests:
            raise ValidationError(f"Session limit of {self.max_requests} requests reached. Restart to continue.")
        normalized = description.casefold()
        if any(normalized == d.casefold() for d in existing_descriptions):
            raise ValidationError("An identical request already exists.")

    def record(self) -> None:
        self.count += 1
