@echo off
setlocal
py -3 -m pip install --upgrade pyinstaller
py -3 -m PyInstaller --noconfirm --clean --windowed --name DeepTest2 --add-data "android-helper\assets;android-helper\assets" --add-data "src\deeptesting\assets;deeptesting\assets" --paths src src\deeptesting\gui.py
echo.
echo Build complete: dist\DeepTest2\DeepTest2.exe
pause
