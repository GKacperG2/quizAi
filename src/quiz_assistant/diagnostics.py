"""Opt-in event fields only; never log exception strings, HTTP bodies or images."""
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from PySide6.QtCore import QStandardPaths


def configure_logging(directory: Path | None = None) -> Path:
    directory = directory or Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation)) / "diagnostics"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "assistant.log"
    logger = logging.getLogger("quiz_assistant")
    for handler in tuple(logger.handlers):
        logger.removeHandler(handler)
        handler.close()
    handler = RotatingFileHandler(path, maxBytes=512_000, backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    logger.info("application_start")
    return path
