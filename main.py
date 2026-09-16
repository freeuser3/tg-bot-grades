import asyncio
import datetime
import sys

from grades import get_grades

sys.stdout.reconfigure(encoding="utf-8")


async def main():
    text = await get_grades(
        datetime.date(2026, 9, 1),
        datetime.date(2026, 9, 30),
    )
    print(text)


if __name__ == "__main__":
    asyncio.run(main())