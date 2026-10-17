"""SDLC Phase-Aware Agent - command line interface. Run: python3 main.py"""
import warnings
from pathlib import Path

from src import monitoring, storage
from src.agent import Interaction, SimpleAgent
from src.analytics import run_analytics
from src.phase_detector import PHASES
from src.request_handler import create_request
from src.security import SessionGuard, ValidationError

# InMemoryChatMessageHistory still works; hide its deprecation notice from end users.
# Must run after the imports above, because LangChain resets its warning filters on import.
warnings.filterwarnings("ignore", message=".*InMemoryChatMessageHistory.*")

ROOT = Path(__file__).resolve().parent
agent = SimpleAgent()
guard = SessionGuard()

BANNER = """
+--------------------------------------------------+
|           SDLC Phase-Aware Agent                 |
|   Observe -> Reason -> Act -> Adapt              |
+--------------------------------------------------+"""

MENU = """
1. Submit a feature request
2. View requests
3. Classify unclassified requests
4. Ask the agent a follow-up
5. Request analytics (chart)
6. Agent statistics
7. Help
8. Exit"""

HELP = """
HOW IT WORKS
  Submit a feature request (option 1). The agent will:
    Observe  - read the request and recall the previous one
    Reason   - ask the AI which SDLC phase it belongs to, with a confidence score
    Act      - give advice and write a document for that phase under artifacts/
    Adapt    - if confidence is below 70%, you confirm or correct the phase;
               corrections become examples that improve future answers

PHASES
  requirements    a need that still has to be defined     -> requirements document
  design          planning how to build it                -> design outline
  implementation  writing or fixing code                  -> task list
  testing         verifying behaviour                     -> test plan
  deployment      releasing / operating software          -> deployment checklist

INPUT RULES
  Description 10-500 characters; client/project up to 100 characters.
  Characters like < > { } ` $ are removed. Duplicate requests are rejected.
  AI calls are rate limited (see RATE_LIMIT_PER_MINUTE in .env).

OTHER OPTIONS
  2 lists stored requests, 3 classifies requests saved without a phase,
  4 answers "why?" about the last request, 5 builds a keyword chart,
  6 shows success rate, response time, phases and recent errors.

FILES
  data/requests.json   stored requests        artifacts/<project>/<phase>/   documents
  logs/                interaction & error logs  data/corrections.json        learned examples
"""


def rel(path: str) -> str:
    try:
        return str(Path(path).relative_to(ROOT))
    except ValueError:
        return path


def print_trace(interaction: Interaction) -> None:
    obs, reasoning, response = interaction.observations, interaction.reasoning, interaction.response
    print("\n[Observe]")
    print(f"  {obs['word_count']} words, client '{obs['client']}', project '{obs['project']}'")
    print("[Reason]")
    for step in reasoning["steps"]:
        print(f"  - {step}")
    print("[Act]")
    print(f"  Advice: {response['advice']}")
    if "artifact_path" in response:
        print(f"  Artifact saved: {rel(response['artifact_path'])}")
    elif "artifact_error" in response:
        print(f"  Artifact error: {response['artifact_error']}")


def confirm_phase(interaction: Interaction) -> Interaction:
    """Adapt step: ask the user to confirm low-confidence phases."""
    if not interaction.needs_confirmation:
        return interaction
    phase = interaction.reasoning["phase"]
    print(f"\n[Adapt] Confidence is low. Press Enter to accept '{phase}', or type the correct phase")
    answer = input(f"        ({', '.join(PHASES)}): ").strip().lower()
    if not answer or answer == phase:
        return interaction
    try:
        updated = agent.adapt(interaction, answer)
    except ValueError as e:
        print(f"  {e} Keeping '{phase}'.")
        return interaction
    print(f"  Thanks - learned '{answer}' for requests like this.")
    if "artifact_path" in updated.response:
        print(f"  Artifact saved: {rel(updated.response['artifact_path'])}")
    return updated


def submit_request() -> None:
    try:
        existing = storage.load_requests()
        request = create_request(
            storage.next_id(),
            input("Description (10-500 chars): "),
            input("Client: "),
            input("Project: "),
        )
        guard.check(request.description, [r["description"] for r in existing])
    except (ValidationError, RuntimeError, OSError) as e:
        print(f"Error: {e}")
        monitoring.log_error("submit_request", str(e))
        return

    guard.record()
    interaction = agent.process(
        {"id": request.id, "description": request.description, "client": request.client, "project": request.project}
    )
    print_trace(interaction)
    interaction = confirm_phase(interaction)
    request.phase = interaction.reasoning["phase"] or ""
    request.confidence = interaction.reasoning["confidence"]
    try:
        storage.append_request(request)
    except (RuntimeError, OSError) as e:
        print(f"Error saving request: {e}")
        monitoring.log_error("submit_request", str(e))
        return
    status = f"phase: {request.phase}" if request.phase else "unclassified - use option 3 to retry"
    print(f"\nSaved request #{request.id} ({status}).")


def view_requests() -> None:
    try:
        requests = storage.load_requests()
    except (RuntimeError, OSError) as e:
        print(f"Error: {e}")
        return
    if not requests:
        print("No requests stored yet.")
        return
    print(f"\n{'#':>3}  {'Phase':<15} {'Conf':>5}  {'Project':<15} Description")
    print("-" * 80)
    for r in requests:
        phase = r.get("phase") or "-"
        conf = f"{r.get('confidence', 0):.0%}" if r.get("phase") else "-"
        desc = r["description"] if len(r["description"]) <= 40 else r["description"][:37] + "..."
        print(f"{r['id']:>3}  {phase:<15} {conf:>5}  {r['project'][:15]:<15} {desc}")


def classify_pending() -> None:
    try:
        requests = storage.load_requests()
    except (RuntimeError, OSError) as e:
        print(f"Error: {e}")
        return
    pending = [r for r in requests if not r.get("phase")]
    if not pending:
        print("All requests are already classified.")
        return
    for r in pending:
        print(f"\n--- Request #{r['id']} ---")
        interaction = agent.process(
            {"id": r["id"], "description": r["description"], "client": r["client"], "project": r["project"]}
        )
        print_trace(interaction)
        if interaction.reasoning["phase"] is None:
            print("Stopping: the AI service is unavailable. Try again later.")
            break
        interaction = confirm_phase(interaction)
        r["phase"] = interaction.reasoning["phase"]
        r["confidence"] = interaction.reasoning["confidence"]
    try:
        storage.save_requests(requests)
    except OSError as e:
        print(f"Error saving: {e}")


def follow_up() -> None:
    print(agent.follow_up(input("Ask (e.g. 'why that phase?'): ")[:200]))


def analytics() -> None:
    try:
        run_analytics()
    except (RuntimeError, OSError) as e:
        print(f"Error: {e}")


def statistics() -> None:
    print(monitoring.format_dashboard(monitoring.compute_metrics(monitoring.load_interactions())))


def main() -> None:
    actions = {
        "1": submit_request, "2": view_requests, "3": classify_pending, "4": follow_up,
        "5": analytics, "6": statistics, "7": lambda: print(HELP),
    }
    print(BANNER)
    while True:
        print(MENU)
        choice = input("\nChoose an option (h for help): ").strip().lower()
        if choice in ("8", "q", "exit"):
            print("Goodbye!")
            break
        action = actions.get("7" if choice in ("h", "help", "?") else choice)
        if action:
            action()
        else:
            print("Invalid choice. Enter a number from 1 to 8.")


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("\nGoodbye!")
