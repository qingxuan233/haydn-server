# 26 · Console 手机状态补全（Termux:API + 综合采集）

> 日期：2026-11-10 22:25–22:55
> 范围：机器本地，无 Root；不接外部服务。

## 1. 目标与结论

目标：让 Console 从“只有 Linux/proot 指标 + 少量 Android 信息”升级为**尽可能完整的手机状态面板**。

结论：
- ✅ 已接入：机型/设备名、Android 版本/SDK/版本号、电池（电量/状态/充电/健康/温度/电压/电流/循环）、WiFi（IP/BSSID/RSSI/链路速率/频段，SSID 被系统隐藏）、Swap、热区（最高/CPU/电池）、应用包数、CPU/内存/磁盘/温度/运行时长。
- ⚠️ 无 Root 硬边界仍不可得：`/proc/stat`（逐核 CPU 精确）、`/proc/net/dev`（网络吞吐字节）、屏幕亮度/锁屏状态、前台应用。
- ⚠️ **重启后 Termux:API App 需手动打开一次**（见 §4）；否则电池/WiFi 字段为空，Console 显示“重启后打开一次 Termux:API”。

## 2. 实施内容

### 2.1 Termux 侧组件

- 安装 **Termux:API App v0.53.0**（APK，GitHub release，经镜像下载，8.85MB）。
- `pkg install termux-api` = **0.60.0**；`pkg install jq` = **1.8.2**。
- 新增采集器 `scripts/termux-metrics.sh`：每 10s 写 `$HOME/termux-status.txt`（key=value），包含：
  - `model/device/android/sdk/build`
  - `uptime_line/cpu_line/task_line`
  - `mem_total_kb/mem_available_kb/swap_total_kb/swap_free_kb`
  - `disk_total_kb/disk_used_kb/disk_free_kb/disk_used_pct`
  - `package_count`
  - `thermal_max_c/thermal_cpu_c/thermal_battery_c`
  - `battery_level/status/health/plugged/temp_c/voltage_mv/current_ma/cycle`
  - `wifi_ssid/bssid/ip/rssi/link_speed_mbps/frequency_mhz`
- 保留旧 `server-metrics.txt`（uptime/cpu）兼容。
- Boot 脚本：`00-server.sh` 已启动采集器；新增 `01-termux-api.sh` 尽力尝试启动 Termux:API App。

### 2.2 Console 侧

- `console-api.py` 新增 `TERMUX_STATUS=/hosthome/termux-status.txt`，`termux_metrics()` 优先读新文件（120s 新鲜度），字段注入 `/api/sysinfo`。
- `/api/sysinfo` 新增：`device_model/device_name/android_version/android_sdk/build_id/battery_*/wifi_*/package_count/swap_*/thermal_*`。
- UI 增加：
  - “机型 / Android”行
  - “WiFi”行（IP/RSSI/链路速率；SSID 隐藏时提示）
  - 电池详情（电量/状态/充电/温度/健康）
  - 页头温度卡同步电池温度
  - 电池/WiFi 缺失时提示“重启后打开一次 Termux:API”

## 3. 验证（本机实测）

`GET /api/sysinfo`：

```text
device_model=M2012K11C  device_name=haydn
android_version=14  android_sdk=34  build_id=V816.0.15.0.UKKCNXM
battery_level=100  battery_status=FULL  battery_plugged=PLUGGED_AC
battery_temp_c=27.0  battery_health=GOOD  battery_cycle=330
wifi_ip=192.168.10.159  wifi_rssi=-33  wifi_link_speed_mbps=573  wifi_frequency_mhz=5745
wifi_ssid=<unknown ssid>  package_count=358
swap_total_mb=6144  swap_free_mb=4833
thermal_max_c=37.0  thermal_cpu_c=34.8  thermal_battery_c=27.0
```

页面含 `d-device`/`d-wifi`/电池提示；API 返回 200。

## 4. 重启后的限制与处理

- Termux:API App **没有可用的 BOOT_COMPLETED receiver**；Termux 侧 `am start` 受 Android 后台启动限制拦截，ADB shell 才能拉起。
- 因此**重启后需手动打开一次 Termux:API App**（桌面图标），采集器下一轮（≤10s）即可恢复电池/WiFi。
- 无 Root 下无法可靠自动化这一步；若以后需要全自动，可评估专用 boot receiver 小工具或外部 ADB 助手（当前按“机器本地”范围未做）。
- 重启后 model/Android/包数/热区/内存/磁盘仍正常采集（不依赖 API App）。

## 5. 复用步骤

1. 安装 APK：`tools/apks/termux-api.apk`（或用 GitHub v0.53.0 release）；
   `miui-adb-install.ps1 -Apk tools/apks/termux-api.apk`。
2. Termux 内：
   ```bash
   pkg install -y termux-api jq
   ```
3. 复制 `scripts/termux-metrics.sh` 到 `$HOME/termux-metrics.sh` 并 `chmod 755`；Boot 脚本已有启动行。
4. 把 `scripts/termux-boot-01-api.sh` 放到 `$HOME/.termux/boot/01-termux-api.sh`（可选的尽力拉起）。
5. 部署 Console：`scripts/server/console-api.py`、`scripts/server/console/index.html`，重启 api。
6. 验证 `/api/sysinfo` 新字段与页面。

## 6. 回滚

- Console：`/root/server/api/app.py.bak-status-20261110-2239`、`/root/server/www/index.html.bak-status-20261110-2239`，恢复后 `server-ops restart api --confirm`。
- Termux 采集：恢复旧 `termux-metrics.sh`（git 历史）；Termux:API 组件可保留，不影响服务器。
- 不涉及 Android 系统包卸载/Gate B0。

## 7. 文件

- `scripts/termux-metrics.sh`
- `scripts/termux-boot-01-api.sh`
- `scripts/server/console-api.py`
- `scripts/server/console/index.html`
- 关联：docs/25（ADB 资源优化）、docs/13（Console 功能）
