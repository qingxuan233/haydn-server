package com.qingxuan.bridge;

import android.Manifest;
import android.app.Activity;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.os.Build;
import android.os.Bundle;
import android.util.TypedValue;
import android.widget.TextView;

import java.util.ArrayList;
import java.util.List;

/** Minimal launcher: starts the service and asks for runtime permissions. */
public class MainActivity extends Activity {
    private static final int REQ = 42;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        Intent svc = new Intent(this, BridgeService.class);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            startForegroundService(svc);
        } else {
            startService(svc);
        }

        requestNeededPermissions();

        TextView tv = new TextView(this);
        tv.setTextSize(TypedValue.COMPLEX_UNIT_SP, 16);
        tv.setPadding(48, 64, 48, 48);
        tv.setText("Qingxuan Bridge\n\n"
                + "Loopback HTTPS: 127.0.0.1:3099\n"
                + "Endpoints: /v1/health, /v1/version, /v1/status\n\n"
                + "This MVP is a development build; token is provisioned via adb.\n"
                + "No data leaves the loopback interface.");
        setContentView(tv);
    }

    private void requestNeededPermissions() {
        List<String> wanted = new ArrayList<String>();
        if (Build.VERSION.SDK_INT >= 33
                && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)
                != PackageManager.PERMISSION_GRANTED) {
            wanted.add(Manifest.permission.POST_NOTIFICATIONS);
        }
        if (checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION)
                != PackageManager.PERMISSION_GRANTED) {
            wanted.add(Manifest.permission.ACCESS_FINE_LOCATION);
        }
        if (!wanted.isEmpty()) {
            requestPermissions(wanted.toArray(new String[0]), REQ);
        }
    }
}
