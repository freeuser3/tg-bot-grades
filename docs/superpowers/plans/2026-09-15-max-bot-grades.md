# Бот Telegram для школьных оценок — План реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Бот в Telegram, показывающий школьные оценки из электронного дневника «Сетевой город».

**Architecture:** Два модуля — `grades.py` (логика дневника) и `bot.py` (бот Telegram). Учётные данные хранятся в `config.json`. Бот отвечает на inline-кнопку «Получить оценки» и команды.

> **Изменение по ходу работы (2026-09-16):** MAX требует бизнес-верификации
> (юрлица/ИП/самозанятые — резиденты РФ). Перешли на Telegram (aiogram 3).
> for maxapi: max_bot_token → tg_bot_token; удалены REGISTER_MAX_BOT.txt и maxapi из requirements.

**Tech Stack:** Python 3.12, `netschoolapi`, `aiogram`, `aiohttp-socks` (прокси), `pytest`.

**Spec:** `docs/superpowers/specs/2026-09-15-max-bot-grades-design.md`

---

## Структура файлов

| Файл | Ответственность |
|---|---|
| `config.json` | Учётные данные (в `.gitignore`) |
| `config.example.json` | Шаблон для репозитория |
| `grades.py` | Загрузка конфига + функция `get_grades(start, end)` |
| `bot.py` | Бот Telegram (aiogram): команды, кнопки, callback |
| `main.py` | CLI-обёртка (обновлена) |
| `tests/test_grades.py` | Unit-тесты логики форматирования |

---

### Task 1: Инфраструктура — конфигурация

**Files:**
- Create: `config.example.json`
- Create: `.gitignore`
- Modify: `.gitignore` (создать если нет)

**Interfaces:**
- Consumes: —
- Produces: файлы конфигурации

- [ ] **Step 1: Создать `.gitignore`**

```
config.json
__pycache__/
*.pyc
.venv/
```

- [ ] **Step 2: Создать `config.example.json`**

```json
{
  "ns_login": "ваш_логин",
  "ns_password": "ваш_пароль",
  "ns_school": "МОУ \"Лицей № 4\"",
  "tg_bot_token": "токен_бота_telegram"
}
```

- [ ] **Step 3: Закоммичить**

```bash
git add .gitignore config.example.json
git commit -m "feat: add config template and gitignore"
```

---

### Task 2: Модуль grades — загрузка конфига

**Files:**
- Create: `grades.py`
- Create: `tests/test_grades.py`

**Interfaces:**
- Consumes: файл `config.json`
- Produces: `load_config() -> dict`

- [ ] **Step 1: Написать тест `tests/test_grades.py`**

```python
import json
import os
import tempfile
import pytest


def test_load_config_reads_file(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({
        "ns_login": "test",
        "ns_password": "pass",
        "ns_school": "School",
        "tg_bot_token": "token123"
    }), encoding='utf-8')

    os.chdir(tmp_path)
    from grades import load_config
    result = load_config(str(config_path))

    assert result["ns_login"] == "test"
    assert result["tg_bot_token"] == "token123"
```

- [ ] **Step 2: Запустить тест — должен упасть ( grades не существует )**

Run: `pytest tests/test_grades.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'grades'`

- [ ] **Step 3: Создать `grades.py`**

```python
import json


def load_config(path="config.json") -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)
```

- [ ] **Step 4: Запустить тест — должен пройти**

Run: `pytest tests/test_grades.py -v`
Expected: PASS

- [ ] **Step 5: Закоммичить**

```bash
git add grades.py tests/test_grades.py
git commit -m "feat: add config loader"
```

---

### Task 3: Модуль grades — функция get_grades

**Files:**
- Modify: `grades.py`
- Modify: `tests/test_grades.py`

**Interfaces:**
- Consumes: `load_config()`
- Produces: `async def get_grades(start, end) -> str`

- [ ] **Step 1: Добавить тест `test_format_diary` в `tests/test_grades.py`**

```python
import datetime
from unittest.mock import AsyncMock, patch, MagicMock
from grades import format_diary


def _make_fake_diary():
    """Создаёт фейковый Diary-объект с одним уроком и одной оценкой."""
    from netschoolapi.schemas import Diary, Day, Lesson, Assignment

    lesson = Lesson(
        day=datetime.date(2026, 9, 15),
        start=datetime.time(9, 0),
        end=datetime.time(9, 45),
        room="101",
        number=1,
        subject="Алгебра",
        assignments=[
            Assignment(
                id=1,
                comment="",
                type="Домашняя работа",
                content="Упр. 5",
                mark=5,
                is_duty=False,
                deadline=datetime.date(2026, 9, 15),
            )
        ],
    )
    day = Day(lessons=[lesson], day=datetime.date(2026, 9, 15))
    diary = Diary(
        start=datetime.date(2026, 9, 15),
        end=datetime.date(2026, 9, 21),
        schedule=[day],
    )
    return diary


def test_format_diary_contains_subject_and_mark():
    diary = _make_fake_diary()
    text = format_diary(diary)
    assert "Алгебра" in text
    assert "5" in text


def test_format_diary_no_marks():
    from netschoolapi.schemas import Day, Lesson, Assignment, Diary

    lesson = Lesson(
        day=datetime.date(2026, 9, 15),
        start=datetime.time(9, 0),
        end=datetime.time(9, 45),
        room="101",
        number=1,
        subject="Физкультура",
        assignments=[
            Assignment(
                id=2,
                comment="",
                type="Ответ на уроке",
                content="",
                mark=None,
                is_duty=False,
                deadline=datetime.date(2026, 9, 15),
            )
        ],
    )
    day = Day(lessons=[lesson], day=datetime.date(2026, 9, 15))
    diary = Diary(
        start=datetime.date(2026, 9, 15),
        end=datetime.date(2026, 9, 21),
        schedule=[day],
    )
    text = format_diary(diary)
    assert "нет" in text
```

- [ ] **Step 2: Запустить тест — должен упасть (format_diary нет)**

Run: `pytest tests/test_grades.py::test_format_diary_contains_subject_and_mark -v`
Expected: FAIL — `AttributeError: module 'grades' has no attribute 'format_diary'`

- [ ] **Step 3: Добавить `format_diary` в `grades.py`**

```python
from netschoolapi.schemas import Diary


def format_diary(diary: Diary) -> str:
    lines: list[str] = []
    for day in diary.schedule:
        lines.append(f"--- {day.day} ---")
        if day.lessons:
            for lesson in day.lessons:
                marks = ", ".join(
                    str(a.mark) for a in lesson.assignments if a.mark
                )
                lines.append(f"  {lesson.subject}: оценки {marks or 'нет'}")
        else:
            lines.append("  выходной / нет занятий")
    return "\n".join(lines)
```

- [ ] **Step 4: Запустить тест — должен пройти**

Run: `pytest tests/test_grades.py -v`
Expected: PASS

- [ ] **Step 5: Закоммичить**

```bash
git add grades.py tests/test_grades.py
git commit -m "feat: add format_diary with tests"
```

---

### Task 4: Модуль grades — асинхронный get_grades

**Files:**
- Modify: `grades.py`
- Modify: `tests/test_grades.py`

**Interfaces:**
- Consumes: `load_config()`, `format_diary()`
- Produces: `async def get_grades(start, end) -> str`

- [ ] **Step 1: Добавить тест в `tests/test_grades.py`**

```python
import datetime
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.mark.asyncio
async def test_get_grades_calls_netschoolapi(tmp_path):
    import json
    import os

    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({
        "ns_login": "user",
        "ns_password": "pass",
        "ns_school": "School",
        "tg_bot_token": "token",
    }), encoding="utf-8")

    fake_diary = _make_fake_diary()

    with patch("grades.load_config") as mock_cfg, \
         patch("grades.NetSchoolAPI") as mock_ns_cls:

        mock_cfg.return_value = {
            "ns_login": "user",
            "ns_password": "pass",
            "ns_school": "School",
            "tg_bot_token": "token",
        }

        mock_ns = AsyncMock()
        mock_ns.diary = AsyncMock(return_value=fake_diary)
        mock_ns.logout = AsyncMock()
        mock_ns.login = AsyncMock()
        mock_ns_cls.return_value = mock_ns

        from grades import get_grades
        result = await get_grades(
            datetime.date(2026, 9, 15),
            datetime.date(2026, 9, 21),
        )

        assert "Алгебра" in result
        mock_ns.login.assert_called_once()
        mock_ns.diary.assert_called_once()
        mock_ns.logout.assert_called_once()
```

- [ ] **Step 2: Запустить тест — должен упасть**

Run: `pytest tests/test_grades.py::test_get_grades_calls_netschoolapi -v`
Expected: FAIL — `AttributeError: module 'grades' has no attribute 'get_grades'`

- [ ] **Step 3: Добавить `get_grades` в `grades.py`**

```python
import datetime
from netschoolapi import NetSchoolAPI
from netschoolapi.schemas import Diary


async def get_grades(start: datetime.date, end: datetime.date) -> str:
    config = load_config()
    ns = NetSchoolAPI("https://sgo.e-mordovia.ru")
    try:
        await ns.login(
            config["ns_login"],
            config["ns_password"],
            config["ns_school"],
        )
        diary = await ns.diary(start=start, end=end)
    except Exception as e:
        return f"Ошибка при получении оценок: {e}"
    finally:
        try:
            await ns.logout()
        except Exception:
            pass
    return format_diary(diary)
```

- [ ] **Step 4: Установить pytest-asyncio**

Run: `pip install pytest-asyncio`
Expected: установка проходит без ошибок

- [ ] **Step 5: Запустить тест — должен пройти**

Run: `pytest tests/test_grades.py -v`
Expected: PASS

- [ ] **Step 6: Закоммичить**

```bash
git add grades.py tests/test_grades.py
git commit -m "feat: add async get_grades with mock test"
```

---

### Task 5: Рефакторинг main.py

**Files:**
- Modify: `main.py`

**Interfaces:**
- Consumes: `grades.get_grades`
- Produces: упрощённый `main.py`

- [ ] **Step 1: Обновить `main.py`**

```python
import asyncio
import datetime
import sys

from grades import get_grades

sys.stdout.reconfigure(encoding="utf-8")


async def main():
    text = await get_grades(
        datetime.date(2026, 9, 1),
        datetime.date(2026, 9, 30),
    )
    print(text)


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: Запустить — проверить что работает с реальными данными**

Run: `python main.py`
Expected: выводятся оценки за сентябрь

- [ ] **Step 3: Закоммичить**

```bash
git add main.py
git commit -m "refactor: simplify main.py to use grades module"
```

---

### Task 6: Бот Telegram — скелет с командами

**Files:**
- Create: `bot.py`

**Interfaces:**
- Consumes: `grades.get_grades()`
- Produces: бот, реагирующий на `/start`, `/оценки`, `/оценки месяц`

- [x] **Step 1: Установить aiogram**

Run: `pip install aiogram`
Expected: установка завершается без ошибок

- [x] **Step 2: Создать `bot.py`** (aiogram 3, команды + reply-клавиатура
      «📊 Получить оценки», только личные чаты -- `F.chat.type == "private"`)

```python
import asyncio
import datetime
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup

from grades import get_grades, load_config

logging.basicConfig(level=logging.INFO)
config = load_config()
dp = Dispatcher()

GET_GRADES_TEXT = "📊 Получить оценки"


def grades_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=GET_GRADES_TEXT)]],
        resize_keyboard=True,
    )


async def send_grades(message: Message, days: int):
    today = datetime.date.today()
    text = await get_grades(today - datetime.timedelta(days=days), today)
    await message.answer(text)


@dp.message(CommandStart(), F.chat.type == "private")
async def cmd_start(message: Message):
    await message.answer(
        "Привет! Нажми кнопку, чтобы получить оценки.",
        reply_markup=grades_keyboard(),
    )


@dp.message(Command("оценки"), F.chat.type == "private")
async def cmd_grades(message: Message, command: CommandObject):
    days = 30 if command.args and command.args.strip().casefold() == "месяц" else 7
    await send_grades(message, days)


@dp.message(F.text == GET_GRADES_TEXT, F.chat.type == "private")
async def on_grades_button(message: Message):
    await send_grades(message, 7)


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
```

- [x] **Step 3: Закоммичить**

```bash
git add bot.py
git commit -m "feat: add MAX bot with grades button"
```

---

### Task 7: Интеграционная проверка

**Files:**
- — проверка запуска

**Interfaces:**
- Consumes: бот + дневник
- Produces: подтверждение работоспособности

- [ ] **Step 1: Создать `config.json` из шаблона**

```bash
cp config.example.json config.json
```
Заполнить реальными данными (ns_* + tg_bot_token из @BotFather).

- [ ] **Step 2: Запустить бота**

Run: `python bot.py`
Expected: логи показывают `INFO: ... Start polling`

- [ ] **Step 3: Отправить боту в Telegram команду `/start`**
Expected: бот отвечает текстом и кнопкой «Получить оценки»

- [ ] **Step 4: Нажать кнопку «Получить оценки»**
Expected: бот присылает оценки за текущую неделю

- [ ] **Step 5: Отправить команду `/оценки месяц`**
Expected: бот присылает оценки за последние 30 дней
