import datetime
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FONT_DIR = Path(__file__).resolve().parent / "fonts"

GRADE_COLORS = {
    5: "#27ae60",
    4: "#6ab04c",
    3: "#f9ca24",
    2: "#f0932b",
    1: "#eb4d4b",
}

MONTHS = ["января", "февраля", "марта", "апреля", "мая", "июня",
          "июля", "августа", "сентября", "октября", "ноября", "декабря"]
DAYS_RU = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]

FONT_NORMAL = "NotoSans-Regular.ttf"
FONT_BOLD = "NotoSans-Bold.ttf"
FONT_ITALIC = "NotoSans-Italic.ttf"


def _font(name: str, size: int, font_dir: Path) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(font_dir / name), size)


def _day_label(iso: datetime.date) -> str:
    return f"{DAYS_RU[iso.weekday()]}, {iso.day} {MONTHS[iso.month - 1]}"


def _text_height(fnt: ImageFont.FreeTypeFont, text: str = "Ag") -> int:
    bbox = fnt.getbbox(text)
    return bbox[3] - bbox[1]


def _center_text(draw, x, y, w, h, text, fnt, fill):
    tw = draw.textlength(text, font=fnt)
    bbox = fnt.getbbox(text)
    th = bbox[3] - bbox[1]
    draw.text((x + (w - tw) / 2, y + (h - th) / 2 - bbox[1]), text, font=fnt, fill=fill)


def _draw_mark(draw, x, y, size, mark, font_dir: Path):
    col = GRADE_COLORS.get(mark, "#95a5a6")
    mf = _font(FONT_BOLD, int(size * 0.62), font_dir)
    draw.ellipse([x, y, x + size, y + size], fill=col, outline="#ffffff", width=2)
    _center_text(draw, x, y, size, size, str(mark), mf, "#ffffff")


def _render_lines(days, font_dir: Path) -> Image.Image:
    W = 720
    padding = 32
    card_pad = 24
    title_font = _font(FONT_BOLD, 32, font_dir)
    date_font = _font(FONT_BOLD, 20, font_dir)
    subject_font = _font(FONT_NORMAL, 20, font_dir)
    empty_font = _font(FONT_ITALIC, 20, font_dir)
    mark_size = 36
    lesson_h = mark_size + 18

    card_heights = []
    for day in days:
        if not day["lessons"]:
            ch = (
                card_pad * 2
                + _text_height(date_font, "Ag")
                + 8
                + _text_height(empty_font, "Оценок нет")
            )
        else:
            ch = card_pad * 2 + _text_height(date_font, "Ag") + 8 + len(day["lessons"]) * lesson_h
        card_heights.append(ch)

    title_h = _text_height(title_font, "Оценки за неделю")
    total_h = 28 + title_h + 20 + sum(card_heights) + (len(days) - 1) * 16 + padding

    img = Image.new("RGB", (W, total_h), "#f4f6fb")
    dr = ImageDraw.Draw(img)
    x0 = padding
    cw = W - 2 * padding
    y = 28

    dr.text((x0, y), "Оценки за неделю", font=title_font, fill="#1c3d6e")
    y += title_h + 20

    for i, day in enumerate(days):
        ch = card_heights[i]
        dr.rounded_rectangle([x0, y, x0 + cw, y + ch], radius=16, fill="#ffffff",
                             outline="#dde3f0", width=1)
        dr.text((x0 + card_pad, y + card_pad), _day_label(day["date"]),
                font=date_font, fill="#2c5aa0")
        if not day["lessons"]:
            ey = y + card_pad + _text_height(date_font, "Ag") + 8
            dr.text((x0 + card_pad, ey), "Оценок нет", font=empty_font, fill="#a9aebd")
        else:
            ly = y + card_pad + _text_height(date_font, "Ag") + 8
            for lesson in day["lessons"]:
                dr.text((x0 + card_pad, ly), lesson["subject"],
                        font=subject_font, fill="#33415c")
                mx = x0 + cw - card_pad - mark_size
                for mark in reversed(lesson["marks"]):
                    _draw_mark(dr, mx, ly - 2, mark_size, mark, font_dir)
                    mx -= mark_size + 8
                ly += lesson_h
        y += ch + 16

    return img


def render_diary_image(diary, font_dir: Path | None = None, output: str | None = None) -> bytes:
    """Возвращает PNG-байты картинки журнала, или None если оценок нет."""
    font_dir = font_dir or FONT_DIR

    days = []
    has_any = False
    for day in sorted(diary.schedule, key=lambda d: d.day):
        lessons = []
        for lesson in day.lessons:
            marks = [a.mark for a in lesson.assignments if a.mark]
            if marks:
                lessons.append({"subject": lesson.subject, "marks": marks})
                has_any = True
        days.append({"date": day.day, "lessons": lessons})

    if not has_any:
        return b""

    img = _render_lines(days, Path(font_dir))
    if output:
        img.save(output)
        return Path(output).read_bytes()
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _render_monthly_grid(weeks, font_dir: Path) -> Image.Image:
    W = 720
    padding = 32
    card_pad = 24
    title_font = _font(FONT_BOLD, 32, font_dir)
    date_font = _font(FONT_BOLD, 18, font_dir)
    subject_font = _font(FONT_NORMAL, 18, font_dir)
    mark_size = 26
    row_h = mark_size + 14
    col_w = 60
    subj_w = 210
    grid_x = padding + card_pad + subj_w
    card_width = W - 2 * padding

    grid_heights = []
    for week in weeks:
        nsubj = len(week["subjects"])
        gh = card_pad * 2 + _text_height(date_font, "Ag") + 8 + max(nsubj, 1) * row_h
        grid_heights.append(gh)

    title_h = _text_height(title_font, "Оценки за месяц")
    total_h = 28 + title_h + 20 + sum(grid_heights) + (len(weeks) - 1) * 16 + padding
    img = Image.new("RGB", (W, total_h), "#f4f6fb")
    dr = ImageDraw.Draw(img)
    x0 = padding
    y = 28

    dr.text((x0, y), "Оценки за месяц", font=title_font, fill="#1c3d6e")
    y += title_h + 20

    for i, week in enumerate(weeks):
        gh = grid_heights[i]
        dr.rounded_rectangle(
            [x0, y, x0 + card_width, y + gh],
            radius=16, fill="#ffffff", outline="#dde3f0", width=1,
        )
        # граница между колонкой предметов и оценками
        dr.line([(grid_x - 12, y + card_pad), (grid_x - 12, y + gh - card_pad)],
                fill="#e3e8f2", width=1)
        # заголовок недели: даты дней
        hx = grid_x
        for day in week["days"]:
            label = f"{day['date'].day} {DAYS_RU[day['date'].weekday()]}"
            tw = dr.textlength(label, font=date_font)
            dr.text(
                (hx + (col_w - tw) / 2, y + card_pad),
                label, font=date_font, fill="#2c5aa0",
            )
            hx += col_w
        # строки предметов
        ry = y + card_pad + _text_height(date_font, "Ag") + 8
        for subj in week["subjects"]:
            dr.text((x0 + card_pad, ry), subj, font=subject_font, fill="#33415c")
            sx = grid_x
            for day in week["days"]:
                marks = day["marks"].get(subj, [])[-2:]
                mx = sx + (col_w - len(marks) * (mark_size + 4) + 4) / 2
                for mark in marks:
                    _draw_mark(dr, mx, ry + (row_h - mark_size) / 2, mark_size, mark, font_dir)
                    mx += mark_size + 4
                sx += col_w
            ry += row_h
        y += gh + 16

    return img


def render_monthly_image(diary, font_dir: Path | None = None, output: str | None = None) -> bytes:
    """Возвращает PNG-байты компактной таблицы оценок за месяц (стопка недель)."""
    font_dir = font_dir or FONT_DIR

    from collections import OrderedDict

    has_any = False
    week_map = OrderedDict()
    for day in sorted(diary.schedule, key=lambda d: d.day):
        y, w, _ = day.day.isocalendar()
        key = (y, w)
        week = week_map.setdefault(key, {"days": [], "subjects": OrderedDict()})
        day_marks = {}
        for lesson in day.lessons:
            marks = [a.mark for a in lesson.assignments if a.mark]
            if marks:
                day_marks[lesson.subject] = marks
                has_any = True
        if day_marks:
            week["days"].append({"date": day.day, "marks": day_marks})

    if not has_any:
        return b""

    weeks = []
    for key in week_map:
        week = week_map[key]
        subjects = []
        for d in week["days"]:
            for s in d["marks"]:
                if s not in subjects:
                    subjects.append(s)
        weeks.append({"days": week["days"], "subjects": sorted(subjects)})

    img = _render_monthly_grid(weeks, Path(font_dir))
    if output:
        img.save(output)
        return Path(output).read_bytes()
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()