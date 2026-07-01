from __future__ import annotations

import base64
import logging

from telegram import PhotoSize, Update
from telegram.ext import ContextTypes

from cursor_tg_connector.cursor_api_models import PromptImage
from cursor_tg_connector.domain_types import WizardStep
from cursor_tg_connector.services_create_agent_service import CreateAgentError
from cursor_tg_connector.services_followup_service import FollowupError
from cursor_tg_connector.services_notification import TelegramNotifier
from cursor_tg_connector.services_voice_transcription import VoiceTranscriptionError
from cursor_tg_connector.telegram_bot_common import (
    auto_enable_thread_mode_if_supported,
    get_message_thread_id,
    get_services,
    render_machine_keyboard,
)
from cursor_tg_connector.telegram_threads import ensure_agent_thread
from cursor_tg_connector.utils_formatting import (
    build_agent_created_message,
    build_thread_opened_message,
)

logger = logging.getLogger(__name__)


async def _download_photo(photo: PhotoSize) -> PromptImage:
    file = await photo.get_file()
    data = await file.download_as_bytearray()
    return PromptImage(
        data=base64.b64encode(data).decode(),
        dimension={"width": photo.width, "height": photo.height},
    )


async def _extract_images(update: Update) -> list[PromptImage]:
    msg = update.effective_message
    if not msg or not msg.photo:
        return []
    best = msg.photo[-1]
    try:
        return [await _download_photo(best)]
    except Exception:
        logger.warning("Failed to download photo from Telegram", exc_info=True)
        return []


async def _transcribe_voice_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> str | None:
    msg = update.effective_message
    if msg is None:
        return None

    voice = msg.voice or msg.audio
    if voice is None:
        return None

    services = get_services(context)
    if services.voice_transcription_service is None:
        await msg.reply_text(
            "Voice messages are not configured. Set OPENAI_API_KEY to enable transcription."
        )
        return None

    status_message = await msg.reply_text("Transcribing voice message...")
    try:
        file = await voice.get_file()
        audio_bytes = await file.download_as_bytearray()
        filename = "voice.ogg" if msg.voice else (voice.file_name or "audio.mp3")
        text = await services.voice_transcription_service.transcribe_audio(
            bytes(audio_bytes),
            filename=filename,
        )
    except VoiceTranscriptionError as exc:
        await status_message.edit_text(str(exc))
        return None
    except Exception:
        logger.warning("Failed to transcribe voice message", exc_info=True)
        await status_message.edit_text("Failed to transcribe voice message.")
        return None

    await status_message.edit_text(f"(transcribed): {text}")
    return text


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user is None or update.effective_message is None:
        return

    services = get_services(context)
    if update.effective_user.id != services.settings.telegram_allowed_user_id:
        return

    notifier = TelegramNotifier(context.bot)
    await services.create_agent_service.state_repo.update_chat_context(
        services.settings.telegram_allowed_user_id,
        update.effective_chat.id,
    )
    await auto_enable_thread_mode_if_supported(
        context,
        services.settings.telegram_allowed_user_id,
    )
    session = await services.create_agent_service.get_session(
        services.settings.telegram_allowed_user_id
    )
    msg = update.effective_message
    message_thread_id = get_message_thread_id(update)
    text = msg.text or msg.caption or ""

    if not text and (msg.voice or msg.audio):
        transcribed = await _transcribe_voice_message(update, context)
        if transcribed is None:
            return
        text = transcribed

    if session.wizard_state == WizardStep.WAITING_MODEL:
        await msg.reply_text("Use the inline buttons to select a model.")
        return

    if session.wizard_state == WizardStep.WAITING_REPOSITORY:
        await msg.reply_text("Use the inline buttons to select a repository.")
        return

    if session.wizard_state == WizardStep.WAITING_BRANCH:
        try:
            page_data = await services.create_agent_service.save_branch(
                services.settings.telegram_allowed_user_id,
                text,
            )
            session = await services.create_agent_service.get_session(
                services.settings.telegram_allowed_user_id
            )
            machines = session.wizard_payload["machines"]
        except CreateAgentError as exc:
            await msg.reply_text(str(exc))
            return
        await msg.reply_text(
            "Step 4/5: Select the My Machine to run this agent on. "
            "The worker must be started in a checkout of the selected repository.",
            reply_markup=render_machine_keyboard(page_data, machines),
        )
        return

    if session.wizard_state == WizardStep.WAITING_MACHINE:
        try:
            machine_name = await services.create_agent_service.save_machine(
                services.settings.telegram_allowed_user_id,
                text,
            )
        except CreateAgentError as exc:
            await msg.reply_text(str(exc))
            return
        await msg.reply_text(
            f"Step 5/5: Send the prompt (text, voice, or photo with caption) for the new agent "
            f"on machine {machine_name!r}."
        )
        return

    if session.wizard_state == WizardStep.WAITING_PROMPT:
        images = await _extract_images(update)
        try:
            agent = await services.create_agent_service.finish_prompt(
                services.settings.telegram_allowed_user_id,
                text,
                images=images or None,
            )
        except CreateAgentError as exc:
            await msg.reply_text(str(exc))
            return

        if session.thread_mode_enabled:
            try:
                binding, created = await ensure_agent_thread(
                    bot=context.bot,
                    state_repo=services.create_agent_service.state_repo,
                    agent=agent,
                    chat_id=update.effective_chat.id,
                )
            except Exception:
                await msg.reply_text(
                    "Agent created, but I could not create its Telegram thread. "
                    "Make sure threaded mode is enabled for this chat."
                )
                return
            await notifier.send_text(
                binding.telegram_chat_id,
                build_agent_created_message(agent),
                message_thread_id=binding.message_thread_id,
            )
            await msg.reply_text(build_thread_opened_message(agent, created))
        else:
            await notifier.send_text(
                update.effective_chat.id,
                build_agent_created_message(agent),
            )
        return

    images = await _extract_images(update)
    try:
        delivered_count = await services.followup_service.send_followup(
            services.settings.telegram_allowed_user_id,
            update.effective_chat.id,
            message_thread_id,
            text,
            notifier,
            images=images or None,
        )
    except FollowupError as exc:
        await msg.reply_text(str(exc))
        return

    if delivered_count == 0:
        await msg.reply_text(
            "Follow-up sent. No new agent response is available yet; polling will keep checking."
        )
