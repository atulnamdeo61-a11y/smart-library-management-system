@echo off
setlocal enabledelayedexpansion

:: ====================================================================
:: SMART LIBRARY MANAGEMENT SYSTEM - ALL-IN-ONE MASTER LAUNCHER
:: Automatically configures custom domain, WampServer, virtualenv,
:: database, and starts the server with one single click.
:: ====================================================================

title Smart Library Management System - All-in-One Launcher
color 0B

:: 1. Self-Elevate to Administrator (required for hosts file and services)
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo ====================================================================
    echo    Requesting Administrator privileges for one-time setup...
    echo ====================================================================
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process cmd -ArgumentList '/c \"\"%~f0\"\"' -Verb RunAs"
    exit /b
)

:: Switch to script's own folder
cd /d "%~dp0"

echo ====================================================================
echo        SMART LIBRARY MANAGEMENT SYSTEM - ALL-IN-ONE LAUNCHER
echo ====================================================================
echo.

:: 2. Configure Windows Hosts File for Custom Domain 'smartlibrary.local'
set "HOSTS_FILE=%WINDIR%\System32\drivers\etc\hosts"
echo [*] Checking custom domain 'smartlibrary.local'...
findstr /I "smartlibrary.local" "%HOSTS_FILE%" >nul 2>&1
if %errorLevel% neq 0 (
    echo. >> "%HOSTS_FILE%"
    echo 127.0.0.1 smartlibrary.local >> "%HOSTS_FILE%"
    echo 127.0.0.1 www.smartlibrary.local >> "%HOSTS_FILE%"
    echo [OK] Added 'smartlibrary.local' to Windows hosts file.
) else (
    echo [OK] Custom domain 'smartlibrary.local' already mapped in hosts.
)

:: 3. Configure and Launch WampServer (if installed)
if exist "C:\wamp64\wampmanager.exe" (
    echo [*] Checking WampServer integration...
    
    :: Enable Apache Proxy modules if not already enabled
    set "HTTPD_CONF=C:\wamp64\bin\apache\apache2.4.65\conf\httpd.conf"
    if exist "!HTTPD_CONF!" (
        powershell -NoProfile -Command "$c = Get-Content '!HTTPD_CONF!' -Raw; $c = $c -replace '#LoadModule proxy_module', 'LoadModule proxy_module'; $c = $c -replace '#LoadModule proxy_http_module', 'LoadModule proxy_http_module'; Set-Content '!HTTPD_CONF!' -Value $c -NoNewline" >nul 2>&1
    )

    :: Configure VirtualHost in Apache
    set "VHOSTS_CONF=C:\wamp64\bin\apache\apache2.4.65\conf\extra\httpd-vhosts.conf"
    if exist "!VHOSTS_CONF!" (
        findstr /I "smartlibrary.local" "!VHOSTS_CONF!" >nul 2>&1
        if errorlevel 1 (
            powershell -NoProfile -Command "Add-Content '!VHOSTS_CONF!' -Value \"`n<VirtualHost *:80>`n  ServerName smartlibrary.local`n  ServerAlias www.smartlibrary.local`n  ProxyPreserveHost On`n  ProxyPass / http://127.0.0.1:5000/`n  ProxyPassReverse / http://127.0.0.1:5000/`n  <Proxy *>`n    Require all granted`n  </Proxy>`n</VirtualHost>`n\"" >nul 2>&1
        )
    )

    :: Configure WampServer www gateway
    if not exist "C:\wamp64\www\smart-library" mkdir "C:\wamp64\www\smart-library"
    echo ^<?php header('Location: http://127.0.0.1:5000/'^); exit(^); ?^> > "C:\wamp64\www\smart-library\index.php"

    :: Start WampServer services & launcher
    net start wampapache64 >nul 2>&1
    net start wampmysqld64 >nul 2>&1
    net start wampmariadb64 >nul 2>&1
    tasklist /fi "imagename eq wampmanager.exe" 2>nul | find /i "wampmanager.exe" >nul
    if errorlevel 1 (
        start "" "C:\wamp64\wampmanager.exe"
    )
    echo [OK] WampServer services configured & active.
) else (
    echo [i] WampServer not detected at C:\wamp64 (running with standalone server).
)

:: 4. Verify Python Virtual Environment
if not exist ".venv\Scripts\python.exe" (
    echo [*] Creating Python virtual environment (.venv)...
    python -m venv .venv
    echo [*] Installing required Python dependencies...
    .\.venv\Scripts\pip.exe install -r requirements.txt
) else (
    echo [OK] Python environment verified.
)

:: 5. Verify & Initialize Database
if not exist "smart_library.db" (
    echo [*] Initializing database and seeding demo data...
    .\.venv\Scripts\python.exe -m flask --app run.py init-db
    .\.venv\Scripts\python.exe -m flask --app run.py seed-data
    echo [OK] Database initialized successfully.
) else (
    echo [OK] Database verified.
)

:: 6. Launch Default Browser
echo.
echo ====================================================================
echo                   SERVER ONLINE & READY!
echo ====================================================================
echo.
echo   [1] Custom Domain:   http://smartlibrary.local
echo   [2] Direct Link:     http://localhost:5000
echo   [3] WampServer Link: http://localhost/smart-library
echo   [4] phpMyAdmin:      http://localhost/phpmyadmin
echo.
echo --------------------------------------------------------------------
echo   PRE-SEEDED EVALUATOR ACCOUNTS (VIVA PRESENTATION):
echo     * Administrator: admin@college.edu       / Admin@123
echo     * Librarian:     librarian@college.edu   / Librarian@123
echo     * Student:       aarav.student@college.edu / Student@123
echo --------------------------------------------------------------------
echo.

:: Automatically open browser after 1 second
start "" "http://smartlibrary.local"
timeout /t 1 >nul 2>&1
start "" "http://localhost:5000"

:: 7. Start Flask Web Server
echo [*] Running application server (Press Ctrl+C to stop)...
echo.
.\.venv\Scripts\python.exe run.py

pause
