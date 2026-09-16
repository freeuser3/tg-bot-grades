import asyncio
import datetime
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from grades import get_grades, load_config

logging.basicConfig(level=logging.INFO)
config = load_config()
dp = Dispatcher()


def grades_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Получить оценки",
                    callback_data="get_grades",
                )
            ]
        ]
    )


@dp.message(CommandStart(), F.chat.type == "private")
async def cmd_start(message: Message):
    await message.answer(
        "Привет! Нажми кнопку, чтобы получить оценки.",
        reply_markup=grades_keyboard(),
    )


@dp.message(Command("оценки"), F.chat.type == "private")
async def cmd_grades(message: Message, command: CommandObject):
    today = datetime.date.today()
    days = 30 if command.args and command.args.strip().casefold() == "месяц" else 7
    text = await get_grades(today - datetime.timedelta(days=days), today)
    await message.answer(text)


@dp.callback_query(F.data == "get_grades")
async def on_callback(callback: CallbackQuery):
    if callback.message is None or callback.message.chat.type != "private":
        return
    await callback.answer()
    today = datetime.date.today()
    text = await get_grades(today - datetime.timedelta(days=7), today)
    await callback.message.answer(text)


async def main():
    token = config.get("tg_bot_token", "").strip()
    if not token:
        raise SystemExit(
            "В config.json не задан tg_bot_token. "
            "Создайте бота через @BotFather и вставьте токен."
        )
    session = None
    if config.get("use_proxy"):
        proxy_url = config.get("proxy_url", "").strip()
        if not proxy_url:
            raise SystemExit(
                "В config.json задан use_proxy, но не указан proxy_url."
            )
        session = AiohttpSession(proxy=proxy_url)
    bot = Bot(token, session=session)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())