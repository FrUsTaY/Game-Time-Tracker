"""
tracker.py — модуль мониторинга игровых процессов для GameTimeTracker.
Работает в отдельном потоке, каждую секунду проверяет активные процессы и
учитывает время для отслеживаемых игр с учётом настройки track_only_active_window.
"""

import threading
import time
import os
from datetime import datetime
from typing import Dict, List, Optional, Callable, Any

import psutil
import win32gui
import win32process
import win32ui
import win32con
from PIL import Image

from database import Database
from settings import AppSettings


class GameTracker:
    def __init__(
        self,
        db: Database,
        settings: AppSettings,
        on_tick: Optional[Callable[[int, int], None]] = None
    ):
        self.db = db
        self.settings = settings
        self.on_tick = on_tick

        # Активные сессии: {game_id: {'session_id': int, 'current_seconds': int, 'process_pid': int, 'was_active': bool}}
        self.active_sessions: Dict[int, Dict[str, Any]] = {}
        self.lock = threading.Lock()

        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        print("GameTracker: поток мониторинга запущен")

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)

        with self.lock:
            for game_id, session_info in list(self.active_sessions.items()):
                self._close_session(game_id, session_info, force=True)
            self.active_sessions.clear()
        print("GameTracker: поток мониторинга остановлен")

    def _monitor_loop(self) -> None:
        while self._running:
            try:
                self._check_processes()
            except Exception as e:
                print(f"Ошибка в цикле мониторинга: {e}")
            time.sleep(1.0)

    def _check_processes(self) -> None:
        # Получаем все активные игры из БД
        games = self.db.get_all_games(archived=False)
        if not games:
            return

        games_by_exe = {game['exe_name'].lower(): game for game in games}

        # Получаем запущенные процессы
        running_processes = {}
        for proc in psutil.process_iter(['pid', 'name', 'exe']):
            try:
                proc_info = proc.info
                if proc_info['name']:
                    exe_name = proc_info['name'].lower()
                    running_processes[exe_name] = {
                        'pid': proc_info['pid'],
                        'exe_path': proc_info['exe']
                    }
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        # Игры, которые сейчас запущены (выбираем процесс с окном, если есть)
        tracked_games = {}
        for exe_name, game_info in games_by_exe.items():
            if exe_name not in running_processes:
                continue
            # Собираем все PID с таким именем
            pids = []
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    if proc.info['name'] and proc.info['name'].lower() == exe_name:
                        pids.append(proc.info['pid'])
                except:
                    continue
            # Выбираем PID, у которого есть видимое окно
            selected_pid = None
            selected_exe_path = None
            for pid in pids:
                has_window = False
                try:
                    def enum_cb(hwnd, hwnds):
                        if win32gui.IsWindowVisible(hwnd):
                            _, found_pid = win32process.GetWindowThreadProcessId(hwnd)
                            if found_pid == pid:
                                hwnds.append(hwnd)
                        return True
                    hwnds = []
                    win32gui.EnumWindows(enum_cb, hwnds)
                    if hwnds:
                        has_window = True
                except:
                    pass
                if has_window:
                    selected_pid = pid
                    break
            if selected_pid is None and pids:
                selected_pid = pids[0]
            if selected_pid is not None:
                tracked_games[game_info['id']] = {
                    'game_info': game_info,
                    'pid': selected_pid,
                    'exe_path': running_processes[exe_name]['exe_path']
                }

        # Получаем активное окно
        active_pid = self._get_active_window_pid()

        with self.lock:
            # 1. Обновляем существующие сессии
            for game_id, session_info in list(self.active_sessions.items()):
                if game_id not in tracked_games:
                    # Игра больше не запущена -> завершаем сессию
                    self._close_session(game_id, session_info, force=False)
                    continue

                # Игра всё ещё запущена
                is_active = self._is_game_active(game_id, tracked_games[game_id]['pid'], active_pid)
                # Отладка
                print(f"DEBUG: game_id {game_id}, active_pid={active_pid}, game_pid={tracked_games[game_id]['pid']}, is_active={is_active}, track_only={self.settings.track_only_active_window}")
                if is_active:
                    # Увеличиваем время текущей сессии (только локально)
                    session_info['current_seconds'] += 1
                    # НЕ обновляем БД каждую секунду, только при завершении сессии
                    # Получаем ранее сохранённое общее время из БД (без учёта текущей сессии)
                    game = self.db.get_game_by_id(game_id)
                    saved_seconds = game['total_seconds'] if game else 0
                    total_seconds = saved_seconds + session_info['current_seconds']
                    print(f"DEBUG: вызываем on_tick для game_id {game_id}, total_seconds={total_seconds} (сессия={session_info['current_seconds']}, сохранено={saved_seconds})")
                    if self.on_tick:
                        self.on_tick(game_id, total_seconds, True)
                    else:
                        print("DEBUG: on_tick is None!")
                # Если не активно, ничего не добавляем, но сессию не закрываем

            # 2. Создаём новые сессии для вновь запущенных игр
            for game_id, proc_info in tracked_games.items():
                if game_id not in self.active_sessions:
                    # Создаём сессию сразу при запуске процесса, даже если не активен
                    # Чтобы потом при активации уже была сессия
                    session_id = self.db.start_session(game_id)
                    # Обновляем last_launched (без добавления секунд)
                    self.db.update_game_time(game_id, 0)
                    self.active_sessions[game_id] = {
                        'session_id': session_id,
                        'current_seconds': 0,
                        'process_pid': proc_info['pid'],
                        'was_active': False
                    }
                    print(f"GameTracker: создана сессия {session_id} для игры ID {game_id} (PID {proc_info['pid']})")

    def _get_active_window_pid(self) -> Optional[int]:
        try:
            hwnd = win32gui.GetForegroundWindow()
            if hwnd == 0:
                return None
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            title = win32gui.GetWindowText(hwnd)
            print(f"DEBUG: активное окно: PID={pid}, заголовок='{title}'")
            return pid
        except Exception as e:
            print(f"DEBUG: ошибка получения активного окна: {e}")
            return None

    def _is_game_active(self, game_id: int, game_pid: int, active_pid: Optional[int]) -> bool:
        track_only = self.settings.track_only_active_window
        if not track_only:
            return True
        
        if active_pid is None:
            return False
        
        # Сначала пробуем прямое сравнение PID
        if game_pid == active_pid:
            return True
        
        # Если не совпало, получаем все окна текущего процесса игры
        try:
            import win32gui
            def enum_windows_callback(hwnd, hwnds):
                if win32gui.IsWindowVisible(hwnd):
                    _, pid = win32process.GetWindowThreadProcessId(hwnd)
                    if pid == game_pid:
                        hwnds.append(hwnd)
                        # Отладочный вывод: заголовок окна
                        title = win32gui.GetWindowText(hwnd)
                        print(f"DEBUG: найдено окно процесса {game_pid}: '{title}'")
                return True
            
            hwnds = []
            win32gui.EnumWindows(enum_windows_callback, hwnds)
            print(f"DEBUG: для PID {game_pid} найдено окон: {len(hwnds)}")
            for hwnd in hwnds:
                title = win32gui.GetWindowText(hwnd)
                print(f"DEBUG:   окно: {title}")
            
            # Проверяем, является ли одно из окон игры активным
            active_hwnd = win32gui.GetForegroundWindow()
            active_title = win32gui.GetWindowText(active_hwnd)
            print(f"DEBUG: активное окно PID={active_pid}, HWND={active_hwnd}, title={active_title}")
            if active_hwnd in hwnds:
                print("DEBUG: активное окно найдено среди окон игры, возвращаем True")
                return True
            else:
                print("DEBUG: активное окно НЕ найдено среди окон игры")
        except Exception as e:
            print(f"DEBUG: ошибка проверки окон: {e}")
        
        return False

    def _close_session(self, game_id: int, session_info: Dict[str, Any], force: bool = False) -> None:
        session_id = session_info['session_id']
        seconds = session_info['current_seconds']

        if seconds > 0 or force:
            self.db.end_session(session_id, seconds)
            # Не обновляем update_game_time повторно, так как уже обновляли каждую секунду
            # Но на случай принудительного закрытия без активности
            if seconds > 0:
                self.db.update_game_time(game_id, seconds)  # уже обновлено, но оставим для синхронизации
            print(f"GameTracker: завершена сессия {session_id} для игры ID {game_id}, секунд: {seconds}")
            # После завершения сессии нужно обновить UI, чтобы статус стал "не играю"
            if self.on_tick:
                # Получаем текущее общее время игры
                game = self.db.get_game_by_id(game_id)
                total_seconds = game['total_seconds'] if game else 0
                self.on_tick(game_id, total_seconds, False)

        if game_id in self.active_sessions:
            del self.active_sessions[game_id]

    # ----- Вспомогательные методы для UI -----

    def get_running_processes(self) -> List[Dict[str, Any]]:
        processes = []
        for proc in psutil.process_iter(['pid', 'name', 'exe']):
            try:
                info = proc.info
                if info['name']:
                    processes.append({
                        'name': info['name'],
                        'pid': info['pid'],
                        'exe': info['exe'] or ''
                    })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return processes

    def get_exe_icon(self, exe_path: str, size: int = 32) -> Optional[Image.Image]:
        if not exe_path or not os.path.exists(exe_path):
            return None
        try:
            large_icons, small_icons = win32gui.ExtractIconEx(exe_path, 0)
            if large_icons and large_icons[0]:
                hicon = large_icons[0]
            elif small_icons and small_icons[0]:
                hicon = small_icons[0]
            else:
                return None

            hdc = win32ui.CreateDCFromHandle(win32gui.GetDC(0))
            hbmp = win32ui.CreateBitmap()
            hbmp.CreateCompatibleBitmap(hdc, size, size)
            hdc_mem = hdc.CreateCompatibleDC()
            hdc_mem.SelectObject(hbmp)

            win32gui.DrawIconEx(hdc_mem.GetSafeHdc(), 0, 0, hicon, size, size, 0, None, win32con.DI_NORMAL)

            bmp_bits = hbmp.GetBitmapBits(True)
            img = Image.frombuffer('RGBA', (size, size), bmp_bits, 'raw', 'BGRA', 0, 1)

            win32gui.DestroyIcon(hicon)
            hdc_mem.DeleteDC()
            # hbmp.DeleteObject()  # 'PyCBitmap' не имеет метода DeleteObject
            hdc.DeleteDC()

            return img
        except Exception as e:
            print(f"Ошибка извлечения иконки из {exe_path}: {e}")
            return None