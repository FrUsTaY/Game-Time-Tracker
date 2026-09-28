import os
import sys
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import customtkinter as ctk
from PIL import Image
from ui.tab_about import TabAbout


class TestTabAbout(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Создаем скрытый корневой виджет для Tkinter тестов
        cls.root = ctk.CTk()
        cls.root.withdraw()

    @classmethod
    def tearDownClass(cls):
        cls.root.destroy()

    def test_pre_rendered_frames_generated(self):
        """Проверка, что кадры анимации предварительно сгенерированы."""
        tab = TabAbout(self.root)
        self.assertGreaterEqual(len(tab.pulse_frames), 6)
        # Проверяем, что кадры не пустые и являются ImageTk.PhotoImage
        for frame in tab.pulse_frames:
            self.assertIsNotNone(frame)
        tab.stop_animation()
        tab.destroy()

    def test_animation_start_stop(self):
        """Проверка запуска и остановки анимации пульсации."""
        tab = TabAbout(self.root)
        tab.stop_animation()
        self.assertFalse(tab._animating)
        self.assertIsNone(tab._after_id)

        tab.start_animation()
        self.assertTrue(tab._animating)
        self.assertIsNotNone(tab._after_id)

        tab.stop_animation()
        self.assertFalse(tab._animating)
        self.assertIsNone(tab._after_id)
        tab.destroy()

    def test_animate_step_does_not_call_resize(self):
        """Проверка, что шаг анимации _animate_step не вызывает Image.resize."""
        tab = TabAbout(self.root)
        tab.stop_animation()

        with patch.object(Image.Image, 'resize') as mock_resize:
            tab._animating = True
            tab._animate_step()
            mock_resize.assert_not_called()

        tab.stop_animation()
        tab.destroy()

    def test_map_unmap_lifecycle(self):
        """Проверка реакции на события Map и Unmap."""
        tab = TabAbout(self.root)
        tab.stop_animation()

        event = MagicMock()
        event.widget = tab

        # Событие Map включает анимацию
        tab._on_map(event)
        self.assertTrue(tab._animating)

        # Событие Unmap останавливает анимацию
        tab._on_unmap(event)
        self.assertFalse(tab._animating)
        self.assertIsNone(tab._after_id)

        tab.destroy()


if __name__ == '__main__':
    unittest.main()
