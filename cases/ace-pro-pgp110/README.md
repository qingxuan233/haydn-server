---
id: CASE-003
title: 一加 Ace Pro（PGP110 / ovaltine）Root 实验平台预研
type: case-study
status: draft
audience: human, agent
tags: oneplus, ace-pro, pgp110, ovaltine, root, kernelsu, apatch, coloros, arb, chroot
depends: MTH-012, MTH-002, MTH-008, GRD-015, PIT-022, PIT-023, PIT-024, PIT-025
updated: 2026-11-14
agent_hint: 2026-11-13 真机已完成官方解锁 + KernelSU LKM Root + 3 轮救援演练，但 24h soak/chroot 基准/服务迁移未完成；2026-11-14 P1 管理面部分落地（Tailscale/SSH、80% 充电上限、无用应用禁用、Quark 加密备份跑通（自动化脚本二次执行））；2026-11-14 晚追加：讯飞输入法安装并最小权限化（唯一 IME）、24 个第三方包真正卸载（保留清单固定）、设备侧 03:30 定时加密备份上线、boot_b 备份已导出并异地校验，回刷演练与重启验证通过；2026-11-14 soak run #2 用户决定提前中止（6.88h，非满期）、SOTA 14 包安装并 14/14 版本核对；2026-11-14 下午修复 backup-loop 判活（pid+boot_id）并手动备份跑通、OTA autoinstall.time 恢复 3:41、包基线 387 个入库；2026-11-14 晚 A 槽整套对齐成功（A 槽首次可启动、8 服务 RUNNING、15/15 分区尺寸一致，boot_a 未动保 KSU 补丁），soak run #3 以 09:43Z 为新起点；2026-11-14 深夜 B 槽诊断：B 不可启动根因是 fastbootd 写 A 槽逻辑分区时把 A 的 liblp 表复制进 metadata slot 1（B 表被覆盖），已整段备份并重建 slot1 primary+backup 写回、slot0 未变，但 B 能否启动未知且用户决定不做启动验证 → **单槽模式：禁止 set-active=b，A 槽再跑 fastbootd 会重复覆盖 slot 1，下次 OTA 前需评估非激活槽影响**；不得标记生产可用，未实测项仍按 unknown 处理；2026-11-14 夜间按用户授权把 §6.1–§6.7 明细下沉为附录 [APP-003](execution-log.md)（仅结构外迁，未改事实）。
---

# CASE-003 · 一加 Ace Pro（PGP110 / ovaltine）Root 实验平台预研

> **状态：draft（部分实测）**。2026-11-13 已完成真机官方解锁与 KernelSU Root，并完成 3 轮救援演练；2026-11-14 P1 管理面部分落地（Tailscale 登录/SSH、充电上限 80%、无用应用禁用、Quark 加密备份跑通（自动化脚本二次执行））；2026-11-14 soak run #2 按用户决定提前中止（6.88h，**非满期通过**）、`boot_b` 回刷演练与重启验证通过、SOTA 14 包安装并核对通过；2026-11-14 晚 A 槽整套对齐成功、A 槽首次可启动（详见附录 [§6.6](execution-log.md)）；B 槽元数据被本轮 fastbootd 覆盖、已离线修复（slot 0 未变），B 能否启动**未验证**、维持单槽（详见附录 [§6.7](execution-log.md)）；chroot 基准、服务迁移与割接验收仍未完成。本页同时保留采购/规划结论与实测证据，未完成项不得表述为"已验证"。
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

> §6.1–§6.7 明细（服务器化准备、P1 管理面、P1 配置要点、恢复链与 SOTA、备份轮询修复、A 槽整套对齐、B 槽 liblp 元数据恢复）已**原样下沉**到附录 [execution-log.md](execution-log.md)（APP-003，2026-11-14 用户授权结构拆分；事实、结论与未验证项未改写）。P1 配置快照仍见 [p1-config.md](p1-config.md)（APP-001）。

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
- 2026-11-14 晚 A 槽整套对齐（用户授权）：A 槽 5 个物理分区 + 15 个逻辑分区对齐到 B 版 build、删 `system_a-cow` 释放 678.2 MiB、`boot_a` 未动；A 槽首次启动成功（8 服务 RUNNING、15/15 尺寸一致、super 空闲 607.66 MiB）；回滚路径不变，详见附录 [§6.6](execution-log.md)。
- 2026-11-14 深夜 B 槽元数据修复（用户授权，未切槽/未重启）：只写 `super` metadata slot1 primary+backup（未写 slot 0、未写数据 extent）；slot0 与写前逐摘要一致、slot1 恢复为 B 表（17 个 `_b` + 2 个 `_b-cow`）；**B 能否启动未验证**，维持单槽（禁止 `--set-active=b`），详见附录 [§6.7](execution-log.md)。

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
