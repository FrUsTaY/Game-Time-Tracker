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

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


class MainWindow(ctk.CTk):
    def __init__(self, db, tracker, settings):
        super().__init__()
        self.db = db
        self.tracker = tracker
        self.settings = settings
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

    def show_tab(self, key, tab_class):
        # Если вкладка уже создана и видима, ничего не делаем
        if key in self.tabs_cache:
            # Если она уже отображается, просто возвращаемся
            if self.current_tab_key == key:
                return
            # Скрываем текущую вкладку
            if self.current_tab is not None:
                self.current_tab.grid_forget()
            # Показываем нужную вкладку
            new_tab = self.tabs_cache[key]
            new_tab.grid(row=0, column=0, sticky="nsew")
            self.current_tab = new_tab
            self.current_tab_key = key
        else:
            # Создаём новую вкладку и прячем старую
            if self.current_tab is not None:
                self.current_tab.grid_forget()
            try:
                new_tab = tab_class(self.content_frame, self.db, self.tracker, self.settings)
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
        SettingsWindow(self, self.db, self.settings)

    def hide_to_tray(self):
        self.withdraw()
        print("GameTimeTracker продолжает работать в фоне")

    def show_window(self):
        self.deiconify()
        self.lift()
        self.focus_force()

    def confirm_exit(self):
        """Подтверждение выхода из приложения."""
        from tkinter import messagebox
        if messagebox.askyesno("Выход", "Вы уверены, что хотите закрыть приложение?"):
            self.quit_app()

    def quit_app(self):
        """Полное завершение приложения."""
        self.quit()
        self.destroy()
        import sys
        sys.exit(0)