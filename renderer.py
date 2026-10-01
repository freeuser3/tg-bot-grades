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

REPORT_TITLE = "Отчёт об успеваемости"

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
    return (
        f"{report.term} · "
        f"{report.period_start.day}.{report.period_start.month}.{report.period_start.year}"
        f" — {report.period_end.day}.{report.period_end.month}.{report.period_end.year}"
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


def _week_blocks(days):
    blocks = []
    current_key = None
    for day in days:
        key = day.isocalendar()[:2]
        if key != current_key:
            blocks.append([])
            current_key = key
        blocks[-1].append(day)
    return blocks


def _report_layout() -> dict:
    w, padding, card_pad = 720, 32, 24
    subj_w, gap, avg_w = 240, 8, 52
    inner_w = w - 2 * padding - 2 * card_pad
    grid_w = inner_w - subj_w - gap - avg_w
    grid_x = padding + card_pad + subj_w + gap
    return {
        "w": w,
        "padding": padding,
        "card_pad": card_pad,
        "subj_w": subj_w,
        "gap": gap,
        "avg_w": avg_w,
        "grid_w": grid_w,
        "grid_x": grid_x,
        "avg_x": grid_x + grid_w,
        "card_right": padding + w - 2 * padding,
    }


def _render_month(report, year: int, month: int, data: dict, font_dir: Path,
                  *, with_header: bool) -> Image.Image:
    layout = _report_layout()
    padding = layout["padding"]
    card_pad = layout["card_pad"]
    subj_w = layout["subj_w"]
    avg_w = layout["avg_w"]
    grid_w = layout["grid_w"]
    grid_x = layout["grid_x"]
    avg_x = layout["avg_x"]

    title_font = _font(FONT_BOLD, 26, font_dir)
    month_font = _font(FONT_BOLD, 20, font_dir)
    label_font = _font(FONT_BOLD, 18, font_dir)
    weekday_font = _font(FONT_BOLD, 14, font_dir)
    subject_font = _font(FONT_NORMAL, 18, font_dir)
    meta_font = _font(FONT_NORMAL, 14, font_dir)

    subjects = data["subjects"]
    blocks = _week_blocks(data["days"])
    max_days = max((len(block) for block in blocks), default=1)
    col_w = min(56, grid_w // max_days)
    mark_size = min(26, col_w - 12)
    mark_font = _font(FONT_BOLD, int(mark_size * 0.62), font_dir)
    row_h = mark_size + 14

    weekday_h = _text_height(weekday_font, "Ag")
    label_h = _text_height(label_font, "Ag")
    hdr_h = weekday_h + 4 + label_h
    block_h = card_pad * 2 + hdr_h + 8 + max(len(subjects), 1) * row_h

    if with_header:
        header_h = _text_height(title_font, "Ag") + 6 + _text_height(meta_font, "Ag") + 18
    else:
        header_h = _text_height(month_font, "Ag") + 18

    total_h = (24 + header_h + len(blocks) * block_h
               + max(len(blocks) - 1, 0) * 14 + padding)

    img = Image.new("RGB", (layout["w"], total_h), "#f4f6fb")
    dr = ImageDraw.Draw(img)
    x0 = padding
    y = 24

    if with_header:
        dr.text((x0, y), REPORT_TITLE, font=title_font, fill="#1c3d6e")
        dr.text((x0, y + _text_height(title_font, "Ag") + 6), _report_meta(report),
                font=meta_font, fill="#5a6478")
    else:
        dr.text((x0, y), f"{MONTHS[month - 1].capitalize()} {year}",
                font=month_font, fill="#2c5aa0")
    y += header_h

    by_subject = {s.subject: s for s in report.subjects}

    for block in blocks:
        dr.rounded_rectangle(
            [x0, y, layout["card_right"], y + block_h],
            radius=14, fill="#ffffff", outline="#dde3f0", width=1,
        )
        dr.line([(grid_x - 4, y + card_pad), (grid_x - 4, y + block_h - card_pad)],
                fill="#e3e8f2", width=1)
        dr.line([(avg_x - 4, y + card_pad), (avg_x - 4, y + block_h - card_pad)],
                fill="#e3e8f2", width=1)

        first, last = block[0], block[-1]
        dr.text((x0 + card_pad, y + card_pad),
                f"{first.day}–{last.day} {MONTHS[first.month - 1][:3]}.",
                font=label_font, fill="#2c5aa0")

        hy = y + card_pad
        for index, day in enumerate(block):
            cx = grid_x + index * col_w
            weekday = DAYS_RU[day.weekday()]
            dr.text((cx + (col_w - dr.textlength(weekday, font=weekday_font)) / 2, hy),
                    weekday, font=weekday_font, fill="#8a94a8")
            number = str(day.day)
            dr.text((cx + (col_w - dr.textlength(number, font=label_font)) / 2,
                     hy + weekday_h + 4), number, font=label_font, fill="#2c5aa0")

        average_label = "Ср."
        dr.text((avg_x + (avg_w - dr.textlength(average_label, font=weekday_font)) / 2,
                 hy + (hdr_h - weekday_h) / 2),
                average_label, font=weekday_font, fill="#2c5aa0")

        ry = y + card_pad + hdr_h + 8
        for name in subjects:
            subject_obj = by_subject.get(name)
            dr.text((x0 + card_pad, ry),
                    _truncate_text(dr, name, subject_font, subj_w - 8),
                    font=subject_font, fill="#33415c")
            for index, day in enumerate(block):
                mark = subject_obj.marks.get(day) if subject_obj else None
                if mark is None:
                    continue
                mx = grid_x + index * col_w + (col_w - mark_size) / 2
                my = ry + (row_h - mark_size) / 2
                colour = GRADE_COLORS[int(mark)] if _is_numeric_mark(mark) else "#95a5a6"
                dr.ellipse([mx, my, mx + mark_size, my + mark_size],
                           fill=colour, outline="#ffffff", width=2)
                _center_text(dr, mx, my, mark_size, mark_size, mark,
                             mark_font, "#ffffff")
            if subject_obj is not None and subject_obj.average is not None:
                average = f"{subject_obj.average:.1f}".replace(".", ",")
                dr.text((avg_x + (avg_w - dr.textlength(average, font=subject_font)) / 2, ry),
                        average, font=subject_font, fill="#33415c")
            ry += row_h
        y += block_h + 14

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


def _render_report_table(report, font_dir: Path) -> Image.Image:
    W = 720
    padding = 32
    card_pad = 24
    title_font = _font(FONT_BOLD, 32, font_dir)
    header_font = _font(FONT_BOLD, 18, font_dir)
    subject_font = _font(FONT_NORMAL, 18, font_dir)
    meta_font = _font(FONT_NORMAL, 16, font_dir)
    mark_size = 26
    row_h = mark_size + 14
    col_w = 40
    subj_w = 210
    avg_w = 52
    final_w = 52

    from collections import OrderedDict

    month_map = OrderedDict()
    for subject in report.subjects:
        if not subject.marks:
            continue
        for day, mark in subject.marks.items():
            key = (day.year, day.month)
            month_map.setdefault(key, {"days": set(), "subjects": []})
            month_map[key]["days"].add(day)
        if subject.subject not in month_map[(day.year, day.month)]["subjects"]:
            month_map[(day.year, day.month)]["subjects"].append(subject.subject)
    for key in month_map:
        month_map[key]["days"] = sorted(month_map[key]["days"], key=lambda d: d)
    for key in month_map:
        month_map[key]["subjects"].sort()

    title_h = _text_height(title_font, "Отчёт об успеваемости")
    meta_h = _text_height(meta_font, "Ag")
    months = []
    for (year, month), data in month_map.items():
        months.append((year, month, data))
    table_h = card_pad * 2 + _text_height(header_font, "Ag") + 8 + len(data["subjects"]) * row_h
    total_h = (
        28 + title_h + 8 + meta_h + 20
        + sum(card_pad * 2 + _text_height(header_font, "Ag") + 8 + len(m["subjects"]) * row_h
              for _, _, m in months)
        + (len(months) - 1) * 16
        + padding
    )

    img = Image.new("RGB", (W, total_h), "#f4f6fb")
    dr = ImageDraw.Draw(img)
    x0 = padding
    y = 28

    dr.text((x0, y), REPORT_TITLE, font=title_font, fill="#1c3d6e")
    y += title_h + 8
    meta = _report_meta(report)
    dr.text((x0, y), meta, font=meta_font, fill="#5a6478")
    y += meta_h + 20

    grid_x = padding + card_pad + subj_w
    avg_x = W - padding - card_pad - avg_w - final_w

    for year, month, data in months:
        n_subjects = max(len(data["subjects"]), 1)
        gh = card_pad * 2 + _text_height(header_font, "Ag") + 8 + n_subjects * row_h
        dr.rounded_rectangle([x0, y, x0 + W - 2 * padding, y + gh],
                             radius=16, fill="#ffffff", outline="#dde3f0", width=1)
        dr.line([(grid_x - 12, y + card_pad), (grid_x - 12, y + gh - card_pad)],
                fill="#e3e8f2", width=1)
        dr.line([(avg_x - 8, y + card_pad), (avg_x - 8, y + gh - card_pad)],
                fill="#e3e8f2", width=1)

        month_label = f"{MONTHS[month - 1].capitalize()} {year}"
        dr.text((x0 + card_pad, y + card_pad), month_label,
                font=header_font, fill="#2c5aa0")
        hx = grid_x
        for day in data["days"]:
            label = str(day.day)
            tw = dr.textlength(label, font=header_font)
            dr.text((hx + (col_w - tw) / 2, y + card_pad), label,
                    font=header_font, fill="#2c5aa0")
            hx += col_w
        cx = avg_x + (avg_w - dr.textlength("Ср.", font=header_font)) / 2
        dr.text((cx, y + card_pad), "Ср.", font=header_font, fill="#2c5aa0")
        fx = avg_x + avg_w + (final_w - dr.textlength("Итог", font=header_font)) / 2
        dr.text((fx, y + card_pad), "Итог", font=header_font, fill="#2c5aa0")

        ry = y + card_pad + _text_height(header_font, "Ag") + 8
        by_subject = {}
        for subject in report.subjects:
            if subject.subject not in data["subjects"]:
                continue
            by_subject[subject.subject] = subject
        for subject in data["subjects"]:
            subj_obj = by_subject[subject]
            label = _truncate_text(dr, subject, subject_font, subj_w - 8)
            dr.text((x0 + card_pad, ry), label, font=subject_font, fill="#33415c")
            sx = grid_x
            for day in data["days"]:
                mark = subj_obj.marks.get(day)
                if mark is not None:
                    if _is_numeric_mark(mark):
                        _draw_mark(dr, sx + (col_w - mark_size) / 2, ry + (row_h - mark_size) / 2,
                                   mark_size, int(mark), font_dir)
                    else:
                        col = "#95a5a6"
                        mf = _font(FONT_BOLD, int(mark_size * 0.62), font_dir)
                        dr.ellipse([sx + (col_w - mark_size) / 2, ry + (row_h - mark_size) / 2,
                                    sx + (col_w - mark_size) / 2 + mark_size,
                                    ry + (row_h - mark_size) / 2 + mark_size],
                                   fill=col, outline="#ffffff", width=2)
                        _center_text(dr, sx + (col_w - mark_size) / 2, ry + (row_h - mark_size) / 2,
                                     mark_size, mark_size, mark, mf, "#ffffff")
                sx += col_w
            if subj_obj.average is not None:
                avg_text = f"{subj_obj.average:.1f}".replace(".", ",")
                tw = dr.textlength(avg_text, font=subject_font)
                dr.text((avg_x + (avg_w - tw) / 2, ry), avg_text,
                        font=subject_font, fill="#33415c")
            if subj_obj.final:
                tw = dr.textlength(subj_obj.final, font=subject_font)
                dr.text((avg_x + avg_w + (final_w - tw) / 2, ry), subj_obj.final,
                        font=subject_font, fill="#33415c")
            ry += row_h
        y += gh + 16

    return img


def render_report_image(report, font_dir: Path | None = None, output: str | None = None) -> bytes:
    """Возвращает PNG-байты отчёта об успеваемости (таблицы по месяцам)."""
    font_dir = font_dir or FONT_DIR
    if not report.subjects or not any(s.marks for s in report.subjects):
        return b""
    img = _render_report_table(report, Path(font_dir))
    if output:
        img.save(output)
        return Path(output).read_bytes()
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()