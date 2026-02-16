param(
    [switch]$WatcherOnly,
    [switch]$AppOnly,
    [switch]$OneDir
)

$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $here

$mode = if ($OneDir) { "--onedir" } else { "--onefile" }

python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install --upgrade pyinstaller

if (-not $WatcherOnly) {
    python -m PyInstaller $mode --noconfirm --clean --name "EuicStatRecorder" `
        --add-data "templates;templates" `
        --add-data "static;static" `
        --add-data "showdown_user_script.js;." `
        desktop_app.py
}

if (-not $AppOnly) {
    python -m PyInstaller $mode --noconfirm --clean --name "EuicStatRecorderWatcher" watcher.py
}

Write-Host "Done. Check the dist\\ folder."
