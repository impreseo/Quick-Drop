@echo off
setlocal EnableExtensions
cd /d "%~dp0\.."

echo.
echo ========================================
echo   QuickDrop 2.0.0 - Windows Release Build
echo ========================================
echo.

where py >nul 2>nul
if %errorlevel%==0 (
  set "PY=py"
) else (
  where python >nul 2>nul
  if errorlevel 1 (
    echo ERROR: Python 3.11+ was not found.
    echo Install Python, then run this script again.
    exit /b 1
  )
  set "PY=python"
)

if exist .buildenv rmdir /s /q .buildenv
%PY% -m venv .buildenv
if errorlevel 1 exit /b 1
call .buildenv\Scripts\activate.bat
python -m pip install --upgrade pip
if errorlevel 1 exit /b 1
python -m pip install ".[build]"
if errorlevel 1 exit /b 1

echo.
echo [1/3] Running tests...
python -m unittest discover -s tests -v
if errorlevel 1 (
  echo ERROR: Tests failed. Build stopped.
  exit /b 1
)

echo.
echo [2/3] Building QuickDrop application...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist QuickDrop.spec del /q QuickDrop.spec
python -m PyInstaller ^
  --noconfirm ^
  --clean ^
  --windowed ^
  --name QuickDrop ^
  --icon src\quickdrop\assets\quickdrop.ico ^
  --version-file installer\version_info.txt ^
  --paths src ^
  --collect-data quickdrop ^
  --collect-all tkinterdnd2 ^
  src\quickdrop\__main__.py
if errorlevel 1 exit /b 1

if not exist dist\QuickDrop\QuickDrop.exe (
  echo ERROR: QuickDrop.exe was not created.
  exit /b 1
)

echo.
echo [3/3] Building Windows installer...
set "ISCC="
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not defined ISCC (
  echo ERROR: Inno Setup 6 was not found.
  echo Install Inno Setup 6, then run this script again.
  exit /b 1
)

if not exist release mkdir release
if exist release\QuickDrop-Setup-2.0.0.exe del /q release\QuickDrop-Setup-2.0.0.exe
"%ISCC%" installer\QuickDrop.iss
if errorlevel 1 exit /b 1

if not exist release\QuickDrop-Setup-2.0.0.exe (
  echo ERROR: Installer output was not created.
  exit /b 1
)

echo.
echo SUCCESS
for %%F in (release\QuickDrop-Setup-2.0.0.exe) do echo Installer: %%~fF
exit /b 0
