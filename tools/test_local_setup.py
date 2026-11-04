"""Configuration tests use synthetic values; never read user credentials."""

import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from dotenv import dotenv_values

spec = importlib.util.spec_from_file_location(
    "setup_local", Path(__file__).with_name("setup_local.py")
)
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)


class LocalSetupTests(unittest.TestCase):
    def test_configuration_roundtrip_no_secret_echo_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            oauth = root / "web-client.json"
            oauth.write_text(
                json.dumps(
                    {
                        "web": {
                            "client_id": "synthetic-client-id",
                            "client_secret": "synthetic-client-secret",
                            "redirect_uris": [
                                "http://localhost:8000/integrations/gmail/callback"
                            ],
                        }
                    }
                ),
                encoding="utf-8",
            )
            output = io.StringIO()
            with (
                patch.object(setup, "private_directory", return_value=root),
                patch("builtins.input", side_effect=[str(oauth), "test-model"]),
                patch.object(
                    setup.getpass, "getpass", return_value="synthetic-api-key"
                ),
                contextlib.redirect_stdout(output),
            ):
                setup.main()
            config = dotenv_values(root / "workspace.env")
            self.assertEqual(config["GOOGLE_CLIENT_SECRET"], "synthetic-client-secret")
            self.assertEqual(config["GEMINI_API_KEY"], "synthetic-api-key")
            self.assertEqual(config["ENABLE_EMAIL_SEND"], "false")
            self.assertNotIn("synthetic-api-key", output.getvalue())
            self.assertNotIn("synthetic-client-secret", output.getvalue())
            setup.Fernet(config["OAUTH_ENCRYPTION_KEY"].encode())
            with (
                patch.object(setup, "private_directory", return_value=root),
                self.assertRaises(SystemExit),
            ):
                setup.main()

    def test_rejects_wrong_callback_without_writing_config(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            oauth = root / "client.json"
            oauth.write_text(
                json.dumps({"installed": {"client_id": "wrong-client-type"}}),
                encoding="utf-8",
            )
            with (
                patch.object(setup, "private_directory", return_value=root),
                patch("builtins.input", return_value=str(oauth)),
                self.assertRaises(SystemExit),
            ):
                setup.main()
            self.assertFalse((root / "workspace.env").exists())


if __name__ == "__main__":
    unittest.main()
