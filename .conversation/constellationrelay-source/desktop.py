"""Constellation Relay — desktop launcher.

Runs the Streamlit app in a native desktop window (via pywebview) so it feels
like a regular application. If pywebview isn't installed, it falls back to
opening your default browser instead.

Usage:
    python desktop.py

Optional install for the native window:
    pip install pywebview
"""

import os
import socket
import subprocess
import sys
import time
import urllib.request

APP_TITLE = "Constellation Relay"
APP_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.py")
STARTUP_TIMEOUT_SECONDS = 60


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def start_streamlit(port: int) -> subprocess.Popen:
    return subprocess.Popen(
        [
            sys.executable, "-m", "streamlit", "run", APP_FILE,
            "--server.headless", "true",
            "--server.address", "127.0.0.1",
            "--server.port", str(port),
            "--browser.gatherUsageStats", "false",
        ],
        cwd=os.path.dirname(APP_FILE),
    )


def wait_for_server(url: str, process: subprocess.Popen) -> bool:
    deadline = time.time() + STARTUP_TIMEOUT_SECONDS
    while time.time() < deadline:
        if process.poll() is not None:
            return False  # streamlit exited before it came up
        try:
            urllib.request.urlopen(url, timeout=1)
            return True
        except Exception:
            time.sleep(0.3)
    return False


def main() -> int:
    port = find_free_port()
    url = f"http://127.0.0.1:{port}"

    print(f"Starting {APP_TITLE} on {url} ...")
    process = start_streamlit(port)

    try:
        if not wait_for_server(url, process):
            print("The app server failed to start. Run it directly to see the error:")
            print("    streamlit run app.py")
            return 1

        try:
            import webview  # pywebview
        except ImportError:
            webview = None

        if webview is not None:
            # Native desktop window; closing it shuts the app down.
            webview.create_window(APP_TITLE, url, width=1400, height=900)
            webview.start()
        else:
            import webbrowser
            print("pywebview is not installed — opening in your browser instead.")
            print("(For a native window: pip install pywebview)")
            webbrowser.open(url)
            print("Press Ctrl+C in this terminal to quit.")
            process.wait()
    except KeyboardInterrupt:
        pass
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
    return 0


if __name__ == "__main__":
    sys.exit(main())
