"""
utils.py — утилиты для работы с путями и ресурсами приложения GameTimeTracker.
Обеспечивает корректное определение базового каталога при автозапуске,
работе из произвольной рабочей директории (CWD) и в скомпилированном PyInstaller виде.
"""

import os
import sys


def get_base_dir() -> str:
    """
    Возвращает абсолютный путь к базовой директории приложения.
    Корректно работает как при обычном запуске Python-скрипта,
    так и при запуске скомпилированного .exe (PyInstaller).
    """
    if getattr(sys, 'frozen', False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def resource_path(relative_path: str) -> str:
    """
    Возвращает абсолютный путь к ресурсу (иконки, ассеты и т.д.).
    Поддерживает распакованные ресурсы PyInstaller (sys._MEIPASS)
    и обычный запуск из исходного кода относительно get_base_dir().
    """
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        bundle_path = os.path.join(sys._MEIPASS, relative_path)
        if os.path.exists(bundle_path):
            return os.path.normpath(bundle_path)
    return os.path.normpath(os.path.join(get_base_dir(), relative_path))


def format_duration(seconds: int, style: str = "short") -> str:
    """
    Форматирует длительность в человекочитаемом виде.

    Args:
        seconds: количество секунд (отрицательные значения трактуются как 0).
        style: "short"   — «1 ч 05 мин», «12 мин», «45 сек»;
               "clock"   — «01:05:12» / «05:12»;
               "hours"   — «1.5 ч».

    Returns:
        Строка с отформатированной длительностью.
    """
    seconds = max(int(seconds or 0), 0)
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)

    if style == "clock":
        if hours:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        return f"{minutes:02d}:{secs:02d}"
    if style == "hours":
        return f"{seconds / 3600:.1f} ч"
    if style != "short":
        raise ValueError(f"Неизвестный стиль форматирования: {style!r}")

    parts = []
    if hours:
        parts.append(f"{hours} ч")
    if minutes:
        parts.append(f"{minutes:02d} мин" if hours else f"{minutes} мин")
    if not parts:
        parts.append(f"{secs} сек")
    return " ".join(parts)
