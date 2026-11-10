# haydn-server

> 一台闲置的 **Redmi K40 Pro（M2012K11C / haydn / Snapdragon 888）**，改造成低功耗、可远程维护的家用 Linux 服务器 + DSH 控制面，并规划 Android Bridge APK 作为宿主感知层。
> **当前规范总纲：[docs/28 全栈整体方案规范](docs/28-全栈整体方案规范.md)**
> **新对话请先读：[docs/30 新会话接手指南](docs/30-新会话接手指南.md)**

---

## 当前状态（2026-11-10）

| 项目 | 状态 |
|---|---|
| 设备 | Android 14 / HyperOS / 8GB / 256GB；Bootloader 锁定、AVB green、**无 Root** |
| 服务器 | Termux + proot Ubuntu；**12/12 supervisord 服务 RUNNING** |
| 自启 | Termux:Boot → `00-server.sh` → `ubuntu.sh` → `server-up` + `server-watch`；实测 ADB 32s、8080 45s、完整服务+DSH 111s |
| DSH | 127.0.0.1:3081 + dsh-login 3082 + dsh-guard；`/app-login` 302，公网入口可用 |
| Console | 8080/8443；`/api/sysinfo`、服务/备份/DSH/ops 审计；Battery/WiFi 目前来自 Termux:API |
| 备份 | `server-backup` + `server-backup-sessions` 每日；加密；可校验恢复 |
| Bridge APK | **尚未构建/安装**；Phase 0/1 待启动 |
| 构建工具 | JDK 17/21 已有；**Gradle/Android SDK 未安装** |
| 外部服务 | 未接 Uptime Kuma/异地备份/MFA/Tailscale；公网仅现有 frp 受控入口 |

**已知限制**
- 重启后 Termux:API App 不自动启动 → 电池/WiFi 为空，需手动打开一次；
- 无 Root：全局 `/proc/stat`、`/proc/net/dev`、dumpsys/settings/冻结/停用不可得；
- DSH 不能启动 Android App；不要让 DSH 控制 Bridge 生命周期。

---

## 总体架构（三轨）

| 轨道 | 内容 | 状态 |
|---|---|---|
| **A. 服务器栈** | Termux + proot Ubuntu + supervisord + nginx + DSH + Console + 备份/审计 | ✅ 运行中 |
| **B. Android Bridge APK** | BootReceiver + Foreground Service + loopback HTTPS + 电池/WiFi/宿主状态 | 🚧 规划/待构建 |
| **C. 集成层** | `bridge_client.py` + `/api/sysinfo` + `server-ops bridge status` + Console/DSH | 🚧 随 B 落地 |

原则：
- **Server 是唯一聚合/存储/展示方**；Bridge 只提供宿主状态；
- **DSH 是控制面/解释层**：只读 Server API + `server-ops`，不持有 Bridge token、不控制 Bridge；
- **Bridge 失败自动回退 Termux 采集**；DSH 故障不影响采集；
- **无 Root**：不承诺系统级特权字段，ADB/Shizuku 仅维护通道。

---

## 新会话从这里开始

1. **[docs/30 新会话接手指南](docs/30-新会话接手指南.md)** —— 当前基线、Phase 0/1、护栏、验收。
2. **[docs/28 全栈整体方案规范](docs/28-全栈整体方案规范.md)** —— 目标/接口/数据/安全/可靠性/部署/ADR（v1.1）。
3. **[docs/27 Android Bridge 架构调研](docs/27-Android-Bridge-APK架构调研.md)** —— 为什么是 Bridge APK、开源对比、Android 14/15 证据。
4. 需要重建服务器时再读 **[docs/17 研究平台环境构建手册](docs/17-研究平台环境构建手册.md)**。

---

## 文档地图

### 入口与规划
- [00-项目规划](docs/00-项目规划.md) —— 路线、阶段、决策记录
- **[28-全栈整体方案规范](docs/28-全栈整体方案规范.md)** —— 当前规范总纲
- [29-项目文档评审报告](docs/29-项目文档评审报告.md) —— 本次评审/修订记录
- **[30-新会话接手指南](docs/30-新会话接手指南.md)** —— 新对话入口
- [02-可行性分析](docs/02-可行性分析.md) · [04-风险与回滚](docs/04-风险与回滚.md)

### 服务器构建与运维
- [17-研究平台环境构建手册](docs/17-研究平台环境构建手册.md) —— 从零重建
- [08-事故复盘与重置重建报告](docs/08-事故复盘与重置重建报告.md) —— bootloop 复盘
- [03-操作手册](docs/03-操作手册.md) · [07-DSH与Linux优化](docs/07-DSH与Linux优化.md)

### DSH 控制面
- [21-控制平面落地手册](docs/21-DSH控制平面落地手册.md)
- [22-Tier2受控写](docs/22-DSH-Tier2受控写落地.md)
- [23-蓝绿升级演练](docs/23-DSH蓝绿升级演练.md)
- [24-sessions持久化补全](docs/24-DSH-sessions持久化补全.md)

### 优化与手机状态
- [06-A+优化方案](docs/06-A+优化方案.md) · [09-性能优化](docs/09-性能优化方案与可行性分析.md)
- [14-安卓深度操作调研](docs/14-安卓深度操作调研与技能沉淀.md) · [16-非官方Root研究](docs/16-非官方Root路径可行性与风险研究.md)
- [18-控制台持久化](docs/18-控制台持久化与容器优化方案.md) · [19-ADB让资源](docs/19-ADB为服务器让资源方案.md)
- [25-ADB资源优化与Console审计](docs/25-ADB资源优化与Console审计落地.md) · [26-Console手机状态](docs/26-Console手机状态补全.md)

### 控制台 / DSH 专项
- [13-控制台功能分析](docs/13-控制台功能分析与完善.md) · [15-账号密码保险库](docs/15-账号密码保险库.md)
- [09-文件管理-文件夹打包下载](docs/09-文件管理-文件夹打包下载.md) · [10-面板治理-移除CI-Runner](docs/10-面板治理-移除CI-Runner.md)
- [10-DSH登录入口优化](docs/10-DSH登录入口优化.md) · [11-DSH服务器配置与模型](docs/11-DSH服务器配置与模型.md) · [12-DSH性能优化](docs/12-DSH性能优化.md) · [13-DSH插件安装-pnpm](docs/13-DSH插件安装-pnpm.md) · [11-移除DSH-GO-App环境SSH](docs/11-移除DSH-GO-App环境SSH.md)
- [17-控制台移动端适配](docs/17-控制台移动端适配.md)

> 历史编号冲突（09/10/11/13/17 各有多个文件）保留原文件避免断链，详见 [docs/29 §5](docs/29-项目文档评审报告.md#5-文档编号冲突保留历史不重命名)。

### 调研与历史归档
- [27-Android Bridge APK 架构调研](docs/27-Android-Bridge-APK架构调研.md)
- [05-B路线执行手册](docs/05-B路线执行手册.md)（已归档）
- [docs/archive/README-2026-11-10.md](docs/archive/README-2026-11-10.md) —— 旧版 README

---

## 边界与护栏（必须）

1. **不 Root、不刷机、不解锁 BL**；不装系统/priv-app。
2. **不卸载系统包**；不执行 `am kill-all`；不改 Android 系统设置（ADB 优化除外）。
3. **不把 Bridge token / 证书 / DSH token / 备份口令**写入日志、聊天、公网页面。
4. **DSH 不直连 Bridge、不持 token、不试图启动 App**；只走 Server API/server-ops。
5. 写操作走 `server-ops` Tier2（`--confirm` + 快照 + 审计）；Tier3 只人工 SSH。
6. 外部服务（Uptime Kuma/异地备份/MFA/Tailscale）未获确认不做。
7. 服务器重装/重置前先备份并按 [docs/17](docs/17-研究平台环境构建手册.md)。

---

## 常用只读检查

```bash
server-ops status
server-ops health
server-ops logs dsh --lines 100
curl -s http://127.0.0.1:8080/api/sysinfo | head
curl -s http://127.0.0.1:8080/api/ops?n=5 | head
```

> 公网入口/DSH token 不在此列出，使用 `/app-login` 或控制台管理入口。

---

## 仓库结构（简化）

```
手机优化/
├── README.md                 ← 当前版
├── docs/
│   ├── 28/29/30              ← 规范总纲 / 评审 / 接手指南
│   ├── 17/21/22/23/25/26     ← 服务器构建 / DSH 控制面 / 状态
│   └── archive/              ← 旧版 README
├── scripts/
│   ├── server/               ← 服务器脚本、Console、server-ops、备份
│   ├── adb-*.ps1             ← ADB/资源优化/安装脚本
│   └── ...
├── tools/                    ← adb/APK（大多 gitignore）
├── backup/                   ← 加密备份/密钥（gitignore）
└── android-bridge/           ← 待创建（Phase 0）
```

---

## 许可

个人项目，仅供自用与研究。第三方开源项目仅按许可证使用/参考，详见 [docs/28 §13](docs/28-全栈整体方案规范.md#13-开源选型与许可)。
