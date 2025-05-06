@echo off
setlocal

:: Set your GitHub repo URL
set REPO_URL=https://github.com/manulapulga/pump-design.git

:: Set branch name (change if your branch is not 'main')
set BRANCH=main

:: Initialize git if not already done
if not exist ".git" (
    echo Initializing new Git repo...
    git init
    git remote add origin %REPO_URL%
)

:: Add all files
git add .

:: Commit with timestamp
git commit -m "Auto commit %date% %time%"

:: Push to GitHub
git push -u origin %BRANCH%

echo.
echo Done!
pause
