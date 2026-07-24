@echo off
setlocal
where adb >nul 2>&1 || (echo adb.exe was not found & exit /b 1)
adb push preload.so /data/local/tmp/preload.so || exit /b 1
adb shell chmod 0644 /data/local/tmp/preload.so || exit /b 1
adb shell /data/local/tmp/su -c id
pause
