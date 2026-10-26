GameTimeTracker v1.4.0 — релизная сборка для Windows
=====================================================

Файл:      GameTimeTracker.exe
Версия:    1.4.0
Платформа: Windows x86-64 (PE32+ GUI, без консольного окна)
Размер:    45.3 МБ (47 523 726 байт)
SHA-256:   d2d9907b5330c344c370c582f4a611a19eb56e9dd3c02b3109d46543bf398292
Собрано:   GitHub Actions, windows-latest, Python 3.11, PyInstaller (onefile)
           коммит 5059c8c, тег v1.4.0, спецификация GameTimeTracker.spec

Как запустить
-------------
1. Скопируйте GameTimeTracker.exe в любую папку (например, сюда же).
2. Двойной клик — приложение запустится и уйдёт в системный трей.
   Установка не требуется, Python не нужен.
3. Данные (база, журналы, бэкапы) создаются рядом с exe в папке data\:
   data\gametracker.db, data\logs\, data\backups\.

Важно про SmartScreen
---------------------
Файл не подписан сертификатом code signing, поэтому Windows SmartScreen может
показать «Windows защитила ваш компьютер» → «Подробнее» → «Всё равно запустить».
Это ожидаемо для неподписанных сборок.

Если что-то не запускается
--------------------------
При старте пишется журнал: data\logs\gametimetracker.log — пришлите его,
чтобы понять причину (у windowed-сборки нет консоли).

Откуда взять файл заново
------------------------
- GitHub Releases: https://github.com/FrUsTaY/Game-Time-Tracker/releases/latest
- Служебная ветка сборки: https://github.com/FrUsTaY/Game-Time-Tracker/tree/build/win-exe (.exe/GameTimeTracker.exe)
- Собрать самому на Windows: pip install -r requirements-dev.txt && python build.py
  (результат — dist\GameTimeTracker.exe; PyInstaller не умеет кросс-компиляцию,
  поэтому с Linux/macOS Windows-бинарник не собрать)
