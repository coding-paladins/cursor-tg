from __future__ import annotations

from cursor_tg_connector.config import Settings


def test_cursor_use_private_worker_defaults_to_false(tmp_path) -> None:
    settings = Settings.model_validate(
        {
            "TELEGRAM_BOT_TOKEN": "token",
            "TELEGRAM_ALLOWED_USER_ID": 1234,
            "CURSOR_API_KEY": "cursor-key",
            "SQLITE_PATH": str(tmp_path / "connector.db"),
        }
    )

    assert settings.cursor_use_private_worker is False
    assert settings.cursor_worker_pool_name is None
    assert settings.cursor_worker_machine_name is None
    assert settings.voice_transcription_enabled is False


def test_voice_transcription_enabled_when_openai_key_set(tmp_path) -> None:
    settings = Settings.model_validate(
        {
            "TELEGRAM_BOT_TOKEN": "token",
            "TELEGRAM_ALLOWED_USER_ID": 1234,
            "CURSOR_API_KEY": "cursor-key",
            "SQLITE_PATH": str(tmp_path / "connector.db"),
            "OPENAI_API_KEY": "openai-key",
        }
    )

    assert settings.voice_transcription_enabled is True


def test_github_default_merge_method_defaults_to_merge(tmp_path) -> None:
    settings = Settings.model_validate(
        {
            "TELEGRAM_BOT_TOKEN": "token",
            "TELEGRAM_ALLOWED_USER_ID": 1234,
            "CURSOR_API_KEY": "cursor-key",
            "SQLITE_PATH": str(tmp_path / "connector.db"),
            "POLL_INTERVAL_SECONDS": 1,
            "FOLLOWUP_POLL_INTERVAL_SECONDS": 0.01,
            "FOLLOWUP_POLL_TIMEOUT_SECONDS": 0.05,
        }
    )

    assert settings.github_default_merge_method == "merge"
