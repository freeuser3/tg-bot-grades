import datetime
import json
import os
from typing import List, Optional

from netschoolapi_plus import NetSchoolAPI
from netschoolapi_plus.schemas import Assignment, Day, Diary, Lesson


def load_config(path="config.json") -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


HOMEWORK_TYPE = "Домашнее задание"

INBOX_ICON_MAP = {
    "word": "📄",
    "presentation": "📽️",
    "spreadsheet": "📊",
    "archive": "📦",
    "image": "🖼️",
}

INBOX_EXTENSIONS = {
    "word": {".doc", ".docx", ".pdf"},
    "presentation": {".ppt", ".pptx"},
    "spreadsheet": {".xls", ".xlsx"},
    "archive": {".zip", ".rar", ".7z"},
    "image": {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"},
}


def attachment_icon(filename: str) -> str:
    ext = os.path.splitext(filename)[1].casefold()
    for category, extensions in INBOX_EXTENSIONS.items():
        if ext in extensions:
            return INBOX_ICON_MAP[category]
    return "📎"


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


async def fetch_report():
    config = load_config()
    ns = NetSchoolAPI("https://sgo.e-mordovia.ru")
    try:
        await ns.login(
            config["ns_login"],
            config["ns_password"],
            config["ns_school"],
        )
        report = await ns.report_studenttotal()
    finally:
        try:
            await ns.logout()
        except Exception:
            pass
    return report


async def get_grades(start: datetime.date, end: datetime.date) -> str:
    try:
        diary = await fetch_diary(start, end)
    except Exception as e:
        return f"Ошибка при получении оценок: {e}"
    return format_diary(diary)


def next_school_day(diary: Diary, start: datetime.date) -> Optional[datetime.date]:
    for day in sorted(diary.schedule, key=lambda d: d.day):
        if day.day >= start and day.lessons:
            return day.day
    return None


def collect_homework(diary: Diary, target: datetime.date) -> List[dict]:
    result: List[dict] = []
    for day in diary.schedule:
        if day.day != target:
            continue
        for lesson in sorted(day.lessons, key=lambda l: l.number):
            for assignment in lesson.assignments:
                if assignment.type == HOMEWORK_TYPE:
                    result.append({
                        "day": day.day,
                        "number": lesson.number,
                        "subject": lesson.subject,
                        "content": assignment.content,
                        "assignment_id": assignment.id,
                        "attachments": [],
                    })
    return result


def format_homework_message(diary: Diary, target: datetime.date) -> str:
    return _format_homework(collect_homework(diary, target), target)


def _format_homework(entries: List[dict], target: datetime.date) -> str:
    if not entries:
        return "На завтра домашних заданий нет."
    lines = [f"📋 Домашние задания на {target.strftime('%d.%m.%Y')}"]
    number_emoji = {1: "1️⃣", 2: "2️⃣", 3: "3️⃣", 4: "4️⃣", 5: "5️⃣",
                    6: "6️⃣", 7: "7️⃣", 8: "8️⃣", 9: "9️⃣"}
    for entry in entries:
        num = number_emoji.get(entry["number"] + 1, entry["number"] + 1)
        attachments = " | ".join(entry["attachments"])
        suffix = f"\n  {attachments}" if attachments else ""
        lines.append(f"{num} {entry['subject']}\n  {entry['content']}{suffix}")
    return "\n".join(lines)


async def fetch_homework(target: datetime.date) -> str:
    config = load_config()
    ns = NetSchoolAPI("https://sgo.e-mordovia.ru")
    try:
        await ns.login(
            config["ns_login"],
            config["ns_password"],
            config["ns_school"],
        )
        diary = await ns.diary(start=target, end=target + datetime.timedelta(days=7))
        target = next_school_day(diary, target) or target
        entries = collect_homework(diary, target)
        if entries:
            for entry in entries:
                entry["attachments"] = await _attachment_icons(ns, entry["assignment_id"])
        return _format_homework(entries, target)
    except Exception as e:
        return f"Ошибка при получении домашних заданий: {e}"
    finally:
        try:
            await ns.logout()
        except Exception:
            pass


async def _attachment_icons(ns, assignment_id: int) -> List[str]:
    try:
        attachments = await ns.attachments(assignment_id)
    except Exception:
        return []
    return [attachment_icon(a.name) for a in attachments]