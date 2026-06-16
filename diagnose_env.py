"""Environment diagnostics for backend/frontend startup on Windows."""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

LOG_PATH = Path(__file__).resolve().parent / "debug-83cec0.log"
PROJECT = Path(__file__).resolve().parent
BACKEND = PROJECT / "backend"
FRONTEND = PROJECT / "frontend"


def log(hypothesis_id: str, message: str, data: dict, run_id: str = "diagnose") -> None:
    entry = {
        "sessionId": "83cec0",
        "runId": run_id,
        "hypothesisId": hypothesis_id,
        "location": "diagnose_env.py",
        "message": message,
        "data": data,
        "timestamp": int(time.time() * 1000),
    }
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def main() -> None:
    policy = subprocess.run(
        ["powershell", "-Command", "Get-ExecutionPolicy -Scope CurrentUser"],
        capture_output=True,
        text=True,
        check=False,
    )
    log("H1", "powershell current user execution policy", {
        "stdout": policy.stdout.strip(),
        "returncode": policy.returncode,
    })

    npm_cmd_version = subprocess.run(
        ["cmd", "/c", "npm --version"],
        capture_output=True,
        text=True,
        check=False,
        cwd=FRONTEND,
    )
    log("H3", "npm via cmd.exe works", {
        "stdout": npm_cmd_version.stdout.strip(),
        "returncode": npm_cmd_version.returncode,
    })

    npm_ps1_test = subprocess.run(
        ["powershell", "-NoProfile", "-Command", "npm --version"],
        capture_output=True,
        text=True,
        check=False,
        cwd=FRONTEND,
    )
    log("H3", "npm via powershell ps1", {
        "stdout": npm_ps1_test.stdout.strip(),
        "stderr": npm_ps1_test.stderr.strip()[:300],
        "returncode": npm_ps1_test.returncode,
    })

    print(f"Diagnostics written to {LOG_PATH}")


if __name__ == "__main__":
    main()
