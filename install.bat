@echo off
setlocal enabledelayedexpansion

echo ================================================================
echo   Sverchok Spotlight Suite - Installer for Windows
echo   Target: Blender 4.2 LTS + Sverchok v1.4.0+
echo ================================================================
echo.

REM 1. Detect Blender 4.2 executable
set "BLENDER_BIN="

if exist "C:\Program Files\Blender Foundation\Blender 4.2\blender.exe" (
    set "BLENDER_BIN=C:\Program Files\Blender Foundation\Blender 4.2\blender.exe"
    goto :BLENDER_FOUND
)
if exist "%LOCALAPPDATA%\Programs\Blender Foundation\Blender 4.2\blender.exe" (
    set "BLENDER_BIN=%LOCALAPPDATA%\Programs\Blender Foundation\Blender 4.2\blender.exe"
    goto :BLENDER_FOUND
)
if exist "C:\Program Files\Blender Foundation\Blender\blender.exe" (
    set "BLENDER_BIN=C:\Program Files\Blender Foundation\Blender\blender.exe"
    goto :BLENDER_FOUND
)

REM Check PATH
where blender.exe >nul 2>nul
if %errorlevel% equ 0 (
    set "BLENDER_BIN=blender"
    goto :BLENDER_FOUND
)

REM If not found, attempt install via winget
echo [!] Blender 4.2 was not found on your system.
echo [*] Checking Windows Package Manager winget...
where winget.exe >nul 2>nul
if %errorlevel% equ 0 (
    echo [*] Installing Blender 4.2 via winget...
    winget install --id BlenderFoundation.Blender --exact -v 4.2.0 --accept-package-agreements --accept-source-agreements
    if exist "C:\Program Files\Blender Foundation\Blender 4.2\blender.exe" (
        set "BLENDER_BIN=C:\Program Files\Blender Foundation\Blender 4.2\blender.exe"
        goto :BLENDER_FOUND
    )
)

REM If still not found, download portable zip
echo [*] Downloading official Blender 4.2 portable package...
set "PORTABLE_DIR=%USERPROFILE%\Blender42_Portable"
if not exist "%PORTABLE_DIR%" mkdir "%PORTABLE_DIR%"
curl.exe -L -o "%TEMP%\blender-4.2.0-windows-x64.zip" "https://download.blender.org/release/Blender4.2/blender-4.2.0-windows-x64.zip"
echo [*] Extracting Blender 4.2 to %PORTABLE_DIR%...
tar.exe -xf "%TEMP%\blender-4.2.0-windows-x64.zip" -C "%PORTABLE_DIR%"
del "%TEMP%\blender-4.2.0-windows-x64.zip" 2>nul
for /d %%d in ("%PORTABLE_DIR%\blender-4.2*") do (
    if exist "%%d\blender.exe" (
        set "BLENDER_BIN=%%d\blender.exe"
        goto :BLENDER_FOUND
    )
)

if "%BLENDER_BIN%"=="" (
    echo [ERROR] Could not find or install Blender 4.2.
    echo Please install Blender 4.2 from https://www.blender.org/download/ and rerun this script.
    if "%CI%"=="" pause
    exit /b 1
)

:BLENDER_FOUND
echo [OK] Using Blender executable: "%BLENDER_BIN%"
echo.

REM 2. Addons Directory for Blender 4.2
set "ADDONS_DIR=%APPDATA%\Blender Foundation\Blender\4.2\scripts\addons"
echo [*] Addons Directory: "%ADDONS_DIR%"
if not exist "%ADDONS_DIR%" mkdir "%ADDONS_DIR%"

REM 3. Install Sverchok v1.4.0+
if exist "%ADDONS_DIR%\sverchok\__init__.py" (
    echo [OK] Sverchok addon already installed in "%ADDONS_DIR%\sverchok".
    goto :SVERCHOK_READY
)

echo [*] Installing Sverchok v1.4.0+...
where git.exe >nul 2>nul
if %errorlevel% equ 0 (
    echo [*] Cloning Sverchok repository via git...
    git clone --depth 1 https://github.com/nortikin/sverchok.git "%ADDONS_DIR%\sverchok"
    goto :VERIFY_SVERCHOK
)

echo [*] Downloading Sverchok master zip...
curl.exe -L -o "%TEMP%\sverchok.zip" "https://github.com/nortikin/sverchok/archive/refs/heads/master.zip"
echo [*] Extracting Sverchok...
tar.exe -xf "%TEMP%\sverchok.zip" -C "%ADDONS_DIR%"
if exist "%ADDONS_DIR%\sverchok-master" (
    ren "%ADDONS_DIR%\sverchok-master" "sverchok"
)
del "%TEMP%\sverchok.zip" 2>nul

:VERIFY_SVERCHOK
if exist "%ADDONS_DIR%\sverchok\__init__.py" (
    echo [OK] Sverchok installed successfully!
) else (
    echo [ERROR] Failed to install Sverchok. Please check your internet connection.
    if "%CI%"=="" pause
    exit /b 1
)

:SVERCHOK_READY
echo.

REM 4. Install Sverchok Spotlight
set "SCRIPT_DIR=%~dp0"
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"

set "TARGET_SPOTLIGHT=%ADDONS_DIR%\sverchok_spotlight"
echo [*] Installing Sverchok Spotlight to: "%TARGET_SPOTLIGHT%"

if /i "%SCRIPT_DIR%"=="%TARGET_SPOTLIGHT%" (
    echo [OK] Already located in Blender addons directory.
) else (
    echo [*] Synchronizing Spotlight addon files...
    robocopy "%SCRIPT_DIR%" "%TARGET_SPOTLIGHT%" /E /XD .git __pycache__ .vscode /XF *.zip *.log /NDL /NFL /NJH /NJS
    echo [OK] Sverchok Spotlight copied to Blender addons directory.
)
echo.

REM 5. Enable Addons in Blender 4.2
echo [*] Enabling Sverchok and Sverchok Spotlight in Blender 4.2...
"%BLENDER_BIN%" -b --python-expr "import bpy; bpy.ops.preferences.addon_enable(module='sverchok'); bpy.ops.preferences.addon_enable(module='sverchok_spotlight'); bpy.ops.wm.save_userpref(); print('\n[VERIFIED] Sverchok and Sverchok Spotlight successfully enabled in Blender user preferences!')"

REM 6. Run Verification Test Suite
echo.
echo [*] Running full test verification suite...
"%BLENDER_BIN%" -b --python "%TARGET_SPOTLIGHT%\test_spotlight_v2.py"
if %errorlevel% equ 0 (
    echo.
    echo ================================================================
    echo   INSTALLATION AND VERIFICATION COMPLETED SUCCESSFULLY [100%%]!
    echo   Launch Blender 4.2 to use the Spotlight node suite in Sverchok.
    echo ================================================================
) else (
    echo.
    echo [!] Addons installed, but one or more verification tests raised a warning.
)

echo.
if "%CI%"=="" pause
