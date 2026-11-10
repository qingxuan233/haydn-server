# raw-notes — Redmi K40 Pro（haydn / SM8350）Linux 服务器可行性：原始研究笔记

> 记录时间：2026-11-10（本机时钟，Asia/Shanghai）。任务要求「2025 年视角」，因此正文同时标注 2025–2026 的现状。
> 研究方式：本会话 `web_search` 工具因搜索插件 API Key 失效（HTTP 401）不可用；改用 `web_fetch` 直接抓取一手来源（项目 Wiki / 官方文档 / GitHub 官方仓库 / kernel.org 文档），并用 `cn.bing.com` 做少量补充检索。**所有关键结论都以下方链接的一手页面为准，未采信的搜索摘要。**
> 标注约定：✅=已核实（抓到一手页面原文）；❓=待验证（需上机 adb/sh 或需当时的厂商政策/社区公告确认）。

---

## 0. 工具与环境异常（留痕）

- `web_search` 返回：`DeepSeek API error (HTTP 401): Authentication Fails ... api key is invalid`（搜索插件 endpoint 配置问题，非本任务可控）。→ 全程改用 `web_fetch`。
- 部分站点不可达：`docs.docker.com`、`developer.android.com`（可换用大陆镜像 `developer.android.google.cn`）、`git.kernel.org`、`gsmarena.com`（Turnstile 人机校验）、DuckDuckGo/Brave/Mojeek（反爬或需 JS）。
- **重要发现（域名迁移）**：`wiki.postmarketos.org` 抓取时被 30x 跨域跳转到 `https://wiki.nura.eco`；该 Wiki 页面标题为「Nura Wiki」，正文仍保留 `PostmarketOS:` 命名空间与 `postmarketos` 内核包名。→ 说明 postmarketOS 项目在 2026 年已更名为/包装为 **Nura**（生态位、pmaports、pmbootstrap 均延续）。❓更名公告本身未抓到（只有 Wiki 首页/页脚证据），引用时写作「postmarketOS（现 Nura）」。

---

## 1. 代号与机型核实

| 项目 | 结论 | 证据 |
|---|---|---|
| Redmi K40 Pro 代号 | **haydn** ✅ | LineageOS Wiki `/devices/haydn/`：同一 build 覆盖 Mi 11i、**Redmi K40 Pro**、Redmi K40 Pro+、Mi 11X Pro 四个变体 |
| Redmi K40（非 Pro）代号 | **alioth**（POCO F3 / Redmi K40 / Mi 11X）✅ | Nura Wiki 设备页：alioth 芯片为 **SM8250-AC（骁龙 870）**，与 K40 Pro（SM8350）不同 |
| SM8350 平台代号 | **lahaina**（骁龙 888，Adreno 660，5nm，2021）✅ | Nura Wiki `Qualcomm Snapdragon 888 (SM8350)` |
| 任务描述里「可能 haydn 或 alioth」 | 需先上机确认：`adb shell getprop ro.product.device`。若是 `haydn` → 本报告结论；若是 `alioth` → 第 2 节须重估（见主报告 §1.3）❓ | — |

关键链接：
- https://wiki.lineageos.org/devices/haydn/ （变体选择页）
- https://wiki.lineageos.org/devices/haydn/variant2 （Redmi K40 Pro 变体）
- https://wiki.nura.eco/wiki/Xiaomi_POCO_F3_/_Redmi_K40_/_Mi_11X_(xiaomi-alioth)
- https://wiki.nura.eco/wiki/Qualcomm_Snapdragon_888_(SM8350)

---

## 2. 原生 Linux 移植（postmarketOS / Nura、mainline、Ubuntu Touch、Droidian、Mobian）

### 2.1 SM8350（骁龙 888）平台层
- Nura Wiki SoC 页字段：`Mainline | yes`；但组件逐项状态多为未验证/部分：
  - CPU：SMP（拉起全部核）、cpufreq、cpuidle → **Partial**
  - Storage（eMMC/UFS）→ **Works**；USB → **Partial**；Pinctrl → Works
  - Display / GPU / I²C / Audio / Video / Thermal / Wi-Fi / Bluetooth / Modem / Camera → **Untested**
- 该 SoC 的 pmOS 内核包路径显示在 **archived** 目录：`device/archived/linux-postmarketos-qcom-sm8350`（说明该 SoC 内核包被归档，不再是活跃开发主线的一部分）。✅ 来自页面链接文本。
- SoC 页列出的设备（2026-06 修订）：OnePlus 9 / 9 Pro（archived）、OnePlus 9RT（testing）、Realme GT 2（archived）、Samsung Galaxy S21 FE 5G / Z Flip3 5G / Sony Xperia 1 III / 5 III（testing）、Microsoft Surface Duo 2。
- 上游 mainline 有部分 SM8350 支持（页面称 "partial support ... more being worked on"）；SM8350 mainline 社区聊天：https://matrix.to/#/#sm8350-mainlining:matrix.org

### 2.2 小米 SM8350 设备（同 SoC 的代际兄弟）
- `Xiaomi Mi 11 (xiaomi-venus)`：页面顶部标记 **「This device is marked as not booting.」**，`Mainline: no`；正文称 USB 可用、regulators 已进，但 1440p DSC panel 驱动是"一团乱麻"，需要 pmbootstrap 自行构建安装镜像。✅
- `Xiaomi Mi 11 Ultra (xiaomi-star)`：同样标记 **not booting**，mainline=no，"与 venus 类似，存在 WIP mainline port"。✅
- **haydn 本尊**：Nura Wiki 全文检索 `haydn` → **0 结果**（没有任何设备页）。✅ 说明 K40 Pro 在 postmarketOS/Nura 生态中连设备页都没有，更谈不上 port。
- 参考移植仓库（venus/star/lemonade 系列，仅供评估工作量）：`cunidev/linux-sm8350`、`nia-e/linux-sm8350`、`strongtz/linux-fun`（页面 See also 链接）。

### 2.3 Ubuntu Touch
- 官方设备库页面自述 **111 supported devices**；逐个列表中没有 Redmi K40 Pro / haydn。✅
- 试探 `/device/haydn` → **HTTP 404**（页面显示 "This device isn't ported yet."）。✅
- 结论：Ubuntu Touch 无 haydn 支持。

### 2.4 Droidian
- Droidian 官网：基于 Debian，用 **libhybris + Halium** 跑在 Android 手机上（= 下游 Android 内核 + Android HAL 支撑的 Debian 用户态）。✅
- 设备支持实现形态：`github.com/droidian-devices` 组织下按设备维护 `adaptation-*` / `linux-android-*` 仓库。抓取其公开仓库列表（GitHub API，第一页 100 条）后检索 `xiaomi|haydn|alioth` → **0 命中**；仅有 fxtec-pro1/pro1x、google-sargo、sony-kumano/bahamut、volla-mimameid/yggdrasil 等。✅
- 结论：Droidian 无 haydn 支持；且 Droidian 也依赖 Halium 移植，而 haydn 无 Halium 设备树（待社区确认❓）。

### 2.5 Mobian
- 官网：基于 Debian + mainline kernel，面向 PinePhone / Librem 5 及部分 Android 机型（OnePlus 6/6T、SHIFT 6MQ）。✅ 无 haydn。
- 结论：不可用。

### 2.6 上游 mainline 的 haydn 设备树
- 未抓到 `arch/arm64/boot/dts/qcom` 目录清单（`git.kernel.org` fetch 失败），因此「mainline 是否已有 haydn dts」只能标记 ❓。已知 SM8350 平台 dts（HDK/MTP）存在，但手机级 dts 通常滞后。
- 这也意味着：即使 mainline 有 SM8350 基础支持，也只是"平台级"，离"手机可日常/可服务器化（Wi-Fi、散热、充电、USB 网络、电源管理）"还很远。

---

## 3. Termux / proot / 容器

### 3.1 Termux + proot（零 root 路线）
- Termux Wiki `PRoot`：PRoot 是 **chroot / mount --bind / binfmt_misc 的用户态实现**；Termux 自带维护版；**`-0` 只是 fake root（伪造 syscall 返回值），无法真正提权**，"需要真 root 才能改内核/硬件状态的程序不会工作"。✅
- `proot-distro` 当前 README（2026 版，jsdelivr 抓取 master）已演进为 **直接拉 Docker/OCI 镜像** 建 rootless 容器：
  - 例：`proot-distro install ubuntu:24.04`、`proot-distro install ghcr.io/...`、`proot-distro build -t myapp:1.0`（Dockerfile 构建也不需要 Docker daemon）。
- **proot-distro README 明列的 Limitations（原文要点，✅）**：
  - 性能：proot 用 ptrace 拦截每个 syscall，文件系统密集负载（编译、包管理）明显变慢。
  - 依赖内核模块的特性（FUSE、特定 iptables targets、自定义 cgroup 层级）不工作。
  - 无真 root：`sudo`、真正 mount、`iptables` 等会失败。
  - **无后台服务**：启动 `systemd`/`OpenRC`/socket-activated daemons 等 supervisor "generally not possible"；可以跑单个长跑进程，但完整 init system 超出范围。
  - **无 cgroups / namespaces**：需要真实内核 namespace 的功能（`unshare`、容器套容器、net namespace）不可用。
  - 不能嵌套（proot 不能 trace 已被 trace 的进程）。
  - Termux 下 Android 限制 `/proc` 部分文件：`/proc/stat`、`/proc/uptime`、`/proc/loadavg`、`/proc/vmstat` 被替换为固定占位值 → `top`/`uptime` 显示的是快照而非实时值（`--minimal` 可关掉占位）。✅ 这条对"做服务器监控"很关键。
- 结论：Termux+proot-distro 是**唯一不依赖 root 的完整 Linux 用户态方案**，但"服务化/容器化"能力是残废的，只适合单进程/轻量自托管。

关键链接：
- https://wiki.termux.com/wiki/PRoot
- https://github.com/termux/proot-distro （README；本次经 https://cdn.jsdelivr.net/gh/termux/proot-distro@master/README.md 抓取，链接仍引用 GitHub 规范地址）

### 3.2 Termux 服务与自启
- `termux-services`：用 **runit** 管服务；包内自带 nginx/apache2/lighttpd/mariadb/postgresql/openssh(sshd, 端口 8022)/cronie/ipfs/tor/transmission 等的 service 脚本；`sv-enable <svc>` / `sv up` / `sv down`；日志在 `$PREFIX/var/log/sv/<pkg>/current`。✅
- `Termux:Boot`：F-Droid 安装后，把脚本放 `~/.termux/boot/`（按文件名排序执行）；建议第一条 `termux-wake-lock` 防休眠；示例即"开机启动 sshd"；要跑 termux-services 可 `. $PREFIX/etc/profile`（其会拉起 service-daemon）。✅
- Termux Wiki `Remote Access`：Termux **没有 init system**，服务手动启动；OpenSSH `sshd` 默认端口 **8022**；支持公钥认证；Dropbear 备选。✅ 另用 `termux-wake-lock` + 关闭电池优化保活。
- 结论：**零 root 路线的"服务化"= Termux:Boot + termux-services(runit) + wake-lock**，桌面 Debian 里的 systemd 不可用（见 proot-distro 限制）。

关键链接：
- https://wiki.termux.com/wiki/Termux-services
- https://wiki.termux.com/wiki/Termux:Boot
- https://wiki.termux.com/wiki/Remote_Access

### 3.3 root 之后：chroot / 容器需要的内核特性
内核侧要求（kernel.org 文档 + Docker/K8s 社区常识），逐项记录：

| 特性 | 内核文档 | 作用 | Android 现状 |
|---|---|---|---|
| user namespace | https://docs.kernel.org/admin-guide/namespaces/index.html | rootless 容器、`unshare` 提权基础 | ❓ 多数手机内核 `CONFIG_USER_NS` 关闭，需上机查 |
| pid/mount/net/ipc/uts namespace | 同上 | 容器隔离、`docker run` 必需 | ❓ 需查 `CONFIG_NAMESPACES`/`*_NS` |
| cgroup v2 单一层级 | https://docs.kernel.org/admin-guide/cgroup-v2.html | 资源限制、systemd/容器运行时基础 | ❓ Android 到底 v1 还是 v2 需 `mount \| grep cgroup`；v1 环境下 Docker 可用但 systemd 受限 |
| overlayfs | https://docs.kernel.org/filesystems/overlayfs.html | 镜像分层（Docker `overlay2` 存储驱动） | ❓ Android 自身用 overlayfs 挂 /system、/product 等，但 `overlay` 是否允许任意 lower/upper 组合需实测 |
| iptables / nftables | https://netfilter.org/ | 容器 NAT/端口映射（Docker 必需） | ❓ 手机内核通常有 netfilter（tethering 用到），但 `iptable_nat`、`nf_nat`、`br_netfilter` 是否齐全需查 |
| binfmt_misc | https://docs.kernel.org/admin-guide/binfmt-misc.html | 跨架构执行（qemu-user）、多架构镜像 | ❓ 常被裁掉；proot 自己模拟 binfmt，不依赖内核 |
| seccomp | https://docs.kernel.org/userspace-api/seccomp_filter.html | 容器默认 seccomp 过滤 | ❓ 需查 `CONFIG_SECCOMP`/`CONFIG_SECCOMP_FILTER` |
| cgroup v2 + 委派（systemd 必需） | 同上 cgroup-v2 `Delegation` 章节 | systemd 需要写 cgroup 树 | ❓ |

**proot 与真 chroot 的能力差异（已核实）**：proot 无 namespace = 容器/服务隔离不可用；proot 的"root"是假 root = `iptables`、`mount`、`chroot` 失败。→ 想要 Docker/Podman/containerd 或 systemd，**必须真 root chroot 或原生内核**。

Docker 侧最权威的"最小要求"本次没抓到（docs.docker.com 不可达），故：Docker/Podman/containerd 在本机能否跑，**只能上机验证**，并以下面命令作为判定依据 ❓：
```sh
# 内核配置（有 config.gz 才行）
zcat /proc/config.gz | grep -E 'CONFIG_(USER_NS|NAMESPACES|PID_NS|NET_NS|IPC_NS|UTS_NS|CGROUPS|CGROUP_BPF|OVERLAY_FS|BINFMT_MISC|SECCOMP|SECCOMP_FILTER|NF_NAT|IP_NF_NAT|BRIDGE)'
# 没有 config.gz 时的替代证据
mount | grep -E 'cgroup|overlay'
ls /sys/fs/cgroup
cat /proc/filesystems | grep -E 'overlay|binfmt'
cat /sys/kernel/security/lsm 2>/dev/null
```
- 参考：Android 官方虚拟化框架 AVF（pKVM）可作为"官方 VM 跑 Linux"的路线：https://source.android.google.cn/docs/core/virtualization （本次仅核实到 AVF 文档存在；其上的 "Linux Terminal"/Debian VM 能否用于 haydn、以及该机型是否启用 pKVM 均 ❓）。老机型（2021、Android 11 时代出厂）大概率不支持。

### 3.4 服务管理（root 之后）

| 方案 | 在 proot | 在 root chroot | 说明 |
|---|---|---|---|
| systemd | ❌ 官方限制"generally not possible"（proot-distro README）✅ | ❓ 可能但常失败：依赖 cgroup 委派、`/proc`/`/sys` 挂载、PID1 语义；社区实践时可用 `systemd --system` 尝试 | 服务器常用，但手机上不保证 |
| s6 / s6-overlay | 可用（纯用户态进程管理） | 可用 | 最稳的"容器式"服务管理 |
| runit | 可用（termux-services 本身即 runit）✅ | 可用 | 轻量、脚本简单 |
| supervisord | 可用（Python 守护进程） | 可用 | 配置直观，适合少量服务 |
| cronie/at | 可用（termux-services 有 crond）✅ | 可用 | 定时任务 |
| Magisk 模块 `service.sh` | n/a | 开机后由 magiskd 执行（Magisk 开发者指南）❓未逐条抓取 | 常与 `boot-completed` 广播配合 |
| Termux:Boot | ✅ `~/.termux/boot` 脚本 | n/a | 零 root 唯一稳定自启通道 |
| Android `BOOT_COMPLETED` 广播 | 需支持该广播的 app（Tasker/MacroDroid/Termux:Boot） | 同 | 受限电策略影响，需关电池优化 |

---

## 4. Root：Magisk vs KernelSU vs APatch

### 4.1 官方口径
- **Magisk**（https://topjohnwu.github.io/Magisk/）：官方文档有 Installation / **OTA Upgrade Guides** / FAQ / Changelog / developer guides / "Android Booting Shenanigans"。✅ 机制=改 ramdisk（boot image）+ 模块（systemless），Zygisk 注入。
- **KernelSU**（https://kernelsu.org/guide/what-is-kernelsu.html）：面向 **Android GKI 设备**的**内核态** root（kernel mode 直接给用户态进程授权）；提供 **metamodule** 体系，系统级修改交给 `meta-overlayfs` 之类 metamodule；文档另有「Difference with Magisk」「Installation」「How to build」「**Integrate for non-GKI devices**」「Unofficially supported devices」。✅
- **APatch**（https://github.com/bmax121/APatch README）：内核 patch 型 root，依赖 **KernelPatch**；支持范围 **ARM64、Android 内核 3.18–6.12**；**要求 `CONFIG_KALLSYMS=y` + `CONFIG_KALLSYMS_ALL=y`**（只有 KALLSYMS 时"initial support"）；有 **APM**（类 Magisk 模块）与 **KPM**（内核内联 hook/syscall 表 hook，可注入任意内核代码）；有 **SuperKey**（权限高于 root，泄露=设备被控）；UI/模块体系源自 KernelSU。✅ 文档站：https://apatch.dev

### 4.2 选型要点（针对 haydn / 2021 SM8350）
- **先确认内核世代**（❓ 上机 `uname -r` / `getprop ro.board.platform` / `ro.build.version.release`）：
  - 出厂 Android 11（内核 5.4，GKI 1.0 时代）或小米后续升级的 HyperOS（内核可能仍为 5.4 厂商树）→ **非 GKI 2.0**，KernelSU 官方只覆盖 GKI 设备，"non-GKI 需自行集成/编译内核"。
  - APatch 支持 3.18–6.12，覆盖 5.4 → 若 KALLSYMS_ALL 开启，**APatch 是低版本内核上更现实的免编译方案**。
  - Magisk 通过 patch boot/init_boot ramdisk，A/B 机型也常用，通用性最好，但 OTA 后需重装（官方有 OTA 指南）。✅
- **结论**：haydn 上 **Magisk（首选，成熟/文档全）或 APatch（若内核 KALLSYMS_ALL 且不想动 ramdisk）**；KernelSU 需自编译内核，属于 §C 路线。全部以 `uname -r`+实测为准 ❓。

### 4.3 解锁后的现实代价（必须写进结论）
- **小米解锁流程（官方页）**：设置→开发者选项→设备解锁状态 绑定账号和设备 → 关机进 bootloader（Vol- + Power）→ USB 连接 → 解锁工具点解锁；官方同时警告"解锁后失去安全保护，指纹识别、查找手机等服务变得不可靠"。✅ 来源：https://www.miui.com/unlock/index.html ，工具下载 https://www.miui.com/unlock/download.html
- **近年收紧门槛（168 小时账号绑定、社区等级、年度次数、HyperOS 限制等）官方页面未列出** → ❓ 必须以申请当时 Mi Community / 解锁工具提示为准；不要按旧教程规划工期。
- 解锁 = **清空数据**、**AVB（Android Verified Boot）变为 UNLOCKED 状态**、可能触发 **dm-verity** 相关校验（Magisk/APatch 会做 disable-verity 类处理）→ ❓ 具体行为按机型实测。
- **Play Integrity / SafetyNet**：解锁+root 后 device integrity 可能不通过，银行/支付/部分游戏/微信部分能力受影响；可用 DenyList + 社区模块缓解但**不保证长期有效**。Google 文档（大陆镜像可达）：https://developer.android.google.cn/google/play/integrity/overview
- **OTA**：Magisk 官方 OTA 指南要求"先还原原厂镜像再 OTA 再重装"；解锁机 OTA 可能被拒/变砖 → ❓ 实测。来源 https://topjohnwu.github.io/Magisk/ota.html
- 保修：解锁/root 通常影响保修（❓ 以小米售后条款为准）。

---

## 5. 长期插电做服务器的硬件问题（全部需实测验证）

- **电池**：
  - 长期 100% + 高温 = 锂电加速老化、鼓包风险（通用锂电常识；本机型具体表现 ❓）。
  - Xiaomi/HyperOS 若有「充电保护/旁路充电」功能（不同机型/版本菜单不同），优先开启；❓ 需在设置里核对是否有"充电保护（80%）""旁路充电（游戏时直供）"。
  - 内核 sysfs 侧可尝试（root 后）：`/sys/class/power_supply/battery/charge_control_limit`、`.../charge_control_limit_max`、`constant_charge_current_max`、`input_current_limit` 等；有的高通 PMIC 驱动支持 `charge_control_limit`，有的只有 `battery_charging_enabled`。❓ 上机 `ls /sys/class/power_supply/` 实测。
  - 若都不支持：退而求其次 = 定期人工放电/限充 App（需 root 的 "Battery Charge Limit" 类工具，同样取决于上面 sysfs 是否存在）❓。
  - 不推荐"拆电池直供"：手机通常需要电池参与供电/开机，拆了可能不开机（❓ 具体机型实测），且失去保护。
- **散热/降频**：骁龙 888 是著名的发热 SoC（2021 旗舰普遍高温 ❓ 无权威单页，属行业共识）；手机无主动散热，长期满载会触发热节流（`/sys/class/thermal/thermal_zone*/temp`，`dumpsys thermalservice`）。建议：限制上限频率、关 boost、加散热背夹/风扇、避免夏天密闭。
- **Wi-Fi 漂移/省电**：Android Doze + 电池优化会杀后台（Termux/sshd 被杀 = 服务器掉线）；对策：Termux 关闭电池优化 + `termux-wake-lock`；Android 自带的 Wi-Fi 省电/漫游策略（Wi-Fi 助理、自适应连接）可能导致重连/换网与 IP 漂移 ❓ 需在"WLAN→高级"里关；服务器场景优先**静态 IP + 固定 DNS**，或干脆**有线/USB 网络**。
- **熄屏策略**：屏幕熄灭不影响 CPU，但某些 OEM 会在熄屏后进入深度休眠；可设"充电时保持唤醒"（开发者选项 "Stay awake"）或 `termux-wake-lock`；AMOLED 长期常亮有烧屏风险 → 让屏幕保持关闭。
- **风扇/环境**：夏季高温会额外降频，建议放在通风处（❓ 实测温度曲线）。
- **USB / 网络接入**：USB 反向 tethering（`adb reverse tcp:8022 tcp:8022`）只在 ADB 连接时可用的临时手段 ❓；想"有线千兆"需要 USB-C 网卡 + 内核驱动（Android 厂商内核常缺 AX88179/RTL8153 驱动、且需 `CONFIG_USB_NET_*`）❓ 实测为准。

---

## 6. 优化可调项（每条都给"命令 + 收益 + 风险"）

> 大部分需要 root 或至少 adb shell；全部 ❓ 待上机确认节点存在。

- **governor**：`ls /sys/devices/system/cpu/cpufreq/` → `policy0/scaling_available_governors`；服务器推荐 `schedutil`（kernel 文档：https://docs.kernel.org/admin-guide/pm/cpufreq.html ），可把 `scaling_max_freq` 压到 ~1.8–2.2GHz 换温度/功耗；`echo 0 > /sys/devices/system/cpu/cpufreq/boost` 关加速（若存在）。
- **I/O scheduler**：`ls /sys/block/` 找 UFS 设备（常见 `sda`/`sdd`），`cat queue/scheduler`；服务器 `mq-deadline` 或 `none`；`queue/read_ahead_kb=128` 以内。
- **zram/swap**：Android 默认有 zram；`cat /proc/swaps`、`ls /sys/block/zram0/`；可调 `vm.swappiness`、`vm.watermark_scale_factor`；kernel 文档 https://docs.kernel.org/admin-guide/blockdev/zram.html
- **内核参数（少量高价值）**：`net.core.somaxconn=1024`（web 服务 backlog）、`net.ipv4.ip_forward=1`（路由/热点共享）、`vm.dirty_ratio/dirty_background_ratio` 调低减卡顿、`kernel.pid_max` 无需动。
- **debloat**：`pm uninstall -k --user 0 <pkg>`（卸载当前用户，不碰系统分区）；`pm disable-user --user 0 <pkg>`；常见可清：遥测/广告/游戏中心类（`com.miui.analytics`、`com.xiaomi.joyose` 需谨慎——joyose 可能影响性能调度！❓）。**每条都需逐包验证**，链式批量卸载风险高。
- **动画**：`settings put global window_animation_scale 0`、`transition_animation_scale 0`、`animator_duration_scale 0`（减 UI 开销，不影响后台服务）。
- **静态 IP / DNS**：WLAN 高级设置 → IP 设为静态（免 root）；或 root 后 `ip addr`/`settings`；DNS 可用 Private DNS 或容器内 resolv.conf（proot-distro 会把容器 `/etc/resolv.conf` 写成 8.8.8.8/8.8.4.4 ✅ README 原文）。
- **SSH**：Termux `sshd` 8022（`wiki.termux.com/wiki/Remote_Access` ✅）；root chroot 里可跑 `sshd` 22；公钥认证 + 禁密码；公网暴露前先上 Tailscale/WireGuard。
- **Tailscale**：官方 Android 客户端（https://tailscale.com/docs/install/android ；下载页 https://tailscale.com/download/android 要求 Android 8+ ✅）；作为"always-on VPN"常驻更稳，需在系统 VPN 设置里设 always-on + 例外；配合 Tailscale SSH/子网路由做无公网端口方案。
- **保活**：`termux-wake-lock`；Magisk `service.sh` 开机脚本；Tasker/自动化配合 boot 广播；Android 开发者选项"充电时保持唤醒"。

---

## 7. 待验证清单（必须在拿到 ADB/解锁权限后逐项跑）

1. `adb shell getprop ro.product.device` → 确认是 `haydn` 还是 `alioth`；`ro.build.version.release`、`ro.board.platform`、`ro.boot.hardware`。
2. `adb shell uname -a` → 内核版本/是否 GKI（5.4 vs 5.10/6.1）。
3. `zcat /proc/config.gz | grep ...`（可能无 config.gz → 改用 `adb shell cat /proc/version` + `/proc/filesystems` + `mount` 推断）。
4. `mount | grep -E 'cgroup|overlay'`、`ls /sys/fs/cgroup` → cgroup v1/v2；overlayfs 可用性。
5. `ls /sys/class/power_supply/battery/` → 是否有 `charge_control_limit*` / bypass 相关节点。
6. 小米解锁资格/时限（以申请时社区公告为准，官方页未载）。
7. `dumpsys thermalservice` / `cat /sys/class/thermal/thermal_zone*/temp` → 温度曲线与降频点。
8. 是否支持 `CONFIG_USER_NS`、`CONFIG_CGROUPS`、`CONFIG_OVERLAY_FS`、`CONFIG_NF_NAT`、`CONFIG_BINFMT_MISC`、`CONFIG_SECCOMP_FILTER`。
9. 是否有可用的第三方内核/LineageOS 官方 haydn 支持（LineageOS 有 haydn 页，但未见社区"容器内核"分支 ❓）。
10. Magisk/APatch 在 haydn + HyperOS 的实测兼容性（是否 A/B、init_boot、是否需要 disable-verity）❓。

---

## 8. 链接总表（本报告引用的一手来源）

| # | 主题 | URL | 状态 |
|---|---|---|---|
| 1 | Nura/postmarketOS 设备总表 | https://wiki.nura.eco/wiki/Devices | ✅ |
| 2 | SM8350 SoC 页 | https://wiki.nura.eco/wiki/Qualcomm_Snapdragon_888_(SM8350) | ✅ |
| 3 | Mi 11 venus（SM8350，小米） | https://wiki.nura.eco/wiki/Xiaomi_Mi_11_(xiaomi-venus) | ✅ |
| 4 | Mi 11 Ultra star | https://wiki.nura.eco/wiki/Xiaomi_Mi_11_Ultra_(xiaomi-star) | ✅ |
| 5 | 红米 K40（alioth, SM8250-AC） | https://wiki.nura.eco/wiki/Xiaomi_POCO_F3_/_Redmi_K40_/_Mi_11X_(xiaomi-alioth) | ✅ |
| 6 | LineageOS haydn 变体 | https://wiki.lineageos.org/devices/haydn/ | ✅ |
| 7 | Ubuntu Touch 设备库 | https://devices.ubuntu-touch.io/ | ✅ |
| 8 | Ubuntu Touch haydn 不存在 | https://devices.ubuntu-touch.io/device/haydn | ✅（404） |
| 9 | Droidian 官网（libhybris/Halium） | https://droidian.org/ | ✅ |
| 10 | Droidian 设备仓库组织 | https://github.com/droidian-devices | ✅ |
| 11 | Mobian 官网 | https://mobian-project.org/ | ✅ |
| 12 | Termux PRoot 原理/限制 | https://wiki.termux.com/wiki/PRoot | ✅ |
| 13 | proot-distro README（2026 版） | https://github.com/termux/proot-distro | ✅ |
| 14 | termux-services（runit） | https://wiki.termux.com/wiki/Termux-services | ✅ |
| 15 | Termux:Boot | https://wiki.termux.com/wiki/Termux:Boot | ✅ |
| 16 | Termux Remote Access（sshd 8022） | https://wiki.termux.com/wiki/Remote_Access | ✅ |
| 17 | cgroup v2 内核文档 | https://docs.kernel.org/admin-guide/cgroup-v2.html | ✅ |
| 18 | namespaces 内核文档 | https://docs.kernel.org/admin-guide/namespaces/index.html | ✅ |
| 19 | binfmt_misc 内核文档 | https://docs.kernel.org/admin-guide/binfmt-misc.html | ✅ |
| 20 | overlayfs 内核文档 | https://docs.kernel.org/filesystems/overlayfs.html | ❓（未逐字抓取，标准路径） |
| 21 | seccomp 内核文档 | https://docs.kernel.org/userspace-api/seccomp_filter.html | ❓（未逐字抓取） |
| 22 | netfilter | https://netfilter.org/ | ❓（未逐字抓取） |
| 23 | cpufreq 内核文档 | https://docs.kernel.org/admin-guide/pm/cpufreq.html | ✅ |
| 24 | zram 内核文档 | https://docs.kernel.org/admin-guide/blockdev/zram.html | ❓（未逐字抓取） |
| 25 | Magisk 文档 | https://topjohnwu.github.io/Magisk/ | ✅ |
| 26 | Magisk OTA 指南 | https://topjohnwu.github.io/Magisk/ota.html | ✅（文档目录中存在） |
| 27 | KernelSU 文档 | https://kernelsu.org/guide/what-is-kernelsu.html | ✅ |
| 28 | APatch README | https://github.com/bmax121/APatch | ✅ |
| 29 | 小米官方解锁页 | https://www.miui.com/unlock/index.html | ✅ |
| 30 | 小米解锁工具下载 | https://www.miui.com/unlock/download.html | ✅ |
| 31 | Android AVF（pKVM）文档 | https://source.android.google.cn/docs/core/virtualization | ✅ |
| 32 | Play Integrity 概览（镜像） | https://developer.android.google.cn/google/play/integrity/overview | ✅（页面可达） |
| 33 | Tailscale Android 安装文档 | https://tailscale.com/docs/install/android | ✅（下载页证实要求 Android 8+） |
