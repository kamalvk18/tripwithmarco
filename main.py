"""
Entry point for Solo Travel Agent.

Usage:
    uv run main.py --api    # launch FastAPI server only (port 8000)
    uv run main.py --ui     # launch React dev server only (port 5173)
    uv run main.py --both   # launch API + React UI together (recommended)
    uv run main.py --help   # show this help
"""

import subprocess
import sys
import time


def _wait_for_api(url: str, timeout: int = 15) -> bool:
    """Poll the health endpoint until the API is ready or timeout expires."""
    import urllib.request

    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{url}/health", timeout=1):
                return True
        except Exception:
            time.sleep(0.5)
    return False


def main():
    args = sys.argv[1:]

    if "--help" in args or "-h" in args:
        print(__doc__)
        return

    if "--api" in args:
        port = "8000"
        print(f"🌍 Starting Solo Travel Agent API on http://localhost:{port} ...")
        print("   Docs at http://localhost:8000/docs")
        subprocess.run(
            ["uvicorn", "backend.api.app:app", "--reload", "--port", port],
            check=True,
        )

    elif "--ui" in args:
        print("🌍 Starting React UI on http://localhost:5173 ...")
        print("   ℹ️  Requires the API server. Run with --both, or start it separately.")
        subprocess.run(["npm", "run", "dev"], cwd="frontend", check=True)

    elif "--both" in args:
        port = "8000"
        print(f"🚀 Starting API server on http://localhost:{port} ...")
        api_proc = subprocess.Popen(
            ["uvicorn", "backend.api.app:app", "--port", port],
        )
        if _wait_for_api(f"http://localhost:{port}"):
            print(f"   ✅ API ready — docs at http://localhost:{port}/docs")
        else:
            print("   ⚠️  API didn't respond in time — UI will show a warning.")

        print("🌍 Starting React UI on http://localhost:5173 ...")
        try:
            subprocess.run(["npm", "run", "dev"], cwd="frontend", check=True)
        finally:
            print("\n🛑 Shutting down API server...")
            api_proc.terminate()
            api_proc.wait()

    else:
        print(__doc__)


if __name__ == "__main__":
    main()
