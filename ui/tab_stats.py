"""
tab_stats.py — вкладка «Статистика» для GameTimeTracker.
"""

import customtkinter as ctk
from datetime import datetime, date, timedelta
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt

from database import Database


class TabStats(ctk.CTkFrame):
    """Вкладка «Статистика»."""

    def __init__(self, master, db: Database, tracker=None, settings=None):
        """
        tracker и settings не используются, но принимаются для единообразия.
        """
        super().__init__(master, fg_color="#0d0d0d")
        self.db = db
        self.tracker = tracker
        self.settings = settings

        plt.style.use('dark_background')
        self._setup_matplotlib_style()
        self._build_ui()
        self.load_stats()

    def _setup_matplotlib_style(self):
        plt.rcParams['figure.facecolor'] = '#0d0d0d'
        plt.rcParams['axes.facecolor'] = '#1a1a2e'
        plt.rcParams['axes.edgecolor'] = '#00d4ff'
        plt.rcParams['axes.labelcolor'] = '#e0e0e0'
        plt.rcParams['xtick.color'] = '#e0e0e0'
        plt.rcParams['ytick.color'] = '#e0e0e0'
        plt.rcParams['text.color'] = '#e0e0e0'
        plt.rcParams['legend.facecolor'] = '#1a1a2e'
        plt.rcParams['legend.edgecolor'] = '#00d4ff'

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.main_canvas = ctk.CTkScrollableFrame(self, fg_color="#0d0d0d")
        self.main_canvas.grid(row=0, column=0, sticky="nsew", padx=20, pady=10)
        self.main_canvas.grid_columnconfigure(0, weight=1)

        # Сводные карточки
        self.cards_frame = ctk.CTkFrame(self.main_canvas, fg_color="transparent")
        self.cards_frame.grid(row=0, column=0, sticky="ew", pady=10)
        for i in range(4):
            self.cards_frame.grid_columnconfigure(i, weight=1)

        self.card_total_hours = self._create_stat_card(self.cards_frame, "Всего часов", "0 ч", 0)
        self.card_longest_session = self._create_stat_card(self.cards_frame, "Самая долгая сессия", "—", 1)
        self.card_best_day = self._create_stat_card(self.cards_frame, "Самый активный день", "—", 2)
        self.card_counts = self._create_stat_card(self.cards_frame, "Игр в библиотеке / архиве", "0 / 0", 3)

        # Топ игр
        self.top_label = ctk.CTkLabel(
            self.main_canvas, text="🏆 Топ игр по времени",
            font=("Consolas", 16, "bold"), text_color="#00d4ff"
        )
        self.top_label.grid(row=1, column=0, sticky="w", pady=(20, 5))

        self.top_frame = ctk.CTkFrame(self.main_canvas, fg_color="#1a1a2e", corner_radius=12)
        self.top_frame.grid(row=2, column=0, sticky="ew", pady=5)
        self.top_frame.grid_columnconfigure(0, weight=1)

        # График активности
        self.activity_label = ctk.CTkLabel(
            self.main_canvas, text="📈 График активности",
            font=("Consolas", 16, "bold"), text_color="#00d4ff"
        )
        self.activity_label.grid(row=3, column=0, sticky="w", pady=(20, 5))

        self.period_frame = ctk.CTkFrame(self.main_canvas, fg_color="transparent")
        self.period_frame.grid(row=4, column=0, sticky="w", pady=5)
        self.period_var = ctk.StringVar(value="30")
        for days, text in [("7", "7 дней"), ("30", "30 дней"), ("90", "90 дней")]:
            btn = ctk.CTkRadioButton(
                self.period_frame, text=text, variable=self.period_var, value=days,
                command=self.update_activity_graph, fg_color="#00d4ff", hover_color="#7b2fff"
            )
            btn.pack(side="left", padx=10)

        self.activity_frame = ctk.CTkFrame(self.main_canvas, fg_color="#1a1a2e", corner_radius=12)
        self.activity_frame.grid(row=5, column=0, sticky="ew", pady=5)

        # Среднее время сессии
        self.avg_label = ctk.CTkLabel(
            self.main_canvas, text="⏱ Среднее время сессии",
            font=("Consolas", 16, "bold"), text_color="#00d4ff"
        )
        self.avg_label.grid(row=6, column=0, sticky="w", pady=(20, 5))

        self.avg_frame = ctk.CTkFrame(self.main_canvas, fg_color="#1a1a2e", corner_radius=12)
        self.avg_frame.grid(row=7, column=0, sticky="ew", pady=5)
        self.avg_frame.grid_columnconfigure(0, weight=1)

        self.avg_table = ctk.CTkScrollableFrame(self.avg_frame, fg_color="transparent")
        self.avg_table.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

    def _create_stat_card(self, parent, title: str, value: str, col: int):
        card = ctk.CTkFrame(parent, fg_color="#1a1a2e", corner_radius=12, border_width=1, border_color="#00d4ff")
        card.grid(row=0, column=col, padx=10, pady=10, sticky="ew")
        card.grid_columnconfigure(0, weight=1)

        title_label = ctk.CTkLabel(card, text=title, font=("Segoe UI", 12), text_color="#888888")
        title_label.grid(row=0, column=0, pady=(10, 5))

        value_label = ctk.CTkLabel(card, text=value, font=("Consolas", 18, "bold"), text_color="#00d4ff")
        value_label.grid(row=1, column=0, pady=(0, 10))

        card.value_label = value_label
        return card

    def load_stats(self):
        self._update_summary_cards()
        self._update_top_games()
        self.update_activity_graph()
        self._update_avg_session_time()

    def _update_summary_cards(self):
        games = self.db.get_all_games(archived=False)
        archived_games = self.db.get_all_games(archived=True)
        active_count = len(games)
        archived_count = len(archived_games)

        total_seconds = sum(g['total_seconds'] for g in games)
        total_hours = total_seconds / 3600
        self.card_total_hours.value_label.configure(text=f"{total_hours:.1f} ч")

        cursor = self.db.conn.cursor()
        cursor.execute('''
            SELECT s.duration_seconds, g.display_name, s.started_at
            FROM sessions s
            JOIN games g ON s.game_id = g.id
            WHERE s.duration_seconds IS NOT NULL
            ORDER BY s.duration_seconds DESC
            LIMIT 1
        ''')
        longest = cursor.fetchone()
        if longest and longest[0] > 0:
            hours = longest[0] / 3600
            game_name = longest[1]
            date_str = longest[2][:10] if longest[2] else "—"
            self.card_longest_session.value_label.configure(text=f"{game_name}\n{hours:.1f} ч ({date_str})")
        else:
            self.card_longest_session.value_label.configure(text="Нет данных")

        cursor.execute('''
            SELECT DATE(s.started_at) as day, SUM(s.duration_seconds) as total
            FROM sessions s
            WHERE s.duration_seconds IS NOT NULL
            GROUP BY day
            ORDER BY total DESC
            LIMIT 1
        ''')
        best_day = cursor.fetchone()
        if best_day and best_day[1] > 0:
            hours = best_day[1] / 3600
            self.card_best_day.value_label.configure(text=f"{best_day[0]}\n{hours:.1f} ч")
        else:
            self.card_best_day.value_label.configure(text="Нет данных")

        self.card_counts.value_label.configure(text=f"{active_count} / {archived_count}")

    def _update_top_games(self, top_n: int = 5):
        games = self.db.get_all_games(archived=False)
        games_sorted = sorted(games, key=lambda x: x['total_seconds'], reverse=True)[:top_n]
        if not games_sorted:
            for widget in self.top_frame.winfo_children():
                widget.destroy()
            label = ctk.CTkLabel(self.top_frame, text="Нет данных", text_color="#666666")
            label.pack(pady=20)
            return

        names = [g['display_name'] for g in games_sorted]
        hours = [g['total_seconds'] / 3600 for g in games_sorted]

        fig = Figure(figsize=(6, 4), dpi=100)
        ax = fig.add_subplot()
        bars = ax.barh(names, hours, color='#00d4ff', edgecolor='#7b2fff', height=0.6)
        for bar, h in zip(bars, hours):
            ax.text(bar.get_width() + 0.1, bar.get_y() + bar.get_height()/2,
                    f'{h:.1f} ч', va='center', fontsize=9, color='#e0e0e0')
        ax.set_xlabel('Часы', color='#e0e0e0')
        ax.set_title('Топ игр по времени', color='#00d4ff')
        ax.invert_yaxis()

        for widget in self.top_frame.winfo_children():
            widget.destroy()
        canvas = FigureCanvasTkAgg(fig, master=self.top_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=10)

    def update_activity_graph(self):
        days = int(self.period_var.get())
        end_date = date.today()
        start_date = end_date - timedelta(days=days-1)
        sessions = self.db.get_sessions_range(start_date, end_date)

        daily_seconds = {}
        for sess in sessions:
            sess_date = datetime.fromisoformat(sess['started_at']).date()
            duration = sess.get('duration_seconds', 0)
            if duration > 0:
                daily_seconds[sess_date] = daily_seconds.get(sess_date, 0) + duration

        current = start_date
        dates = []
        hours_list = []
        while current <= end_date:
            dates.append(current.strftime("%d.%m"))
            secs = daily_seconds.get(current, 0)
            hours_list.append(secs / 3600)
            current += timedelta(days=1)

        fig = Figure(figsize=(8, 4), dpi=100)
        ax = fig.add_subplot()
        ax.bar(dates, hours_list, color='#7b2fff', edgecolor='#00d4ff', alpha=0.7)
        ax.set_xlabel('Дата', color='#e0e0e0')
        ax.set_ylabel('Часы', color='#e0e0e0')
        ax.set_title(f'Активность за последние {days} дней', color='#00d4ff')
        plt.setp(ax.get_xticklabels(), rotation=45, ha='right', fontsize=8)

        for widget in self.activity_frame.winfo_children():
            widget.destroy()
        canvas = FigureCanvasTkAgg(fig, master=self.activity_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=10)

    def _update_avg_session_time(self):
        for widget in self.avg_table.winfo_children():
            widget.destroy()

        header_frame = ctk.CTkFrame(self.avg_table, fg_color="transparent")
        header_frame.pack(fill="x", pady=(0, 5))
        ctk.CTkLabel(header_frame, text="Игра", font=("Segoe UI", 12, "bold"), width=200, anchor="w").pack(side="left", padx=5)
        ctk.CTkLabel(header_frame, text="Сессий", font=("Segoe UI", 12, "bold"), width=80, anchor="center").pack(side="left")
        ctk.CTkLabel(header_frame, text="Среднее время", font=("Segoe UI", 12, "bold"), width=120, anchor="center").pack(side="left")

        cursor = self.db.conn.cursor()
        cursor.execute('''
            SELECT g.display_name, COUNT(s.id) as session_count, AVG(s.duration_seconds) as avg_sec
            FROM games g
            LEFT JOIN sessions s ON g.id = s.game_id
            WHERE g.is_archived = 0 AND s.duration_seconds IS NOT NULL
            GROUP BY g.id
            ORDER BY avg_sec DESC
        ''')
        rows = cursor.fetchall()

        if not rows:
            empty_label = ctk.CTkLabel(self.avg_table, text="Нет данных о сессиях", text_color="#666666")
            empty_label.pack(pady=20)
            return

        for row in rows:
            game_name = row[0]
            count = row[1]
            avg_sec = row[2] or 0
            avg_hours = avg_sec / 3600
            if avg_hours >= 1:
                avg_str = f"{avg_hours:.1f} ч"
            else:
                avg_min = avg_sec / 60
                avg_str = f"{avg_min:.0f} мин"

            row_frame = ctk.CTkFrame(self.avg_table, fg_color="transparent")
            row_frame.pack(fill="x", pady=2)
            ctk.CTkLabel(row_frame, text=game_name, width=200, anchor="w", font=("Segoe UI", 11)).pack(side="left", padx=5)
            ctk.CTkLabel(row_frame, text=str(count), width=80, anchor="center", font=("Segoe UI", 11)).pack(side="left")
            ctk.CTkLabel(row_frame, text=avg_str, width=120, anchor="center", font=("Consolas", 11), text_color="#00d4ff").pack(side="left")