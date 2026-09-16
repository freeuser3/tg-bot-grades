import datetime
import json
from io import BytesIO

import pytest
from PIL import Image

from grades import format_diary
from renderer import render_diary_image, render_monthly_image


def _make_fake_diary():
    from netschoolapi_plus.schemas import Diary, Day, Lesson, Assignment

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
    return Diary(
        start=datetime.date(2026, 9, 15),
        end=datetime.date(2026, 9, 21),
        schedule=[day],
    )


def _make_fake_diary_no_marks():
    from netschoolapi_plus.schemas import Diary, Day, Lesson, Assignment

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
    return Diary(
        start=datetime.date(2026, 9, 15),
        end=datetime.date(2026, 9, 21),
        schedule=[day],
    )


def test_render_diary_image_returns_png_bytes():
    diary = _make_fake_diary()
    data = render_diary_image(diary)
    assert isinstance(data, bytes)
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    img = Image.open(BytesIO(data))
    assert img.width == 720
    assert img.height > 100


def test_render_diary_image_empty_diary_returns_empty_bytes():
    diary = _make_fake_diary_no_marks()
    data = render_diary_image(diary)
    assert data == b""


def test_render_diary_image_writes_file(tmp_path):
    diary = _make_fake_diary()
    out = tmp_path / "diary.png"
    data = render_diary_image(diary, output=str(out))
    assert out.exists()
    assert out.read_bytes() == data


def test_render_monthly_image_returns_png_bytes():
    from netschoolapi_plus.schemas import Day as DayCls

    graded = _make_fake_diary().schedule[0]
    # 3 дня в разных неделях, чтобы проверить группировку по неделям
    days = [
        graded,
        DayCls(lessons=[], day=datetime.date(2026, 9, 16)),  # нет оценок
        DayCls(
            lessons=[graded.lessons[0]],  # та же Алгебра
            day=datetime.date(2026, 9, 22),
        ),
    ]
    from netschoolapi_plus.schemas import Diary
    diary = Diary(
        start=datetime.date(2026, 9, 1),
        end=datetime.date(2026, 9, 30),
        schedule=days,
    )
    data = render_monthly_image(diary)
    assert isinstance(data, bytes)
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    img = Image.open(BytesIO(data))
    assert img.width == 720
    assert img.height > 100


def test_render_monthly_image_empty_diary_returns_empty_bytes():
    data = render_monthly_image(_make_fake_diary_no_marks())
    assert data == b""


def test_render_monthly_image_writes_file(tmp_path):
    diary = _make_fake_diary()
    out = tmp_path / "monthly.png"
    data = render_monthly_image(diary, output=str(out))
    assert out.exists()
    assert out.read_bytes() == data


def test_empty_day_text_stays_inside_card():
    from netschoolapi_plus.schemas import Diary, Day

    graded = _make_fake_diary().schedule[0]
    empty_day = Day(lessons=[], day=datetime.date(2026, 9, 16))
    diary = Diary(
        start=datetime.date(2026, 9, 15),
        end=datetime.date(2026, 9, 21),
        schedule=[graded, empty_day],
    )
    data = render_diary_image(diary)
    img = Image.open(BytesIO(data)).convert("RGB")

    # цвет текста "Оценок нет" #a9aebd, фон между карточками #f4f6fb
    BAD = (169, 174, 189)
    BG = (244, 246, 251)
    found = 0
    for y in range(img.height):
        for x in range(img.width):
            p = img.getpixel((x, y))
            if p == BAD and (y + 1) < img.height and img.getpixel((x, y + 1)) == BG:
                found += 1
    # Если текст вылезает из карточки — под ним сразу фон. Не должно быть
    # ни одного пикселя текста, под которым фон.
    assert found == 0


@pytest.mark.asyncio
async def test_fetch_diary_returns_diary_object(tmp_path):
    from unittest.mock import AsyncMock, patch

    fake_diary = _make_fake_diary()

    with patch("grades.load_config") as mock_cfg, \
         patch("grades.NetSchoolAPI") as mock_ns_cls:
        mock_cfg.return_value = {
            "ns_login": "user",
            "ns_password": "pass",
            "ns_school": "School",
        }
        mock_ns = AsyncMock()
        mock_ns.diary = AsyncMock(return_value=fake_diary)
        mock_ns.login = AsyncMock()
        mock_ns.logout = AsyncMock()
        mock_ns_cls.return_value = mock_ns

        from grades import fetch_diary
        result = await fetch_diary(
            datetime.date(2026, 9, 15),
            datetime.date(2026, 9, 21),
        )
        assert result.schedule == fake_diary.schedule
        mock_ns.login.assert_called_once()
        mock_ns.diary.assert_called_once()
        mock_ns.logout.assert_called_once()


def test_format_diary_via_get_grades_mock_uses_fetch_diary(tmp_path):
    import json

    from unittest.mock import AsyncMock, patch

    # fetch_diary mocked to return fake diary
    with patch("grades.fetch_diary", new=AsyncMock(return_value=_make_fake_diary())), \
         patch("grades.load_config", return_value={"ns_login": "x", "ns_password": "y"}):
        import datetime
        from grades import get_grades
        text = __import__("asyncio").run(
            get_grades(datetime.date(2026, 9, 15), datetime.date(2026, 9, 21))
        )
        assert "Алгебра" in text
        assert "5️⃣" in text