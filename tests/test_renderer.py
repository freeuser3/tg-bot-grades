import datetime
import json
from io import BytesIO

import pytest
from PIL import Image

from grades import format_diary
from renderer import (
    render_diary_image,
    render_monthly_image,
    render_report_image,
)

from renderer import REPORT_TITLE, _report_meta, _truncate_text


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


def _make_fake_report():
    from netschoolapi_plus.schemas import StudentTotalReport, SubjectReport

    return StudentTotalReport(
        school="МОУ \"Лицей № 4\"",
        student="Пронюшкин Егор Николаевич",
        year="2026/2027",
        period_start=datetime.date(2026, 9, 1),
        period_end=datetime.date(2026, 11, 30),
        term="1 триместр",
        subjects=[
            SubjectReport(
                subject="Алгебра",
                marks={
                    datetime.date(2026, 9, 1): "5",
                    datetime.date(2026, 9, 3): "н",
                },
                average=4.5,
                final="4",
            ),
            SubjectReport(
                subject="Физкультура",
                marks={datetime.date(2026, 9, 2): "4"},
                average=4.0,
                final=None,
            ),
        ],
    )


def test_render_report_image_returns_png_bytes():
    data = render_report_image(_make_fake_report())
    assert isinstance(data, bytes)
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    img = Image.open(BytesIO(data))
    assert img.width == 720
    assert img.height > 100


def test_render_report_image_writes_file(tmp_path):
    out = tmp_path / "report.png"
    data = render_report_image(_make_fake_report(), output=str(out))
    assert out.exists()
    assert out.read_bytes() == data


def test_render_report_image_contains_gray_mark_for_non_numeric():
    # «н» (не был) — серый кружок #95a5a6, средний балл и итоговая — колонки
    data = render_report_image(_make_fake_report())
    img = Image.open(BytesIO(data)).convert("RGB")
    GRAY = (149, 165, 166)
    found = 0
    for y in range(img.height):
        for x in range(img.width):
            if img.getpixel((x, y)) == GRAY:
                found += 1
    assert found > 0


def test_report_meta_does_not_contain_student_name():
    meta = _report_meta(_make_fake_report())
    assert "Пронюшкин" not in meta
    assert "1 триместр" in meta
    assert "2026" in meta


def test_report_title_does_not_mention_attendance():
    assert REPORT_TITLE == "Отчёт об успеваемости"


def test_truncate_text_shortens_long_subject_to_fit_width():
    from PIL import Image, ImageDraw, ImageFont
    from renderer import _truncate_text

    fnt = ImageFont.load_default(size=18)
    img = Image.new("RGB", (500, 50))
    dr = ImageDraw.Draw(img)
    full = "Ин.яз./Английский язык"
    subj_w = int(dr.textlength(full, font=fnt) * 0.5)
    shortened = _truncate_text(dr, full, fnt, subj_w)
    assert len(shortened) < len(full)
    assert shortened.endswith("…")
    assert dr.textlength(shortened, font=fnt) <= subj_w


def test_truncate_text_keeps_short_subject_unchanged():
    from PIL import Image, ImageDraw, ImageFont
    from renderer import _truncate_text

    fnt = ImageFont.load_default(size=18)
    img = Image.new("RGB", (500, 50))
    dr = ImageDraw.Draw(img)
    assert _truncate_text(dr, "Алгебра", fnt, 210) == "Алгебра"


@pytest.mark.asyncio
async def test_fetch_report_calls_library_report_studenttotal(tmp_path):
    from unittest.mock import AsyncMock, patch

    fake_report = _make_fake_report()

    with patch("grades.load_config") as mock_cfg, \
         patch("grades.NetSchoolAPI") as mock_ns_cls:
        mock_cfg.return_value = {
            "ns_login": "user",
            "ns_password": "pass",
            "ns_school": "School",
        }
        mock_ns = AsyncMock()
        mock_ns.report_studenttotal = AsyncMock(return_value=fake_report)
        mock_ns.login = AsyncMock()
        mock_ns.logout = AsyncMock()
        mock_ns_cls.return_value = mock_ns

        from grades import fetch_report
        result = await fetch_report()
        assert result.subjects == fake_report.subjects
        mock_ns.login.assert_called_once()
        mock_ns.report_studenttotal.assert_called_once()
        mock_ns.logout.assert_called_once()


def _weekdays(year: int, month: int) -> list:
    import datetime
    day = datetime.date(year, month, 1)
    out = []
    while day.month == month:
        if day.weekday() < 5:
            out.append(day)
        day += datetime.timedelta(days=1)
    return out


def _school_report(subjects: list, period=(2026, 9, 2026, 11)):
    import datetime
    from netschoolapi_plus.schemas import StudentTotalReport
    start_y, start_m, end_y, end_m = period
    return StudentTotalReport(
        school='МОУ "Лицей № 4"',
        student="Фамилия Имя Отчество",
        year="2026/2027",
        period_start=datetime.date(start_y, start_m, 1),
        period_end=datetime.date(end_y, end_m, 28),
        term="1 триместр",
        subjects=subjects,
    )


def _subject(name: str, marks: dict, average=4.5, final=None):
    from netschoolapi_plus.schemas import SubjectReport
    return SubjectReport(subject=name, marks=marks, average=average, final=final)


def test_group_by_month_places_subject_in_every_month_it_has_marks():
    import datetime
    from renderer import _group_by_month

    report = _school_report([
        _subject("Алгебра", {
            datetime.date(2026, 9, 3): "5",
            datetime.date(2026, 10, 10): "4",
        }),
        _subject("Литература", {
            datetime.date(2026, 9, 3): "5",
            datetime.date(2026, 9, 10): "4",
        }),
    ])

    grouped = _group_by_month(report)

    assert grouped[(2026, 9)]["subjects"] == ["Алгебра", "Литература"]
    assert grouped[(2026, 10)]["subjects"] == ["Алгебра"]
    assert grouped[(2026, 9)]["days"] == [
        datetime.date(2026, 9, 3),
        datetime.date(2026, 9, 10),
    ]
    assert list(grouped) == [(2026, 9), (2026, 10)]


def test_group_by_month_collects_each_month_days_independently():
    import datetime
    from renderer import _group_by_month

    report = _school_report([
        _subject("Алгебра", {
            datetime.date(2026, 9, 1): "5",
            datetime.date(2026, 10, 5): "4",
        }),
    ])

    grouped = _group_by_month(report)

    assert grouped[(2026, 10)]["subjects"] == ["Алгебра"]
    assert grouped[(2026, 10)]["days"] == [datetime.date(2026, 10, 5)]


def test_group_by_month_returns_empty_for_report_without_marks():
    from renderer import _group_by_month
    assert _group_by_month(_school_report([])) == {}


def test_week_blocks_splits_september_weekdays_into_iso_weeks():
    import datetime
    from renderer import _week_blocks

    days = _weekdays(2026, 9)
    blocks = _week_blocks(days)

    assert len(days) == 22
    assert [len(b) for b in blocks] == [4, 5, 5, 5, 3]
    assert blocks[0] == [
        datetime.date(2026, 9, 1),
        datetime.date(2026, 9, 2),
        datetime.date(2026, 9, 3),
        datetime.date(2026, 9, 4),
    ]
    assert blocks[-1] == [
        datetime.date(2026, 9, 28),
        datetime.date(2026, 9, 29),
        datetime.date(2026, 9, 30),
    ]


def test_week_blocks_returns_empty_list_for_no_days():
    from renderer import _week_blocks
    assert _week_blocks([]) == []


def test_week_blocks_keeps_saturday_and_sunday_in_one_block():
    import datetime
    from renderer import _week_blocks

    days = [datetime.date(2026, 9, d) for d in (7, 8, 9, 10, 11, 12, 13)]
    blocks = _week_blocks(days)

    assert len(blocks) == 1
    assert blocks[0] == days


def _realistic_report():
    names = [
        "Русский язык", "Литература", "Алгебра", "Геометрия",
        "Ин.яз./Английский язык", "Физика", "Химия", "Биология",
        "История", "Обществознание", "Информатика", "Физкультура",
        "Вероятность и статистика", "Труд (технология)",
    ]
    pool = ["5", "4", "3", "5", "н", "4", "5", "4"]
    subjects = []
    for index, name in enumerate(names):
        marks = {}
        counter = 0
        for day in _weekdays(2026, 9):
            marks[day] = pool[(counter + index * 3) % len(pool)]
            counter += 1
        subjects.append(_subject(name, marks, average=4.0 + (index % 5) / 10))
    return _school_report(subjects)


def _render_september():
    from pathlib import Path
    from renderer import FONT_DIR, _group_by_month, _render_month
    report = _realistic_report()
    grouped = _group_by_month(report)
    return _render_month(report, 2026, 9, grouped[(2026, 9)],
                         Path(FONT_DIR), with_header=True)


def test_month_image_has_no_pixels_outside_the_card():
    from renderer import _report_layout
    layout = _report_layout()
    img = _render_september().convert("RGB")
    background = (244, 246, 251)
    offenders = [
        x
        for y in range(img.height)
        for x in range(layout["card_right"] + 1, img.width)
        if img.getpixel((x, y)) != background
    ]
    assert offenders == []


def test_month_image_fits_telegram_dimension_limit():
    img = _render_september()
    assert img.width + img.height <= 10000


def test_month_image_has_no_column_after_average():
    from renderer import _report_layout
    layout = _report_layout()
    img = _render_september().convert("RGB")
    allowed = {(244, 246, 251), (255, 255, 255), (221, 227, 240), (227, 232, 242)}
    offenders = [
        x
        for y in range(img.height)
        for x in range(layout["avg_x"] + layout["avg_w"], img.width)
        if img.getpixel((x, y)) not in allowed
    ]
    assert offenders == []


def test_month_image_keeps_subject_names_inside_their_column():
    from renderer import _report_layout
    layout = _report_layout()
    img = _render_september().convert("RGB")
    subject_text = (51, 65, 92)
    offenders = [
        x
        for y in range(img.height)
        for x in range(layout["grid_x"] - 4, layout["avg_x"])
        if img.getpixel((x, y)) == subject_text
    ]
    assert offenders == []


def test_month_image_renders_longest_known_subject_name_untruncated():
    from PIL import Image as PILImage, ImageDraw
    from pathlib import Path
    from renderer import FONT_DIR, FONT_NORMAL, _font, _report_layout, _truncate_text

    layout = _report_layout()
    font = _font(FONT_NORMAL, 18, Path(FONT_DIR))
    scratch = PILImage.new("RGB", (720, 60))
    draw = ImageDraw.Draw(scratch)
    assert _truncate_text(draw, "Вероятность и статистика", font,
                          layout["subj_w"] - 8) == "Вероятность и статистика"
    assert _truncate_text(draw, "Ин.яз./Английский язык", font,
                          layout["subj_w"] - 8) == "Ин.яз./Английский язык"


def test_month_image_renders_non_numeric_mark_as_gray_circle():
    img = _render_september().convert("RGB")
    gray = (149, 165, 166)
    assert any(
        img.getpixel((x, y)) == gray
        for y in range(img.height)
        for x in range(img.width)
    )


def test_month_image_draws_weekday_above_day_number():
    from renderer import _report_layout
    layout = _report_layout()
    img = _render_september().convert("RGB")
    weekday_grey = (138, 148, 168)
    number_blue = (44, 90, 160)

    def topmost(colour, x_range):
        ys = [y for y in range(img.height) for x in x_range
              if img.getpixel((x, y)) == colour]
        return min(ys) if ys else None

    column = range(layout["grid_x"], layout["grid_x"] + 56)
    weekday_top = topmost(weekday_grey, column)
    number_top = topmost(number_blue, column)

    assert weekday_top is not None
    assert number_top is not None
    assert weekday_top < number_top


def test_six_day_week_narrows_columns_without_touching_average_column():
    from pathlib import Path
    import datetime
    from renderer import (FONT_DIR, _group_by_month, _render_month,
                          _report_layout)

    days = {datetime.date(2026, 9, d): "5" for d in (7, 8, 9, 10, 11, 12, 13)}
    report = _school_report([_subject("Алгебра", days, average=5.0)])
    grouped = _group_by_month(report)
    img = _render_month(report, 2026, 9, grouped[(2026, 9)],
                        Path(FONT_DIR), with_header=True).convert("RGB")

    layout = _report_layout()
    mark_colors = {
        (39, 174, 96), (106, 176, 76), (249, 202, 36),
        (240, 147, 43), (235, 77, 75), (149, 165, 166),
    }
    offenders = [
        x
        for y in range(img.height)
        for x in range(layout["avg_x"] - 4, img.width)
        if img.getpixel((x, y)) in mark_colors
    ]
    assert offenders == []


def test_very_long_subject_name_is_truncated_and_stays_inside_column():
    from pathlib import Path
    import datetime
    from renderer import (FONT_DIR, _group_by_month, _render_month,
                          _report_layout)

    long_name = "Основы мировой художественной культуры и музыкальной литературы"
    report = _school_report([
        _subject(long_name, {datetime.date(2026, 9, 1): "5"}, average=5.0),
    ])
    grouped = _group_by_month(report)
    img = _render_month(report, 2026, 9, grouped[(2026, 9)],
                        Path(FONT_DIR), with_header=True).convert("RGB")

    layout = _report_layout()
    subject_text = (51, 65, 92)
    offenders = [
        x
        for y in range(img.height)
        for x in range(layout["grid_x"] - 4, layout["avg_x"])
        if img.getpixel((x, y)) == subject_text
    ]
    assert offenders == []


def test_month_image_keeps_bottom_padding_for_both_header_variants():
    from pathlib import Path
    from renderer import FONT_DIR, _group_by_month, _render_month, _report_layout

    layout = _report_layout()
    report = _realistic_report()
    grouped = _group_by_month(report)
    background = (244, 246, 251)

    for with_header in (True, False):
        img = _render_month(report, 2026, 9, grouped[(2026, 9)],
                            Path(FONT_DIR), with_header=with_header).convert("RGB")
        below_last_card = range(img.height - layout["padding"] + 1, img.height)
        offenders = [
            (x, y)
            for y in below_last_card
            for x in range(img.width)
            if img.getpixel((x, y)) != background
        ]
        assert offenders == [], f"content reaches the bottom padding with_header={with_header}"


def test_month_label_is_drawn_instead_of_title_when_header_is_off():
    from pathlib import Path
    from renderer import FONT_DIR, _group_by_month, _render_month

    report = _realistic_report()
    grouped = _group_by_month(report)
    img = _render_month(report, 2026, 9, grouped[(2026, 9)],
                        Path(FONT_DIR), with_header=False).convert("RGB")

    title_colour = (28, 61, 110)
    assert not any(
        img.getpixel((x, y)) == title_colour
        for y in range(img.height)
        for x in range(img.width)
    )
    header_blue = (44, 90, 160)
    assert any(
        img.getpixel((x, y)) == header_blue
        for y in range(img.height)
        for x in range(img.width)
    )
