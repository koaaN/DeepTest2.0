adb push preload.so /data/local/tmp/preload.so                      # push preload to device
adb shell 'chmod 0644 /data/local/tmp/preload.so'                   # set file permissions
adb shell 'LD_PRELOAD=/data/local/tmp/preload.so /system/bin/true'  # run it to gain temp root, if it fails, just run it again
echo "root complete"
