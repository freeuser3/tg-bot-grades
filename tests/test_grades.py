import json

import pytest


@pytest.mark.asyncio
async def test_get_grades_calls_netschoolapi(tmp_path):
    import datetime
    import os
    from unittest.mock import AsyncMock, patch, MagicMock

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


def test_load_config_reads_file(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({
        "ns_login": "test",
        "ns_password": "pass",
        "ns_school": "School",
        "tg_bot_token": "token123"
    }), encoding='utf-8')

    from grades import load_config
    result = load_config(str(config_path))

    assert result["ns_login"] == "test"
    assert result["tg_bot_token"] == "token123"


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