import os
import sys

from database import Database
from settings import AppSettings
from tracker import GameTracker
from ui.main_window import MainWindow
from tray import SystemTray
from utils import get_base_dir, resource_path


get_app_dir = get_base_dir


class App:
    def __init__(self):
        # Используем абсолютный путь для БД, чтобы избежать проблем с автозагрузкой
        db_path = os.path.join(get_base_dir(), "data", "gametracker.db")
        self.db = Database(db_path)
        self.settings = AppSettings(self.db)
        # Настройки загружаются из БД, ничего не переопределяем
        self.tracker = None
        self.window = None
        self.tray = None
        self.on_tick_callback = None
        self._is_exiting = False
        self._background_notified = False

        self._init_ui()
        self._init_tracker()
        self._init_tray()
        self.window.protocol("WM_DELETE_WINDOW", self.on_window_close)

    def _init_ui(self):
        self.window = MainWindow(self.db, None, self.settings, on_exit=self.exit_app)

    def _init_tracker(self):
        def _safe_on_game_detected(exe_name, exe_path):
            if not self._is_exiting and self.window:
                try:
                    self.window.after(0, lambda: self.window.add_detected_notification(exe_name, exe_path))
                except Exception:
                    pass

        # Создаём трекер с временным колбэком
        self.tracker = GameTracker(self.db, self.settings, None, on_game_detected=_safe_on_game_detected)
        self.window.tracker = self.tracker
        # Обновляем трекер во всех вкладках кеша
        for tab in self.window.tabs_cache.values():
            if tab and hasattr(tab, 'tracker'):
                tab.tracker = self.tracker
        # Устанавливаем колбэк для обновления времени из вкладки "Мои игры"
        if "games" in self.window.tabs_cache:
            games_tab = self.window.tabs_cache["games"]
            if hasattr(games_tab, 'update_tick'):
                def _safe_dispatch_tick(gid, total, active):
                    if not self._is_exiting and self.window:
                        try:
                            self.window.after(0, lambda: games_tab.update_tick(gid, total, active))
                        except Exception:
                            pass
                self.tracker.on_tick = _safe_dispatch_tick
        self.tracker.start()

    def _init_tray(self):
        self.tray = SystemTray(
            icon_path=resource_path("assets/icon.png"),
            on_open=self.show_window,
            on_settings=self.open_settings,
            on_exit=self.exit_app,
            on_notification_click=self.on_notification_click
        )
        if self.tracker:
            self.tracker.tray = self.tray
        self.tray.start()
        if self.settings.minimize_to_tray_on_start:
            self._background_notified = True
            self.window.after(100, self.window.hide_to_tray)
            self.tray.show_notification(
                "GameTimeTracker",
                "Приложение запущено и работает в фоновом режиме"
            )

    def show_notification(self, title: str, message: str):
        if self.tray:
            self.tray.show_notification(title, message)

    def show_window(self, *args):
        if self.window:
            try:
                self.window.after(0, self.window.show_window)
            except Exception:
                pass

    def open_settings(self, *args):
        if self.window:
            try:
                self.window.after(0, self.window.open_settings)
            except Exception:
                pass

    def on_notification_click(self, *args):
        if self.window and not self._is_exiting:
            try:
                self.window.after(0, self.window.open_detected_game_from_notification)
            except Exception:
                pass

    def on_window_close(self):
        if self.tray and not getattr(self, '_background_notified', False):
            self._background_notified = True
            self.tray.show_notification(
                "GameTimeTracker",
                "Приложение продолжает работать в фоне"
            )
        self.window.hide_to_tray()

    def exit_app(self, *args):
        if self._is_exiting:
            return
        if self.window:
            try:
                self.window.after(0, self._perform_exit)
                return
            except Exception:
                pass
        self._perform_exit()

    def _perform_exit(self):
        if self._is_exiting:
            return
        self._is_exiting = True

        # 1. Остановка трекера (сохраняет накопленные данные сессий в БД)
        if self.tracker:
            try:
                self.tracker.stop()
            except Exception as e:
                print(f"Ошибка при остановке трекера: {e}")

        # 2. Остановка трея
        if self.tray:
            try:
                self.tray.stop()
            except Exception as e:
                print(f"Ошибка при остановке трея: {e}")

        # 3. Закрытие соединения с базой данных
        if self.db:
            try:
                self.db.close()
            except Exception as e:
                print(f"Ошибка при закрытии базы данных: {e}")

        # 4. Завершение работы Tkinter и уничтожение главного окна
        if self.window:
            try:
                self.window.quit()
                self.window.destroy()
            except Exception as e:
                print(f"Ошибка при уничтожении окна: {e}")

        # 5. Завершение процесса
        sys.exit(0)

    def run(self):
        self.window.mainloop()