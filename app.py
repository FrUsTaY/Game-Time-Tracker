import os
import sys
from tkinter import messagebox

from database import Database
from settings import AppSettings
from tracker import GameTracker
from ui.main_window import MainWindow
from tray import SystemTray


def get_app_dir():
    """Возвращает абсолютный путь к директории, в которой находится исполняемый файл или скрипт."""
    if getattr(sys, 'frozen', False):
        # Если запущено как скомпилированный .exe (через PyInstaller)
        return os.path.dirname(sys.executable)
    else:
        # Если запущено как обычный python скрипт
        return os.path.dirname(os.path.abspath(__file__))


class App:
    def __init__(self):
        # Используем абсолютный путь для БД, чтобы избежать проблем с автозагрузкой
        db_path = os.path.join(get_app_dir(), "data", "gametracker.db")
        self.db = Database(db_path)
        self.settings = AppSettings(self.db)
        # Настройки загружаются из БД, ничего не переопределяем
        self.tracker = None
        self.window = None
        self.tray = None
        self.on_tick_callback = None
        self._is_exiting = False

        self._init_ui()
        self._init_tracker()
        self._init_tray()
        self.window.protocol("WM_DELETE_WINDOW", self.on_window_close)

    def _init_ui(self):
        self.window = MainWindow(self.db, None, self.settings)

    def _init_tracker(self):
        # Создаём трекер с временным колбэком
        self.tracker = GameTracker(self.db, self.settings, None)
        self.window.tracker = self.tracker
        # Обновляем трекер во всех вкладках кеша
        for tab in self.window.tabs_cache.values():
            if tab and hasattr(tab, 'tracker'):
                tab.tracker = self.tracker
        # Устанавливаем колбэк для обновления времени из вкладки "Мои игры"
        if "games" in self.window.tabs_cache:
            games_tab = self.window.tabs_cache["games"]
            if hasattr(games_tab, 'update_tick'):
                self.tracker.on_tick = games_tab.update_tick
                print("DEBUG: on_tick установлен на games_tab.update_tick")
        else:
            print("DEBUG: Вкладка games не найдена в кеше")
        self.tracker.start()

    def _init_tray(self):
        self.tray = SystemTray(
            icon_path="assets/icon.png",
            on_open=self.show_window,
            on_settings=self.open_settings,
            on_exit=self.exit_app
        )
        self.tray.start()
        if self.settings.minimize_to_tray_on_start:
            self.window.after(100, self.window.hide_to_tray)
            self.tray.show_notification(
                "GameTimeTracker",
                "Приложение запущено и работает в фоновом режиме"
            )

    def show_window(self):
        if self.window:
            self.window.show_window()

    def open_settings(self):
        if self.window:
            self.window.open_settings()

    def on_window_close(self):
        if self.tray:
            self.tray.show_notification(
                "GameTimeTracker",
                "Приложение продолжает работать в фоне"
            )
        self.window.hide_to_tray()

    def exit_app(self):
        if self._is_exiting:
            return
        self._is_exiting = True
        if self.tracker:
            self.tracker.stop()
        if self.tray:
            self.tray.stop()
        if self.window:
            self.window.quit()
            self.window.destroy()
        if self.db:
            self.db.close()
        sys.exit(0)

    def run(self):
        self.window.mainloop()