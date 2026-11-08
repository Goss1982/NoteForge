"""Run real app/worker/browser against an isolated, deterministic test AI server.

Never connects to a live AI provider or reMarkable account. Does not touch the
normal app database or environment file. Build frontend before running this.
"""

import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import fitz

ROOT = Path(__file__).resolve().parents[3]
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"


def main():
    for port in (3000, 8000, 9901):
        with socket.socket() as probe:
            if probe.connect_ex(("127.0.0.1", port)) == 0:
                raise RuntimeError(f"Test port {port} is already in use. Stop that local service first.")
    with tempfile.TemporaryDirectory(prefix="noteforge-browser-test-") as folder:
        temp = Path(folder)
        pdf = temp / "Meeting.pdf"
        with fitz.open() as doc:
            page = doc.new_page()
            page.insert_text((50, 60), "Alex to send the proposal on Friday. Budget: GBP 2500.")
            doc.save(pdf)
        env = {
            **os.environ,
            "DATABASE_URL": f"sqlite:///{temp}/state.db",
            "DATA_DIR": str(temp / "data"),
            "ADMIN_PASSWORD": "browser-test-password",
            "SECRET_KEY": "browser-test-signing-key-longer-than-32",
            "COOKIE_SECURE": "false",
            "PUBLIC_URL": "http://127.0.0.1:3000",
            "OPENAI_API_KEY": "test-only-fixture",
            "OPENAI_BASE_URL": "http://127.0.0.1:9901/v1",
            "RMAPI_CONFIG": str(temp / "unpaired"),
            "AUTO_DOCUMENT_TYPE": "meeting_minutes",
            "E2E_PDF": str(pdf),
            "NO_PROXY": os.environ.get("NO_PROXY", "") + ",127.0.0.1,localhost",
            "no_proxy": os.environ.get("no_proxy", "") + ",127.0.0.1,localhost",
        }
        subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=BACKEND, env=env, check=True)
        processes = []
        logpath = temp / "services.log"
        with logpath.open("w+") as log:
            try:
                commands = [
                    (
                        [
                            sys.executable,
                            "-m",
                            "uvicorn",
                            "app.main:app",
                            "--host",
                            "127.0.0.1",
                            "--port",
                            "8000",
                        ],
                        BACKEND,
                    ),
                    ([sys.executable, "-m", "app.worker"], BACKEND),
                    (
                        [
                            sys.executable,
                            "-m",
                            "uvicorn",
                            "fake_provider:app",
                            "--host",
                            "127.0.0.1",
                            "--port",
                            "9901",
                        ],
                        Path(__file__).parent,
                    ),
                    (["npm", "run", "start"], FRONTEND),
                ]
                for command, cwd in commands:
                    processes.append(subprocess.Popen(command, cwd=cwd, env=env, stdout=log, stderr=log))
                opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
                for url in ["http://127.0.0.1:8000/health", "http://127.0.0.1:3000/"]:
                    deadline = time.monotonic() + 30
                    while True:
                        try:
                            with opener.open(url, timeout=2) as response:
                                if response.status == 200:
                                    break
                        except (OSError, urllib.error.URLError):
                            if time.monotonic() > deadline:
                                raise RuntimeError(f"Service failed to start: {url}")
                            time.sleep(0.2)
                subprocess.run(["node", "tests/e2e.cjs"], cwd=FRONTEND, env=env, check=True, timeout=120)
            except Exception:
                log.flush()
                print(logpath.read_text(), file=sys.stderr)
                raise
            finally:
                for process in reversed(processes):
                    process.terminate()
                for process in reversed(processes):
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()


if __name__ == "__main__":
    main()
