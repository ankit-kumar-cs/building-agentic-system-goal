from src import storage
from src.analytics import run_analytics
from src.phase_detector import PhaseDetectionError, confidence_label, detect_phase
from src.request_handler import create_request

MENU = """
=== Feature Request Manager ===
1. Add request
2. View requests
3. Analytics
4. Detect phases for unclassified requests
5. Exit
"""


def add_request() -> None:
    description = input("Description (10-500 chars): ")
    client = input("Client: ")
    project = input("Project: ")
    try:
        request = create_request(storage.next_id(), description, client, project)
        try:
            request.phase, request.confidence = detect_phase(request.description)
        except PhaseDetectionError as e:
            print(f"Warning: phase not detected ({e}). Use option 4 to retry.")
        storage.append_request(request)
    except (ValueError, RuntimeError, OSError) as e:
        print(f"Error: {e}")
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
        try:
            r["phase"], r["confidence"] = detect_phase(r["description"])
        except PhaseDetectionError as e:
            print(f"Error: {e}")
            break
        print(f"#{r['id']}: {r['phase']} ({confidence_label(r['confidence'])}, {r['confidence']:.0%})")
    try:
        storage.save_requests(requests)
    except OSError as e:
        print(f"Error saving: {e}")


def main() -> None:
    actions = {"1": add_request, "2": view_requests, "3": analytics, "4": detect_phases}
    while True:
        print(MENU)
        choice = input("Choose an option: ").strip()
        if choice == "5":
            print("Goodbye!")
            break
        action = actions.get(choice)
        if action:
            action()
        else:
            print("Invalid choice. Enter 1-5.")


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("\nGoodbye!")
