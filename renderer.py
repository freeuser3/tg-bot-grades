import datetime
import math
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

REPORT_TITLE = "Отчёт об успеваемости"

RENDER_SCALE = 1.5
AA_SCALE = 4
BASE_MARK_SIZE = 26
CARD_BG = "#ffffff"

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


def _is_numeric_mark(mark: str) -> bool:
    return mark.strip() in {"1", "2", "3", "4", "5"}


def _truncate_text(draw, text: str, fnt, max_w: int) -> str:
    if draw.textlength(text, font=fnt) <= max_w:
        return text
    ellipsis = "…"
    low, high = 1, len(text)
    result = text[: max(1, len(text) - 1)] + ellipsis
    while low <= high:
        mid = (low + high) // 2
        candidate = text[:mid] + ellipsis
        if draw.textlength(candidate, font=fnt) <= max_w:
            result = candidate
            low = mid + 1
        else:
            high = mid - 1
    return result


def _report_meta(report) -> str:
    def _fmt(day) -> str:
        return f"{day.day}.{day.month}.{day.year}"

    if report.period_start is None or report.period_end is None:
        return report.term or ""

    return (
        f"{report.term} · "
        f"{_fmt(report.period_start)} — {_fmt(report.period_end)}"
    )


def _group_by_month(report) -> "OrderedDict":
    from collections import OrderedDict

    buckets = OrderedDict()
    for subject in report.subjects:
        for day in subject.marks:
            entry = buckets.setdefault((day.year, day.month), {"days": set(), "subjects": []})
            entry["days"].add(day)
            if subject.subject not in entry["subjects"]:
                entry["subjects"].append(subject.subject)

    grouped = OrderedDict()
    for key in sorted(buckets):
        entry = buckets[key]
        grouped[key] = {
            "days": sorted(entry["days"]),
            "subjects": sorted(entry["subjects"]),
        }
    return grouped


def _mark_chunks(days, size: int = 8):
    days = sorted(days)
    return [days[i:i + size] for i in range(0, len(days), size)]


def _block_label(block) -> str:
    first, last = block[0], block[-1]
    return f"{first.day}–{last.day} {MONTHS[first.month - 1][:3]}."


def _block_rows(block, names, by_subject) -> list:
    days = set(block)
    rows = []
    for name in names:
        entry = by_subject.get(name)
        if entry and any(day in entry["marks"] for day in days):
            rows.append(name)
    return rows


def _report_layout() -> dict:
    s = RENDER_SCALE
    w, padding, card_pad = (int(round(v * s)) for v in (720, 32, 24))
    subj_w, gap, avg_w = (int(round(v * s)) for v in (240, 8, 52))
    inner_w = w - 2 * padding - 2 * card_pad
    grid_w = inner_w - subj_w - gap - avg_w
    grid_x = padding + card_pad + subj_w + gap
    geom = {
        "scale": s,
        "w": w,
        "padding": padding,
        "card_pad": card_pad,
        "subj_w": subj_w,
        "gap": gap,
        "avg_w": avg_w,
        "inner_w": inner_w,
        "grid_w": grid_w,
        "grid_x": grid_x,
        "avg_x": grid_x + grid_w,
        "card_right": padding + w - 2 * padding,
    }
    for key, base in (("top_pad", 24), ("card_gap", 14), ("row_gap", 8),
                      ("list_hdr_gap", 6), ("weekday_gap", 4),
                      ("card_radius", 14), ("col_max", 56), ("col_gap", 12),
                      ("mark_max", BASE_MARK_SIZE), ("mark_pad", 14)):
        geom[key] = int(round(base * s))
    return geom


def _split_marks(value: str) -> list:
    parts = [p for p in value.replace(",", " ").replace("/", " ").split() if p]
    return parts


def _mark_color(mark: str) -> str:
    if _is_numeric_mark(mark):
        return GRADE_COLORS[int(mark)]
    return "#95a5a6"


def _fit_font(draw, text: str, size: int, font_dir: Path, ratio: float = 0.62):
    unit = size / BASE_MARK_SIZE
    limit = size - 3 * unit
    floor = max(4, int(round(8 * unit)))
    fnt = _font(FONT_BOLD, max(floor, int(size * ratio)), font_dir)
    while draw.textlength(text, font=fnt) > limit and fnt.size > floor:
        fnt = _font(FONT_BOLD, fnt.size - 1, font_dir)
    return fnt


def _aa_shape(img, box, kind, fill, **kw) -> None:
    x0, y0 = int(round(box[0])), int(round(box[1]))
    x1, y1 = int(round(box[2])), int(round(box[3]))
    w, h = max(1, x1 - x0), max(1, y1 - y0)
    s = AA_SCALE
    tile = Image.new("RGB", (w * s, h * s), CARD_BG)
    td = ImageDraw.Draw(tile)
    frame = [0, 0, w * s - 1, h * s - 1]
    if kind == "wedges":
        for start, end, colour in kw["wedges"]:
            td.pieslice(frame, start, end, fill=colour)
    elif kind == "rrect":
        td.rounded_rectangle(frame, radius=int(round(kw["radius"] * s)), fill=fill)
    elif fill is not None:
        td.ellipse(frame, fill=fill)
    if kw.get("outline"):
        td.ellipse(frame, outline=kw["outline"],
                   width=int(round(kw.get("width", 1) * s)))
    img.paste(tile.resize((w, h), Image.LANCZOS), (x0, y0))


def _draw_mark_cell(img, draw, cx, cy, value, size, cell_w, font_dir: Path):
    marks = _split_marks(value)
    if not marks:
        return
    unit = size / BASE_MARK_SIZE
    count = len(marks)
    box = [cx - size / 2, cy - size / 2, cx + size / 2, cy + size / 2]

    if count == 1:
        _aa_shape(img, box, "ellipse", _mark_color(marks[0]),
                  outline="#ffffff", width=2 * unit)
        _center_text(draw, cx - size / 2, cy - size / 2, size, size, marks[0],
                     _fit_font(draw, marks[0], size, font_dir), "#ffffff")
        return

    if count >= 4:
        width = min(cell_w - 4 * unit, size * 2)
        _aa_shape(img, [cx - width / 2, cy - size / 2, cx + width / 2,
                        cy + size / 2], "rrect", "#95a5a6", radius=size / 2)
        raw = "/".join(marks)
        _center_text(draw, cx - width / 2, cy - size / 2, width, size, raw,
                     _fit_font(draw, raw, width, font_dir), "#ffffff")
        return

    step = 360 / count
    wedges = []
    for index, mark in enumerate(marks):
        start = -90 + index * step + 1.2
        wedges.append((start, start + step - 2.4, _mark_color(mark)))
    _aa_shape(img, box, "wedges", None, wedges=wedges, outline="#ffffff",
              width=2 * unit)
    if count == 2:
        draw.line([(cx, cy - size / 2 + 2 * unit), (cx, cy + size / 2 - 2 * unit)],
                  fill="#ffffff", width=max(1, int(round(unit))))
        fnt = _font(FONT_BOLD, int(size * 0.46), font_dir)
        offset = size * 0.25
        _center_text(draw, cx - offset - size / 4, cy - size / 4, size / 2,
                     size / 2, marks[0], fnt, "#ffffff")
        _center_text(draw, cx + offset - size / 4, cy - size / 4, size / 2,
                     size / 2, marks[1], fnt, "#ffffff")
    else:
        step = 360 / count
        radius = size * 0.28
        fnt = _font(FONT_BOLD, int(size * 0.38), font_dir)
        for index, mark in enumerate(marks):
            angle = math.radians(-90 + (index + 0.5) * step)
            dx = math.cos(angle) * radius
            dy = math.sin(angle) * radius
            _center_text(draw, cx + dx - size / 4, cy + dy - size / 4,
                         size / 2, size / 2, mark, fnt, "#ffffff")


def _merge_subjects(report) -> dict:
    merged = {}
    for subject in report.subjects:
        entry = merged.setdefault(subject.subject,
                                  {"marks": {}, "average": None})
        entry["marks"].update(subject.marks or {})
        if subject.average is not None:
            entry["average"] = subject.average
    return merged


def _draw_block(dr, block, rows, y, block_h, geom) -> None:
    layout = geom["layout"]
    x0 = geom["x0"]
    card_pad = geom["card_pad"]
    grid_x = geom["grid_x"]
    avg_x = geom["avg_x"]
    avg_w = geom["avg_w"]
    subj_w = geom["subj_w"]
    col_w = geom["col_w"]
    mark_size = geom["mark_size"]
    row_h = geom["row_h"]
    by_subject = geom["by_subject"]
    label_font = geom["label_font"]
    weekday_font = geom["weekday_font"]
    subject_font = geom["subject_font"]
    font_dir = geom["font_dir"]

    if len(block) == 1:
        day = block[0]
        dr.text((x0 + card_pad, y + card_pad), _day_label(day),
                font=label_font, fill="#2c5aa0")
        mark_x = x0 + card_pad + mark_size / 2
        name_x = x0 + card_pad + mark_size + layout["col_gap"]
        name_max = layout["card_right"] - card_pad - name_x
        text_h = _text_height(subject_font)
        ry = y + card_pad + geom["list_hdr_h"] + layout["row_gap"]
        for name in rows:
            mark = by_subject[name]["marks"].get(day)
            if mark is not None:
                _draw_mark_cell(geom["img"], dr, mark_x, ry + row_h / 2, mark,
                                mark_size, col_w, font_dir)
            dr.text((name_x, ry + (row_h - text_h) / 2),
                    _truncate_text(dr, name, subject_font, name_max),
                    font=subject_font, fill="#33415c")
            ry += row_h
        return

    dr.line([(grid_x - layout["weekday_gap"], y + card_pad),
             (grid_x - layout["weekday_gap"], y + block_h - card_pad)],
            fill="#e3e8f2", width=1)
    dr.line([(avg_x - layout["weekday_gap"], y + card_pad),
             (avg_x - layout["weekday_gap"], y + block_h - card_pad)],
            fill="#e3e8f2", width=1)
    dr.text((x0 + card_pad, y + card_pad), _block_label(block),
            font=label_font, fill="#2c5aa0")

    hy = y + card_pad
    for index, day in enumerate(block):
        cx = grid_x + index * col_w
        weekday = DAYS_RU[day.weekday()]
        dr.text((cx + (col_w - dr.textlength(weekday, font=weekday_font)) / 2, hy),
                weekday, font=weekday_font, fill="#8a94a8")
        number = str(day.day)
        dr.text((cx + (col_w - dr.textlength(number, font=label_font)) / 2,
                 hy + geom["weekday_h"] + layout["weekday_gap"]), number,
                font=label_font, fill="#2c5aa0")

    average_label = "Ср."
    dr.text((avg_x + (avg_w - dr.textlength(average_label, font=weekday_font)) / 2,
             hy + (geom["table_hdr_h"] - geom["weekday_h"]) / 2),
            average_label, font=weekday_font, fill="#2c5aa0")

    ry = y + card_pad + geom["table_hdr_h"] + layout["row_gap"]
    for name in rows:
        subject_obj = by_subject.get(name)
        dr.text((x0 + card_pad, ry),
                _truncate_text(dr, name, subject_font,
                               subj_w - layout["col_gap"]),
                font=subject_font, fill="#33415c")
        for index, day in enumerate(block):
            mark = subject_obj["marks"].get(day) if subject_obj else None
            if mark is None:
                continue
            cx = grid_x + index * col_w + col_w / 2
            cy = ry + row_h / 2
            _draw_mark_cell(geom["img"], dr, cx, cy, mark, mark_size, col_w,
                            font_dir)
        if subject_obj is not None and subject_obj["average"] is not None:
            average = f"{subject_obj['average']:.1f}".replace(".", ",")
            dr.text((avg_x + (avg_w - dr.textlength(average, font=subject_font)) / 2, ry),
                    average, font=subject_font, fill="#33415c")
        ry += row_h


def _render_month(report, year: int, month: int, data: dict, font_dir: Path,
                  *, with_header: bool) -> Image.Image:
    layout = _report_layout()
    s = layout["scale"]
    padding = layout["padding"]
    card_pad = layout["card_pad"]
    subj_w = layout["subj_w"]
    avg_w = layout["avg_w"]
    grid_w = layout["grid_w"]
    grid_x = layout["grid_x"]
    avg_x = layout["avg_x"]

    title_font = _font(FONT_BOLD, round(26 * s), font_dir)
    month_font = _font(FONT_BOLD, round(20 * s), font_dir)
    label_font = _font(FONT_BOLD, round(18 * s), font_dir)
    weekday_font = _font(FONT_BOLD, round(14 * s), font_dir)
    subject_font = _font(FONT_NORMAL, round(18 * s), font_dir)
    meta_font = _font(FONT_NORMAL, round(14 * s), font_dir)

    subjects = data["subjects"]
    by_subject = _merge_subjects(report)
    blocks = _mark_chunks(data["days"])
    rows_per_block = [_block_rows(block, subjects, by_subject) for block in blocks]
    max_days = max((len(block) for block in blocks), default=1)
    col_w = min(layout["col_max"], grid_w // max_days)
    mark_size = min(layout["mark_max"], col_w - layout["col_gap"])
    row_h = mark_size + layout["mark_pad"]

    weekday_h = _text_height(weekday_font, "Ag")
    label_h = _text_height(label_font, "Ag")
    table_hdr_h = weekday_h + layout["weekday_gap"] + label_h
    list_hdr_h = label_h + layout["list_hdr_gap"]
    block_heights = [
        card_pad * 2 + (list_hdr_h if len(block) == 1 else table_hdr_h)
        + layout["row_gap"] + max(len(rows), 1) * row_h
        for block, rows in zip(blocks, rows_per_block)
    ]

    if with_header:
        header_h = (_text_height(title_font, "Ag") + 6 * s
                    + _text_height(meta_font, "Ag") + 18 * s)
    else:
        header_h = _text_height(month_font, "Ag") + 18 * s

    total_h = int(round(layout["top_pad"] + header_h + sum(block_heights)
                        + layout["card_gap"] * max(len(blocks) - 1, 0) + padding))

    img = Image.new("RGB", (int(round(layout["w"])), total_h), "#f4f6fb")
    dr = ImageDraw.Draw(img)
    x0 = padding
    y = layout["top_pad"]

    if with_header:
        dr.text((x0, y), REPORT_TITLE, font=title_font, fill="#1c3d6e")
        dr.text((x0, y + _text_height(title_font, "Ag") + 6 * s),
                _report_meta(report), font=meta_font, fill="#5a6478")
    else:
        dr.text((x0, y), f"{MONTHS[month - 1].capitalize()} {year}",
                font=month_font, fill="#2c5aa0")
    y += header_h

    geom = {
        "img": img,
        "layout": layout,
        "x0": x0,
        "card_pad": card_pad,
        "subj_w": subj_w,
        "avg_w": avg_w,
        "grid_x": grid_x,
        "avg_x": avg_x,
        "col_w": col_w,
        "mark_size": mark_size,
        "row_h": row_h,
        "weekday_h": weekday_h,
        "table_hdr_h": table_hdr_h,
        "list_hdr_h": list_hdr_h,
        "by_subject": by_subject,
        "label_font": label_font,
        "weekday_font": weekday_font,
        "subject_font": subject_font,
        "font_dir": font_dir,
    }

    for block, rows, block_h in zip(blocks, rows_per_block, block_heights):
        dr.rounded_rectangle(
            [x0, y, layout["card_right"], y + block_h],
            radius=int(round(layout["card_radius"])), fill="#ffffff", outline="#dde3f0",
            width=1,
        )
        _draw_block(dr, block, rows, y, block_h, geom)
        y += block_h + layout["card_gap"]

    return img


def render_report_images(report, font_dir: Path | None = None) -> list[bytes]:
    font_dir = Path(font_dir or FONT_DIR)
    if not report.subjects or not any(s.marks for s in report.subjects):
        return []

    images = []
    for index, ((year, month), data) in enumerate(_group_by_month(report).items()):
        img = _render_month(report, year, month, data, font_dir,
                            with_header=(index == 0))
        buf = BytesIO()
        img.save(buf, format="PNG")
        images.append(buf.getvalue())
    return images
