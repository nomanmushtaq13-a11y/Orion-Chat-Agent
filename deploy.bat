@echo off
REM ORION Chat Agent - One-click Deploy Script
REM Run this to push updates to GitHub (which auto-deploys to Railway)

echo ORION Chat Agent - Deploy Tool
echo =================================
echo.

REM Check if git is set up
git status >nul 2>&1
if errorlevel 1 (
    echo ERROR: Not a git repository. Run this from chat-agent/ directory.
    pause
    exit /b 1
)

REM Check for remote
git remote -v >nul 2>&1
if errorlevel 1 (
    echo No GitHub remote found.
    echo.
    echo Create a repo on GitHub.com:
    echo   1. Go to https://github.com/new
    echo   2. Name: orion-chat-agent
    echo   3. Click Create repository
    echo   4. Then run these commands:
    echo.
    echo   git remote add origin https://github.com/YOUR_USERNAME/orion-chat-agent.git
    echo   git push -u origin master
    echo.
    pause
    exit /b 0
)

REM Commit and push
git add .
git commit -m "Auto-update %DATE% %TIME%"
git push

echo.
echo Done! Railway will auto-deploy in 1-2 minutes.
echo Check status at: https://railway.app/dashboard
pause
