# Redmi K40 Pro → 家用 Linux 服务器（项目：haydn-server）

把一台闲置的 **Redmi K40 Pro（M2012K11C / 内部代号 `haydn` / 骁龙 888 / SM8350）** 改造成一台低功耗、可远程维护的家用 Linux 服务器。

- 目标：SSH 远程登录、文件同步/备份、轻量 Web 与自托管服务、下载/定时任务
- 原则：**先零风险上线（Termux + proot），再用运行数据决定是否解锁 Root 升级**
- 状态：**P0 完成**；2026-11-10 发生过一次「误删系统必需包导致 bootloop」，已恢复出厂并**从备份重建服务器**（复盘见 [docs/08](docs/08-事故复盘与重置重建报告.md)）；当前 **11/11 服务 RUNNING**（CI Runner 常驻，卡片按治理移除），**控制台 v2 已上线**（实时指标/趋势/服务健康/日志/备份，见 [docs/13](docs/13-控制台功能分析与完善.md)）、**重启自动拉起（实测 43s 就绪）**、公网入口恢复
- 动态 IP / 入口切换：控制台自动检测当前局域网 IP；公网页面可一键跳到局域网，也支持 `?to=lan`（公网→局域网）与 `?to=public`（局域网→公网 HTTPS）自动跳转；WiFi IP 变化后仍可用固定公网入口 `https://47.97.70.99:44904/`（管理）或 `http://47.97.70.99:48108/`（只读），详见 [docs/13 §4.1/§4.3](docs/13-控制台功能分析与完善.md#41-动态-ip-兼容wifi-dhcp)
- 账号密码：**加密保险库**已上线（AES-256-CBC + HMAC，管理 token 解锁后可增删改查/搜索/复制/导入导出），并已导入服务器现有 **9 条**凭据（WebDAV/Gitea/Syncthing/Supervisor/DSH/备份口令/控制台 token/Runner token/SSH），详见 [docs/15](docs/15-账号密码保险库.md)
- 移动端：控制台已适配 390px 手机（**无横向溢出**、服务/检查/账号列表可折叠、吸顶快速导航、弹层底部抽屉），桌面端不变，详见 [docs/17](docs/17-控制台移动端适配.md)

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
| 能解锁 Root 吗？ | ❌ **不行（已确认）**：国行为 CN 区域，小米社区 App 无解锁入口（2026 年国行官方解锁关闭）→ 走 **A+ 无 Root 优化**（[docs/06](docs/06-A+优化方案.md)） |
| 解锁后 KernelSU 还是 Magisk？ | **Magisk 优先**（5.4 QGKI 非 GKI 2.0；KernelSU 需自编译内核） |
| 长期插电电池怎么办？ | 系统"充电保护" / Root 后 ACC 限充 60–80% + 通风散热 |

> **深度清理结果（2026-11-10）**：活跃包 **390 → 252 → 248**（二轮清理后）、禁用 10；MemAvailable **2.21 → 约 4.1 GiB**、/data 释放约 6GB；10 个服务器服务与 SSH 全程正常。详见 [docs/06](docs/06-A+优化方案.md)。

> **DSH 已重新部署于手机服务器（2026-11-10）**：Node 24 + @deepseek-ai/dsh 0.2.2-rc.1，127.0.0.1:3081，supervisord 托管；复用原 `https://<手机IP>:8443/app/` 入口（公网 `https://47.97.70.99:44904/app/`，Basic Auth），详见 [docs/07](docs/07-DSH与Linux优化.md)。

## 路线图

| 阶段 | 内容 | 状态 |
|---|---|---|
| **P0** | ADB 连通 + 设备建档 + 内核能力实测 | ✅ 已完成 |
| **P1** | Termux + SSH + 保活自启 + proot Ubuntu（2–3 小时） | ⬜ 下一步 |
| **P2** | 服务落地 + 7 天稳定观察 + 备份演练 | ⬜ |
| **P3** | Gate B0/B 决策：国行无法解锁 → **转 A+** | ✅ 完成 |
| **P4** | ~~B 路线~~（已取消） | ⛔ 取消 |
| **P5** | A+ 优化：设置/debloat 已落地；监控/网络/备份待办 | 🔶 进行中 |
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
│   ├── 05-B路线执行手册.md      ← B 路线手册（已归档：Gate B0 失败）
│   ├── 06-A+优化方案.md        ← **当前主方案**：无 Root 优化、已执行项、待办与回滚
│   ├── 07-DSH与Linux优化.md    ← 服务器 DSH 部署、Linux 优化、手机 ADB 第二轮分析
│   ├── 08-事故复盘与重置重建报告.md ← ⚠️ bootloop 事故、恢复出厂、服务器重建与开机自启验证
│   ├── 09-性能优化方案与可行性分析.md ← 下一轮 ADB/服务器优化清单与风险/收益评估
│   ├── 09-文件管理-文件夹打包下载.md ← /files/ 文件夹 zip 打包下载（API + UI + 安全边界）
│   ├── 10-面板治理-移除CI-Runner.md ← 面板删除 CI Runner 卡片 + 按需启用开关
│   ├── 10-DSH登录入口优化.md  ← /app/ 免 token 自动登录（dsh-login + nginx 入口标记）
│   ├── 11-DSH服务器配置与模型.md ← DSH server/web profile、desktop 模型配置迁移、凭据与环境
│   ├── 12-DSH性能优化.md   ← 运行环境分析、gzip/缓存/插件精简、优化前后对比
│   ├── 13-DSH插件安装-pnpm.md ← pnpm 缺失导致 ENOENT 的修复与 codex 插件验证
│   ├── 13-控制台功能分析与完善.md ← 控制台 v2：指标/趋势/服务/日志/操作/备份（参考成熟项目）
│   ├── 15-账号密码保险库.md ← AES-256+HMAC 加密、管理 token 解锁、增删改查/导入导出
│   ├── 17-控制台移动端适配.md ← 390px 手机布局、列表折叠、吸顶导航、底部抽屉
│   └── 11-移除DSH-GO-App环境SSH.md ← 删除旧 DSH-GO 的 App 环境 SSH（2224/57166）
│   └── research/
│       ├── raw-notes.md        ← 研究原始笔记与 33 条来源链接
│       └── ...
├── scripts/
│   ├── get-platform-tools.ps1  ← 下载 adb/fastboot 到 tools/
│   ├── adb.ps1                 ← adb 包装器（自动定位项目内 adb）
│   ├── check-connection.ps1    ← 连接状态检查（退出码 0/2/3）
│   ├── collect-device-info.ps1 ← 全量设备档案采集 → inventory/
│   ├── probe-device.sh         ← 设备端能力探测脚本（内核/容器/充电）
│   ├── apply-a-plus.ps1        ← A+ 设置优化/回滚（-Apply / -Restore）
│   ├── setup-dsh-server.ps1   ← 一键部署 DSH + Node24 到手机服务器（幂等）
│   ├── optimize-server-profile.ps1 ← 重置后安全优化（第三方移除 + 系统 disable，带保护名单）
│   ├── finalize-dsh-server.sh ← 服务器端 DSH 收尾（原生模块/包装器/supervisor/nginx）
│   ├── server/ubuntu.sh, 00-server.sh ← Termux 侧容器启动与开机脚本（重建用）
│   ├── server/termux-metrics.sh ← Termux 侧 CPU/uptime 采集器（供控制台）
│   ├── server/console-api.py    ← 控制台 API v2 源码（部署到 /root/server/api/app.py）
│   ├── server/console/          ← 控制台页面源码（部署到 /root/server/www/index.html）
│   ├── server/webui/            ← 文件管理器源码（含"下载整个文件夹"增强，见 docs/09）
│   └── server/www/index.html, server/bin/server-runner ← 面板与 CI Runner 按需启停脚本（docs/10）
│   ├── debloat-server-mode.ps1 ← 服务器模式深度清理（-Tier safe|aggressive|all，-Restore）
│   ├── phone-health.ps1       ← 温度/负载/磁盘/9 个服务健康检查
│   ├── restart-termux-services.ps1 ← 远程恢复 Termux/proot 服务（run-as，不需解锁）
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
6. **想在服务器里跑 DSH / 看 Linux 优化与 ADB 分析** → [07-DSH与Linux优化](docs/07-DSH与Linux优化.md)
7. **想了解 bootloop 事故与重置后重建过程** → [08-事故复盘与重置重建报告](docs/08-事故复盘与重置重建报告.md)
8. **想看下一轮性能优化方案与可行性分析** → [09-性能优化方案与可行性分析](docs/09-性能优化方案与可行性分析.md)
9. **想看安卓/小米深度操作调研、Shizuku/自建 ADB 等技能** → [14-安卓深度操作调研与技能沉淀](docs/14-安卓深度操作调研与技能沉淀.md)
10. **想看非官方 Root 路径的可行性与风险分析** → [16-非官方Root路径可行性与风险研究](docs/16-非官方Root路径可行性与风险研究.md)
11. **想从头复现这套研究平台（环境构建/踩坑/方法论）** → [17-研究平台环境构建手册](docs/17-研究平台环境构建手册.md)
12. **想看控制台/持久化/容器优化的下一步方案** → [18-控制台持久化与容器优化方案](docs/18-控制台持久化与容器优化方案.md)
13. **想看用 ADB 给服务器让资源的方案** → [19-ADB为服务器让资源方案](docs/19-ADB为服务器让资源方案.md)
14. **想看 DSH 作为服务器控制平面（管理/执行大脑）的方案** → [20-DSH控制平面方案](docs/20-DSH控制平面方案.md)
8. **想下载整个文件夹 / 了解文件管理器增强** → [09-文件管理-文件夹打包下载](docs/09-文件管理-文件夹打包下载.md)
9. **想了解面板为什么去掉 CI Runner / 如何按需启用** → [10-面板治理-移除CI-Runner](docs/10-面板治理-移除CI-Runner.md)
9. **打开 DSH 时提示 authentication required / 想免 token 登录** → [10-DSH登录入口优化](docs/10-DSH登录入口优化.md)
10. **想了解 DSH 服务器 profile / 模型配置 / 凭据** → [11-DSH服务器配置与模型](docs/11-DSH服务器配置与模型.md)
11. **DSH 有点卡 / 想做性能优化** → [12-DSH性能优化](docs/12-DSH性能优化.md)
12. **DSH 安装插件报 spawn pnpm ENOENT** → [13-DSH插件安装-pnpm](docs/13-DSH插件安装-pnpm.md)
10. **想清理旧 DSH-GO 的 App 环境 SSH / 2224 端口** → [11-移除DSH-GO-App环境SSH](docs/11-移除DSH-GO-App环境SSH.md)
12. **想了解控制台 v2 的功能分析与改进参考** → [13-控制台功能分析与完善](docs/13-控制台功能分析与完善.md)
13. **想管理账号密码 / 避免忘记密码** → [15-账号密码保险库](docs/15-账号密码保险库.md)
14. **手机上看控制台 / 移动端适配说明** → [17-控制台移动端适配](docs/17-控制台移动端适配.md)

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
