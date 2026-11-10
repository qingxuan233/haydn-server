# 32 · 多厂商 Android 适配与迁移指南

> 背景：当前机器是小米/Redmi，但未来接入的可能不是小米手机。Bridge / Server / DSH 的核心设计必须 **OEM-agnostic**，厂商差异只放在“适配 profile”，不能进入核心代码/数据契约。
> 关联：[docs/28 全栈规范](28-全栈整体方案规范.md) · [docs/31 拍板事项](31-拍板事项决策分析与Root升级路线.md) · [docs/30 接手指南](30-新会话接手指南.md)

---

## 1. 核心原则

1. **Bridge 包名固定为 `com.qingxuan.bridge`**（不含 `haydn`/`miui`/`xiaomi`；未来换机无需迁移包名）。
2. **核心只用标准 Android API/权限**：BatteryManager、WifiManager、UsageStats、NetworkStats、PackageManager、PowerManager、DisplayManager、Foreground Service、BOOT_COMPLETED。
3. **OEM 特有步骤只进 profile**：自启动、电池白名单、后台限制、安装弹窗等，不写成核心逻辑/API。
4. **Server 仍走 Termux + proot**：OEM 只影响 Termux:Boot 是否被放行、后台是否被杀；不改变 server 代码。
5. **Root 方案也厂商无关**：按“能否解锁 + 内核/社区 + Magisk/KernelSU/APatch 支持”选机，不按品牌写死。
6. **当前小米专属脚本/清单保留为 profile**：`miui-adb-install.ps1`、MIUI debloat 列表只用于当前设备，不进入通用路径。

---

## 2. 标准核心 vs OEM Profile

| 层 | 内容 | 是否设备无关 |
|---|---|---|
| Bridge 核心 | BootReceiver、specialUse FGS、loopback HTTPS、token/pin、Battery/Wifi/Build/Memory/Disk/Thermal/Packages | ✅ 全部通用 |
| Bridge 可选 | Usage/Network/Display/Keyguard | ✅ 标准 API，但 OEM 权限/行为有差异 |
| Server 核心 | Termux/proot Ubuntu、supervisord、nginx、DSH、Console、备份 | ✅ 通用（Termux 支持的 Android） |
| 自启 | Termux:Boot + BOOT_COMPLETED；OEM 白名单 | ⚠️ 通用机制 + OEM 差异 |
| 安装 | 标准 `adb install`；MIUI/HyperOS 弹窗需额外点按 | ⚠️ 通用 + 当前 profile |
| Root | Magisk/KernelSU/APatch/Sui/Shizuku | ⚠️ 取决于机型的解锁/内核/社区 |

---

## 3. OEM 适配矩阵（典型路径，实际以 ROM 为准）

> 目标：让 Bridge FGS + Termux 服务器在重启后自启、不被清理。**标准保障 = 电池优化白名单 + appops + deviceidle whitelist + 自启动/后台白名单**。

| 厂商/ROM | 安装 | 自启/保活（人工/ADB） | 备注 |
|---|---|---|---|
| **AOSP / Pixel / Nothing / Sony / Motorola** | 标准 `adb install` | 标准 BOOT_COMPLETED + FGS；电池优化设为“不限制” | 最接近标准；Termux:Boot 通常可用 |
| **小米 / Redmi / HyperOS / MIUI** | `miui-adb-install.ps1`（处理“继续安装”弹窗） | 设置→应用→自启动；省电策略“无限制”；允许后台弹出；`appops RUN_ANY_IN_BACKGROUND`、`deviceidle whitelist` | 当前设备 profile；MIUI 可能清理后台 |
| **Samsung One UI** | 标准 `adb install` | 电池→后台使用限制→“从不休眠的应用”；Device care 勿优化；`deviceidle whitelist` | 部分机型有自动优化；Knox 影响 Root |
| **OnePlus / OPPO / realme（ColorOS/OxygenOS）** | 标准 `adb install` | 电池→应用电池管理→允许后台活动；自启动/关联启动放行；`deviceidle whitelist` | 厂商后台策略较强 |
| **vivo / iQOO（OriginOS）** | 标准 `adb install` | 自启动管理放行；后台耗电管理/高耗电保护关闭；`deviceidle whitelist` | 部分型号限制较多 |
| **Huawei / Honor（EMUI/MagicOS）** | 标准 `adb install` | 应用启动管理→手动管理（允许自启动/关联启动/后台活动）；电池不优化 | Root 通常受限；先确认解锁 |
| **其他通用 Android** | 标准 `adb install` | 电池优化不限制 + `deviceidle whitelist` + 允许自启 | 以实测为准 |

**统一 ADB 基线（所有 OEM 先做）**：
```bash
adb install -r bridge.apk
adb shell pm grant <pkg> android.permission.POST_NOTIFICATIONS
adb shell pm grant <pkg> android.permission.ACCESS_FINE_LOCATION
adb shell cmd appops set <pkg> GET_USAGE_STATS allow       # 仅启用 Usage 时
adb shell cmd appops set <pkg> RUN_ANY_IN_BACKGROUND allow
adb shell dumpsys deviceidle whitelist +<pkg>
# 小米/部分 OEM 另有私有“自启动/后台弹出”开关，必须人工开
```

---

## 4. Server 自启在不同 OEM 的情况

- **Termux:Boot** 依赖 `BOOT_COMPLETED`；若 OEM 阻止自启，Termux 服务器不会自动恢复。
- 通用保障：
  1. 电池/自启动白名单（人工/ADB）；
  2. 5 次重启验证；
  3. 若仍失败且未来手机有 Root → Magisk `post-fs-data`/`service.d` 启动 Termux/server；
  4. 非 Root 可选：一个“Server Boot Starter”伴生 App 通过 Termux `RUN_COMMAND` 触发（需要权限/签名/安全评估，未列入当前 MVP）；
  5. 兜底：用户手动打开 Termux；文档明确该限制。
- **不要**假设 Termux:Boot 在所有 OEM 都可靠；必须把“Server 自启”纳入换机验收。

---

## 5. Root 选机矩阵（厂商无关的准入标准）

| 机型/品牌 | 解锁/Root 典型情况 | 备注 |
|---|---|---|
| Google Pixel | 官方 OEM 解锁；Magisk/KernelSU/APatch 社区成熟 | 首选试验机 |
| Nothing / Sony / Motorola | 多数支持官方解锁 | 需逐型号确认 |
| OnePlus | 部分型号/地区支持解锁 | OPPO 合并后政策变化，需查当前型号 |
| 小米/Redmi（国际版/部分老机型） | 部分可解锁；国行当前不可 | 当前 haydn 不可 |
| Samsung | 部分型号开发者选项 OEM 解锁；Knox 永久触发 | 需确认型号/地区 |
| OPPO / realme / vivo / iQOO | 多数限制/需深度测试/申请 | 先查解锁政策 |
| Huawei / Honor | 多数官方解锁关闭 | 通常不作为 Root 候选 |

**准入清单（比品牌更重要）**：
1. Bootloader 可解锁（官方/社区）；
2. Magisk / KernelSU / APatch 至少一种成熟且有更新；
3. 内核能力可验证（`/proc`、cgroup、zram；容器需 `USER_NS/PID_NS` 实测）；
4. Android 14+、A/B 分区、fastboot/recovery 可救砖；
5. ≥8GB RAM、≥256GB、散热可；
6. 接受 Play Integrity/银行/OTA 影响。

---

## 6. Root 后通用优化（不依赖厂商）

| 方向 | 内容 |
|---|---|
| 特权遥测 | root 读 `/proc/stat`、`/proc/net/dev`、cpufreq；dumpsys battery/wifi/power；settings/appops |
| 自启/持久化 | Magisk `post-fs-data`/`service.d`；Sui/Shizuku 自启；可选 priv-app（需权限 allowlist） |
| 系统级优化 | systemless freeze/debloat（不删 boot 必需包）、thermal/CPU governor、zram/IO |
| Bridge | `PrivilegedProvider`（Sui/Shizuku 或 root helper）；Bridge 主进程不写 `su` |
| Server | 可评估 chroot/systemd；容器仅在 custom kernel 支持 `USER_NS/PID_NS` 时尝试 |
| ADB | root 启动 adbd/Shizuku/Sui，不再依赖 PC |

> Root 方案使用的命令必须是 AOSP 通用命令（`cmd appops`、`settings`、`dumpsys`、`/proc`），**不得**写死 MIUI 私有命令。

---

## 7. 换机迁移清单

1. 新机：确认 BL 解锁/Root 计划、Android 版本、内存/存储、散热；
2. 安装 Termux + Termux:Boot；按 OEM profile 设自启/省电白名单；
3. 安装/构建 Bridge APK；标准 ADB 权限 + OEM 人工白名单；
4. 恢复服务器：按 docs/17 重建（或迁移 proot rootfs + 配置 + 备份）；
5. 配置 token/证书、Console、DSH；
6. 5 次重启 + 24h soak；检查 Termux 服务器、Bridge、DSH 三条链；
7. 记录 OEM profile 到 `profiles/oem/<manufacturer>.md`（未来可建配置目录）。

---

## 8. 当前设备 profile（保留，不进入通用核心）

- `miui-adb-install.ps1`：处理 MIUI/HyperOS “继续安装”弹窗（当前设备专用）。
- MIUI/小米 debloat 清单（docs/06）：当前设备专用，换机不照搬。
- 当前自启/省电设置（自启动、无限制省电、后台弹出）：当前设备 profile。
- 当前包名/路径：**Bridge 包名统一 `com.qingxuan.bridge`**，不随设备变。

---

## 9. 数据契约的 OEM 字段（可选）

Bridge `/v1/status` 可增加（可空，不影响现有服务端）：

```json
{
  "device": {
    "model": "...",
    "name": "...",
    "oem": "Xiaomi",
    "brand": "Redmi",
    "rom": "HyperOS 1.0",
    "android": "14",
    "sdk": 34
  }
}
```

- 优先 `Build.MANUFACTURER` / `Build.BRAND` / `Build.DISPLAY`；
- **不得**根据 OEM 硬编码行为；只作为展示/诊断；
- 服务端按字段存在性降级，不假定某厂商。

---

## 10. 风险

| 风险 | 说明 | 缓解 |
|---|---|---|
| OEM 自启/后台策略差异 | Termux/Bridge 被限制 | 标准 ADB 基线 + OEM profile + 5 次重启 |
| Termux:Boot 失效 | 服务器不自启 | Root Magisk 脚本 / 手动兜底 / 换机验收 |
| 厂商私有设置无标准 API | 无法完全自动化 | 以人工 profile 为准，不承诺自动 |
| Root 解锁政策 | 部分品牌不可解锁 | 选机按解锁/社区，不按品牌 |
| Play Integrity/OTA | Root 后部分 App 不可用 | 选机前确认接受 |
| 通用脚本误用 | MIUI 脚本用于其他 OEM | 脚本标注设备专用，核心路径用标准 adb |
