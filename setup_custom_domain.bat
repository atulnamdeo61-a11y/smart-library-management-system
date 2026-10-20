@echo off
:: ====================================================================
:: Setup Custom Domain for Smart Library Management System
:: Maps 'smartlibrary.local' -> 127.0.0.1 in Windows hosts file
:: ====================================================================

title Setup Custom Domain - Smart Library
echo ====================================================================
echo   CONFIGURING CUSTOM DOMAIN: http://smartlibrary.local
echo ====================================================================
echo.

:: Check for Administrative privileges
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [!] Requesting Administrator privileges to update hosts file...
    powershell -Command "Start-Process cmd -ArgumentList '/c \"%~f0\"' -Verb RunAs"
    exit /b
)

set "HOSTS_FILE=%WINDIR%\System32\drivers\etc\hosts"

:: Check if already exists in hosts
findstr /I "smartlibrary.local" "%HOSTS_FILE%" >nul 2>&1
if %errorLevel% equ 0 (
    echo [*] Domain 'smartlibrary.local' is already mapped in hosts file.
) else (
    echo. >> "%HOSTS_FILE%"
    echo 127.0.0.1 smartlibrary.local >> "%HOSTS_FILE%"
    echo 127.0.0.1 www.smartlibrary.local >> "%HOSTS_FILE%"
    echo [OK] Added '127.0.0.1 smartlibrary.local' to %HOSTS_FILE%
)

echo.
echo [SUCCESS] You can now access your application at:
echo           http://smartlibrary.local
echo.
timeout /t 3 >nul
exit /b
