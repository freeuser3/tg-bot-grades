import datetime
from unittest.mock import AsyncMock, patch

import pytest

from grades import (
    attachment_icon,
    collect_homework,
    next_school_day,
)

import grades


def _make_diary_for(date, lessons):
    from netschoolapi_plus.schemas import Day, Diary

    return Diary(
        start=date,
        end=date + datetime.timedelta(days=13),
        schedule=[Day(lessons=lessons, day=date)],
    )


def _make_lesson(number, subject, assignments):
    from netschoolapi_plus.schemas import Lesson

    return Lesson(
        day=datetime.date(2026, 9, 21),
        start=datetime.time(9, 0),
        end=datetime.time(9, 45),
        room="101",
        number=number,
        subject=subject,
        assignments=assignments,
    )


def _make_assignment(assignment_id, type_, content, deadline):
    from netschoolapi_plus.schemas import Assignment

    return Assignment(
        id=assignment_id,
        comment="",
        type=type_,
        content=content,
        mark=None,
        is_duty=False,
        deadline=deadline,
    )


def test_collect_homework_takes_only_homework_type():
    day = datetime.date(2026, 9, 21)
    lesson = _make_lesson(
        1,
        "Алгебра",
        [
            _make_assignment(1, "Домашнее задание", "Упр. 5", day),
            _make_assignment(2, "Ответ на уроке", "---Не указана---", day),
        ],
    )
    diary = _make_diary_for(day, [lesson])

    result = collect_homework(diary, day)

    assert len(result) == 1
    assert result[0]["subject"] == "Алгебра"
    assert result[0]["content"] == "Упр. 5"
    assert result[0]["number"] == 1
    assert result[0]["day"] == day


def test_collect_homework_ignores_day_without_lessons():
    from netschoolapi_plus.schemas import Day, Diary

    sunday = datetime.date(2026, 9, 20)
    saturday = datetime.date(2026, 9, 19)
    diary = Diary(
        start=saturday,
        end=sunday,
        schedule=[
            Day(lessons=[], day=sunday),
            Day(lessons=[], day=saturday),
        ],
    )

    result = collect_homework(diary, saturday)

    assert result == []


def test_next_school_day_skips_weekend():
    from netschoolapi_plus.schemas import Day, Diary

    saturday = datetime.date(2026, 9, 19)
    sunday = datetime.date(2026, 9, 20)
    monday = datetime.date(2026, 9, 21)
    diary = Diary(
        start=saturday,
        end=monday,
        schedule=[
            Day(lessons=[], day=sunday),
            Day(
                lessons=[
                    _make_lesson(1, "Алгебра", [_make_assignment(1, "Домашнее задание", "Упр. 5", monday)])
                ],
                day=monday,
            ),
        ],
    )

    assert next_school_day(diary, saturday) == monday
    assert next_school_day(diary, monday) == monday


def test_next_school_day_none_when_no_lessons():
    from netschoolapi_plus.schemas import Day, Diary

    sunday = datetime.date(2026, 9, 20)
    diary = Diary(
        start=sunday,
        end=sunday + datetime.timedelta(days=2),
        schedule=[Day(lessons=[], day=d) for d in [sunday, sunday + datetime.timedelta(days=1)]],
    )

    assert next_school_day(diary, sunday) is None


def test_attachment_icons():
    assert attachment_icon("photo.png") == "🖼️"
    assert attachment_icon("photo.JPG") == "🖼️"
    assert attachment_icon("doc.docx") == "📄"
    assert attachment_icon("doc.doc") == "📄"
    assert attachment_icon("file.PDF") == "📄"
    assert attachment_icon("presentation.pptx") == "📽️"
    assert attachment_icon("presentation.ppt") == "📽️"
    assert attachment_icon("table.xlsx") == "📊"
    assert attachment_icon("archive.rar") == "📦"
    assert attachment_icon("archive.zip") == "📦"
    assert attachment_icon("archive.7z") == "📦"
    assert attachment_icon("notes.txt") == "📎"
    assert attachment_icon("no_extension") == "📎"


def test_format_homework_no_assignments():
    day = datetime.date(2026, 9, 21)
    lesson = _make_lesson(1, "Алгебра", [_make_assignment(1, "Ответ на уроке", "---", day)])
    diary = _make_diary_for(day, [lesson])

    text = grades.format_homework_message(diary, day)

    assert "нет" in text.casefold()


def test_format_homework_multiple_subjects_sorted_by_number():
    from netschoolapi_plus.schemas import Lesson

    day = datetime.date(2026, 9, 21)

    def make_lesson(number, subject):
        return Lesson(
            day=day,
            start=datetime.time(9, 0),
            end=datetime.time(9, 45),
            room="101",
            number=number,
            subject=subject,
            assignments=[_make_assignment(number, "Домашнее задание", f"Задание {number}", day)],
        )

    diary = _make_diary_for(
        day,
        [make_lesson(1, "Физика"), make_lesson(0, "Алгебра")],
    )

    text = grades.format_homework_message(diary, day)

    assert text.index("1️⃣") < text.index("2️⃣")
    assert "Алгебра" in text
    assert "Задание 0" in text


def test_format_homework_lesson_number_is_one_based():
    day = datetime.date(2026, 9, 21)
    lesson = _make_lesson(0, "Алгебра", [_make_assignment(1, "Домашнее задание", "Упр. 5", day)])
    diary = _make_diary_for(day, [lesson])

    text = grades.format_homework_message(diary, day)

    assert "1️⃣ Алгебра" in text


@pytest.mark.asyncio
async def test_fetch_homework_calls_diary_and_logout(tmp_path):
    import json

    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({
        "ns_login": "user",
        "ns_password": "pass",
        "ns_school": "School",
        "tg_bot_token": "token",
    }), encoding="utf-8")

    target = datetime.date(2026, 9, 21)
    lesson = _make_lesson(
        1,
        "Алгебра",
        [_make_assignment(1, "Домашнее задание", "Упр. 5", target)],
    )
    fake_diary = _make_diary_for(target, [lesson])

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
        mock_ns_cls.return_value = mock_ns

        result = await grades.fetch_homework(target)

        assert "Алгебра" in result
        assert "Упр. 5" in result
        mock_ns.login.assert_called_once()
        mock_ns.diary.assert_called_once_with(
            start=target, end=target + datetime.timedelta(days=7)
        )
        mock_ns.logout.assert_called_once()


@pytest.mark.asyncio
async def test_fetch_homework_shows_attachment_icons(tmp_path):
    import json

    from netschoolapi_plus.schemas import Attachment

    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({
        "ns_login": "user",
        "ns_password": "pass",
        "ns_school": "School",
        "tg_bot_token": "token",
    }), encoding="utf-8")

    target = datetime.date(2026, 9, 21)
    lesson = _make_lesson(
        1,
        "Алгебра",
        [_make_assignment(1, "Домашнее задание", "Упр. 5", target)],
    )
    fake_diary = _make_diary_for(target, [lesson])

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
        mock_ns.attachments = AsyncMock(return_value=[
            Attachment(id=10, name="задание.docx", description=""),
            Attachment(id=11, name="картинка.png", description=""),
        ])
        mock_ns_cls.return_value = mock_ns

        result = await grades.fetch_homework(target)

        assert "📄" in result
        assert "🖼️" in result
        mock_ns.attachments.assert_called_once_with(1)