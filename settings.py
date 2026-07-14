"""
Модуль управления настройками приложения GameTimeTracker.
Использует реестр Windows для автозапуска и базу данных для остальных настроек.
"""

import winreg
import sys
import os
from typing import Optional
from database import Database


class AppSettings:
    """Класс для удобного доступа к настройкам приложения"""

    def __init__(self, db: Database):
        self.db = db
        self._cache = {}  # Простой кеш на время жизни объекта

    def _get_bool(self, key: str, default: bool) -> bool:
        """Получить булево значение из БД"""
        val = self.db.get_setting(key)
        if val is None:
            return default
        return val.lower() == 'true'

    def _set_bool(self, key: str, value: bool) -> None:
        """Сохранить булево значение в БД"""
        self.db.set_setting(key, 'true' if value else 'false')
        self._cache[key] = value

    def _get_int(self, key: str, default: int) -> int:
        """Получить целочисленное значение из БД"""
        val = self.db.get_setting(key)
        if val is None:
            return default
        try:
            return int(val)
        except ValueError:
            return default

    def _set_int(self, key: str, value: int) -> None:
        """Сохранить целочисленное значение в БД"""
        self.db.set_setting(key, str(value))
        self._cache[key] = value

    # ----- Автозапуск (работа с реестром) -----

    def enable_autostart(self) -> None:
        """Добавляет приложение в автозапуск Windows (HKCU)"""
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0, winreg.KEY_SET_VALUE
            )
            # Путь к текущему исполняемому файлу (поддерживает .exe и .py)
            if getattr(sys, 'frozen', False):
                # Запущено как .exe
                app_path = sys.executable
            else:
                # Запущено как скрипт
                app_path = f'"{sys.executable}" "{os.path.abspath("main.py")}"'

            winreg.SetValueEx(key, "GameTimeTracker", 0, winreg.REG_SZ, app_path)
            winreg.CloseKey(key)
            self._set_bool("autostart", True)
        except Exception as e:
            print(f"Ошибка включения автозапуска: {e}")

    def disable_autostart(self) -> None:
        """Удаляет приложение из автозапуска"""
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0, winreg.KEY_SET_VALUE
            )
            winreg.DeleteValue(key, "GameTimeTracker")
            winreg.CloseKey(key)
            self._set_bool("autostart", False)
        except FileNotFoundError:
            # Ключа не было — ничего страшного
            pass
        except Exception as e:
            print(f"Ошибка отключения автозапуска: {e}")

    def is_autostart_enabled(self) -> bool:
        """Проверяет, включён ли автозапуск"""
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0, winreg.KEY_READ
            )
            winreg.QueryValueEx(key, "GameTimeTracker")
            winreg.CloseKey(key)
            return True
        except FileNotFoundError:
            return False
        except Exception:
            return False

    # ----- Остальные настройки (через БД) -----

    @property
    def autostart(self) -> bool:
        """Автозапуск с Windows (управляется через реестр, но сохраняем флаг в БД)"""
        return self._get_bool("autostart", False)

    @autostart.setter
    def autostart(self, value: bool) -> None:
        if value:
            self.enable_autostart()
        else:
            self.disable_autostart()

    @property
    def minimize_to_tray_on_start(self) -> bool:
        """Сворачивать в трей при запуске"""
        return self._get_bool("minimize_to_tray_on_start", False)

    @minimize_to_tray_on_start.setter
    def minimize_to_tray_on_start(self, value: bool) -> None:
        self._set_bool("minimize_to_tray_on_start", value)

    @property
    def track_only_active_window(self) -> bool:
        """Считать время только при активном окне игры"""
        return self._get_bool("track_only_active_window", True)

    @track_only_active_window.setter
    def track_only_active_window(self, value: bool) -> None:
        self._set_bool("track_only_active_window", value)

    @property
    def notify_new_game(self) -> bool:
        """Показывать уведомление при обнаружении новой игры"""
        return self._get_bool("notify_new_game", True)

    @notify_new_game.setter
    def notify_new_game(self, value: bool) -> None:
        self._set_bool("notify_new_game", value)

    @property
    def notify_long_session(self) -> bool:
        """Напоминать о долгой сессии"""
        return self._get_bool("notify_long_session", True)

    @notify_long_session.setter
    def notify_long_session(self, value: bool) -> None:
        self._set_bool("notify_long_session", value)

    @property
    def long_session_minutes(self) -> int:
        """Через сколько минут напоминать о долгой сессии"""
        return self._get_int("long_session_minutes", 60)

    @long_session_minutes.setter
    def long_session_minutes(self, value: int) -> None:
        if value < 1:
            value = 1
        self._set_int("long_session_minutes", value)

    # ----- Сохранение всех настроек (удобно при закрытии окна) -----
    def save_all(self) -> None:
        """Ничего не делает, так как каждый сеттер сразу пишет в БД.
           Оставлен для единообразия."""
        pass