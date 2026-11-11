---
id: GRD-008
title: 供电与热安全
type: guardrail
status: current
audience: human, agent
tags: power, thermal, battery, charging, unattended, availability
depends: MTH-004, MTH-008
updated: 2026-11-11
agent_hint: 7×24 运行前必须确认通风、充电保护、温度阈值与告警路径；出现发热异常/电池膨胀立即停用并报告。
severity: blocker
scope: device
---

# GRD-008 · 供电与热安全

> 手机做服务器是"把消费电子放进长期通电场景"。最贵的故障不是服务挂了，而是电池鼓包、起火或设备在无人值守时高温关机。

## 红线（MUST NOT）

1. **R1** **MUST NOT** 把设备放在密闭、无通风、被覆盖或阳光直射的位置长期运行；也不得在散热明显不足时提升持续负载。
2. **R2** **MUST NOT** 在未启用可用充电保护/充电上限的情况下，让设备长期满电插电；无此能力时必须在设备档案记录剩余风险与检查频率。
3. **R3** **MUST NOT** 忽略温度/电池异常：出现电池膨胀、后盖顶起、异常发热、电量跳变时，立即停止充电与运行，人工检查后再决定是否继续使用。
4. **R4** **MUST NOT** 在无告警路径的情况下承诺"无人值守稳定"；单点故障（断电、死机、断网）必须有已知处置方案或明确标注为未验证。
5. **R5** **MUST NOT** 把性能调优置于热安全之上：禁止默认使用极限性能策略、关闭热保护或绕过温控；调优必须逐步、可回滚、有温度对比。
6. **R6** **MUST NOT** 使用已损坏/鼓包的电池或改造电池安全电路；也不得在雷雨/供电不稳环境无人值守充电。

## 为什么（风险与案例）

- 锂电在长期满电 + 高温下老化最快，鼓包是安全事件而不只是续航问题；案例风险登记将其列为高风险（见 [04 风险与回滚](../docs/10-device/04-风险与回滚.md) R-04/R-05）。
- 手机散热依赖被动设计，持续服务器负载 + 充电叠加会触发降频或直接关机；案例通过限并发、降频与散热支撑长期运行。
- 无 Root 时电池充电控制与 sysfs 常不可读，必须依赖 OEM 充电保护设置 + 温度观测 + 物理检查；这是能力边界（见 PIT-011、PIT-007）。
- 案例实证：[06 A+ 优化方案 §4.4/§5](../docs/20-server/06-A+优化方案.md)、[03 操作手册](../docs/20-server/03-操作手册.md)、[09 性能优化方案](../docs/20-server/09-性能优化方案与可行性分析.md)。

## 允许的替代（MUST/SHOULD/MAY）

- **MUST** 在设备档案定义温度/电池阈值与检查频率；每次巡检记录温度、负载、充电状态、外观（是否顶起/变形）。
- **MUST** 启用 OEM 提供的充电保护/充电上限/智能充电（如支持）；不支持的设备要明确记录风险。
- **MUST** 保证通风与稳定供电；长期运行前做一次 24h 温度/功耗观测并留存记录。
- **SHOULD** 配置温度/充电/可用性告警（本地或既有受控入口）；外部告警服务需用户同意（[GRD-009](GRD-009-external-services-consent.md)）。
- **SHOULD** 把电池当耗材管理：定期评估容量衰减，必要时更换；更换前先做受控停机与备份。
- **MAY** 用智能插座/看门狗做远程断电重启，但必须限定操作范围、审计并验证不会造成反复掉电（见 PIT-020）。

## 检查方式（Agent 可执行）

```bash
adb shell dumpsys battery | grep -E 'level|status|health|temperature|present'
adb shell dumpsys thermalservice | grep -iE 'temperature|status|throttl'
adb shell dumpsys power | grep -iE 'mWakefulness|Display'
```

- 人工核对：设备放置位置是否通风、无覆盖、远离热源；每周检查外观与充电状态。
- 人工核对：设备档案中是否记录温度阈值、告警路径、单点故障处置与最近一次 24h 观测结果。
- 趋势核对：连续多次温度记录是否上升；高峰/满载时是否超过阈值；出现异常是否触发告警。
- 恢复核对：断电/高温停机后是否按备份与自启流程恢复，并重跑验收（[GRD-013](GRD-013-no-fake-acceptance.md)）。

## 关联

- 踩坑：[PIT-011 无 Root 电池 sysfs 不可读](../pitfalls/PIT-011-battery-sysfs-unreadable.md)、[PIT-007 proot 开销与热风险](../pitfalls/PIT-007-proot-overhead-thermal.md)
- 护栏：[GRD-004 变更前备份](GRD-004-backup-before-change.md)、[GRD-009 外部服务同意](GRD-009-external-services-consent.md)、[GRD-013 不伪造验收](GRD-013-no-fake-acceptance.md)
- 方法论：[MTH-004 服务器栈](../methodology/03-server-stack.md)、[MTH-008 验收与稳定性](../methodology/07-validation.md)
- 案例：[haydn K40 Pro 案例](../cases/haydn-k40pro/README.md)
