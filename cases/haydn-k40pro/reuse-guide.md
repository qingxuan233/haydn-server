---
id: CASE-006
title: haydn K40 Pro 案例附录：换机复用指南（2026-11-14 快照）
type: case-study
status: current
audience: human, agent
tags: case, haydn-k40pro, migration, reuse, appendix
depends: CASE-001
updated: 2026-11-14
agent_hint: CASE-001 的结构性附录，只承载"保留/重做/换机步骤"三张清单；案例事实、结论与未完成项一律以 CASE-001 正文为准。
---

# CASE-006 · 换机复用指南（附录）

> 本文件由 [CASE-001](README.md) §8 于 2026-11-14 **原样下沉**（用户授权结构拆分；事实、结论与未完成项未改写）；案例的偏差、未验证项与冻结规则以 CASE-001 正文为准。

## 1. 保留（设备无关，直接复用）

- **三轨架构与边界**：Server 唯一聚合/存储/展示、Bridge 只做宿主采集、DSH 只读控制面、故障隔离与回退。
- **Bridge 核心设计**：包名 `com.qingxuan.bridge`；BootReceiver + `specialUse` FGS；环回 HTTPS + GET-only + token（后续升 mTLS）；null 语义与 capabilities。
- **服务器栈**：Termux + proot + supervisord（不用 systemd）；启动链 + 看门狗；`server-ops` Tier1/2/3；每日加密备份 + 审计。
- **数据契约**：`bridge_source` / 新鲜度 / 字段来源标记 / 缺失即 null / 不可得字段由 capabilities 解释。
- **验收框架**：5 次重启 + 24h soak + 故障注入 + 恢复演练；未过项必须显式记录。

## 2. 必须重做 / 重探测（换机时）

| 项 | 为什么 | 怎么做 |
|---|---|---|
| OEM profile | 自启动/省电/后台/安装弹窗各厂商不同，无标准 API | 按 [oem-profile.md](oem-profile.md) 的模板结构逐项填写；以 5 次重启为准 |
| `profile.json` 全部字段 | 硬件/启动链/内核能力是设备事实 | 用 `toolkit probe`/`detect` 重新探测，`source.mode` 改为 `adb`/`fixture`，更新 `unknowns` |
| 内核能力评估 | `USER_NS`/`PID_NS`/cgroup/overlay 决定容器与原生 Linux 是否可能 | `toolkit assess` 复评；不要沿用"本机不可用"的结论 |
| 设备专属脚本 | MIUI 安装弹窗、debloat/保护名单只对当前设备成立 | 只作案例证据，不迁移为通用脚本；换机按标准 ADB 基线重写 |
| 构建环境 | JDK/SDK 位置与路径 ASCII 要求 | 重新探测 JDK/SDK；仓库路径保持 ASCII；跑一次构建验收 |
| 凭据与入口 | 换设备必须重新生成 token/证书/密钥，公网入口外置后轮换 | 新配对流程；不要把旧凭据/入口复制到新文档 |
| 存储与分区策略 | A/B、动态分区、无 SD 卡影响刷机/扩容/备份 | 写进新案例关键事实与 profile |
| 若新机可解锁/Root | 结论不能沿用"无 Root" | 按 [MTH-002](../../methodology/01-assessment.md) 重评路线；容器仍需实测命名空间 |

## 3. 换机步骤（本案例视角，与 MTH 对齐）

1. 读 [MTH-002 评估](../../methodology/01-assessment.md) 与案例正文 §2 → 用 `toolkit` 探测新机，填新 `profile.json`；
2. 用 `toolkit assess` 得到路线/门禁/风险，先拒绝"做不了"的路线（锁定/OEM 策略/内核缺项）；
3. 按 [OEM profile 模板](oem-profile.md) 完成标准 Android 基线 + 厂商人工白名单，跑 5 次重启；
4. 按 [MTH-004 服务器栈](../../methodology/03-server-stack.md) 与 [17 重建手册](../../docs/20-server/17-研究平台环境构建手册.md) 重建/迁移服务器，接备份与审计；
5. 按 [MTH-005 遥测桥](../../methodology/04-telemetry-bridge.md) 构建/安装 Bridge，验证自启、401、回退；
6. 按 [MTH-008 验收](../../methodology/07-validation.md) 跑完整验收；未过项写进新案例"未验证清单"，不得美化。

## 4. 关联

- 正文：[CASE-001](README.md)（关键事实/偏差教训/冻结声明）· [OEM profile](oem-profile.md) · [profile.json](profile.json)
- 规范与索引：[cases/README.md](../README.md) · [methodology/README.md](../../methodology/README.md)
