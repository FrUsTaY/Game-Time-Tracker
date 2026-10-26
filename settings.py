"""
Модуль управления настройками приложения GameTimeTracker.
Использует реестр Windows для автозапуска и базу данных для остальных настроек.
"""

import os
import sys

try:  # winreg доступен только в Windows — это позволяет запускать тесты на Linux/CI
    import winreg
    WINREG_AVAILABLE = True
except ImportError:  # pragma: no cover - зависит от платформы
    winreg = None
    WINREG_AVAILABLE = False

from database import Database
from utils import get_base_dir

# Значения по умолчанию для новых настроек (используются в UI и трекере)
DEFAULT_PAUSE_WHEN_IDLE = False
DEFAULT_IDLE_THRESHOLD_MINUTES = 5
DEFAULT_DAILY_LIMIT_ENABLED = False
DEFAULT_DAILY_LIMIT_MINUTES = 180
DEFAULT_BACKUP_ON_STARTUP = True
DEFAULT_BACKUP_KEEP = 7


class AppSettings:
    """Класс для удобного доступа к настройкам приложения"""

    def __init__(self, db: Database):
        self.db = db
        self._cache = {}  # Простой кеш на время жизни объекта

    def invalidate_cache(self, key: str = None) -> None:
        """Сбрасывает кэш настроек (полностью или для одного ключа)."""
        if key is None:
            self._cache.clear()
        else:
            self._cache.pop(key, None)

    def _get_bool(self, key: str, default: bool) -> bool:
        """Получить булево значение из БД (с кэшированием)"""
        if key in self._cache:
            return self._cache[key]
        val = self.db.get_setting(key)
        if val is None:
            self._cache[key] = default
            return default
        res = val.lower() == 'true'
        self._cache[key] = res
        return res

    def _set_bool(self, key: str, value: bool) -> None:
        """Сохранить булево значение в БД"""
        self.db.set_setting(key, 'true' if value else 'false')
        self._cache[key] = value

    def _get_int(self, key: str, default: int) -> int:
        """Получить целочисленное значение из БД (с кэшированием)"""
        if key in self._cache:
            return self._cache[key]
        val = self.db.get_setting(key)
        if val is None:
            self._cache[key] = default
            return default
        try:
            res = int(val)
            self._cache[key] = res
            return res
        except ValueError:
            self._cache[key] = default
            return default

    def _set_int(self, key: str, value: int) -> None:
        """Сохранить целочисленное значение в БД"""
        self.db.set_setting(key, str(value))
        self._cache[key] = value

    # ----- Автозапуск (работа с реестром) -----

    def enable_autostart(self) -> None:
        """Добавляет приложение в автозапуск Windows (HKCU)"""
        if winreg is None:
            print("Автозапуск доступен только в Windows")
            return
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0, winreg.KEY_SET_VALUE
            )
            # Путь к текущему исполняемому файлу (поддерживает .exe и .py)
            if getattr(sys, 'frozen', False):
                # Запущено как .exe
                app_path = f'"{sys.executable}"'
            else:
                # Запущено как скрипт
                main_script = os.path.abspath(os.path.join(get_base_dir(), "main.py"))
                app_path = f'"{sys.executable}" "{main_script}"'

            winreg.SetValueEx(key, "GameTimeTracker", 0, winreg.REG_SZ, app_path)
            winreg.CloseKey(key)
            self._set_bool("autostart", True)
        except Exception as e:
            print(f"Ошибка включения автозапуска: {e}")

    def disable_autostart(self) -> None:
        """Удаляет приложение из автозапуска"""
        if winreg is None:
            return
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
        if winreg is None:
            return False
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

    # ----- Пауза при бездействии (AFK) -----

    @property
    def pause_when_idle(self) -> bool:
        """Не учитывать время, если пользователь неактивен (нет ввода мыши/клавиатуры)."""
        return self._get_bool("pause_when_idle", DEFAULT_PAUSE_WHEN_IDLE)

    @pause_when_idle.setter
    def pause_when_idle(self, value: bool) -> None:
        self._set_bool("pause_when_idle", value)

    @property
    def idle_threshold_minutes(self) -> int:
        """Порог бездействия в минутах, после которого трекинг приостанавливается."""
        return self._get_int("idle_threshold_minutes", DEFAULT_IDLE_THRESHOLD_MINUTES)

    @idle_threshold_minutes.setter
    def idle_threshold_minutes(self, value: int) -> None:
        if value < 1:
            value = 1
        self._set_int("idle_threshold_minutes", value)

    # ----- Дневной лимит игрового времени -----

    @property
    def daily_limit_enabled(self) -> bool:
        """Включён ли дневной лимит игрового времени."""
        return self._get_bool("daily_limit_enabled", DEFAULT_DAILY_LIMIT_ENABLED)

    @daily_limit_enabled.setter
    def daily_limit_enabled(self, value: bool) -> None:
        self._set_bool("daily_limit_enabled", value)

    @property
    def daily_limit_minutes(self) -> int:
        """Дневной лимит игрового времени в минутах."""
        return self._get_int("daily_limit_minutes", DEFAULT_DAILY_LIMIT_MINUTES)

    @daily_limit_minutes.setter
    def daily_limit_minutes(self, value: int) -> None:
        if value < 5:
            value = 5
        self._set_int("daily_limit_minutes", value)

    # ----- Резервное копирование -----

    @property
    def backup_on_startup(self) -> bool:
        """Создавать резервную копию базы при каждом запуске приложения."""
        return self._get_bool("backup_on_startup", DEFAULT_BACKUP_ON_STARTUP)

    @backup_on_startup.setter
    def backup_on_startup(self, value: bool) -> None:
        self._set_bool("backup_on_startup", value)

    @property
    def backup_keep(self) -> int:
        """Сколько последних автоматических резервных копий хранить."""
        value = self._get_int("backup_keep", DEFAULT_BACKUP_KEEP)
        if value < 1:
            value = 1
        return value

    @backup_keep.setter
    def backup_keep(self, value: int) -> None:
        if value < 1:
            value = 1
        self._set_int("backup_keep", value)

    # ----- Сохранение всех настроек (удобно при закрытии окна) -----
    def save_all(self) -> None:
        """Ничего не делает, так как каждый сеттер сразу пишет в БД.
           Оставлен для единообразия."""
        pass
