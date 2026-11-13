---
id: MTH-002
title: 评估与可行性决策
type: methodology
status: current
audience: human, agent
tags: assessment, feasibility, decision, gate, oem, profile
depends: MTH-001
updated: 2026-11-11
agent_hint: 新设备接入第一步；先 detect 再 probe，然后 assess；未知字段一律走保守路线并降置信度。
---

# MTH-002 · 评估与可行性决策（核心 SOP）

> **结论先行**：改造任何设备前，必须先完成 **detect → probe → assess → 人工复核** 四步，产出结构化设备档案与路线结论。
> **默认结论是 A 路线**（无 Root 的 Termux + proot）；B/C/D 只有在对应门禁**全部通过**且设备所有者明确授权后才可实施。
> **未知字段不臆测**：写进 `unknowns`/`assumptions`，按保守规则降级并降低 `confidence`；门禁 `unknown` 视同未通过。
> 工具契约：输入 `repurpose.device-profile.v1`，输出 `repurpose.assessment.v1`；字段与门禁以 [toolkit schema](../toolkit/schema/device-profile.schema.json) 与 `toolkit assess` 为准。

---

## 1. 输入与输出

| 项 | 内容 |
|---|---|
| 输入 | 设备档案 `profile.json`（schema `repurpose.device-profile.v1`）；可选 OEM 现场信息、用户约束确认 |
| 输出 | 评估 JSON（schema `repurpose.assessment.v1`）：`route`/`route_hint`/`route_label`/`confidence`/`gates`/`blocked`/`alternatives`/`risks`/`next_steps`/`assumptions`/`unknowns` |
| 触发时机 | 新设备接入；换机迁移；系统大版本升级后复核；修复后重新评估（**不允许跳过**） |
| 存储与退出 | 运行期档案写入 `profiles/`（gitignored，含隐私），仅脱敏样例进入案例层；门禁 G-A 通过 + 人工复核签字后结束（记录在评估记录或案例 oem-profile） |

---

## 2. device-profile Schema（`repurpose.device-profile.v1`）

**顶层结构**：`schema` · `generated_at`（UTC ISO）· `source` · `identity` · `boot` · `root` · `kernel` · `hardware` · `storage` · `crypto` · `features` · `constraints` · `unknowns[]` · `evidence_refs[]` · `warnings[]`。

| 顶层 | 内容与约束 |
|---|---|
| `schema` / `generated_at` | 固定 `repurpose.device-profile.v1`；时间用 UTC ISO；评估必须能追溯到采集时刻；版本不匹配应拒读并提示升级 |
| `source` | `mode: adb`（真机探测）/ `fixture`（离线测试）/ `documented`（文档或社区证据）/ `manual`（人工填写）；`commands[]`、`notes` |
| `unknowns[]` | 未知/待验证字段名或问题；每个 unknown 必须有验证计划（否则视为评估未完成） |
| `evidence_refs[]` | 证据引用：命令文本或相对路径；**不得**写 IP/端口/token/序列号 |
| `warnings[]` | 采集异常（权限不足、字段缺失、读取失败等）；不得静默丢弃 |
| probe 扩展（可选） | probe 后在 profile 副本追加：`capabilities`（12 项 `{status,evidence}`）、`verdicts`（summary/route_hint/items）、`probe`（probed_at/mode/commands） |

**分组字段（字段名必须与工具一致）**

| 分组 | 关键字段 | 说明/用途 |
|---|---|---|
| `identity` | `codename`, `model`, `market_name`, `manufacturer`, `brand`, `product`, `fingerprint`, `android_version`, `sdk`(int), `build_id`, `build_type`, `security_patch`, `serial`（默认 null）, `serial_redacted`(bool) | 身份与版本；**序列号不入库**；决定 OEM profile 查找 |
| `boot` | `bootloader_unlocked`(bool/null), `verified_boot_state`, `vbmeta_device_state`, `dm_verity_mode`, `selinux`, `slot_suffix`, `partition_style`（"A/B"/"A-only"）, `has_init_boot`, `oem_unlock_policy`（"open"/"available"/"closed"/"unknown"）, `oem_unlock_evidence` | A/B 路线的第一分叉；`oem_unlock_policy` 是 G-B0 的唯一依据，证据写入 `oem_unlock_evidence` |
| `root` | `state`（"none"/"magisk"/"kernelsu"/"apatch"/"unknown"）, `su_available`, `root_manager_packages[]`, `adb_uid`, `ro_secure`, `ro_debuggable` | 判断当前 root 状态；决定 G-B1 |
| `kernel` | `release`, `version_string`, `arch`, `gki_generation`（"gki-2.x"/"gki-1.x"/"legacy"/"unknown"）, `config_source`, `config_readable` | 决定 root 方案与容器/内核能力的可信度 |
| `hardware` | `soc{manufacturer,platform,model,marketing_name}`, `cpu{cores,abi[],governors[],clusters[{policy,cpus,governor,scaling_max_freq_khz,hw_max_freq_khz}]}`, `memory{total_kb,available_kb,swap_total_kb}`, `display{width_px,height_px,density_dpi,refresh_hz}`, `battery{design_capacity_mah,charge_full_mah,level_pct,temperature_c,health,status,voltage_mv,charge_control_nodes[]}`, `thermal{zone_count,status,max_temp_c}` | 资源预算、温度/充电策略、长期插电风险；`charge_control_nodes[]` 决定能否限充 |
| `storage` | `data_total_kb`, `data_used_kb`, `data_available_kb`, `data_filesystem`, `external_sdcard`, `external_expandable`, `zram`, `zram_total_kb` | 容量与日志/备份预算；外置存储决定异地备份可行性 |
| `crypto` | `userdata_encrypted`, `encryption_type`（"FBE"/"FDE"/"none"/"unknown"）, `keystore`（"tee"/"strongbox"/"software"/"unknown"）, `play_integrity_required`(bool/null), `play_integrity_level` | FBE 影响无人值守自启；完整性要求影响是否可解锁 |
| `features` | `user_ns`, `pid_ns`, `mount_ns`, `net_ns`, `uts_ns`, `ipc_ns`, `cgroup_v1`, `cgroup_v2`, `cgroup_v2_delegation`, `overlay_fs`, `binfmt_misc`, `seccomp_filter`, `kallsyms`, `modules`, `ptrace_allowed`, `native_linux_port`, `custom_kernel`, `termux_available`, `shizuku_available`, `boot_completed_receiver`（均 bool/null） | 容器（USER_NS/PID_NS + cgroup 委派）、systemd 可行性、原生移植、root 方案的前提；`unknown` 不得当真 |
| `constraints` | `external_storage`（"none"/"expandable"/"unknown"）, `oem_autostart`（"manual-required"/"supported"/"blocked"/"unknown"）, `background_execution`（"restricted"/"normal"/"unknown"）, `battery_long_term_plugged`（"unknown"/"acceptable"/"risky"）, `root_required_capabilities[]`, `notes[]` | 现场限制与用户约束的落点；`root_required_capabilities[]` 列出"必须 root 才可得"的能力（如精确 CPU/原始网络字节） |

**隐私与一致性**：`serial` 默认 null；`profiles/` 不入库；案例只保留脱敏 `cases/<codename>/profile.json`（`source.mode=documented` 时逐字段给证据链接）。文档字段表与 [toolkit schema](../toolkit/schema/device-profile.schema.json) 冲突时**以 schema 为准**并修正本文与 [MTH-010](09-glossary.md)。

---

## 3. 评估流程（四步，必须按序）

| 步骤 | 命令（仓库根目录执行） | 产出 | 失败处理 |
|---|---|---|---|
| 1 · detect | `python -m toolkit.repurpose detect --out profiles/<codename>.json` | 身份/启动/存储/加密/硬件字段 | 无真机：用 toolkit 的 fixture 模式离线走通流程（`source.mode=fixture`）；无 ADB：先解决连接，**不得手填当实测** |
| 2 · probe | `python -m toolkit.repurpose probe --base profiles/<codename>.json --out profiles/<codename>.capabilities.json` | 12 项能力探测 + `verdicts` | 单项探测失败记 `status=unknown` 与证据；不要臆测为 pass |
| 3 · assess | `python -m toolkit.repurpose assess --profile profiles/<codename>.json --json` | 路线/门禁/置信度/风险/下一步 | `blocked`/`unknown` 按保守规则处理（见 §5）；重新探测补证据 |
| 4 · 人工复核 | 复核字段来源（measured/documented/assumed）+ 确认用户约束（见 §5.3） | 评估记录/门禁结论；写入案例或运行期记录 | 来源不明→定为假设并降 confidence；用户约束未确认→不得进 B/C/D |

**probe 能力清单（12 项）**：`proot`、`containers`、`systemd`、`native_linux`、`precise_cpu`、`raw_network_bytes`、`battery_sysfs`、`charge_limit_shell`、`dumpsys`、`appops`、`usage_stats`、`boot_autostart`；
每项为 `{status:"pass"|"fail"|"unknown", evidence}`，另附 `verdicts{summary, route_hint, items}` 与 `probe{probed_at, mode, commands}`。**无法探测的项必须如实记 `unknown`**，它直接决定评审置信度。probe 结果以 `capabilities`/`verdicts`/`probe` 三个可选键追加到 profile 副本（`--out` 指定输出路径）。

---

## 4. 路线决策表

| 路线 | 适用条件（必要条件） | 能力上限 | 代价/限制 | 默认结论 |
|---|---|---|---|---|
| **A** | BL 锁定/无法解锁；无 Root；不需要容器/特权 | Linux 用户态服务、局域网访问、宿主状态（经桥） | 假 root；无 systemd/容器；proot 性能损耗；部分系统级数据不可得 | ✅ **默认**（绝大多数设备） |
| **A+** | 同上，且已稳定运行、需要降温度/功耗/提高稳定性 | A 的全部 + 系统设置/包治理/看护 | 仍是 A 的能力边界；优化项必须可回滚 | ✅ A 的优化档（**不是独立 route ID**，见 §6） |
| **B** | G-B0 通过（可解锁且代价可接受）；有 root 方案；可选容器需 G-B2 通过 | 真 chroot、特权遥测、内核调参、可选容器 | 清数据/失保/完整性/OTA 风险；救砖预案必需 | ⚠️ 仅门禁+授权通过后；专用实验设备另按 [MTH-012](11-root-lab.md) 执行 |
| **C** | G-B0 + G-C 通过；有自编译/刷机条件 | 自定义内核/ROM（可开 NS/cgroup） | 极高风险、无维护、OTA 失效 | ❌ 非默认（研究性） |
| **D** | G-B0 + G-D 通过；存在可用社区移植 | 原生 Linux 完整内核能力 | 无移植则不可行；服务器关键驱动常不齐 | ❌ 仅"已有移植"且验证可跑时 |

---

## 5. 决策规则与门禁

### 5.1 路线选择顺序（工具已冻结，文档不得自创顺序）

```text
1) G-B0 fail/unknown（bootloader_unlocked=false 或 oem_unlock_policy=closed；或两者均未证实） → route=A（保守）
2) G-B0 pass 时：
   a) native_linux_port=true                          → D
   b) 容器/root 可得（依赖 B1/B2 判定）              → B
   c) custom_kernel=true                             → C
   d) 其余/证据不足                                  → B（并降低 confidence）
3) 任一关键字段 unknown：不臆测 → 落 assumptions/unknowns，按更保守路线倾向
```

### 5.2 门禁（gates，按顺序输出；`item={id,name,status,reason}`）

| ID | 名称 | 判定标准 | 失败处置 |
|---|---|---|---|
| **G-A** | 无根路线（Termux+proot）可用性 | `features.termux_available` 等支持；无阻断级 unknown；G-A 用于放行 A/A+ | fail→评估不可用/需换机；unknown→补探测 |
| **G-B0** | 解锁前置（B/C/D 硬门禁） | `bootloader_unlocked=false` **或** `oem_unlock_policy=closed` → **fail**（B/C/D 全部不可用）；两者均未证实 → **unknown**（同样停留 A） | fail/unknown→**B/C/D 终止**，保持 A/A+（案例实证：[PIT-010](../pitfalls/PIT-010-cn-oem-unlock-closed.md)） |
| **G-B1** | Root 管理器可用性（Magisk/KernelSU/APatch） | Magisk/KernelSU/APatch 至少一种可得 | fail→B 降级为不可实施 |
| **G-B2** | 容器运行时前提（user_ns + pid_ns + cgroup 委派） | `user_ns` 与 `pid_ns` 均 true **且** `cgroup_v2_delegation=true`；任一 false→fail，有 unknown→unknown | fail→不做容器（B 仍可为 chroot）；见 [PIT-006](../pitfalls/PIT-006-no-user-ns-containers.md) |
| **G-C** | 自定义内核/第三方 ROM 可行性 | `features.custom_kernel=true` **且 G-B0=pass** | fail→C 不进入 |
| **G-D** | 原生 Linux 移植是否存在 | `features.native_linux_port=true` **且 G-B0=pass** | fail→D 不进入（不得假设"别人机型能跑"） |
| **G-RISK** | Play Integrity / Root 兼容性（软门禁） | `crypto.play_integrity_required=true` → **unknown**（提示完整性风险）；false→pass | 不参与路线选择，但必须写入 `risks` 并要求用户确认 |

**门禁状态语义**：`pass`=证据充分且满足；`fail`=证据充分且不满足；`unknown`=证据不足——**`unknown` 一律不得当作通过**。

### 5.3 用户/现场约束（人工确认，落 `assumptions`/`blocked`/`constraints.notes`）

| 约束 | 判定问题 | 记录位置 |
|---|---|---|
| `data_wipe_acceptable` / `warranty_loss_acceptable` | 能否接受解锁清数据/失保？ | G-B0 结论 + `blocked`/notes |
| `play_integrity_required` | 是否依赖支付/银行/完整性 App？ | `crypto.play_integrity_required` + `risks` |
| `containers_needed` | 是否必须 Docker/Podman 生态？ | `features` 判定 + G-B2 |
| `privileged_metrics_needed` | 是否必须精确 CPU/原始网络字节？ | `constraints.root_required_capabilities[]` + probe 能力 |
| `external_services_allowed` | 是否允许接外部服务（隧道/异地备份/监控）？ | `assumptions`/`notes`（默认不允许） |
| `public_exposure` | 是否需要公网访问？ | 网络方案与 `risks`（默认局域网） |

### 5.3.1 网络假设（不得依赖固定地址/路由器权限）

> 移动设备会连不同 Wi-Fi；不是所有路由器都支持静态 DHCP 租约，访客/公司/酒店网络通常不可管理。**固定 IP/租约只能作为优化项，不能作为路线门禁前提。**

| 现场条件 | 是否阻塞 A 路线 | 应采用 |
|---|---|---|
| 家庭路由器可做静态租约 | 否（优化） | 可选固定租约；仍必须在服务端动态读取当前地址并做发现兜底 |
| 路由器不可管理/无租约功能 | 否 | 动态读取当前 IP；页面显示/扫码/发现机制；脚本禁止硬编码 |
| 多 SSID 漫游/换网（家庭↔公司↔访客） | 否 | 每次联网后重新发现；地址变化视为正常状态；必要时用已批准的受控隧道 |
| 访客网络隔离（AP isolation） | 是（局域网不可达） | 改走受控隧道或用户批准的其他入口；不得假设同网段可互访 |
| Captive portal（酒店/机场） | 是（未认证前不可达） | 不作为无人值守长期方案；写限制并需人工认证 |
| MAC 随机化/设备识别变化 | 否 | 关闭随机 MAC 仅作优化；不得把租约依赖建立在 MAC 上 |

**记录**：`assumptions[]` 写"地址动态、依靠发现机制"；`risks[]` 写"换网/租约不可控"；若使用隧道/外部服务必须 `external_services_allowed=true` 并获用户授权（见 [MTH-007](06-security.md)）。
**工具衔接**：当前 `toolkit assess` 尚未建模网络策略（见 [backlog](../backlog.json) BL-019）；评估时以本表人工结论为准，不得把"无法静态租约"当 fail。

### 5.4 未知字段 → 保守取值

| 字段状态 | 保守假设 | 影响 |
|---|---|---|
| `bootloader_unlocked=null` 或 `oem_unlock_policy=unknown` | 按"锁定/不可解锁"处理 | 路线停留 A，G-B0 记 unknown |
| `user_ns`/`pid_ns`/`cgroup_v2_delegation` unknown | 按"无容器"处理 | B 只能 chroot；容器列入待验证 |
| `native_linux_port` unknown 或 null | 按"无移植"处理 | 不产生 D 路线 |
| `features.boot_completed_receiver` unknown | 按"自启不可保证"处理 | 必须做人工兜底并写限制 |
| `play_integrity_required` unknown | 按"未声明"处理（G-RISK=unknown，写入 assumptions） | 提示风险，要求用户确认 |
| `source.mode=documented` 的字段 | 逐字段给证据；无证据的降为 assumed | 整体 confidence 下调 |

---

## 6. assess 输出契约（`repurpose.assessment.v1`）

| 字段 | 含义 |
|---|---|
| `schema` / `generated_at` | `repurpose.assessment.v1`；生成时刻 UTC |
| `profile{schema, generated_at, source_mode, capabilities_present}` | 输入档案的 schema/生成时间/来源模式（adb/fixture/documented/manual）/已探测能力数量 |
| `route` | **严格枚举** `"A"`/`"B"`/`"C"`/`"D"`；**A+ 不是 route ID** |
| `route_hint` | 路线提示（当前实现与 route 同值，保留给未来启发式扩展；下游应以 `route` 为准） |
| `route_label` | 人类可读标签，可含"A+ 优化"字样（如 A · 无 Root（Termux + proot，含 A+ 优化）） |
| `confidence` | 0.1–0.95 启发式置信度；证据越多、unknown 越少越高 |
| `gates[]` | `{id,name,status,reason}`，按 G-A→G-B0→G-B1→G-B2→G-C→G-D→G-RISK 顺序 |
| `blocked[]` | 阻断项（门禁 fail/unknown 导致不可继续） |
| `alternatives[]` | 可选替代路线/降级方案 |
| `risks[]` | 风险提示（完整性、数据、功耗、OEM 行为等） |
| `next_steps[]` | 建议下一步（补探测/确认约束/进入阶段） |
| `assumptions[]` / `unknowns[]` | 已采用的默认假设 / 仍未知项；**必须能被后续真机验证替代** |

**必须**：`route` 与 `route_label` 语义分离；下游脚本只读 `route`；`A+` 只出现在文档与 label 中，避免工具/文档口径漂移。

---

## 7. 阶段计划（plan）与命令

```powershell
python -m toolkit.repurpose detect --out profiles/<codename>.json
python -m toolkit.repurpose probe --base profiles/<codename>.json --out profiles/<codename>.capabilities.json
python -m toolkit.repurpose assess --profile profiles/<codename>.json --json
python -m toolkit.repurpose plan --profile profiles/<codename>.json --route auto --format md
```

- `plan --route auto`：根据评估结论生成 P0–P6 计划（见 [MTH-003](02-roadmap.md)）；指定 `--route A|B|C|D` 时仅生成该路线计划。
- 输出为人类摘要或 JSON（阶段/门禁/交付物/估时）；JSON schema 与退出码以 [toolkit/README.md](../toolkit/README.md) 为准；所有子命令均支持 `--help`。
- **必须**先 assess 通过再 plan；`blocked` 非空时应生成"先解除阻断"的计划，而不是强行排期。

---

## 8. OEM 评估清单（厂商无关）

| 检查项 | 如何检查（只读/现场） | 记录字段 | 影响 |
|---|---|---|---|
| 安装弹窗/安装限制 | 侧载一次测试包观察是否被拦截 | `source.notes` / oem-profile | 影响桥/工具安装流程；只进 profile |
| 自启动开关 | 系统设置中"自启动/后台启动"是否存在、默认值 | `constraints.oem_autostart` | manual-required 时需人工步骤 |
| 后台清理策略 | 省电/后台限制选项与默认行为 | `constraints.background_execution` | restricted 时需白名单+验收 |
| 权限重置行为 | 重启后通知/使用情况访问/定位是否被重置 | `warnings` / oem-profile | 桥字段可能重启后失效 |
| 解锁策略 | 官方通道是否存在、门槛（账号年限/实名/名额/冷却期）、代价 | `boot.oem_unlock_policy` + `oem_unlock_evidence` | G-B0 直接判定；门槛见 [PIT-022](../pitfalls/PIT-022-oem-unlock-quota.md) |
| 防回滚/OTA | 是否有 ARB/e-fuse、触发版本、能否降级、全量包/救援包可得性 | `boot` 字段 + `source.notes` / oem-profile | 决定"能否安全升级/回滚"；见 [PIT-023](../pitfalls/PIT-023-oneplus-arb-hard-brick.md) |
| 锁屏/FBE 策略 | 是否可无锁屏、BOOT_COMPLETED 是否延迟 | `crypto.encryption_type` + 人工确认 | 无人值守自启可行性 |
| 充电策略 | 是否有充电上限/旁路充电、相关节点是否可读 | `hardware.battery.charge_control_nodes` | 长期插电风险 |
| 社区 root/移植与救砖 | 官方/社区项目是否成熟、官方镜像与 EDL/recovery 是否可得 | `root.state`/`features.native_linux_port` + `source.notes` | B/D 可行性与高风险路线前置 |

**要求**：OEM 结论必须标注来源（实测/官方文档/社区证据）；**不得**根据品牌硬编码核心行为（标准 API 优先，差异只进 profile）。

---

## 9. 产出物清单

- [ ] 运行期 `profiles/<codename>.json` + 能力探测结果（12 项 + verdicts）；含 `source`/`evidence_refs`/`warnings`/`unknowns`，不入库
- [ ] 评估 JSON（route/label/confidence/gates/blocked/alternatives/risks/next_steps/assumptions/unknowns）+ 阶段计划（P0–P6，含门禁与回滚）
- [ ] 人工复核记录（字段来源分级、用户约束确认、门禁结论）
- [ ] OEM 评估记录（脱敏后进入案例 `oem-profile.md` 或运行期笔记）
- [ ] 未验证项的验证计划（每条 unknown 有 owner/方法/时限，或明确标注"待设备验证"）

---

## 10. 失败处理

| 现象 | 处理 |
|---|---|
| 无 ADB / 无法连接 | 先解决授权/驱动；用 fixture 走通工具流程；**不得手填当实测** |
| `serial` 等隐私字段被采集 | 脱敏（默认 null/redacted）后再入库；运行期档案放在 `profiles/` |
| `oem_unlock_policy=unknown` | 记 G-B0 unknown；默认停留 A；补官方/用户确认证据后重评估 |
| `config_readable=false` / probe 单项失败 | 用运行时证据（mount/uname 等）替代；每项失败记 `unknown` + 证据，不要重试到"看起来通过"，结论降 confidence |
| assess 与人工判断不一致 | **以证据为准**；先复核字段来源，再修工具或文档（记录差异） |
| 路线结论被用户约束推翻（如不能清数据） | 更新 `assumptions`/`blocked`，降 confidence，改走 A/A+ |
| 非 ASCII 路径导致脚本/构建失败 | 迁移到 ASCII 路径后重跑；这是构建链的硬约束（[PIT-001](../pitfalls/PIT-001-ascii-path-aapt2.md)） |

---

## 11. 示例（脱敏）

```json
{
  "schema": "repurpose.assessment.v1",
  "generated_at": "<UTC>",
  "profile": {"schema": "repurpose.device-profile.v1", "source_mode": "documented"},
  "route": "A",
  "route_label": "A · 无 Root（Termux + proot，含 A+ 优化）",
  "confidence": 0.82,
  "gates": [
    {"id": "G-A", "name": "无根路线可用性", "status": "pass", "reason": "Termux/Boot 可用"},
    {"id": "G-B0", "name": "解锁前置", "status": "fail", "reason": "bootloader 锁定且官方解锁不可用"},
    {"id": "G-B1", "name": "Root 管理器", "status": "unknown", "reason": "未解锁，未探测"},
    {"id": "G-B2", "name": "容器前提", "status": "fail", "reason": "user_ns/pid_ns 缺失"},
    {"id": "G-RISK", "name": "完整性/Root 风险", "status": "fail", "reason": "用户依赖完整性应用"}
  ],
  "blocked": ["B/C/D 因 G-B0 失败不可用"],
  "alternatives": ["A+ 优化路线（无 Root）"],
  "risks": ["前置服务可能被 OEM 清理", "系统级指标不可得"],
  "next_steps": ["按 MTH-003 P1 准备宿主", "补 24h soak 验收"],
  "assumptions": ["用户不需要容器", "无锁屏凭据可接受"],
  "unknowns": ["其他 OEM 白名单行为待验证"]
}
```

> 案例参考：haydn 案例的脱敏档案与评估结论见 [cases/haydn-k40pro/profile.json](../cases/haydn-k40pro/profile.json)（`source.mode=documented`，**案例实证**，当前结论为 route=A）。

---

## 12. 相关入口

| 需要 | 去哪里 |
|---|---|
| 边界/原则/三轨 | [MTH-001](00-foundations.md) |
| 阶段计划与门禁 | [MTH-003](02-roadmap.md) |
| 服务器栈 / 遥测桥实现 | [MTH-004](03-server-stack.md) · [MTH-005](04-telemetry-bridge.md) |
| 安全边界 / 验收 soak | [MTH-007](06-security.md) · [MTH-008](07-validation.md) |
| Root 实验设备（专用/已授权） | [MTH-012](11-root-lab.md) · [GRD-015](../guardrails/GRD-015-root-lab-controlled.md) |
| 工具/字段定义 | [toolkit/README.md](../toolkit/README.md) · [device-profile schema](../toolkit/schema/device-profile.schema.json) |
| 红线（不 Root/快照/密钥） | [guardrails/README.md](../guardrails/README.md) |
| 真实踩坑（解锁/容器/FBE） | [PIT-010](../pitfalls/PIT-010-cn-oem-unlock-closed.md) · [PIT-006](../pitfalls/PIT-006-no-user-ns-containers.md) · [PIT-004](../pitfalls/PIT-004-fbe-lockscreen-boot.md) |
