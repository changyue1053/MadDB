package io.maddb.smoke;
import android.app.Activity;
import android.os.Bundle;
import android.widget.TextView;

public final class MainActivity extends Activity {
    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        TextView text = new TextView(this); text.setText("Running real SQLite JNI smoke…"); setContentView(text);
        new Thread(() -> {
            String result;
            try { Smoke.run(getFilesDir()); result = "PASS: ARM64 JNI persistence / binary / empty / close"; }
            catch (Throwable failure) { result = "FAIL: " + failure.getClass().getSimpleName() + ": " + failure.getMessage(); }
            String finalResult = result;
            runOnUiThread(() -> text.setText(finalResult));
        }, "maddb-smoke").start();
    }
}
