"""
tab_archive.py — вкладка «Архив» для GameTimeTracker.
"""

import os
import customtkinter as ctk
from ui.widgets import ArchiveCard, SectionTitle
from database import Database
from utils import get_base_dir


class TabArchive(ctk.CTkFrame):
    def __init__(self, master, db: Database, tracker=None, settings=None):
        super().__init__(master, fg_color="#0d0d0d")
        self.db = db
        self.tracker = tracker
        self.settings = settings
        self.master_window = master
        self.icons_dir = os.path.join(get_base_dir(), "data", "icons")

        self._build_ui()
        self.refresh()

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=0)

        top_panel = ctk.CTkFrame(self, fg_color="transparent")
        top_panel.grid(row=0, column=0, sticky="ew", padx=20, pady=10)
        top_panel.grid_columnconfigure(0, weight=0)
        top_panel.grid_columnconfigure(1, weight=1)

        self.title_label = SectionTitle(top_panel, "Архив")
        self.title_label.grid(row=0, column=0, sticky="w")

        self.counter_label = ctk.CTkLabel(
            top_panel, text="0 игр пройдено",
            font=("Segoe UI", 12), text_color="#888888"
        )
        self.counter_label.grid(row=0, column=1, sticky="e", padx=10)

        sort_frame = ctk.CTkFrame(self, fg_color="transparent")
        sort_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 10))

        ctk.CTkLabel(sort_frame, text="Сортировать по:", text_color="#e0e0e0").pack(side="left", padx=(0, 10))

        self.sort_var = ctk.StringVar(value="📅 По дате архивации")
        sort_menu = ctk.CTkOptionMenu(
            sort_frame,
            values=["📅 По дате архивации", "⏱ По времени прохождения"],
            variable=self.sort_var,
            command=self.refresh,
            fg_color="#1a1a2e", button_color="#7b2fff"
        )
        sort_menu.pack(side="left")

        self.scrollable_frame = ctk.CTkScrollableFrame(self, fg_color="#0d0d0d", height=500)
        self.scrollable_frame.grid(row=2, column=0, sticky="nsew", padx=20, pady=(0, 20))
        self.scrollable_frame.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

    def refresh(self, *args):
        games = self.db.get_all_games(archived=True)

        sort_type = self.sort_var.get()
        if sort_type == "📅 По дате архивации":
            games.sort(key=lambda g: g.get('archived_at') or '', reverse=True)
        elif sort_type == "⏱ По времени прохождения":
            games.sort(key=lambda g: g['total_seconds'], reverse=True)

        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        count = len(games)
        self.counter_label.configure(text=f"{count} игр пройдено")

        if not games:
            empty_label = ctk.CTkLabel(
                self.scrollable_frame,
                text="📭 Архив пуст\nИгры, которые вы завершите, появятся здесь",
                font=("Segoe UI", 16), text_color="#666666"
            )
            empty_label.pack(pady=50)
            return

        for game in games:
            icon_path = game.get('icon_path')
            if icon_path and not self._icon_exists(icon_path):
                icon_path = None
            card = ArchiveCard(
                self.scrollable_frame,
                game_id=game['id'],
                display_name=game['display_name'],
                total_seconds=game['total_seconds'],
                added_at=game.get('added_at', ''),
                archived_at=game.get('archived_at', ''),
                icon_path=icon_path,
                on_restore=self.restore_game
            )
            card.pack(fill="x", padx=10, pady=5)

    def _icon_exists(self, path: str) -> bool:
        import os
        return os.path.exists(path)

    def _get_main_window(self):
        main_win = getattr(self, 'main_window', None)
        if main_win:
            return main_win
        try:
            top = self.winfo_toplevel()
            if hasattr(top, 'refresh_tab') or hasattr(top, 'tabs_cache'):
                return top
        except Exception:
            pass
        return None

    def restore_game(self, game_id: int):
        self.db.unarchive_game(game_id)
        self.refresh()
        # Обновляем вкладку "Мои игры", если она существует
        main_win = self._get_main_window()
        if main_win and hasattr(main_win, 'refresh_tab'):
            main_win.refresh_tab('games')
        elif main_win and hasattr(main_win, 'tabs_cache') and 'games' in main_win.tabs_cache:
            games_tab = main_win.tabs_cache['games']
            if hasattr(games_tab, 'refresh_games'):
                games_tab.refresh_games()
            elif hasattr(games_tab, 'refresh'):
                games_tab.refresh()