from __future__ import annotations

import httpx
import pytest
import respx

from cursor_tg_connector.config import Settings
from cursor_tg_connector.services_voice_transcription import (
    VoiceTranscriptionError,
    VoiceTranscriptionService,
)


@pytest.mark.asyncio
async def test_transcribe_audio_returns_text(tmp_path) -> None:
    settings = Settings.model_validate(
        {
            "TELEGRAM_BOT_TOKEN": "token",
            "TELEGRAM_ALLOWED_USER_ID": 1234,
            "CURSOR_API_KEY": "cursor-key",
            "SQLITE_PATH": str(tmp_path / "connector.db"),
            "OPENAI_API_KEY": "openai-key",
        }
    )
    service = VoiceTranscriptionService(settings)

    with respx.mock(assert_all_called=True) as router:
        router.post("https://api.openai.com/v1/audio/transcriptions").mock(
            return_value=httpx.Response(200, json={"text": "Ship the feature"})
        )
        text = await service.transcribe_audio(b"audio-bytes", filename="voice.ogg")

    await service.aclose()
    assert text == "Ship the feature"


@pytest.mark.asyncio
async def test_transcribe_audio_surfaces_api_error(tmp_path) -> None:
    settings = Settings.model_validate(
        {
            "TELEGRAM_BOT_TOKEN": "token",
            "TELEGRAM_ALLOWED_USER_ID": 1234,
            "CURSOR_API_KEY": "cursor-key",
            "SQLITE_PATH": str(tmp_path / "connector.db"),
            "OPENAI_API_KEY": "openai-key",
        }
    )
    service = VoiceTranscriptionService(settings)

    with respx.mock(assert_all_called=True) as router:
        router.post("https://api.openai.com/v1/audio/transcriptions").mock(
            return_value=httpx.Response(401, json={"error": {"message": "bad key"}})
        )
        with pytest.raises(VoiceTranscriptionError, match="Transcription failed"):
            await service.transcribe_audio(b"audio-bytes")

    await service.aclose()
