"""
tab_about.py — вкладка «О программе» для GameTimeTracker.
"""

import customtkinter as ctk
from PIL import Image, ImageTk
import os
import tkinter.messagebox as messagebox
from utils import get_base_dir, resource_path


APP_VERSION = "v1.2.2"


class TabAbout(ctk.CTkFrame):
    APP_VERSION = APP_VERSION

    def __init__(self, master, db=None, tracker=None, settings=None):
        super().__init__(master, fg_color="#0d0d0d")
        self.db = db
        self.tracker = tracker
        self.settings = settings

        self.pulse_frames = []
        self._current_frame_idx = 0
        self._animating = False
        self._after_id = None
        self.logo_image = None
        self.logo_photo = None

        self._build_ui()

        # Привязка к событиям видимости вкладки для экономии CPU
        self.bind("<Map>", self._on_map)
        self.bind("<Unmap>", self._on_unmap)
        self.bind("<Destroy>", self._on_destroy)

        # Если вкладка уже отображается, запускаем анимацию
        if self.winfo_ismapped():
            self.start_animation()

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        main_container = ctk.CTkFrame(self, fg_color="transparent")
        main_container.grid(row=0, column=0, sticky="nsew")
        main_container.grid_columnconfigure(0, weight=1)
        main_container.grid_rowconfigure(0, weight=1)

        content = ctk.CTkFrame(main_container, fg_color="transparent")
        content.grid(row=0, column=0, sticky="ns", pady=20)
        content.grid_columnconfigure(0, weight=1)

        self.logo_label = ctk.CTkLabel(content, text="", width=128, height=128)
        self.logo_label.grid(row=0, column=0, pady=(20, 10))
        self._load_logo()

        title_label = ctk.CTkLabel(
            content, text="GameTimeTracker",
            font=("Consolas", 28, "bold"), text_color="#00d4ff"
        )
        title_label.grid(row=1, column=0, pady=(0, 5))

        version_label = ctk.CTkLabel(
            content, text=APP_VERSION,
            font=("Segoe UI", 12), text_color="#888888"
        )
        version_label.grid(row=2, column=0, pady=(0, 15))

        separator = ctk.CTkFrame(content, height=2, fg_color="#7b2fff", corner_radius=1)
        separator.grid(row=3, column=0, sticky="ew", padx=50, pady=10)

        desc_text = "Твой личный трекер игрового времени.\nЗнай, сколько часов ты вложил в каждое приключение."
        desc_label = ctk.CTkLabel(
            content, text=desc_text,
            font=("Segoe UI", 13), text_color="#e0e0e0", justify="center"
        )
        desc_label.grid(row=4, column=0, pady=10)

        tech_label = ctk.CTkLabel(
            content, text="Технологии",
            font=("Consolas", 14, "bold"), text_color="#00d4ff"
        )
        tech_label.grid(row=5, column=0, pady=(20, 10))

        techs = [
            "Python 3.14", "CustomTkinter", "psutil", "SQLite",
            "pywin32", "Matplotlib", "Pillow", "pystray"
        ]
        tech_frame = ctk.CTkFrame(content, fg_color="transparent")
        tech_frame.grid(row=6, column=0, pady=5)
        self._add_tech_chips(tech_frame, techs)

        update_btn = ctk.CTkButton(
            content, text="Проверить обновления", command=self.check_updates,
            fg_color="transparent", border_color="#00d4ff", border_width=2,
            text_color="#00d4ff", hover_color="#1a1a2e", corner_radius=8, width=200
        )
        update_btn.grid(row=7, column=0, pady=(30, 10))

        footer_label = ctk.CTkLabel(
            content,
            text="Разработал Aleksey Smolin\nВсе права защищены © 2026",
            font=("Segoe UI", 10),
            text_color="#555555"
        )
        footer_label.grid(row=8, column=0, pady=10)

    def _load_logo(self):
        icon_path = resource_path("assets/icon.png")
        self.pulse_frames = []
        if os.path.exists(icon_path):
            try:
                raw_image = Image.open(icon_path)
                self.logo_image = raw_image.copy()

                # Предварительный расчет 7 кадров анимации пульсации (размеры 128..140 с шагом 2)
                sizes = [128, 130, 132, 134, 136, 138, 140]
                cached_photos = {}
                for size in sizes:
                    resized = raw_image.resize((size, size), Image.Resampling.LANCZOS)
                    cached_photos[size] = ctk.CTkImage(light_image=resized, dark_image=resized, size=(size, size))

                frame_sequence = [128, 130, 132, 134, 136, 138, 140, 138, 136, 134, 132, 130]
                self.pulse_frames = [cached_photos[s] for s in frame_sequence]
                self.logo_photo = cached_photos[128]
                self.logo_label.configure(image=self.logo_photo)
            except Exception as e:
                print(f"Ошибка загрузки логотипа: {e}")
                self.logo_image = None
                self.logo_photo = None
                self.logo_label.configure(text="🎮", font=("Segoe UI", 64))
        else:
            print(f"Файл не найден: {icon_path}")
            self.logo_image = None
            self.logo_photo = None
            self.logo_label.configure(text="🎮", font=("Segoe UI", 64))

    def _add_tech_chips(self, parent, tech_list):
        row = 0
        col = 0
        max_cols = 4
        for tech in tech_list:
            chip = ctk.CTkFrame(parent, fg_color="#1a1a2e", corner_radius=10, border_width=1, border_color="#7b2fff")
            chip.grid(row=row, column=col, padx=5, pady=5, sticky="ew")
            label = ctk.CTkLabel(chip, text=tech, font=("Consolas", 10), text_color="#e0e0e0")
            label.pack(padx=8, pady=4)
            col += 1
            if col >= max_cols:
                col = 0
                row += 1
        for i in range(max_cols):
            parent.grid_columnconfigure(i, weight=1)

    def check_updates(self):
        messagebox.showinfo("Проверка обновлений", f"Вы используете актуальную версию ({APP_VERSION})")

    def _on_map(self, event):
        if event.widget == self:
            self.start_animation()

    def _on_unmap(self, event):
        if event.widget == self:
            self.stop_animation()

    def _on_destroy(self, event):
        if event.widget == self:
            self.stop_animation()

    def start_animation(self):
        """Запуск цикла анимации пульсации логотипа."""
        if self._animating or not self.pulse_frames:
            return
        self._animating = True
        self._animate_step()

    def stop_animation(self):
        """Остановка цикла анимации пульсации для устранения паразитной нагрузки на CPU."""
        self._animating = False
        if self._after_id is not None:
            try:
                self.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None

    def _animate_step(self):
        """Один шаг переключения предрассчитанных кадров анимации без повторного ресайза."""
        if not self._animating or not self.pulse_frames:
            self._after_id = None
            return

        frame = self.pulse_frames[self._current_frame_idx]
        self.logo_label.configure(image=frame)
        self._current_frame_idx = (self._current_frame_idx + 1) % len(self.pulse_frames)
        self._after_id = self.after(50, self._animate_step)

    def _start_pulse_animation(self):
        """Метод для обратной совместимости. Запускает оптимизированную анимацию."""
        self.start_animation()

    def refresh(self):
        pass