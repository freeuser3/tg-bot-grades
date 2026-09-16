import datetime
import json

from netschoolapi_plus import NetSchoolAPI
from netschoolapi_plus.schemas import Diary


def load_config(path="config.json") -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


GRADE_EMOJI = {1: "1️⃣", 2: "2️⃣", 3: "3️⃣", 4: "4️⃣", 5: "5️⃣"}


def format_diary(diary: Diary) -> str:
    lines: list[str] = []
    for day in sorted(diary.schedule, key=lambda d: d.day):
        lines.append(f"--- {day.day} ---")
        graded = [
            lesson
            for lesson in day.lessons
            if any(a.mark for a in lesson.assignments)
        ]
        if not graded:
            lines.append("  —")
            continue
        for lesson in graded:
            marks = ", ".join(
                GRADE_EMOJI.get(a.mark, str(a.mark))
                for a in lesson.assignments
                if a.mark
            )
            lines.append(f"  {lesson.subject}: {marks}")
    return "\n".join(lines)


async def fetch_diary(start: datetime.date, end: datetime.date) -> Diary:
    config = load_config()
    ns = NetSchoolAPI("https://sgo.e-mordovia.ru")
    try:
        await ns.login(
            config["ns_login"],
            config["ns_password"],
            config["ns_school"],
        )
        diary = await ns.diary(start=start, end=end)
    finally:
        try:
            await ns.logout()
        except Exception:
            pass
    return diary


async def get_grades(start: datetime.date, end: datetime.date) -> str:
    try:
        diary = await fetch_diary(start, end)
    except Exception as e:
        return f"Ошибка при получении оценок: {e}"
    return format_diary(diary)