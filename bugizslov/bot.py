import asyncio
import json
import logging
from io import BytesIO
from typing import Any

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import (
    BufferedInputFile, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup,
    KeyboardButton, Message, ReplyKeyboardMarkup,
)

from .config import Settings
from .llm import ALLOWED_FIELDS, LLMError, OpenAICompatibleProvider
from .report import FIELDS, render_report
from .secrets import contains_secret
from .storage import Storage

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger(__name__)

BTN_NEW = "🐞 Новый баг"
BTN_DATA = "📊 Мои данные"
BTN_DELETE = "🗑 Удалить историю"
BTN_REPORT = "📄 Сформировать отчёт"
BTN_DONT_KNOW = "Не знаю"


def main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text=BTN_NEW)],
        [KeyboardButton(text=BTN_DATA), KeyboardButton(text=BTN_DELETE)],
    ], resize_keyboard=True)


def question_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=BTN_DONT_KNOW, callback_data="unknown")],
        [InlineKeyboardButton(text="Исправить ответ", callback_data="edit_answer")],
        [InlineKeyboardButton(text=BTN_REPORT, callback_data="make_report")],
    ])


def field_keyboard(prefix: str) -> InlineKeyboardMarkup:
    buttons = [InlineKeyboardButton(text=label, callback_data=f"{prefix}:{key}") for key, label in FIELDS.items()]
    return InlineKeyboardMarkup(inline_keyboard=[buttons[i:i + 2] for i in range(0, len(buttons), 2)])


def report_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Скачать .md", callback_data="download")],
        [InlineKeyboardButton(text="Исправить поле", callback_data="edit_field")],
        [InlineKeyboardButton(text=BTN_NEW, callback_data="new_bug")],
    ])


def session_fields(row: Any) -> dict[str, Any]:
    try:
        data = json.loads(row["extracted_data"] or "{}")
        return data if isinstance(data, dict) else {}
    except (TypeError, json.JSONDecodeError):
        return {}


async def build_report(message: Message, storage: Storage, session: Any, fields: dict[str, Any]) -> None:
    markdown = render_report(fields)
    storage.save_report(session["id"], fields, markdown)
    storage.update_session(session["id"], stage="report", pending_field=None)
    storage.save_message(session["id"], "bot", "Сформирован черновик отчёта.")
    display = markdown
    if len(display) > 3900:
        display = display[:3850] + "\n…\n\nПолный текст можно скачать в .md файле."
    await message.answer(display, reply_markup=report_keyboard())


async def run_bot(settings: Settings) -> None:
    storage = Storage(settings.database_path, settings.session_ttl_days)
    llm = OpenAICompatibleProvider(
        settings.llm_api_base_url, settings.llm_api_key, settings.llm_model, settings.llm_timeout_seconds
    )
    bot = Bot(settings.telegram_bot_token)
    dp = Dispatcher()

    @dp.message(CommandStart())
    async def start(message: Message) -> None:
        await message.answer(
            "Привет! Я помогу уточнить детали ошибки и подготовить баг-репорт.\n\n"
            "Не отправляйте пароли, токены и персональные данные. Описание передаётся языковой модели.",
            reply_markup=main_keyboard(),
        )

    @dp.message(F.text == BTN_NEW)
    async def new_bug(message: Message) -> None:
        sid = storage.create_session(message.from_user.id)
        storage.save_message(sid, "bot", "Попросил описать найденную ошибку.")
        await message.answer("Опишите одну ошибку обычными словами. Что произошло?", reply_markup=main_keyboard())

    @dp.message(F.text == BTN_DATA)
    async def my_data(message: Message) -> None:
        active, completed = storage.user_summary(message.from_user.id)
        await message.answer(
            f"В хранилище: активных диалогов — {active}, завершённых — {completed}. "
            f"Диалоги автоматически удаляются через {settings.session_ttl_days} дней.", reply_markup=main_keyboard()
        )

    @dp.message(F.text == BTN_DELETE)
    async def delete_history(message: Message) -> None:
        storage.delete_user_data(message.from_user.id)
        await message.answer("История и сохранённые отчёты удалены из хранилища бота.", reply_markup=main_keyboard())

    @dp.callback_query(F.data == "new_bug")
    async def new_bug_callback(callback: CallbackQuery) -> None:
        sid = storage.create_session(callback.from_user.id)
        storage.save_message(sid, "bot", "Попросил описать найденную ошибку.")
        await callback.message.answer("Опишите одну ошибку обычными словами. Что произошло?", reply_markup=main_keyboard())
        await callback.answer()

    @dp.callback_query(F.data == "unknown")
    async def unknown(callback: CallbackQuery) -> None:
        session = storage.get_active_session(callback.from_user.id)
        if session and session["stage"] == "collecting":
            storage.save_message(session["id"], "user", "На вопрос бота: не знаю / не указано.")
            await process_turn(callback.message, session)
        await callback.answer()

    @dp.callback_query(F.data == "make_report")
    async def make_report(callback: CallbackQuery) -> None:
        session = storage.get_active_session(callback.from_user.id)
        if session:
            await build_report(callback.message, storage, session, session_fields(session))
        else:
            await callback.message.answer("Сначала начните новый баг.")
        await callback.answer()

    @dp.callback_query(F.data == "edit_answer")
    async def choose_answer_field(callback: CallbackQuery) -> None:
        session = storage.get_active_session(callback.from_user.id)
        if session:
            storage.update_session(session["id"], stage="editing_answer")
            await callback.message.answer("Какое поле исправить?", reply_markup=field_keyboard("answer"))
        await callback.answer()

    @dp.callback_query(F.data.startswith("answer:"))
    async def set_answer_field(callback: CallbackQuery) -> None:
        key = callback.data.split(":", 1)[1]
        session = storage.get_active_session(callback.from_user.id)
        if session and key in ALLOWED_FIELDS:
            storage.update_session(session["id"], stage="editing_answer", pending_field=key)
            await callback.message.answer(f"Напишите новое значение поля «{FIELDS[key]}».")
        await callback.answer()

    @dp.callback_query(F.data == "edit_field")
    async def choose_report_field(callback: CallbackQuery) -> None:
        session = storage.get_active_session(callback.from_user.id)
        if session:
            storage.update_session(session["id"], stage="editing_report")
            await callback.message.answer("Какое поле исправить?", reply_markup=field_keyboard("report"))
        await callback.answer()

    @dp.callback_query(F.data.startswith("report:"))
    async def set_report_field(callback: CallbackQuery) -> None:
        key = callback.data.split(":", 1)[1]
        session = storage.get_active_session(callback.from_user.id)
        if session and key in ALLOWED_FIELDS:
            storage.update_session(session["id"], stage="editing_report", pending_field=key)
            await callback.message.answer(f"Напишите новое значение поля «{FIELDS[key]}».")
        await callback.answer()

    @dp.callback_query(F.data == "download")
    async def download(callback: CallbackQuery) -> None:
        session = storage.get_active_session(callback.from_user.id)
        report = storage.db.execute("SELECT md_text FROM bug_reports WHERE session_id=?", (session["id"],)).fetchone() if session else None
        if report:
            doc = BufferedInputFile(report["md_text"].encode("utf-8"), filename="bug-report.md")
            await callback.message.answer_document(doc, caption="Ваш баг-репорт в Markdown.")
        else:
            await callback.message.answer("Сначала сформируйте отчёт.")
        await callback.answer()

    async def process_turn(message: Message, session: Any) -> None:
        current = storage.get_session(session["id"])
        if not current:
            return
        fields = session_fields(current)
        if not storage.record_request(current["user_id"], settings.user_requests_per_hour):
            await message.answer("Достигнут часовой лимит запросов. Попробуйте позже.")
            return
        try:
            result = await llm.analyze(storage.get_messages(current["id"]), fields)
        except LLMError:
            await message.answer("Модель задумалась, повторите сообщение чуть позже.")
            return
        fields = result["extracted_fields"]
        rounds = current["question_rounds"] + 1
        storage.update_session(current["id"], extracted_data=fields, question_rounds=rounds)
        if result["is_ready_for_report"] or rounds >= settings.max_question_rounds:
            await build_report(message, storage, current, fields)
            return
        question = result["next_question"].strip() or "Что происходило непосредственно перед ошибкой и что вы ожидали увидеть?"
        storage.save_message(current["id"], "bot", question)
        await message.answer(question, reply_markup=question_keyboard())

    @dp.message(F.text)
    async def handle_text(message: Message) -> None:
        text = message.text or ""
        if len(text) > settings.max_input_length:
            await message.answer(f"Сообщение слишком длинное. Максимум — {settings.max_input_length} символов.")
            return
        session = storage.get_active_session(message.from_user.id)
        if not session:
            await message.answer("Нажмите «Новый баг», чтобы начать диалог.", reply_markup=main_keyboard())
            return
        if contains_secret(text):
            await message.answer("Похоже, в сообщении есть пароль или ключ. Удалите секрет и отправьте описание без него.")
            return
        stage = session["stage"]
        if stage in ("editing_answer", "editing_report") and session["pending_field"]:
            fields = session_fields(session)
            fields[session["pending_field"]] = text.strip()
            storage.update_session(session["id"], extracted_data=fields, stage="collecting", pending_field=None)
            if stage == "editing_report":
                refreshed = storage.get_session(session["id"])
                await build_report(message, storage, refreshed, fields)
            else:
                storage.save_message(session["id"], "user", f"Исправлено поле {session['pending_field']}: {text.strip()}")
                await message.answer("Ответ обновлён. Продолжим уточнение.", reply_markup=question_keyboard())
            return
        if stage == "report":
            await message.answer("Отчёт уже готов. Используйте кнопки, чтобы исправить поле или начать новый баг.")
            return
        storage.save_message(session["id"], "user", text)
        await process_turn(message, session)

    async def cleanup_loop() -> None:
        while True:
            try:
                removed = storage.cleanup_expired()
                if removed:
                    log.info("Removed %d expired sessions", removed)
            except Exception:
                log.exception("Session cleanup failed")
            await asyncio.sleep(3600)

    cleanup_task = asyncio.create_task(cleanup_loop())
    try:
        await dp.start_polling(bot)
    finally:
        cleanup_task.cancel()
        await bot.session.close()
        storage.close()
