package io.maddb.smoke;

import android.os.Build;
import android.test.InstrumentationTestCase;
import java.io.File;
import java.util.Arrays;

/** Real target process test, not a host/JVM substitute. No AndroidX dependency. */
@SuppressWarnings("deprecation")
public final class MadDbInstrumentedTest extends InstrumentationTestCase {
    public void testRealArm64PersistenceAndLifecycle() {
        assertTrue(Arrays.asList(Build.SUPPORTED_ABIS).contains("arm64-v8a"));
        File directory = new File(getInstrumentation().getTargetContext().getFilesDir(), "instrumentation");
        assertTrue(directory.isDirectory() || directory.mkdirs());
        Smoke.run(directory);
        File foreign = new File(directory, "foreign.sqlite");
        try (android.database.sqlite.SQLiteDatabase sqlite = android.database.sqlite.SQLiteDatabase.openOrCreateDatabase(foreign, null)) {
            sqlite.execSQL("CREATE TABLE IF NOT EXISTS sqliteX_customer(value TEXT)");
        }
        try { io.maddb.MadDb.open(foreign, "ns"); fail("foreign schema accepted"); }
        catch (io.maddb.MadDb.MadDbException expected) { assertEquals(-4, expected.status); }
    }
}
