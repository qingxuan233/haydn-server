# haydn-server

> 一台闲置的 **Redmi K40 Pro（`M2012K11C` / `haydn` / Snapdragon 888）**，改造成低功耗、可远程维护的家用 Linux 服务器 + Android Bridge 宿主状态桥 + DSH 控制面。
>
> **2026-11-11 仓库更名**：`手机优化` → `haydn-server`。原因：aapt2 在 Windows 下无法处理含中文的路径，导致 Android Bridge APK 构建失败；同时统一 ASCII 路径，避免后续构建/CI 工具踩坑。旧版 README 已归档在 [docs/90-archive](docs/90-archive/README-2026-11-10.md)。

---

## 当前状态（2026-11-11）

| 项目 | 状态 |
|---|---|
| 设备 | Android 14 / HyperOS / 8GB / 256GB；Bootloader 锁定、AVB green、**无 Root** |
| 服务器 | Termux + proot Ubuntu；**12/12 supervisord 服务 RUNNING** |
| 自启 | Termux:Boot → `00-server.sh` → `ubuntu.sh` → `server-up` + `server-watch`；实测 ADB 32s / 8080 45s / 完整服务+DSH 111s |
| DSH | 127.0.0.1:3081 + dsh-login 3082 + dsh-guard；公网 `/app-login` 302 |
| Console | 8080/8443；总览 + `?view=details` 详情双视图 |
| 备份 | `server-backup` + `server-backup-sessions` 每日；加密；可校验恢复 |
| Bridge APK | **release 版运行中**（debuggable=false）；5/5 debug 重启 + 1/1 release 重启；Phase 2 字段（display/usage/network/uptime）已接入；**24h soak 待完成** |
| 构建 | JDK 17/21（`build.ps1` 自动探测）+ `tools/android-sdk`（platforms android-35 / build-tools 35.0.0）；无 Gradle，手工构建 |
| 外部服务 | 未接 Uptime Kuma / 异地备份 / MFA / Tailscale；公网仅现有 frp 受控入口 |

> 权威状态源：[docs/00-overview/当前状态.md](docs/00-overview/当前状态.md)。README 只做概览，不重复维护细节。

**已知限制**
- 无 Root：全局 `/proc/stat`、`/proc/net/dev`、`dumpsys`/`settings`/冻结/停用不可得；
- MIUI/HyperOS 重启后会把 `POST_NOTIFICATIONS` 重置为 ignore（FGS 仍运行，通知不可见）；
- `GET_USAGE_STATS` 重启后回到 default，`usage_foreground` 为空，需用户/ADB 再授权；
- DSH 不能启动 Android App；不要让 DSH 控制 Bridge 生命周期。

---

## 总体架构（三轨）

| 轨道 | 内容 | 状态 |
|---|---|---|
| **A. 服务器栈** | Termux + proot Ubuntu + supervisord + nginx + DSH + Console + 备份/审计 | ✅ 运行中 |
| **B. Android Bridge APK** | BootReceiver + specialUse FGS + loopback HTTPS + 电池/WiFi/宿主状态 | ✅ release 运行中 |
| **C. 集成层** | `bridge_client.py` + `/api/sysinfo` + `server-ops bridge status` + Console | ✅ 已接入 |

原则：
- **Server 是唯一聚合/存储/展示方**；Bridge 只提供宿主状态；
- **DSH 是控制面/解释层**：只读 Server API + `server-ops`，不持有 Bridge token、不控制 Bridge；
- **Bridge 失败自动回退 Termux 采集**；DSH 故障不影响采集；
- **无 Root**：不承诺系统级特权字段，ADB/Shizuku 仅维护通道。

---

## 从这里开始

| 入口 | 用途 |
|---|---|
| **[docs/README.md 文档索引](docs/README.md)** | 全部文档的唯一导航入口（含旧编号对照） |
| **[当前状态](docs/00-overview/当前状态.md)** | 单页事实：设备/服务/Bridge/构建/限制 |
| **[30 新会话接手指南](docs/00-overview/30-新会话接手指南.md)** | 新对话先读；读序、下一步、护栏、验收 |
| **[28 全栈整体方案规范](docs/00-overview/28-全栈整体方案规范.md)** | 当前规范总纲（架构/接口/数据/安全/可靠性/部署/ADR） |
| **[27 Android Bridge 调研](docs/50-bridge/27-Android-Bridge-APK架构调研.md)** | 为什么是 Bridge APK、开源对比、Android 14/15 证据 |
| **[17 研究平台环境构建手册](docs/20-server/17-研究平台环境构建手册.md)** | 换机/重置时从零重建服务器 |

---

## 仓库结构

```
haydn-server/
├── README.md                 # 本文件：项目概览与入口
├── CHANGELOG.md              # 全部变更记录（唯一变更日志）
├── docs/
│   ├── README.md             # 文档索引（唯一导航）
│   ├── 00-overview/          # 规划、规范、评审、接手指南、当前状态
│   ├── 10-device/            # 设备档案、可行性、风险、OEM 适配、Root 路线
│   ├── 20-server/            # 服务器重建/运维/性能/优化/复盘
│   ├── 30-dsh/               # DSH 部署、配置、性能、控制面、蓝绿、sessions
│   ├── 40-console/           # Console 功能/移动端/保险库/手机状态/IA 改版
│   ├── 50-bridge/            # Bridge 调研与实施记录
│   ├── 90-archive/           # 已归档历史（B 路线、非官方 Root、旧 README、原始笔记）
│   └── assets/               # 文档截图
├── scripts/
│   ├── README.md             # 脚本索引（用途/用法/运行位置）
│   ├── adb/                  # PC 侧 ADB/设备脚本（采集、优化、安装、探测）
│   ├── termux/               # Termux 侧 shell
│   ├── server/               # proot 服务器脚本与配置（server-ops/备份/DSH/Console）
│   └── dev/                  # 开发校验工具（check-links.py）
├── android-bridge/           # Bridge APK 源码 + 手工构建脚本
├── tools/                    # 本地工具（多数 gitignored，见 tools/README）
├── inventory/                # 采集快照（gitignored，见 inventory/README）
└── backup/                   # 个人加密备份（gitignored，勿入库）
```

---

## 常用命令

```bash
# 服务器只读检查（在 proot Ubuntu 内）
server-ops status
server-ops health
server-ops logs dsh --lines 100
curl -s http://127.0.0.1:8080/api/sysinfo | head
curl -s http://127.0.0.1:8080/api/ops?n=5 | head
```

```powershell
# 构建 Bridge APK（Windows，仓库路径必须为 ASCII）
powershell -NoProfile -ExecutionPolicy Bypass -File android-bridge\build.ps1
# 产物：android-bridge\build\bridge.apk + build\bridge.crt（均 gitignored）

# 文档链接检查
python scripts\dev\check-links.py --strict-anchors
```

> 公网入口/DSH token 不在此列出，使用 `/app-login` 或控制台管理入口。

---

## 边界与护栏（必须）

1. **不 Root、不刷机、不解锁 BL**；不装系统/priv-app。
2. **不卸载系统包**；不执行 `am kill-all`；不改 Android 系统设置（ADB 优化除外）。
3. **不把 Bridge token / 证书 / DSH token / 备份口令**写入日志、聊天、公网页面。
4. **DSH 不直连 Bridge、不持 token、不试图启动 App**；只走 Server API/`server-ops`。
5. 写操作走 `server-ops` Tier2（`--confirm` + 快照 + 审计）；Tier3 只人工 SSH。
6. 外部服务（Uptime Kuma/异地备份/MFA/Tailscale）未获确认不做。
7. 服务器重装/重置前先备份并按 [17 重建手册](docs/20-server/17-研究平台环境构建手册.md)。

---

## 文档维护约定

1. **状态唯一源**：[docs/00-overview/当前状态.md](docs/00-overview/当前状态.md)；其他文档引用它，不复制状态数字。
2. **变更记录唯一源**：[CHANGELOG.md](CHANGELOG.md)；按日期追加，版本号只增不复用。
3. **新文档**：放入对应 `docs/<group>/`，同步更新 [docs/README.md](docs/README.md) 索引；不再使用旧 `docs/NN` 编号。
4. **链接**：一律相对路径 Markdown 链接；提交前跑 `python scripts\dev\check-links.py --strict-anchors`。
5. **敏感信息**：token/密码/证书/备份口令不进仓库、不进文档、不进日志。
6. 历史实现记录保留证据，但标注“历史记录（日期）”，不写成当前状态。

---

## 许可

个人项目，仅供自用与研究。第三方开源项目仅按许可证使用/参考，详见 [28 规范 §13](docs/00-overview/28-全栈整体方案规范.md#13-开源选型与许可)。
