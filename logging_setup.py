"""
logging_setup.py — централизованная настройка журналирования GameTimeTracker.

Зачем это нужно:
  * в скомпилированном виде (`--windowed`) у приложения нет консоли, поэтому
    все сообщения через `print()` просто теряются;
  * при ошибках в фоновом потоке трекера пользователь и разработчик не видят
    причины сбоя;
  * файловый журнал с ротацией даёт возможность разобрать инцидент постфактум.

Журнал пишется в `data/logs/gametimetracker.log` (рядом с базой данных),
ротация — 1 МБ, хранится 3 архивных файла.
"""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from typing import Optional

from utils import get_base_dir

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(threadName)s %(name)s: %(message)s"
LOG_FILE_NAME = "gametimetracker.log"
MAX_BYTES = 1024 * 1024
BACKUP_COUNT = 3

_configured = False


def get_log_dir() -> str:
    """Возвращает каталог для файлов журнала (`data/logs`)."""
    return os.path.join(get_base_dir(), "data", "logs")


def get_log_path() -> str:
    """Возвращает полный путь к основному файлу журнала."""
    return os.path.join(get_log_dir(), LOG_FILE_NAME)


def setup_logging(
    level: int = logging.INFO,
    log_dir: Optional[str] = None,
    console: Optional[bool] = None,
) -> logging.Logger:
    """
    Настраивает корневой логгер приложения.

    Args:
        level: уровень журналирования.
        log_dir: каталог для файла журнала (по умолчанию `data/logs`).
        console: дублировать ли сообщения в stderr. По умолчанию — только
            если приложение запущено из исходников (не в сборке PyInstaller).

    Returns:
        Настроенный корневой логгер.
    """
    global _configured
    root = logging.getLogger()
    if _configured:
        return root

    root.setLevel(level)
    formatter = logging.Formatter(LOG_FORMAT)

    target_dir = log_dir or get_log_dir()
    try:
        os.makedirs(target_dir, exist_ok=True)
        file_handler = RotatingFileHandler(
            os.path.join(target_dir, LOG_FILE_NAME),
            maxBytes=MAX_BYTES,
            backupCount=BACKUP_COUNT,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)
    except OSError:
        # Нет прав на запись — приложение должно продолжить работу без журнала.
        pass

    if console is None:
        console = not getattr(sys, "frozen", False) and sys.stderr is not None
    if console and sys.stderr is not None:
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        root.addHandler(stream_handler)

    _configured = True
    root.debug("Журналирование инициализировано")
    return root


def get_logger(name: str) -> logging.Logger:
    """Возвращает именованный логгер (журналирование уже настроено в main)."""
    return logging.getLogger(name)
