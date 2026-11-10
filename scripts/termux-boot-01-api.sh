#!/data/data/com.termux/files/usr/bin/bash
# Termux:Boot: 启动 Termux:API App，确保 termux-battery-status / wifi 可用
export PREFIX=/data/data/com.termux/files/usr
export PATH="$PREFIX/bin:$PATH"
export LD_LIBRARY_PATH="$PREFIX/lib"
termux-wake-lock 2>/dev/null || true
"$PREFIX/bin/am" start -n com.termux.api/.activities.TermuxAPILauncherActivity >/dev/null 2>&1 || true
timeout 20 "$PREFIX/bin/termux-battery-status" >/dev/null 2>&1 || true
