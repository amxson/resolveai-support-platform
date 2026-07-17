"""Configuration parsing regression tests."""

from app.config import Settings


def test_cors_origins_accept_comma_separated_environment_value(monkeypatch) -> None:
    monkeypatch.setenv(
        "CORS_ORIGINS",
        "https://resolveai-support-platform.vercel.app,https://example.com",
    )

    settings = Settings(_env_file=None)

    assert settings.cors_origins == [
        "https://resolveai-support-platform.vercel.app",
        "https://example.com",
    ]


def test_cors_origins_accept_json_environment_value(monkeypatch) -> None:
    monkeypatch.setenv("CORS_ORIGINS", '["https://example.com"]')

    settings = Settings(_env_file=None)

    assert settings.cors_origins == ["https://example.com"]
