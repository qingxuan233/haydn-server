---
id: CASE-003
title: 一加 Ace Pro（PGP110 / ovaltine）Root 实验平台预研
type: case-study
status: draft
audience: human, agent
tags: oneplus, ace-pro, pgp110, ovaltine, root, kernelsu, apatch, coloros, arb, chroot
depends: MTH-012, MTH-002, MTH-008, GRD-015, PIT-022, PIT-023, PIT-024, PIT-025
updated: 2026-11-14
agent_hint: 2026-11-13 真机已完成官方解锁 + KernelSU LKM Root + 3 轮救援演练，但 24h soak/chroot 基准/服务迁移未完成；2026-11-14 P1 管理面部分落地（Tailscale/SSH、80% 充电上限、无用应用禁用、Quark 加密备份跑通（自动化脚本二次执行））；2026-11-14 晚追加：讯飞输入法安装并最小权限化（唯一 IME）、24 个第三方包真正卸载（保留清单固定）、设备侧 03:30 定时加密备份上线、boot_b 备份已导出并异地校验，回刷演练与重启验证通过；2026-11-14 soak run #2 用户决定提前中止（6.88h，非满期）、SOTA 14 包安装并 14/14 版本核对；2026-11-14 下午修复 backup-loop 判活（pid+boot_id）并手动备份跑通、OTA autoinstall.time 恢复 3:41、包基线 387 个入库；2026-11-14 晚 A 槽整套对齐成功（A 槽首次可启动、8 服务 RUNNING、15/15 分区尺寸一致，boot_a 未动保 KSU 补丁），soak run #3 以 09:43Z 为新起点；不得标记生产可用，未实测项仍按 unknown 处理。
---

# CASE-003 · 一加 Ace Pro（PGP110 / ovaltine）Root 实验平台预研

> **状态：draft（部分实测）**。2026-11-13 已完成真机官方解锁与 KernelSU Root，并完成 3 轮救援演练；2026-11-14 P1 管理面部分落地（Tailscale 登录/SSH、充电上限 80%、无用应用禁用、Quark 加密备份跑通（自动化脚本二次执行））；2026-11-14 soak run #2 按用户决定提前中止（6.88h，**非满期通过**）、`boot_b` 回刷演练与重启验证通过、SOTA 14 包安装并核对通过；2026-11-14 晚 A 槽整套对齐成功、A 槽首次可启动（详见 §6.6）；chroot 基准、服务迁移与割接验收仍未完成。本页同时保留采购/规划结论与实测证据，未完成项不得表述为"已验证"。
> 定位：生产机 [haydn K40 Pro](../haydn-k40pro/README.md) 继续无 Root 运行；本设备是**专用实验/候选服务器**。
> 用户决策（2026-11-11）：下一部手机选一加 Ace Pro 16+256GB 作为 Root 平台；接受解锁清数据、失保、硬砖与数据丢失风险；生产机不 Root。

---

## 1. 概况

| 项 | 值 |
|---|---|
| 市场名称 | 一加 Ace Pro（中国大陆版） |
| 型号 / 代号 | PGP110 / `ovaltine`（与 OnePlus 10T 同源，官方参数页图片路径亦为 ovaltine） |
| SoC / 内存 / 存储 | 骁龙 8+ Gen 1（SM8475）/ 16GB LPDDR5 / 256GB UFS 3.1 |
| 发布系统 | ColorOS 12.1（Android 12） |
| 已知后续系统 | ColorOS 15.0 正式版（2025-01 开放尝鲜，公开报道）；ColorOS 16 是否推送**待验证** |
| 硬件要点 | 6.7" 2412×1080 120Hz；双电芯 4800mAh / 150W；USB 2.0；无 microSD；Wi-Fi 6；NFC |
| 改造路线 | **B（已解锁 + Root + chroot）**；C/D 仅作后续研究，不默认 |
| 改造状态 | 部分实测（2026-11-13：官方解锁 + KernelSU Root + 3 轮救援演练）；2026-11-14 P1 管理面部分落地（Tailscale/SSH、80% 充电、应用禁用、Quark 加密备份跑通（自动化脚本二次执行））；2026-11-14 soak run #2 提前中止（6.88h，非满期）、回刷演练与重启验证通过、SOTA 14 包安装；chroot 基准/服务迁移/割接未完成 |
| 权威状态源 | 本页 + [profile.json](profile.json)（documented）；实测后另建运行期记录 |

---

## 2. 为什么是它（决策逻辑）

| 维度 | 判断 | 依据/等级 |
|---|---|---|
| 性能/内存 | 骁龙 8+ Gen 1 + 16GB，明显高于 haydn K40 Pro；适合编译、容器/ chroot、多服务 | 官方参数（高） |
| 解锁可能性 | 老机型/ColorOS≤15 不被 2026 新政策直接点名；一加传统上允许官方解锁 | 官方公告/社区（中，**未证实本机**） |
| Root 生态 | KernelSU/APatch 主流；社区有 KernelSU-Next 一加构建、TWRP device tree、非官方 LineageOS 21、/e/OS | 社区（中） |
| 救援资源 | PGP110 的 OFP 全量包在社区镜像可见；9008 工具存在但高风险 | 社区（中低） |
| 成本 | 2022 年机型，二手价低；16+256 是理想档 | 二手行情（中） |
| 风险 | ARB 可能延伸、二手电池衰减、USB 2.0、无存储扩展、官方保修到期 | 见 §7 |

> 选择它是"低成本可实验平台"，不是"最优服务器"；若要长期生产，后续应评估更新机型（但新机型解锁政策更严、ARB 风险更高，见 [PIT-022](../../pitfalls/PIT-022-oem-unlock-quota.md)/[PIT-023](../../pitfalls/PIT-023-oneplus-arb-hard-brick.md)）。

---

## 3. 公开证据摘要（只作线索，非本机实测）

| 主题 | 事实（摘要） | 等级 | 对本项目影响 |
|---|---|---|---|
| 一加解锁政策 | 2025-08-14 公告：ColorOS 16 起上调解锁方式；2026-07-24 调整深度测试条件：账号 60 天、实名/人脸、本机连续登录 7 天、30 天冷却、一年 ≤4 台、名额上限、14 天有效、7 工作日审核 | 官方公告+公开报道（高） | 新机型门槛高；Ace Pro 属老机型，是否豁免**待验证** |
| 政策分界 | 官方 QA：ColorOS 16+ / 升至 ColorOS 17+ 的机型走深度测试；未满足条件的旧 ColorOS 机型"不受影响" | 官方公告转述（中高） | 不能据此断定 Ace Pro 免流程；仍需按机型实测 |
| 深度测试适用范围 | 社区工具文档：深度测试适用于真我全系 + 一加 2025-10 后发布机型；其余机型选择"不需要深度测试" | 社区文档（中） | 暗示 Ace Pro 走旧/直接解锁；**待验证** |
| ARB 防回滚 | 一加在 ColorOS 16.0.3.500/501/503 引入硬件级 ARB（e-fuse）；触发后不能降级，旧固件/旧 ROM/EDL 救砖可能硬砖；已知机型 13/13T/15/Ace 5 系列 | 公开报道+社区（中高） | Ace Pro 若收到 COS16 需按最坏情况处理；Ace Pro 是否引入**待验证** |
| Root 实现 | KernelSU v3.0+ 主推 LKM：不替换原内核、可临时卸载、OTA 友好（GKI 2.0 前提；安装仍需刷入补丁后的 boot/init_boot，保留原厂备份）。APatch 要求 `CONFIG_KALLSYMS`；Magisk 兼容最广但 OTA 需恢复原厂镜像 | 官方文档（高） | 首选 KernelSU LKM；APatch 备选；Magisk 兜底 |
| 社区适配 | KernelSU-Next 一加构建仓库包含 Ace Pro/10T；TWRP for OnePlus 10T；非官方 LineageOS 21（Android 14）/e/OS 有 ovaltine 版本 | 社区仓库/论坛（中） | 有生态，但版本与质量需逐项核验 |
| 救援 | PGP110 OFP 全量包可见；9008 免授权工具与官方"熔断"计划并存；第三方一键工具箱闭源、报毒/服务端下发方案 | 社区（中低） | 救援包必须离线自备；不依赖闭源工具 |
| 二手电池 | 双电芯 4800mAh、150W；官方有电池更换活动（二手报道） | 二手报道（低） | 收货先测电池健康；预留换电池成本 |

> 本仓库不收录外链；以上来源名称/日期供人工复核。凡"待验证"项，不得写成本机结论。

---

## 4. 目标架构（Root 实验轨）

| 层 | 设计 | 说明 |
|---|---|---|
| 启动/自启 | ColorOS 原生启动 + Root 管理器 `service.d` 启动脚本 | 不依赖 OEM 自启动 UI；5 次重启验收 |
| Root | KernelSU LKM（首选）→ APatch（备选）→ Magisk（兜底） | 补丁目标按分区布局判定；保留原厂镜像 |
| 服务基座 | 原生 chroot（Debian/Ubuntu arm64）+ bind `/proc /sys /dev`；s6/supervisord | 替代 proot；先基准对比再切换 |
| 资源隔离 | cgroup 限额（若可用）；zram/sysctl 逐项调优 | 一次一项，带原值与回滚 |
| 网络 | 动态地址 + 发现；nftables 默认拒绝入站 + 白名单；维护走本地 console | 不硬编码地址；不开放公网 root shell |
| 观测 | 特权遥测（`/proc/stat`、`/proc/net/dev`、`dumpsys`、sysfs 电池/热区） | 只读、来源/新鲜度标注、缺失不补 0 |
| 电源/热 | 插电运行；温控只读观测；充电上限（若节点可写且验证安全） | 7×24 插电按 [GRD-008](../../guardrails/GRD-008-power-thermal-safety.md) |
| 更新 | 固件冻结；同版本或更新才可恢复；不降级；OTA 前恢复原厂镜像 | 见 [MTH-012 §7](../../methodology/11-root-lab.md) |

---

## 5. 阶段计划（未执行，按门禁推进）

| 阶段 | 任务 | 通过标准 | 状态 |
|---|---|---|---|
| R0 采购前 | 核对机型政策/版本/ARB/卖家来源；准备核验清单（§8） | G-L0 全项有证据；用户确认风险 | 已完成（2026-11-13） |
| R1 到货验收 | 只读采 identity/boot/kernel/电池；记录当前版本与解锁状态；禁止先升级 | 证据入库；无"待装更新" | 已完成（2026-11-13） |
| R2 救援与解锁 | 备齐原厂镜像/全量包/哈希/两条线/第二台电脑；按官方通道解锁 | G-L1..G-L4 通过；解锁后正常开机 | 已完成（2026-11-13，3/3 救援演练） |
| R3 Root | KernelSU LKM 补丁；零模块；su 最小授权；记录状态 | G-L5..G-L6 通过；5/5 重启 | Root 已通过；24h soak run #2 提前中止（6.88h，非满期） |
| R4 chroot 迁移 | 基线对比 proot；核心服务跑通；备份/恢复演练；特权遥测 | 基准/5 重启/恢复演练/24h soak | 部分完成（chroot/supervisor/遥测已跑通；回刷演练与重启验证已通过；基准与迁移待执行） |
| R5 双跑割接 | 隔离网段双跑 ≥7 天；按服务逐步切换；保留 haydn 回退 | 割接验收 + 回退演练 | 待执行 |

---

## 6. 2026-11-13 真机执行记录（部分验收）

> 证据摘要；完整命令输出、SHA-256 清单与救援包保存在运行期 `inventory/` 与 `tools/firmware/`（两者 gitignored，不入库）。本节不替代 G-R1..R5 与 §9 的完整验收。

| 项 | 结果 | 证据 |
|---|---|---|
| 设备身份 | 一加 Ace Pro / PGP110 / OP5551L1；ColorOS 15.0.0.1901(CN01)；Android 15；安全补丁 2026-07-01；内核 KMI 5.10-android12-9；A/B，无 `init_boot` | adb 只读 profile（运行期） |
| G-L1 固件 | 官方 CN CDN 全量包：包内 `ota-id/ota_version=PGP110_11.H.25_3250_202606302344`、`post-build` 与本机 fingerprint 一致；大小 7,223,765,587 B；官方对象 MD5 `82b83c3a733e802b0af51454230f10dc` 本地复算一致；本地 SHA-256 `db588d43afe556de0541a9863c39581b893f713a375de4d3d3dea4b7d40da699` | `rescue-kit --verify`：12 文件 ok |
| 原厂 boot | 从 `payload.bin` 按 dst_extents 提取 `boot` 分区（96 个操作），201,326,592 B；SHA-256 `0e2b315cc2ea38b93c12ad246c58f266883d27a1033039c6a5b6d5a9c2522689`，与 payload manifest `new_partition_info.hash` 相等 | 零依赖提取脚本 + manifest 哈希 |
| G-L4 解锁 | `fastboot flashing get_unlock_ability: 1`；`fastboot flashing unlock` 成功（清空数据）；`ro.boot.flash.locked=0`、`verifiedbootstate=orange`；dm-verity 与 SELinux 仍为 enforcing | adb/fastboot 输出 |
| G-L5 Root | KernelSU v3.3.1 LKM：APK/LKM/ksud 的 SHA-256 与官方 release digest 一致；补丁后 boot SHA-256 `2cdcc6f50832bb0c7c90ee22dfd47a1b3ccf390a6df4ae3509a632ed4540a047` 刷入 `boot_b`；`lsmod` 显示 `kernelsu` 已加载；管理器显示 Working；`/system/bin/su` 可用；`su -c id` 返回 uid=0，SELinux context `u:r:ksu:s0` | 运行期证据 + 管理器界面 |
| G-R 重启/演练 | Root 在 5 次重启后可用；3 轮「回刷原厂 boot → 正常开机且 Root 消失 → 重刷补丁 boot → Root 恢复」演练 3/3 成功 | 运行期 `boot_completed` / `su` 输出 |
| G-L6 基线 | SELinux=Enforcing；verity=enforcing；无第三方模块；ADB 仅 USB 调试；su 未授予第三方应用 | 运行期 `getenforce` / `getprop` |
| 工具限制 | `rootcheck` RC-T07 因 `detect` 将带 `-o-` 后缀的 OnePlus 内核判为 `gki_generation=legacy` 而 fail；实测 KernelSU LKM 已加载且 su 可用，按人工复核记录该启发式误判 | 运行期 profile/rootcheck JSON |

未完成（不得写"已验证"）：24h soak（run #2 用户决定提前中止，6.88h，非满期）、chroot vs proot 基准、nftables/网络基线、服务自启矩阵（服务尚未迁移）、7 天双跑、生产割接；生产 haydn 保持无 Root。

附带事实：解锁后 `verified_boot_state=orange` 属预期；未关闭 AVB/verity、未修改 `system`/`vendor` 动态分区、未由 Agent 执行系统包卸载/`disable-user`。研究阶段曾运行官方 ColorOS 助手进行版本查询，其环境检查自行临时卸载并重装了 `com.coloros.backuprestore`（官方工具行为，当前包已存在）；该过程未用于刷机，后续不再使用该工具。

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

---

## 7. 风险登记

| 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|
| 官方解锁不可用/需账号 60 天 | 中 | 计划停摆 | 采购前核实；先养账号；不买"已秒解"机器；不满足则换机 |
| ARB 触发/降级硬砖 | 中（若升 COS16） | 设备永久损坏 | 冻结固件；不降级；禁止清单；同版本救援包 |
| 9008 工具失效/供应链 | 中 | 救援失败/主机风险 | 不依赖；离线备份；哈希；隔离环境 |
| KernelSU/APatch 不兼容 | 中 | Root 失败 | 先按官方文档小步验证；失败恢复原厂 boot；备选方案 |
| 二手电池衰减/鼓包 | 中高 | 7×24 插电不安全 | 收货测健康；官方换电池；温控巡检 |
| 模块/OTA 回归 | 中 | bootloop/服务中断 | 最小模块；OTA 前恢复镜像；5 重启+soak |
| 指纹/完整性/DRM 回退 | 高 | 影响日常使用（实验机可接受） | 实验机不承载支付/银行；记录并告知 |
| USB 2.0/无扩展 | 确定 | 传输/备份慢 | 备份走网络/外置硬盘；不靠设备内唯一副本 |

---

## 8. 采购前 10 项现场核验清单

1. 卖家提供**当前 ColorOS 版本号/build 指纹**，并在"关于本机"现场核对一致。
2. 确认设备**未解锁/未 Root/未刷第三方 ROM**（或明确告知并降价）；不买来源不明"已秒解"机。
3. 确认**无 ColorOS 16 待装更新**；若有，先不装（ARB 风险）。
4. 核对版本后缀**不在 `.500/.501/.503` 禁止清单**；记录安全补丁日期。
5. 开发者选项是否存在 **OEM 解锁/深度测试入口**；现场只读查看，不点解锁。
6. 现场只读核对 `ro.boot.flash.locked`/`verifiedbootstate`/`build.fingerprint`（ADB 可用时）。
7. 电池健康：`dumpsys battery` 健康状态/循环估算（可用第三方只读 App）；外观无鼓包。
8. 确认 **16GB+256GB** 配置与实际存储一致；屏幕/触控/摄像头基本功能正常。
9. 确认 **USB 数据连接**可被 PC 识别（换线测试）；fastboot 模式可进入（只进入不刷写）。
10. 索要/确认 **OFP 全量包版本**与设备版本匹配；确认可离线保存。

---

## 9. 验收与回滚（摘要）

- 技术姿态：`python -m toolkit.repurpose rootcheck --profile cases/ace-pro-pgp110/profile.json --json`（`tech_ready` 只代表技术项，授权/救援/演练仍需人工确认）。
- 救援包：`python -m toolkit.repurpose rescue-kit --dir <kit> --init` 生成 SHA-256 清单，交付前 `--verify`；它只证明目录一致，不证明版本匹配/可救援。
- 验收：5/5 重启、24h soak、3 轮救援演练、chroot 基准、网络暴露扫描、su 审计、备份恢复演练（[MTH-008](../../methodology/07-validation.md)）。
- 回滚：原厂 boot 恢复 → 切槽（若支持）→ 官方全量包 → EDL（最后手段）；割接前 haydn 保持生产。
- **未实测项一律不写通过**；本页任何"通过"必须附日期、命令与证据路径。
- 2026-11-14 结构拆分（用户授权）：§6.3 P1 配置要点下沉为附录 [p1-config.md](p1-config.md)（APP-001）；案例事实/结论/未完成项未改写。
- 2026-11-14 boot 备份（用户授权）：当前槽 `boot_b` 已导出 `boot_b-20261114.img`（192 MiB，文件 SHA-256 与分区直读一致）+ PC 副本；**回刷演练已完成**（2026-11-14用户决定提前中止 soak 后执行：fastboot 37.0.3、三方哈希一致、原样刷回 `boot_b`、重启验证通过；见 §6.4）。
- 2026-11-14 SOTA（用户授权）：`com.oplus.ota` 安装 14 个模块 APK（619.4 MiB）成功，安装后自动重启一次；14/14 versionCode 核对一致，被删应用未回归；slot A 仍不可启动（未修复）。
- 2026-11-14 下午备份修复（用户授权，未重启）：`backup-loop` 判活改为 `pid+boot_id`+cmdline 校验并重启，手动全链路备份跑通（快照/加密/解密自检/上传/DONE）；`oplus.ota.autoinstall.time` 恢复 3:41；包基线 387 个落 `inventory/package-baseline-20261114.txt`（见 §6.5）。
- 2026-11-14 晚 A 槽整套对齐（用户授权）：A 槽 5 个物理分区 + 15 个逻辑分区对齐到 B 版 build、删 `system_a-cow` 释放 678.2 MiB、`boot_a` 未动；A 槽首次启动成功（8 服务 RUNNING、15/15 尺寸一致、super 空闲 607.66 MiB）；回滚路径不变，详见 §6.6。

---

## 10. 关联

| 入口 | 说明 |
|---|---|
| [MTH-012 Root 实验方法论](../../methodology/11-root-lab.md) | 门禁/选型/特权/OTA/救援/验收 |
| [GRD-015 Root 实验受控](../../guardrails/GRD-015-root-lab-controlled.md) · [GRD-001](../../guardrails/GRD-001-no-root-no-unlock-default.md) · [GRD-014](../../guardrails/GRD-014-firmware-freeze-ota.md) | 授权与红线 |
| [PIT-022](../../pitfalls/PIT-022-oem-unlock-quota.md) · [PIT-023](../../pitfalls/PIT-023-oneplus-arb-hard-brick.md) · [PIT-024](../../pitfalls/PIT-024-flash-tool-supply-chain.md) · [PIT-025](../../pitfalls/PIT-025-root-module-regression.md) | 风险证据 |
| [OEM profile](oem-profile.md) · [profile.json](profile.json) · [P1 配置附录](p1-config.md) | ColorOS/一加人工适配清单；机器档案；P1 配置快照 |
| [haydn K40 Pro 案例](../haydn-k40pro/README.md) | 生产基线/迁移源 |
| [MTH-004 服务器栈](../../methodology/03-server-stack.md) · [MTH-007 安全](../../methodology/06-security.md) | chroot/网络/安全通用规则 |
