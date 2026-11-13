---
id: MTH-012
title: Root 实验设备方法论：受控解锁与特权应用
type: methodology
status: current
audience: human, agent
tags: root, bootloader, kernelsu, apatch, magisk, lab-device, arb, ota, recovery, privilege
depends: MTH-002, MTH-003, MTH-007, MTH-008, GRD-001, GRD-004, GRD-005, GRD-014, GRD-015
updated: 2026-11-11
agent_hint: 只有"专用实验设备 + 用户书面授权"才可按本页推进；先过采购准入与救援演练，再解锁；生产/主力设备仍按 GRD-001 默认拒绝。
---

# MTH-012 · Root 实验设备方法论：受控解锁与特权应用

> **结论先行（MUST 可执行）**
>
> 1. **生产设备不因本方案改变**：haydn K40 Pro 继续走 A/A+（Termux + proot，无 Root）；Root 只进入下一部**专用实验设备**。
> 2. "可以 Root"不等于"默认可执行"：必须依次通过 §2 采购准入、§3 G-L1..G-L6 门禁与 §9 验收；任一 `unknown` 按未通过处理。
> 3. **解锁优先官方通道**：OEM 明确允许的深度测试 / `fastboot flashing unlock`（以机型现行政策为准）。禁止付费"秒解"、泄露账号、远程代刷、EDL 漏洞绕过解锁；**EDL/9008 只用于救援**，且必须来源可核验、固件版本匹配。
> 4. **Root 实现首选 KernelSU LKM**（注入模块、不替换原内核；安装时仅补丁并刷入 boot/init_boot，保留原厂备份；可临时卸载、OTA 友好）；APatch 为备选（要求 `CONFIG_KALLSYMS`）；Magisk 仅在兼容性确需时使用。所有镜像/二进制必须来自官方发布并校验哈希；闭源"一键刷机"工具不得作为唯一路径。
> 5. **Root 只作为能力提供者**：默认最小权限；系统级写、全局 SELinux permissive、关闭 AVB/verity、root shell 暴露到网络一律禁止（见 §5）。
> 6. **固件冻结优先**：解锁前关闭自动更新并记录版本；已触发硬件防回滚（ARB/e-fuse）的固件不得降级；末尾 `.500/.501/.503` 的 ColorOS 16 构建在确认前不得安装。
> 7. **未实测不标完成**：目标机型（一加 Ace Pro / PGP110 / ovaltine）的解锁可用性、Root 兼容性、ARB 状态、EDL 救援链路均为"待验证"（§11），任何文档不得写"已验证/已完成"。

---

## 1. 适用范围、角色与授权

| 项 | 内容 |
|---|---|
| 适用 | **专用实验设备**（无个人数据、无生产服务）；目标平台：一加 Ace Pro（中国大陆版 PGP110，代号 ovaltine，骁龙 8+ Gen 1，16GB+256GB） |
| 不适用 | 主力/生产设备（haydn K40 Pro）、含个人账号/数据/支付的设备、政企/运营商定制机、非本人设备 |
| 前置授权 | 用户**书面/会话内明确授权**该具体设备接受：BL 解锁清数据、保修/完整性失效、硬砖与数据丢失风险；授权记录写入案例或运行期记录，格式见 [GRD-015](../guardrails/GRD-015-root-lab-controlled.md) |
| 数据边界 | 实验机不登录个人账号、不存唯一副本数据、不承载生产服务；生产服务在割接验收前仍留在 haydn |
| 网络边界 | 实验机与生产机分 SSID/网段/凭据；Root 机默认不暴露任何管理端口到公网，维护用本地 console 或受控 LAN |
| 决策记录 | 2026-11-11 用户确认：下一部手机一加 Ace Pro 作为 Root 平台；接受硬砖/数据丢失风险；生产 haydn 保持不 Root |

> 本方法论是"允许做 Root"的**执行规范**，不是对 Root 的普遍放行；[GRD-001](../guardrails/GRD-001-no-root-no-unlock-default.md) 对非实验设备继续有效。

---

## 2. 采购前设备准入（G-L0）

采购/收货前逐项取证，不得凭发布会参数或卖家描述当实测。**G-L0 通过 = 每项都有证据等级与结论（有利或不利均可），未知项有补证计划，且用户已接受残余风险。**

| 维度 | 必须回答 | 目标机型当前结论（证据等级） |
|---|---|---|
| 解锁通道 | 现行官方政策、账号门槛、名额/有效期、是否需要深度测试、`fastboot flashing unlock` 是否可用 | 一加 2026 新政策针对 ColorOS 16+ 与 2025-10 后发布机型；Ace Pro 属老机型/ColorOS≤15，**是否免深度测试：待验证**（社区文档/论坛，非官方逐机型确认） |
| 防回滚 | 是否有 ARB/e-fuse；触发版本；能否降级 | 一加已对 ColorOS 16.0.3.500/501/503 引入硬件级 ARB（13/13T/15/Ace 5 系列等）；Ace Pro **是否/何时引入：待验证**；策略按"可能熔断"对待 |
| 内核与分区 | 内核版本/KMI、GKI 代际、`boot` vs `init_boot`、A/B | 骁龙 8+ Gen 1 + Android 12 起：GKI 2.0 可能性高；具体 KMI/分区**待实测** |
| Root 生态 | KernelSU/APatch/Magisk 社区实测；官方支持列表 | 社区存在 KernelSU-Next 一加构建、TWRP device tree、非官方 LineageOS 21 / /e/OS（社区证据）；本机兼容性**待实测** |
| 救援链路 | 官方全量包/OFP、boot 镜像、9008/EDL 工具与授权状态、能否离线保存 | PGP110 OFP 全量包在社区镜像站可见（社区证据）；9008 免授权工具存在但官方有"熔断"计划（高不确定）；**必须离线备齐并演练** |
| 硬件寿命 | 电池健康（双电芯 4800mAh / 150W）、USB 2.0、无 microSD、散热 | 二手电池衰减是主要不确定项；官方有电池更换活动（二手报道，待核）；存储 256GB 对服务器够用但无扩展 |
| ROM 生命周期 | 最后大版本、OTA 是否仍推送、社区 ROM 维护 | ColorOS 15.0 已于 2025-01 对 Ace Pro 开放（官方报道）；ColorOS 16 是否推送**待验证**；若推送且含 ARB，按 §7 处理 |
| 采购验收 | 卖家提供当前版本号/指纹、是否解锁/刷过、是否已熔断、能否当面验机 | 必须现场核验；**不买"已 root/已秒解"来源不明机器** |

---

## 3. 执行门禁（G-L1..G-L6）

> 阶段顺序不可跳；每阶段失败→停在上一稳定态，不"带病推进"。

| 门禁 | 目标 | 通过标准 | 失败回退 |
|---|---|---|---|
| **G-L1 救援包就绪** | 解锁前具备离线、可验证的恢复能力 | 与设备版本匹配的 `boot`/`init_boot` 原厂镜像、完整 OFP/固件包、SHA-256 清单、两条数据线、第二台电脑、恢复命令手册齐备；镜像与包来源可核验 | 缺任何一项→不解锁；先补包/换机 |
| **G-L2 数据与边界** | 解锁清数据可控 | 实验机无个人数据/账号/唯一副本；生产数据已留在 haydn 且有备份；记录设备初始状态（版本/指纹/解锁状态） | 有未备份数据→先迁移；不满足→不解锁 |
| **G-L3 固件冻结** | 避免 OTA/ARB 改变前提 | 关闭自动更新；记录 build/fingerprint/security patch；确认无待装更新；建立版本基线；`.500/.501/.503` 类构建打入禁止清单 | OTA 已装→重新评估解锁与 ARB 风险，不降级 |
| **G-L4 解锁** | 只做官方解锁，不做 Root | 按现行官方流程（深度测试或 OEM 允许的 fastboot 解锁）成功；`ro.boot.flash.locked=0` 类证据；解锁后先正常开机 1 次；不安装任何 Root/模块 | 解锁失败→停止，不尝试付费/漏洞通道；记录并换机 |
| **G-L5 Root 安装** | 最小化方式获得 su | 从**匹配版本**全量包提取 boot/init_boot；用官方 KernelSU 管理器/`ksud`（或 APatch）补丁并校验哈希/KMI；`fastboot flash` 对应分区；首次开机成功；`su -c id` 返回 uid=0；Root 管理器状态正常 | 不开机→按 §8 回滚原厂镜像；不反复盲刷 |
| **G-L6 最小权限基线** | 先收紧，再谈能力 | su 仅授权必要主体（人工 shell/指定脚本），关闭"默认允许"；不装第三方模块；SELinux=Enforcing；AVB/verity 未被关闭；ADB 维护后关闭；记录 su 授权与审计方式 | 任一不满足→回退到无 Root（恢复原厂 boot），重做基线 |

**执行纪律**：一次只改一个变量；每步留命令输出/截图/哈希；Root 后至少 24h 无异常才进入 §5/§6 的能力改造。
**工具辅助**：用 `python -m toolkit.repurpose rootcheck --profile <profile.json> --json` 汇总 §2/§3 的技术姿态（`repurpose.rootcheck.v1`）；`tech_ready=false` 时按 `checks`/`manual_checks` 补证据，工具不替代授权/演练人工确认。救援包可用 `rescue-kit --dir <kit> --init/--verify` 生成/校验 SHA-256 清单；它只证明目录与清单一致，不替代版本匹配与 G-R3 演练。

---

## 4. Root 方案选型

| 方案 | 机制/前提 | 优点 | 代价/风险 | 本项目结论 |
|---|---|---|---|---|
| **KernelSU（官方，LKM）** | GKI 2.0；LKM 注入内核模块；管理器/`ksud` 补丁 boot/init_boot | 不替换原内核、可临时卸载、OTA 友好（可装到非活动槽）、官方维护 | 需 KMI/安全补丁匹配；仍会刷入补丁镜像（须保留原厂 boot）；修改 `/system` 需 metamodule；部分机型不兼容 | **首选**（先验证管理器显示支持与 KMI） |
| **APatch** | 内核补丁；要求 `CONFIG_KALLSYMS`；ARM64、内核 3.18–6.12 | 可直接补丁原厂 boot；支持较广；TWRP 可刷 | 仅补 `boot`（禁止补 `init_boot`）；超级密钥管理；对 ROM 差异敏感 | 备选（KernelSU 不可用时；先查 KALLSYMS） |
| **Magisk** | 补丁 boot/init_boot + Zygisk/模块 | 生态最成熟、模块最多 | OTA 需先恢复原厂镜像；完整性/隐藏对抗成本高；模块冲突常见 | 兼容性兜底（不默认） |
| **KernelSU-Next（社区分支）** | 社区维护的 KernelSU 衍生；有一加构建 | 对新一加机型适配快 | 供应链/版本可信度低于官方；升级路径不统一 | 仅作参考/备选，须核验来源与哈希 |
| **自定义内核 / 第三方 ROM** | 解锁后刷入社区内核/ROM（如非官方 LineageOS） | 可开更多内核能力、摆脱 OEM 限制 | 极高风险、OTA 失效、相机/指纹/DRM 等兼容问题；ARB 下刷旧镜像可能硬砖 | **非默认**，须走 C/D 路线并单独授权 |

**补丁目标判定（MUST）**：设备若有独立 `init_boot` 分区则补 `init_boot`，否则补 `boot`；KernelSU/APatch/Magisk 各有约定，**不得混用**；补丁前核对内核 KMI 与安全补丁级别，避免"同 KMI 但补丁更旧"的回滚/引导失败。

---

## 5. 特权能力目录（"用起来"但受控）

Root 的价值是补齐 A 路线不可得能力；按优先级逐项引入，每项都有**收益、风险、护栏、验收证据**。
> 收益目标（目标值，非实测）：chroot 去掉 proot 的 ptrace 路径重写后，单核 CPU 开销应接近无 proot 基线（参考案例 proot 税 19–33% 单核，见 [PIT-007](../pitfalls/PIT-007-proot-overhead-thermal.md)）；实际以本机同一基准脚本前后对比为准，不达标不得宣称"性能提升"。

| 优先级 | 能力 | 收益 | 风险 | 最小护栏 |
|---|---|---|---|---|
| P1 | **原生 chroot**（Debian/Ubuntu arm64 + bind mount `/proc /sys /dev`）替代 proot | 去掉 ptrace 开销，接近原生 I/O/网络性能；可用发行版包管理 | 挂载错误导致数据不可见；服务隔离弱 | rootfs 快照；服务跑独立目录；启动脚本可回滚；先基准测试再迁移 |
| P1 | **特权遥测**（`/proc/stat`、`/proc/net/dev`、`dumpsys`、sysfs 电池/热区） | 精确 CPU/网络/温度/电池数据；替代桥的缺失字段 | 误读/伪造数据；隐私边界 | 只读；来源+新鲜度标注；缺失不补 0；脱敏入库 |
| P2 | **网络最小化**（nftables/iptables 默认拒绝入站、端口白名单、流量计量） | 比 App 层更可靠的暴露面控制 | 规则错误锁死远程维护；重启丢失 | 规则快照+定时回滚；保留本地 console；变更后立即本地验证；持久化脚本幂等 |
| P2 | **服务与自启**（Root 管理器支持的启动脚本（模块 `service.sh`/`service.d`，按官方文档）、s6/supervisord、看门狗） | 不依赖 OEM 自启动白名单；重启自愈 | 启动脚本死循环拖慢开机 | 超时/退出码/日志；失败降级；5 次重启验收 |
| P3 | **资源与电源**（cgroup 限额、zram、swappiness、充电上限/温控只读） | 服务器长稳、降低 OOM/热降频 | 参数不当导致卡顿/耗电/电池损伤 | 一次一项；记录原值；压测+24h soak；异常即回滚 |
| P3 | **调度/频率**（仅限已验证节点，如 `sched_*`/`cpufreq` 可写时） | 峰值性能/能效优化 | 热失控、随机重启、寿命损耗 | 温度墙优先；不做"禁用温控"；可写性先实测；回滚脚本 |
| P4 | **系统级模块/overlay**（systemless 挂载、/system 文件替换） | 免改分区实现定制 | 模块冲突→bootloop；OTA 后失效 | 最小模块集；一次一个；保留原厂镜像；模块清单与版本固定 |

**即使有 Root 也不做（MUST NOT）**

- 关闭 AVB/verity、全局 `setenforce 0`、修改 `system`/`vendor` 动态分区；
- 卸载系统包（只允许 `disable-user`，见 [GRD-002](../guardrails/GRD-002-no-system-package-uninstall.md)）；
- 禁用温控/充电保护、绕过电池安全策略；
- 对公网开放 root shell、管理面、ADB；
- 安装来源不明的闭源"一键 Root/救砖"工具作为唯一手段；
- 用 Root 权限"顺手"改生产机或他人设备。

---

## 6. 服务器栈迁移（Root 可用时）

| 项 | 无 Root（A/A+，现状） | Root 实验机（B） | 迁移建议 |
|---|---|---|---|
| 运行环境 | Termux + proot-distro | 原生 chroot（可选 Termux 作引导/兜底） | 先并行跑基准，再切主链路 |
| 服务管理 | supervisord/s6 | s6/supervisord（root 下更可靠）；不假设 systemd | 统一用可回滚的 supervisor 配置 |
| 数据面 | proot rootfs + Termux home | 独立数据目录 + 快照/备份脚本 | 数据迁移演练一次，校验哈希 |
| 容器 | 通常不可用（G-B2 失败） | Root 可能满足部分前提，但 Android 内核/SELinux 仍可能限制 | 仅当 `G-B2` 全 pass 再试；失败退回 chroot，不硬刚 |
| 观测 | Termux 采集 + 桥 | 特权遥测补齐 | 字段来源/新鲜度不变；不做假数据 |
| 网络 | 动态地址 + 发现兜底 | 同上 + nftables 白名单 | 地址仍不得硬编码；隔离生产/实验网段 |
| 电源/热 | 插电 + 温控策略 | 增加充电上限/温控只读观测 | 7×24 插电按 [GRD-008](../guardrails/GRD-008-power-thermal-safety.md) 管理 |

**迁移顺序（MUST）**：先备份 haydn 生产数据与服务清单 → 实验机搭 chroot 并用基准脚本对比性能 → 同一套服务在实验机跑通→双跑 7 天 → 再决定是否割接。**割接前 haydn 保持可回退，不得先拆生产。**

---

## 7. 固件、OTA 与防回滚策略

1. **解锁前冻结**：关闭自动更新，记录 `build.fingerprint`/版本号/安全补丁；把"不升级"作为解锁前提（[GRD-014](../guardrails/GRD-014-firmware-freeze-ota.md)）。
2. **不降级**：任何已触发 ARB 的固件，禁止刷入更旧版本/旧第三方 ROM；旧镜像可能直接硬砖且 EDL 救不回（见 [PIT-023](../pitfalls/PIT-023-oneplus-arb-hard-brick.md)）。
3. **禁止清单**：ColorOS 版本号末尾 `.500/.501/.503`（已知 ARB 触发批次）；收到系统更新提示先查该构建是否在清单内，确认前不装。
4. **OTA 后重 Root**：KernelSU LKM 可用"安装到非活动槽"；Magisk 需先恢复原厂镜像；APatch 需重新补丁匹配版本。任何 OTA 后都必须重跑 §9 验收与救援演练。
5. **版本一致性**：补丁镜像、OFP、boot 备份必须对应同一构建；混版本=高风险。
6. **若必须升级**：先备份/导出数据 → 恢复原厂镜像并解除 Root → 升级 → 重新解锁/Root 评估（解锁状态通常保留，但 ARB 与政策可能变化）→ 重跑验收。升级后不得假设 Root 仍可用。

---

## 8. 救援与回滚阶梯

| 级别 | 手段 | 前提 | 风险 |
|---|---|---|---|
| 1 | `fastboot flash boot <stock>` 恢复原厂 boot/init_boot | 有匹配镜像、fastboot 可用 | 镜像版本错→不开机 |
| 2 | A/B 切槽（若设备支持） | 另一槽可启动 | 切槽后数据/版本状态需核对 |
| 3 | 官方 Recovery/全量包恢复 | 官方包签名匹配、ARB 未阻止 | 可能清数据 |
| 4 | EDL/9008 深刷 | 匹配 firehose/loader + 完整 OFP；工具来源可核验；ARB 未熔断 | 硬砖、保修、供应链风险；**禁止用于绕过解锁** |

- **演练是验收前提**：解锁后至少完成 **3 轮"制造可恢复故障 → 按阶梯恢复 → 服务复验"**；只写方案未演练=没有回滚（[GRD-004](../guardrails/GRD-004-backup-before-change.md)）。
- 回滚包离线保存两份（不同介质），记录 SHA-256；不依赖网盘/单台电脑。
- 重新上锁（relock）只允许在**完全恢复官方系统**后执行；有修改时上锁可能直接不开机。

---

## 9. 验收（Root 轨）

| 验收项 | 通过标准 | 证据 |
|---|---|---|
| Root 存活性 | Root 管理器与 `su` 在 5/5 重启后可用 | 每次重启记录 |
| 服务自启 | 重启后核心服务/端口/健康检查自动恢复 | 5 次矩阵 + 日志 |
| 稳定性 | 24h soak 无崩溃循环；温度/负载在预算内 | soak 记录（[MTH-008](07-validation.md)） |
| 特权最小化 | su 授权清单最小；SELinux Enforcing；无公网管理面 | 审计输出/配置快照 |
| 救援 | 3 轮恢复演练全部成功 | 演练记录 |
| 迁移 | chroot 基准优于 proot 目标值（目标值先定义，后填实测） | 前后对比 |
| 数据 | 备份可恢复；无唯一副本只存在实验机 | 恢复演练 |
| 文档 | 版本/命令/回滚路径可交接 | 案例 README + runbook |

> 未完成 soak/演练/迁移验收 → 状态只能是"实验机可用"，**不得标记为生产可用**（[GRD-013](../guardrails/GRD-013-no-fake-acceptance.md)）。

---

## 10. 割接与回退（haydn → 实验机）

1. **双跑**：实验机以同一服务清单在隔离网段运行 ≥7 天；haydn 继续对外服务。
2. **切换窗口**：低峰期切换；先切只读/低风险服务，再切核心；每步有回退命令。
3. **回退**：保留 haydn 原配置与数据快照；实验机故障→按 §8 恢复或直接切回 haydn；回退后复盘。
4. **不拆旧**：实验机稳定 ≥7 天且用户确认后，才考虑将 haydn 降为冷备/研究机；不提前清空。

---

## 11. 待验证清单（不得写成已完成）

| 项 | 当前证据等级 | 补证方式 | 阻塞 |
|---|---|---|---|
| Ace Pro 官方解锁是否可用、是否需深度测试/账号门槛 | 社区文档/论坛，**未证实** | 收货后现场核对版本→开发者选项→fastboot 只读探测→官方公告逐条比对 | 是（G-L4） |
| 是否已/将触发 ARB，哪些构建熔断 | 官方/媒体对一加 13/15/Ace 5 有报道；Ace Pro **未证实** | 核对 build 后缀、厂商公告、社区熔断报告；不降级 | 是（§7） |
| 内核版本/KMI/GKI/分区布局（boot vs init_boot、A/B） | 参数页+社区，**未实测** | `getprop`/`uname -r`/全量包解包后核对 | 是（G-L5） |
| KernelSU LKM / APatch / Magisk 在本机兼容 | 社区构建存在，**未实测** | 按官方安装文档小步验证；失败回退原厂 boot | 是（G-L5） |
| chroot 相对 proot 的实测收益 | 理论/社区，**未实测** | 同一基准脚本对比 CPU/IO/网络 | 否（但影响割接） |
| 9008/EDL 救援链路可用性 | 社区工具/授权状态不稳，**未证实** | 仅救援时验证；优先 fastboot/官方包；不依赖 | 是（G-L1/§8） |
| 二手电池健康、长期插电温控 | **未实测** | 收货后 `dumpsys battery`/sysfs + 24h 观测；必要时官方换电池 | 否 |
| ColorOS 15 及更早的权限重置/自启策略 | 参考小米案例，**未证实** | 按 OEM profile 逐项实测 | 否 |

---

## 12. 关联

| 入口 | 说明 |
|---|---|
| [MTH-002 评估](01-assessment.md) · [MTH-003 路线图](02-roadmap.md) | 路线门禁 G-B0/B1/B2 与 P4 决策；本文是其"实验设备执行细则" |
| [MTH-004 服务器栈](03-server-stack.md) · [MTH-007 安全](06-security.md) · [MTH-008 验收](07-validation.md) | chroot/特权/安全/验收的通用规则 |
| [GRD-001 默认不 Root](../guardrails/GRD-001-no-root-no-unlock-default.md) · [GRD-015 Root 实验受控](../guardrails/GRD-015-root-lab-controlled.md) · [GRD-014 固件冻结](../guardrails/GRD-014-firmware-freeze-ota.md) | 红线与例外边界 |
| [PIT-022 解锁政策门槛](../pitfalls/PIT-022-oem-unlock-quota.md) · [PIT-023 ARB 硬砖](../pitfalls/PIT-023-oneplus-arb-hard-brick.md) · [PIT-024 第三方工具供应链](../pitfalls/PIT-024-flash-tool-supply-chain.md) · [PIT-025 Root 模块回归](../pitfalls/PIT-025-root-module-regression.md) | 已知风险证据 |
| [一加 Ace Pro 预研案例](../cases/ace-pro-pgp110/README.md) · [OEM profile](../cases/ace-pro-pgp110/oem-profile.md) | 本方法论的实例化与采购核验清单 |
| [toolkit assess/plan/rootcheck/rescue-kit](../toolkit/README.md) | `assess` 输出 G-B0/B1/B2；`rootcheck` 查技术姿态（不改路线顺序，`--strict` 非 tech-ready 退 4）；`rescue-kit` 生成/校验救援包 SHA-256 清单（G-L1 辅助） |
