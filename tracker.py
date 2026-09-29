"""
tracker.py — модуль мониторинга игровых процессов для GameTimeTracker.
Работает в отдельном потоке, каждую секунду проверяет активные процессы и
учитывает время для отслеживаемых игр с учётом настройки track_only_active_window.
"""

import threading
import time
import os
from typing import Dict, List, Optional, Callable, Any

import psutil
import win32gui
import win32process
import win32ui
import win32con
from PIL import Image

from database import Database
from settings import AppSettings

# Общеизвестные системные процессы и консольные утилиты Windows
SYSTEM_EXCLUDE_EXES = {
    # Системные оболочки, менеджеры и терминалы
    'explorer.exe', 'taskmgr.exe', 'cmd.exe', 'powershell.exe', 'pwsh.exe',
    'conhost.exe', 'wt.exe', 'bash.exe', 'wsl.exe',
    # Системные службы и фоновые процессы Windows
    'svchost.exe', 'dwm.exe', 'csrss.exe', 'smss.exe', 'lsass.exe', 'services.exe',
    'wininit.exe', 'winlogon.exe', 'sihost.exe', 'fontdrvhost.exe', 'ctfmon.exe',
    'searchhost.exe', 'searchindexer.exe', 'searchfilterhost.exe', 'searchprotocolhost.exe',
    'startmenuexperiencehost.exe', 'shellexperiencehost.exe', 'textinputhost.exe',
    'applicationframehost.exe', 'runtimebroker.exe', 'lockapp.exe', 'systemsettings.exe',
    'regedit.exe', 'smartscreen.exe', 'securityhealthsystray.exe', 'securityhealthservice.exe',
    'spoolsv.exe', 'audiodg.exe', 'wlanext.exe', 'dashost.exe',
    # Браузеры
    'chrome.exe', 'msedge.exe', 'firefox.exe', 'opera.exe', 'brave.exe',
    'yandex.exe', 'browser.exe', 'vivaldi.exe', 'tor.exe',
    # Мессенджеры и клиенты связи
    'telegram.exe', 'discord.exe', 'skype.exe', 'slack.exe', 'whatsapp.exe',
    'teams.exe', 'viber.exe', 'element.exe', 'zoom.exe',
    # Медиаплееры, редакторы, системные и игровые лаунчеры
    'spotify.exe', 'vlc.exe', 'mpc-hc.exe', 'mpc-be.exe', 'foobar2000.exe', 'aimp.exe',
    'notepad.exe', 'notepad++.exe', 'code.exe', 'devenv.exe',
    'winrar.exe', '7zfm.exe', 'everything.exe', 'calculator.exe', 'calc.exe',
    'steam.exe', 'steamwebhelper.exe', 'epicgameslauncher.exe',
    # Утилиты разработки и исполняемый файл приложения
    'git.exe', 'python.exe', 'pythonw.exe', 'gametimetracker.exe'
}


def is_system_process(exe_name: str, exe_path: Optional[str] = None) -> bool:
    """
    Проверяет, является ли процесс системной утилитой Windows или фоновой службой.
    Исключаются как известные системные имена, так и файлы из папок Windows (System32, SysWOW64 и др.).
    """
    if not exe_name:
        return False
    name_lower = exe_name.lower()
    if name_lower in SYSTEM_EXCLUDE_EXES:
        return True

    if exe_path:
        path_lower = os.path.normpath(exe_path).lower()
        system_root = os.environ.get("SystemRoot", "C:\\Windows").lower()
        windir = os.environ.get("windir", "C:\\Windows").lower()
        if path_lower.startswith(system_root) or path_lower.startswith(windir) or path_lower.startswith("c:\\windows"):
            return True
        if "\\system32\\" in path_lower or "\\syswow64\\" in path_lower or "\\winsxs\\" in path_lower:
            return True

    return False


class GameTracker:
    def __init__(
        self,
        db: Database,
        settings: AppSettings,
        on_tick: Optional[Callable[[int, int, bool], None]] = None,
        tray: Optional[Any] = None,
        on_notification: Optional[Callable[[str, str], None]] = None,
        on_game_detected: Optional[Callable[[str, Optional[str]], None]] = None
    ):
        self.db = db
        self.settings = settings
        self.on_tick = on_tick
        self.tray = tray
        self.on_notification = on_notification
        self.on_game_detected = on_game_detected

        # Активные сессии: {game_id: {'session_id': int, 'current_seconds': int, 'last_flushed_seconds': int, 'initial_total_seconds': int, 'process_pid': int, 'was_active': bool, 'long_session_notified': bool}}
        self.active_sessions: Dict[int, Dict[str, Any]] = {}
        self.flush_interval = 60  # Интервал периодического сброса прогресса в БД (секунды)
        self.lock = threading.Lock()

        self._running = False
        self._thread: Optional[threading.Thread] = None

        # Множества для отслеживания запущенных процессов (.exe) и предотвращения спама уведомлениями
        self._seen_exes: set = set()
        self._notified_new_exes: set = set()
        self._ignored_exes: set = set()
        self._unwindowed_attempts: Dict[str, int] = {}

        # Загружаем сохранённые игнорируемые процессы из БД
        if self.db and hasattr(self.db, 'get_ignored_processes'):
            try:
                ignored_list = self.db.get_ignored_processes()
                self._ignored_exes = {row['exe_name'].lower() for row in ignored_list if row.get('exe_name')}
            except Exception as e:
                print(f"GameTracker: ошибка загрузки игнорируемых процессов: {e}")

    def notify(self, title: str, message: str) -> None:
        """Отправка системного уведомления через tray или колбэк"""
        if self.on_notification:
            try:
                self.on_notification(title, message)
            except Exception as e:
                print(f"GameTracker: ошибка в on_notification: {e}")

        if self.tray and hasattr(self.tray, 'show_notification'):
            try:
                self.tray.show_notification(title, message)
            except Exception as e:
                print(f"GameTracker: ошибка в tray.show_notification: {e}")

        if not self.on_notification and not self.tray:
            print(f"Уведомление: {title} - {message}")

    def get_game_total_seconds(self, game_id: int, default_seconds: int = 0) -> int:
        """Возвращает актуальное общее время игры с учётом текущей незавершённой сессии"""
        with self.lock:
            if game_id in self.active_sessions:
                info = self.active_sessions[game_id]
                return info.get('initial_total_seconds', default_seconds) + info.get('current_seconds', 0)
            return default_seconds

    def is_game_currently_playing(self, game_id: int) -> bool:
        """Возвращает True, если игра сейчас активно запущена и окно активно (если включена опция track_only_active_window)"""
        with self.lock:
            if game_id not in self.active_sessions:
                return False
            if not self.settings.track_only_active_window:
                return True
            session = self.active_sessions[game_id]
            if not session.get('was_active', False):
                return False
            try:
                active_pid = self._get_active_window_pid()
                if not active_pid:
                    return False
                return self._is_game_active(game_id, session.get('process_pid', 0), active_pid)
            except Exception:
                return session.get('was_active', False)

    def ignore_exe(self, exe_name: str) -> None:
        """Добавляет имя файла в список игнорируемых, чтобы не предлагать его снова, и сохраняет в БД"""
        if not exe_name:
            return
        name_lower = exe_name.lower()
        self._ignored_exes.add(name_lower)
        if self.db and hasattr(self.db, 'add_ignored_process'):
            try:
                self.db.add_ignored_process(name_lower)
            except Exception as e:
                print(f"GameTracker: ошибка сохранения игнорируемого процесса: {e}")

    def unignore_exe(self, exe_name: str) -> None:
        """Удаляет процесс из игнорируемых в БД и памяти, чтобы его снова можно было отслеживать"""
        if not exe_name:
            return
        name_lower = exe_name.lower()
        self._ignored_exes.discard(name_lower)
        self._seen_exes.discard(name_lower)
        self._notified_new_exes.discard(name_lower)
        if self.db and hasattr(self.db, 'remove_ignored_process'):
            try:
                self.db.remove_ignored_process(name_lower)
            except Exception as e:
                print(f"GameTracker: ошибка удаления игнорируемого процесса: {e}")

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        # Фиксируем уже работающие процессы при старте, чтобы не спамить уведомлениями
        if not self._seen_exes:
            try:
                self._seen_exes = {p['name'].lower() for p in self.get_running_processes() if p.get('name')}
            except Exception:
                pass
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
            loop_start = time.monotonic()
            try:
                self._check_processes()
            except Exception as e:
                print(f"Ошибка в цикле мониторинга: {e}")
            elapsed = time.monotonic() - loop_start
            sleep_time = max(0.1, 1.0 - elapsed)
            time.sleep(sleep_time)

    def _get_visible_window_pids(self) -> set:
        """Возвращает множество PID процессов, имеющих хотя бы одно видимое окно верхнего уровня"""
        visible_pids = set()
        try:
            def enum_cb(hwnd, _):
                try:
                    if win32gui.IsWindowVisible(hwnd):
                        rect = win32gui.GetWindowRect(hwnd)
                        if (rect[2] - rect[0] > 0) and (rect[3] - rect[1] > 0):
                            _, found_pid = win32process.GetWindowThreadProcessId(hwnd)
                            visible_pids.add(found_pid)
                except Exception:
                    pass
                return True

            win32gui.EnumWindows(enum_cb, None)
        except Exception:
            pass
        return visible_pids

    def _has_visible_window(self, pids: List[int], visible_pids: Optional[set] = None) -> bool:
        """Проверяет, есть ли среди переданных PID видимое окно верхнего уровня"""
        if visible_pids is not None:
            return any(pid in visible_pids for pid in pids)
        cur_visible = self._get_visible_window_pids()
        return any(pid in cur_visible for pid in pids)

    def _check_processes(self) -> None:
        # Получаем все активные игры из БД
        games = self.db.get_all_games(archived=False)
        games_by_exe = {game['exe_name'].lower(): game for game in games} if games else {}

        # Получаем запущенные процессы
        running_processes = {}
        for proc in psutil.process_iter(['pid', 'name', 'exe']):
            try:
                proc_info = proc.info
                if proc_info['name']:
                    exe_name = proc_info['name'].lower()
                    if exe_name not in running_processes:
                        running_processes[exe_name] = {
                            'pids': [],
                            'exe_path': proc_info['exe']
                        }
                    running_processes[exe_name]['pids'].append(proc_info['pid'])
                    # Обновляем exe_path, если он появился
                    if proc_info['exe'] and not running_processes[exe_name]['exe_path']:
                        running_processes[exe_name]['exe_path'] = proc_info['exe']
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        # Получаем множество PID процессов с видимыми окнами
        visible_window_pids = self._get_visible_window_pids()

        # Обнаружение новых запущенных процессов (.exe), которых ещё нет в библиотеке
        if self.settings.notify_new_game:
            try:
                all_games = self.db.get_all_games(archived=False) + self.db.get_all_games(archived=True)
                library_exes = {g['exe_name'].lower() for g in all_games}
            except Exception:
                library_exes = set(games_by_exe.keys())

            for exe_name, proc_data in running_processes.items():
                if exe_name in self._seen_exes or exe_name in self._ignored_exes:
                    continue

                # Игнорируем процессы, которые уже есть в библиотеке
                if exe_name in library_exes:
                    self._seen_exes.add(exe_name)
                    continue

                # Игнорируем системные процессы и файлы из системных каталогов
                if is_system_process(exe_name, proc_data.get('exe_path')):
                    self._seen_exes.add(exe_name)
                    continue

                # Отправляем уведомление только для процессов с видимым окном верхнего уровня
                pids = proc_data.get('pids', [])
                if self._has_visible_window(pids, visible_window_pids):
                    self._seen_exes.add(exe_name)
                    if exe_name not in self._notified_new_exes:
                        self._notified_new_exes.add(exe_name)
                        clean_name = os.path.splitext(exe_name)[0].replace('_', ' ').replace('-', ' ').title()
                        self.notify("GameTimeTracker", f"🎮 Обнаружена игра: {clean_name} ({exe_name})! Нажмите для добавления")
                        if self.on_game_detected:
                            try:
                                self.on_game_detected(exe_name, proc_data.get('exe_path'))
                            except Exception as e:
                                print(f"GameTracker: ошибка в on_game_detected: {e}")
                else:
                    # Фоновый процесс без окна (или окно ещё не создано)
                    attempts = self._unwindowed_attempts.get(exe_name, 0) + 1
                    self._unwindowed_attempts[exe_name] = attempts
                    if attempts >= 10:
                        self._seen_exes.add(exe_name)
        else:
            for exe_name in running_processes.keys():
                self._seen_exes.add(exe_name)

        # Игры, которые сейчас запущены (выбираем процесс с окном, если есть)
        tracked_games = {}
        for exe_name, game_info in games_by_exe.items():
            if exe_name not in running_processes:
                continue

            pids = running_processes[exe_name]['pids']

            # Выбираем PID, у которого есть видимое окно
            selected_pid = None
            for pid in pids:
                if pid in visible_window_pids:
                    selected_pid = pid
                    break
            if selected_pid is None and pids:
                selected_pid = pids[0]
            if selected_pid is not None:
                tracked_games[game_info['id']] = {
                    'game_info': game_info,
                    'pid': selected_pid,
                    'pids': pids,
                    'exe_path': running_processes[exe_name]['exe_path']
                }

        # Получаем активное окно
        active_pid = self._get_active_window_pid()
        now = time.monotonic()

        with self.lock:
            # 1. Обновляем существующие сессии
            for game_id, session_info in list(self.active_sessions.items()):
                if game_id not in tracked_games:
                    # Игра больше не запущена -> завершаем сессию
                    self._close_session(game_id, session_info, force=False)
                    continue

                # Игра всё ещё запущена
                is_active = self._is_game_active(
                    game_id,
                    tracked_games[game_id]['pid'],
                    active_pid,
                    tracked_games[game_id].get('pids')
                )

                last_tick = session_info.get('last_tick_time', now)
                delta = now - last_tick
                session_info['last_tick_time'] = now

                # Защита от аномалий (сон ПК или зависание)
                if delta < 0:
                    delta = 0.0
                elif delta > 5.0:
                    delta = 1.0

                if is_active:
                    if not session_info.get('was_active', False):
                        # Первый шаг активности после неактивности
                        session_info['was_active'] = True
                        delta = min(delta, 1.0)

                    accumulated = session_info.get('accumulated_seconds', float(session_info['current_seconds']))
                    accumulated += delta
                    session_info['accumulated_seconds'] = accumulated
                    session_info['current_seconds'] = int(accumulated)

                    # Проверка напоминания о долгой сессии
                    if self.settings.notify_long_session:
                        limit_seconds = self.settings.long_session_minutes * 60
                        if session_info['current_seconds'] >= limit_seconds and not session_info.get('long_session_notified', False):
                            session_info['long_session_notified'] = True
                            minutes = self.settings.long_session_minutes
                            self.notify(
                                "GameTimeTracker",
                                f"Вы играете уже {minutes} минут! Пора сделать перерыв"
                            )

                    initial_sec = session_info.setdefault('initial_total_seconds', 0)
                    total_seconds = initial_sec + session_info['current_seconds']
                    if self.on_tick:
                        self.on_tick(game_id, total_seconds, True)

                    # Периодический сброс прогресса в БД (раз в flush_interval секунд)
                    unflushed = session_info['current_seconds'] - session_info.get('last_flushed_seconds', 0)
                    if unflushed >= self.flush_interval:
                        self._flush_session(game_id, session_info)
                else:
                    was_active = session_info.get('was_active', False)
                    session_info['was_active'] = False
                    if was_active and self.on_tick:
                        initial_sec = session_info.setdefault('initial_total_seconds', 0)
                        total_seconds = initial_sec + session_info['current_seconds']
                        self.on_tick(game_id, total_seconds, False)

            # 2. Создаём новые сессии для вновь запущенных игр
            for game_id, proc_info in tracked_games.items():
                if game_id not in self.active_sessions:
                    # Создаём сессию сразу при запуске процесса, даже если не активен
                    # Чтобы потом при активации уже была сессия
                    session_id = self.db.start_session(game_id)
                    # Обновляем last_launched (без добавления секунд)
                    self.db.update_game_time(game_id, 0)
                    initial_sec = proc_info['game_info'].get('total_seconds', 0) if proc_info.get('game_info') else 0
                    self.active_sessions[game_id] = {
                        'session_id': session_id,
                        'current_seconds': 0,
                        'accumulated_seconds': 0.0,
                        'last_tick_time': now,
                        'last_flushed_seconds': 0,
                        'initial_total_seconds': initial_sec,
                        'process_pid': proc_info['pid'],
                        'was_active': False,
                        'long_session_notified': False
                    }
                    print(f"GameTracker: создана сессия {session_id} для игры ID {game_id} (PID {proc_info['pid']})")

    def _get_active_window_pid(self) -> Optional[int]:
        try:
            hwnd = win32gui.GetForegroundWindow()
            if not hwnd:
                return None
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            return pid
        except Exception:
            return None

    def _is_game_active(
        self,
        game_id: int,
        game_pid: int,
        active_pid: Optional[int],
        game_pids: Optional[List[int]] = None
    ) -> bool:
        track_only = self.settings.track_only_active_window
        if not track_only:
            return True

        if active_pid is None:
            return False

        # Прямое совпадение PID процесса игры
        if game_pid == active_pid:
            return True

        if game_pids and active_pid in game_pids:
            return True

        # Проверяем, является ли active_pid дочерним процессом игры
        try:
            proc = psutil.Process(game_pid)
            child_pids = {child.pid for child in proc.children(recursive=True)}
            if active_pid in child_pids:
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

        # Проверяем, не является ли game_pid родителем active_pid (например, при лаунчере)
        try:
            active_proc = psutil.Process(active_pid)
            if active_proc.ppid() == game_pid:
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

        return False

    def _flush_session(self, game_id: int, session_info: Dict[str, Any]) -> None:
        """Периодический сброс накопленного прогресса активной сессии в БД"""
        unflushed = session_info['current_seconds'] - session_info.get('last_flushed_seconds', 0)
        if unflushed > 0:
            try:
                self.db.update_game_time(game_id, unflushed)
                self.db.update_session_duration(session_info['session_id'], session_info['current_seconds'])
                session_info['last_flushed_seconds'] = session_info['current_seconds']
                print(f"GameTracker: сброс прогресса сессии {session_info['session_id']} (игра ID {game_id}): +{unflushed} сек, всего {session_info['current_seconds']} сек")
            except Exception as e:
                print(f"GameTracker: ошибка при периодическом сбросе прогресса: {e}")

    def _close_session(self, game_id: int, session_info: Dict[str, Any], force: bool = False) -> None:
        session_id = session_info['session_id']
        seconds = session_info['current_seconds']
        last_flushed = session_info.get('last_flushed_seconds', 0)
        unflushed = seconds - last_flushed

        try:
            if unflushed > 0:
                self.db.update_game_time(game_id, unflushed)
                session_info['last_flushed_seconds'] = seconds
            self.db.end_session(session_id, seconds)
            print(f"GameTracker: завершена сессия {session_id} для игры ID {game_id}, секунд: {seconds}")
        except Exception as e:
            print(f"GameTracker: ошибка при сохранении завершения сессии {session_id}: {e}")

        # После завершения сессии нужно обновить UI, чтобы статус стал "не играю"
        if self.on_tick:
            initial_sec = session_info.get('initial_total_seconds', 0)
            total_seconds = initial_sec + seconds
            try:
                self.on_tick(game_id, total_seconds, False)
            except Exception as e:
                print(f"GameTracker: ошибка в on_tick при завершении сессии: {e}")

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

        large_icons, small_icons = [], []
        hdc_raw = None
        hdc = None
        hdc_mem = None
        hbmp = None
        old_bmp = None

        try:
            large_icons, small_icons = win32gui.ExtractIconEx(exe_path, 0)
            if large_icons and large_icons[0]:
                hicon = large_icons[0]
            elif small_icons and small_icons[0]:
                hicon = small_icons[0]
            else:
                return None

            hdc_raw = win32gui.GetDC(0)
            if not hdc_raw:
                return None

            hdc = win32ui.CreateDCFromHandle(hdc_raw)
            hbmp = win32ui.CreateBitmap()
            hbmp.CreateCompatibleBitmap(hdc, size, size)
            hdc_mem = hdc.CreateCompatibleDC()
            old_bmp = hdc_mem.SelectObject(hbmp)

            win32gui.DrawIconEx(hdc_mem.GetSafeHdc(), 0, 0, hicon, size, size, 0, None, win32con.DI_NORMAL)

            bmp_bits = hbmp.GetBitmapBits(True)
            img = Image.frombuffer('RGBA', (size, size), bmp_bits, 'raw', 'BGRA', 0, 1)

            return img
        except Exception as e:
            print(f"Ошибка извлечения иконки из {exe_path}: {e}")
            return None
        finally:
            for h in large_icons + small_icons:
                try:
                    if h:
                        win32gui.DestroyIcon(h)
                except Exception:
                    pass

            if hdc_mem is not None:
                try:
                    if old_bmp is not None:
                        hdc_mem.SelectObject(old_bmp)
                    hdc_mem.DeleteDC()
                except Exception:
                    pass

            if hbmp is not None:
                try:
                    win32gui.DeleteObject(hbmp.GetHandle())
                except Exception:
                    pass

            if hdc is not None:
                try:
                    hdc.DeleteDC()
                except Exception:
                    pass

            if hdc_raw is not None:
                try:
                    win32gui.ReleaseDC(0, hdc_raw)
                except Exception:
                    pass