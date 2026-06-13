Write-Host "ORION Chat Agent - GitHub Deploy" -ForegroundColor Cyan
Write-Host "=================================" -ForegroundColor Cyan
Write-Host ""

# Check if remote exists
$remote = git remote -v
if (-not $remote) {
    Write-Host "Step 1: Go to https://github.com/new in your browser" -ForegroundColor Yellow
    Write-Host "  Repository name: orion-chat-agent" -ForegroundColor White
    Write-Host "  Keep it Public" -ForegroundColor White
    Write-Host "  DON'T initialize with README" -ForegroundColor White
    Write-Host "  Click Create repository" -ForegroundColor White
    Write-Host ""
    Read-Host "Press Enter after you created the repo"
    
    $user = Read-Host "Enter your GitHub username"
    git remote add origin "https://github.com/$user/orion-chat-agent.git"
}

Write-Host "Pushing to GitHub..." -ForegroundColor Cyan
git add .
git commit -m "Auto-update $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
git push -u origin master

if ($LASTEXITCODE -eq 0) {
    Write-Host "SUCCESS!" -ForegroundColor Green
    Write-Host "Railway will auto-deploy in 1-2 minutes." -ForegroundColor Green
    Write-Host "Check: https://railway.app/dashboard" -ForegroundColor Green
} else {
    Write-Host "Push failed. Did you create the repo?" -ForegroundColor Red
}
