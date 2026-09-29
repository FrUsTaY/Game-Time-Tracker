"""
tray.py — модуль системного трея для GameTimeTracker.
"""

import threading
import pystray
from PIL import Image, ImageDraw
import os
import sys
from typing import Callable
from utils import resource_path


class SystemTray:
    """Класс для управления иконкой в системном трее."""

    def __init__(
        self,
        icon_path: str,
        on_open: Callable,
        on_settings: Callable,
        on_exit: Callable,
        on_notification_click: Callable = None
    ):
        self.icon_path = icon_path
        self.on_open = on_open
        self.on_settings = on_settings
        self.on_exit = on_exit
        self.on_notification_click = on_notification_click

        self.icon = None
        self.thread = None
        self._running = False

        self._image = self._load_icon()

    def _load_icon(self) -> Image.Image:
        full_path = resource_path(self.icon_path)
        if os.path.exists(full_path):
            try:
                return Image.open(full_path)
            except Exception as e:
                print(f"Ошибка загрузки иконки трея: {e}")
        # Иконка-заглушка
        size = 64
        img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.ellipse((8, 8, size-8, size-8), fill=(0, 212, 255, 255))
        draw.ellipse((24, 24, size-24, size-24), fill=(13, 13, 13, 255))
        return img

    def _setup_menu(self):
        return pystray.Menu(
            pystray.MenuItem("Открыть GameTimeTracker", self._on_open, default=True),
            pystray.MenuItem("Настройки", self._on_settings),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Выход", self._on_exit)
        )

    def _on_open(self, icon=None, item=None):
        if self.on_open:
            self.on_open()

    def _on_settings(self, icon=None, item=None):
        if self.on_settings:
            self.on_settings()

    def _on_exit(self, icon=None, item=None):
        """Обработчик выхода. Вызывается в потоке трея."""
        # Не вызываем self.stop() здесь, чтобы избежать self-join
        if self.on_exit:
            self.on_exit()

    def _run(self):
        self.icon = pystray.Icon("GameTimeTracker", self._image, "GameTimeTracker", self._setup_menu())
        orig_on_notify = getattr(self.icon, '_on_notify', None)

        def custom_on_notify(wparam, lparam):
            # 1029 (0x0405) = NIN_BALLOONUSERCLICK в Windows
            # Проверяем как lparam, так и LOWORD(lparam) для различных версий Shell_NotifyIcon
            event_code = (lparam & 0xFFFF) if isinstance(lparam, int) else lparam
            if event_code == 1029 or lparam == 1029:
                if self.on_notification_click:
                    try:
                        self.on_notification_click()
                    except Exception as e:
                        print(f"SystemTray: ошибка в on_notification_click: {e}")
            if orig_on_notify:
                try:
                    return orig_on_notify(wparam, lparam)
                except Exception:
                    return 0
            return 0

        self.icon._on_notify = custom_on_notify
        if hasattr(self.icon, '_message_handlers'):
            for k, handler in list(self.icon._message_handlers.items()):
                if getattr(handler, '__name__', '') == '_on_notify':
                    self.icon._message_handlers[k] = custom_on_notify
            try:
                import pystray._win32 as pystray_win32
                if hasattr(pystray_win32, 'win32') and hasattr(pystray_win32.win32, 'WM_NOTIFY'):
                    self.icon._message_handlers[pystray_win32.win32.WM_NOTIFY] = custom_on_notify
            except Exception:
                pass

        self.icon.run()

    def start(self):
        if self._running:
            return
        self._running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        print("SystemTray: иконка трея запущена")

    def stop(self):
        """Останавливает иконку трея. Вызывать из основного потока."""
        self._running = False
        if self.icon:
            self.icon.stop()
        # Присоединяем поток только если он не является текущим
        if self.thread and self.thread.is_alive() and self.thread != threading.current_thread():
            self.thread.join(timeout=1.0)
        print("SystemTray: иконка трея остановлена")

    def show_notification(self, title: str, message: str):
        if self.icon and self._running:
            try:
                self.icon.notify(message, title)
                return
            except Exception:
                pass
        try:
            from plyer import notification
            notification.notify(title=title, message=message, app_name="GameTimeTracker", timeout=5)
        except ImportError:
            print(f"Уведомление: {title} - {message}")
        except Exception as e:
            print(f"Ошибка показа уведомления: {e}")