---
id: GRD-009
title: 外部服务须用户明确同意
type: guardrail
status: current
audience: human, agent
tags: external-service, consent, monitoring, backup, vpn, dependency
depends: MTH-006, MTH-007
updated: 2026-11-11
agent_hint: 任何外部托管服务、云监控、异地备份、MFA、VPN/隧道、云推送接入前，先说明数据流与代价并取得用户明确同意，未同意不实施。
severity: warning
scope: server
---

# GRD-009 · 外部服务须用户明确同意

> 外部服务不是"加个功能"，而是新增信任关系、数据流向和故障点。用户没点过头的依赖，一律不应存在。

## 红线（MUST NOT）

1. **R1** **MUST NOT** 在未取得用户明确同意前接入外部服务：云监控/告警、异地备份、MFA/SSO、VPN/隧道/中继、云推送、APM、第三方账号或云盘。
2. **R2** **MUST NOT** 静默外发数据或自动注册试用账号；任何出站数据都要能说明"发什么、发给谁、为什么、保留多久"。
3. **R3** **MUST NOT** 把外部服务做成核心可用性的硬依赖；必须保留可用的本地路径与禁用开关，外部不可达时优雅降级。
4. **R4** **MUST NOT** 把外部凭据写入仓库/日志/文档；接入 token 按 [GRD-006](GRD-006-secret-hygiene.md) 管理。
5. **R5** **MUST NOT** 允许外部服务自动改写设备/服务器配置、远程执行命令或自动升级，除非用户逐项批准且边界可审计。
6. **R6** **MUST NOT** 以"以后可以关"为理由先接上再说；新增依赖必须同步记录决策、回滚与退出方案。

## 为什么（风险与案例）

- 系统当前明确保持"外部监控/异地备份/MFA/VPN 均未接入"的边界；这是用户授权范围的一部分，不是待办遗漏（见 [README](../README.md) 与 [30 接手指南](../docs/00-overview/30-新会话接手指南.md)）。
- 外部服务会扩大攻击面与隐私面：账号、数据与入口都可能成为泄露源；自动化重启类服务还可能放大故障（见 PIT-020 看门狗级联）。
- 依赖外部服务后，"它挂了我怎么办"成为新的运维问题；没有降级与退出方案的接入只会降低整体可靠性。
- 案例实证：[28 全栈规范 §10.5/§12](../docs/00-overview/28-全栈整体方案规范.md)、[20 控制面方案 §7 P2](../docs/30-dsh/20-DSH控制平面方案.md)。

## 允许的替代（MUST/SHOULD/MAY）

- **MUST** 先提方案与决策记录，字段至少含：服务名与用途、数据流与敏感级别、保留期、成本、失败模式、降级方式、退出方案、责任人。
- **MUST** 取得用户明确同意后才可实施；实施按 [GRD-004](GRD-004-backup-before-change.md) 备份、按 [GRD-005](GRD-005-tiered-ops-confirmation.md) 分级变更。
- **MUST** 提供禁用开关并演练"外部不可达"时的系统行为；核心链路不得因此不可用。
- **SHOULD** 优先自托管/私网/只读探测等最小暴露方案；确需云服务时最小权限、最小数据。
- **MAY** 在用户批准后接入只读可用性探测或加密异地备份；上线后定期复核数据与权限。

## 检查方式（Agent 可执行）

```bash
ss -tnp
adb shell pm list packages | grep -iE 'vpn|monitor|tunnel|remote'
git grep -nE 'https?://' -- <本次改动文件>
```

- 人工核对：出站连接清单与已知外部依赖清单一致；出现未登记的外部连接即判违规（先关闭再讨论）。
- 人工核对：新增配置/代码中是否出现第三方服务地址、SDK 或账号；逐项确认有无用户同意记录。
- 决策核对：决策记录是否包含数据流、保留期、降级方式、退出方案；缺任一项视为未批准。
- 演练核对：断开外部服务后核心功能是否仍可用；禁用开关是否真的能关闭出站。
- 历史核对：用户是否曾明确拒绝某类外部服务；拒绝项不得以"新方案"名义变相接入。

## 关联

- 踩坑：[PIT-020 看门狗自愈级联](../pitfalls/PIT-020-watchdog-selfheal-cascade.md)、[PIT-015 明文凭据](../pitfalls/PIT-015-plaintext-credentials.md)
- 护栏：[GRD-006 密钥卫生](GRD-006-secret-hygiene.md)、[GRD-007 网络最小暴露](GRD-007-network-least-exposure.md)、[GRD-011 隐私与脱敏](GRD-011-privacy-inventory.md)
- 方法论：[MTH-006 控制面](../methodology/05-control-plane.md)、[MTH-007 安全与密钥生命周期](../methodology/06-security.md)
- 案例：[haydn K40 Pro 案例](../cases/haydn-k40pro/README.md)
