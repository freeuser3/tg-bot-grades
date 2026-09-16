import asyncio
import datetime
import logging

from maxapi import Bot, Dispatcher
from maxapi.enums.chat_type import ChatType
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
    if event.message.recipient.chat_type != ChatType.DIALOG:
        return
    await event.message.answer(
        "Привет! Нажми кнопку, чтобы получить оценки.",
        attachments=[grades_keyboard().as_markup()],
    )


@dp.message_created(Command("оценки"))
async def cmd_grades(event: MessageCreated, args: list[str]):
    if event.message.recipient.chat_type != ChatType.DIALOG:
        return
    today = datetime.date.today()
    days = 30 if args and args[0].strip() == "месяц" else 7
    text = await get_grades(today - datetime.timedelta(days=days), today)
    await event.message.answer(text)


@dp.message_callback()
async def on_callback(callback: MessageCallback):
    if callback.callback.payload != "get_grades":
        return
    if callback.message is None:
        return
    if callback.message.recipient.chat_type != ChatType.DIALOG:
        return
    today = datetime.date.today()
    text = await get_grades(today - datetime.timedelta(days=7), today)
    chat_id, _ = callback.get_ids()
    await bot.send_message(chat_id=chat_id, text=text)


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())