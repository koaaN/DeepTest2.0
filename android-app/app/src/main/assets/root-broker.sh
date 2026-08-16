#!/system/bin/sh

# DeepTest 2.0 restricted temporary-root broker.
# This intentionally exposes only the fixed operations below, never a shell.

HOME_DIR="${GHOSTLOCK_HOME:-/data/user/0/com.koaan.deeptest2/files}"
READY="$HOME_DIR/.deeptest_root_ready"
REQUEST="$HOME_DIR/.deeptest_root_request"
RESPONSE="$HOME_DIR/.deeptest_root_response"
CODE="$HOME_DIR/unlock-code.bin"
VERIFY="$HOME_DIR/verify.bin"
OPLOG="$HOME_DIR/.deeptest_root_operation.log"
NATIVE_HELPER="${DEEPTEST_NATIVE_HELPER:-}"
OFFSET=4562944

finish() {
  rm -f "$READY" "$REQUEST"
}
trap finish EXIT INT TERM

respond() {
  TOKEN="$1"
  RC="$2"
  BACKUP="$3"
  MESSAGE="$4"
  TMP="$RESPONSE.tmp.$$"
  {
    printf '%s\n%s\n%s\n%s\n' "$TOKEN" "$RC" "$BACKUP" "$MESSAGE"
    if [ -f "$OPLOG" ]; then cat "$OPLOG"; fi
  } >"$TMP"
  chmod 0644 "$TMP"
  mv -f "$TMP" "$RESPONSE"
}

rm -f "$REQUEST" "$RESPONSE"
printf '%s\n' "$$" >"$READY.tmp"
chmod 0644 "$READY.tmp"
mv -f "$READY.tmp" "$READY"

while true; do
  if [ ! -f "$REQUEST" ]; then
    sleep 0.2
    continue
  fi

  TOKEN=$(sed -n '1p' "$REQUEST")
  OP=$(sed -n '2p' "$REQUEST")
  rm -f "$REQUEST" "$OPLOG"

  case "$OP" in
    PING)
      respond "$TOKEN" 0 "" "Root available."
      ;;

    INSTALL)
      STAMP="$(date +%s)-$$"
      BACKUP="/sdcard/deeptest-backup/oplusreserve1-preunlock-$STAMP.img"
      PATCHED="/sdcard/deeptest-backup/oplusreserve1-preunlock-$STAMP-patched.img"
      (
        set -e
        cleanup_install() {
          rm -f "$CODE" "$VERIFY" /data/local/tmp/preload.so /data/local/tmp/oplusreserve1.img /data/local/tmp/su_daemon.log /data/local/tmp/temp_su.sock
        }
        trap cleanup_install EXIT
        test -f "$CODE"
        test "$(wc -c <"$CODE")" -eq 316
        mkdir -p /sdcard/deeptest-backup
        chmod 0771 /sdcard/deeptest-backup
        dd if=/dev/block/by-name/oplusreserve1 of="$BACKUP"
        cp "$BACKUP" "$PATCHED"
        dd if="$CODE" of="$PATCHED" bs=1 seek=$OFFSET conv=notrunc,fsync
        dd if="$PATCHED" of=/dev/block/by-name/oplusreserve1 conv=fsync
        dd if=/dev/block/by-name/oplusreserve1 bs=1 skip=$OFFSET count=316 of="$VERIFY" 2>/dev/null
        cmp "$CODE" "$VERIFY"
        echo AUTHORIZATION_OK
      ) >"$OPLOG" 2>&1
      RC=$?
      chmod 0644 "$OPLOG" 2>/dev/null
      if [ "$RC" -eq 0 ]; then
        respond "$TOKEN" 0 "$BACKUP" "Authorization completed successfully."
      else
        respond "$TOKEN" "$RC" "$BACKUP" "Authorization failed."
      fi
      ;;

    REBOOT_BOOTLOADER)
      # A successful reboot tears this process and the app down, so there is
      # deliberately no early success response.  If Android rejects every
      # route and this process is still alive, report a real failure instead.
      {
        echo "Requesting direct kernel reboot to bootloader."
        sync
        if [ -n "$NATIVE_HELPER" ] && [ -x "$NATIVE_HELPER" ]; then
          "$NATIVE_HELPER" --reboot-bootloader
          echo "Direct kernel reboot returned without rebooting."
        else
          echo "Bundled native reboot helper is unavailable."
        fi
        echo "Trying Android power service fallback."
        /system/bin/svc power reboot bootloader
        echo "Power service returned without rebooting; trying sys.powerctl."
        /system/bin/setprop sys.powerctl reboot,bootloader
        sleep 5
        echo "sys.powerctl returned without rebooting; trying reboot binary."
        /system/bin/reboot bootloader
        sleep 5
        echo "All reboot methods returned and the phone is still running."
      } >"$OPLOG" 2>&1
      chmod 0644 "$OPLOG" 2>/dev/null
      respond "$TOKEN" 1 "" "Could not reboot to bootloader."
      ;;

    STOP)
      respond "$TOKEN" 0 "" "Root service stopped."
      exit 0
      ;;

    *)
      respond "$TOKEN" 2 "" "Unsupported root operation."
      ;;
  esac
done
