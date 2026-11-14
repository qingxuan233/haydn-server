---
id: APP-001
title: 一加 Ace Pro 案例附录：P1 管理面配置要点（2026-11-14 快照）
type: case-study
status: current
audience: human, agent
tags: case, oneplus-ace-pro, p1, config, snapshot, appendix
depends: CASE-003
updated: 2026-11-14
agent_hint: CASE-003 的结构性附录，只承载 P1 配置快照与回滚命令；设备事实、结论与未完成项一律以 CASE-003 正文为准。
---

# APP-001 · P1 管理面配置要点（附录）

> 本文件由 [CASE-003](README.md) §6.3 于 2026-11-14 **原样下沉**（用户授权结构拆分；事实、结论与未完成项未改写）；验收结论与未完成项以 CASE-003 正文为准。设备侧 shell 脚本必须**以 LF 文本经 `adb push` 部署**，部署后跑 `sh -n` 校验并核对进程存活/下一采集周期；本批曾因脚本转写问题导致遥测循环静默退出（见 CASE-003 §6.2）。以下为 2026-11-14 实测配置摘要；完整运行期脚本/日志在 gitignored `inventory/`，改动前快照见 `inventory/device-snapshot-20261114/`。所有改动可按文末命令回滚。

## 1. 配置摘要

**KernelSU 模块 `service.sh`（开机持久化）**：
```sh
# P1: keep CPU awake + disable Wi-Fi power save（可回滚）
echo haydn-server > /sys/power/wake_lock
i=0
while [ "$i" -lt 10 ]; do
  iw dev wlan0 set power_save off >/dev/null 2>&1 && break
  i=$((i + 1)); sleep 3
done
```

**sshd（仅 loopback、密钥登录）** `/data/server/rootfs/etc/ssh/sshd_config.d/99-haydn.conf`：
```text
PasswordAuthentication no
KbdInteractiveAuthentication no
PubkeyAuthentication yes
PermitRootLogin prohibit-password
ListenAddress 127.0.0.1
X11Forwarding no
PermitEmptyPasswords no
```

**supervisord 程序**（追加到 `/etc/supervisor/conf.d/haydn.conf`）：
```text
haydn-sshd            command=/usr/sbin/sshd -D
haydn-node-exporter   command=/usr/bin/prometheus-node-exporter --web.listen-address=127.0.0.1:9100
haydn-cron            command=/usr/sbin/cron -f
haydn-tailscaled      command=/usr/local/bin/tailscaled --tun=userspace-networking --socks5-server=127.0.0.1:1055 --state=/var/lib/tailscale/tailscaled.state --socket=/var/run/tailscale/tailscaled.sock
```

**健康检查与告警**：cron `*/5 * * * * root /usr/local/bin/haydn-healthcheck.sh`（检查 supervisor/http/node_exporter/sshd/disk，OK/FAIL 写 `/var/log/haydn/health.log`）；telemetry-loop 每 5 分钟调用 `alert-watch.sh`，FAIL 时发 Android 通知并写 `/data/server/logs/alerts.log`（同一 FAIL 行去重，恢复后自动清状态）。

**Tailscale（登录与 tailnet SSH 入口，密钥不入库）**：
```sh
# 登录：auth key 用 file: 方式传递，避免出现在命令行/日志
# （先把 key 放在 chroot 内临时文件 /tmp/.tskey，用完立即删除）
/data/server/bin/chroot-enter.sh /usr/local/bin/tailscale up \
  --auth-key=file:/tmp/.tskey --hostname=haydn-pgp110 --accept-dns=false

# tailnet 内 TCP 转发 :22 -> 本机 loopback sshd（tailnet-only）
/data/server/bin/chroot-enter.sh /usr/local/bin/tailscale serve --bg --tcp 22 tcp://127.0.0.1:22
/data/server/bin/chroot-enter.sh /usr/local/bin/tailscale serve status
```

**验收/回滚命令**：
```sh
# 验收（只读）
iw dev wlan0 get power_save                       # 期望 Power save: off
/data/server/bin/chroot-enter.sh sh -c 'ss -ltn'  # 期望仅 127.0.0.1:22/9100/1055/18080
/data/server/bin/chroot-enter.sh /usr/bin/supervisorctl -c /etc/supervisor/supervisord.conf status  # 6 服务 RUNNING
iptables -S INPUT | head                          # 期望 -P INPUT DROP + haydnlab 白名单

# 回滚
echo haydn-server > /sys/power/wake_unlock
iw dev wlan0 set power_save on
# 停用单个服务：supervisorctl -c /etc/supervisor/supervisord.conf stop haydn-tailscaled
```

## 2. 关联

- 正文：[CASE-003](README.md)（关键事实/时间线/验收与未完成项）· [OEM profile](oem-profile.md) · [profile.json](profile.json)
- 规范：[MTH-012 Root 实验方法论](../../methodology/11-root-lab.md) · [GRD-015 Root 实验受控](../../guardrails/GRD-015-root-lab-controlled.md)
