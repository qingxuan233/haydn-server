# Redmi K40 Pro → 家用 Linux 服务器（项目：haydn-server）

把一台闲置的 **Redmi K40 Pro（M2012K11C / 内部代号 `haydn` / 骁龙 888 / SM8350）** 改造成一台低功耗、可远程维护的家用 Linux 服务器。

- 目标：SSH 远程登录、文件同步/备份、轻量 Web 与自托管服务、下载/定时任务
- 原则：**先零风险上线（Termux + proot），再用运行数据决定是否解锁 Root 升级**
- 状态：**P0 已完成**（2026-11-10）——ADB 已连通、设备档案与能力实测已产出，P1 可立即开始

---

## 当前设备（实测确认）

| 项目 | 值 |
|---|---|
| 型号 / 代号 | M2012K11C / **haydn** |
| SoC | Snapdragon 888（SM8350 / lahaina），8 核 |
| 内存 / 存储 | 8GB（可用 7.13 GiB）/ 256GB UFS（`/data` 可用约 193 GiB） |
| 系统 | Android 14（SDK 34）/ HyperOS 1.0 / `V816.0.15.0.UKKCNXM` |
| 内核 | Linux **5.4.274-qgki**（GKI 1.x 代） |
| 启动链 | Bootloader **锁定**、AVB green、dm-verity enforcing、SELinux Enforcing、**未 Root** |
| 分区 | **A/B 双分区 + 动态分区（`super`）** |
| 电池 | 4520 mAh，当前 100% / 27 °C / GOOD（长期插电需做充电上限） |
| 网络 | WiFi `wlan0`，当前 192.168.10.143/24（需做 DHCP 保留/静态 IP） |
| 已装关键 App | Termux `0.118.3`、Termux:Boot `0.8.1`、Clash、ToDesk |

## 核心结论（一句话版）

| 问题 | 结论 |
|---|---|
| 能刷原生 Linux（postmarketOS/Ubuntu Touch 等）吗？ | ❌ 不可行——haydn 没有任何可刷的移植 |
| 不解锁能用 Linux 吗？ | ✅ 可以：Termux + proot-distro（假 root、无 systemd、无容器、I/O 有损耗） |
| 能跑 Docker 吗？ | ❌ **实测否决**：内核 `CONFIG_USER_NS`、`CONFIG_PID_NS` 未启用，容器无法创建命名空间 |
| 想更强能力怎么办？ | 解锁 + Root + chroot（s6/supervisord），中高风险（清数据、失保修、变砖）；**国行 2026 可能已关闭官方解锁，先做 Gate B0 验证（[docs/05](docs/05-B路线执行手册.md)）** |
| 解锁后 KernelSU 还是 Magisk？ | **Magisk 优先**（5.4 QGKI 非 GKI 2.0；KernelSU 需自编译内核） |
| 长期插电电池怎么办？ | 系统"充电保护" / Root 后 ACC 限充 60–80% + 通风散热 |

## 路线图

| 阶段 | 内容 | 状态 |
|---|---|---|
| **P0** | ADB 连通 + 设备建档 + 内核能力实测 | ✅ 已完成 |
| **P1** | Termux + SSH + 保活自启 + proot Ubuntu（2–3 小时） | ⬜ 下一步 |
| **P2** | 服务落地 + 7 天稳定观察 + 备份演练 | ⬜ |
| **P3** | 升级决策门（继续 A / 解锁 Root 升级 B） | ⬜ |
| **P4** | B 路线：解锁 + Magisk + chroot + s6（条件执行） | ⬜ |
| **P5** | 优化调优：熄屏/充电上限/CPU/网络/debloat | ⬜ |
| **P6** | 30 天稳定运行 + 监控/备份/远程重启闭环 | ⬜ |

## 目录结构

```
手机优化/
├── README.md                  ← 本文件
├── .gitignore
├── docs/
│   ├── 00-项目规划.md          ← 阶段路线、里程碑、决策记录、待确认问题
│   ├── 01-设备档案.md          ← T0 基线（硬件/系统/热区/网络/软件现状）
│   ├── 02-可行性分析.md        ← 技术路线证据（含 §13 上机实测结论）
│   ├── 03-操作手册.md          ← 分阶段操作步骤与命令
│   ├── 04-风险与回滚.md        ← 风险登记册 + 回滚手册 + 准入检查表
│   ├── 05-B路线执行手册.md      ← Gate B0 解锁验证 + 解锁/Root/chroot 全流程
│   └── research/
│       ├── raw-notes.md        ← 研究原始笔记与 33 条来源链接
│       └── ...
├── scripts/
│   ├── get-platform-tools.ps1  ← 下载 adb/fastboot 到 tools/
│   ├── adb.ps1                 ← adb 包装器（自动定位项目内 adb）
│   ├── check-connection.ps1    ← 连接状态检查（退出码 0/2/3）
│   ├── collect-device-info.ps1 ← 全量设备档案采集 → inventory/
│   ├── probe-device.sh         ← 设备端能力探测脚本（内核/容器/充电）
│   └── probe-device.ps1        ← 推送并执行 probe-device.sh 的包装器
├── inventory/                 ← 采集产物（已 gitignore：含序列号/应用清单）
└── tools/platform-tools/      ← adb / fastboot（已 gitignore）
```

## 快速开始

```powershell
# 1) 检查手机连接（返回 0 = 已授权）
powershell -ExecutionPolicy Bypass -File scripts\check-connection.ps1

# 2) 采集设备档案（生成 inventory/ 时间戳快照 + latest 副本）
powershell -ExecutionPolicy Bypass -File scripts\collect-device-info.ps1

# 3) 探测内核能力（容器/命名空间/充电控制/温控）
powershell -ExecutionPolicy Bypass -File scripts\probe-device.ps1
```

> 环境：Windows PowerShell 5.1 即可（无需 PowerShell 7）。首次使用若提示找不到 adb，先运行 `scripts\get-platform-tools.ps1`。

## 文档怎么读

1. **先读 [00-项目规划](docs/00-项目规划.md)** —— 目标、路线、阶段、决策门、待你拍板的问题
2. **再看 [01-设备档案](docs/01-设备档案.md)** —— 这台手机到底是什么状态
3. **想知道为什么这么规划** → [02-可行性分析](docs/02-可行性分析.md)
4. **要动手** → [03-操作手册](docs/03-操作手册.md)（含每步的风险标注）
5. **动手前必读** → [04-风险与回滚](docs/04-风险与回滚.md)

## 重要警告

- **解锁 Bootloader 会清空全部数据且不可恢复**，并通常失去保修；
- **当前未 Root、未解锁**，任何 "刷机/容器/系统级调优" 文档里的操作都**不要直接照抄**，按 00 的阶段与 04 的准入检查表执行；
- `inventory/` 内含设备序列号、网络地址与应用清单，**不要公开上传**；
- 本项目默认**不暴露公网端口**，远程访问使用 Tailscale/WireGuard。

## 安全与隐私

- 手机端 SSH 只启用公钥认证；
- 不把 ADB 无线调试长期开着；用完关闭；
- 关键配置与服务清单纳入 Git（不含密钥；密钥单独保管）。

## 许可

个人项目，仅供自用与研究。
