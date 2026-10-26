import logging
import os
import sys
from datetime import date

from database import Database
from digest import format_weekly_digest, is_weekly_digest_due
from settings import AppSettings
from tracker import GameTracker
from tray import SystemTray
from ui.main_window import MainWindow
from utils import format_duration, get_base_dir, resource_path

logger = logging.getLogger(__name__)

# Как часто обновлять подсказку иконки в трее (мс)
TRAY_TOOLTIP_INTERVAL_MS = 60_000

# Задержка перед проверкой еженедельной сводки после старта (мс):
# даём приложению и трею полностью инициализироваться.
WEEKLY_DIGEST_DELAY_MS = 3_000


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
        self._tooltip_job = None
        self._weekly_digest_job = None

        # Проверка целостности БД и автоматическая резервная копия при запуске
        self._check_database_integrity()
        self._create_startup_backup()

        self._init_ui()
        self._init_tracker()
        self._init_tray()
        self.window.protocol("WM_DELETE_WINDOW", self.on_window_close)

    def _check_database_integrity(self) -> None:
        """Предупреждает пользователя, если файл базы данных повреждён."""
        try:
            if self.db.check_integrity():
                return
            logger.error("База данных повреждена: %s", self.db.db_path)
            if self.tray is not None:
                self.tray.show_notification(
                    "GameTimeTracker",
                    "⚠ Обнаружено повреждение базы данных. Используйте последнюю "
                    "резервную копию из папки data/backups."
                )
        except Exception as e:
            logger.warning("Не удалось проверить целостность БД: %s", e)

    def _maybe_send_weekly_digest(self) -> None:
        """
        Раз в неделю показывает ненавязчивую сводку игровой активности.

        Отправка не чаще одного раза в 7 дней (дата хранится в настройках),
        без активности за период сводка не отправляется.
        """
        try:
            self._weekly_digest_job = None
            if self._is_exiting or not self.settings.weekly_summary_enabled:
                return
            if not is_weekly_digest_due(self.settings.last_weekly_summary_date):
                return
            summary = self.db.get_weekly_digest()
            if int(summary.get('total_seconds') or 0) <= 0:
                return
            message = format_weekly_digest(summary)
            if self.tray is not None:
                self.tray.show_notification("Итоги недели", message)
            else:
                logger.info("Итоги недели: %s", message)
            self.settings.last_weekly_summary_date = date.today().isoformat()
        except Exception as e:
            logger.warning("Не удалось отправить еженедельную сводку: %s", e)

    def _create_startup_backup(self) -> None:
        """Создаёт ротационную резервную копию БД при запуске приложения."""
        try:
            if not self.settings.backup_on_startup:
                return
            backup_path = self.db.create_rotating_backup(keep=self.settings.backup_keep)
            if backup_path:
                logger.info("Резервная копия при запуске: %s", backup_path)
        except Exception as e:
            logger.warning("Не удалось создать резервную копию при запуске: %s", e)

    def _init_ui(self):
        self.window = MainWindow(self.db, None, self.settings, on_exit=self.exit_app)
        self._refresh_tray_tooltip()

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
        # Еженедельная сводка — после полной инициализации UI и трея
        if self.window is not None:
            try:
                self._weekly_digest_job = self.window.after(
                    WEEKLY_DIGEST_DELAY_MS, self._maybe_send_weekly_digest
                )
            except Exception:
                pass

        if self.settings.minimize_to_tray_on_start:
            self._background_notified = True
            self.window.after(100, self.window.hide_to_tray)
            self.tray.show_notification(
                "GameTimeTracker",
                "Приложение запущено и работает в фоновом режиме"
            )

    def _refresh_tray_tooltip(self) -> None:
        """Периодически обновляет подсказку трея со временем за сегодня."""
        if getattr(self, '_is_exiting', False):
            return
        try:
            tracker = getattr(self, 'tracker', None)
            db = getattr(self, 'db', None)
            tray = getattr(self, 'tray', None)
            if tracker is not None:
                seconds = tracker.get_live_today_seconds()
            elif db is not None:
                seconds = db.get_today_seconds()
            else:
                seconds = 0
            if tray is not None:
                tray.set_tooltip(f"GameTimeTracker — сегодня {format_duration(seconds)}")
        except Exception as e:
            logger.debug("Ошибка обновления подсказки трея: %s", e)

        window = getattr(self, 'window', None)
        if window is not None and not getattr(self, '_is_exiting', False):
            try:
                self._tooltip_job = window.after(
                    TRAY_TOOLTIP_INTERVAL_MS, self._refresh_tray_tooltip
                )
            except Exception:
                pass

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

        # 0. Останавливаем отложенные задачи Tkinter
        for job_attr in ('_weekly_digest_job', '_tooltip_job'):
            job = getattr(self, job_attr, None)
            if job is not None and getattr(self, 'window', None):
                try:
                    self.window.after_cancel(job)
                except Exception:
                    pass
                setattr(self, job_attr, None)

        # 1. Остановка трекера (сохраняет накопленные данные сессий в БД)
        if self.tracker:
            try:
                self.tracker.stop()
            except Exception as e:
                logger.warning("Ошибка при остановке трекера: %s", e)

        # 2. Остановка трея
        if self.tray:
            try:
                self.tray.stop()
            except Exception as e:
                logger.warning("Ошибка при остановке трея: %s", e)

        # 3. Закрытие соединения с базой данных
        if self.db:
            try:
                self.db.close()
            except Exception as e:
                logger.warning("Ошибка при закрытии базы данных: %s", e)

        # 4. Завершение работы Tkinter и уничтожение главного окна
        if self.window:
            try:
                self.window.quit()
                self.window.destroy()
            except Exception as e:
                logger.warning("Ошибка при уничтожении окна: %s", e)

        # 5. Завершение процесса
        sys.exit(0)

    def run(self):
        self.window.mainloop()
