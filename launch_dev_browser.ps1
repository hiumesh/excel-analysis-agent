$chromePath = "C:\Program Files\Google\Chrome\Application\chrome.exe"
$edgePath = "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
$tempDir = "$env:TEMP\spfx_dev_session"

# Try Chrome first, fallback to Edge
if (Test-Path $chromePath) {
    Write-Host "Launching Google Chrome with web security disabled..."
    Start-Process $chromePath -ArgumentList "--disable-web-security --user-data-dir=`"$tempDir`""
} elseif (Test-Path $edgePath) {
    Write-Host "Chrome not found. Launching Microsoft Edge with web security disabled..."
    Start-Process $edgePath -ArgumentList "--disable-web-security --user-data-dir=`"$tempDir`""
} else {
    Write-Host "Could not find Chrome or Edge in default locations. Please run the command manually."
}
