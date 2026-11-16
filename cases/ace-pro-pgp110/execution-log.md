---
id: APP-003
title: 一加 Ace Pro 案例附录：2026-11-13/14 真机执行记录明细（§6.1–§6.7）
type: case-study
status: current
audience: human, agent
tags: case, oneplus-ace-pro, root, chroot, super, liblp, fastbootd, appendix
depends: CASE-003, APP-001
updated: 2026-11-14
agent_hint: CASE-003 的结构性附录，承载 §6.1–§6.7 执行明细（服务器化、P1 管理面、恢复链、备份轮询、A 槽对齐、B 槽元数据恢复）；结论、验收口径与未完成项一律以 CASE-003 正文为准，本文件不改写事实。
---

# APP-003 · 真机执行记录明细（附录，§6.1–§6.7）

> 本文件由 [CASE-003](README.md) §6.1–§6.7 于 2026-11-14 **原样下沉**（用户授权结构拆分；事实、结论与未完成项未改写）；验收结论、风险登记与未完成项以 CASE-003 正文为准。P1 配置快照仍见 [APP-001](p1-config.md)。

### 6.1 服务器化准备（2026-11-13，部分完成）

| 项 | 结果 |
|---|---|
| 原生 chroot | Ubuntu Base 24.04.5 LTS arm64（官方发布；rootfs SHA-256 `a91d5a93010193712d346d761372b7c9db6dfcf093893161c64ca107f05914f2` 与官方 SHA256SUMS 一致）；解包到 `/data/server/rootfs`；bind `/proc /sys /dev /dev/pts`；apt 使用官方 ports 源且签名校验通过 |
| 服务基座 | supervisord 4.2.5（daemon 模式）+ Python 3.12.3；服务 `haydn-heartbeat`（心跳/负载/内存 CSV）与 `haydn-local-http`（仅 loopback、端口 18080）；已验证 supervisor 对单个服务的停止/重启自愈 |
| 开机自启 | KernelSU 模块 `server-chroot`（`service.sh` + `boot-completed.sh`）；5/5 次重启后 supervisor RUNNING、loopback 端口 LISTEN、心跳产生新 boot_id、遥测写入、iptables DROP 生效 |
| 特权遥测 | root 侧 5 分钟 CSV：uptime/load/CPU jiffies/可用内存/网卡字节/电池/温区/supervisor/HTTP；历史 soak 起点 2026-11-13 23:16（后因 P1 变更作废，P1 基线见 §6.2） |
| 入站最小化 | iptables + ip6tables 默认 DROP INPUT/FORWARD；白名单 lo/established/DHCP/NDP；带唯一注释规则可精准回滚（已实测 apply→restore→apply）；局域网入站 10150/18080 实测被阻断，设备出网正常 |
| chroot 基线 | `dd` 256MB（fsync）≈532 MB/s；chroot 内 uname/nproc/free 正常；proot 对照未做（Termux 未安装） |
| 观测与约束 | 内核无 `CONFIG_NF_TABLES` → 使用 iptables；无 user_ns/CGROUP_PIDS/NFT，cgroup v2 无委派 → 容器/systemd 仍不可用；电池 100%、电池温度约 28°C、温区峰值观测 82.2°C（只读，未改充电/温控） |
| 已知限制 | KernelSU 模块脚本运行在私有 mount namespace：chroot 挂载仅对该 namespace 内服务可见，ADB shell 侧需经入口脚本重新挂载；服务管理走 supervisor control socket；遥测循环无外部看门狗（模块仅开机启动一次） |
| 未完成（不得写"完成"） | tailnet 端到端 SSH 验证（需用户第二 tailnet 节点；本机自连超时）、夸克备份计划任务注册（自动化脚本已二次执行）与口令异地保管、定期恢复演练、24h soak（run #2 于 2026-11-14T06:01:16Z 提前中止，6.88h，非满期）、充电上限 80% 长时维持观测、proot vs chroot 基准、资源/电源调优、Uptime Kuma/外部告警、服务迁移、7 天双跑、生产割接 |

### 6.2 P1 管理面准备（2026-11-14，部分完成）

> 依据本地服务器化方案稿（P1：管理面、可观测、备份；方案稿为运行期分析产物，未入库）。本节只记录实测事实；未实测/未完成的项不写"通过"。

| 项 | 结果 | 证据 |
|---|---|---|
| 常电/唤醒 | `wake_lock=haydn-server` 已持有；屏幕 Asleep；Wi‑Fi power save **off**；三项均由 KernelSU 模块 `service.sh` 在 boot_completed 后重新应用（**5/5 重启验证通过**） | `/sys/power/wake_lock`、`iw dev wlan0 get power_save`、`/data/server/logs/boot.log` 中的 `P1 runtime:` 行 |
| 远程管理（Tailscale） | tailscale/tailscaled **1.104.7** 官方 static（下载后 SHA-256 校验一致）安装于 `/usr/local/bin`；tailscaled 以 userspace networking 运行（SOCKS 仅 `127.0.0.1:1055`）。**已用 auth key 登录成功**：`BackendState=Running`、节点名 `haydn-pgp110`、取得 tailnet 地址（具体 IP/DNS 不入库）；配置 **tailnet TCP 转发 `:22 → 127.0.0.1:22`**（tailnet-only，本机 sshd 仍仅 loopback）；tailscaled 重启后登录与转发配置保持（未重启设备）。auth key 以 `--auth-key=file:` 文件方式传递，临时文件已删除，未打印/未入库。**从其它 tailnet 节点做端到端 SSH 验证待用户**（本机自连超时属 userspace 模式限制，不作失败证据） | 安装日志、`tailscale status`/`serve status`、运行期验证输出 |
| SSH | openssh-server 9.6p1；仅 `127.0.0.1:22`；`PasswordAuthentication no`、`KbdInteractiveAuthentication no`、`PermitRootLogin prohibit-password`、`X11Forwarding no`；`sshd -t` 通过。临时 ed25519 密钥经 adb forward 端到端验证；长期管理员 ed25519 密钥亦验证通过。**用户自有 ed25519 公钥（轮换后、已取消口令）已安装并自动化端到端验证通过**（`uid=0(root)`/`USER_ONLY_OK`；设备端指纹 `SHA256:FnDTpacQ0ANDq6ao54QkeEJxH43dgu8/3Xif++qbKv0` 与用户公钥一致）；旧公钥与运行期管理员回退密钥均已从 `authorized_keys` 移除（仅保留用户公钥），旧管理员密钥登录已被拒绝（`Permission denied`）；Windows 端私钥 ACL 已收紧 | `sshd -T` 输出、`/etc/ssh/sshd_config.d/99-haydn.conf`、设备端 authorized_keys 指纹、运行期 SSH 验证输出 |
| 可观测 | prometheus-node-exporter 1.7.0 仅 `127.0.0.1:9100`；cron 每 5 分钟运行 `/usr/local/bin/haydn-healthcheck.sh`（检查 supervisor/http/node_exporter/sshd/disk），OK/FAIL 写 `/var/log/haydn/health.log`；telemetry-loop 每 5 分钟调用 `alert-watch.sh`，**FAIL 时在设备上发 Android 通知**并写 `/data/server/logs/alerts.log`（同一 FAIL 行去重，恢复 OK 自动清状态）。受控验证：暂停 local-http → `FAIL supervisor http` → 通知/告警日志 → 恢复 → `OK` | supervisor status、`health.log`、`alerts.log`、运行期验证输出 |
| 备份工具 | restic 0.16.4 与 rclone 1.60.1 已安装；restic 本机加密/恢复演练通过（19 文件、`check` 无错误、3 文件 SHA-256 MATCH，临时仓库已删除；**非持久备份**）。**夸克备份链路（2026-11-14）**：设备侧 tar.gz 快照（286 文件/37.4MB，含 MANIFEST SHA-256）→ PC AES-256-GCM 加密（scrypt 派生 + 认证头）→ Quark Skill CLI 上传到新建 `haydn-server-backup` 文件夹（首次 2 文件/37,420,075 B）→ 从网盘回下载复算 SHA-256 与本地一致；设备端恢复演练：解压 288 文件、MANIFEST **286/286 OK**。**自动化脚本（运行期 `inventory/quark-backup.ps1`）已二次执行成功**：code 0、2 文件/37,421,705 B 上传到同一目录；本地仅保留 `.enc`；加密口令保存在运行期 inventory（未入库，需异地保管）；**计划任务未注册、定期恢复演练未做** | 运行期快照/加密/上传/下载/恢复输出、自动化运行日志 |
| 定时/日志 | cron 3.0pl1（supervisor `haydn-cron` 运行 `cron -f`）；logrotate 3.21.0，配置 `/etc/logrotate.d/haydn`（weekly/rotate 4/compress） | supervisor status、配置文件 |
| 30 分钟满载热测试 | 7 线程满载 **1825s / 180 采样**：温区峰值 **79.0°C**（平均 74.4°C）、电池峰值 **35.9°C**、`load1` 峰值 12.32、可用内存最低 9.79GiB；未触发方案阈值（>80°C 暂停重任务 / >85°C 停服务 / 电池 >45°C 停机） | `/data/server/logs/thermal-30min-*.csv`（gitignored） |
| 重启矩阵（P1 后） | **5/5 重启**：每次 `boot_completed=1`、6 个 supervisor 服务 RUNNING、wake_lock/省电关闭/4 个 loopback 端口/iptables DROP 均符合 | 运行期逐次验证输出 + `boot.log` |
| 24h soak 基线（run #2） | 起点 **2026-11-13T23:08:20Z**（原计划 2026-11-15 07:08 满期）；run #1（2026-11-13T18:00:03Z 起）在 **4.91h** 后因遥测循环脚本故障于 22:54Z 中止（设备未重启），数据保留追溯但**不作为 24h 验收依据**；**run #2 由用户决定提前中止于 2026-11-14T06:01:16Z（6.88h），不作为满期通过**；中止记录留在设备 `/data/server/logs/soak-run2-abort-20261114.txt` | `soak-baseline.txt`、`telemetry.csv` |
| 遥测循环修复 | 2026-11-14 06:54–07:08（本地）发现遥测循环脚本运行时报 `syntax error: unexpected 'done'` 并退出，造成 **22:54–23:08Z 遥测缺口**（健康检查/uptime 未受影响）；改用 **LF 文本经 `adb push` 覆盖**、`sh -n` 通过、`setsid` 重启，并核对下一采集周期（23:08/23:13 正常），随后将 soak 基线重置为 run #2 | 运行期输出、`telemetry.csv` |
| soak 数据与中止 | run #1（已中止）：4.91h、60 个 5 分钟采样、0 缺口、0 重启、supervisord/http 可用率 100%；run #2（**提前中止，非满期通过**）：6.88h、83 个采样、无 >10min 断档、supervisord 与 chroot HTTP 均 83/83 up、`load1` 均值 3.11（峰 8.60）、可用内存最低 9.92GiB、电池 22.6–27.8℃、温区峰值 63.9℃、0 条新告警。数据保留供后续几天复查 | `telemetry.csv`（gitignored）+ 运行期统计脚本 |
| OTA/升级现状（2026-11-14 只读核对） | ColorOS 15.0.0.1901(CN01)、安全补丁 2026-07-01、活动槽 `_b`（A/B）、`verifiedbootstate=orange`、解锁+Root（KernelSU LKM 3.3.1）；`/data/ota_package/OTA` 下**无已下载载荷**；但存在 `can_update_at_night=1`、`oplus.ota.autoinstall.time=3:41`；2026-11-14 夜晚已执行 `settings put global can_update_at_night 0` 并**回读=0**（原值 1，快照 `inventory/ota-settings-before-20261114.txt`；回滚 `settings put global can_update_at_night 1`），**夜间自动更新已关闭**。是否升级/如何保留 Root 的评估登记为 [BL-032](../../backlog.json)（用户明确授权前不执行 OTA/刷写） | 运行期只读命令输出 |
| 充电上限（80%） | 2026-11-14 通过 ColorOS「电池健康」页开启**原生充电上限保护**：充电时电量最终维持 **80%**（可点"本次充满"临时到 100%）。开启后电池 100% 即停止充电（`status=Discharging`），状态键 `regular_charge_protection_switch_state=1`、`regular_charge_protection_status=1`，内核 `charge_control_limit=4`；回滚 = 同页关闭开关。**80% 长时维持待观测**（停充已确认） | UI 截图（运行期 inventory）+ settings 键值 + sysfs 读数 |
| 第三方应用清理 | 用户请求"删除无用第三方 APP"。2026-11-14 首轮按 [GRD-002](../../guardrails/GRD-002-no-system-package-uninstall.md) **仅 `pm disable-user --user 0`**：目标 41 个，新禁用 28（13 个已禁用），累计 45。**同日晚获用户明确授权后执行真正卸载**：先用 `com.unionpay.tsmservice` 小包试验确认 `pm uninstall --user 0` 对第三方包等同完整卸载（`/data/app` 目录消失、包列表移除、可用空间 +11,208 KB）→ 批次 1 卸载 20 个（19 个成功 + 试验包，释放 3,524,848 KB）→ 批次 2 按用户修正范围仅卸载 4 个（儿童模式/家人守护/翻译/搜狗输入法，释放 288,120 KB；`com.coloros.translate` 的"仍在列表"为 `pm list packages` 子串匹配误判，实测 `pm path` 为空、APK 目录已删）；整机可用空间 217,300,504 → 220,928,528 KB（净 +3,628,024 KB ≈ 3.46 GiB）。删除前把第三方包名/版本/APK 大小/路径写入 `/data/server/etc/package-inventory-20261114.txt`（随设备备份入包，可据此重装还原）。**保留**：讯飞输入法、便签、录音机、天气、邮件、文档阅读、快捷指令、文件管理、日历、计算器、时钟、指南针、备份恢复、KernelSU；系统包一律未卸载 | 运行期 `app-removal-20261114.log`、`pm list packages -3`（余 14 个）、`df /data` |
| 输入法（讯飞，唯一 IME） | 安装前 `ime list -s` 为空、默认/enabled 指向已禁用的 `com.baidu.input_oppo`（系统内无可用键盘）。2026-11-14 从讯飞官方下载接口取官方 APK（84,200,066 B，SHA-256 `6e65405b…48a0`；v1 证书主体 iFlytek、v2/v3 签名块存在、zip 完整）→ `adb install` 成功 → 版本 16.0.3/16002（uid 10343）→ `ime list -s` 可见并设为默认 → **实际按键验证**：短信输入框聚焦后 `mInputShown=true`、点 1/2/3 得 `text='123'`、退格清空（未发送任何短信）。最小权限：iptables/ip6tables 按 uid REJECT（计数 239/507 包被拒）、appops 后台/悬浮窗/通知与全部危险权限 ignore、百度输入法保持 disabled、开机由 `service.sh` 调 `ime-lockdown.sh` 重放；应用首页显示"网络故障"佐证断网。应用内云输入/账号开关未改（无命令入口，网络已封死）。回滚：`ime enable/set` 切回 → `pm uninstall com.iflytek.inputmethod` → 删除 `service.sh` IME 段（备份 `service.sh.bak-20261114-p2`） | 运行期 adb/uiautomator/dumpsys 输出 |
| 设备侧定时备份 | 2026-11-14 起备份脱离 Windows：`backup-loop.sh`（`service.sh` 开机拉起，pid 26486）每 60s 轮询，命中本地 03:30 且当日未跑（标记 `/data/server/run/backup-last-day`）触发 `haydn-backup.sh`：快照 → HYDNBK1 加密（scrypt+AES-256-GCM）→ **解密自检比对 SHA-256** → 夸克上传（3 次重试，退避 300/900s）→ 保留最近 7 份 → 清理临时明文；口令/凭据 600 权限、不入包不入日志。手工实测一次成功（`code 0`，2 文件/37,617,687 B；密文 37,617,580 B，PC 旧工具可解密且哈希一致）。**首次自动触发（2026-11-15 03:30）与重试/轮转分支未实测** | `/data/server/logs/backup.log`、`rootfs/var/backups/haydn/` |
| boot 分区备份（2026-11-14） | 导出 `boot_b`（`/dev/block/sde43`，201,326,592 B=192 MiB）→ `/data/server/backups/boot_b-20261114.img`；文件 SHA-256 与分区直读一致 `2cdcc6f5…a047`；元数据（槽 `_b`、`uname 5.10.236-android12-9-o-…`（KMI 推断 android12-5.10）、build `PGP110_11.H.25_3250_202606302344`、安全补丁 2026-07-01、ksud 3.3.1）存 `boot-backup-20261114.txt`；**PC 侧另存一份**，大小/SHA-256 复核一致、头部 `ANDROID!` 魔数可读。无 `init_boot` 分区；**回刷演练已完成**（2026-11-14，fastboot 37.0.3；三方哈希一致后原样刷回 `boot_b`，重启正常且哈希不变；见 §6.4） | 导出/哈希/PC 复核输出 |
| 入站最小化（复核） | iptables/ip6tables INPUT 仍为 DROP + lo/established/DHCP/NDP 白名单；新增监听 22/9100/1055/18080 **全部仅 127.0.0.1**；未开放局域网/公网新端口 | `iptables -S INPUT`、`ss -ltn` |
| 网络地址 | 按 [MTH-002 §5.3.1](../../methodology/01-assessment.md) 与 [PIT-021](../../pitfalls/PIT-021-dhcp-lease-assumption.md) 保持**动态地址 + 发现机制**（当前 DHCP `192.168.31.50/24`）；未固定 DHCP 租约/静态地址（需路由器权限，仅可选优化；与旧方案稿 P1 草案的差异已在此记录） | `ip -4 addr show wlan0` |
| 偏差/限制 | tailscaled 为 userspace 模式（未验证内核 TUN 模式；`/dev/net/tun` 状态待测）；tailnet 本机自连超时（userspace 自连不适用），**端到端 SSH 需用户第二节点验证**；Uptime Kuma 与外部告警通道未部署（需外部节点与凭据）；**充电上限语义未验证**（`charge_control_limit=0` / `max=4`、`charge_type=Standard`，未写测试值，避免误改 7×24 供电策略）；ADB 仍保持 USB 维护通道，待 tailnet 登录可用后再关闭 | 运行期记录 |

### 6.3 P1 配置要点（可复现，不含任何密钥）

配置摘要、部署前提（LF 文本 `adb push` + `sh -n` 校验）与回滚命令**原样下沉到附录** [p1-config.md](p1-config.md)（附录 APP-001，2026-11-14 快照；用户授权结构拆分，事实/结论/未完成项未改写）；本节不重复，避免两处漂移。

### 6.4 恢复链演练与 SOTA 安装（2026-11-14，实测）

> 用户决定不等 soak 满期，先执行重启环节，过几天再复查。刷写目标限定 `boot_b`，未触碰 `boot` 与槽 A；任何一步失败即停。

| 项 | 结果 |
|---|---|
| soak run #2 收尾 | **用户决定提前中止，非满期通过**：2026-11-13T23:08:20Z → 2026-11-14T06:01:16Z（6.88h，计划 24h）；83 个 5 分钟采样、无 >10min 断档；supervisord 与 chroot HTTP 均 83/83 up；`load1` 均值 3.11（峰 8.60）、可用内存最低 9.92GiB、电池 22.6–27.8℃、温区峰值 63.9℃、0 条新告警。中止记录存设备 `/data/server/logs/soak-run2-abort-20261114.txt`，`telemetry.csv` 保留供后续复查 |
| fastboot 来源 | 本机**无官方 platform-tools**；使用仓库工具链自带 fastboot **37.0.3**（`Pkg.Revision`），未引入其他来源或第三方刷机工具 |
| 刷前哈希 | PC 镜像、设备备份文件、当前 `boot_b` 分区直读三方 SHA-256 均 `2cdcc6f5…a047`，与 `boot-backup-20261114.txt` 一致；`boot_a` 仍 `b3e158a0…0e0b2e`（未动） |
| bootloader 只读查询 | `current-slot=b`、`slot-count=2`、`has-slot:boot=yes`；`slot-unbootable:a=yes`、`slot-unbootable:b=no`；`unlocked=yes`。**`rollback-index` 变量不支持**（`GetVar Variable not found`），防回滚索引仍**待验证** |
| 回刷 `boot_b` | `fastboot flash boot_b boot_b-20261114.img`：Sending OKAY 4.551s / Writing OKAY 0.422s；重启后 `boot_completed=1`、槽仍 `_b`，`boot_b` SHA-256 与备份一致（原样回刷未改变内容） |
| 重启后服务验证 | KernelSU 生效（`su -c id` uid=0、context `u:r:ksu:s0`、ksud 3.3.1）；模块 `server-chroot` enabled/1.0.0；supervisord/sshd(:22 仅 loopback)/tailscaled/http.server(:18080)/prometheus-node(:9100) 全部运行；HTTP 200；tailscale `haydn-pgp110` 在线；遥测恢复采样；Wi‑Fi power save off 且守护周期执行；`backup-loop` 当时记录为在跑（**06:29 复查发现实际已死，见 §6.5**）；开机后 firewall 与 IME 锁定规则重放 |
| 输入法实测 | 短信输入框实敲 `123`/`456` 上屏，`mCurMethodId=FlyIME`、`mInputShown=true`；appops 危险权限 ignore 与 iptables/ip6tables `REJECT uid=10343` 开机后已重放——此前"锁定规则生效"仅为推断，**本次实测确认**；测试后已还原 `stay_on_while_plugged_in=0` |
| SOTA 安装 | `com.oplus.ota` 页面点击"下载并安装"（14 个模块 APK，`shelf_pkg_total_size=649,471,952` B≈619.4 MiB），约 06:10Z 安装成功；**06:14:20Z 设备自动重启一次**（安装流程行为，按计划内重启处理并补做验证） |
| 安装后核对 | 14 个 APK versionCode **14/14** 与目标一致；被删应用 translate/sogouoem/brickmode/familyguard/unionpay 均 `pm path` 为空（**未被带回**）；第三方包仍 14 个；短信 App 可用、IME 复测通过；`boot_b` 哈希不变 |
| 槽状态 | **slot A 仍不可启动**（`slot-unbootable:a=yes`），按要求不修复；回滚路径仍为原厂 boot 恢复 → 槽 B 重刷 |

### 6.5 备份轮询修复与包基线（2026-11-14 下午，实测）

> 升级后只读体检发现 `backup-loop` 未存活；用户授权修复，全过程**未重启设备**。

| 项 | 结果 |
|---|---|
| 故障与根因 | 06:14 开机后轮询进程缺失：pidfile 仍为上一 boot 的 `7842`，旧逻辑用 `kill -0` 判活；重启后 PID 被复用导致新实例误判"已有实例"而 `exit 0`（`boot.log` 却仍写 started，具误导性）。根因属**推断**；已核验部分：pidfile 未更新、`backup.log` 无 06:14 start、进程不存在 |
| 修复 | pidfile 改存 `pid boot_id`；判活须同时满足 `/proc/<pid>/cmdline` 含 `backup-loop.sh` 且 boot_id 与当前 `/proc/sys/kernel/random/boot_id` 一致；`service.sh` 启动后 1s 校验 cmdline，仅在存活时写 `backup loop started`，否则写 `FAILED`，`service.sh done` 移至末尾。改动前脚本备份于 `/data/server/backups/script-backup-20261114T1435Z`（含 sha256.txt），回滚=复制回原路径 |
| 重启与去重 | 清除陈旧 pidfile 后启动，pid `20257`、pidfile 带 boot_id；再次执行立即退出 0 且不新增日志（去重生效） |
| 手动全链路 | 06:36:23Z START → 06:36:42 snapshot（SHA-256 `7c360e8d…feba9c`）→ 06:36:43 加密+解密自检哈希一致 → 06:36:54 上传成功（2 文件，夸克目录 `haydn-server-backup`）→ DONE ok；留存 2 份 `.enc`（KEEP=7，未触发轮转） |
| 03:30 触发条件 | 进程存活 + 本地时间恰为 `03:30` + `backup-last-day` ≠ 当日；只读确认方式：`ps -A` 查 `backup-loop`、读 pidfile 与 `/proc/<pid>/cmdline`、看 `backup.log` 的 start 行、`cat /data/server/run/backup-last-day`。本次为手动执行、未写当日标记，故 2026-11-15 03:30 仍会再跑一次 |
| OTA 设置 | `oplus.ota.autoinstall.time` 已恢复为 `3:41`（回读一致）；`can_update_at_night` 仍为 `0` |
| 包基线 | 全量 387 个（system 373 + third-party 14，disabled 13）落 `inventory/package-baseline-20261114.txt`（包名/versionName/versionCode/启停/类型），供下次升级比对 |

### 6.6 A 槽整套对齐与 A 槽首次可启动（2026-11-14 晚，实测）

> 用户授权；只动 A 槽（`boot_a` 除外，保 KSU 补丁），B 槽/`vbmeta_b`/userdata 全程未写。完整哈希、命令输出与账本在 gitignored `inventory/slot-a-align-case003-draft.md`、`payload_extract_a.log`、`flash-logical-a.log`、`lpdump-post-align.txt`。§6.4「slot A 仍不可启动」为当日 06:14 状态，已被本小节更新。

| 项 | 结果 |
|---|---|
| 固件匹配依据 | 官方全量包 `PGP110_15.0.0.1901_CN01_H.25_full_ota.zip`（7,223,765,587 B，SHA-256 `db588d43…a699`）；`metadata.txt` 的 ota-id/post-build=`PGP110_11.H.25_3250_202606302344`、patch 2026-07-01、ota-type=AB、pre-device=OP5551L1 与设备逐项一致；payload **无 `super` 整体镜像** → 只能逐分区刷 |
| 预检账本 | super=11,274,289,152 B/22,020,096 扇区，对齐前空闲仅 2,048 扇区=1.0 MiB；A 槽残留 cow system 678.2/vendor 133.3/odm 75.6/product 0.4 MiB；目标净增长 ≈+72.5 MiB；fastbootd 只暴露当前激活槽，必须先 `--set-active=a` |
| 空间释放 | 删 `system_a-cow` 释放 678.2 MiB（其余 A 槽 cow 与 B 槽 cow 未碰）；resize 后空闲 1,244,488 扇区=607.66 MiB（与 678.2−72.5 自洽） |
| 物理分区组 | 写前快照 5 分区 + 2 份 lpdump 原文到 `/data/server/backups/slot-a-pre-align-20261114/`（sha256.txt 齐全）；`vendor_boot_a`/`dtbo_a`/`vbmeta_a`/`vbmeta_system_a`/`vbmeta_vendor_a` 刷写全部 OKAY |
| 逻辑分区组 | 15 个 `_a` 分区 resize+flash 全部 OKAY（my_stock 16 个 sparse 分片 102s，整组约 4 min）；`partition-size` 按十六进制回读 **15/15** 与 payload 一致；`snapshot-update-status: none` |
| A 启动验证 | `slot=_a`、current=0/active=0、`boot_completed=1`、`verifiedbootstate=orange`；内核 `5.10.236-android12-9-o-g55571f3ffcfa`；ksud 3.3.1(uapi 5)、`su` uid=0 `u:r:ksu:s0`、Enforcing；supervisor **8/8 RUNNING**（cron/frpc/heartbeat/local-http/node-exporter/sshd/tailscaled/tls）；22/1055/9100/18080 仅 loopback、HTTP 200；INPUT DROP+DHCP 白名单、appops ignore 43、IME 仅讯飞；chroot/日志/遥测正常；backup-loop pid 7637 且 boot_id 匹配；`boot_a`=`boot_b`=`2cdcc6f5…a047` |
| 经验教训 | ①仅刷 `boot_a` 会 bootloop 且 USB 不枚举，只能物理键进 fastboot（本次 `--set-active=b` 回滚已实测可用）；②virtual A/B 的 super 余量可能 ≈0，整槽对齐前必须 `lpdump` 算账；③fastbootd 逻辑分区名须带 `_a`；④`fastboot partition-size` 返回十六进制 |
| 待验证（不写通过） | `my_preload_a`(1206 MiB)/`my_company_a` 按决定保留未对齐；引导链/基带未刷，与 B 槽底层是否一致**未知**；`boot_a` 仍为 B 版 KSU 内核（与已更新的 vendor_boot/dtbo 混搭），是否对齐待决策；B 槽未回确实测（`bootctl` 报两槽 bootable 属推断）；`rollback-index` **未知**；首次自动备份触发与 24h 满期 soak 未完成（run #3 新起点 2026-11-14T09:43:00Z） |

### 6.7 B 槽 liblp 元数据被覆盖与恢复（2026-11-14 深夜，部分验收）

| 项 | 结果 |
|---|---|
| 根因与证据（已核验/推断） | §6.6 的 fastbootd 逻辑分区写会把当前槽表按 `Metadata slot count: 3` 复制进各 metadata slot：pre-align `lpdump --slot 1` 为完整 B 表（7020 B、17 个 `_b` + 2 个 `_b-cow`），写后变成 A 表副本（7096 B，与 slot 0 完全相同）；slot1 ≡ slot0、super 前 2 MB（4 个 header）与末 512 KB 无 `system_b`/`vendor_b` 残留；B 的 `boot_b`/`vendor_boot_b`/`dtbo_b`/`vbmeta×3` 哈希仍等于 payload 且 `AVB0` 合法、pstore 空；A-pre 表为旧 build 布局 → 本轮前运行槽是 B（**推断**） |
| 修复过程（已核验） | ①整段备份 metadata 区 `/data/server/backups/super-meta-pre-bfix-20261114/super-head-512k.bin`（sha256 `ae91a2d7…091f5a`）+ 写入-还原演练（回滚 `dd if=<备份> of=/dev/block/by-name/super bs=4096 count=128 conv=notrunc && sync`）；②自建 liblp 序列化器对现网 A 表 round-trip **7096 B 逐字节一致**，再由 pre-align 文本重建 B 表 7020 B；③设备仅有 `lpdump`/`dmctl`（无 lpmake/lpflash），raw dd 写 slot1 primary `0x13000` 与 backup `0x43000` 各 64 KB（未写 slot 0、未写任何数据 extent） |
| 双回读（已核验） | slot0 primary/backup `d4cde900…`、`lpdump --slot 0` 摘要 `819f5863…` 均与写前一致；slot1 `1495823e…`，`lpdump --slot 1` rc=0、`Metadata size: 7020`、17 个 `_b` + 2 个 `_b-cow`，与 pre-align 逐行仅差 `Current slot`（运行时值）；8 服务/端口/遥测无变化 |
| 未验证（不写通过） | **B 能否启动未知**：B 数据区已被 A extents 覆盖 99.3%（未覆盖仅 `my_stock_b` 尾部约 71.6 MiB），cow extent 与 A live 数据的关系未知；用户决定**不做启动验证、维持单槽** |
| 硬约束 | **单槽模式**——禁止 `fastboot --set-active=b`；在 A 槽用 fastbootd 修改任何逻辑分区都会再次覆盖 metadata slot 1、使 B 元数据丢失；下次系统 OTA 前需评估该状态对非激活槽的影响 |

### 6.8 系统更新关闭（2026-11-16，用户决定冻结固件，已核验）

> 依据 [GRD-014](../../guardrails/GRD-014-firmware-freeze-ota.md)（冻结固件 + 关闭自动更新）与 §6.7 的单槽约束：非激活槽（B）元数据已被覆盖、数据区 99.3% 被 A 覆盖，**任何 OTA 都可能在重启切换到 B 时失败**，因此用户决定冻结固件、关闭系统更新。

| 项 | 结果 | 证据 |
|---|---|---|
| 用户决定 | 不升级，冻结在 ColorOS 15.0.0.1901(CN01C20P01)、安全补丁 2026-07-01；不触发 [PIT-023](../../pitfalls/PIT-023-oneplus-arb-hard-brick.md) 降级路径 | 用户 2026-11-16 指令 |
| UI 层关闭 | 「软件更新 → ⋮ → 自动更新设置」：**自动下载 = 关闭**、**夜间自动更新 = 关闭** | 运行期截图（UI 状态核对），设置页可复现 |
| 应用层关闭 | `pm disable-user --user 0 com.oplus.ota` → `new state: disabled-user`；`com.oplus.cota` / `com.oplus.romupdate` **保持启用**（维持系统完整性） | `pm list packages -d` 回读：`com.oplus.ota disabled=1` |
| 状态回读 | `com.oplus.ota.downloaded_status=0`（无待装包）；`can_update_at_night=0`；`/data/ota_package/OTA` 下 `.otaPackage`/`.localUpdatePackage` 均无载荷 | `settings get` + `ls` |
| 未做 | 未安装任何 OTA、未刷写、未改槽；A 槽保持当前运行槽与 KSU 补丁 boot | — |
| 回滚 | `pm enable com.oplus.ota` + 在「自动更新设置」恢复原选项（自动下载/WLAN、夜间自动更新）；若日后确需升级，必须重走 GRD-014 全流程（备份→官方 OFP→维护窗口→重 Root→全量验收） | — |
