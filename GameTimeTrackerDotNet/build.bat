@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
echo ========================================================
echo Сборка релизной версии GameTimeTracker (C# / .NET 8)
echo ========================================================
echo.

:: Переходим в папку с .csproj, так как dotnet publish работает надежнее с файлом проекта
cd GameTimeTracker

dotnet publish GameTimeTracker.csproj -c Release -r win-x64 --self-contained true -p:PublishSingleFile=true -p:IncludeNativeLibrariesForSelfExtract=true -o "..\Release"

echo.
echo ========================================================
echo Сборка завершена! 
echo Итоговый .exe файл находится в папке: GameTimeTrackerDotNet\Release
echo ========================================================
pause