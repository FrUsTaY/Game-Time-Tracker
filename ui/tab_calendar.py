"""
tab_calendar.py — вкладка «Календарь» для GameTimeTracker.
Календарь сверху, детали выбранного дня отображаются внизу во всю ширину.
"""

import customtkinter as ctk
from datetime import datetime, date, timedelta
import calendar
from database import Database

# Русские названия месяцев и дней недели
MONTHS_RU = {
    1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель",
    5: "Май", 6: "Июнь", 7: "Июль", 8: "Август",
    9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь"
}
DAYS_RU = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


class TabCalendar(ctk.CTkFrame):
    def __init__(self, master, db: Database, tracker=None, settings=None):
        super().__init__(master, fg_color="#0d0d0d")
        self.db = db
        self.tracker = tracker
        self.settings = settings

        self.current_date = date.today()
        self.current_year = self.current_date.year
        self.current_month = self.current_date.month
        self.sessions_cache = {}  # {date: {game_name: seconds}}
        self.is_loading = False

        self._build_ui()
        self.load_month_data()

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=0)  # навигация
        self.grid_rowconfigure(1, weight=1)  # календарь
        self.grid_rowconfigure(2, weight=0)  # детали (фиксированная высота, будет растягиваться по содержимому)

        # Навигация
        nav_frame = ctk.CTkFrame(self, fg_color="transparent")
        nav_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=10)
        nav_frame.grid_columnconfigure(0, weight=1)
        nav_frame.grid_columnconfigure(1, weight=0)
        nav_frame.grid_columnconfigure(2, weight=0)
        nav_frame.grid_columnconfigure(3, weight=1)

        self.month_label = ctk.CTkLabel(
            nav_frame, text="", font=("Consolas", 20, "bold"), text_color="#00d4ff"
        )
        self.month_label.grid(row=0, column=1, padx=10)

        prev_btn = ctk.CTkButton(
            nav_frame, text="←", width=40, command=self.prev_month,
            fg_color="#1a1a2e", hover_color="#2a2a4e", font=("Segoe UI", 16, "bold")
        )
        prev_btn.grid(row=0, column=0, sticky="e", padx=5)

        next_btn = ctk.CTkButton(
            nav_frame, text="→", width=40, command=self.next_month,
            fg_color="#1a1a2e", hover_color="#2a2a4e", font=("Segoe UI", 16, "bold")
        )
        next_btn.grid(row=0, column=2, sticky="w", padx=5)

        # Итог за месяц (помещаем справа от навигации)
        self.total_month_label = ctk.CTkLabel(
            nav_frame, text="", font=("Consolas", 14), text_color="#00d4ff"
        )
        self.total_month_label.grid(row=0, column=3, padx=10, sticky="e")

        # Календарь (контейнер)
        self.calendar_frame = ctk.CTkFrame(self, fg_color="#1a1a2e", corner_radius=12)
        self.calendar_frame.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 10))
        self.calendar_frame.grid_rowconfigure(0, weight=0)  # заголовки
        # строки для недель будут добавляться динамически

        # Детали (нижняя панель)
        self.details_frame = ctk.CTkFrame(self, fg_color="#1a1a2e", corner_radius=12)
        self.details_frame.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 20))
        self.details_frame.grid_columnconfigure(0, weight=1)

        # Заголовок деталей
        self.details_title = ctk.CTkLabel(
            self.details_frame, text="Выберите день", font=("Consolas", 16, "bold"), text_color="#00d4ff"
        )
        self.details_title.grid(row=0, column=0, pady=10, padx=10, sticky="w")

        # Прокручиваемая область для списка игр
        self.details_scroll = ctk.CTkScrollableFrame(self.details_frame, fg_color="transparent", orientation="vertical")
        self.details_scroll.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.details_frame.grid_rowconfigure(1, weight=1)

        # Сумма за день
        self.total_day_label = ctk.CTkLabel(
            self.details_frame, text="", font=("Consolas", 14), text_color="#7b2fff"
        )
        self.total_day_label.grid(row=2, column=0, pady=10)

        self._update_month_label()

    def _update_month_label(self):
        month_name = MONTHS_RU.get(self.current_month, "")
        self.month_label.configure(text=f"{month_name} {self.current_year}")

    def prev_month(self):
        if self.is_loading:
            return
        if self.current_month == 1:
            self.current_month = 12
            self.current_year -= 1
        else:
            self.current_month -= 1
        self._update_month_label()
        self.after(0, self.load_month_data)

    def next_month(self):
        if self.is_loading:
            return
        if self.current_month == 12:
            self.current_month = 1
            self.current_year += 1
        else:
            self.current_month += 1
        self._update_month_label()
        self.after(0, self.load_month_data)

    def load_month_data(self):
        if self.is_loading:
            return
        self.is_loading = True

        start_date = date(self.current_year, self.current_month, 1)
        if self.current_month == 12:
            end_date = date(self.current_year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = date(self.current_year, self.current_month + 1, 1) - timedelta(days=1)

        sessions = self.db.get_sessions_range(start_date, end_date)

        self.sessions_cache.clear()
        month_total_seconds = 0
        for sess in sessions:
            sess_date_str = sess['started_at'][:10]
            sess_date = datetime.fromisoformat(sess_date_str).date()
            duration = sess.get('duration_seconds', 0)
            if duration <= 0:
                continue
            if sess_date not in self.sessions_cache:
                self.sessions_cache[sess_date] = {}
            game_name = sess['display_name']
            self.sessions_cache[sess_date][game_name] = self.sessions_cache[sess_date].get(game_name, 0) + duration
            month_total_seconds += duration

        total_hours = month_total_seconds / 3600
        total_str = f"Итого за месяц: {int(total_hours)} ч {int((total_hours % 1) * 60)} мин"
        self.total_month_label.configure(text=total_str)

        self._build_calendar_grid()
        self.is_loading = False

    def _build_calendar_grid(self):
        # Очищаем календарь
        for widget in self.calendar_frame.winfo_children():
            widget.destroy()

        # Заголовки дней недели
        for col, header in enumerate(DAYS_RU):
            lbl = ctk.CTkLabel(
                self.calendar_frame, text=header, font=("Segoe UI", 12, "bold"), text_color="#7b2fff"
            )
            lbl.grid(row=0, column=col, padx=5, pady=5, sticky="nsew")

        cal = calendar.monthcalendar(self.current_year, self.current_month)
        today = date.today()

        for week_idx, week in enumerate(cal, start=1):
            for col_idx, day in enumerate(week):
                if day == 0:
                    cell = ctk.CTkFrame(self.calendar_frame, fg_color="#2a2a3e", corner_radius=8)
                    cell.grid(row=week_idx, column=col_idx, padx=2, pady=2, sticky="nsew")
                    ctk.CTkLabel(cell, text="").pack(expand=True)
                    continue

                cell_date = date(self.current_year, self.current_month, day)
                has_activity = cell_date in self.sessions_cache
                bg_color = "#004466" if has_activity else "#1a1a2e"
                border_color = "#00ff88" if cell_date == today else bg_color

                cell = ctk.CTkFrame(
                    self.calendar_frame, fg_color=bg_color, corner_radius=8,
                    border_width=2 if cell_date == today else 0, border_color=border_color
                )
                cell.grid(row=week_idx, column=col_idx, padx=2, pady=2, sticky="nsew")

                day_btn = ctk.CTkButton(
                    cell, text=str(day), fg_color="transparent", text_color="#e0e0e0",
                    hover_color="#2a2a4e", font=("Segoe UI", 12),
                    command=lambda d=cell_date: self.show_day_details(d)
                )
                day_btn.pack(expand=True, fill="both", padx=2, pady=2)

                if has_activity:
                    dot = ctk.CTkLabel(cell, text="●", text_color="#00d4ff", font=("Segoe UI", 8))
                    dot.place(relx=0.5, rely=0.85, anchor="center")

        # Настройка весов
        for col in range(7):
            self.calendar_frame.grid_columnconfigure(col, weight=1)
        for row in range(1, len(cal) + 1):
            self.calendar_frame.grid_rowconfigure(row, weight=1)

    def show_day_details(self, day_date: date):
        """Отображает детали по выбранному дню в нижней панели."""
        month_name = MONTHS_RU.get(day_date.month, "")
        self.details_title.configure(text=f"{day_date.day} {month_name} {day_date.year}")

        # Очищаем область списка
        for widget in self.details_scroll.winfo_children():
            widget.destroy()

        day_data = self.sessions_cache.get(day_date, {})
        if not day_data:
            no_data_lbl = ctk.CTkLabel(
                self.details_scroll, text="Нет игровой активности в этот день",
                text_color="#666666", font=("Segoe UI", 12)
            )
            no_data_lbl.pack(pady=20)
            self.total_day_label.configure(text="Всего: 0 ч 0 мин")
            return

        sorted_games = sorted(day_data.items(), key=lambda x: x[1], reverse=True)
        total_day_sec = 0
        # Используем горизонтальную прокрутку, если нужно, но лучше вертикальную: каждый блок – игра
        for game_name, secs in sorted_games:
            total_day_sec += secs
            hours = secs // 3600
            minutes = (secs % 3600) // 60
            time_str = f"{hours:02d}:{minutes:02d}"
            game_frame = ctk.CTkFrame(self.details_scroll, fg_color="transparent")
            game_frame.pack(fill="x", pady=4, padx=5)
            # Название игры слева, время справа
            ctk.CTkLabel(game_frame, text=game_name, font=("Segoe UI", 13), text_color="#e0e0e0", anchor="w").pack(side="left", padx=5)
            ctk.CTkLabel(game_frame, text=time_str, font=("Consolas", 13), text_color="#00d4ff", anchor="e").pack(side="right", padx=5)

        total_hours = total_day_sec / 3600
        total_str = f"Всего за день: {int(total_hours)} ч {int((total_hours % 1) * 60)} мин"
        self.total_day_label.configure(text=total_str)