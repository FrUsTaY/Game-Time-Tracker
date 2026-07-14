"""
settings_window.py — окно настроек GameTimeTracker.
"""

import customtkinter as ctk
from tkinter import messagebox, filedialog
import os
import shutil
from datetime import datetime

from database import Database
from settings import AppSettings


class SettingsWindow(ctk.CTkToplevel):
    def __init__(self, parent, db: Database, settings: AppSettings):
        super().__init__(parent)
        self.db = db
        self.settings = settings

        self.title("Настройки GameTimeTracker")
        self.geometry("600x550")
        self.resizable(False, False)
        # Скрываем окно до позиционирования
        self.withdraw()
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - (self.winfo_width() // 2)
        y = parent.winfo_y() + (parent.winfo_height() // 2) - (self.winfo_height() // 2)
        self.geometry(f"+{x}+{y}")
        self.grab_set()
        self.focus_force()
        self.deiconify()   # показываем окно уже в центре

        self.vars = {}
        self._build_ui()
        self._load_settings()

    def _build_ui(self):
        main_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        # ---- Автозапуск ----
        self._add_section(main_frame, "Автозапуск")
        self.vars["autostart"] = ctk.BooleanVar()
        autostart_switch = ctk.CTkSwitch(
            main_frame, text="Запускать вместе с Windows",
            variable=self.vars["autostart"], command=self._on_autostart_toggle,
            text_color="#e0e0e0"
        )
        autostart_switch.pack(anchor="w", padx=20, pady=(0, 10))

        # ---- Трей ----
        self._add_section(main_frame, "Трей")
        self.vars["minimize_to_tray_on_start"] = ctk.BooleanVar()
        minimize_switch = ctk.CTkSwitch(
            main_frame, text="Сворачивать в трей при запуске",
            variable=self.vars["minimize_to_tray_on_start"],
            text_color="#e0e0e0"
        )
        minimize_switch.pack(anchor="w", padx=20, pady=(0, 5))
        # Изменён текст подсказки: теперь он просто информирует о поведении крестика
        info_label = ctk.CTkLabel(
            main_frame,
            text="При нажатии на крестик окно всегда сворачивается в трей",
            font=("Segoe UI", 10), text_color="#888888"
        )
        info_label.pack(anchor="w", padx=35, pady=(0, 10))

        # ---- Трекинг ----
        self._add_section(main_frame, "Трекинг")
        self.vars["track_only_active_window"] = ctk.BooleanVar()
        tracking_switch = ctk.CTkSwitch(
            main_frame, text="Считать время только при активном окне игры",
            variable=self.vars["track_only_active_window"],
            text_color="#e0e0e0"
        )
        tracking_switch.pack(anchor="w", padx=20, pady=(0, 10))

        # ---- Уведомления ----
        self._add_section(main_frame, "Уведомления")
        self.vars["notify_new_game"] = ctk.BooleanVar()
        notify_new_switch = ctk.CTkSwitch(
            main_frame, text="Уведомлять об обнаружении новой игры",
            variable=self.vars["notify_new_game"], text_color="#e0e0e0"
        )
        notify_new_switch.pack(anchor="w", padx=20, pady=(0, 5))

        self.vars["notify_long_session"] = ctk.BooleanVar()
        notify_long_switch = ctk.CTkSwitch(
            main_frame, text="Напоминать о долгой сессии",
            variable=self.vars["notify_long_session"],
            command=self._toggle_long_session_entry,
            text_color="#e0e0e0"
        )
        notify_long_switch.pack(anchor="w", padx=20, pady=(5, 0))

        minutes_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        minutes_frame.pack(anchor="w", padx=35, pady=(5, 10))
        ctk.CTkLabel(minutes_frame, text="Напоминать через:", text_color="#e0e0e0").pack(side="left")
        self.vars["long_session_minutes"] = ctk.StringVar()
        minutes_entry = ctk.CTkEntry(minutes_frame, width=60, textvariable=self.vars["long_session_minutes"], justify="center")
        minutes_entry.pack(side="left", padx=5)
        ctk.CTkLabel(minutes_frame, text="минут", text_color="#e0e0e0").pack(side="left")
        self.minutes_entry = minutes_entry

        # ---- Данные ----
        self._add_section(main_frame, "Данные")
        btn_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        btn_frame.pack(anchor="w", padx=20, pady=(0, 10), fill="x")

        export_btn = ctk.CTkButton(
            btn_frame, text="📁 Экспортировать данные в CSV",
            command=self.export_csv, fg_color="transparent",
            border_color="#00d4ff", border_width=1,
            text_color="#00d4ff", hover_color="#1a1a2e", height=35
        )
        export_btn.pack(fill="x", pady=2)

        backup_btn = ctk.CTkButton(
            btn_frame, text="💾 Создать резервную копию базы",
            command=self.backup_db, fg_color="transparent",
            border_color="#7b2fff", border_width=1,
            text_color="#7b2fff", hover_color="#1a1a2e", height=35
        )
        backup_btn.pack(fill="x", pady=2)

        open_folder_btn = ctk.CTkButton(
            btn_frame, text="📂 Открыть папку с данными",
            command=self.open_data_folder, fg_color="transparent",
            border_color="#ffaa00", border_width=1,
            text_color="#ffaa00", hover_color="#1a1a2e", height=35
        )
        open_folder_btn.pack(fill="x", pady=2)

        # ---- Кнопки внизу ----
        bottom_frame = ctk.CTkFrame(self, fg_color="transparent")
        bottom_frame.pack(side="bottom", fill="x", padx=20, pady=20)

        exit_btn = ctk.CTkButton(
            bottom_frame, text="🚪 Выйти из приложения",
            command=self.exit_app, fg_color="#ff4444",
            hover_color="#cc0000", width=150
        )
        exit_btn.pack(side="left", padx=5)

        save_btn = ctk.CTkButton(
            bottom_frame, text="Сохранить и закрыть",
            command=self.save_and_close, fg_color="#00d4ff",
            hover_color="#0099cc", width=150
        )
        save_btn.pack(side="right", padx=5)

        cancel_btn = ctk.CTkButton(
            bottom_frame, text="Отмена",
            command=self.destroy, fg_color="#555555",
            hover_color="#777777", width=100
        )
        cancel_btn.pack(side="right", padx=5)

    def _add_section(self, parent, title: str):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="x", pady=(10, 5))
        label = ctk.CTkLabel(frame, text=title, font=("Consolas", 14, "bold"), text_color="#00d4ff")
        label.pack(anchor="w")
        separator = ctk.CTkFrame(parent, height=1, fg_color="#7b2fff")
        separator.pack(fill="x", pady=(0, 10))

    def _load_settings(self):
        self.vars["autostart"].set(self.settings.autostart)
        self.vars["minimize_to_tray_on_start"].set(self.settings.minimize_to_tray_on_start)
        self.vars["track_only_active_window"].set(self.settings.track_only_active_window)
        self.vars["notify_new_game"].set(self.settings.notify_new_game)
        self.vars["notify_long_session"].set(self.settings.notify_long_session)
        self.vars["long_session_minutes"].set(str(self.settings.long_session_minutes))
        self._toggle_long_session_entry()

    def _toggle_long_session_entry(self):
        if self.vars["notify_long_session"].get():
            self.minutes_entry.configure(state="normal")
        else:
            self.minutes_entry.configure(state="disabled")

    def _on_autostart_toggle(self):
        if self.vars["autostart"].get():
            self.settings.enable_autostart()
        else:
            self.settings.disable_autostart()

    def save_and_close(self):
        self.settings.minimize_to_tray_on_start = self.vars["minimize_to_tray_on_start"].get()
        self.settings.track_only_active_window = self.vars["track_only_active_window"].get()
        self.settings.notify_new_game = self.vars["notify_new_game"].get()
        self.settings.notify_long_session = self.vars["notify_long_session"].get()
        try:
            minutes = int(self.vars["long_session_minutes"].get())
            self.settings.long_session_minutes = minutes
        except ValueError:
            pass
        self.destroy()

    def export_csv(self):
        filepath = filedialog.asksaveasfilename(
            title="Сохранить CSV", defaultextension=".csv",
            filetypes=[("CSV файлы", "*.csv"), ("Все файлы", "*.*")]
        )
        if filepath:
            success = self.db.export_sessions_csv(filepath)
            if success:
                messagebox.showinfo("Экспорт", f"Данные успешно экспортированы в:\n{filepath}")
            else:
                messagebox.showerror("Ошибка", "Не удалось экспортировать данные")

    def backup_db(self):
        backup_dir = "data/backups"
        os.makedirs(backup_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"gametracker_backup_{timestamp}.db"
        backup_path = os.path.join(backup_dir, backup_name)
        try:
            shutil.copy2(self.db.db_path, backup_path)
            messagebox.showinfo("Резервная копия", f"База данных сохранена:\n{backup_path}")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось создать резервную копию:\n{e}")

    def open_data_folder(self):
        data_dir = os.path.abspath("data")
        if os.path.exists(data_dir):
            os.startfile(data_dir)
        else:
            messagebox.showwarning("Папка не найдена", "Папка data ещё не создана.")

    def exit_app(self):
        if messagebox.askyesno("Выход", "Вы уверены, что хотите закрыть приложение?"):
            self.destroy()
            if hasattr(self.master, 'quit_app'):
                self.master.quit_app()
            else:
                import sys
                sys.exit(0)