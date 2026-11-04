"""Load the private local environment and run one development service."""

import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in {"api", "worker", "frontend"}:
        raise SystemExit("Usage: python tools/run_local.py api|worker|frontend")
    config = (
        Path(os.environ.get("LOCALAPPDATA", Path.home() / ".config"))
        / "ResolveAI"
        / "workspace.env"
    )
    if not config.is_file():
        raise SystemExit("Run python tools/setup_local.py first.")
    load_dotenv(config, override=True)
    if os.environ.get("APP_ENV") != "development":
        raise SystemExit("This launcher is restricted to local development.")
    repo = Path(__file__).resolve().parent.parent
    service = sys.argv[1]
    if service == "frontend":
        # Do not pass server credentials to npm/Vite or its subprocesses.
        frontend_env = {
            k: v
            for k, v in os.environ.items()
            if k
            not in {
                "DATABASE_URL",
                "GEMINI_API_KEY",
                "GEMINI_MODEL",
                "GOOGLE_CLIENT_ID",
                "GOOGLE_CLIENT_SECRET",
                "GOOGLE_REDIRECT_URI",
                "OAUTH_ENCRYPTION_KEY",
            }
        }
        frontend_env.update(
            VITE_APP_MODE="workspace", VITE_API_BASE_URL="http://localhost:8000"
        )
        npm = "npm.cmd" if os.name == "nt" else "npm"
        raise SystemExit(
            subprocess.call(
                [
                    npm,
                    "run",
                    "dev",
                    "--",
                    "--host",
                    "localhost",
                    "--port",
                    "5173",
                    "--strictPort",
                ],
                cwd=repo / "frontend",
                env=frontend_env,
            )
        )
    if service == "api":
        subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=repo / "backend",
            check=True,
        )
        command = [
            sys.executable,
            "-m",
            "uvicorn",
            "production.app:create_app",
            "--factory",
            "--host",
            "localhost",
            "--port",
            "8000",
            "--no-access-log",
        ]
    else:
        command = [sys.executable, "-m", "production.worker"]
    raise SystemExit(subprocess.call(command, cwd=repo / "backend"))


if __name__ == "__main__":
    main()
