package com.qingxuan.bridge;

import android.content.Context;
import android.util.Log;

import java.io.BufferedInputStream;
import java.io.BufferedOutputStream;
import java.io.BufferedReader;
import java.io.FileInputStream;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.net.Socket;
import java.net.SocketTimeoutException;
import java.nio.charset.StandardCharsets;
import java.security.KeyStore;
import java.security.MessageDigest;
import java.security.SecureRandom;
import java.util.HashMap;
import java.util.Map;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;

import javax.net.ssl.KeyManagerFactory;
import javax.net.ssl.SSLContext;
import javax.net.ssl.SSLServerSocket;
import javax.net.ssl.SSLServerSocketFactory;

/** Tiny read-only HTTPS server bound to loopback only. No external dependencies. */
final class LocalHttpsServer {
    private static final String TAG = "BridgeHttps";
    static final int PORT = 3099;
    private static final String TLS_PASSWORD = "BrdgTls2026!";

    private final Context context;
    private volatile boolean running;
    private SSLServerSocket serverSocket;
    private Thread acceptThread;
    private ExecutorService pool;

    LocalHttpsServer(Context context) {
        this.context = context.getApplicationContext();
    }

    void start() throws Exception {
        KeyStore ks = KeyStore.getInstance("PKCS12");
        InputStream in = context.getAssets().open("bridge.p12");
        try {
            ks.load(in, TLS_PASSWORD.toCharArray());
        } finally {
            in.close();
        }
        KeyManagerFactory kmf = KeyManagerFactory.getInstance(
                KeyManagerFactory.getDefaultAlgorithm());
        kmf.init(ks, TLS_PASSWORD.toCharArray());

        SSLContext ssl = SSLContext.getInstance("TLS");
        ssl.init(kmf.getKeyManagers(), null, new SecureRandom());
        SSLServerSocketFactory factory = ssl.getServerSocketFactory();
        SSLServerSocket socket = (SSLServerSocket) factory.createServerSocket();
        socket.setReuseAddress(true);
        socket.bind(new InetSocketAddress(InetAddress.getByName("127.0.0.1"), PORT));
        socket.setSoTimeout(30000);
        this.serverSocket = socket;
        this.pool = Executors.newCachedThreadPool();
        this.running = true;

        acceptThread = new Thread(new Runnable() {
            @Override
            public void run() {
                acceptLoop();
            }
        }, "bridge-accept");
        acceptThread.setDaemon(true);
        acceptThread.start();
    }

    void stop() {
        running = false;
        try {
            if (serverSocket != null) serverSocket.close();
        } catch (Exception ignored) {
        }
        if (pool != null) {
            pool.shutdownNow();
            try {
                pool.awaitTermination(2, TimeUnit.SECONDS);
            } catch (InterruptedException ignored) {
                Thread.currentThread().interrupt();
            }
        }
    }

    private void acceptLoop() {
        while (running) {
            try {
                Socket s = serverSocket.accept();
                final Socket client = s;
                pool.execute(new Runnable() {
                    @Override
                    public void run() {
                        handle(client);
                    }
                });
            } catch (SocketTimeoutException ignored) {
                // periodic chance to observe running=false
            } catch (Exception e) {
                if (running) Log.w(TAG, "accept failed", e);
            }
        }
    }

    private void handle(Socket socket) {
        try {
            socket.setSoTimeout(5000);
            BufferedReader reader = new BufferedReader(new InputStreamReader(
                    socket.getInputStream(), StandardCharsets.UTF_8));
            String requestLine = reader.readLine();
            if (requestLine == null || requestLine.isEmpty()) {
                return;
            }
            Map<String, String> headers = new HashMap<String, String>();
            String line;
            while ((line = reader.readLine()) != null && !line.isEmpty()) {
                int colon = line.indexOf(':');
                if (colon > 0) {
                    headers.put(line.substring(0, colon).trim().toLowerCase(),
                            line.substring(colon + 1).trim());
                }
            }
            String[] parts = requestLine.split(" ");
            if (parts.length < 2) {
                writeResponse(socket, 400, "Bad Request", "{\"ok\":false,\"error\":\"bad request\"}");
                return;
            }
            if (!"GET".equals(parts[0])) {
                writeResponse(socket, 405, "Method Not Allowed",
                        "{\"ok\":false,\"error\":\"GET only\"}");
                return;
            }
            String path = parts[1];
            int q = path.indexOf('?');
            if (q >= 0) path = path.substring(0, q);

            if ("/v1/health".equals(path)) {
                writeResponse(socket, 200, "OK",
                        "{\"ok\":true,\"service\":\"bridge\",\"version\":\"1.0.0\","
                                + "\"schema\":\"bridge.status.v1\",\"source\":\"android\"}");
                return;
            }
            if ("/v1/version".equals(path)) {
                writeResponse(socket, 200, "OK",
                        "{\"ok\":true,\"version\":\"1.0.0\",\"schema\":\"bridge.status.v1\"}");
                return;
            }
            if ("/v1/status".equals(path)) {
                if (!authorized(headers.get("authorization"))) {
                    writeResponse(socket, 401, "Unauthorized",
                            "{\"ok\":false,\"error\":\"invalid or missing token\"}");
                    return;
                }
                String body = BridgeStatus.json(context);
                writeResponse(socket, 200, "OK", body);
                return;
            }
            writeResponse(socket, 404, "Not Found",
                    "{\"ok\":false,\"error\":\"not found\"}");
        } catch (Exception e) {
            Log.w(TAG, "request failed", e);
        } finally {
            try {
                socket.close();
            } catch (Exception ignored) {
            }
        }
    }

    private boolean authorized(String authorization) {
        if (authorization == null || !authorization.startsWith("Bearer ")) return false;
        String provided = authorization.substring("Bearer ".length()).trim();
        String expected = TokenStore.token(context);
        return MessageDigest.isEqual(
                expected.getBytes(StandardCharsets.US_ASCII),
                provided.getBytes(StandardCharsets.US_ASCII));
    }

    private static void writeResponse(Socket socket, int code, String reason, String body) {
        try {
            byte[] payload = body.getBytes(StandardCharsets.UTF_8);
            OutputStream out = new BufferedOutputStream(socket.getOutputStream());
            String headers = "HTTP/1.1 " + code + " " + reason + "\r\n"
                    + "Content-Type: application/json; charset=utf-8\r\n"
                    + "Content-Length: " + payload.length + "\r\n"
                    + "Connection: close\r\n"
                    + "Cache-Control: no-store\r\n"
                    + "\r\n";
            out.write(headers.getBytes(StandardCharsets.US_ASCII));
            out.write(payload);
            out.flush();
        } catch (Exception e) {
            Log.w(TAG, "write failed", e);
        }
    }
}
