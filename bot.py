import asyncio
import datetime
import logging

from maxapi import Bot, Dispatcher
from maxapi.types import (
    CallbackButton,
    Command,
    CommandStart,
    MessageCallback,
    MessageCreated,
)
from maxapi.utils.inline_keyboard import InlineKeyboardBuilder

from grades import get_grades, load_config

logging.basicConfig(level=logging.INFO)
config = load_config()
bot = Bot(config["max_bot_token"])
dp = Dispatcher()


def grades_keyboard() -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()
    builder.row(CallbackButton(text="Получить оценки", payload="get_grades"))
    return builder


@dp.message_created(CommandStart())
async def cmd_start(event: MessageCreated):
    await event.message.answer(
        "Привет! Нажми кнопку, чтобы получить оценки.",
        attachments=[grades_keyboard().as_markup()],
    )


@dp.message_created(Command("оценки"))
async def cmd_grades_week(event: MessageCreated):
    today = datetime.date.today()
    text = await get_grades(today - datetime.timedelta(days=7), today)
    await event.message.answer(text)


@dp.message_created(Command("оценки месяц"))
async def cmd_grades_month(event: MessageCreated):
    today = datetime.date.today()
    text = await get_grades(today - datetime.timedelta(days=30), today)
    await event.message.answer(text)


@dp.message_callback()
async def on_callback(callback: MessageCallback):
    if callback.callback.payload == "get_grades":
        today = datetime.date.today()
        text = await get_grades(today - datetime.timedelta(days=7), today)
        chat_id, _ = callback.get_ids()
        await bot.send_message(chat_id=chat_id, text=text)


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())