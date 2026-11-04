"""Run interactively to configure local development without exposing secrets."""

import csv
import getpass
import json
import os
import subprocess
from pathlib import Path

from cryptography.fernet import Fernet


def private_directory():
    root = Path(os.environ.get("LOCALAPPDATA", Path.home() / ".config")) / "ResolveAI"
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    if os.name == "nt":
        identity = subprocess.run(
            ["whoami", "/user", "/fo", "csv", "/nh"],
            check=True,
            capture_output=True,
            text=True,
        )
        sid = next(csv.reader(identity.stdout.strip().splitlines()))[1]
        subprocess.run(
            ["icacls", str(root), "/inheritance:r", "/grant:r", f"*{sid}:(OI)(CI)F"],
            check=True,
            capture_output=True,
        )
    else:
        root.chmod(0o700)
    return root


def quote(value):
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"


def main():
    root = private_directory()
    destination = root / "workspace.env"
    if destination.exists():
        raise SystemExit(
            f"Configuration already exists at {destination}. It was not overwritten."
        )
    print(
        "Local development only. Secrets will not be echoed or stored in the repository."
    )
    oauth_file = Path(
        input("Path to Google's downloaded Web application OAuth JSON: ")
        .strip()
        .strip('"')
    )
    payload = json.loads(oauth_file.read_text(encoding="utf-8"))
    client = payload.get("web", {})
    redirect = "http://localhost:8000/integrations/gmail/callback"
    if (
        not client.get("client_id")
        or not client.get("client_secret")
        or redirect not in client.get("redirect_uris", [])
    ):
        raise SystemExit(
            "Use a Web application client with the exact localhost callback from the setup guide."
        )
    key = getpass.getpass("Paste Gemini API key (hidden): ").strip()
    if not key:
        raise SystemExit("Gemini key is required; nothing was saved.")
    model = input(
        "Gemini model ID shown in AI Studio (for example gemini-2.5-flash): "
    ).strip()
    if not model:
        raise SystemExit("A model ID is required; nothing was saved.")
    config = {
        "APP_ENV": "development",
        "APP_ORIGINS": "http://localhost:5173",
        "DATABASE_URL": "sqlite:///" + (root / "workspace.db").as_posix(),
        "GEMINI_API_KEY": key,
        "GEMINI_MODEL": model,
        "GOOGLE_CLIENT_ID": client["client_id"],
        "GOOGLE_CLIENT_SECRET": client["client_secret"],
        "GOOGLE_REDIRECT_URI": redirect,
        "OAUTH_ENCRYPTION_KEY": Fernet.generate_key().decode(),
        "ENABLE_EMAIL_SEND": "false",
        "ALLOW_SIGNUP": "true",
    }
    with destination.open("x", encoding="utf-8") as file:
        file.write(
            "\n".join(f"{name}={quote(value)}" for name, value in config.items()) + "\n"
        )
    if os.name != "nt":
        destination.chmod(0o600)
    print(f"Saved private local configuration: {destination}")
    print("No provider call or email was sent. Next: python tools/run_local.py api")


if __name__ == "__main__":
    main()
