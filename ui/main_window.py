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

        self.title("GameTimeTracker")
        self.geometry("1100x700")
        self.minsize(900, 500)

        ico_path = resource_path("assets/app.ico")
        png_path = resource_path("assets/icon.png")
        if os.path.exists(ico_path):
            self.iconbitmap(ico_path)
        if os.path.exists(png_path):
            icon_img = Image.open(png_path)
            icon_photo = ImageTk.PhotoImage(icon_img)
            self.iconphoto(True, icon_photo)

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
        self.lift()
        self.focus_force()

    def prompt_add_new_game(self, exe_name: str, exe_path: str = None):
        """Отображает диалог добавления обнаруженной игры с красивым именем."""
        from ui.tab_games import AddNewGameDialog
        self.show_window()
        if self.current_tab_key != "games":
            self.show_tab("games")

        games_tab = self.tabs_cache.get("games")

        def on_add(exe, title, path):
            if games_tab and hasattr(games_tab, 'add_detected_game'):
                games_tab.add_detected_game(exe, title, path)

        AddNewGameDialog(self, exe_name=exe_name, exe_path=exe_path, tracker=self.tracker, on_confirm=on_add)

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