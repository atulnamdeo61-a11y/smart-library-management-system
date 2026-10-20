@echo off
setlocal EnableDelayedExpansion
title Smart Library - Push to GitHub

echo ===================================================
echo     SMART LIBRARY MANAGEMENT SYSTEM - GITHUB PUSH
echo ===================================================
echo.

set "PATH=%LOCALAPPDATA%\Programs\Git\cmd;%LOCALAPPDATA%\Programs\gh;%PATH%"

where git >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Git was not found in PATH.
    pause
    exit /b 1
)

where gh >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] GitHub CLI (gh) was not found in PATH.
    pause
    exit /b 1
)

echo [1/4] Checking GitHub authentication status...
gh auth status >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] You are not logged into GitHub CLI yet.
    echo Launching browser authentication...
    gh auth login -h github.com -p https -w
    if %errorlevel% neq 0 (
        echo [ERROR] GitHub authentication was not completed.
        pause
        exit /b 1
    )
)

echo [SUCCESS] Logged in to GitHub!
echo.

echo [2/4] Verifying local Git repository...
if not exist ".git" (
    echo Initializing Git repository...
    git init
    git config user.name "atulnamdeo61-a11y"
    git config user.email "atulnamdeo61@gmail.com"
    git branch -M main
    git add .
    git commit -m "Initial commit: Smart Library Management System"
) else (
    git branch -M main
    git add .
    git commit -m "Update: Smart Library Management System" >nul 2>&1
)

echo [3/4] Creating/Connecting remote repository 'smart-library-management-system'...
gh repo view atulnamdeo61-a11y/smart-library-management-system >nul 2>&1
if %errorlevel% neq 0 (
    echo Creating public repository 'smart-library-management-system' on GitHub...
    gh repo create atulnamdeo61-a11y/smart-library-management-system --public --source=. --remote=origin --description "Smart Library Management System - Python Flask, SQLite/MySQL, Dynamic UPI Payment QR, CR80 Digital ID Cards, Circulation Analytics" --push
) else (
    echo Repository exists. Setting remote origin and pushing...
    git remote remove origin >nul 2>&1
    git remote add origin https://github.com/atulnamdeo61-a11y/smart-library-management-system.git
    git push -u origin main
)

echo.
echo ===================================================
echo [4/4] PROJECT SUCCESSFULLY PUSHED TO GITHUB!
echo Repository URL: https://github.com/atulnamdeo61-a11y/smart-library-management-system
echo ===================================================
echo.
pause
