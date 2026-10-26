"""
build.py — скрипт для сборки GameTimeTracker в один .exe файл.
Запускать после всех изменений.
"""

import os
import shutil
import subprocess
import sys


def pyinstaller_command(*args):
    """
    Возвращает команду запуска PyInstaller через текущий интерпретатор.

    `python -m PyInstaller` надёжнее, чем просто `pyinstaller`: работает и в
    venv без активированного Scripts/PATH, и на CI-раннерах Windows.
    """
    return [sys.executable, "-m", "PyInstaller", *args]


def ensure_pyinstaller():
    """Проверяет, что PyInstaller установлен, иначе подсказывает команду."""
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("PyInstaller не установлен. Установите его: pip install -r requirements-dev.txt")
        sys.exit(1)


def clean_build():
    """Удаляет старые папки сборки."""
    dirs_to_remove = ['build', 'dist', '__pycache__']
    for dir_name in dirs_to_remove:
        if os.path.exists(dir_name):
            shutil.rmtree(dir_name)
            print(f"Удалена папка {dir_name}")

def run_pyinstaller_from_spec():
    """
    Собирает .exe по GameTimeTracker.spec — единому источнику настроек сборки.

    Раньше параметры дублировались в build.py и в .spec, из-за чего они
    расходились (например, забытые hidden-import после добавления модулей).
    """
    spec_path = "GameTimeTracker.spec"
    if not os.path.exists(spec_path):
        print("Файл GameTimeTracker.spec не найден, используется резервная сборка")
        return run_pyinstaller()

    ensure_pyinstaller()
    print("Запуск PyInstaller по спецификации GameTimeTracker.spec...")
    # Вывод не перехватываем: при ошибке нужен полный лог PyInstaller
    result = subprocess.run(pyinstaller_command("--noconfirm", "--clean", spec_path))
    if result.returncode != 0:
        print(f"Ошибка сборки: PyInstaller завершился с кодом {result.returncode}")
        sys.exit(1)
    print("Сборка завершена успешно!")
    print(f"Исполняемый файл: {os.path.abspath('dist/GameTimeTracker.exe')}")


def run_pyinstaller():
    """Резервная сборка: PyInstaller с явными параметрами командной строки."""
    # Проверяем наличие иконок
    if not os.path.exists("assets/app.ico"):
        print("Иконка assets/app.ico не найдена. Запустите generate_icon.py")
        sys.exit(1)
    if not os.path.exists("assets/icon.png"):
        print("Иконка assets/icon.png не найдена. Запустите generate_icon.py")
        sys.exit(1)

    ensure_pyinstaller()

    # Команда сборки
    cmd = pyinstaller_command(
        "--noconfirm",
        "--onefile",                  # один exe файл
        "--windowed",                 # без консоли (оконное приложение)
        "--icon=assets/app.ico",      # иконка для exe
        "--name=GameTimeTracker",     # имя выходного файла
        "--add-data=assets;assets",   # папка assets
        "--add-data=ui;ui",           # папка ui (все вкладки)
        "--collect-all=customtkinter",# все ресурсы и темы customtkinter
        "--hidden-import=win32gui",   # явные импорты для pyinstaller
        "--hidden-import=win32process",
        "--hidden-import=win32ui",
        "--hidden-import=win32con",
        "--hidden-import=psutil",
        "--hidden-import=pystray",
        "--hidden-import=matplotlib",
        "--hidden-import=customtkinter",
        "--hidden-import=PIL",
        "main.py",
    )

    print("Запуск PyInstaller...")
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print(f"Ошибка сборки: PyInstaller завершился с кодом {result.returncode}")
        sys.exit(1)
    print("Сборка завершена успешно!")
    print(f"Исполняемый файл: {os.path.abspath('dist/GameTimeTracker.exe')}")

def create_launcher_bat():
    """Создаёт bat-файл для удобного запуска exe (опционально)."""
    bat_content = (
        '@echo off\n'
        'if exist "%~dp0GameTimeTracker.exe" (\n'
        '    start "" "%~dp0GameTimeTracker.exe"\n'
        ') else if exist "%~dp0dist\\GameTimeTracker.exe" (\n'
        '    start "" "%~dp0dist\\GameTimeTracker.exe"\n'
        ') else (\n'
        '    echo GameTimeTracker.exe не найден!\n'
        '    pause\n'
        ')\n'
        'exit\n'
    )
    with open("run_game_tracker.bat", "w", encoding="utf-8") as f:
        f.write(bat_content)
    print("Создан run_game_tracker.bat для быстрого запуска.")

if __name__ == "__main__":
    print("=== Сборка GameTimeTracker в .exe ===\n")
    clean_build()
    # Проверяем наличие иконок, но не генерируем (используем свои)
    if not os.path.exists("assets/app.ico") or not os.path.exists("assets/icon.png"):
        print("Ошибка: отсутствуют assets/app.ico или assets/icon.png. Поместите свои иконки в папку assets.")
        sys.exit(1)
    else:
        print("Используются существующие иконки из папки assets")
    run_pyinstaller_from_spec()
    create_launcher_bat()
    print("\nГотово! Файл GameTimeTracker.exe находится в папке dist.")
