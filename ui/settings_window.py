"""
settings_window.py — окно настроек GameTimeTracker.
"""

import os
from datetime import datetime
from tkinter import filedialog, messagebox

import customtkinter as ctk

from database import Database
from settings import AppSettings
from utils import get_base_dir


class SettingsWindow(ctk.CTkToplevel):
    def __init__(self, parent, db: Database, settings: AppSettings):
        super().__init__(parent)
        self.db = db
        self.settings = settings

        self.title("Настройки GameTimeTracker")
        self.geometry("620x640")
        self.resizable(False, False)
        self.transient(parent)
        # Скрываем окно до позиционирования
        self.withdraw()
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - (self.winfo_width() // 2)
        y = parent.winfo_y() + (parent.winfo_height() // 2) - (self.winfo_height() // 2)
        self.geometry(f"+{x}+{y}")
        self.deiconify()   # показываем окно уже в центре
        self.lift()
        self.grab_set()
        self.focus_force()
        self.after(20, self.lift)

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
            variable=self.vars["autostart"],
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

        # ---- Бездействие (AFK) ----
        self._add_section(main_frame, "Бездействие (AFK)")
        self.vars["pause_when_idle"] = ctk.BooleanVar()
        idle_switch = ctk.CTkSwitch(
            main_frame, text="Не считать время, если пользователь отошёл",
            variable=self.vars["pause_when_idle"],
            command=self._toggle_idle_entry,
            text_color="#e0e0e0"
        )
        idle_switch.pack(anchor="w", padx=20, pady=(0, 5))
        idle_hint = ctk.CTkLabel(
            main_frame,
            text="Время не учитывается, если мышь и клавиатура неактивны дольше порога.\n"
                 "Полезно, если игра остаётся открытой без присмотра.",
            font=("Segoe UI", 10), text_color="#888888", justify="left"
        )
        idle_hint.pack(anchor="w", padx=35, pady=(0, 5))

        idle_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        idle_frame.pack(anchor="w", padx=35, pady=(0, 10))
        ctk.CTkLabel(idle_frame, text="Порог бездействия:", text_color="#e0e0e0").pack(side="left")
        self.vars["idle_threshold_minutes"] = ctk.StringVar()
        self.idle_entry = ctk.CTkEntry(
            idle_frame, width=60, textvariable=self.vars["idle_threshold_minutes"], justify="center"
        )
        self.idle_entry.pack(side="left", padx=5)
        ctk.CTkLabel(idle_frame, text="минут", text_color="#e0e0e0").pack(side="left")

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

        # ---- Дневной лимит ----
        self._add_section(main_frame, "Дневной лимит")
        self.vars["daily_limit_enabled"] = ctk.BooleanVar()
        limit_switch = ctk.CTkSwitch(
            main_frame, text="Напоминать о достижении дневного лимита",
            variable=self.vars["daily_limit_enabled"],
            command=self._toggle_limit_entry,
            text_color="#e0e0e0"
        )
        limit_switch.pack(anchor="w", padx=20, pady=(0, 5))

        limit_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        limit_frame.pack(anchor="w", padx=35, pady=(5, 10))
        ctk.CTkLabel(limit_frame, text="Лимит в день:", text_color="#e0e0e0").pack(side="left")
        self.vars["daily_limit_minutes"] = ctk.StringVar()
        self.limit_entry = ctk.CTkEntry(
            limit_frame, width=60, textvariable=self.vars["daily_limit_minutes"], justify="center"
        )
        self.limit_entry.pack(side="left", padx=5)
        ctk.CTkLabel(limit_frame, text="минут", text_color="#e0e0e0").pack(side="left")

        # ---- Не отслеживаются ----
        self._add_section(main_frame, "Не отслеживаются")
        desc_label = ctk.CTkLabel(
            main_frame,
            text="Процессы, для которых ранее был выбран отказ от отслеживания:",
            font=("Segoe UI", 11), text_color="#888888"
        )
        desc_label.pack(anchor="w", padx=20, pady=(0, 5))

        self.ignored_frame = ctk.CTkFrame(main_frame, fg_color="#1a1a2e", corner_radius=8)
        self.ignored_frame.pack(anchor="w", padx=20, pady=(0, 10), fill="x")
        self._refresh_ignored_list()

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

        self.vars["backup_on_startup"] = ctk.BooleanVar()
        backup_switch = ctk.CTkSwitch(
            main_frame, text="Автоматическая резервная копия при запуске",
            variable=self.vars["backup_on_startup"], text_color="#e0e0e0"
        )
        backup_switch.pack(anchor="w", padx=20, pady=(5, 0))
        backup_hint = ctk.CTkLabel(
            main_frame,
            text="Копии хранятся в data/backups (по умолчанию — последние 7)",
            font=("Segoe UI", 10), text_color="#888888"
        )
        backup_hint.pack(anchor="w", padx=35, pady=(0, 5))

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
        self.vars["pause_when_idle"].set(self.settings.pause_when_idle)
        self.vars["idle_threshold_minutes"].set(str(self.settings.idle_threshold_minutes))
        self.vars["daily_limit_enabled"].set(self.settings.daily_limit_enabled)
        self.vars["daily_limit_minutes"].set(str(self.settings.daily_limit_minutes))
        self.vars["backup_on_startup"].set(self.settings.backup_on_startup)
        self._toggle_long_session_entry()
        self._toggle_idle_entry()
        self._toggle_limit_entry()

    def _toggle_long_session_entry(self):
        if self.vars["notify_long_session"].get():
            self.minutes_entry.configure(state="normal")
        else:
            self.minutes_entry.configure(state="disabled")

    def _toggle_idle_entry(self):
        self.idle_entry.configure(
            state="normal" if self.vars["pause_when_idle"].get() else "disabled"
        )

    def _toggle_limit_entry(self):
        self.limit_entry.configure(
            state="normal" if self.vars["daily_limit_enabled"].get() else "disabled"
        )

    def _var_bool(self, key: str, default: bool = False) -> bool:
        """Безопасно читает булеву переменную (устойчиво к неполному набору vars)."""
        var = self.vars.get(key)
        if var is None:
            return default
        try:
            return bool(var.get())
        except Exception:
            return default

    def _read_int(self, key: str, setter, fallback: int) -> None:
        """Аккуратно сохраняет целочисленную настройку из поля ввода."""
        var = self.vars.get(key)
        if var is None:
            return
        try:
            value = int(str(var.get()).strip())
        except (TypeError, ValueError):
            return
        setter(value)

    def _refresh_ignored_list(self):
        """Обновляет список процессов в секции 'Не отслеживаются'."""
        for widget in self.ignored_frame.winfo_children():
            widget.destroy()

        ignored = self.db.get_ignored_processes() if (self.db and hasattr(self.db, 'get_ignored_processes')) else []
        if not ignored:
            empty_lbl = ctk.CTkLabel(
                self.ignored_frame,
                text="Список пуст. Процессы, для которых выбран отказ, появятся здесь.",
                font=("Segoe UI", 11),
                text_color="#666666"
            )
            empty_lbl.pack(pady=10)
            return

        for row in ignored:
            exe_name = row['exe_name']
            item_frame = ctk.CTkFrame(self.ignored_frame, fg_color="transparent")
            item_frame.pack(fill="x", padx=10, pady=4)

            name_lbl = ctk.CTkLabel(
                item_frame,
                text=f"•  {exe_name}",
                font=("Consolas", 12),
                text_color="#e0e0e0"
            )
            name_lbl.pack(side="left", padx=5)

            def make_unignore_cmd(exe):
                return lambda: self._unignore_process(exe)

            allow_btn = ctk.CTkButton(
                item_frame,
                text="Разрешить отслеживание",
                command=make_unignore_cmd(exe_name),
                fg_color="#2a6d8a",
                hover_color="#1d4d66",
                text_color="#ffffff",
                height=26,
                font=("Segoe UI", 11),
                width=170
            )
            allow_btn.pack(side="right", padx=5)

    def _unignore_process(self, exe_name: str):
        """Удаляет процесс из игнорируемых и обновляет список."""
        if hasattr(self.master, 'tracker') and self.master.tracker and hasattr(self.master.tracker, 'unignore_exe'):
            self.master.tracker.unignore_exe(exe_name)
        elif self.db and hasattr(self.db, 'remove_ignored_process'):
            self.db.remove_ignored_process(exe_name)
        self._refresh_ignored_list()

    def _on_autostart_toggle(self):
        """Раньше применял настройку мгновенно, теперь сохранение происходит только в save_and_close()."""
        pass

    def save_and_close(self):
        autostart_val = self.vars["autostart"].get()
        if autostart_val != self.settings.autostart:
            self.settings.autostart = autostart_val
        self.settings.minimize_to_tray_on_start = self.vars["minimize_to_tray_on_start"].get()
        self.settings.track_only_active_window = self.vars["track_only_active_window"].get()
        self.settings.notify_new_game = self.vars["notify_new_game"].get()
        self.settings.notify_long_session = self.vars["notify_long_session"].get()
        try:
            minutes = int(self.vars["long_session_minutes"].get())
            self.settings.long_session_minutes = minutes
        except ValueError:
            pass
        self.settings.pause_when_idle = self._var_bool("pause_when_idle", self.settings.pause_when_idle)
        self._read_int("idle_threshold_minutes", lambda v: setattr(self.settings, 'idle_threshold_minutes', v), 5)
        self.settings.daily_limit_enabled = self._var_bool("daily_limit_enabled", self.settings.daily_limit_enabled)
        self._read_int("daily_limit_minutes", lambda v: setattr(self.settings, 'daily_limit_minutes', v), 180)
        self.settings.backup_on_startup = self._var_bool("backup_on_startup", self.settings.backup_on_startup)
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
        backup_dir = os.path.join(get_base_dir(), "data", "backups")
        os.makedirs(backup_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"gametracker_backup_{timestamp}.db"
        backup_path = os.path.join(backup_dir, backup_name)
        try:
            self.db.backup_database(backup_path)
            messagebox.showinfo("Резервная копия", f"База данных сохранена:\n{backup_path}")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось создать резервную копию:\n{e}")

    def open_data_folder(self):
        data_dir = os.path.join(get_base_dir(), "data")
        if not os.path.exists(data_dir):
            messagebox.showwarning("Папка не найдена", "Папка data ещё не создана.")
            return
        if hasattr(os, "startfile"):
            os.startfile(data_dir)
        else:  # не-Windows: просто показываем путь
            messagebox.showinfo("Папка с данными", data_dir)

    def exit_app(self):
        if messagebox.askyesno("Выход", "Вы уверены, что хотите закрыть приложение?"):
            self.destroy()
            if hasattr(self.master, 'quit_app'):
                self.master.quit_app()
            else:
                import sys
                sys.exit(0)
