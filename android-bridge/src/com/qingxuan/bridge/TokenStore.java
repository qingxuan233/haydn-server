package com.qingxuan.bridge;

import android.content.Context;
import android.util.Base64;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.nio.charset.StandardCharsets;
import java.security.SecureRandom;

/** Runtime-generated pairing token; debug provisioning reads it via adb run-as. */
final class TokenStore {
    private static final String FILE = "bridge.token";

    private TokenStore() {}

    static synchronized String token(Context context) {
        File f = new File(context.getFilesDir(), FILE);
        try {
            if (f.exists()) {
                byte[] buf = new byte[(int) f.length()];
                FileInputStream in = new FileInputStream(f);
                try {
                    int n = in.read(buf);
                    if (n > 16) {
                        String s = new String(buf, 0, n, StandardCharsets.US_ASCII).trim();
                        if (!s.isEmpty()) return s;
                    }
                } finally {
                    in.close();
                }
            }
            byte[] raw = new byte[32];
            new SecureRandom().nextBytes(raw);
            String value = Base64.encodeToString(raw,
                    Base64.URL_SAFE | Base64.NO_WRAP | Base64.NO_PADDING);
            FileOutputStream out = new FileOutputStream(f);
            try {
                out.write(value.getBytes(StandardCharsets.US_ASCII));
                out.getFD().sync();
            } finally {
                out.close();
            }
            return value;
        } catch (Exception e) {
            throw new IllegalStateException("cannot provision token", e);
        }
    }
}
