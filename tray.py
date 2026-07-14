"""
tray.py — модуль системного трея для GameTimeTracker.
"""

import threading
import pystray
from PIL import Image, ImageDraw
import os
import sys
from typing import Callable

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


class SystemTray:
    """Класс для управления иконкой в системном трее."""

    def __init__(
        self,
        icon_path: str,
        on_open: Callable,
        on_settings: Callable,
        on_exit: Callable
    ):
        self.icon_path = icon_path
        self.on_open = on_open
        self.on_settings = on_settings
        self.on_exit = on_exit

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
            pystray.MenuItem("Открыть GameTimeTracker", self.on_open, default=True),
            pystray.MenuItem("Настройки", self.on_settings),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Выход", self._on_exit)
        )

    def _on_exit(self, icon, item):
        """Обработчик выхода. Вызывается в потоке трея."""
        # Не вызываем self.stop() здесь, чтобы избежать self-join
        self.on_exit()

    def _run(self):
        self.icon = pystray.Icon("GameTimeTracker", self._image, "GameTimeTracker", self._setup_menu())
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
            except AttributeError:
                try:
                    from plyer import notification
                    notification.notify(title=title, message=message, app_name="GameTimeTracker", timeout=5)
                except ImportError:
                    print(f"Уведомление: {title} - {message}")
                except Exception as e:
                    print(f"Ошибка показа уведомления: {e}")
        else:
            print(f"Уведомление (трей не активен): {title} - {message}")