@echo off
if exist "%~dp0GameTimeTracker.exe" (
    start "" "%~dp0GameTimeTracker.exe"
) else if exist "%~dp0dist\GameTimeTracker.exe" (
    start "" "%~dp0dist\GameTimeTracker.exe"
) else (
    echo GameTimeTracker.exe не найден!
    pause
)
exit
