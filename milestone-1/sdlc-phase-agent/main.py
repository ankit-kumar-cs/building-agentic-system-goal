from src import storage
from src.request_handler import create_request

MENU = """
=== Feature Request Manager ===
1. Add request
2. View requests
3. Exit
"""


def add_request() -> None:
    description = input("Description (10-500 chars): ")
    client = input("Client: ")
    project = input("Project: ")
    try:
        request = create_request(storage.next_id(), description, client, project)
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


def main() -> None:
    actions = {"1": add_request, "2": view_requests}
    while True:
        print(MENU)
        choice = input("Choose an option: ").strip()
        if choice == "3":
            print("Goodbye!")
            break
        action = actions.get(choice)
        if action:
            action()
        else:
            print("Invalid choice. Enter 1, 2, or 3.")


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("\nGoodbye!")
