"""
tab_games.py — вкладка «Мои игры» для GameTimeTracker.
"""

import customtkinter as ctk
from tkinter import filedialog, messagebox
import os
from datetime import datetime
from typing import Dict, Optional, List
import win32gui
import win32process

from ui.widgets import GameCard, SectionTitle
from database import Database
from tracker import GameTracker
from settings import AppSettings
from utils import get_base_dir


class AddNewGameDialog(ctk.CTkToplevel):
    """Модальное окно при обнаружении новой игры."""
    def __init__(self, parent, exe_name: str, exe_path: Optional[str], tracker, on_confirm, on_ignore=None):
        super().__init__(parent)
        self.exe_name = exe_name
        self.exe_path = exe_path
        self.tracker = tracker
        self.on_confirm = on_confirm
        self.on_ignore = on_ignore

        self.title("🎮 Обнаружена новая игра!")
        self.geometry("500x320")
        self.resizable(False, False)
        self.grab_set()

        # Центрирование окна
        self.withdraw()
        self.update_idletasks()
        try:
            x = parent.winfo_x() + (parent.winfo_width() // 2) - (self.winfo_width() // 2)
            y = parent.winfo_y() + (parent.winfo_height() // 2) - (self.winfo_height() // 2)
            self.geometry(f"+{x}+{y}")
        except Exception:
            pass
        self.deiconify()
        self.focus_force()

        self._build_ui()

    def _build_ui(self):
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=20, pady=20)

        title_lbl = ctk.CTkLabel(
            container, text="🎮 Обнаружен запуск новой игры!",
            font=("Segoe UI", 16, "bold"), text_color="#00d4ff"
        )
        title_lbl.pack(pady=(0, 5))

        sub_lbl = ctk.CTkLabel(
            container, text="Добавить её в библиотеку для отслеживания времени?",
            font=("Segoe UI", 12), text_color="#888888"
        )
        sub_lbl.pack(pady=(0, 15))

        # Поле exe
        exe_frame = ctk.CTkFrame(container, fg_color="transparent")
        exe_frame.pack(fill="x", pady=5)
        ctk.CTkLabel(exe_frame, text="Файл:", width=80, anchor="w", text_color="#e0e0e0").pack(side="left")
        exe_entry = ctk.CTkEntry(exe_frame)
        exe_entry.insert(0, self.exe_name)
        exe_entry.configure(state="disabled")
        exe_entry.pack(side="left", fill="x", expand=True)

        # Поле красивого имени
        name_frame = ctk.CTkFrame(container, fg_color="transparent")
        name_frame.pack(fill="x", pady=5)
        ctk.CTkLabel(name_frame, text="Название:", width=80, anchor="w", text_color="#e0e0e0").pack(side="left")
        clean_name = os.path.splitext(self.exe_name)[0].replace('_', ' ').replace('-', ' ').title()
        self.name_entry = ctk.CTkEntry(name_frame)
        self.name_entry.insert(0, clean_name)
        self.name_entry.pack(side="left", fill="x", expand=True)
        self.name_entry.focus()
        self.name_entry.bind("<Return>", lambda e: self._confirm())

        # Кнопки
        btn_frame = ctk.CTkFrame(container, fg_color="transparent")
        btn_frame.pack(fill="x", pady=(20, 0))

        add_btn = ctk.CTkButton(
            btn_frame, text="✅ Добавить в трекер",
            command=self._confirm, fg_color="#00d4ff", hover_color="#0099cc",
            text_color="#0d0d0d", font=("Segoe UI", 12, "bold"), height=36
        )
        add_btn.pack(side="left", fill="x", expand=True, padx=(0, 10))

        ignore_btn = ctk.CTkButton(
            btn_frame, text="❌ Не отслеживать",
            command=self._ignore, fg_color="#333333", hover_color="#555555",
            text_color="#ffffff", height=36, width=140
        )
        ignore_btn.pack(side="right")

    def _confirm(self):
        display_name = self.name_entry.get().strip()
        if not display_name:
            display_name = os.path.splitext(self.exe_name)[0].title()
        self.on_confirm(self.exe_name, display_name, self.exe_path)
        self.destroy()

    def _ignore(self):
        if self.tracker and hasattr(self.tracker, 'ignore_exe'):
            self.tracker.ignore_exe(self.exe_name)
        if self.on_ignore:
            self.on_ignore(self.exe_name)
        self.destroy()


class AddFromProcessesDialog(ctk.CTkToplevel):
    """Модальное окно для выбора процесса из запущенных с поиском."""

    def __init__(self, parent, tracker: GameTracker, on_add):
        super().__init__(parent)
        self.tracker = tracker
        self.on_add = on_add
        self.selected_processes = []
        self.selected_pids = set()
        self.all_processes = []   # список всех процессов
        self.filtered_processes = []
        self.check_vars = {}

        self.title("Добавить игру из запущенных")
        self.geometry("750x550")
        self.grab_set()

        # Поле поиска и переключатель фоновых процессов
        search_frame = ctk.CTkFrame(self, fg_color="transparent")
        search_frame.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(search_frame, text="Поиск:", text_color="#e0e0e0").pack(side="left", padx=5)
        self.search_entry = ctk.CTkEntry(search_frame, placeholder_text="фильтр по имени или заголовку")
        self.search_entry.pack(side="left", fill="x", expand=True, padx=5)
        self._search_timer = None
        self.search_entry.bind("<KeyRelease>", self._on_search_key)

        self.show_background_var = ctk.BooleanVar(value=False)
        self.bg_checkbox = ctk.CTkCheckBox(
            search_frame, text="Показать фоновые процессы",
            variable=self.show_background_var, command=self.filter_processes,
            font=("Segoe UI", 11), text_color="#aaaaaa", width=190
        )
        self.bg_checkbox.pack(side="right", padx=5)

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

    def _on_search_key(self, event=None):
        if self._search_timer:
            self.after_cancel(self._search_timer)
        self._search_timer = self.after(100, self.filter_processes)

    def load_processes(self):
        from tracker import is_system_process

        processes = self.tracker.get_running_processes()
        # Собираем заголовки окон для всех PID за один быстрый проход EnumWindows
        pid_to_title = {}
        try:
            def enum_cb(hwnd, _):
                if win32gui.IsWindowVisible(hwnd):
                    _, found_pid = win32process.GetWindowThreadProcessId(hwnd)
                    title = win32gui.GetWindowText(hwnd).strip()
                    if title and found_pid not in pid_to_title:
                        pid_to_title[found_pid] = title
                return True
            win32gui.EnumWindows(enum_cb, None)
        except Exception:
            pass

        self.all_processes = []
        for proc in processes:
            try:
                pid = proc.get('pid')
                proc_name = proc.get('name', '')
                window_title = pid_to_title.get(pid, '')
                proc['window_title'] = window_title
                proc['is_system'] = is_system_process(proc_name, proc.get('exe'))
                self.all_processes.append(proc)
            except Exception:
                continue

        self.all_processes.sort(key=lambda x: (not bool(x.get('window_title')), x['name'].lower()))
        self.filter_processes()

    def filter_processes(self, event=None):
        self._search_timer = None
        text = self.search_entry.get().strip().lower()
        show_all = self.show_background_var.get()

        filtered = []
        for p in self.all_processes:
            has_window = bool(p.get('window_title'))
            is_sys = p.get('is_system', False)

            # По умолчанию скрываем системные процессы и процессы без видимого окна
            if not show_all and (is_sys or not has_window):
                if p['pid'] not in self.selected_pids:
                    continue

            if not text or text in p['name'].lower() or text in p.get('window_title', '').lower():
                filtered.append(p)

        self.filtered_processes = filtered
        self._refresh_list()

    def _refresh_list(self):
        # Удаляем старые чекбоксы
        for widget in self.frame.winfo_children():
            widget.destroy()
        self.check_vars = {}
        for idx, proc in enumerate(self.filtered_processes):
            pid = proc['pid']
            var = ctk.BooleanVar(value=(pid in self.selected_pids))

            def _make_cmd(p_pid, p_var):
                return lambda: self.selected_pids.add(p_pid) if p_var.get() else self.selected_pids.discard(p_pid)

            title_suffix = f" — {proc['window_title'][:50]}" if proc.get('window_title') else " (без окна)"
            cb = ctk.CTkCheckBox(
                self.frame, 
                text=f"{proc['name']} (PID: {proc['pid']}){title_suffix}",
                variable=var,
                command=_make_cmd(pid, var),
                text_color="#e0e0e0",
                fg_color="#2a6d8a",
                hover_color="#1d4d66"
            )
            cb.pack(anchor="w", padx=10, pady=2)
            self.check_vars[idx] = var
        # Сохраняем привязку индекса к процессу
        self.filtered_procs = self.filtered_processes

    def add_selected(self):
        self.selected_processes = [p for p in self.all_processes if p['pid'] in self.selected_pids]
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

        self.icons_dir = os.path.join(get_base_dir(), "data", "icons")
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

        def _get_game_sec(g):
            if self.tracker and hasattr(self.tracker, 'get_game_total_seconds'):
                return self.tracker.get_game_total_seconds(g['id'], g.get('total_seconds') or 0)
            return g.get('total_seconds') or 0

        if sort_key == "⏱ По времени":
            games.sort(key=_get_game_sec, reverse=True)
        elif sort_key == "📅 По дате добавления":
            games.sort(key=lambda x: x['added_at'], reverse=True)
        elif sort_key == "🕒 По дате запуска":
            games.sort(key=lambda x: x['last_launched'] or '', reverse=True)
        elif sort_key == "🎮 По статусу":
            def _is_active_for_sort(g):
                if self.tracker and hasattr(self.tracker, 'is_game_currently_playing'):
                    return not self.tracker.is_game_currently_playing(g['id'])
                return True
            games.sort(key=lambda g: (_is_active_for_sort(g), g['display_name']))

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
            gid = game['id']
            if self.tracker and hasattr(self.tracker, 'is_game_currently_playing'):
                is_active = self.tracker.is_game_currently_playing(gid)
            elif self.tracker and hasattr(self.tracker, 'active_sessions') and not getattr(self.settings, 'track_only_active_window', False):
                is_active = gid in self.tracker.active_sessions
            else:
                is_active = False

            total_sec = _get_game_sec(game)

            icon_path = game.get('icon_path')
            if icon_path and not os.path.exists(icon_path):
                icon_path = None

            card = GameCard(
                self.scrollable_frame,
                game_id=gid,
                display_name=game['display_name'],
                total_seconds=total_sec,
                last_launched=game.get('last_launched'),
                is_active=is_active,
                icon_path=icon_path,
                on_rename=self.rename_game,
                on_archive=self.archive_game,
                on_delete=self.delete_game
            )
            card.pack(fill="x", padx=10, pady=5)
            self.cards[gid] = card

        # Повторно применяем текущий поисковый фильтр к новым карточкам
        if hasattr(self, 'search_var') and self.search_var.get().strip():
            self.filter_games()

    def update_tick(self, game_id: int, total_seconds: int, is_active: bool = None):
        # Проверяем, существует ли карточка и не уничтожена ли она
        if game_id not in self.cards:
            return
        card = self.cards[game_id]
        # Проверяем, что виджет info_label существует (не уничтожен)
        try:
            if card.info_label.winfo_exists():
                if is_active is None:
                    if self.tracker and hasattr(self.tracker, 'is_game_currently_playing'):
                        is_active = self.tracker.is_game_currently_playing(game_id)
                    elif self.tracker and not getattr(self.settings, 'track_only_active_window', False):
                        is_active = game_id in self.tracker.active_sessions
                    else:
                        is_active = False
                card.update_time(total_seconds, is_active)
                # Обновляем дату последнего запуска при первой секунде после старта сессии
                if total_seconds == 1 or (is_active and not hasattr(card, '_session_launched_updated')):
                    last = datetime.now().strftime('%Y-%m-%d')
                    card.date_label.configure(text=f"Последний запуск: {last}")
                    if is_active:
                        card._session_launched_updated = True

                # Сбрасываем флаг при окончании сессии
                if not is_active and hasattr(card, '_session_launched_updated'):
                    delattr(card, '_session_launched_updated')
            else:
                pass
        except Exception:
            pass

    def filter_games(self):
        search_text = self.search_var.get().strip().lower()
        if not search_text:
            for gid in self.current_games:
                if gid in self.cards:
                    card = self.cards[gid]
                    card.pack_forget()
                    card.pack(fill="x", padx=10, pady=5)
        else:
            for gid in self.current_games:
                if gid in self.cards:
                    card = self.cards[gid]
                    card.pack_forget()
                    if search_text in card.display_name.lower():
                        card.pack(fill="x", padx=10, pady=5)

    def clear_search(self):
        """Очищает поле поиска."""
        self.search_var.set("")
        self.filter_games()

    def add_detected_game(self, exe_name: str, display_name: str, exe_path: Optional[str]):
        """Добавляет обнаруженную игру в библиотеку."""
        if exe_path and os.path.exists(exe_path):
            existing = self.db.get_game_by_exe_name(exe_name)
            if existing:
                return
            game_id = self.db.add_game(exe_name, display_name, exe_path)
            icon = self.tracker.get_exe_icon(exe_path) if self.tracker else None
            if icon:
                icon_path = os.path.join(self.icons_dir, f"{game_id}.png")
                icon.save(icon_path, "PNG")
                self.db.update_icon_path(game_id, icon_path)
        else:
            self._add_game_by_name(exe_name, display_name, exe_path, silent=True, refresh=False)
        self.refresh_games()
        self._refresh_archive_tab()

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
        added_count = 0
        for proc in processes:
            exe_path = proc.get('exe')
            if not exe_path:
                exe_name = proc['name']
                display_name = exe_name.replace('.exe', '').title()
                if self._add_game_by_name(exe_name, display_name, None, silent=True, refresh=False):
                    added_count += 1
            else:
                if self._add_game(exe_path, silent=True, refresh=False):
                    added_count += 1
        self.refresh_games()
        self._refresh_archive_tab()
        messagebox.showinfo("Пакетное добавление", f"Добавлено игр: {added_count}")

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
            if not exe_name.lower().endswith('.exe'):
                exe_name += '.exe'
            display_name = name_entry.get().strip()
            if not display_name:
                display_name = os.path.splitext(exe_name)[0].title()
            self._add_game_by_name(exe_name, display_name, None)
            dialog.destroy()

        ctk.CTkButton(dialog, text="Добавить", command=confirm, fg_color="#00d4ff").pack(pady=10)

    def _add_game(self, exe_path: str, silent: bool = False, refresh: bool = True) -> bool:
        exe_name = os.path.basename(exe_path)
        display_name = os.path.splitext(exe_name)[0].title()
        existing = self.db.get_game_by_exe_name(exe_name)
        if existing:
            if existing.get('is_archived'):
                if not silent:
                    restore = messagebox.askyesno(
                        "Игра в Архиве",
                        f"Игра «{existing['display_name']}» находится в Архиве.\n\nВосстановить её в активные игры?"
                    )
                    if restore:
                        self.db.unarchive_game(existing['id'])
                        if refresh:
                            self.refresh_games()
                            self._refresh_archive_tab()
                        messagebox.showinfo("Успех", f"Игра «{existing['display_name']}» восстановлена из архива!")
                        return True
                return False
            if not silent:
                messagebox.showinfo("Информация", f"Игра {existing['display_name']} уже есть в списке.")
            return False
        game_id = self.db.add_game(exe_name, display_name, exe_path)
        icon = self.tracker.get_exe_icon(exe_path) if (self.tracker and hasattr(self.tracker, 'get_exe_icon')) else None
        if icon:
            icon_path = os.path.join(self.icons_dir, f"{game_id}.png")
            icon.save(icon_path, "PNG")
            self.db.update_icon_path(game_id, icon_path)
        if not silent:
            messagebox.showinfo("Успех", f"Игра {display_name} добавлена!")
        if refresh:
            self.refresh_games()
            self._refresh_archive_tab()
        return True

    def _add_game_by_name(self, exe_name: str, display_name: str, exe_path: Optional[str], silent: bool = False, refresh: bool = True) -> bool:
        existing = self.db.get_game_by_exe_name(exe_name)
        if existing:
            if existing.get('is_archived'):
                if not silent:
                    restore = messagebox.askyesno(
                        "Игра в Архиве",
                        f"Игра «{existing['display_name']}» находится в Архиве.\n\nВосстановить её в активные игры?"
                    )
                    if restore:
                        self.db.unarchive_game(existing['id'])
                        if refresh:
                            self.refresh_games()
                            self._refresh_archive_tab()
                        messagebox.showinfo("Успех", f"Игра «{existing['display_name']}» восстановлена из архива!")
                        return True
                return False
            if not silent:
                messagebox.showinfo("Информация", f"Игра {existing['display_name']} уже есть в списке.")
            return False
        game_id = self.db.add_game(exe_name, display_name, exe_path)
        if exe_path and os.path.exists(exe_path) and hasattr(self.tracker, 'get_exe_icon'):
            icon = self.tracker.get_exe_icon(exe_path)
            if icon:
                icon_path = os.path.join(self.icons_dir, f"{game_id}.png")
                icon.save(icon_path, "PNG")
                self.db.update_icon_path(game_id, icon_path)
        if not silent:
            messagebox.showinfo("Успех", f"Игра {display_name} добавлена!")
        if refresh:
            self.refresh_games()
            self._refresh_archive_tab()
        return True

    def add_detected_game(self, exe_name: str, display_name: str, exe_path: Optional[str] = None):
        return self._add_game_by_name(exe_name, display_name, exe_path, silent=False, refresh=True)

    def refresh(self):
        self.refresh_games()

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

    def _refresh_archive_tab(self):
        # Обновляем вкладку архива, если она уже существует в кеше
        main_win = self._get_main_window()
        if main_win and hasattr(main_win, 'refresh_tab'):
            main_win.refresh_tab('archive')
        elif main_win and hasattr(main_win, 'tabs_cache') and 'archive' in main_win.tabs_cache:
            archive_tab = main_win.tabs_cache['archive']
            if hasattr(archive_tab, 'refresh'):
                archive_tab.refresh()

    def rename_game(self, game_id: int, new_name: str):
        self.db.rename_game(game_id, new_name)
        if game_id in self.cards:
            self.cards[game_id].display_name = new_name
            self.cards[game_id].name_label.configure(text=new_name)
        else:
            self.refresh_games()
        self.filter_games()

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