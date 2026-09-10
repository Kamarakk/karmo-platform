"""Day 1 environment check -- run this first.

Not part of the lesson exercise. Verifies the local learning environment
only: this file's own interpreter, the Day-1 packages, and local-only
Ollama connectivity. Makes no production connection of any kind.
"""

import sys
import urllib.request
import urllib.error
import json

OLLAMA_URL = "http://127.0.0.1:11434"


def check_python():
    print(f"Python executable: {sys.executable}")
    print(f"Python version:    {sys.version.split()[0]}")
    ok = sys.version_info >= (3, 11)
    print(f"Python >= 3.11:    {'OK' if ok else 'FAIL'}")
    in_venv = ".venv" in sys.executable
    print(f"Running from learning-labs/.venv: {'OK' if in_venv else 'WARNING -- not in the dedicated venv'}")
    return ok and in_venv


def check_packages():
    ok = True
    for name in ("pytest", "pydantic", "httpx", "jupyterlab"):
        try:
            module = __import__(name)
            version = getattr(module, "__version__", getattr(module, "VERSION", "unknown"))
            print(f"{name}: OK (version {version})")
        except ImportError as error:
            print(f"{name}: FAIL ({error})")
            ok = False
    return ok


def check_ollama():
    try:
        with urllib.request.urlopen(f"{OLLAMA_URL}/api/version", timeout=5) as response:
            data = json.loads(response.read())
            print(f"Ollama reachable at {OLLAMA_URL}: OK (version {data.get('version')})")
    except (urllib.error.URLError, OSError) as error:
        print(f"Ollama reachable at {OLLAMA_URL}: FAIL ({error})")
        return False

    try:
        with urllib.request.urlopen(f"{OLLAMA_URL}/api/tags", timeout=5) as response:
            data = json.loads(response.read())
            models = [m["name"] for m in data.get("models", [])]
            print(f"Local models available: {models if models else '(none)'}")
            return len(models) > 0
    except (urllib.error.URLError, OSError) as error:
        print(f"Listing local models: FAIL ({error})")
        return False


if __name__ == "__main__":
    print("=== Day 1 environment check ===\n")
    python_ok = check_python()
    print()
    packages_ok = check_packages()
    print()
    ollama_ok = check_ollama()
    print()

    if python_ok and packages_ok and ollama_ok:
        print("Environment check: READY")
    else:
        print("Environment check: NOT READY -- see failures above")
        sys.exit(1)
