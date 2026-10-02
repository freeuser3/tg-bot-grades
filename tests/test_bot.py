import asyncio
import importlib
import sys

import pytest


class FakeMessage:
    def __init__(self):
        self.answers = []
        self.photos = []

    async def answer(self, text, **kwargs):
        self.answers.append(text)

    async def answer_photo(self, photo, **kwargs):
        self.photos.append(photo)


@pytest.fixture
def bot_module(monkeypatch):
    import grades
    monkeypatch.setattr(grades, "load_config", lambda: {"tg_bot_token": "token"})
    sys.modules.pop("bot", None)
    module = importlib.import_module("bot")
    yield module
    sys.modules.pop("bot", None)


def test_send_report_tells_user_when_rendering_fails(bot_module, monkeypatch):
    async def fake_fetch_report():
        return object()

    def broken_render(report):
        raise ValueError("boom")

    monkeypatch.setattr(bot_module, "fetch_report", fake_fetch_report)
    monkeypatch.setattr(bot_module, "render_report_images", broken_render)

    message = FakeMessage()
    asyncio.run(bot_module.send_report(message))

    assert len(message.photos) == 0
    assert len(message.answers) == 1
    assert "Ошибка" in message.answers[0]


def test_send_report_tells_user_when_report_request_fails(bot_module, monkeypatch):
    async def failing_fetch_report():
        raise RuntimeError("net down")

    monkeypatch.setattr(bot_module, "fetch_report", failing_fetch_report)

    message = FakeMessage()
    asyncio.run(bot_module.send_report(message))

    assert len(message.photos) == 0
    assert len(message.answers) == 1
    assert "Ошибка" in message.answers[0]


def test_send_report_says_nothing_about_marks_when_report_is_empty(bot_module, monkeypatch):
    async def fake_fetch_report():
        return object()

    monkeypatch.setattr(bot_module, "fetch_report", fake_fetch_report)
    monkeypatch.setattr(bot_module, "render_report_images", lambda report: [])

    message = FakeMessage()
    asyncio.run(bot_module.send_report(message))

    assert message.photos == []
    assert message.answers == ["За период оценок нет"]