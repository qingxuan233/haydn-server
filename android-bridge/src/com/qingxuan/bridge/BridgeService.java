package com.qingxuan.bridge;

import android.app.Activity;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.Service;
import android.content.Intent;
import android.content.pm.ServiceInfo;
import android.os.Build;
import android.os.IBinder;
import android.util.Log;

/** Foreground service hosting the loopback HTTPS bridge. */
public class BridgeService extends Service {
    static final String CHANNEL_ID = "bridge";
    static final int NOTIFICATION_ID = 1099;
    private static final String TAG = "BridgeService";
    private LocalHttpsServer server;

    @Override
    public void onCreate() {
        super.onCreate();
        Log.i(TAG, "onCreate");
        createChannel();
        startForegroundCompat();
        Log.i(TAG, "onCreate after foreground");
        try {
            TokenStore.token(this);
            server = new LocalHttpsServer(this);
            server.start();
            Log.i(TAG, "bridge https server started on 127.0.0.1:3099");
        } catch (Throwable t) {
            Log.e(TAG, "cannot start bridge server", t);
            stopSelf();
        }
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        Log.i(TAG, "onStartCommand");
        startForegroundCompat();
        if (server == null) {
            try {
                TokenStore.token(this);
                server = new LocalHttpsServer(this);
                server.start();
            } catch (Throwable t) {
                Log.e(TAG, "cannot start bridge server", t);
            }
        }
        return START_STICKY;
    }

    @Override
    public void onDestroy() {
        if (server != null) {
            server.stop();
            server = null;
        }
        super.onDestroy();
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }

    private void createChannel() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return;
        NotificationChannel channel = new NotificationChannel(
                CHANNEL_ID, "Qingxuan Bridge", NotificationManager.IMPORTANCE_LOW);
        channel.setDescription("Phone telemetry bridge");
        NotificationManager nm = getSystemService(NotificationManager.class);
        if (nm != null) nm.createNotificationChannel(channel);
    }

    private void startForegroundCompat() {
        Notification.Builder b;
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            b = new Notification.Builder(this, CHANNEL_ID);
        } else {
            b = new Notification.Builder(this);
        }
        b.setSmallIcon(android.R.drawable.stat_sys_download_done)
                .setContentTitle("Qingxuan Bridge")
                .setContentText("Phone telemetry bridge is running")
                .setOngoing(true)
                .setPriority(Notification.PRIORITY_LOW);

        try {
            Log.i(TAG, "calling startForeground sdk=" + Build.VERSION.SDK_INT);
            if (Build.VERSION.SDK_INT >= 34) {
                startForeground(NOTIFICATION_ID, b.build(),
                        ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE);
            } else {
                startForeground(NOTIFICATION_ID, b.build());
            }
            Log.i(TAG, "startForeground returned");
        } catch (Throwable t) {
            Log.e(TAG, "startForeground failed", t);
            throw t;
        }
    }
}
