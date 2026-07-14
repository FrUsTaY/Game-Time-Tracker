"""
widgets.py — переиспользуемые виджеты для GameTimeTracker.
"""

import customtkinter as ctk
from PIL import Image, ImageTk
from typing import Callable, Optional
import os


class NeonButton(ctk.CTkButton):
    def __init__(self, master, text: str = "", command: Optional[Callable] = None,
                 accent_color: str = "#00d4ff", hover_color: str = "#7b2fff", **kwargs):
        super().__init__(
            master, text=text, command=command,
            fg_color="transparent", border_color=accent_color, border_width=2,
            text_color=accent_color, hover_color=hover_color, corner_radius=8, **kwargs
        )
        self.configure(font=("Segoe UI", 12, "bold"))


class SectionTitle(ctk.CTkLabel):
    def __init__(self, master, text: str, **kwargs):
        super().__init__(master, text=text, font=("Consolas", 18, "bold"), text_color="#00d4ff", **kwargs)


class GameCard(ctk.CTkFrame):
    def __init__(self, master, game_id: int, display_name: str, total_seconds: int,
                 last_launched: Optional[str], is_active: bool, icon_path: Optional[str],
                 on_rename: Callable[[int, str], None],
                 on_archive: Callable[[int], None],
                 on_delete: Callable[[int], None], **kwargs):
        super().__init__(master, fg_color="#1a1a2e", corner_radius=12, border_width=1, border_color="#00d4ff", **kwargs)
        self.game_id = game_id
        self.display_name = display_name
        self.total_seconds = total_seconds
        self.last_launched = last_launched
        self.is_active = is_active
        self.on_rename = on_rename
        self.on_archive = on_archive
        self.on_delete = on_delete

        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(2, weight=0)

        # Иконка
        self.icon_label = ctk.CTkLabel(self, text="🎮", width=48, height=48, font=("Segoe UI", 32))
        if icon_path and os.path.exists(icon_path):
            try:
                img = Image.open(icon_path)
                img = img.resize((48, 48), Image.Resampling.LANCZOS)
                self.icon_img = ImageTk.PhotoImage(img)
                self.icon_label.configure(image=self.icon_img, text="")
            except Exception:
                pass
        self.icon_label.grid(row=0, column=0, rowspan=2, padx=10, pady=10)

        # Название (двойной клик для редактирования)
        self.name_label = ctk.CTkLabel(self, text=display_name, font=("Segoe UI", 16, "bold"),
                                       text_color="#e0e0e0", anchor="w")
        self.name_label.grid(row=0, column=1, sticky="w", padx=10, pady=(10, 0))
        #self.name_label.bind("<Double-1>", self._start_rename)

        # Время и статус
        time_text = self._format_time(total_seconds)
        status_text = "🟢 Сейчас играю" if is_active else "⚪ Не играю"
        status_color = "#00ff88" if is_active else "#888888"
        self.info_label = ctk.CTkLabel(self, text=f"{time_text}  |  {status_text}",
                                       font=("Consolas", 12), text_color=status_color, anchor="w")
        self.info_label.grid(row=1, column=1, sticky="w", padx=10, pady=(0, 10))

        # Дата последнего запуска
        last_launched_text = last_launched[:10] if last_launched else "никогда"
        self.date_label = ctk.CTkLabel(self, text=f"Последний запуск: {last_launched_text}",
                                       font=("Segoe UI", 10), text_color="#666666")
        self.date_label.grid(row=2, column=1, sticky="w", padx=10, pady=(0, 10))

        # Кнопки
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=0, column=2, rowspan=3, padx=10, pady=10, sticky="e")

        self.edit_btn = NeonButton(btn_frame, text="✏️", command=self._start_rename,
                                   accent_color="#00d4ff", hover_color="#0099cc", width=40)
        self.edit_btn.pack(side="left", padx=2)

        self.archive_btn = NeonButton(btn_frame, text="📦 В архив", command=lambda: on_archive(game_id),
                                      accent_color="#ffaa00", hover_color="#ff6600", width=90)
        self.archive_btn.pack(side="left", padx=5)

        self.delete_btn = NeonButton(btn_frame, text="🗑 Удалить", command=lambda: on_delete(game_id),
                                     accent_color="#ff4444", hover_color="#cc0000", width=90)
        self.delete_btn.pack(side="left", padx=5)

    def _format_time(self, seconds: int) -> str:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    def _start_rename(self, event=None):
        entry = ctk.CTkEntry(self, font=("Segoe UI", 16, "bold"))
        entry.grid(row=0, column=1, sticky="w", padx=10, pady=(10, 0))
        entry.insert(0, self.display_name)
        self.name_label.grid_remove()
        entry.focus()

        saved = False

        def save_rename():
            nonlocal saved
            if saved:
                return
            saved = True
            new_name = entry.get().strip()
            if new_name and new_name != self.display_name:
                self.on_rename(self.game_id, new_name)
                self.name_label.configure(text=new_name)
                self.display_name = new_name
            self.name_label.grid()
            entry.destroy()

        entry.bind("<Return>", lambda e: save_rename())
        entry.bind("<FocusOut>", lambda e: save_rename())

    def update_time(self, total_seconds: int, is_active: bool):
        self.total_seconds = total_seconds
        self.is_active = is_active
        time_text = self._format_time(total_seconds)
        status_text = "🟢 Сейчас играю" if is_active else "⚪ Не играю"
        status_color = "#00ff88" if is_active else "#888888"
        self.info_label.configure(text=f"{time_text}  |  {status_text}", text_color=status_color)
        self.update_idletasks()


class ArchiveCard(ctk.CTkFrame):
    def __init__(self, master, game_id: int, display_name: str, total_seconds: int,
                 added_at: str, archived_at: str, icon_path: Optional[str],
                 on_restore: Callable[[int], None], **kwargs):
        super().__init__(master, fg_color="#1a1a2e", corner_radius=12, border_width=1, border_color="#7b2fff", **kwargs)
        self.game_id = game_id
        self.on_restore = on_restore

        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(2, weight=0)

        self.icon_label = ctk.CTkLabel(self, text="🎮", width=48, height=48, font=("Segoe UI", 32))
        if icon_path and os.path.exists(icon_path):
            try:
                img = Image.open(icon_path)
                img = img.resize((48, 48), Image.Resampling.LANCZOS)
                self.icon_img = ImageTk.PhotoImage(img)
                self.icon_label.configure(image=self.icon_img, text="")
            except Exception:
                pass
        self.icon_label.grid(row=0, column=0, rowspan=2, padx=10, pady=10)

        hours = total_seconds / 3600
        time_text = f"{hours:.1f} ч"
        self.name_label = ctk.CTkLabel(self, text=f"{display_name}  |  {time_text}",
                                       font=("Segoe UI", 16, "bold"), text_color="#e0e0e0", anchor="w")
        self.name_label.grid(row=0, column=1, sticky="w", padx=10, pady=(10, 0))

        added_short = added_at[:10] if added_at else "—"
        archived_short = archived_at[:10] if archived_at else "—"
        self.date_label = ctk.CTkLabel(self, text=f"Добавлена: {added_short}  |  Архивирована: {archived_short}",
                                       font=("Segoe UI", 11), text_color="#888888")
        self.date_label.grid(row=1, column=1, sticky="w", padx=10, pady=(0, 10))

        self.restore_btn = NeonButton(self, text="↺ Вернуть", command=lambda: on_restore(game_id),
                                      accent_color="#00ff88", hover_color="#00cc66", width=100)
        self.restore_btn.grid(row=0, column=2, rowspan=2, padx=10, pady=10, sticky="e")