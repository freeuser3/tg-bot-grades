import datetime
import json

from netschoolapi import NetSchoolAPI
from netschoolapi.schemas import Diary


def load_config(path="config.json") -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


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