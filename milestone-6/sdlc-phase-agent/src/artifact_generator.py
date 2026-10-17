import re
from datetime import date
from pathlib import Path

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from openai import OpenAIError

from src.phase_detector import PhaseDetectionError, build_llm

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = ROOT / "templates"
ARTIFACTS_DIR = ROOT / "artifacts"

# phase -> (template placeholder filled by the LLM, what to ask the LLM for)
SECTIONS = {
    "requirements": ("basic_requirements", "5 short, testable requirements as markdown bullets"),
    "design": ("design_outline", "a basic design outline: components, data, and interfaces as nested markdown bullets"),
    "implementation": ("task_list", "6 implementation tasks as a markdown checklist ('- [ ] ...')"),
    "testing": ("test_cases", "4 test cases, each as '- **TC-n**: steps -> expected result'"),
    "deployment": ("checklist", "8 deployment steps as a markdown checklist ('- [ ] ...')"),
}

FALLBACK = "- [ ] TODO: fill in manually (automatic content generation was unavailable)"

CONTENT_PROMPT = PromptTemplate.from_template(
    """You are helping a software team document a feature request.

Feature request: "{description}"
Client: {client}
Project: {project}

Write {what}. Output only the markdown, with no heading or commentary."""
)


def load_template(phase: str) -> str:
    return (TEMPLATES_DIR / f"{phase}.md").read_text(encoding="utf-8")


def generate_content(phase: str, request: dict) -> str:
    _, what = SECTIONS[phase]
    try:
        chain = CONTENT_PROMPT | build_llm(max_tokens=1500) | StrOutputParser()
        text = chain.invoke({**request, "what": what}).strip()
    except (PhaseDetectionError, OpenAIError):
        return FALLBACK
    return text or FALLBACK


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "general"


def generate_artifact(phase: str, request: dict) -> Path:
    """request needs: id, description, client, project."""
    if phase not in SECTIONS:
        raise ValueError(f"Unknown phase: {phase}")
    placeholder, _ = SECTIONS[phase]
    description = request["description"]
    document = load_template(phase).format(
        feature_name=description if len(description) <= 60 else description[:57] + "...",
        date=date.today().isoformat(),
        description=description,
        client=request["client"],
        project=request["project"],
        **{placeholder: generate_content(phase, request)},
    )
    path = ARTIFACTS_DIR / _slug(request["project"]) / phase / f"request-{request['id']}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(document, encoding="utf-8")
    return path
