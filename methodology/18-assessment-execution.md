---
id: MTH-018
title: 评估执行、OEM 清单与失败处理
type: methodology
status: current
audience: human, agent
tags: assessment, execution, plan, oem, checklist, failure-handling, example
depends: MTH-002, MTH-003, MTH-008
updated: 2026-11-14
agent_hint: 已读完 MTH-002 的流程/决策表/门禁，准备跑 detect/probe/assess/plan、做 OEM 现场核对或处理失败时读本文；路线判定口径仍以 MTH-002 为准。
---

# MTH-018 · 评估执行、OEM 清单与失败处理

> **一句话**：本篇是 [MTH-002 评估与可行性决策](01-assessment.md) 的**执行侧清单**——命令顺序、OEM 现场检查项、产出物、失败处理与脱敏示例，照做即可，不重复决策口径。
> **权威边界**：输入/输出、评估流程、路线决策表、门禁规则与 `assess` 输出契约在 [MTH-002](01-assessment.md)；阶段计划与门禁定义在 [MTH-003](02-roadmap.md)；验收证据口径在 [MTH-008](07-validation.md)；字段 schema 以 [toolkit/schema/device-profile.schema.json](../toolkit/schema/device-profile.schema.json) 与 `toolkit assess` 为准。本文只保留执行清单与失败处理。

## 1. 阶段计划（plan）与命令

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

## 2. OEM 评估清单（厂商无关）

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

## 3. 产出物清单

- [ ] 运行期 `profiles/<codename>.json` + 能力探测结果（12 项 + verdicts）；含 `source`/`evidence_refs`/`warnings`/`unknowns`，不入库
- [ ] 评估 JSON（route/label/confidence/gates/blocked/alternatives/risks/next_steps/assumptions/unknowns）+ 阶段计划（P0–P6，含门禁与回滚）
- [ ] 人工复核记录（字段来源分级、用户约束确认、门禁结论）
- [ ] OEM 评估记录（脱敏后进入案例 `oem-profile.md` 或运行期笔记）
- [ ] 未验证项的验证计划（每条 unknown 有 owner/方法/时限，或明确标注"待设备验证"）

---

## 4. 失败处理

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

## 5. 示例（脱敏）

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

## 6. 相关入口

| 需要 | 去哪里 |
|---|---|
| 评估流程/决策表/门禁口径 | [MTH-002](01-assessment.md) |
| 边界/原则/三轨 | [MTH-001](00-foundations.md) |
| 阶段计划与门禁 | [MTH-003](02-roadmap.md) |
| 服务器栈 / 遥测桥实现 | [MTH-004](03-server-stack.md) · [MTH-005](04-telemetry-bridge.md) |
| 安全边界 / 验收 soak | [MTH-007](06-security.md) · [MTH-008](07-validation.md) |
| Root 实验设备（专用/已授权） | [MTH-012](11-root-lab.md) · [GRD-015](../guardrails/GRD-015-root-lab-controlled.md) |
| 工具/字段定义 | [toolkit/README.md](../toolkit/README.md) · [device-profile schema](../toolkit/schema/device-profile.schema.json) |
| 红线（不 Root/快照/密钥） | [guardrails/README.md](../guardrails/README.md) |
| 真实踩坑（解锁/容器/FBE） | [PIT-010](../pitfalls/PIT-010-cn-oem-unlock-closed.md) · [PIT-006](../pitfalls/PIT-006-no-user-ns-containers.md) · [PIT-004](../pitfalls/PIT-004-fbe-lockscreen-boot.md) |
