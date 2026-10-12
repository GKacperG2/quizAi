"""Double-click bootstrap. Standard library only until the error dialog is available."""
import ctypes
import sys
from pathlib import Path


def launch():
    root = Path(__file__).resolve().parent
    sys.path.insert(0, str(root / "src"))
    try:
        from quiz_assistant.app import main
    except Exception as exc:
        ctypes.windll.user32.MessageBoxW(
            None,
            "Nie udało się wczytać programu lub zależności (" + type(exc).__name__ + ").\n\n"
            "W folderze projektu wykonaj:\n"
            '.venv\\Scripts\\python.exe -m pip install -e ".[dev]"\n\n'
            "Uruchamiaj przez Uruchom_Asystenta.cmd.",
            "Asystent quizów — błąd uruchamiania", 0x10,
        )
        return 2
    try:
        return main()
    except Exception as exc:
        ctypes.windll.user32.MessageBoxW(
            None, "Błąd uruchamiania: " + type(exc).__name__ +
            ". Sprawdź dziennik diagnostyczny lub uruchom .venv\\Scripts\\python.exe -m quiz_assistant.",
            "Asystent quizów", 0x10,
        )
        return 2


if __name__ == "__main__":
    sys.exit(launch())
