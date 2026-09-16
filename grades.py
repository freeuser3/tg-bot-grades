import json

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