# tg-bot-grades — Telegram-бот школьных оценок

Бот показывает оценки из «Сетевого города» (СГО). Отвечает в личных чатах,
выводит оценки за последние 7 или 30 дней.

- **Бот:** @lc4gradesBot
- **Школа:** МОУ «Лицей № 4»
- **Режим вывода:** `output_mode` в config.json — `"image"` (PNG-картинка) или `"text"` (текст с эмодзи)

## Быстрый старт

1. Скопируйте `config.example.json` → `config.json` и заполните:
   - `ns_login`, `ns_password`, `ns_school` — учётка «Сетевого города»
   - `tg_bot_token` — токен Telegram-бота
   - `use_proxy` / `proxy_url` — прокси (на Debian прямой доступ, поставьте `false`)
   - `output_mode` — `"image"` | `"text"`
2. Установите зависимости:

   ```bash
   pip install aiogram==3.7.0 pydantic==2.6.4 pydantic_core==2.16.3 typing-extensions==4.16.0
   pip install netschool-api-plus aiohttp-socks Pillow
   pip install pytest pytest-asyncio   # только для тестов
   ```

3. Запустите:

   ```bash
   python bot.py
   ```

4. Проверьте в Telegram: `/start`, кнопка «Получить оценки», `/оценки`, `/оценки месяц`, «Отчёт об успеваемости».

## Библиотека для СГО: netschool-api-plus

Бот работает с форком `netschoolapi` — **`netschool-api-plus`**
(https://github.com/freeuser3/netschool-api-plus).

Переход на форк даёт:

- **`report_file()`** — получение официального HTML-отчёта через цепочку
  `POST reports/studenttotal/queue` → WebSocket `signalr/queueHub` → `GET files/{fileCode}`.
  Старый флоу (SignalR negotiate/SSE) на серверах СГО 5.56 возвращал 404.
  Без дат берёт период текущего триместра с сервера (`filterSources.period`).
- **`report_studenttotal()`** — парсинг отчёта в структурированные данные:
  `StudentTotalReport`, `SubjectReport` (оценки по датам + средняя + итоговая).
- Кнопка **«📄 Отчёт об успеваемости»** в боте отдаёт PNG-картинку отчёта за
  триместр: таблицы по месяцам (предмет × даты), колонки «Ср.» и «Итог»,
  нечисловые отметки (`н`, `п`, …) — серые кружки.
- Интерфейс базовых методов (`login`, `logout`, `diary`, `schemas`) — идентичен
  оригиналу, поэтому миграция сводится к замене импорта:

  ```python
  from netschoolapi import NetSchoolAPI          # было
  from netschoolapi_plus import NetSchoolAPI     # стало
  ```

  и в `requirements.txt` — `netschoolapi==11.0.5` → `netschool-api-plus==11.0.5`.

### Почему не netschoolapi

Оригинальный пакет жёстко закрепляет `typing-extensions==4.4.0`, который
конфликтует с `pydantic`/`aiogram` (требуются 4.16+). В форке эта зависимость
убрана — связка aiogram 3.7.0 + pydantic 2.6.4 ставится без предупреждений.

## Структура проекта

- `bot.py` — точка входа (aiogram 3.7, Bot/Dispatcher/F/CommandStart)
- `grades.py` — `load_config`, `format_diary`, `fetch_diary`, `get_grades`
- `renderer.py` — PNG-рендер оценок (Pillow, шрифты `fonts/`)
- `fonts/` — бандл шрифтов (NotoSans-Regular/Bold/Italic)
- `config.example.json` — шаблон конфигурации
- `config.json` — реальные данные (не в git)
- `tests/` — `test_grades.py`, `test_renderer.py`

## Тесты

```bash
python -m pytest -q
```

Ожидание: 22 passed.

## Обновление на сервере (Debian)

Порядок после `git pull`:

```bash
# 1. Остановить бота
#    (Ctrl+C в терминале, где он запущен, или pkill -f bot.py)

# 2. Обновить зависимости (форк netschool-api-plus из git + точно pinned aiogram/pydantic)
pip install -r requirements.txt

# 3. Убедиться, что старый netschoolapi не мешает (перетирает typing-extensions)
pip uninstall -y netschoolapi   # если установлен

# 4. Прогнать тесты и запустить
python -m pytest -q             # ожидание: 22 passed
python bot.py
```

ВАЖНО: `requirements.txt` ставит форк прямо из git
(`netschoolapi-plus @ git+https://github.com/freeuser3/netschool-api-plus.git`)
и жёстко пинит aiogram==3.7.0/pydantic==2.6.4, поэтому единая команда
`pip install -r requirements.txt` приводит зависимости в порядок и не
откатывает aiogram (как было с ручным `pip install netschoolapi`).
Актуальный код бота — в `master` на GitHub.

## Инструкции

Подробные гайды по Windows/Debian, регистрации бота и настройке opencode —
в каталоге `instructions/`.