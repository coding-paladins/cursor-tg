from __future__ import annotations

import logging

import httpx

from cursor_tg_connector.config import Settings

logger = logging.getLogger(__name__)


class VoiceTranscriptionError(RuntimeError):
    pass


class VoiceTranscriptionService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = httpx.AsyncClient(
            base_url=settings.openai_api_base_url,
            headers={"Authorization": f"Bearer {settings.openai_api_key}"},
            timeout=60.0,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def transcribe_audio(self, audio_bytes: bytes, *, filename: str = "voice.ogg") -> str:
        if not self._settings.openai_api_key:
            raise VoiceTranscriptionError(
                "Voice transcription is not configured. Set OPENAI_API_KEY in your environment."
            )

        files = {"file": (filename, audio_bytes, "application/octet-stream")}
        data = {"model": self._settings.voice_transcription_model}
        try:
            response = await self._client.post(
                "/v1/audio/transcriptions",
                files=files,
                data=data,
            )
        except httpx.RequestError as exc:
            raise VoiceTranscriptionError(
                f"Failed to reach transcription service: {exc}"
            ) from exc

        if response.status_code != 200:
            message = response.text.strip() or f"HTTP {response.status_code}"
            logger.warning(
                "Voice transcription failed status=%s message=%s",
                response.status_code,
                message,
            )
            raise VoiceTranscriptionError(f"Transcription failed: {message}")

        payload = response.json()
        text = payload.get("text")
        if not isinstance(text, str) or not text.strip():
            raise VoiceTranscriptionError("Transcription returned no text.")
        return text.strip()
