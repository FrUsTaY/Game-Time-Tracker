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
