package com.koaan.deeptest2;

import android.content.Context;
import android.os.Build;
import android.provider.Settings;
import org.json.JSONObject;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.Locale;

final class RootOps {
    private static volatile boolean ghostLockSucceeded;
    private static final long OFFSET = 0x45A000L;
    private static final String BROKER_SCRIPT = ".deeptest_root_broker.sh";
    private static final String BROKER_READY = ".deeptest_root_ready";
    private static final String BROKER_REQUEST = ".deeptest_root_request";
    private static final String BROKER_RESPONSE = ".deeptest_root_response";

    private static final class BrokerResult {
        final int code;
        final String backup;
        final String message;
        final String log;
        BrokerResult(int code, String backup, String message, String log) {
            this.code = code;
            this.backup = backup;
            this.message = message;
            this.log = log;
        }
    }
    private static String command(String... args) throws Exception {
        Process p = new ProcessBuilder(args).redirectErrorStream(true).start();
        String out = new String(p.getInputStream().readAllBytes(), StandardCharsets.UTF_8);
        int rc = p.waitFor();
        if (rc != 0) throw new IOException(out.isBlank() ? "Command failed: " + rc : out.trim());
        return out.trim();
    }
    private static String prop(String name) {
        try { return command("/system/bin/getprop", name); } catch (Exception e) { return ""; }
    }
    private static String rootBinary() {
        for (String candidate : new String[]{"/data/local/tmp/su", "su"}) {
            try { if (command(candidate, "-c", "id").contains("uid=0")) return candidate; } catch (Exception ignored) {}
        }
        return "";
    }
    static String deviceInfo(Context context) {
        try {
            JSONObject j = new JSONObject();
            String prj = "";
            for (String property : new String[]{
                    "ro.boot.prjname", "ro.boot.project_name", "ro.boot.prjid",
                    "ro.boot.project_id", "ro.product.prjname"
            }) {
                prj = prop(property).trim();
                if (!prj.isBlank()) break;
            }
            String udid = Settings.Secure.getString(context.getContentResolver(), Settings.Secure.ANDROID_ID);
            j.put("model", prop("ro.product.model").isBlank() ? Build.MODEL : prop("ro.product.model"))
                    .put("prjid", prj).put("chipId", prop("ro.boot.chipid"))
                    .put("udid", udid == null ? "" : udid);
            return j.toString();
        } catch (Exception e) { return "{}"; }
    }
    static String rootCheck(Context context) {
        try {
            BrokerResult broker = brokerCommand(context, "PING", 2500);
            if (broker != null && broker.code == 0) {
                ghostLockSucceeded = true;
                return "{\"ok\":true,\"message\":\"Root available.\"}";
            }
        } catch (Exception ignored) {}
        ghostLockSucceeded = false;
        String su = rootBinary();
        return "{\"ok\":" + (!su.isBlank()) + ",\"message\":" +
                JSONObject.quote(su.isBlank() ? "Root unavailable." : "Root available.") + "}";
    }
    static String rebootBootloader(Context context) {
        try {
            BrokerResult broker = brokerCommand(context, "REBOOT_BOOTLOADER", 20000);
            if (broker != null && broker.code == 0) {
                return new JSONObject().put("ok", true).put("message", broker.message).toString();
            }
            if (broker != null) {
                throw new IOException(broker.message + (broker.log.isBlank() ? "" : "\n" + broker.log));
            }
            String su = rootBinary();
            if (!su.isBlank()) {
                command(su, "-c", "sync; /system/bin/svc power reboot bootloader; sleep 5; " +
                        "/system/bin/setprop sys.powerctl reboot,bootloader; sleep 5; /system/bin/reboot bootloader");
                throw new IOException("The reboot commands returned, but the phone is still running.");
            }
            throw new IOException("Root unavailable. Run the root helper first.");
        } catch (Throwable error) {
            try { return new JSONObject().put("ok", false).put("error", error.getMessage()).toString(); }
            catch (Exception ignored) { return "{\"ok\":false}"; }
        }
    }
    static String gainTempRoot(Context context) {
        try {
            BrokerResult existing = brokerCommand(context, "PING", 1500);
            if (existing != null && existing.code == 0) {
                ghostLockSucceeded = true;
                return new JSONObject().put("ok", true).put("message", "Root available.").put("log", "Existing DeepTest root service is active.").toString();
            }
            File binary = new File(context.getApplicationInfo().nativeLibraryDir, "libghostlock.so");
            if (!binary.isFile()) throw new IOException("The packaged root helper is missing.");
            prepareBrokerScript(context);
            new File(context.getFilesDir(), BROKER_READY).delete();
            new File(context.getFilesDir(), BROKER_REQUEST).delete();
            new File(context.getFilesDir(), BROKER_RESPONSE).delete();
            File rootLog = new File(context.getFilesDir(), ".ghostlock_ksu.log");
            rootLog.delete();
            long startedAt = System.currentTimeMillis();
            ProcessBuilder builder = new ProcessBuilder(binary.getAbsolutePath());
            builder.directory(context.getFilesDir());
            builder.redirectErrorStream(true);
            builder.environment().put("GHOSTLOCK_HOME", context.getFilesDir().getAbsolutePath());
            builder.environment().put("DEEPTEST_NATIVE_HELPER", binary.getAbsolutePath());
            builder.environment().put("TMPDIR", context.getFilesDir().getAbsolutePath());
            builder.environment().put("HOME", context.getFilesDir().getAbsolutePath());
            Process process = builder.start();
            String output = new String(process.getInputStream().readAllBytes(), StandardCharsets.UTF_8);
            int result = process.waitFor();
            String rootDetails = rootLog.isFile() && rootLog.lastModified() >= startedAt - 1000
                    ? new String(Files.readAllBytes(rootLog.toPath()), StandardCharsets.UTF_8) : "";
            BrokerResult broker = brokerCommand(context, "PING", 5000);
            ghostLockSucceeded = result == 0 && broker != null && broker.code == 0;
            JSONObject response = new JSONObject();
            response.put("ok", ghostLockSucceeded);
            response.put("message", ghostLockSucceeded ? "Root available." : "Root unavailable.");
            response.put("exitCode", result);
            response.put("log", rootDetails.isBlank() ? output : output + "\n\n--- Root helper log ---\n" + rootDetails);
            return response.toString();
        } catch (Throwable error) {
            try { return new JSONObject().put("ok", false).put("error", error.getMessage()).toString(); }
            catch (Exception ignored) { return "{\"ok\":false}"; }
        }
    }
    private static String normalizeChip(String value) {
        String v = value.trim().toLowerCase(Locale.ROOT);
        if (v.startsWith("0x")) v = v.substring(2);
        return String.format("%8s", v).replace(' ', '0');
    }
    private static String shellQuote(String value) {
        return "'" + value.replace("'", "'\\''") + "'";
    }
    private static void writeSynced(File file, String value) throws Exception {
        try (FileOutputStream out = new FileOutputStream(file)) {
            out.write(value.getBytes(StandardCharsets.UTF_8));
            out.getFD().sync();
        }
    }
    private static void prepareBrokerScript(Context context) throws Exception {
        File target = new File(context.getFilesDir(), BROKER_SCRIPT);
        try (InputStream input = context.getAssets().open("root-broker.sh");
             FileOutputStream output = new FileOutputStream(target)) {
            input.transferTo(output);
            output.getFD().sync();
        }
        if (!target.setExecutable(true, true)) throw new IOException("Could not prepare the root service.");
    }
    private static synchronized BrokerResult brokerCommand(Context context, String operation, long timeoutMs) throws Exception {
        File home = context.getFilesDir();
        File ready = new File(home, BROKER_READY);
        if (!ready.isFile()) return null;
        File request = new File(home, BROKER_REQUEST);
        File response = new File(home, BROKER_RESPONSE);
        File pending = new File(home, BROKER_REQUEST + ".pending");
        response.delete();
        request.delete();
        pending.delete();
        String token = Long.toHexString(System.nanoTime()) + Long.toHexString(Thread.currentThread().getId());
        writeSynced(pending, token + "\n" + operation + "\n");
        if (!pending.renameTo(request)) throw new IOException("Could not contact the root service.");
        long deadline = System.currentTimeMillis() + timeoutMs;
        while (System.currentTimeMillis() < deadline) {
            if (response.isFile()) {
                String value = new String(Files.readAllBytes(response.toPath()), StandardCharsets.UTF_8);
                String[] lines = value.split("\n", -1);
                if (lines.length >= 4 && token.equals(lines[0])) {
                    int code = Integer.parseInt(lines[1].trim());
                    StringBuilder log = new StringBuilder();
                    for (int i = 4; i < lines.length; i++) {
                        if (i > 4) log.append('\n');
                        log.append(lines[i]);
                    }
                    response.delete();
                    return new BrokerResult(code, lines[2], lines[3], log.toString().trim());
                }
            }
            Thread.sleep(100);
        }
        request.delete();
        ready.delete();
        return null;
    }
    private static String runRootPayload(Context context, File payload, File result, File log) throws Exception {
        String su = rootBinary();
        if (!su.isBlank()) {
            String wrapper = "/system/bin/sh " + shellQuote(payload.getAbsolutePath()) +
                    " >" + shellQuote(log.getAbsolutePath()) + " 2>&1; " +
                    "rc=$?; echo $rc >" + shellQuote(result.getAbsolutePath()) + "; " +
                    "chmod 644 " + shellQuote(log.getAbsolutePath()) + " " + shellQuote(result.getAbsolutePath()) + "; " +
                    "rm -f " + shellQuote(payload.getAbsolutePath());
            command(su, "-c", wrapper);
        } else {
            throw new IOException("Root unavailable. Run the root helper first.");
        }
        long deadline = System.currentTimeMillis() + 45000;
        while (!result.isFile() && System.currentTimeMillis() < deadline) Thread.sleep(250);
        if (!result.isFile()) throw new IOException("Root authorization operation timed out.");
        return log.isFile() ? new String(Files.readAllBytes(log.toPath()), StandardCharsets.UTF_8) : "";
    }
    static String install(Context context, String rawCode) {
        String code = rawCode.replaceAll("\\s+", "");
        try {
            if (!code.matches("[0-9a-fA-F]{632}")) throw new IllegalArgumentException("Unlock code must be exactly 632 hexadecimal characters.");
            String embedded = new String(hex(code.substring(512, 528)), StandardCharsets.US_ASCII).toLowerCase(Locale.ROOT);
            String rawLiveChip = prop("ro.boot.chipid");
            if (rawLiveChip.isBlank()) throw new IllegalArgumentException("Could not read the connected phone's chip ID.");
            String live = normalizeChip(rawLiveChip);
            if (!embedded.matches("[0-9a-f]{8}") || !embedded.equals(live)) throw new IllegalArgumentException("Unlock code belongs to a different connected phone.");
            File codeFile = new File(context.getFilesDir(), "unlock-code.bin");
            try (FileOutputStream out = new FileOutputStream(codeFile)) { out.write(hex(code)); out.getFD().sync(); }
            BrokerResult broker = brokerCommand(context, "INSTALL", 120000);
            if (broker != null) {
                if (broker.code != 0 || !broker.log.contains("AUTHORIZATION_OK")) {
                    throw new IOException(broker.message + (broker.log.isBlank() ? "" : "\n" + broker.log));
                }
                return new JSONObject().put("ok", true).put("backup", broker.backup).put("log", broker.log).toString();
            }
            long stamp = System.currentTimeMillis();
            String backup = "/sdcard/deeptest-backup/oplusreserve1-preunlock-" + stamp + ".img";
            String patched = backup.replace(".img", "-patched.img");
            File payload = new File(context.getFilesDir(), ".deeptest_authorize.sh");
            File result = new File(context.getFilesDir(), ".deeptest_authorize.result");
            File log = new File(context.getFilesDir(), ".deeptest_authorize.log");
            result.delete(); log.delete();
            String script = "#!/system/bin/sh\nset -e\n" +
                    "cleanup() { rm -f '" + codeFile.getAbsolutePath() + "' '" + context.getFilesDir().getAbsolutePath() + "/verify.bin' /data/local/tmp/preload.so /data/local/tmp/oplusreserve1.img /data/local/tmp/su_daemon.log /data/local/tmp/temp_su.sock; }\n" +
                    "trap cleanup EXIT\nmkdir -p /sdcard/deeptest-backup\nchmod 0771 /sdcard/deeptest-backup\n" +
                    "dd if=/dev/block/by-name/oplusreserve1 of='" + backup + "'\ncp '" + backup + "' '" + patched + "'\n" +
                    "dd if='" + codeFile.getAbsolutePath() + "' of='" + patched + "' bs=1 seek=" + OFFSET + " conv=notrunc,fsync\n" +
                    "dd if='" + patched + "' of=/dev/block/by-name/oplusreserve1 conv=fsync\n" +
                    "dd if=/dev/block/by-name/oplusreserve1 bs=1 skip=" + OFFSET + " count=316 of='" + context.getFilesDir().getAbsolutePath() + "/verify.bin' 2>/dev/null\n" +
                    "cmp '" + codeFile.getAbsolutePath() + "' '" + context.getFilesDir().getAbsolutePath() + "/verify.bin'\n" +
                    "echo AUTHORIZATION_OK\n";
            writeSynced(payload, script);
            payload.setExecutable(true, true);
            String details = runRootPayload(context, payload, result, log);
            String rc = new String(Files.readAllBytes(result.toPath()), StandardCharsets.UTF_8).trim();
            if (!"0".equals(rc) || !details.contains("AUTHORIZATION_OK")) throw new IOException("Authorization handoff failed. " + details);
            return new JSONObject().put("ok", true).put("backup", backup).put("log", details).toString();
        } catch (Throwable e) {
            try { return new JSONObject().put("ok", false).put("error", e.getMessage()).toString(); }
            catch (Exception ignored) { return "{\"ok\":false}"; }
        }
    }
    private static byte[] hex(String value) {
        byte[] out = new byte[value.length() / 2];
        for (int i = 0; i < out.length; i++) out[i] = (byte) Integer.parseInt(value.substring(i * 2, i * 2 + 2), 16);
        return out;
    }
    private static String bytesHex(byte[] data) {
        StringBuilder b = new StringBuilder(data.length * 2);
        for (byte v : data) b.append(String.format(Locale.ROOT, "%02x", v & 0xff));
        return b.toString();
    }
}
