package io.maddb;

import java.io.File;
import java.nio.ByteBuffer;
import java.nio.CharBuffer;
import java.nio.charset.CharacterCodingException;
import java.nio.charset.StandardCharsets;
import java.util.Objects;

/** Synchronous plaintext SQLite. Call from a worker, not the Android UI thread.
 * Close with try-with-resources. No finalizer, telemetry or Obs dependency.
 * Caller must not mutate input byte arrays concurrently with a call.
 */
public final class MadDb implements AutoCloseable {
    public static final String VERSION = "0.1.0-preview.1";
    private static final int OK = 0, NOT_FOUND = 1, BUFFER_TOO_SMALL = 2;
    private static final int MAX_VALUE_BYTES = 16 * 1024 * 1024;
    private long handle;
    static {
        System.loadLibrary("maddb");
        System.loadLibrary("maddb_jni");
        if (nativeVersion() != 1) throw new LinkageError("Unsupported MadDB ABI");
    }
    private MadDb(long handle) { this.handle = handle; }
    public static MadDb open(File file, String namespace) {
        Objects.requireNonNull(file, "file");
        long[] result = {0};
        check(nativeOpen(utf8(file.getAbsolutePath()), utf8(namespace), result));
        try { return new MadDb(result[0]); }
        catch (Error failure) { nativeClose(result[0]); throw failure; }
    }
    public synchronized void put(String key, byte[] value) {
        requireOpen();
        Objects.requireNonNull(value, "value");
        if (value.length > MAX_VALUE_BYTES) throw new IllegalArgumentException("Value exceeds 16 MiB adapter limit");
        check(nativePut(handle, utf8(key), value));
    }
    /** Null means absent; a zero-length array is a present empty value.
     * Probe/copy can race other handles. At most three retries, then an explicit
     * error instead of returning partial data or looping indefinitely.
     */
    public synchronized byte[] get(String key) {
        requireOpen();
        byte[] k = utf8(key);
        for (int attempt = 0; attempt < 3; attempt++) {
            long[] length = {0};
            int status = nativeGet(handle, k, new byte[0], length);
            if (status == NOT_FOUND) return null;
            if (status == OK) return new byte[0];
            if (status != BUFFER_TOO_SMALL) check(status);
            if (length[0] < 0 || length[0] > MAX_VALUE_BYTES) throw new IllegalStateException("Value exceeds 16 MiB adapter limit");
            byte[] value = new byte[(int) length[0]];
            status = nativeGet(handle, k, value, length);
            if (status == NOT_FOUND) return null;
            if (status == BUFFER_TOO_SMALL) continue;
            check(status);
            return java.util.Arrays.copyOf(value, (int) length[0]);
        }
        throw new IllegalStateException("Value changed size repeatedly; retry get");
    }
    public synchronized void remove(String key) { requireOpen(); check(nativeRemove(handle, utf8(key))); }
    @Override public synchronized void close() {
        if (handle == 0) return;
        long old = handle;
        handle = 0;
        check(nativeClose(old));
    }
    private void requireOpen() { if (handle == 0) throw new IllegalStateException("MadDB is closed"); }
    private static byte[] utf8(String text) {
        Objects.requireNonNull(text, "text");
        try {
            ByteBuffer encoded = StandardCharsets.UTF_8.newEncoder().encode(CharBuffer.wrap(text));
            byte[] bytes = new byte[encoded.remaining()]; encoded.get(bytes); return bytes;
        } catch (CharacterCodingException e) { throw new IllegalArgumentException("Malformed Unicode", e); }
    }
    private static void check(int status) { if (status != OK) throw new MadDbException(status); }
    public static final class MadDbException extends RuntimeException {
        public final int status;
        private MadDbException(int status) { super("MadDB status " + status); this.status = status; }
    }
    private static native int nativeVersion();
    private static native int nativeOpen(byte[] path, byte[] ns, long[] out);
    private static native int nativePut(long handle, byte[] key, byte[] value);
    private static native int nativeGet(long handle, byte[] key, byte[] buffer, long[] length);
    private static native int nativeRemove(long handle, byte[] key);
    private static native int nativeClose(long handle);
}
