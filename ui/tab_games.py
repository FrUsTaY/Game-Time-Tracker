"""
tab_games.py — вкладка «Мои игры» для GameTimeTracker.
"""

import customtkinter as ctk
from tkinter import filedialog, messagebox
import os
from typing import Dict, Optional, List
import psutil
import win32gui
import win32process

from ui.widgets import GameCard, NeonButton, SectionTitle
from database import Database
from tracker import GameTracker
from settings import AppSettings


class AddFromProcessesDialog(ctk.CTkToplevel):
    """Модальное окно для выбора процесса из запущенных с поиском."""

    def __init__(self, parent, tracker: GameTracker, on_add):
        super().__init__(parent)
        self.tracker = tracker
        self.on_add = on_add
        self.selected_processes = []
        self.all_processes = []   # список всех процессов
        self.filtered_processes = []
        self.check_vars = {}

        self.title("Добавить игру из запущенных")
        self.geometry("750x550")
        self.grab_set()

        # Поле поиска
        search_frame = ctk.CTkFrame(self, fg_color="transparent")
        search_frame.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(search_frame, text="Поиск:", text_color="#e0e0e0").pack(side="left", padx=5)
        self.search_entry = ctk.CTkEntry(search_frame, placeholder_text="фильтр по имени или заголовку")
        self.search_entry.pack(side="left", fill="x", expand=True, padx=5)
        self.search_entry.bind("<KeyRelease>", self.filter_processes)

        # Список процессов с прокруткой
        self.frame = ctk.CTkScrollableFrame(self, height=400)
        self.frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Кнопки
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=10)

        add_btn = ctk.CTkButton(
            btn_frame, text="✅ Добавить выбранные",
            command=self.add_selected, fg_color="#2a6d8a", hover_color="#1d4d66",
            text_color="#ffffff", width=150
        )
        add_btn.pack(side="left", padx=5)

        cancel_btn = ctk.CTkButton(
            btn_frame, text="❌ Отмена",
            command=self.destroy, fg_color="#8a2a2a", hover_color="#5a1d1d",
            text_color="#ffffff", width=100
        )
        cancel_btn.pack(side="left", padx=5)

        self.load_processes()

    def load_processes(self):
        processes = self.tracker.get_running_processes()
        import win32gui
        import win32process
        # Собираем заголовки окон для каждого PID
        self.all_processes = []
        for proc in processes:
            try:
                pid = proc['pid']
                # Получаем список окон этого процесса
                def enum_cb(hwnd, hwnds):
                    if win32gui.IsWindowVisible(hwnd):
                        _, found_pid = win32process.GetWindowThreadProcessId(hwnd)
                        if found_pid == pid:
                            title = win32gui.GetWindowText(hwnd)
                            if title:
                                hwnds.append(title)
                    return True
                hwnds = []
                win32gui.EnumWindows(enum_cb, hwnds)
                window_title = hwnds[0] if hwnds else ""
                proc['window_title'] = window_title
                self.all_processes.append(proc)
            except Exception:
                continue
        self.all_processes.sort(key=lambda x: x['name'])
        self.filtered_processes = self.all_processes.copy()
        self._refresh_list()

    def filter_processes(self, event=None):
        text = self.search_entry.get().strip().lower()
        if not text:
            self.filtered_processes = self.all_processes.copy()
        else:
            self.filtered_processes = [p for p in self.all_processes 
                                       if text in p['name'].lower() or text in p.get('window_title', '').lower()]
        self._refresh_list()

    def _refresh_list(self):
        # Удаляем старые чекбоксы
        for widget in self.frame.winfo_children():
            widget.destroy()
        self.check_vars = {}
        for idx, proc in enumerate(self.filtered_processes):
            var = ctk.BooleanVar()
            title_suffix = f" — {proc['window_title'][:50]}" if proc.get('window_title') else " (без окна)"
            cb = ctk.CTkCheckBox(
                self.frame, 
                text=f"{proc['name']} (PID: {proc['pid']}){title_suffix}",
                variable=var,
                text_color="#e0e0e0",
                fg_color="#2a6d8a",
                hover_color="#1d4d66"
            )
            cb.pack(anchor="w", padx=10, pady=2)
            self.check_vars[idx] = var
        # Сохраняем привязку индекса к процессу
        self.filtered_procs = self.filtered_processes

    def add_selected(self):
        self.selected_processes = []
        for idx, var in self.check_vars.items():
            if var.get():
                self.selected_processes.append(self.filtered_procs[idx])
        if self.selected_processes:
            self.on_add(self.selected_processes)
        self.destroy()


class TabGames(ctk.CTkFrame):
    """Вкладка «Мои игры»."""

    def __init__(self, master, db: Database, tracker: GameTracker, settings: AppSettings):
        super().__init__(master, fg_color="#0d0d0d")
        self.db = db
        self.tracker = tracker
        self.settings = settings
        self.master_window = master

        self.cards: Dict[int, GameCard] = {}
        self.current_games = []

        self.icons_dir = "data/icons"
        os.makedirs(self.icons_dir, exist_ok=True)

        self._build_ui()
        self.refresh_games()

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        top_panel = ctk.CTkFrame(self, fg_color="transparent")
        top_panel.grid(row=0, column=0, sticky="ew", padx=20, pady=10)
        top_panel.grid_columnconfigure(0, weight=0)
        top_panel.grid_columnconfigure(1, weight=0)
        top_panel.grid_columnconfigure(2, weight=0)
        top_panel.grid_columnconfigure(3, weight=1)
        top_panel.grid_columnconfigure(4, weight=0)

        SectionTitle(top_panel, "Мои игры").grid(row=0, column=0, padx=(0, 20))

        add_btn = ctk.CTkButton(
            top_panel, text="➕ Добавить игру",
            command=self.add_game_from_file,
            fg_color="transparent",
            border_color="#00d4ff",
            border_width=2,
            text_color="#ffffff",
            hover_color="#0055aa",
            anchor="center",
            font=("Segoe UI", 12, "bold"),
            corner_radius=8,
            width=120
        )
        add_btn.grid(row=0, column=1, padx=5)

        from_running_btn = ctk.CTkButton(
            top_panel, text="📋 Из запущенных",
            command=self.add_game_from_running,
            fg_color="transparent",
            border_color="#7b2fff",
            border_width=2,
            text_color="#ffffff",
            hover_color="#3d1a66",
            anchor="center",
            font=("Segoe UI", 12, "bold"),
            corner_radius=8,
            width=120
        )
        from_running_btn.grid(row=0, column=2, padx=5)

        manual_btn = ctk.CTkButton(
            top_panel, text="✏️ Ввести вручную",
            command=self.add_game_manual,
            fg_color="transparent",
            border_color="#ffaa00",
            border_width=2,
            text_color="#ffffff",
            hover_color="#aa6600",
            anchor="center",
            font=("Segoe UI", 12, "bold"),
            corner_radius=8,
            width=120
        )
        manual_btn.grid(row=0, column=3, padx=5, sticky="w")

        # Поиск
        search_frame = ctk.CTkFrame(top_panel, fg_color="transparent")
        search_frame.grid(row=0, column=4, padx=10, sticky="e")

        search_label = ctk.CTkLabel(search_frame, text="🔍", font=("Segoe UI", 14), text_color="#00d4ff")
        search_label.pack(side="left", padx=(0, 5))

        self.search_var = ctk.StringVar()
        self.search_var.trace("w", lambda *args: self.filter_games())
        search_entry = ctk.CTkEntry(
            search_frame, placeholder_text="Поиск игры...",
            textvariable=self.search_var, width=180
        )
        search_entry.pack(side="left", padx=(0, 5))

        clear_btn = ctk.CTkButton(
            search_frame, text="✖", width=30, height=30,
            command=self.clear_search, fg_color="transparent",
            text_color="#888888", hover_color="#444444"
        )
        clear_btn.pack(side="left")

        sort_frame = ctk.CTkFrame(self, fg_color="transparent")
        sort_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 10))
        sort_frame.grid_columnconfigure(0, weight=0)
        sort_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(sort_frame, text="Сортировать по:", text_color="#e0e0e0").pack(side="left", padx=(0, 10))

        self.sort_option = ctk.StringVar(value="⏱ По времени")
        sort_menu = ctk.CTkOptionMenu(
            sort_frame,
            values=["⏱ По времени", "📅 По дате добавления", "🕒 По дате запуска", "🎮 По статусу"],
            variable=self.sort_option,
            command=self.refresh_games,
            fg_color="#1a1a2e", button_color="#7b2fff"
        )
        sort_menu.pack(side="left")

        self.scrollable_frame = ctk.CTkScrollableFrame(self, fg_color="#0d0d0d", height=500)
        self.scrollable_frame.grid(row=2, column=0, sticky="nsew", padx=20, pady=(0, 20))
        self.scrollable_frame.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

    def refresh_games(self, *args):
        games = self.db.get_all_games(archived=False)
        sort_key = self.sort_option.get()
        if sort_key == "⏱ По времени":
            games.sort(key=lambda x: x['total_seconds'], reverse=True)
        elif sort_key == "📅 По дате добавления":
            games.sort(key=lambda x: x['added_at'], reverse=True)
        elif sort_key == "🕒 По дате запуска":
            games.sort(key=lambda x: x['last_launched'] or '', reverse=True)
        elif sort_key == "🎮 По статусу":
            active_ids = list(self.tracker.active_sessions.keys()) if self.tracker else []
            games.sort(key=lambda g: (g['id'] not in active_ids, g['display_name']))

        self.current_games = [g['id'] for g in games]

        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        if not games:
            empty_label = ctk.CTkLabel(
                self.scrollable_frame,
                text="✨ Добавьте свою первую игру ✨\nНажмите «Добавить игру» или «Из запущенных»",
                font=("Segoe UI", 16),
                text_color="#666666"
            )
            empty_label.pack(pady=50)
            self.cards.clear()
            return

        self.cards = {}
        for game in games:
            is_active = game['id'] in (self.tracker.active_sessions.keys() if self.tracker else {})
            icon_path = game.get('icon_path')
            if icon_path and not os.path.exists(icon_path):
                icon_path = None

            card = GameCard(
                self.scrollable_frame,
                game_id=game['id'],
                display_name=game['display_name'],
                total_seconds=game['total_seconds'],
                last_launched=game.get('last_launched'),
                is_active=is_active,
                icon_path=icon_path,
                on_rename=self.rename_game,
                on_archive=self.archive_game,
                on_delete=self.delete_game
            )
            card.pack(fill="x", padx=10, pady=5)
            self.cards[game['id']] = card

    def update_tick(self, game_id: int, total_seconds: int, is_active: bool = None):
        # Проверяем, существует ли карточка и не уничтожена ли она
        if game_id not in self.cards:
            print(f"DEBUG: game_id {game_id} не найден в cards, пропускаем обновление")
            return
        card = self.cards[game_id]
        # Проверяем, что виджет info_label существует (не уничтожен)
        try:
            if card.info_label.winfo_exists():
                if is_active is None:
                    is_active = game_id in (self.tracker.active_sessions.keys() if self.tracker else {})
                card.update_time(total_seconds, is_active)
                # Обновляем дату последнего запуска при первой секунде после старта
                if total_seconds == 1:
                    game = self.db.get_game_by_id(game_id)
                    if game and game.get('last_launched'):
                        last = game['last_launched'][:10]
                        card.date_label.configure(text=f"Последний запуск: {last}")
                self.scrollable_frame.update_idletasks()
                self.update_idletasks()
                if self.winfo_toplevel():
                    self.winfo_toplevel().update_idletasks()
            else:
                # Карточка уничтожена, но не удаляем из словаря – при следующем refresh_games() она пересоздастся
                print(f"DEBUG: карточка game_id {game_id} уничтожена, но оставлена в cards для пересоздания")
        except Exception as e:
            print(f"DEBUG: ошибка обновления карточки {game_id}: {e}")

    def filter_games(self):
        search_text = self.search_var.get().strip().lower()
        if not search_text:
            for card in self.cards.values():
                card.pack(fill="x", padx=10, pady=5)
        else:
            for game_id, card in self.cards.items():
                if search_text in card.display_name.lower():
                    card.pack(fill="x", padx=10, pady=5)
                else:
                    card.pack_forget()

    def clear_search(self):
        """Очищает поле поиска."""
        self.search_var.set("")

    def add_game_from_file(self):
        filepath = filedialog.askopenfilename(
            title="Выберите исполняемый файл игры",
            filetypes=[("Исполняемые файлы", "*.exe"), ("Все файлы", "*.*")]
        )
        if not filepath:
            return
        self._add_game(filepath)

    def add_game_from_running(self):
        dialog = AddFromProcessesDialog(self, self.tracker, self._add_games_from_processes)
        dialog.wait_window()

    def _add_games_from_processes(self, processes: List[dict]):
        for proc in processes:
            exe_path = proc.get('exe')
            if not exe_path:
                exe_name = proc['name']
                display_name = exe_name.replace('.exe', '').title()
                self._add_game_by_name(exe_name, display_name, None)
            else:
                self._add_game(exe_path)

    def add_game_manual(self):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Ввести игру вручную")
        dialog.geometry("400x200")
        dialog.grab_set()

        ctk.CTkLabel(dialog, text="Имя исполняемого файла (например, witcher3.exe):").pack(pady=10)
        entry = ctk.CTkEntry(dialog, width=300)
        entry.pack(pady=5)
        entry.focus()
        ctk.CTkLabel(dialog, text="Отображаемое название (оставьте пустым для автоматического):").pack(pady=5)
        name_entry = ctk.CTkEntry(dialog, width=300)
        name_entry.pack(pady=5)

        def confirm():
            exe_name = entry.get().strip()
            if not exe_name:
                messagebox.showerror("Ошибка", "Введите имя исполняемого файла")
                return
            display_name = name_entry.get().strip()
            if not display_name:
                display_name = exe_name.replace('.exe', '').title()
            self._add_game_by_name(exe_name, display_name, None)
            dialog.destroy()

        ctk.CTkButton(dialog, text="Добавить", command=confirm, fg_color="#00d4ff").pack(pady=10)

    def _add_game(self, exe_path: str):
        exe_name = os.path.basename(exe_path)
        display_name = os.path.splitext(exe_name)[0].title()
        existing = self.db.get_game_by_exe_name(exe_name)
        if existing:
            messagebox.showinfo("Информация", f"Игра {existing['display_name']} уже есть в списке.")
            return
        game_id = self.db.add_game(exe_name, display_name, exe_path)
        icon = self.tracker.get_exe_icon(exe_path)
        if icon:
            icon_path = os.path.join(self.icons_dir, f"{game_id}.png")
            icon.save(icon_path, "PNG")
            self.db.update_icon_path(game_id, icon_path)
        messagebox.showinfo("Успех", f"Игра {display_name} добавлена!")
        self.refresh_games()
        self._refresh_archive_tab()

    def _add_game_by_name(self, exe_name: str, display_name: str, exe_path: Optional[str]):
        existing = self.db.get_game_by_exe_name(exe_name)
        if existing:
            messagebox.showinfo("Информация", f"Игра {existing['display_name']} уже есть в списке.")
            return
        self.db.add_game(exe_name, display_name, exe_path)
        messagebox.showinfo("Успех", f"Игра {display_name} добавлена!")
        self.refresh_games()
        self._refresh_archive_tab()

    def _refresh_archive_tab(self):
        # Обновляем вкладку архива, если она уже существует в кеше
        if hasattr(self.master_window, 'tabs_cache') and 'archive' in self.master_window.tabs_cache:
            self.master_window.tabs_cache['archive'].refresh()
            print("DEBUG: Архив обновлён через tabs_cache")
        else:
            # Если вкладка ещё не создана, ничего не делаем (она обновится при первом открытии)
            print("DEBUG: Архив ещё не создан, пропускаем обновление")

    def rename_game(self, game_id: int, new_name: str):
        self.db.rename_game(game_id, new_name)
        if game_id in self.cards:
            self.cards[game_id].display_name = new_name
            self.cards[game_id].name_label.configure(text=new_name)
        else:
            self.refresh_games()

    def archive_game(self, game_id: int):
        if messagebox.askyesno("Архивация", "Переместить игру в архив?"):
            self.db.archive_game(game_id)
            self.refresh_games()
            self._refresh_archive_tab()

    def delete_game(self, game_id: int):
        if messagebox.askyesno("Удаление", "Вы уверены? Все данные об игре будут удалены безвозвратно."):
            game = self.db.get_game_by_id(game_id)
            if game and game.get('icon_path') and os.path.exists(game['icon_path']):
                os.remove(game['icon_path'])
            self.db.delete_game(game_id)
            self.refresh_games()
            self._refresh_archive_tab()