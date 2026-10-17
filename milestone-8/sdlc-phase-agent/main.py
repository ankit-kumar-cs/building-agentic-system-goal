from src import monitoring, storage
from src.agent import SimpleAgent
from src.analytics import run_analytics
from src.phase_detector import confidence_label
from src.request_handler import create_request

agent = SimpleAgent()

MENU = """
=== Feature Request Manager ===
1. Add request
2. View requests
3. Analytics
4. Classify unclassified requests (agent)
5. Ask agent a follow-up
6. View agent statistics
7. Exit
"""


def print_trace(interaction) -> None:
    print("\n[Observe]")
    obs = interaction.observations
    print(f"  {obs['word_count']} words, project '{obs['project']}'")
    print("[Reason]")
    for step in interaction.reasoning["steps"]:
        print(f"  - {step}")
    print("[Act]")
    print(f"  {interaction.response['advice']}")
    if "artifact_path" in interaction.response:
        print(f"  Artifact saved: {interaction.response['artifact_path']}")
    elif "artifact_error" in interaction.response:
        print(f"  Artifact error: {interaction.response['artifact_error']}")


def add_request() -> None:
    description = input("Description (10-500 chars): ")
    client = input("Client: ")
    project = input("Project: ")
    try:
        request = create_request(storage.next_id(), description, client, project)
        interaction = agent.process(
            {"id": request.id, "description": request.description, "client": request.client, "project": request.project}
        )
        print_trace(interaction)
        request.phase = interaction.reasoning["phase"] or ""
        request.confidence = interaction.reasoning["confidence"]
        storage.append_request(request)
    except (ValueError, RuntimeError, OSError) as e:
        print(f"Error: {e}")
        monitoring.log_error("add_request", str(e))
        return
    print(f"Saved request #{request.id}.")


def view_requests() -> None:
    try:
        requests = storage.load_requests()
    except (RuntimeError, OSError) as e:
        print(f"Error: {e}")
        return
    if not requests:
        print("No requests stored yet.")
        return
    for r in requests:
        print(f"\n#{r['id']} [{r['timestamp']}]")
        print(f"  Client:      {r['client']}")
        print(f"  Project:     {r['project']}")
        print(f"  Description: {r['description']}")
        if r.get("phase"):
            conf = r.get("confidence", 0.0)
            print(f"  Phase:       {r['phase']} ({confidence_label(conf)} confidence, {conf:.0%})")
        else:
            print("  Phase:       not classified")


def analytics() -> None:
    try:
        run_analytics()
    except (RuntimeError, OSError) as e:
        print(f"Error: {e}")


def detect_phases() -> None:
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
        interaction = agent.process(
            {"id": r["id"], "description": r["description"], "client": r["client"], "project": r["project"]}
        )
        print(f"\n--- Request #{r['id']} ---")
        print_trace(interaction)
        if interaction.reasoning["phase"] is None:
            break
        r["phase"] = interaction.reasoning["phase"]
        r["confidence"] = interaction.reasoning["confidence"]
    try:
        storage.save_requests(requests)
    except OSError as e:
        print(f"Error saving: {e}")


def follow_up() -> None:
    print(agent.follow_up(input("Ask (e.g. 'why that phase?'): ")))


def view_statistics() -> None:
    print(monitoring.format_dashboard(monitoring.compute_metrics(monitoring.load_interactions())))


def main() -> None:
    actions = {"1": add_request, "2": view_requests, "3": analytics, "4": detect_phases, "5": follow_up,
               "6": view_statistics}
    while True:
        print(MENU)
        choice = input("Choose an option: ").strip()
        if choice == "7":
            print("Goodbye!")
            break
        action = actions.get(choice)
        if action:
            action()
        else:
            print("Invalid choice. Enter 1-7.")


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("\nGoodbye!")
