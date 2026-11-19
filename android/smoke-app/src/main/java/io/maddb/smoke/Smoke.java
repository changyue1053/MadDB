package io.maddb.smoke;
import io.maddb.MadDb;
import java.io.File;
import java.util.Arrays;

public final class Smoke {
    private static void require(boolean value) { if (!value) throw new AssertionError("MadDB smoke failed"); }
    public static void run(File directory) {
        File file = new File(directory, "数据库-😀.sqlite");
        String key = "键\u0000😀";
        byte[] binary = {0, (byte)255, (byte)128, 42};
        try (MadDb db = MadDb.open(file, "独立应用")) {
            db.remove(key);
            require(db.get(key) == null);
            db.put(key, binary);
        }
        MadDb reopened = MadDb.open(file, "独立应用");
        try {
            require(Arrays.equals(reopened.get(key), binary));
            reopened.put(key, new byte[0]);
            require(reopened.get(key) != null && reopened.get(key).length == 0);
            reopened.remove(key); reopened.remove(key);
            require(reopened.get(key) == null);
            try { reopened.put("bad\uD800", binary); throw new AssertionError("invalid Unicode accepted"); }
            catch (IllegalArgumentException expected) { /* Strict UTF-8 encoding. */ }
        } finally { reopened.close(); reopened.close(); }
        try { reopened.get(key); throw new AssertionError("closed handle accepted"); }
        catch (IllegalStateException expected) { /* wrapper prevents stale use */ }
        try { MadDb.open(file, ""); throw new AssertionError("empty namespace accepted"); }
        catch (MadDb.MadDbException expected) { require(expected.status == -1); }
        try { MadDb.open(new File(directory, "missing-parent/store.sqlite"), "ns"); throw new AssertionError("missing parent accepted"); }
        catch (MadDb.MadDbException expected) { require(expected.status == -3); }
        try { MadDb.open(new File(directory, "bad\u0000name"), "ns"); throw new AssertionError("NUL path accepted"); }
        catch (MadDb.MadDbException expected) { require(expected.status == -1); }
    }
    private Smoke() {}
}
