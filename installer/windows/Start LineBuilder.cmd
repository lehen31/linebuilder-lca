@echo off
rem Starts LineBuilder on this PC and opens it in the browser. Closing this window stops it.
chcp 65001 >nul
cd /d "%~dp0"
title LineBuilder
if "%PORT%"=="" set PORT=5050
set PYTHONWARNINGS=ignore

if not exist ".venv\Scripts\python.exe" (
  echo Run "Install LineBuilder" first.
  pause
  exit /b 1
)
rem an existing Activity Browser 2 project (brightway-folder.txt), else the own project in the subfolder "brightway":
rem check that the chosen project is still there and still Brightway2
".venv\Scripts\python.exe" setup_ecoinvent.py --check
if not exist "linebuilder_config.json" (
  echo LineBuilder needs ecoinvent 3.12 cutoff first.
  ".venv\Scripts\python.exe" setup_ecoinvent.py
  if not exist "linebuilder_config.json" (
    echo.
    echo The Brightway project is not set up, so LineBuilder cannot start.
    pause
    exit /b 1
  )
  echo.
)
if exist "brightway-folder.txt" (
  set /p BRIGHTWAY2_DIR=<"brightway-folder.txt"
) else (
  set "BRIGHTWAY2_DIR=%~dp0brightway"
  if not exist "%~dp0brightway" mkdir "%~dp0brightway"
)
netstat -ano | findstr /r /c:"127.0.0.1:%PORT% .*LISTENING" >nul
if not errorlevel 1 (
  echo Port %PORT% is already in use ^(LineBuilder may already be running^): http://127.0.0.1:%PORT%
  start "" "http://127.0.0.1:%PORT%"
  timeout /t 5 >nul
  exit /b 0
)

echo LineBuilder: http://127.0.0.1:%PORT%
echo Keep this window open. Closing it stops LineBuilder.
echo The first calculation reads ecoinvent and takes a minute.
start "" /b cmd /c "timeout /t 3 >nul & start "" http://127.0.0.1:%PORT%"
".venv\Scripts\python.exe" app.py
pause
