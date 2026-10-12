import os
import pytest

os.environ["QT_QPA_PLATFORM"] = "offscreen"


@pytest.fixture(scope="session", autouse=True)
def qt_app():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture(autouse=True)
def no_paid_api(monkeypatch):
    # Tests must inject a fake client; any accidental live OpenAI request fails closed.
    import openai
    async def forbidden(*args, **kwargs):
        raise AssertionError("Live API forbidden during offline tests")
    monkeypatch.setattr(openai.AsyncOpenAI, "request", forbidden)
