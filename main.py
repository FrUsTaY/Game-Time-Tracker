"""
main.py — точка входа в приложение GameTimeTracker.
Проверяет, не запущен ли уже экземпляр, и запускает приложение.

Расположение: GameTimeTracker/main.py
"""

import logging
import sys
from tkinter import messagebox

try:  # Приложение поддерживает только Windows, но импорт не должен «ронять» тесты
    import win32api
    import win32event
    import winerror
    WIN32_AVAILABLE = True
except ImportError:  # pragma: no cover - зависит от платформы
    win32event = win32api = winerror = None
    WIN32_AVAILABLE = False

from logging_setup import setup_logging

logger = logging.getLogger(__name__)


_app_mutex = None


def is_already_running():
    """Проверяет, не запущен ли уже другой экземпляр приложения."""
    global _app_mutex
    if not WIN32_AVAILABLE:
        return False
    mutex_name = "GameTimeTracker_Mutex_{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}"
    try:
        # Пытаемся создать мьютекс и сохранить дескриптор в глобальной переменной
        _app_mutex = win32event.CreateMutex(None, False, mutex_name)
        if win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS:
            # Мьютекс уже существует → приложение уже запущено
            if _app_mutex:
                win32api.CloseHandle(_app_mutex)
                _app_mutex = None
            return True
        return False
    except Exception:
        # В случае ошибки считаем, что экземпляр не запущен (чтобы не блокировать запуск)
        return False


def main():
    """Главная функция."""
    global _app_mutex
    setup_logging()
    logger.info("Запуск GameTimeTracker")

    if not WIN32_AVAILABLE:
        messagebox.showerror(
            "GameTimeTracker",
            "Приложение поддерживает только Windows:\n"
            "требуются модули pywin32 (win32api, win32event)."
        )
        sys.exit(1)

    if is_already_running():
        messagebox.showwarning(
            "GameTimeTracker",
            "Приложение уже запущено.\nПроверьте системный трей."
        )
        sys.exit(0)

    # Импортируем App здесь, чтобы не загружать все зависимости при проверке мьютекса
    from app import App

    try:
        app = App()
        app.run()
    finally:
        if _app_mutex:
            try:
                win32api.CloseHandle(_app_mutex)
            except Exception:
                pass
            _app_mutex = None


if __name__ == "__main__":
    main()
