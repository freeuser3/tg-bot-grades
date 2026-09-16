import asyncio
import datetime
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import BufferedInputFile, KeyboardButton, Message, ReplyKeyboardMarkup

from grades import fetch_diary, get_grades, load_config
from renderer import render_diary_image, render_monthly_image

logging.basicConfig(level=logging.INFO)
config = load_config()
dp = Dispatcher()

GET_GRADES_TEXT = "📊 Получить оценки"
GET_GRADES_MONTH_TEXT = "📊 Оценки за месяц"


def grades_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=GET_GRADES_TEXT)],
            [KeyboardButton(text=GET_GRADES_MONTH_TEXT)],
        ],
        resize_keyboard=True,
    )


async def send_grades(message: Message, start: datetime.date, end: datetime.date,
                      month: bool = False):
    output_mode = config.get("output_mode", "text")
    if output_mode == "image":
        diary = await fetch_diary(start, end)
        png = render_monthly_image(diary) if month else render_diary_image(diary)
        if png:
            title = "📊 Оценки за месяц" if month else "📊 Оценки за неделю"
            await message.answer(title)
            await message.answer_photo(BufferedInputFile(png, filename="grades.png"))
            return
        await message.answer("За указанный период оценок нет")
        return
    text = await get_grades(start, end)
    await message.answer(text)


@dp.message(CommandStart(), F.chat.type == "private")
async def cmd_start(message: Message):
    await message.answer(
        "Привет! Нажми кнопку, чтобы получить оценки.",
        reply_markup=grades_keyboard(),
    )


@dp.message(Command("оценки"), F.chat.type == "private")
async def cmd_grades(message: Message, command: CommandObject):
    today = datetime.date.today()
    if command.args and command.args.strip().casefold() == "месяц":
        start = today.replace(day=1)
        await send_grades(message, start, today, month=True)
        return
    await send_grades(message, today - datetime.timedelta(days=7), today)


@dp.message(F.text == GET_GRADES_TEXT, F.chat.type == "private")
async def on_grades_button(message: Message):
    today = datetime.date.today()
    await send_grades(message, today - datetime.timedelta(days=7), today)


@dp.message(F.text == GET_GRADES_MONTH_TEXT, F.chat.type == "private")
async def on_grades_month_button(message: Message):
    today = datetime.date.today()
    await send_grades(message, today.replace(day=1), today, month=True)


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