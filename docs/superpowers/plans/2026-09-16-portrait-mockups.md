# Plan: Portrait Phone Mockups (03 Day Cards + 5 Alternatives)

## Context
User liked design 03 (day cards with rounded rectangles, vertical day stacking).
Need to regenerate in portrait phone format (720px wide, auto height) for fast Telegram loading.
6 total images: base 03 + 5 style variations.

## Design Layout (portrait, all 6 share same structure)
- Width: 720px
- Height: auto (depends on content, typically ~800-1100px)
- Structure: title at top → vertical day cards (full width, rounded corners)
- Each card: date label header + lessons with marks inside
- Empty days show "Оценок нет"

## 6 Variants

| # | Filename | Style | Background | Cards | Marks | Font |
|---|----------|-------|-----------|-------|-------|------|
| 1 | `03_portrait_light.png` | Classic light | `#f4f6fb` | white, soft shadow/outline | colored circles | Calibri |
| 2 | `03_portrait_dark.png` | Dark theme | `#171a23` | dark gray, light border | colored circles | Calibri |
| 3 | `03_portrait_emoji.png` | Emoji marks | `#f7f8fc` | white, soft border | keycap emoji 5️⃣ | Corbel + Segoe UI Emoji |
| 4 | `03_portrait_minimal.png` | Minimal | `#ffffff` | no borders, subtle divider lines | plain numbers (colored text) | Consolas |
| 5 | `03_portrait_ring.png` | Ring marks | `#fdf3f8` (pink tint) | white, pink border | outlined circles | Calibri |
| 6 | `03_portrait_warm.png` | Warm pastel | `#faf6f0` | beige/cream cards, soft outline | colored circles | Georgia |

## Implementation

### Step 1: Update `design_base.py`
- Add shared portrait rendering function: `render_portrait(days, variant_name, bg_color, card_color, card_border, mark_mode, title_font, title_size, title_color, date_font, subject_font, empty_text, card_radius, padding)`
- This single function draws the portrait layout; each variant just calls it with different style params

### Step 2: Create `designs/03_portrait.py`
- Imports `render_portrait` from `design_base`
- Calls it 6 times with different color/style params
- Saves 6 PNGs to `designs/` folder

### Step 3: Run & verify
- `python designs/03_portrait.py`
- Check all 6 PNGs exist and are reasonable size (<50KB each)
- Open a few to visually verify

## Files Modified
- `designs/design_base.py` — add `render_portrait()` function
- `designs/03_portrait.py` — new file, generates 6 variants

## Verification
- All 6 PNGs generated in `designs/`
- Each PNG < 50KB (fast Telegram loading)
- Width = 720px confirmed
- Russian text renders correctly (Cyrillic fonts)
- Marks render correctly in each variant's style
