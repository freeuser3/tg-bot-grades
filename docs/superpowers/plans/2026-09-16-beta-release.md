# Plan: Beta Release — Image Output + Cross-Platform + Rename

## Goal
Beta release: integrate portrait image output, bundle font for cross-platform, rename to tg-bot-grades, update SDD.

## Tasks

### T1: Bundle font + create renderer.py
- Download NotoSans-Regular.ttf to `fonts/`
- Create `renderer.py` with `render_diary_image(diary, font_path=None) → bytes`
- Uses 03_portrait_light design (720px wide, auto height, colored circles)
- Font resolution: config font_path → `fonts/NotoSans-Regular.ttf` relative to script

### T2: Update grades.py
- Add `fetch_diary(start, end) → Diary` (raw data, no formatting)
- Refactor `get_grades()` to call `fetch_diary()` + `format_diary()`
- Update tests

### T3: Update bot.py
- Read `output_mode` from config ("image" | "text", default "text")
- In `send_grades()`: if image mode → call renderer, send_photo; else send text
- Add import for renderer

### T4: Update config + requirements
- `config.example.json`: add `"output_mode": "image"`
- `requirements.txt`: add `Pillow`
- `config.json`: add `"output_mode": "image"` (gitignored)

### T5: Tests
- `test_render_diary_image_returns_png`: renderer produces valid PNG bytes
- `test_fetch_diary_returns_diary`: fetch_diary returns Diary object
- Existing 7 tests pass

### T6: Rename branch
- `git branch -m max-bot-grades tg-bot-grades`
- Update worktree references if needed

### T7: Update instructions
- `RUN_BOT_WINDOWS.txt`: mention image output, Pillow
- `RUN_BOT_DEBIAN.txt`: mention Pillow, font bundled
- `REGISTER_TG_BOT.txt`: no changes needed

### T8: Update SDD
- Update `.superpowers/sdd/2026-09-15-max-bot-grades/progress.md`
- Add task entries for T1-T8

### T9: Commit + restart bot
- Stage all changes
- Commit with descriptive message
- Stop old bot process, restart with new code

## Verification
- `python -m pytest -q` → all tests pass (9 expected)
- `python main.py` → text output works
- Bot starts and sends images in Telegram
- Both Windows and Debian compatible (font bundled)
