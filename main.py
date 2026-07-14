"""
main.py — точка входа в приложение GameTimeTracker.
Проверяет, не запущен ли уже экземпляр, и запускает приложение.

Расположение: GameTimeTracker/main.py
"""

import sys
import win32event
import win32api
import winerror
from tkinter import messagebox


def is_already_running():
    """Проверяет, не запущен ли уже другой экземпляр приложения."""
    mutex_name = "GameTimeTracker_Mutex_{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}"
    try:
        # Пытаемся создать мьютекс
        mutex = win32event.CreateMutex(None, False, mutex_name)
        if win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS:
            # Мьютекс уже существует → приложение уже запущено
            return True
        return False
    except Exception:
        # В случае ошибки считаем, что экземпляр не запущен (чтобы не блокировать запуск)
        return False


def main():
    """Главная функция."""
    if is_already_running():
        messagebox.showwarning(
            "GameTimeTracker",
            "Приложение уже запущено.\nПроверьте системный трей."
        )
        sys.exit(0)

    # Импортируем App здесь, чтобы не загружать все зависимости при проверке мьютекса
    from app import App

    app = App()
    app.run()


if __name__ == "__main__":
    main()