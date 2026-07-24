import java.lang.reflect.Method;

/**
 * Minimal Android entry point for passing a server-issued authorization to the
 * Oplus engineer service. DeepTest launches this through app_process as root.
 */
public final class FastbootUnlockHelper {
    private FastbootUnlockHelper() {
    }

    private static byte[] decodeHex(String value) {
        if (value == null || value.isEmpty() || (value.length() & 1) != 0) {
            throw new IllegalArgumentException("unlock code must be non-empty, even-length hex");
        }
        byte[] output = new byte[value.length() / 2];
        for (int index = 0; index < value.length(); index += 2) {
            int high = Character.digit(value.charAt(index), 16);
            int low = Character.digit(value.charAt(index + 1), 16);
            if (high < 0 || low < 0) {
                throw new IllegalArgumentException("unlock code contains a non-hex character");
            }
            output[index / 2] = (byte) ((high << 4) | low);
        }
        return output;
    }

    public static void main(String[] args) {
        try {
            if (args.length != 1) {
                throw new IllegalArgumentException("expected one unlock-code argument");
            }
            byte[] authorization = decodeHex(args[0]);
            Class<?> manager = Class.forName("android.engineer.OplusEngineerManager");
            Method method = manager.getMethod("fastbootUnlock", byte[].class, int.class);
            Object result = method.invoke(null, authorization, authorization.length);
            boolean accepted = Boolean.TRUE.equals(result);
            System.out.println("authorizationBytes=" + authorization.length);
            System.out.println("fastbootUnlockResult=" + accepted);
            if (!accepted) {
                System.exit(2);
            }
        } catch (Throwable error) {
            System.err.println("fastbootUnlockError=" + error.getClass().getSimpleName()
                    + ": " + String.valueOf(error.getMessage()));
            System.exit(1);
        }
    }
}
