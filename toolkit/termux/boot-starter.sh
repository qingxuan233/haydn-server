#!/usr/bin/env bash
# toolkit/termux/boot-starter.sh
# 用途：Termux:Boot 自启链的安全引导脚本（幂等、可 dry-run、可中断）。
#       只负责"等待 → 加锁 → 启动指定命令 → 记录"，不修改系统、不写设备、不碰凭据。
# 用法：
#   bash toolkit/termux/boot-starter.sh --dry-run              # 只演练，不启动任何服务
#   bash toolkit/termux/boot-starter.sh                        # 默认启动 server-up（若存在）
#   bash toolkit/termux/boot-starter.sh --command server-up --wait 90 --log boot.log
#   bash toolkit/termux/boot-starter.sh --check                 # 仅检查前置条件
#   bash toolkit/termux/boot-starter.sh --help
# 参数：
#   --command <cmd>    要启动的命令（默认 $SERVER_START_CMD，否则自动探测 server-up）
#   --wait <sec>       启动前等待上限（默认 120；每 2 秒检查一次命令是否存在）
#   --log <path>       启动输出日志（默认 ./boot-starter.log；禁止绝对路径/..）
#   --check            仅检查前置条件并退出（不启动、不加锁）
#   --dry-run          打印将要执行的动作，不启动任何进程、不加锁、不写日志
#   --help             显示本帮助
# 退出码：0=成功/无需启动；1=前置条件或启动失败；2=用法错误；130=被中断（已清理锁）。
# 幂等：使用 mkdir 原子锁（同一时间只启动一次），异常中断由 trap 清理；重复执行安全。
# 安全：不硬编码凭据/IP/端口；启动命令由用户或环境变量提供；只追加日志。

set -u

START_CMD="${SERVER_START_CMD:-server-up}"
WAIT_SECONDS="120"
LOG_FILE="./boot-starter.log"
CHECK_ONLY=0
DRY_RUN=0
LOCK_DIR="${TMPDIR:-/tmp}/repurpose-boot-starter.lock"
LOCKED=0

usage() {
    sed -n '2,24p' "$0" | sed 's/^# \{0,1\}//'
}

while [ $# -gt 0 ]; do
    case "$1" in
        --command) START_CMD="${2:-}"; shift 2 || { echo "用法错误：--command 缺少参数" >&2; exit 2; } ;;
        --wait) WAIT_SECONDS="${2:-}"; shift 2 || { echo "用法错误：--wait 缺少参数" >&2; exit 2; } ;;
        --log) LOG_FILE="${2:-}"; shift 2 || { echo "用法错误：--log 缺少参数" >&2; exit 2; } ;;
        --check) CHECK_ONLY=1 ;;
        --dry-run) DRY_RUN=1 ;;
        --help|-h) usage; exit 0 ;;
        *) echo "用法错误：未知参数 $1（--help 查看用法）" >&2; exit 2 ;;
    esac
done

case "$WAIT_SECONDS" in *[!0-9]*|"") echo "用法错误：--wait 必须是整数秒" >&2; exit 2 ;; esac
[ "$WAIT_SECONDS" -le 600 ] || { echo "用法错误：--wait 不能超过 600 秒" >&2; exit 2; }
case "$LOG_FILE" in *..*|/*) echo "用法错误：--log 不能是绝对路径或包含 .." >&2; exit 2 ;; esac
[ -n "$START_CMD" ] || { echo "用法错误：--command 不能为空" >&2; exit 2; }

cleanup() {
    if [ "$LOCKED" -eq 1 ]; then
        rmdir "$LOCK_DIR" 2>/dev/null || true
        LOCKED=0
    fi
}
trap 'echo "boot-starter 被中断，已清理锁" >&2; cleanup; exit 130' INT TERM

log_line() {
    # 日志只写动作与结果，不写环境变量/凭据。
    [ "$DRY_RUN" -eq 1 ] && { printf '[dry-run] %s\n' "$1"; return; }
    printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || echo unknown-time)" "$1" >> "$LOG_FILE"
}

check_prereqs() {
    rc=0
    if command -v "$START_CMD" >/dev/null 2>&1; then
        echo "OK  命令可用：$START_CMD"
    else
        echo "WARN 未找到启动命令：$START_CMD（需先安装/配置或改用 --command）"
        rc=1
    fi
    if [ -n "${TERMUX_VERSION:-}" ] || [ -n "${PREFIX:-}" ]; then
        echo "OK  检测到 Termux 环境（PREFIX 已设置）"
    else
        echo "INFO 未检测到 Termux 环境变量（在 PC 上演练时属正常）"
    fi
    if [ -w "$(dirname "$LOG_FILE")" ]; then
        echo "OK  日志目录可写：$(dirname "$LOG_FILE")"
    else
        echo "WARN 日志目录不可写：$(dirname "$LOG_FILE")"
        rc=1
    fi
    if command -v termux-wake-lock >/dev/null 2>&1; then
        echo "OK  termux-wake-lock 可用（将申请后台保活）"
    else
        echo "INFO termux-wake-lock 不可用（非 Termux 环境或未安装 termux-api）"
    fi
    return "$rc"
}

if [ "$CHECK_ONLY" -eq 1 ]; then
    check_prereqs
    exit $?
fi

if [ "$DRY_RUN" -eq 1 ]; then
    echo "[dry-run] 前置检查："
    check_prereqs || true
    echo "[dry-run] 将等待命令可用：$START_CMD（最多 ${WAIT_SECONDS}s）"
    echo "[dry-run] 将加锁：$LOCK_DIR"
    echo "[dry-run] 将执行：termux-wake-lock（若可用）"
    echo "[dry-run] 将启动：$START_CMD（日志：$LOG_FILE）"
    exit 0
fi

# 幂等锁：mkdir 是原子操作；锁目录存在说明另一个启动流程正在进行/上次异常残留。
if mkdir "$LOCK_DIR" 2>/dev/null; then
    LOCKED=1
    printf '%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || echo unknown-time)" > "$LOCK_DIR/started_at" 2>/dev/null || true
else
    lock_age_s=0
    if [ -f "$LOCK_DIR/started_at" ]; then
        started="$(head -n 1 "$LOCK_DIR/started_at" 2>/dev/null || echo "")"
        now="$(date +%s 2>/dev/null || echo 0)"
        started_epoch="$(date -u -d "$started" +%s 2>/dev/null || echo 0)"
        [ "$now" -gt "$started_epoch" ] && lock_age_s=$((now - started_epoch))
    fi
    if [ "$lock_age_s" -gt 3600 ]; then
        echo "WARN 发现超过 1 小时的陈旧锁，清理后继续" >&2
        rm -rf "$LOCK_DIR" 2>/dev/null || true
        if mkdir "$LOCK_DIR" 2>/dev/null; then LOCKED=1; else
            echo "错误：无法获取启动锁（另一实例正在运行）" >&2; exit 1
        fi
    else
        echo "INFO 已有启动流程在执行（锁：$LOCK_DIR），本实例退出（幂等）"
        exit 0
    fi
fi

trap 'cleanup; exit 130' INT TERM
log_line "boot-starter 开始（等待命令：$START_CMD）"

# 等待启动命令可用（开机初期 PREFIX/PATH 可能尚未就绪）；有界等待，不无限重试。
waited=0
while ! command -v "$START_CMD" >/dev/null 2>&1; do
    if [ "$waited" -ge "$WAIT_SECONDS" ]; then
        log_line "WARN 等待 ${WAIT_SECONDS}s 后仍找不到启动命令，退出（不启动）"
        echo "错误：启动命令不可用：$START_CMD" >&2
        cleanup
        exit 1
    fi
    sleep 2
    waited=$((waited + 2))
done

if command -v termux-wake-lock >/dev/null 2>&1; then
    termux-wake-lock >/dev/null 2>&1 || log_line "WARN termux-wake-lock 调用失败（继续）"
    log_line "已申请 termux-wake-lock"
fi

log_line "启动命令：$START_CMD"
nohup "$START_CMD" >> "$LOG_FILE" 2>&1 &
child_pid=$!
log_line "已启动 pid=$child_pid（日志追加到 $LOG_FILE）"

# 只等待 5 秒粗检进程是否立刻退出；不阻塞开机流程，也不做无限重启。
sleep 5
if kill -0 "$child_pid" 2>/dev/null; then
    log_line "启动进程仍在运行，交给服务管理器/看门狗继续守护"
    cleanup
    exit 0
else
    log_line "WARN 启动命令在 5 秒内退出，请检查日志（可能是配置/依赖问题）"
    cleanup
    exit 1
fi
