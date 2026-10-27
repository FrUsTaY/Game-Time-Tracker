@echo off
setlocal
cd /d "%~dp0"

echo ========================================================
echo Building Release version of GameTimeTracker (C# / .NET 8)
echo ========================================================
echo.

cd GameTimeTracker
dotnet publish GameTimeTracker.csproj -c Release -r win-x64 --self-contained true -p:PublishSingleFile=true -p:IncludeNativeLibrariesForSelfExtract=true -o "..\Release"

echo.
echo ========================================================
echo Build complete!
echo The resulting .exe file is located in the folder: GameTimeTrackerDotNet\Release
echo ========================================================
pause
