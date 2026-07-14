"""
build.py — скрипт для сборки GameTimeTracker в один .exe файл.
Запускать после всех изменений.
"""

import os
import shutil
import subprocess
import sys

def clean_build():
    """Удаляет старые папки сборки."""
    dirs_to_remove = ['build', 'dist', '__pycache__']
    for dir_name in dirs_to_remove:
        if os.path.exists(dir_name):
            shutil.rmtree(dir_name)
            print(f"Удалена папка {dir_name}")
    # Удаляем файл .spec
    spec_file = "GameTimeTracker.spec"
    if os.path.exists(spec_file):
        os.remove(spec_file)
        print(f"Удалён {spec_file}")

def run_pyinstaller():
    """Запускает PyInstaller с нужными параметрами."""
    # Проверяем наличие иконок
    if not os.path.exists("assets/app.ico"):
        print("Иконка assets/app.ico не найдена. Запустите generate_icon.py")
        sys.exit(1)
    if not os.path.exists("assets/icon.png"):
        print("Иконка assets/icon.png не найдена. Запустите generate_icon.py")
        sys.exit(1)

    # Команда сборки
    cmd = [
        "pyinstaller",
        "--onefile",                  # один exe файл
        "--windowed",                 # без консоли (оконное приложение)
        f"--icon={os.path.abspath('assets/app.ico')}",     # иконка для exe
        "--name=GameTimeTracker",     # имя выходного файла
        "--add-data=assets;assets",   # папка assets
        "--add-data=ui;ui",           # папка ui (все вкладки)
        "--hidden-import=win32gui",   # явные импорты для pyinstaller
        "--hidden-import=win32process",
        "--hidden-import=win32ui",
        "--hidden-import=win32con",
        "--hidden-import=psutil",
        "--hidden-import=pystray",
        "--hidden-import=matplotlib",
        "--hidden-import=customtkinter",
        "--hidden-import=PIL",
        "main.py"
    ]

    print("Запуск PyInstaller...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print("Ошибка сборки:")
        print(result.stderr)
        sys.exit(1)
    else:
        print("Сборка завершена успешно!")
        print(f"Исполняемый файл: {os.path.abspath('dist/GameTimeTracker.exe')}")

def create_launcher_bat():
    """Создаёт bat-файл для удобного запуска exe (опционально)."""
    bat_content = '@echo off\nstart "" "%~dp0dist\\GameTimeTracker.exe"\nexit'
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
    run_pyinstaller()
    create_launcher_bat()
    print("\nГотово! Файл GameTimeTracker.exe находится в папке dist.")