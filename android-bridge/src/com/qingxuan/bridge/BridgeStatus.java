package com.qingxuan.bridge;

import android.app.ActivityManager;
import android.app.KeyguardManager;
import android.app.usage.UsageEvents;
import android.app.usage.UsageStatsManager;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.pm.PackageManager;
import android.hardware.display.DisplayManager;
import android.net.TrafficStats;
import android.net.wifi.WifiInfo;
import android.net.wifi.WifiManager;
import android.os.BatteryManager;
import android.os.Build;
import android.os.PowerManager;
import android.os.StatFs;
import android.os.SystemClock;
import android.provider.Settings;
import android.telephony.TelephonyManager;
import android.util.Log;

import org.json.JSONArray;
import org.json.JSONObject;

import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;
import java.util.TimeZone;

/** Read-only Android state collector for the bridge MVP. */
final class BridgeStatus {
    private static final String TAG = "BridgeStatus";
    private static final String VERSION = "1.0.0";

    private BridgeStatus() {}

    static String json(Context context) {
        JSONObject root = new JSONObject();
        try {
            root.put("schema", "bridge.status.v1");
            root.put("version", VERSION);
            root.put("source", "android");
            root.put("ts", isoNow());
            root.put("uptime_s", SystemClock.elapsedRealtime() / 1000L);

            JSONArray caps = new JSONArray();
            for (String c : new String[]{"battery", "wifi", "build", "memory", "disk", "thermal", "packages", "display", "usage", "network_bytes", "uptime"}) {
                caps.put(c);
            }
            root.put("capabilities", caps);

            root.put("device", device());
            root.put("battery", battery(context));
            root.put("wifi", wifi(context));
            root.put("memory", memory(context));
            root.put("disk", disk(context));
            root.put("thermal", thermal(context));
            root.put("packages", packages(context));

            root.put("display", display(context));
            root.put("usage", usage(context));
            root.put("network", network(context));

            JSONObject cpu = new JSONObject();
            putNullable(cpu, "approx_pct", null);
            root.put("cpu", cpu);

            return root.toString();
        } catch (Exception e) {
            JSONObject err = new JSONObject();
            try {
                err.put("ok", false);
                err.put("error", "status collection failed: " + e.getClass().getSimpleName());
            } catch (Exception ignored) {
            }
            return err.toString();
        }
    }

    private static JSONObject device() throws Exception {
        JSONObject d = new JSONObject();
        d.put("manufacturer", Build.MANUFACTURER);
        d.put("oem", Build.MANUFACTURER);
        d.put("brand", Build.BRAND);
        d.put("model", Build.MODEL);
        d.put("name", Build.DEVICE);
        d.put("product", Build.PRODUCT);
        d.put("android", Build.VERSION.RELEASE);
        d.put("sdk", Build.VERSION.SDK_INT);
        d.put("build", Build.DISPLAY);
        return d;
    }

    private static JSONObject battery(Context context) throws Exception {
        JSONObject b = new JSONObject();
        Intent intent = null;
        try {
            IntentFilter filter = new IntentFilter(Intent.ACTION_BATTERY_CHANGED);
            if (Build.VERSION.SDK_INT >= 33) {
                intent = context.registerReceiver(null, filter, Context.RECEIVER_NOT_EXPORTED);
            } else {
                intent = context.registerReceiver(null, filter);
            }
        } catch (Exception e) {
            Log.w(TAG, "battery receiver failed", e);
        }
        if (intent == null) {
            putNullable(b, "level", null);
            putNullable(b, "status", null);
            putNullable(b, "plugged", null);
            putNullable(b, "health", null);
            putNullable(b, "temp_c", null);
            putNullable(b, "voltage_mv", null);
            putNullable(b, "present", null);
            putNullable(b, "technology", null);
        } else {
            int level = intent.getIntExtra(BatteryManager.EXTRA_LEVEL, -1);
            int scale = intent.getIntExtra(BatteryManager.EXTRA_SCALE, 100);
            int pct = (level >= 0 && scale > 0) ? Math.round(level * 100f / scale) : -1;
            putNullable(b, "level", pct >= 0 ? pct : null);
            putNullable(b, "status", statusName(intent.getIntExtra(BatteryManager.EXTRA_STATUS, -1)));
            putNullable(b, "plugged", pluggedName(intent.getIntExtra(BatteryManager.EXTRA_PLUGGED, 0)));
            putNullable(b, "health", healthName(intent.getIntExtra(BatteryManager.EXTRA_HEALTH, -1)));
            int temp = intent.getIntExtra(BatteryManager.EXTRA_TEMPERATURE, Integer.MIN_VALUE);
            putNullable(b, "temp_c", temp == Integer.MIN_VALUE ? null : (temp / 10.0));
            int voltage = intent.getIntExtra(BatteryManager.EXTRA_VOLTAGE, -1);
            putNullable(b, "voltage_mv", voltage > 0 ? voltage : null);
            putNullable(b, "present", intent.getBooleanExtra(BatteryManager.EXTRA_PRESENT, false));
            putNullable(b, "technology", emptyToNull(intent.getStringExtra(BatteryManager.EXTRA_TECHNOLOGY)));
        }

        BatteryManager bm = (BatteryManager) context.getSystemService(Context.BATTERY_SERVICE);
        if (bm != null) {
            int current = bm.getIntProperty(BatteryManager.BATTERY_PROPERTY_CURRENT_NOW);
            putNullable(b, "current_ma", current == Integer.MIN_VALUE ? null : current / 1000.0);
            long charge = bm.getLongProperty(BatteryManager.BATTERY_PROPERTY_CHARGE_COUNTER);
            putNullable(b, "charge_counter", charge > 0 ? charge : null);
        }
        return b;
    }

    private static JSONObject wifi(Context context) throws Exception {
        JSONObject w = new JSONObject();
        WifiManager wm = (WifiManager) context.getApplicationContext()
                .getSystemService(Context.WIFI_SERVICE);
        WifiInfo info = wm == null ? null : wm.getConnectionInfo();
        if (info == null) {
            putNullable(w, "ssid", null);
            putNullable(w, "bssid", null);
            putNullable(w, "ip", null);
            putNullable(w, "rssi", null);
            putNullable(w, "link_mbps", null);
            putNullable(w, "freq_mhz", null);
            return w;
        }
        String ssid = info.getSSID();
        if (ssid != null) {
            ssid = ssid.replace("\"", "");
            if (ssid.startsWith("0x") || "<unknown ssid>".equals(ssid) || ssid.isEmpty()) ssid = null;
        }
        putNullable(w, "ssid", ssid);
        putNullable(w, "bssid", emptyToNull(info.getBSSID()));
        int ip = info.getIpAddress();
        putNullable(w, "ip", ip == 0 ? null : ipString(ip));
        int rssi = info.getRssi();
        putNullable(w, "rssi", rssi);
        int link = info.getLinkSpeed();
        putNullable(w, "link_mbps", link > 0 ? link : null);
        int freq = info.getFrequency();
        putNullable(w, "freq_mhz", freq > 0 ? freq : null);
        return w;
    }

    private static JSONObject memory(Context context) throws Exception {
        JSONObject m = new JSONObject();
        ActivityManager am = (ActivityManager) context.getSystemService(Context.ACTIVITY_SERVICE);
        ActivityManager.MemoryInfo mi = new ActivityManager.MemoryInfo();
        if (am != null) am.getMemoryInfo(mi);
        long totalMb = Bytes.mb(mi.totalMem);
        long availMb = Bytes.mb(mi.availMem);
        putNullable(m, "total_mb", totalMb > 0 ? totalMb : null);
        putNullable(m, "available_mb", availMb > 0 ? availMb : null);
        putNullable(m, "low_memory", am != null ? mi.lowMemory : null);
        putNullable(m, "swap_total_mb", null);
        putNullable(m, "swap_free_mb", null);
        return m;
    }

    private static JSONObject disk(Context context) throws Exception {
        JSONObject d = new JSONObject();
        StatFs fs = new StatFs("/data");
        long total = fs.getBlockCountLong() * fs.getBlockSizeLong();
        long free = fs.getAvailableBlocksLong() * fs.getBlockSizeLong();
        putNullable(d, "total_gb", round1(Bytes.gb(total)));
        putNullable(d, "free_gb", round1(Bytes.gb(free)));
        putNullable(d, "used_pct", total > 0 ? round1((total - free) * 100.0 / total) : null);
        return d;
    }

    private static JSONObject thermal(Context context) throws Exception {
        JSONObject t = new JSONObject();
        Intent battery = null;
        try {
            IntentFilter filter = new IntentFilter(Intent.ACTION_BATTERY_CHANGED);
            if (Build.VERSION.SDK_INT >= 33) {
                battery = context.registerReceiver(null, filter, Context.RECEIVER_NOT_EXPORTED);
            } else {
                battery = context.registerReceiver(null, filter);
            }
        } catch (Exception ignored) {
        }
        int temp = battery == null ? Integer.MIN_VALUE
                : battery.getIntExtra(BatteryManager.EXTRA_TEMPERATURE, Integer.MIN_VALUE);
        putNullable(t, "battery_c", temp == Integer.MIN_VALUE ? null : temp / 10.0);
        putNullable(t, "max_c", temp == Integer.MIN_VALUE ? null : temp / 10.0);
        putNullable(t, "cpu_c", null);
        PowerManager pm = (PowerManager) context.getSystemService(Context.POWER_SERVICE);
        String status = null;
        if (pm != null && Build.VERSION.SDK_INT >= 29) {
            status = thermalStatus(pm.getCurrentThermalStatus());
        }
        putNullable(t, "status", status);
        return t;
    }

    private static JSONObject packages(Context context) throws Exception {
        PackageManager pm = context.getPackageManager();
        int count = pm.getInstalledPackages(0).size();
        JSONObject p = new JSONObject();
        p.put("count", count);
        return p;
    }

    private static JSONObject display(Context context) throws Exception {
        JSONObject d = new JSONObject();
        PowerManager pm = (PowerManager) context.getSystemService(Context.POWER_SERVICE);
        putNullable(d, "interactive", pm == null ? null : pm.isInteractive());
        KeyguardManager km = (KeyguardManager) context.getSystemService(Context.KEYGUARD_SERVICE);
        putNullable(d, "locked", km == null ? null : km.isKeyguardLocked());
        DisplayManager dm = (DisplayManager) context.getSystemService(Context.DISPLAY_SERVICE);
        if (dm != null) {
            android.view.Display display = dm.getDisplay(android.view.Display.DEFAULT_DISPLAY);
            if (display != null) {
                android.view.Display.Mode mode = display.getMode();
                putNullable(d, "refresh_hz", mode == null ? null : mode.getRefreshRate());
            }
        }
        int brightness = -1;
        try {
            brightness = Settings.System.getInt(context.getContentResolver(), Settings.System.SCREEN_BRIGHTNESS, -1);
        } catch (Exception ignored) {
        }
        putNullable(d, "brightness", brightness >= 0 ? brightness : null);
        return d;
    }

    private static JSONObject usage(Context context) throws Exception {
        JSONObject u = new JSONObject();
        String foreground = null;
        boolean available = false;
        try {
            UsageStatsManager usm = (UsageStatsManager) context.getSystemService(Context.USAGE_STATS_SERVICE);
            if (usm != null) {
                long now = System.currentTimeMillis();
                UsageEvents events = usm.queryEvents(now - 60 * 1000L, now);
                if (events != null) {
                    UsageEvents.Event e = new UsageEvents.Event();
                    while (events.hasNextEvent()) {
                        events.getNextEvent(e);
                        if (e.getEventType() == UsageEvents.Event.ACTIVITY_RESUMED
                                || e.getEventType() == UsageEvents.Event.MOVE_TO_FOREGROUND) {
                            foreground = e.getPackageName();
                        }
                    }
                    available = true;
                }
            }
        } catch (Exception ignored) {
        }
        putNullable(u, "foreground", foreground);
        putNullable(u, "available", available);
        return u;
    }

    private static JSONObject network(Context context) throws Exception {
        JSONObject n = new JSONObject();
        long rx = TrafficStats.getTotalRxBytes();
        long tx = TrafficStats.getTotalTxBytes();
        putNullable(n, "rx_bytes", rx == TrafficStats.UNSUPPORTED ? null : rx);
        putNullable(n, "tx_bytes", tx == TrafficStats.UNSUPPORTED ? null : tx);
        n.put("since_boot", true);
        return n;
    }

    private static String ipString(int ip) {
        return String.format(Locale.US, "%d.%d.%d.%d",
                (ip & 0xff), (ip >> 8) & 0xff, (ip >> 16) & 0xff, (ip >> 24) & 0xff);
    }

    private static String statusName(int status) {
        switch (status) {
            case BatteryManager.BATTERY_STATUS_CHARGING: return "CHARGING";
            case BatteryManager.BATTERY_STATUS_DISCHARGING: return "DISCHARGING";
            case BatteryManager.BATTERY_STATUS_FULL: return "FULL";
            case BatteryManager.BATTERY_STATUS_NOT_CHARGING: return "NOT_CHARGING";
            default: return null;
        }
    }

    private static String pluggedName(int plugged) {
        switch (plugged) {
            case BatteryManager.BATTERY_PLUGGED_AC: return "PLUGGED_AC";
            case BatteryManager.BATTERY_PLUGGED_USB: return "PLUGGED_USB";
            case BatteryManager.BATTERY_PLUGGED_WIRELESS: return "PLUGGED_WIRELESS";
            default: return "UNPLUGGED";
        }
    }

    private static String healthName(int health) {
        switch (health) {
            case BatteryManager.BATTERY_HEALTH_GOOD: return "GOOD";
            case BatteryManager.BATTERY_HEALTH_OVERHEAT: return "OVERHEAT";
            case BatteryManager.BATTERY_HEALTH_DEAD: return "DEAD";
            case BatteryManager.BATTERY_HEALTH_OVER_VOLTAGE: return "OVER_VOLTAGE";
            case BatteryManager.BATTERY_HEALTH_COLD: return "COLD";
            default: return null;
        }
    }

    private static String thermalStatus(int status) {
        switch (status) {
            case PowerManager.THERMAL_STATUS_NONE: return "NONE";
            case PowerManager.THERMAL_STATUS_LIGHT: return "LIGHT";
            case PowerManager.THERMAL_STATUS_MODERATE: return "MODERATE";
            case PowerManager.THERMAL_STATUS_SEVERE: return "SEVERE";
            case PowerManager.THERMAL_STATUS_CRITICAL: return "CRITICAL";
            case PowerManager.THERMAL_STATUS_EMERGENCY: return "EMERGENCY";
            case PowerManager.THERMAL_STATUS_SHUTDOWN: return "SHUTDOWN";
            default: return null;
        }
    }

    private static String isoNow() {
        SimpleDateFormat f = new SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss'Z'", Locale.US);
        f.setTimeZone(TimeZone.getTimeZone("UTC"));
        return f.format(new Date());
    }

    private static String emptyToNull(String s) {
        return (s == null || s.isEmpty()) ? null : s;
    }

    private static double round1(double v) {
        return Math.round(v * 10.0) / 10.0;
    }

    private static void putNullable(JSONObject o, String key, Object value) throws Exception {
        o.put(key, value == null ? JSONObject.NULL : value);
    }

    private static final class Bytes {
        static long mb(long b) { return b / (1024L * 1024L); }
        static double gb(long b) { return b / (1024.0 * 1024.0 * 1024.0); }
    }
}
