import customtkinter as ctk
from PIL import Image, ImageTk
import os
import sys
import traceback

from ui.tab_games import TabGames
from ui.tab_calendar import TabCalendar
from ui.tab_archive import TabArchive
from ui.tab_stats import TabStats
from ui.tab_about import TabAbout
from ui.settings_window import SettingsWindow
from utils import get_base_dir, resource_path


class NotificationsDialog(ctk.CTkToplevel):
    """Окно списка уведомлений о новых процессах."""
    def __init__(self, parent, db, tracker, on_add_game, on_remove_notification):
        super().__init__(parent)
        self.db = db
        self.tracker = tracker
        self.on_add_game = on_add_game
        self.on_remove_notification = on_remove_notification

        self.title("🔔 Уведомления")
        self.geometry("540x420")
        self.minsize(450, 300)
        self.resizable(True, True)
        self.transient(parent)

        self.withdraw()
        self.update_idletasks()
        try:
            x = parent.winfo_x() + (parent.winfo_width() // 2) - (self.winfo_width() // 2)
            y = parent.winfo_y() + (parent.winfo_height() // 2) - (self.winfo_height() // 2)
            self.geometry(f"+{x}+{y}")
        except Exception:
            pass
        self.deiconify()
        self.lift()
        self.focus_force()
        self.after(20, self.lift)
        self.after(50, self.focus_force)

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._build_ui()
        self.refresh()

    def _on_close(self):
        if hasattr(self.master, '_notifications_window'):
            self.master._notifications_window = None
        self.destroy()

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Заголовок
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=(15, 10))

        title_lbl = ctk.CTkLabel(
            header_frame,
            text="🔔 Обнаруженные процессы",
            font=("Segoe UI", 16, "bold"),
            text_color="#00d4ff"
        )
        title_lbl.pack(side="left")

        # Список
        self.scroll_frame = ctk.CTkScrollableFrame(self, fg_color="#1a1a2e", corner_radius=8)
        self.scroll_frame.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 15))
        self.scroll_frame.grid_columnconfigure(0, weight=1)

        # Нижняя панель
        bottom_frame = ctk.CTkFrame(self, fg_color="transparent")
        bottom_frame.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 15))

        self.clear_btn = ctk.CTkButton(
            bottom_frame,
            text="Очистить все",
            command=self.clear_all,
            fg_color="#333333",
            hover_color="#555555",
            text_color="#ffffff",
            width=120
        )
        self.clear_btn.pack(side="left")

        close_btn = ctk.CTkButton(
            bottom_frame,
            text="Закрыть",
            command=self._on_close,
            fg_color="#00d4ff",
            hover_color="#0099cc",
            text_color="#0d0d0d",
            font=("Segoe UI", 12, "bold"),
            width=100
        )
        close_btn.pack(side="right")

    def refresh(self):
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()

        notifications = self.db.get_pending_notifications() if (self.db and hasattr(self.db, 'get_pending_notifications')) else []
        if not notifications:
            self.clear_btn.configure(state="disabled")
            empty_lbl = ctk.CTkLabel(
                self.scroll_frame,
                text="Нет новых уведомлений\nЗдесь будут появляться процессы, обнаруженные трекером в фоновом режиме.",
                font=("Segoe UI", 13),
                text_color="#888888"
            )
            empty_lbl.pack(pady=40)
            return

        self.clear_btn.configure(state="normal")
        for item in notifications:
            exe_name = item['exe_name']
            exe_path = item.get('exe_path')
            clean_name = os.path.splitext(exe_name)[0].replace('_', ' ').replace('-', ' ').title()

            card = ctk.CTkFrame(self.scroll_frame, fg_color="#121224", corner_radius=8, border_width=1, border_color="#2a2a4e")
            card.pack(fill="x", padx=5, pady=6)
            card.grid_columnconfigure(0, weight=1)

            top_row = ctk.CTkFrame(card, fg_color="transparent")
            top_row.pack(fill="x", padx=12, pady=(10, 4))

            name_lbl = ctk.CTkLabel(
                top_row,
                text=f"🎮 {clean_name}",
                font=("Segoe UI", 13, "bold"),
                text_color="#00d4ff"
            )
            name_lbl.pack(side="left")

            exe_lbl = ctk.CTkLabel(
                card,
                text=f"Файл: {exe_name}",
                font=("Consolas", 11),
                text_color="#aaaaaa"
            )
            exe_lbl.pack(anchor="w", padx=12, pady=(0, 8))

            btn_row = ctk.CTkFrame(card, fg_color="transparent")
            btn_row.pack(fill="x", padx=12, pady=(0, 10))

            add_btn = ctk.CTkButton(
                btn_row,
                text="➕ Добавить в трекер",
                command=lambda e=exe_name, p=exe_path: self._add(e, p),
                fg_color="#00d4ff",
                hover_color="#0099cc",
                text_color="#0d0d0d",
                font=("Segoe UI", 11, "bold"),
                height=30,
                width=150
            )
            add_btn.pack(side="left", padx=(0, 8))

            ignore_btn = ctk.CTkButton(
                btn_row,
                text="❌ Не отслеживать",
                command=lambda e=exe_name: self._ignore(e),
                fg_color="#333333",
                hover_color="#555555",
                text_color="#ffffff",
                font=("Segoe UI", 11),
                height=30,
                width=130
            )
            ignore_btn.pack(side="left", padx=(0, 8))

            skip_btn = ctk.CTkButton(
                btn_row,
                text="Пропустить",
                command=lambda e=exe_name: self._skip(e),
                fg_color="transparent",
                hover_color="#2a2a4e",
                text_color="#888888",
                font=("Segoe UI", 11),
                height=30,
                width=90
            )
            skip_btn.pack(side="right")

    def _add(self, exe_name, exe_path):
        self._on_close()
        self.on_add_game(exe_name, exe_path)

    def _ignore(self, exe_name):
        if self.tracker and hasattr(self.tracker, 'ignore_exe'):
            self.tracker.ignore_exe(exe_name)
        self.on_remove_notification(exe_name)
        self.refresh()

    def _skip(self, exe_name):
        self.on_remove_notification(exe_name)
        self.refresh()

    def clear_all(self):
        if self.db and hasattr(self.db, 'clear_pending_notifications'):
            self.db.clear_pending_notifications()
        if hasattr(self.master, 'pending_notifications'):
            self.master.pending_notifications = []
            if hasattr(self.master, 'update_notifications_badge'):
                self.master.update_notifications_badge()
        self.refresh()


class MainWindow(ctk.CTk):
    def __init__(self, db, tracker, settings, on_exit=None):
        super().__init__()
        self.db = db
        self.tracker = tracker
        self.settings = settings
        self.on_exit = on_exit
        self.current_tab = None
        self.current_tab_key = None
        self.tabs_cache = {}   # Для хранения ссылок на созданные вкладки (если нужно обновлять время)
        self.pending_notifications = self.db.get_pending_notifications() if (self.db and hasattr(self.db, 'get_pending_notifications')) else []
        self._notifications_window = None

        self.title("GameTimeTracker")
        self.geometry("1100x700")
        self.minsize(900, 500)

        try:
            ico_path = resource_path("assets/app.ico")
            png_path = resource_path("assets/icon.png")
            if os.path.exists(ico_path):
                self.iconbitmap(ico_path)
            if os.path.exists(png_path):
                icon_img = Image.open(png_path)
                icon_photo = ImageTk.PhotoImage(icon_img)
                self.iconphoto(True, icon_photo)
        except Exception:
            pass

        self.protocol("WM_DELETE_WINDOW", self.hide_to_tray)

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Sidebar
        self.sidebar = ctk.CTkFrame(self, width=200, corner_radius=0, fg_color="#1a1a2e")
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)

        self.logo_label = ctk.CTkLabel(
            self.sidebar,
            text="🎮 GameTimeTracker",
            font=("Consolas", 16, "bold"),
            text_color="#00d4ff"
        )
        self.logo_label.pack(pady=(20, 30))

        self.nav_buttons = {}
        nav_items = [
            ("🎮 Мои игры", "games", TabGames),
            ("📅 Календарь", "calendar", TabCalendar),
            ("📦 Архив", "archive", TabArchive),
            ("📊 Статистика", "stats", TabStats),
            ("ℹ️ О программе", "about", TabAbout)
        ]

        for text, key, tab_class in nav_items:
            btn = ctk.CTkButton(
                self.sidebar,
                text=text,
                command=lambda k=key, tc=tab_class: self.show_tab(k, tc),
                fg_color="transparent",
                text_color="#e0e0e0",
                hover_color="#2a2a4e",
                anchor="w",
                font=("Segoe UI", 14)
            )
            btn.pack(fill="x", padx=10, pady=5)
            self.nav_buttons[text] = (btn, key)

        # Кнопка колокольчика / уведомлений
        self.notifications_btn = ctk.CTkButton(
            self.sidebar,
            text="🔔 Уведомления",
            command=self.show_notifications_window,
            fg_color="transparent",
            text_color="#e0e0e0",
            hover_color="#2a2a4e",
            anchor="w",
            font=("Segoe UI", 14)
        )
        self.notifications_btn.pack(fill="x", padx=10, pady=(15, 5))
        self.update_notifications_badge()

        # Кнопка настроек
        self.settings_btn = ctk.CTkButton(
            self.sidebar,
            text="⚙ Настройки",
            command=self.open_settings,
            fg_color="transparent",
            text_color="#e0e0e0",
            hover_color="#2a2a4e",
            anchor="w",
            font=("Segoe UI", 14)
        )
        self.settings_btn.pack(side="bottom", fill="x", padx=10, pady=(10, 5))

        # Кнопка выхода из приложения
        self.exit_btn = ctk.CTkButton(
            self.sidebar,
            text="🚪 Выход",
            command=self.confirm_exit,
            fg_color="transparent",
            text_color="#ff4444",
            hover_color="#440000",
            anchor="w",
            font=("Segoe UI", 14)
        )
        self.exit_btn.pack(side="bottom", fill="x", padx=10, pady=(0, 20))

        self.content_frame = ctk.CTkFrame(self, fg_color="#0d0d0d", corner_radius=0)
        self.content_frame.grid(row=0, column=1, sticky="nsew")
        self.content_frame.grid_columnconfigure(0, weight=1)
        self.content_frame.grid_rowconfigure(0, weight=1)

        # Показываем вкладку по умолчанию
        self.show_tab("games", TabGames)

        if self.settings.minimize_to_tray_on_start:
            self.after(100, self.hide_to_tray)

    def _refresh_tab_instance(self, tab):
        """Вызывает метод обновления данных у экземпляра вкладки, если он существует."""
        try:
            if hasattr(tab, "refresh"):
                tab.refresh()
            elif hasattr(tab, "refresh_games"):
                tab.refresh_games()
            elif hasattr(tab, "load_stats"):
                tab.load_stats()
            elif hasattr(tab, "load_month_data"):
                tab.load_month_data()
        except Exception as e:
            print(f"Ошибка обновления вкладки: {e}")
            traceback.print_exc()

    def refresh_tab(self, key: str):
        """Обновляет вкладку по её ключу из кэша tabs_cache."""
        if key in self.tabs_cache:
            self._refresh_tab_instance(self.tabs_cache[key])

    def show_tab(self, key, tab_class):
        if key in self.tabs_cache:
            # Если она уже отображается, просто обновляем её данные
            if self.current_tab_key == key:
                self._refresh_tab_instance(self.tabs_cache[key])
                return
            # Скрываем текущую вкладку
            if self.current_tab is not None:
                self.current_tab.grid_forget()
            # Показываем нужную вкладку и обновляем в ней данные
            new_tab = self.tabs_cache[key]
            new_tab.grid(row=0, column=0, sticky="nsew")
            self.current_tab = new_tab
            self.current_tab_key = key
            self._refresh_tab_instance(new_tab)
        else:
            # Создаём новую вкладку и прячем старую
            if self.current_tab is not None:
                self.current_tab.grid_forget()
            try:
                new_tab = tab_class(self.content_frame, self.db, self.tracker, self.settings)
                new_tab.main_window = self
                new_tab.grid(row=0, column=0, sticky="nsew")
                self.tabs_cache[key] = new_tab
                self.current_tab = new_tab
                self.current_tab_key = key
            except Exception as e:
                print(f"Ошибка создания вкладки {key}: {e}")
                traceback.print_exc()
                return

        # Подсветка кнопки
        for text, (btn, btn_key) in self.nav_buttons.items():
            if btn_key == key:
                btn.configure(fg_color="#2a2a4e", text_color="#00d4ff")
            else:
                btn.configure(fg_color="transparent", text_color="#e0e0e0")

    def open_settings(self):
        if hasattr(self, '_settings_window') and self._settings_window is not None:
            try:
                if self._settings_window.winfo_exists():
                    self._settings_window.lift()
                    self._settings_window.focus_force()
                    return
            except Exception:
                pass
        self._settings_window = SettingsWindow(self, self.db, self.settings)

    def hide_to_tray(self):
        self.withdraw()
        print("GameTimeTracker продолжает работать в фоне")

    def show_window(self):
        self.deiconify()
        try:
            self.state("normal")
        except Exception:
            pass
        try:
            self.attributes("-topmost", True)
            self.update_idletasks()
            self.lift()
            self.focus_force()
            self.after(50, lambda: self.attributes("-topmost", False))
        except Exception:
            self.lift()
            self.focus_force()

    def update_notifications_badge(self):
        """Обновляет бейдж на кнопке уведомлений."""
        count = len(self.pending_notifications)
        if count > 0:
            self.notifications_btn.configure(
                text=f"🔔 Уведомления ({count})",
                text_color="#00d4ff"
            )
        else:
            self.notifications_btn.configure(
                text="🔔 Уведомления",
                text_color="#e0e0e0"
            )

    def add_detected_notification(self, exe_name: str, exe_path: str = None):
        """
        Регистрирует обнаруженный процесс в списке уведомлений без принудительного
        восстановления и фокуса главного окна приложения.
        """
        if not exe_name:
            return
        if self.db and hasattr(self.db, 'add_pending_notification'):
            self.db.add_pending_notification(exe_name, exe_path)
            self.pending_notifications = self.db.get_pending_notifications()
        else:
            if not any(n['exe_name'].lower() == exe_name.lower() for n in self.pending_notifications):
                self.pending_notifications.insert(0, {'exe_name': exe_name, 'exe_path': exe_path})

        self.update_notifications_badge()
        if self._notifications_window and self._notifications_window.winfo_exists():
            self._notifications_window.refresh()

    def remove_pending_notification(self, exe_name: str):
        """Удаляет уведомление из базы и локального списка."""
        if not exe_name:
            return
        if self.db and hasattr(self.db, 'remove_pending_notification'):
            self.db.remove_pending_notification(exe_name)
            self.pending_notifications = self.db.get_pending_notifications()
        else:
            self.pending_notifications = [n for n in self.pending_notifications if n['exe_name'].lower() != exe_name.lower()]

        self.update_notifications_badge()
        if self._notifications_window and self._notifications_window.winfo_exists():
            self._notifications_window.refresh()

    def show_notifications_window(self):
        """Открывает окно списка ожидающих уведомлений."""
        if self._notifications_window is not None:
            try:
                if self._notifications_window.winfo_exists():
                    self._notifications_window.deiconify()
                    self._notifications_window.lift()
                    self._notifications_window.focus_force()
                    return
            except Exception:
                pass
        self._notifications_window = NotificationsDialog(
            self,
            self.db,
            self.tracker,
            on_add_game=self.prompt_add_new_game,
            on_remove_notification=self.remove_pending_notification
        )
        try:
            self._notifications_window.lift()
            self._notifications_window.focus_force()
        except Exception:
            pass

    def open_detected_game_from_notification(self):
        """Вызывается только при клике пользователя по системному уведомлению."""
        self.show_window()
        if self.db and hasattr(self.db, 'get_pending_notifications'):
            self.pending_notifications = self.db.get_pending_notifications()
        if self.pending_notifications:
            latest = self.pending_notifications[0]
            self.prompt_add_new_game(latest['exe_name'], latest.get('exe_path'))
        else:
            self.show_notifications_window()

    def prompt_add_new_game(self, exe_name: str, exe_path: str = None):
        """Отображает диалог добавления обнаруженной игры с красивым именем."""
        from ui.tab_games import AddNewGameDialog, TabGames
        self.show_window()
        if self.current_tab_key != "games":
            self.show_tab("games", TabGames)

        games_tab = self.tabs_cache.get("games")

        if hasattr(self, '_add_game_dialog') and self._add_game_dialog is not None:
            try:
                if self._add_game_dialog.winfo_exists():
                    self._add_game_dialog.deiconify()
                    self._add_game_dialog.lift()
                    self._add_game_dialog.focus_force()
                    return
            except Exception:
                pass

        def on_add(exe, title, path):
            if games_tab and hasattr(games_tab, 'add_detected_game'):
                games_tab.add_detected_game(exe, title, path)
            self.remove_pending_notification(exe)

        def on_ignore(exe):
            self.remove_pending_notification(exe)

        self._add_game_dialog = AddNewGameDialog(
            self,
            exe_name=exe_name,
            exe_path=exe_path,
            tracker=self.tracker,
            on_confirm=on_add,
            on_ignore=on_ignore
        )
        try:
            self._add_game_dialog.lift()
            self._add_game_dialog.focus_force()
        except Exception:
            pass

    def confirm_exit(self):
        """Подтверждение выхода из приложения."""
        from tkinter import messagebox
        if messagebox.askyesno("Выход", "Вы уверены, что хотите закрыть приложение?"):
            self.quit_app()

    def quit_app(self):
        """Полное завершение приложения."""
        if self.on_exit:
            self.on_exit()
        else:
            self.quit()
            self.destroy()
            import sys
            sys.exit(0)