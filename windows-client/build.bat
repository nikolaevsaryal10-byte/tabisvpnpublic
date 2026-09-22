@echo off
setlocal enabledelayedexpansion

echo ============================================================
echo  TABIS VPN WINDOWS BUILD PIPELINE
echo ============================================================

:: ---- Check Python ----
where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found in PATH. Please install Python 3.11+
    pause & exit /b 1
)

:: ---- Install/Update PyInstaller ----
echo [1/4] Checking PyInstaller...
python -m pip install --quiet --upgrade pyinstaller pillow pystray pywebview requests
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies.
    pause & exit /b 1
)

:: ---- Build EXE with PyInstaller ----
echo [2/4] Building TabisVPN.exe with PyInstaller...
python -m PyInstaller --clean --noconfirm TabisVPN.spec
if errorlevel 1 (
    echo [ERROR] PyInstaller build failed.
    pause & exit /b 1
)
echo [OK] EXE built: dist\TabisVPN.exe

:: ---- Find or Download Inno Setup ----
echo [3/4] Checking Inno Setup...
set ISCC=
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" (
    set ISCC=C:\Program Files (x86)\Inno Setup 6\ISCC.exe
) else if exist "C:\Program Files\Inno Setup 6\ISCC.exe" (
    set ISCC=C:\Program Files\Inno Setup 6\ISCC.exe
) else if exist "%~dp0tools\ISCC.exe" (
    set ISCC=%~dp0tools\ISCC.exe
)

if "!ISCC!"=="" (
    echo [INFO] Inno Setup not found. Downloading portable version...
    mkdir tools 2>nul
    powershell -Command "Invoke-WebRequest -Uri 'https://jrsoftware.org/download.php/is.exe' -OutFile 'tools\inno_setup_installer.exe' -UseBasicParsing"
    if errorlevel 1 (
        echo [WARN] Could not download Inno Setup. Skipping setup.exe build.
        echo [INFO] Install Inno Setup 6 from https://jrsoftware.org/isinfo.php and re-run.
        goto :copy_output
    )
    echo [INFO] Please run tools\inno_setup_installer.exe to install Inno Setup 6, then re-run this script.
    start "" "tools\inno_setup_installer.exe"
    goto :copy_output
)

:: ---- Build setup.exe ----
echo Building TabisVPN_Setup.exe...
mkdir ..\release 2>nul
"!ISCC!" TabisVPN_Setup.iss
if errorlevel 1 (
    echo [WARN] Inno Setup build failed. Check TabisVPN_Setup.iss
) else (
    echo [OK] Installer built: ..\release\TabisVPN_Setup.exe
)

:copy_output
:: ---- Copy to tabisvpnpublic ----
echo [4/4] Copying to tabisvpnpublic...
set PUBLIC_DIR=%~dp0..\..\tabisvpnpublic

if exist "dist\TabisVPN.exe" (
    copy /Y "dist\TabisVPN.exe" "%PUBLIC_DIR%\TabisVPN.exe"
    echo [OK] Copied TabisVPN.exe to tabisvpnpublic
)

if exist "..\release\TabisVPN_Setup.exe" (
    copy /Y "..\release\TabisVPN_Setup.exe" "%PUBLIC_DIR%\TabisVPN_Setup.exe"
    echo [OK] Copied TabisVPN_Setup.exe to tabisvpnpublic
)

echo.
echo ============================================================
echo  BUILD COMPLETE
echo  TabisVPN.exe    : dist\TabisVPN.exe
echo  TabisVPN_Setup  : ..\release\TabisVPN_Setup.exe
echo  Published to    : %PUBLIC_DIR%
echo ============================================================
pause
