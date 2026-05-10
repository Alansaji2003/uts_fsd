"""CLIUniApp — entry point.

Run:
    python cli_app.py
"""
from controllers.university_controller import UniversityController


if __name__ == "__main__":
    try:
        UniversityController.run()
    except (KeyboardInterrupt, EOFError):
        print("\nThank You")
