package io.maddb.smoke;

import android.os.Build;
import android.system.Os;
import android.system.OsConstants;
import android.test.InstrumentationTestCase;
import android.test.InstrumentationTestRunner;
import java.io.File;

/** Real target process test, not a host/JVM substitute. No AndroidX dependency. */
@SuppressWarnings("deprecation")
public final class MadDbInstrumentedTest extends InstrumentationTestCase {
    public void testRealArm64PersistenceAndLifecycle() {
        assertTrue("Requires the Android platform test runner",
                getInstrumentation() instanceof InstrumentationTestRunner);
        InstrumentationTestRunner runner = (InstrumentationTestRunner) getInstrumentation();
        String mode = runner.getArguments().getString("maddb_expected_page_size");
        assertTrue("Pass an explicit maddb_expected_page_size (4096 or 16384)",
                "4096".equals(mode) || "16384".equals(mode));

        // Check from the process that will load and use MadDB, before the smoke operations.
        String machine = Os.uname().machine;
        assertTrue("Requires an ARM64 machine in the test process",
                "aarch64".equals(machine) || "arm64".equals(machine));
        assertTrue("Requires a 64-bit test process", android.os.Process.is64Bit());
        assertTrue("Requires primary Android ABI arm64-v8a",
                Build.SUPPORTED_ABIS.length > 0 && "arm64-v8a".equals(Build.SUPPORTED_ABIS[0]));
        assertEquals("Actual test-process page size", Long.parseLong(mode),
                Os.sysconf(OsConstants._SC_PAGESIZE));
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
