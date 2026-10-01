# Отчёт об успеваемости: исправление раскладки таблицы — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Переписать `_render_report_table` так, чтобы картинка отчёта не теряла оценки и не обрезала названия предметов: месяц разбит на недельные блоки, бот отправляет по одной картинке на месяц.

**Architecture:** Четыре чистые функции-единицы в `renderer.py`: `_group_by_month` (группировка, без Pillow), `_week_blocks` (разбивка дат, без Pillow), `_render_month` (рисование одного месяца), публичная `render_report_images` (список PNG). Старые `_render_report_table` и `render_report_image` удаляются на последнем шаге, чтобы на каждом коммите бот импортировал существующее имя.

**Tech Stack:** Python 3.12, Pillow 12, `netschoolapi-plus` 11.1.0 (`StudentTotalReport` / `SubjectReport`), aiogram 3.7, pytest + pytest-asyncio.

**Spec:** `docs/superpowers/specs/2026-10-01-report-table-layout-design.md`

## Global Constraints

- Ширина холста `W = 720`, `padding = 32`, `card_pad = 24`.
- Колонки: `subj_w = 240`, `gap = 8`, `avg_w = 52` («Ср.»), `grid_w = 608 - 240 - 8 - 52 = 308`.
- `col_w = min(56, grid_w // max_days_in_block)`; `mark_size = min(26, col_w - 12)`; `row_h = mark_size + 14`.
- Колонки «Итог» не существует: `final_w` не вводится.
- Жёсткий лимит Telegram: `width + height <= 10000` для каждой картинки. При `W = 720` высота ≤ 9280.
- Цвета: фон `#f4f6fb`, карточка `#ffffff`, рамка карточки `#dde3f0`, разделители `#e3e8f2`, титул `#1c3d6e` (**только на первой картинке**), заголовки блоков и шапки дат `#2c5aa0`, день недели `#8a94a8`, текст предмета и «Ср.» `#33415c`, нечисловая отметка `#95a5a6`.
- Шрифты из `fonts/`: `FONT_BOLD` (`NotoSans-Bold.ttf`), `FONT_NORMAL` (`NotoSans-Regular.ttf`). Титул 26px, метка месяца 20px, заголовок блока и число даты 18px, день недели 14px, мета 14px, текст предмета и значение «Ср.» 18px.
- `_week_blocks` вызывается **внутри месяца** на уже отфильтрованных днях месяца — блок никогда не пересекает границу месяца.
- Не трогать: `render_diary_image`, `_render_lines`, `render_monthly_image`, `_render_monthly_grid`, `grades.fetch_report`, текстовый режим вывода.
- Комментарии в коде не писать. Существующий стиль — `from collections import OrderedDict` локально внутри функции; соблюдать его.

## Review Focus

Пять классов входных данных, которые спецификация подразумевает, но ни один тест не покрывает. Для каждого — тест добавлен в задачу, владеющую кодом.

1. **Нестандартная неделя из 6-7 дней с оценками** (зачёт в субботу/воскресенье) → `col_w` падает до 44, кружок остаётся 26px. Ожидание: сетка не залезает на колонку «Ср.». → Task 3.
2. **Предмет, у которого в этом месяце нет ни одной оценки** → строка обязана существовать с пустыми клетками, предмет не пропадает и рендер не падает. → Task 1.
3. **Название предмера длиннее 232px** → `_truncate_text` срабатывает, многоточие, текст не выходит за `grid_x`. → Task 3.
4. **Нечисловая отметка («н», «п»)** → серый кружок `#95a5a6`, не падает. → Task 3.
5. **Триместр с оценками в одном месяце** → ровно одна картинка, не ноль и не две. → Task 4.

## File Structure

| Файл | Ответственность | Действие |
|---|---|---|
| `renderer.py` | Рендер всех PNG | изменить: добавить 4 функции на `renderer.py:1-30`; удалить `renderer.py:281-419` |
| `bot.py` | Отправка в Telegram | изменить: `bot.py:11` (импорт), `bot.py:52-63` (`send_report`) |
| `tests/test_renderer.py` | Тесты рендера | изменить: заменить блок тестов отчёта `tests/test_renderer.py:216-298` |
| `README.md` | Документация для пользователя | изменить: `README.md:45-47` |

Раскладка по функциям в `renderer.py` — после изменений, по порядку следования:

```
_report_layout()                  -> dict      # константы раскладки, чтобы тесты и рендер брали одно число
_group_by_month(report)           -> OrderedDict
_week_blocks(days)                -> list[list[date]]
_render_month(...)                -> Image
render_report_images(report, ...) -> list[bytes]
```

---

### Task 1: `_group_by_month` — предметы в каждом месяце, где есть оценки

**Files:**
- Modify: `renderer.py` (добавить после `_report_meta`, то есть после `renderer.py:278`)
- Test: `tests/test_renderer.py`

**Interfaces:**
- Consumes: ничего (первая задача). Тип отчёта — `netschoolapi_plus.schemas.StudentTotalReport`.
- Produces: `_group_by_month(report) -> OrderedDict[tuple[int, int], dict]`, где значение — `{"days": list[date], "subjects": list[str]}`, оба списка отсортированы; ключи отсортированы хронологически. Используется Task 3 и Task 4.

- [ ] **Step 1: Write the failing test**

Добавить в `tests/test_renderer.py` в конец файла. Также добавить хелперы `_weekdays` и `_school_report`, они понадобятся дальше:

```python
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


def test_group_by_month_keeps_subject_row_that_has_no_marks_in_that_month():
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_renderer.py -k group_by_month -v`
Expected: FAIL — `ImportError: cannot import name '_group_by_month' from 'renderer'`

- [ ] **Step 3: Write minimal implementation**

Вставить в `renderer.py` сразу после функции `_report_meta` (заканчивается на `renderer.py:278`):

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_renderer.py -k group_by_month -v`
Expected: PASS — 3 passed

- [ ] **Step 5: Run the whole suite to check nothing else broke**

Run: `python -m pytest -q`
Expected: все тесты проходят, кроме ещё не написанных (их нет). Если упали тесты старого отчёта — это ожидаемо, они удаляются в Task 5.

- [ ] **Step 6: Commit**

```bash
git add renderer.py tests/test_renderer.py
git commit -m "fix(report): group subjects into every month they have marks in"
```

---

### Task 2: `_week_blocks` — разбивка дат на ISO-недели

**Files:**
- Modify: `renderer.py` (добавить после `_group_by_month`)
- Test: `tests/test_renderer.py`

**Interfaces:**
- Consumes: ничего.
- Produces: `_week_blocks(days: list[datetime.date]) -> list[list[datetime.date]]`. На входе уже отсортированный список дней одного месяца. Используется Task 3.

- [ ] **Step 1: Write the failing test**

Добавить в `tests/test_renderer.py` в конец файла:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_renderer.py -k week_blocks -v`
Expected: FAIL — `ImportError: cannot import name '_week_blocks' from 'renderer'`

- [ ] **Step 3: Write minimal implementation**

Вставить в `renderer.py` сразу после `_group_by_month`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_renderer.py -k week_blocks -v`
Expected: PASS — 3 passed

- [ ] **Step 5: Commit**

```bash
git add renderer.py tests/test_renderer.py
git commit -m "feat(report): split month dates into ISO week blocks"
```

---

### Task 3: `_render_month` — раскладка карточек без переполнения

**Files:**
- Modify: `renderer.py` (добавить `_report_layout` и `_render_month` после `_week_blocks`)
- Test: `tests/test_renderer.py`

**Interfaces:**
- Consumes: `_group_by_month` (Task 1), `_week_blocks` (Task 2), существующие `_font`, `_text_height`, `_center_text`, `_truncate_text`, `_is_numeric_mark`, `_report_meta`, константы `FONT_BOLD`, `FONT_NORMAL`, `MONTHS`, `DAYS_RU`, `GRADE_COLORS`, `REPORT_TITLE`.
- Produces:
  - `_report_layout() -> dict` с ключами `w`, `padding`, `card_pad`, `subj_w`, `gap`, `avg_w`, `grid_w`, `grid_x`, `avg_x`, `card_right`. Тесты читают эти числа, чтобы не дублировать геометрию.
  - `_render_month(report, year, month, data, font_dir, *, with_header: bool) -> Image.Image`. Используется Task 4.

- [ ] **Step 1: Write the failing tests**

Добавить в `tests/test_renderer.py` в конец файла. Хелпер `_realistic_report` — 14 предметов, 22 будних дня сентября 2026:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_renderer.py -k "month_image or month_label or six_day_week or very_long_subject" -v`
Expected: FAIL — `ImportError: cannot import name '_report_layout' from 'renderer'`

- [ ] **Step 3: Write minimal implementation**

Вставить в `renderer.py` сразу после `_week_blocks`:

```python
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
        y += _text_height(title_font, "Ag") + 6
        dr.text((x0, y), _report_meta(report), font=meta_font, fill="#5a6478")
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_renderer.py -k "month_image or month_label or six_day_week or very_long_subject" -v`
Expected: PASS — 10 passed

- [ ] **Step 5: Run the whole suite**

Run: `python -m pytest -q`
Expected: PASS. Если падают старые тесты отчёта — они удаляются в Task 5, отметь это и не чини их здесь.

- [ ] **Step 6: Render one image by hand and look at it**

```bash
python -c "
import sys; sys.path.insert(0, r'C:\Users\max\Documents\zeroCode\tg-bot grades')
sys.path.insert(0, r'C:\Users\max\Documents\zeroCode\tg-bot grades\tests')
from pathlib import Path
from renderer import FONT_DIR, _group_by_month, _render_month
import test_renderer as t
r = t._realistic_report()
g = _group_by_month(r)
img = _render_month(r, 2026, 9, g[(2026,9)], Path(FONT_DIR), with_header=True)
img.save(r'C:\Users\max\AppData\Local\Temp\opencode\new_september.png')
print('new_september.png', img.size)
"
```

Открыть `new_september.png` и проверить глазами: пять карточек с подписями «1–4 сент.» … «28–30 сент.», над числами дни недели, справа одна колонка «Ср.», предметы не обрезаны, ничего не вылезает за карточку. Расхождение с ожиданием — вернуться к этому шагу, а не идти дальше.

- [ ] **Step 7: Commit**

```bash
git add renderer.py tests/test_renderer.py
git commit -m "feat(report): render month as week blocks with auto-sized columns"
```

---

### Task 4: `render_report_images` — публичный контракт

**Files:**
- Modify: `renderer.py` (добавить после `_render_month`)
- Test: `tests/test_renderer.py`

**Interfaces:**
- Consumes: `_group_by_month` (Task 1), `_render_month` (Task 3), `FONT_DIR`, `BytesIO`, `Path`.
- Produces: `render_report_images(report, font_dir: Path | None = None) -> list[bytes]`. Используется Task 5 (`bot.py`) и всеми тестами отчёта.

- [ ] **Step 1: Write the failing tests**

Добавить в `tests/test_renderer.py` в конец файла:

```python
def _trimester_report():
    marks = {}
    for month in (9, 10, 11):
        for day in _weekdays(2026, month):
            marks[day] = ["5", "4", "3", "н"][day.day % 4]
    return _school_report([_subject("Алгебра", marks, average=4.5),
                           _subject("Русский язык", marks, average=4.6)])


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


def test_render_report_images_returns_empty_list_when_all_marks_are_empty():
    from renderer import render_report_images
    report = _school_report([_subject("Алгебра", {}, average=None)])
    assert render_report_images(report) == []


def test_render_report_images_accepts_custom_font_dir(tmp_path):
    from pathlib import Path
    from renderer import FONT_DIR, render_report_images
    images = render_report_images(_realistic_report(), font_dir=Path(FONT_DIR))
    assert len(images) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_renderer.py -k render_report_images -v`
Expected: FAIL — `ImportError: cannot import name 'render_report_images' from 'renderer'`

- [ ] **Step 3: Write minimal implementation**

Вставить в `renderer.py` сразу после `_render_month`:

```python
def render_report_images(report, font_dir: Path | None = None) -> list:
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
```

- [ ] **Step 4: Run tests to verify they passes**

Run: `python -m pytest tests/test_renderer.py -k render_report_images -v`
Expected: PASS — 6 passed

- [ ] **Step 5: Verify every image fits the Telegram limit**

Run: `python -m pytest tests/test_renderer.py -q -k "report_images or month_image"`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add renderer.py tests/test_renderer.py
git commit -m "feat(report): render_report_images returns one PNG per month"
```

---

### Task 5: Переключить бота и удалить старый рендер

**Files:**
- Modify: `bot.py:11` (импорт), `bot.py:52-63` (`send_report`)
- Modify: `renderer.py:281-419` (удалить `_render_report_table` и `render_report_image`)
- Modify: `tests/test_renderer.py:216-298` (удалить тесты старого отчёта)
- Modify: `README.md:45-47`

**Interfaces:**
- Consumes: `render_report_images` (Task 4).
- Produces: бот отправляет по одной картинке на месяц. Удалённое имя `_render_report_table` и `render_report_image` больше не существует нигде в репозитории.

- [ ] **Step 1: Update the import in bot.py**

Заменить `bot.py:11`:

```python
from renderer import render_diary_image, render_monthly_image, render_report_images
```

- [ ] **Step 2: Rewrite send_report**

Заменить `bot.py:52-63` целиком:

```python
async def send_report(message: Message):
    try:
        report = await fetch_report()
    except Exception as e:
        await message.answer(f"Ошибка при получении отчёта: {e}")
        return
    images = render_report_images(report)
    if not images:
        await message.answer("За период оценок нет")
        return
    await message.answer("📄 Отчёт об успеваемости")
    for index, png in enumerate(images, start=1):
        await message.answer_photo(
            BufferedInputFile(png, filename=f"report_{index}.png")
        )
```

- [ ] **Step 3: Delete the old renderer functions**

Удалить из `renderer.py` всё от строки `def _render_report_table(report, font_dir: Path) -> Image.Image:` (строка 281) до конца файла (строка 419), то есть обе функции `_render_report_table` и `render_report_image`.

Проверить, что не осталось ссылок:

Run: `grep -rn "render_report_image(" renderer.py bot.py tests/`
Expected: нет вывода

Run: `grep -rn "_render_report_table" renderer.py bot.py tests/`
Expected: нет вывода

- [ ] **Step 4: Delete the obsolete tests**

Сначала поправить импорты в шапке `tests/test_renderer.py`. Строки 9-15 сейчас
такие:

```python
from renderer import (
    render_diary_image,
    render_monthly_image,
    render_report_image,
)

from renderer import REPORT_TITLE, _report_meta, _truncate_text
```

Заменить на:

```python
from renderer import (
    render_diary_image,
    render_monthly_image,
    render_report_images,
)

from renderer import _truncate_text
```

Затем удалить функции тестов:
- `_make_fake_report` (строки 216-243);
- `test_render_report_image_returns_png_bytes` (246-252);
- `test_render_report_image_writes_file` (255-260);
- `test_render_report_image_contains_gray_mark_for_non_numeric` (262-272);
- `test_report_meta_does_not_contain_student_name` (275-279);
- `test_report_title_does_not_mention_attendance` (282-283).

`REPORT_TITLE` и `_report_meta` больше не нужны в импортах: их использовали
только два удаляемых теста. Сами функции в `renderer.py` остаются —
`_report_meta` вызывает `_render_month`.

Не удалять `test_truncate_text_shortens_long_subject_to_fit_width` и
`test_truncate_text_keeps_short_subject_unchanged` (286-308) — они проверяют
`_truncate_text`, который остаётся в работе.

Оставить `test_fetch_report_calls_library_report_studenttotal` (311-334) — он
проверяет `grades.fetch_report`, а не рендер.

- [ ] **Step 5: Run the whole suite**

Run: `python -m pytest -q`
Expected: PASS — все тесты проходят, ни одного падения. Записать фактическое число в README.

- [ ] **Step 6: Verify bot.py imports cleanly**

Run: `python -c "import ast, pathlib; ast.parse(pathlib.Path('bot.py').read_text(encoding='utf-8')); print('bot.py parses')"`
Expected: `bot.py parses`

Run: `python -c "import renderer; print(sorted(n for n in dir(renderer) if 'report' in n))"`
Expected: список содержит `render_report_images` и не содержит `render_report_image`

- [ ] **Step 7: Update README**

Заменить `README.md:45-47`:

```markdown
- **`report_studenttotal()`** — парсинг отчёта в структурированные данные:
  `StudentTotalReport`, `SubjectReport` (оценки по датам + средняя + итоговая).
- Кнопка **«📄 Отчёт об успеваемости»** в боте отдаёт PNG-картинки отчёта за
  триместр: по одной картинке на месяц, внутри месяца даты разбиты на недельные
  блоки (предмет × даты), колонка «Ср.», нечисловые отметки (`н`, `п`, …) —
  серые кружки.
```

И в блоке «Тесты» (`README.md:80`, `README.md:97`) заменить ожидаемое число на
фактическое из шага 5.

- [ ] **Step 8: Commit**

```bash
git add renderer.py bot.py tests/test_renderer.py README.md
git commit -m "refactor(report): send one image per month, drop old table renderer"
```

---

## Self-Review

**1. Покрытие спецификации.** Все разделы spec сопоставлены с задачами:

| Раздел spec | Задача |
|---|---|
| Дефект 1 — теряются предметы | Task 1 (`_group_by_month` + тест) |
| Дефект 2 — переполнение сетки | Task 3 (недельные блоки, авто-`col_w`, тесты 3/4/RF1) |
| Дефект 3 — обрезка предметов | Task 3 (`subj_w = 240`, тест 5) |
| Дефект 4 — колонка «Итог» | Task 3 (`final_w` не вводится, тест «no column after average») |
| Ограничения Telegram | Task 3 (тест на `width + height`) |
| Архитектура (5 единиц) | Task 1, 2, 3, 4, 5 |
| Раскладка и константы | Task 3 (`_report_layout`) |
| Шапка даты в две строки | Task 3 (тест `draws_two_lines_per_date_header`) |
| Титул только на первой картинке | Task 3 (`with_header=False` → метка месяца), Task 4 (тест порядка) |
| Поток данных | Task 5 (`send_report`) |
| Обработка ошибок | Task 4 (пустой отчёт → `[]`) |
| Что не меняется | ни одна задача не трогает `render_diary_image`, `_render_lines`, `render_monthly_image`, `_render_monthly_grid`, `grades.fetch_report` |
| Известный риск | вне плана: требует проверки на телефоне после Task 5 |

**2. Поиск плейсхолдеров.** В плане нет `TBD`, `TODO`, «similar to Task N», «add
appropriate error handling». Каждый шаг с кодом содержит полный листинг; каждый
тест содержит полный код; каждая команда приведена дословно.

**3. Согласованность имён и типов.**

- `_group_by_month(report) -> OrderedDict[tuple[int, int], dict]` — определена в Task 1, используется в Task 3 (`_render_month` вызывается вручную в тестах Task 3) и Task 4. Во всех местах одна сигнатура. ✓
- `_week_blocks(days) -> list[list[date]]` — Task 2, используется в `_render_month` (Task 3). ✓
- `_report_layout() -> dict` — Task 3, читается тестами Task 3 и Task 4 через `from renderer import _report_layout`. Ключи `card_right`, `avg_x`, `avg_w`, `grid_x`, `subj_w` используются в тестах и все присутствуют в возвращаемом словаре. ✓
- `_render_month(report, year, month, data, font_dir, *, with_header)` — Task 3; все вызовы передают `with_header` keyword-only. ✓
- `render_report_images(report, font_dir=None) -> list[bytes]` — Task 4, используется в Task 5 и в тестах Task 4. ✓
- Хелперы `_weekdays`, `_school_report`, `_subject`, `_realistic_report`, `_trimester_report` введены в Task 1 и Task 3/4 и нигде не переопределяются. ✓
- `_make_fake_report` удаляется в Task 5; до этого момента остаётся и используется старыми тестами отчёта. Ни один новый тест её не вызывает. ✓

**4. Review Focus.** Все пять строк покрыты: RF2 в Task 1, RF1/RF3/RF4 в Task 3,
RF5 в Task 4. ✓