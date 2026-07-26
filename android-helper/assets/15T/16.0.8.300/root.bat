@echo off
setlocal
where adb >nul 2>&1
adb push preload.so /data/local/tmp/preload.so
adb shell chmod 0644 /data/local/tmp/preload.so
adb shell LD_PRELOAD=/data/local/tmp/preload.so /system/bin/true
pause
