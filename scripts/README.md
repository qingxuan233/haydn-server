# scripts 脚本索引

本文件是 `scripts/` 下全部脚本/配置的唯一索引：按**运行位置**分成 `adb/`（PC 侧）、`termux/`（手机 Termux 内）、`server/`（proot 服务器内）与 `dev/`（开发工具）。

> 2026-11-11 重构：原先直挂 `scripts/*.ps1|py|sh` 的脚本已移入分组子目录，仓库改名为 `haydn-server`；本文所有用法使用新路径。旧路径对照见 §6。

> **证据层指针（2026-11-11 重构起）**：本目录是 **haydn K40 Pro 实证案例的实现证据**（冻结，仅修事实错误），不是通用方法论入口；通用方法论见 [methodology/README.md](../methodology/README.md)，项目总入口 [根 README](../README.md)，Agent 入口 [AGENTS.md](../AGENTS.md)。
> 脚本是历史实现，换机/通用化时优先按 `methodology/` 与 `toolkit/` 重新生成，不要直接套用本目录的 MIUI 专用脚本。

| 文档 ID | `HB-OPS-001` |
|---|---|
| 版本 | v1.0（2026-11-11 新建） |
| 状态 | 现行 |
| 关联 | [当前状态](../docs/00-overview/当前状态.md) · [03 操作手册](../docs/20-server/03-操作手册.md) · [17 构建手册](../docs/20-server/17-研究平台环境构建手册.md) · [服务器 agent 约束](server/AGENTS.md) |

## 0. 分组与运行环境

| 分组 | 在哪运行 | 依赖 | 说明 |
|---|---|---|---|
| `scripts/adb/` | **PC**（Windows PowerShell / Python） | ADB（USB 或无线 5555）；少数还需要 SSH | 设备采集、优化、安装、健康检查；默认自动定位 `tools/platform-tools/adb.exe` |
| `scripts/termux/` | **手机 Termux 内** | Termux:Boot / Termux:API / `termux-wake-lock` | 开机自启与宿主指标采集 |
| `scripts/server/` | **proot Ubuntu 服务器内**（少数在 Termux 内） | Python3、supervisord、nginx、Node24 | 服务器运行时脚本与配置的**仓库源副本**，部署到 `/root/server/...` 后生效 |
| `scripts/dev/` | 开发机（PC） | Python3 | 仓库维护工具（链接检查） |

约定：
- PowerShell 脚本统一用 `powershell -NoProfile -ExecutionPolicy Bypass -File <路径>` 执行；Windows PowerShell 5.1 即可（无需 PowerShell 7）。
- `adb/` 下脚本默认 `$PSScriptRoot\..\tools\platform-tools\adb.exe`；找不到 adb 时先跑 `adb/get-platform-tools.ps1`。
- **不要**把 token/密码/私钥写进任何脚本或文档；`tools/`、`inventory/`、`backup/` 多数内容已 gitignored（见 [tools/README.md](../tools/README.md)）。

## 1. `scripts/adb/` — PC 侧 ADB / 设备脚本（22 个）

| 脚本 | 用途 | 典型用法 | 需要 |
|---|---|---|---|
| `adb.ps1` | adb 包装器：自动定位项目内 adb，回退 `ADB_PATH`/PATH；透传所有 adb 参数 | `... -File scripts\adb\adb.ps1 devices -l`；`... shell getprop ro.product.model` | ADB |
| `get-platform-tools.ps1` | 下载并解压 platform-tools（adb/fastboot/sqlite3）到 `tools/platform-tools`；已存在默认跳过 | `... -File scripts\adb\get-platform-tools.ps1 -Force`（强制重下） | 网络 |
| `check-connection.ps1` | 检查 adb 工具链与设备授权状态；退出码 `0`=可用、`2`=找不到 adb、`3`=无设备/未授权 | `... -File scripts\adb\check-connection.ps1` | ADB |
| `collect-device-info.ps1` | 全量设备档案采集：身份/构建/安全/硬件/内存/存储/电池/网络/包列表/温度；写 `inventory/device-info-*.json`、`device-raw-*.txt`、`packages-*.txt` + `*-latest` | `... -File scripts\adb\collect-device-info.ps1` | ADB |
| `probe-device.sh` | 设备端能力探测 shell（内核命名空间/cgroup/overlayfs/seccomp/充电节点/zram/温控/boot 分区） | `adb push scripts\adb\probe-device.sh /data/local/tmp/ && adb shell sh /data/local/tmp/probe-device.sh` | ADB |
| `probe-device.ps1` | 推送并执行 `probe-device.sh` 的包装器，结果写 `inventory/capability-probe-*.txt` + latest | `... -File scripts\adb\probe-device.ps1` | ADB |
| `adb-deep-probe.ps1` | 安卓/小米深度只读探查（不改设备）；输出 `inventory/deep-probe-*.md` | `... -File scripts\adb\adb-deep-probe.ps1 [-Serial <serial>]` | ADB |
| `adb-server-resource.ps1` | "ADB 为服务器让资源"：Status / Quiet / Restore（可逆） | `... -File scripts\adb\adb-server-resource.ps1 -Status` | ADB |
| `after-reboot-android.ps1` | 重启/重连后恢复 Android 侧技能环境（Shizuku、AppManager、logcat 等 MIUI 重置项） | `... -File scripts\adb\after-reboot-android.ps1 [-EnableTcpip]` | ADB |
| `apply-a-plus.ps1` | A+ 无 Root 优化：可逆系统设置 + 安全 debloat；默认 DryRun，变更写 `inventory/apply-a-plus-*.json` + latest | `... -Apply` / `... -Restore` | ADB |
| `optimize-server-profile.ps1` | **现行**重置后安全优化（保护名单；系统包只 `disable`、第三方 `uninstall --user 0`；分批） | `... -File scripts\adb\optimize-server-profile.ps1 [-Apply|-Restore]` | ADB |
| `debloat-server-mode.ps1` | ⚠️ **历史/已废弃**：2026-11-10 bootloop 事故后，禁止再对系统包执行 `pm uninstall`；现行用 `optimize-server-profile.ps1` | 仅作历史参考，勿在新机执行 `-Apply` | ADB |
| `perf-adb-apply.ps1` | 性能优化 P0/P1 的 ADB 侧一键执行/回滚（suspend/appops 可逆） | `... -Apply` / `... -Status` / `... -Restore` | ADB |
| `phone-health.ps1` | 手机服务器健康检查：温度/负载/内存/磁盘/服务状态，报告写 `inventory/phone-health-*.md` + latest | `... -File scripts\adb\phone-health.ps1` | ADB + SSH |
| `restart-termux-services.ps1` | 远程恢复 Termux/proot 服务（ADB `run-as com.termux` 触发 Termux:Boot，脚本不需解锁/Root） | `... -File scripts\adb\restart-termux-services.ps1` | ADB |
| `setup-dsh-server.ps1` | 在 proot 服务器内安装 DSH（Node24 + supervisord + `server-dsh` + 环境优化），幂等 | `... -File scripts\adb\setup-dsh-server.ps1 [-SshHost <host>]` | SSH |
| `shizuku-adb-start.ps1` | Shizuku 安装/启动/状态（无 Root 的 ADB 特权路线；重启后需重新启动） | `... -Install` / `... -Start` / `... -Status` | ADB |
| `appmanager-adb-mode.ps1` | AppManager ADB 特权模式（librun_server）启停/状态 | `... -Start` / `... -Status` / `... -Stop` | ADB |
| `miui-adb-install.ps1` | MIUI/HyperOS 下 ADB 安装 APK：自动点按 `AdbInstallActivity` 确认弹窗 | `... -Apk tools\apks\shizuku.apk` | ADB |
| `preflight-b.ps1` | B 路线前置检查（只读）：解锁状态/区域/工具/固件/备份；退出码 `0`=无阻断、`1`=有 FAIL。**B 路线已取消，仅历史用途** | `... -File scripts\adb\preflight-b.ps1` | ADB |
| `verify-research-env.ps1` | 研究平台环境验证（ADB + SSH 只读），报告写 `inventory/env-verify-*.md` | `... -File scripts\adb\verify-research-env.ps1 [-SshKey <key>]` | ADB + SSH |
| `uad-compare.py` | UAD-NG 清单只读对比（不卸载/不禁用），输出 `inventory/uad-compare-*.md` | `python scripts\adb\uad-compare.py [--json tools\uad_lists.json]` | ADB + Python3 |

## 2. `scripts/termux/` — Termux 内 shell

| 脚本 | 用途 | 部署/用法 | 需要 |
|---|---|---|---|
| `termux-boot-01-api.sh` | **Termux:Boot 开机脚本**：`termux-wake-lock` 后拉起 Termux:API（保证 `termux-battery-status`/WiFi 可用） | 复制到 `~/.termux/boot/01-api.sh`，`chmod +x`；开机按文件名顺序执行 | Termux:Boot |
| `termux-metrics.sh` | Termux 侧综合状态采集器（每 10s 用 `/system/bin/top` + `uptime`），输出 `$HOME/termux-status.txt` 供 proot 内 Console 读 `/hosthome` | `~/.termux/boot/` 后台启动，或 `~/.termux-metrics.sh &`；服务器侧旧副本见 `server/termux-metrics.sh` | 无（Termux 内） |

> 注意：Termux 内脚本需在 Termux 里执行/放 `~/.termux/boot/`；它们**不能**在 proot Ubuntu 内运行（依赖 Termux 的 `$PREFIX` 与 `/system/bin`）。

## 3. `scripts/server/` — 服务器（proot）脚本与配置

这些文件是**仓库源副本**；部署时复制到 proot Ubuntu 内的 `/root/server/...`（或 nginx/supervisor 配置目录）后生效。直接在本机 PC 上执行大部分没有意义。

### 3.1 Termux 侧启动入口

| 文件 | 用途 |
|---|---|
| `00-server.sh` | Termux:Boot 开机入口：`termux-wake-lock` → 后台起 `termux-metrics.sh` → 进入 Ubuntu 执行 `server-up` + `server-watch` |
| `ubuntu.sh` | Termux 内 proot 启动包装：`$HOME/ubuntu.sh '<命令>'`，`exec proot ... -0 -r $HOME/ubuntu`（不绑定 `/sdcard`，避免软链崩溃） |

### 3.2 服务管理与运维（部署到 `/root/server/bin/`）

| 文件 | 用途 |
|---|---|
| `server-ops` | **运维 CLI（Tier1 只读 / Tier2 受控写）**：`status`/`health`/`logs`/`backups`/`backup-verify`/`audit`/`bridge status`；Tier2 `restart|start|stop <svc> --confirm`、`nginx test|reload --confirm`、`backup --confirm`、`rotate --confirm`；自动写配置快照与 `ops-audit.jsonl` |
| `dsh-guard` + `dsh-guard.conf` | DSH 看门狗：仅在服务 `RUNNING` 时做 HTTP 健康检查，`STARTING/BACKOFF` 不误杀；supervisord `[program:dsh-guard]` |
| `server-backup-sessions` | 备份 DSH sessions（排除 proot `link2symlink` 的 `.l2s.*` 伪链接），保留最近 N 份 |
| `server-runner` / `bin/server-runner` | CI Runner 按需启停（面板治理后不常驻） |
| `import-server-credentials.py` | 把服务器现有账号/密码/口令导入控制台加密保险库（只走 127.0.0.1 API，不打印密钥） |

### 3.3 Console / 文件管理源码

| 文件 | 部署目标 |
|---|---|
| `console-api.py` | `/root/server/api/app.py`（控制台 API v2，零第三方依赖） |
| `bridge_client.py` | 与 `console-api.py` 同目录：Bridge 只读客户端（loopback HTTPS + token + 证书 pin） |
| `console/index.html` | `/root/server/www/index.html`（控制台页面源码） |
| `webui/app.py` + `webui/static/index.html` | 文件管理器源码（含"下载整个文件夹"增强） |
| `www/index.html` | 面板页（与 `server-runner` 配合） |
| `remote-access/index.html` | 远程入口/跳转页 |

### 3.4 DSH 部署与调优

| 文件 | 用途 |
|---|---|
| `finalize-dsh-server.sh` | 服务器端 DSH 收尾：原生模块/包装器/supervisor/nginx `/app` 反代/`server-dsh` |
| `install-dsh-control-plane.sh` | 安装 DSH 控制平面 P0（`dsh-guard`/`server-ops`/`AGENTS.md` 等） |
| `install-pnpm.sh` | 给 Node24 安装 pnpm（DSH 插件管理器会 spawn `pnpm add`） |
| `dsh-login.py` + `dsh-login-program.conf` | `/app-login` 的 cookie broker（从 `dsh.log` 取最新 token 换 DSH session；拿不到时 503，不循环跳转） |
| `nginx-dsh-proxy-common.conf`、`nginx-zz-dsh-gzip.conf` | nginx 反代公共头 / DSH 静态资源 gzip |
| `patch-dsh-login-nginx.py`、`patch-nginx-dsh-ratelimit.py` | 幂等修补 nginx 配置（`/app-login` 反代、`/app` 限流） |
| `patch-server-backup-dsh.py`、`patch-server-backup-sessions.py` | 幂等地把 DSH profile/sessions 纳入 `server-backup` |
| `dsh-web-cordis.patch.yml`、`dsh-web-profile-package.json` | DSH web profile 补丁/依赖清单（**已入库**；`dsh-web-cordis.patch.yml` 为服务器实际使用版本，profile 配置归档） |
| `analyze-dsh-runtime.sh`、`inspect-dsh-perf.sh` | 只读诊断：DSH 运行时/页面/nginx gzip 性能分析 |
| `termux-metrics.sh` | 早期 Termux 指标采集副本（输出 `$HOME/server-metrics.txt`）；**现行**版本在 `scripts/termux/` |

> 服务器侧 agent 的操作红线（Tier1/Tier2/Tier3、不得持有 Bridge token 等）见 [server/AGENTS.md](server/AGENTS.md)。

## 4. `scripts/dev/` — 开发工具

| 脚本 | 用途 | 用法 | 退出码 |
|---|---|---|---|
| `check-links.py` | 检查仓库 Markdown 的**相对链接与锚点**。扫描根：`README.md`、`CHANGELOG.md`、`docs/`、`android-bridge/`、`scripts/`；跳过 `.git`、`backup`、`inventory`、`tools` | `python scripts\dev\check-links.py` | `0` = 无缺失链接目标；`1` = 存在 error |
| `check-links.py --strict-anchors` | 同上，且把"锚点不存在"也视为 error（默认仅 warning） | `python scripts\dev\check-links.py --strict-anchors` | 同上 |

说明：

- 链接目标必须存在（相对当前文件解析）；`http(s)://`、`mailto:`、纯 `#anchor` 跳过检查。
- 绝对路径链接（以 `/` 开头）列为 warning；尽量使用相对路径。
- 文档改动后、提交前跑一次；本次重构的验收标准是**自己负责范围内 0 error**。

## 5. 常用命令示例

```powershell
# 设备连通 / 采集快照（PC）
... -File scripts\adb\check-connection.ps1
... -File scripts\adb\collect-device-info.ps1
... -File scripts\adb\probe-device.ps1
```

```powershell
# A+ 优化（先 DryRun，确认后 Apply，可 Restore）
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\adb\apply-a-plus.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\adb\apply-a-plus.ps1 -Apply
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\adb\apply-a-plus.ps1 -Restore
```

```bash
# 服务器内：状态/健康/Tier2 重启（--confirm 会写快照+审计）
server-ops status
server-ops health
server-ops bridge status
server-ops restart nginx --confirm
```

```powershell
# 构建 Bridge APK（PC；无需 Gradle，路径必须 ASCII）
powershell -NoProfile -ExecutionPolicy Bypass -File android-bridge\build.ps1
```

```powershell
# 文档链接检查（改完文档/提交前）
python scripts\dev\check-links.py
```

## 6. 旧路径 → 新路径对照（2026-11-11 迁移）

| 旧路径 | 新路径 |
|---|---|
| `scripts/adb.ps1`、`scripts/collect-device-info.ps1` 等 22 个 PC 脚本 | `scripts/adb/<同名>` |
| `scripts/termux-boot-01-api.sh`、`scripts/termux-metrics.sh` | `scripts/termux/<同名>` |
| `scripts/finalize-dsh-server.sh` | `scripts/server/finalize-dsh-server.sh` |
| `scripts/server/*`（其余） | 位置不变 |
| 旧仓库名 `D:\CODE\手机优化` | `D:\CODE\haydn-server`（aapt2 不支持中文路径） |

> 本文档只是索引；每个脚本的完整参数与行为以其源码头部注释为准。新增脚本请按分组放入对应目录并同步更新本文件。

## 7. 已知技术债与安全注意

| 项 | 说明 |
|---|---|
| 公网入口硬编码 | `scripts/server/console-api.py`、`scripts/server/import-server-credentials.py`、`scripts/adb/verify-research-env.ps1` 及 Console 页面源码中仍硬编码旧公网入口/IP/端口（**历史既有实现，非本次重构引入**）。文档已全部去敏（`docs/`+README+CHANGELOG 0 命中），但源码值仍在；后续建议外置到配置文件/环境变量并轮换入口。 |
| Bridge 密钥材料 | `android-bridge/signing.p12`、`assets/bridge.p12`、`certs/` 均 gitignored，**不得提交**；`build.ps1` 的默认 TLS/签名口令仅本地 MVP 使用，可用环境变量 `BRIDGE_TLS_PASS` / `BRIDGE_SIGN_PASS` 覆盖。 |
| 派生数据不入库 | `tools/uad_lists.json`（UAD-NG 第三方清单，约 1.6MB）已 gitignore、不入库；缺失时 `scripts/adb/uad-compare.py` 会提示下载地址。 |
| 未校验项 | 11 个 `.sh` 仅做内容迁移，未跑 `bash -n`（本机无可用 bash）；建议在 Termux/Linux 侧补一次语法校验。 |
