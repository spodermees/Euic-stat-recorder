@echo off
setlocal
cd /d %~dp0

py -m pip install --upgrade pip
py -m pip install -r requirements.txt
py -m pip install --upgrade pyinstaller

py -m PyInstaller --onefile --noconfirm --clean --name "EuicStatRecorder" --add-data "templates;templates" --add-data "static;static" --add-data "showdown_user_script.js;." desktop_app.py
py -m PyInstaller --onefile --noconfirm --clean --name "EuicStatRecorderWatcher" watcher.py

echo Done. Check the dist\ folder.
