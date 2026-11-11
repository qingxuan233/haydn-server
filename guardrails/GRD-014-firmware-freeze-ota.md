---
id: GRD-014
title: 固件冻结与受控升级
type: guardrail
status: current
audience: human, agent
tags: firmware, ota, freeze, upgrade, regression, permissions
depends: MTH-002, MTH-008
updated: 2026-11-11
agent_hint: 禁止开启自动 OTA；固件升级必须走"评估→备份→维护窗口→人工批准→升级→全量回归验收→记录/回滚"流程。
severity: blocker
scope: device
---

# GRD-014 · 固件冻结与受控升级

> 对手机服务器而言，系统越"新"不代表越稳。一次自动 OTA 可能重排权限、改后台策略、重置自启，让运行数月的服务在无人值守时集体失效。

## 红线（MUST NOT）

1. **R1** **MUST NOT** 开启系统自动更新/自动 OTA；固件应冻结在已验证版本，并记录版本、指纹与安全补丁级别。
2. **R2** **MUST NOT** 在未完成评估前升级固件：兼容性、权限/自启回归、入口与证书影响、恢复路径、用户批准缺一不可。
3. **R3** **MUST NOT** 在未备份且未验证恢复路径的情况下升级；升级前按 [GRD-004](GRD-004-backup-before-change.md) 完成备份与恢复演练。
4. **R4** **MUST NOT** 在无人值守或 soak 观测窗口内升级；必须安排维护窗口，并明确升级失败的回滚动作。
5. **R5** **MUST NOT** 升级后只凭"看起来正常"收工；必须重跑完整验收：自启矩阵、服务全量、遥测桥、控制面、权限重授权与 soak 观察。
6. **R6** **MUST NOT** 因"安全补丁焦虑"私自升级或跳过记录；需要安全补丁时先评估影响并记录例外，而不是静默更新。
7. **R7** **MUST NOT** 在升级记录中抹掉失败尝试或退版记录；升级历史必须可追溯（版本、时间、结果、回滚点）。

## 为什么（风险与案例）

- 案例的决策基线是"关闭自动更新、固件冻结"（ADR-005），因为 OTA 可能破坏 Root/接口、重置权限与后台策略（见 [04 风险与回滚](../docs/10-device/04-风险与回滚.md) R-08/R-13、[00 项目规划](../docs/00-overview/00-项目规划.md)）。
- OEM 大版本升级常改变后台限制、通知与系统设置接口；案例中权限在重启后即被重置，升级后更需重授权与回归（见 PIT-008、PIT-009）。
- 自启链依赖开机广播与宿主策略，升级后可能变化；必须用重启矩阵验证而不是推测（见 PIT-004）。
- 案例实证：[06 A+ 优化方案](../docs/20-server/06-A+优化方案.md) 的"固件冻结"待办与 ADR-005、[90-archive B 路线手册](../docs/90-archive/05-B路线执行手册.md) 的升级策略教训。

## 允许的替代（MUST/SHOULD/MAY）

- **MUST** 在 OEM 设置中关闭自动更新（若存在系统级开关，记录其键值与当前值；不同 OEM 的名称以设备 profile 为准）。
- **MUST** 升级流程：读取当前版本/指纹 → 评估发布说明与已知回归 → 备份 + 恢复校验 → 维护窗口 + 人工批准 → 升级 → 全量验收 → 更新设备档案与案例记录。
- **MUST** 升级后重新授权/重放被 OEM 重置的权限与后台策略，并验证自启链（含锁屏/FBE 条件）。
- **SHOULD** 先用可回滚的测试设备或克隆环境验证升级包；主设备坚持"一次只升一个变量"。
- **SHOULD** 在无官方完整包/无可靠回滚路径时，明确记录"不建议升级"，保持冻结。
- **MAY** 在用户批准后使用官方恢复工具/完整固件包作为回滚路径，并提前验证可用。

## 检查方式（Agent 可执行）

```bash
adb shell getprop ro.build.version.release
adb shell getprop ro.build.version.security_patch
adb shell getprop ro.build.fingerprint
adb shell settings get global ota_disable_automatic_update
adb shell dumpsys package | grep -i update
```

- 人工核对：OEM 自动更新开关是否为关闭；系统更新提示是否被忽略；开关状态记入设备档案。
- 记录核对：设备档案中是否有当前固件版本/指纹/补丁级别，以及最近一次升级的"版本前后、时间、批准人、回滚点、验收结果"。
- 升级前核对：备份与恢复校验是否完成、回滚包/官方恢复工具是否可用、维护窗口是否确认。
- 升级后核对：重启矩阵、服务全量、遥测桥、控制面、权限重授权与 soak 是否全部重跑通过（[GRD-013](GRD-013-no-fake-acceptance.md)）。
- 偏差核对：升级失败是否已回滚并如实记录；未验证的兼容性结论是否标注"待验证"。

## 关联

- 踩坑：[PIT-008 OEM 重启重置权限](../pitfalls/PIT-008-miui-permission-reset.md)、[PIT-009 OEM 杀前台服务](../pitfalls/PIT-009-oem-fgs-killer.md)、[PIT-004 FBE 锁屏影响自启](../pitfalls/PIT-004-fbe-lockscreen-boot.md)、[PIT-010 官方解锁通道关闭](../pitfalls/PIT-010-cn-oem-unlock-closed.md)
- 护栏：[GRD-004 变更前备份](GRD-004-backup-before-change.md)、[GRD-008 供电与热安全](GRD-008-power-thermal-safety.md)、[GRD-013 不伪造验收](GRD-013-no-fake-acceptance.md)
- 方法论：[MTH-002 评估与决策](../methodology/01-assessment.md)、[MTH-008 验收与稳定性](../methodology/07-validation.md)
- 案例：[haydn K40 Pro 案例](../cases/haydn-k40pro/README.md)、[ADR-005 固件冻结](../docs/00-overview/28-全栈整体方案规范.md)
