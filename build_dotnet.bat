@echo off
chcp 65001 >nul
echo ========================================================
echo Сборка релизной версии GameTimeTracker (C# / .NET 8)
echo ========================================================
echo.

:: Переходим в папку с проектом
cd GameTimeTrackerDotNet\GameTimeTracker

:: Выполняем публикацию проекта
:: -c Release : собираем в режиме релиза (с оптимизацией)
:: -r win-x64 : целевая платформа Windows 64-bit
:: --self-contained true : включает среду .NET в сборку (не требует установки .NET на ПК)
:: -p:PublishSingleFile=true : упаковывает всё в один .exe файл
:: -p:IncludeNativeLibrariesForSelfExtract=true : включает нативные библиотеки (SQLite) внутрь .exe
:: -o ... : папка для вывода готового приложения
dotnet publish -c Release -r win-x64 --self-contained true -p:PublishSingleFile=true -p:IncludeNativeLibrariesForSelfExtract=true -o ..\..\Release_CSharp

echo.
echo ========================================================
echo Сборка завершена! 
echo Итоговый .exe файл находится в папке: Release_CSharp
echo ========================================================
pause
