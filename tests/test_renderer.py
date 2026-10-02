import datetime
import json
from io import BytesIO

import pytest
from PIL import Image

from grades import format_diary
from renderer import (
    RENDER_SCALE as _RENDER_SCALE,
    render_diary_image,
    render_monthly_image,
)


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


def test_mark_chunks_splits_every_eight_marked_days():
    from renderer import _mark_chunks

    days = _weekdays(2026, 9)
    blocks = _mark_chunks(days)

    assert len(days) == 22
    assert [len(b) for b in blocks] == [8, 8, 6]
    assert [day for block in blocks for day in block] == days


def test_mark_chunks_keeps_a_short_last_block():
    import datetime
    from renderer import _mark_chunks

    days = [datetime.date(2026, 9, d) for d in range(1, 11)]

    assert [len(b) for b in _mark_chunks(days)] == [8, 2]


def test_mark_chunks_returns_empty_list_for_no_days():
    from renderer import _mark_chunks
    assert _mark_chunks([]) == []


def test_mark_chunks_does_not_respect_calendar_weeks():
    import datetime
    from renderer import _mark_chunks

    days = [datetime.date(2026, 9, d) for d in (7, 8, 9, 10, 11, 12, 13, 14, 15)]
    blocks = _mark_chunks(days)

    assert [len(b) for b in blocks] == [8, 1]
    assert blocks[0][-1] == datetime.date(2026, 9, 14)
    assert blocks[1] == [datetime.date(2026, 9, 15)]


def test_block_label_spans_the_gaps_left_by_days_without_marks():
    import datetime
    from renderer import _block_label

    block = [datetime.date(2026, 9, d) for d in (1, 2, 4, 5, 6, 7, 8, 9, 10, 11)]

    assert _block_label(block) == "1–11 сен."


def test_block_rows_skip_subjects_that_were_not_marked_in_that_block():
    import datetime
    from renderer import _block_rows

    by_subject = {
        "Алгебра": {
            "marks": {datetime.date(2026, 9, 1): "5",
                      datetime.date(2026, 9, 15): "4"},
            "average": 4.5,
        },
        "Физика": {
            "marks": {datetime.date(2026, 9, 15): "3"},
            "average": 3.0,
        },
    }
    names = ["Алгебра", "Физика"]
    first = [datetime.date(2026, 9, d) for d in range(1, 9)]
    second = [datetime.date(2026, 9, d) for d in range(9, 17)]

    assert _block_rows(first, names, by_subject) == ["Алгебра"]
    assert _block_rows(second, names, by_subject) == ["Алгебра", "Физика"]


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

    column = range(layout["grid_x"], layout["grid_x"] + 60)
    weekday_top = topmost(weekday_grey, column)
    number_top = topmost(number_blue, column)

    assert weekday_top is not None
    assert number_top is not None
    assert weekday_top < number_top


def test_seven_day_block_keeps_marks_clear_of_average_column():
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


def test_widest_block_narrows_columns_to_fit_whole_grid():
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
    number_blue = (44, 90, 160)
    xs = sorted({x for y in range(img.height) for x in range(layout["grid_x"], layout["avg_x"])
                 if img.getpixel((x, y)) == number_blue})

    groups = []
    for x in xs:
        if groups and x - groups[-1][-1] <= 10:
            groups[-1].append(x)
        else:
            groups.append([x])
    assert len(groups) == 7

    centres = [(g[0] + g[-1]) / 2 for g in groups]
    gaps = [round(centres[i + 1] - centres[i]) for i in range(6)]
    expected = layout["grid_w"] // 7
    jitter = max(2, expected // 20)
    assert all(abs(gap - expected) <= jitter for gap in gaps), gaps
    assert max(groups[-1]) < layout["avg_x"] - 4


def test_very_long_subject_name_is_truncated_and_stays_inside_column():
    from pathlib import Path
    import datetime
    from renderer import (FONT_DIR, _group_by_month, _render_month,
                          _report_layout)

    long_name = "Основы мировой художественной культуры и музыкальной литературы"
    report = _school_report([
        _subject(long_name, {datetime.date(2026, 9, 1): "5"}, average=5.0),
        _subject("Физика", {datetime.date(2026, 9, 2): "5"}, average=5.0),
    ])
    grouped = _group_by_month(report)
    img = _render_month(report, 2026, 9, grouped[(2026, 9)],
                        Path(FONT_DIR), with_header=True).convert("RGB")

    layout = _report_layout()
    name_column = range(layout["padding"] + layout["card_pad"], layout["grid_x"] - 4)
    subject_text = (51, 65, 92)
    offenders = [
        x
        for y in range(img.height)
        for x in range(layout["grid_x"] - 4, layout["avg_x"])
        if img.getpixel((x, y)) == subject_text
    ]
    assert offenders == []
    assert any(
        img.getpixel((x, y)) == subject_text
        for y in range(img.height)
        for x in name_column
    )


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
    from renderer import FONT_DIR, _group_by_month, _render_month, _report_layout

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
    label_band = range(0, 62)
    label_xs = [
        x
        for y in label_band
        for x in range(img.width)
        if img.getpixel((x, y)) == header_blue
    ]
    assert label_xs
    assert max(label_xs) < _report_layout()["avg_x"]


def test_group_by_month_sorts_subjects_alphabetically_not_in_report_order():
    import datetime
    from renderer import _group_by_month

    report = _school_report([
        _subject("Русский язык", {datetime.date(2026, 9, 1): "5"}),
        _subject("Алгебра", {datetime.date(2026, 9, 2): "4"}),
    ])

    grouped = _group_by_month(report)

    assert grouped[(2026, 9)]["subjects"] == ["Алгебра", "Русский язык"]


def _trimester_report():
    marks = {}
    for month in (9, 10, 11):
        for day in _weekdays(2026, month):
            marks[day] = ["5", "4", "3", "н"][day.day % 4]
    return _school_report([_subject("Русский язык", marks, average=4.6),
                           _subject("Алгебра", marks, average=4.5)])


def test_render_report_images_returns_one_png_per_month():
    from renderer import render_report_images
    images = render_report_images(_trimester_report())
    assert len(images) == 3
    for data in images:
        assert isinstance(data, bytes)
        assert data[:8] == b"\x89PNG\r\n\x1a\n"


def test_render_report_images_orders_months_chronologically():
    import datetime
    from io import BytesIO
    from PIL import Image
    from renderer import render_report_images

    subject = _subject("Алгебра", {datetime.date(2026, 11, 3): "5",
                                    datetime.date(2026, 9, 1): "4",
                                    datetime.date(2026, 10, 2): "3"}, average=4.0)
    images = render_report_images(_school_report([subject]))

    assert len(images) == 3
    first = Image.open(BytesIO(images[0])).convert("RGB")
    assert any(first.getpixel((x, y)) == (28, 61, 110)
               for y in range(first.height) for x in range(first.width))
    for data in images[1:]:
        later = Image.open(BytesIO(data)).convert("RGB")
        assert not any(later.getpixel((x, y)) == (28, 61, 110)
                       for y in range(later.height) for x in range(later.width))


def test_render_report_images_puts_each_month_on_its_own_image():
    import datetime
    from io import BytesIO
    from pathlib import Path
    from PIL import Image
    from renderer import (FONT_DIR, _group_by_month, _render_month,
                          render_report_images)

    subject = _subject("Алгебра", {datetime.date(2026, 11, 3): "5",
                                    datetime.date(2026, 9, 1): "4",
                                    datetime.date(2026, 10, 2): "3"}, average=4.0)
    report = _school_report([subject])
    images = render_report_images(report)
    grouped = _group_by_month(report)

    assert len(images) == 3
    for index, month in enumerate((9, 10, 11)):
        expected = _render_month(report, 2026, month, grouped[(2026, month)],
                                 Path(FONT_DIR),
                                 with_header=(index == 0)).convert("RGB")
        actual = Image.open(BytesIO(images[index])).convert("RGB")
        assert actual.tobytes() == expected.tobytes(), month


def test_render_report_images_returns_single_image_for_one_month():
    import datetime
    from renderer import render_report_images
    report = _school_report([
        _subject("Алгебра", {datetime.date(2026, 11, 3): "5"}, average=5.0),
    ], period=(2026, 11, 2026, 11))
    assert len(render_report_images(report)) == 1


def test_render_report_images_returns_empty_list_for_report_without_marks():
    from renderer import render_report_images
    assert render_report_images(_school_report([])) == []


def test_month_image_renders_the_average_column_with_comma_separator():
    from pathlib import Path
    from renderer import (FONT_DIR, _group_by_month, _render_month,
                          _report_layout)

    report = _school_report([_subject("Алгебра", {
        datetime.date(2026, 9, 1): "5",
        datetime.date(2026, 9, 2): "4",
    }, average=4.5)])
    grouped = _group_by_month(report)
    img = _render_month(report, 2026, 9, grouped[(2026, 9)],
                        Path(FONT_DIR), with_header=True).convert("RGB")

    layout = _report_layout()
    column = range(layout["avg_x"], layout["avg_x"] + layout["avg_w"])
    subject_text = (51, 65, 92)
    assert any(
        img.getpixel((x, y)) == subject_text
        for y in range(img.height)
        for x in column
    )


def test_month_image_draws_the_average_column_header():
    from pathlib import Path
    from renderer import FONT_DIR, _group_by_month, _render_month, _report_layout

    report = _school_report([
        _subject("Алгебра", {datetime.date(2026, 9, 1): "5"}, average=4.5),
        _subject("Физика", {datetime.date(2026, 9, 2): "5"}, average=4.5),
    ])
    grouped = _group_by_month(report)
    img = _render_month(report, 2026, 9, grouped[(2026, 9)],
                        Path(FONT_DIR), with_header=True).convert("RGB")

    layout = _report_layout()
    header_blue = (44, 90, 160)
    column = range(layout["avg_x"], layout["avg_x"] + layout["avg_w"])
    assert any(
        img.getpixel((x, y)) == header_blue
        for y in range(img.height)
        for x in column
    )


def test_report_meta_and_title_expose_no_student_data():
    from renderer import REPORT_TITLE, _report_meta
    report = _school_report([_subject("Алгебра", {datetime.date(2026, 9, 1): "5"})])
    meta = _report_meta(report)
    assert report.student not in meta
    assert report.school not in meta
    assert "Фамилия" not in meta
    assert "Лицей" not in meta
    assert "Фамилия" not in REPORT_TITLE
    assert "Лицей" not in REPORT_TITLE
    assert "Посещаемость" not in REPORT_TITLE


def test_month_image_separates_block_cards_by_the_inter_card_gap():
    from pathlib import Path
    from renderer import FONT_DIR, _group_by_month, _render_month, _report_layout

    report = _realistic_report()
    grouped = _group_by_month(report)
    img = _render_month(report, 2026, 9, grouped[(2026, 9)],
                        Path(FONT_DIR), with_header=True).convert("RGB")

    probe = _report_layout()["grid_x"] - 12
    card_rows = [y for y in range(img.height)
                 if img.getpixel((probe, y)) == (255, 255, 255)]
    blocks = []
    current = []
    for y in card_rows:
        if current and y - current[-1] > 1:
            blocks.append(current)
            current = []
        current.append(y)
    if current:
        blocks.append(current)

    assert len(grouped[(2026, 9)]["days"]) == 22
    assert len(blocks) == 3
    for upper, lower in zip(blocks, blocks[1:]):
        gap = lower[0] - upper[-1] - 1
        assert gap >= 10, f"block cards only {gap}px apart"


def test_render_report_images_returns_empty_list_when_all_marks_are_empty():
    from renderer import render_report_images
    report = _school_report([_subject("Алгебра", {}, average=None)])
    assert render_report_images(report) == []


def test_render_report_images_accepts_custom_font_dir():
    from pathlib import Path
    from renderer import FONT_DIR, render_report_images
    images = render_report_images(_realistic_report(), font_dir=Path(FONT_DIR))
    assert len(images) == 1


def test_render_report_images_uses_the_font_dir_it_is_given(tmp_path):
    from renderer import render_report_images
    with pytest.raises(OSError):
        render_report_images(_realistic_report(), font_dir=tmp_path / "fonts")


def test_report_images_fit_telegram_dimension_limit():
    from io import BytesIO
    from PIL import Image
    from renderer import render_report_images
    images = render_report_images(_realistic_report())
    assert len(images) == 1
    for data in images:
        img = Image.open(BytesIO(data))
        assert img.width + img.height <= 10000


def _report_without_period(subjects):
    from netschoolapi_plus.schemas import StudentTotalReport
    return StudentTotalReport(
        school='МОУ "Лицей № 4"',
        student="Фамилия Имя Отчество",
        year="2026/2027",
        period_start=None,
        period_end=None,
        term="1 триместр",
        subjects=subjects,
    )


def test_report_meta_survives_missing_period_bounds():
    from renderer import _report_meta
    report = _report_without_period([
        _subject("Алгебра", {datetime.date(2026, 9, 3): "5"}),
    ])
    meta = _report_meta(report)
    assert "1 триместр" in meta
    assert "None" not in meta


def test_render_report_images_renders_when_period_bounds_are_missing():
    from io import BytesIO
    from PIL import Image
    from renderer import render_report_images
    report = _report_without_period([
        _subject("Алгебра", {datetime.date(2026, 9, 3): "5",
                              datetime.date(2026, 9, 4): "4"}),
    ])
    images = render_report_images(report)
    assert len(images) == 1
    assert Image.open(BytesIO(images[0])).width == round(720 * _RENDER_SCALE)


def _rgb(hex_color: str) -> tuple:
    return tuple(int(hex_color[i:i + 2], 16) for i in (1, 3, 5))


def _grade_colors(*grades):
    from renderer import GRADE_COLORS
    return {_rgb(GRADE_COLORS[g]) for g in grades}


NON_NUMERIC = (149, 165, 166)


def _cell_image(marks: dict, subjects=None, *, table: bool = False):
    from pathlib import Path
    from renderer import FONT_DIR, _group_by_month, _render_month
    if subjects is None:
        subjects = [_subject("Алгебра", marks, average=4.5)]
        if table:
            subjects = subjects + [_subject("Физика",
                                             {datetime.date(2026, 9, 2): "н"},
                                             average=4.0)]
    report = _school_report(subjects)
    grouped = _group_by_month(report)
    return _render_month(report, 2026, 9, grouped[(2026, 9)],
                         Path(FONT_DIR), with_header=True).convert("RGB")


def _color_bbox(img, colors):
    return _blend_bbox(img, colors, tolerance=0)


def _blend_bbox(img, colors, tolerance=24):
    xs = []
    ys = []
    for y in range(img.height):
        for x in range(img.width):
            pixel = img.getpixel((x, y))
            if any(max(abs(a - b) for a, b in zip(pixel, color)) <= tolerance
                   for color in colors):
                xs.append(x)
                ys.append(y)
    if not xs:
        return None
    return min(xs), min(ys), max(xs), max(ys)


@pytest.mark.parametrize("value,expected", [
    ("5", ["5"]),
    ("5/4", ["5", "4"]),
    ("5 4", ["5", "4"]),
    ("5,4", ["5", "4"]),
    ("н/б", ["н", "б"]),
    ("осв", ["осв"]),
    ("", []),
])
def test_split_marks_separates_several_marks_in_one_cell(value, expected):
    from renderer import _split_marks
    assert _split_marks(value) == expected


def test_report_layout_is_scaled_up_from_the_base_measurements():
    from renderer import RENDER_SCALE, _report_layout

    layout = _report_layout()

    assert RENDER_SCALE > 1
    assert layout["w"] == round(720 * RENDER_SCALE)
    assert layout["padding"] == round(32 * RENDER_SCALE)
    assert layout["card_pad"] == round(24 * RENDER_SCALE)
    assert layout["subj_w"] == round(240 * RENDER_SCALE)
    assert layout["avg_w"] == round(52 * RENDER_SCALE)
    assert layout["grid_x"] - layout["subj_w"] - layout["padding"] - layout["card_pad"] == layout["gap"]


def test_september_image_is_wider_than_the_base_width():
    from renderer import RENDER_SCALE

    assert _render_september().width == round(720 * RENDER_SCALE)


def test_marks_are_drawn_bigger_than_the_base_grid():
    img = _cell_image({datetime.date(2026, 9, 1): "5"}, table=True)
    box = _blend_bbox(img, _grade_colors(5))
    diameter = box[2] - box[0] + 1
    assert diameter >= 30, diameter


def test_mark_circle_edges_are_anti_aliased_instead_of_stepped():
    img = _cell_image({datetime.date(2026, 9, 1): "5"}, table=True)
    left, top, right, bottom = _color_bbox(img, _grade_colors(5))
    edge_row = (top + bottom) // 2

    outside = img.getpixel((left - 1, edge_row))
    inside = img.getpixel((left, edge_row))

    assert outside != (255, 255, 255), "circle edge is a hard cut, no blending"
    assert outside != inside, "edge pixel is the same flat colour as the fill"


def test_two_marks_in_one_day_share_a_single_circle():
    from renderer import _report_layout
    single = _color_bbox(_cell_image({datetime.date(2026, 9, 1): "5"}, table=True),
                         _grade_colors(5))
    pair = _color_bbox(_cell_image({datetime.date(2026, 9, 1): "5/4"}, table=True),
                       _grade_colors(5, 4))
    edge = round(3 * _RENDER_SCALE)
    assert single is not None
    assert pair is not None
    assert pair[0] - single[0] <= edge and single[2] - pair[2] <= edge, (single, pair)
    assert (pair[2] - pair[0]) - (single[2] - single[0]) <= round(4 * _RENDER_SCALE)
    layout = _report_layout()
    assert layout["padding"] < pair[0] and pair[2] < layout["card_right"]


def test_three_marks_in_one_day_share_a_single_circle():
    single = _color_bbox(_cell_image({datetime.date(2026, 9, 1): "5"}, table=True),
                         _grade_colors(5))
    triple = _color_bbox(
        _cell_image({datetime.date(2026, 9, 1): "5/4/3"}, table=True),
        _grade_colors(5, 4, 3))
    edge = round(3 * _RENDER_SCALE)
    assert triple is not None
    assert triple[0] - single[0] <= edge and single[2] - triple[2] <= edge, (single, triple)


def test_four_marks_in_one_day_draw_a_pill_wider_than_a_circle():
    from renderer import _report_layout
    single = _color_bbox(_cell_image({datetime.date(2026, 9, 1): "5"}, table=True),
                         _grade_colors(5))
    pill = _color_bbox(_cell_image({datetime.date(2026, 9, 1): "5/4/3/2"}, table=True),
                       {NON_NUMERIC})
    assert pill is not None
    assert pill[2] - pill[0] - (single[2] - single[0]) > 20 * _RENDER_SCALE
    layout = _report_layout()
    assert pill[0] > layout["grid_x"] - 4 and pill[2] < layout["avg_x"]


def test_single_day_block_is_drawn_as_a_list_without_a_grid():
    from renderer import _report_layout
    layout = _report_layout()
    img = _cell_image({datetime.date(2026, 9, 1): "5"})

    dividers = [(x, y) for y in range(img.height) for x in range(img.width)
                if img.getpixel((x, y)) == (227, 232, 242)]
    mark = _color_bbox(img, _grade_colors(5))

    assert dividers == []
    assert mark is not None
    assert mark[0] < layout["grid_x"]


def test_two_day_block_is_drawn_as_a_grid_with_dividers():
    from renderer import _report_layout
    layout = _report_layout()
    img = _cell_image({datetime.date(2026, 9, 1): "5",
                       datetime.date(2026, 9, 2): "4"})

    dividers = [x for y in range(img.height) for x in range(img.width)
                if img.getpixel((x, y)) == (227, 232, 242)]
    mark = _color_bbox(img, _grade_colors(5))

    assert len(set(dividers)) == 2
    assert mark is not None
    assert mark[0] > layout["grid_x"] - 4


def test_single_day_list_gives_long_subject_names_more_room_than_the_grid():
    from renderer import _report_layout
    layout = _report_layout()
    subject_text = (51, 65, 92)
    long_name = "Основы мировой художественной культуры и музыкальной литературы"
    day_one = {datetime.date(2026, 9, 1): "5"}
    as_grid = _cell_image(
        {}, subjects=[_subject(long_name, dict(day_one), average=5.0),
                      _subject("Физика", {datetime.date(2026, 9, 2): "5"},
                               average=5.0)])
    as_list = _cell_image({}, subjects=[_subject(long_name, dict(day_one),
                                                 average=5.0)])

    def rightmost_name_pixel(img, limit):
        xs = [x for y in range(img.height) for x in range(limit)
              if img.getpixel((x, y)) == subject_text]
        assert xs
        return max(xs)

    grid_right = rightmost_name_pixel(as_grid, layout["grid_x"] - 4)
    list_right = rightmost_name_pixel(as_list,
                                      layout["card_right"] - layout["card_pad"])

    assert list_right - grid_right > 200, (grid_right, list_right)


def test_two_subject_rows_with_the_same_name_keep_every_mark():
    merged = _cell_image(
        {},
        subjects=[
            _subject("Алгебра", {datetime.date(2026, 9, 1): "5"}, average=4.5),
            _subject("Алгебра", {datetime.date(2026, 9, 2): "4"}, average=4.5),
        ])
    assert _color_bbox(merged, _grade_colors(5)) is not None
    assert _color_bbox(merged, _grade_colors(4)) is not None
    single_row = _cell_image(
        {},
        subjects=[_subject("Алгебра", {datetime.date(2026, 9, 1): "5",
                                       datetime.date(2026, 9, 2): "4"},
                           average=4.5)])
    assert merged.height == single_row.height
