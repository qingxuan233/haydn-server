---
id: GRD-015
title: Root 实验设备的受控操作边界
type: guardrail
status: current
audience: human, agent
tags: root, bootloader, lab-device, authorization, arb, privilege, supply-chain
depends: GRD-001, GRD-004, GRD-005, GRD-014, MTH-012
updated: 2026-11-11
agent_hint: 只有"专用实验设备+用户授权记录+救援包+G-L 门禁"同时满足才允许解锁/Root；任一缺失即回到 GRD-001 默认拒绝。
severity: blocker
scope: device
---

# GRD-015 · Root 实验设备的受控操作边界

> 定位：本护栏是 [GRD-001](GRD-001-no-root-no-unlock-default.md) 的**受控例外实施细则**，不是普遍放行。GRD-001 对生产/主力/他人设备继续有效；本护栏只适用于用户明确授权的专用实验设备。

## 1. 红线（MUST NOT）

1. **R1 无授权不执行**：未取得"设备型号 + 授权范围 + 风险确认（清数据/失保/硬砖/数据丢失）+ 日期"的用户明确授权前，**MUST NOT** 解锁、Root、刷入或修改任何启动/系统分区。授权记录必须写入案例或运行期记录，不得口头默认。
2. **R2 只限专用实验设备**：**MUST NOT** 在含个人数据、支付账号、唯一副本或生产服务的设备上执行 Root；实验机不得承载生产服务，直到 [MTH-012 §10](../methodology/11-root-lab.md) 割接验收通过。
3. **R3 只走官方解锁通道**：**MUST NOT** 使用付费"秒解"、远程代刷、泄露账号、EDL/9008 漏洞绕过解锁或任何提权漏洞；只允许 OEM 现行政策明确允许的深度测试 / OEM 解锁开关 / `fastboot flashing unlock`。EDL/9008 仅可用于救援，且不得用于绕过 AVB/解锁。
4. **R4 不破坏启动完整性**：**MUST NOT** 关闭 AVB/verity、全局 `setenforce 0`、写入 `system`/`vendor` 等动态分区、卸载系统包；仍受 [GRD-002](GRD-002-no-system-package-uninstall.md)、[GRD-003](GRD-003-no-kill-all.md) 约束。
5. **R5 救援未就绪不解锁**：**MUST NOT** 在缺匹配原厂镜像/全量包、哈希清单、第二条数据线/第二台电脑、恢复演练计划时解锁；"有官方包"不等于"能恢复"（[GRD-004](GRD-004-backup-before-change.md)）。
6. **R6 固件冻结与不降级**：**MUST NOT** 在自动更新未关闭、版本未记录、ARB 状态未核验时解锁；**MUST NOT** 降级到已触发硬件防回滚的旧固件或旧第三方 ROM；`.500/.501/.503` 类 ColorOS 16 构建在确认前不得安装（[GRD-014](GRD-014-firmware-freeze-ota.md)）。
7. **R7 特权不下放**：**MUST NOT** 对公网开放 root shell/ADB/管理面；**MUST NOT** 使用"默认允许"的 su 授权；**MUST NOT** 安装来源不明/闭源的一键 Root 或救砖工具作为唯一手段；所有镜像/APK 必须官方来源并校验哈希。
8. **R8 一次一变更**：**MUST NOT** 在 Root 后同时改内核参数、网络规则、模块与 OTA；每次只改一项，带快照、回滚与验收（[GRD-005](GRD-005-tiered-ops-confirmation.md)）。

## 2. 为什么

- **不可逆代价**：解锁清数据、失效保修与完整性；硬件级防回滚（e-fuse）触发后无法软件回退，旧镜像/旧 ROM/EDL 救援可能直接硬砖（见 [PIT-023](../pitfalls/PIT-023-oneplus-arb-hard-brick.md)）。
- **政策收紧**：一加 2026 新政策对 ColorOS 16+ 机型增加账号 60 天、实名/人脸、连续登录 7 天、30 天冷却、一年 ≤4 台、名额 14 天有效等门槛（见 [PIT-022](../pitfalls/PIT-022-oem-unlock-quota.md)）；二手设备还面临"来源/已刷/已熔断"不透明风险。
- **供应链风险**：第三方一键工具可能被安全软件报毒、服务端下发刷机方案、闭源不可审计；EDL 免授权工具依赖泄露 loader，官方有熔断计划（见 [PIT-024](../pitfalls/PIT-024-flash-tool-supply-chain.md)）。
- **Root 后的稳定性**：模块冲突、OTA 与补丁错配、指纹/完整性/DRM 回退是常见事故（见 [PIT-025](../pitfalls/PIT-025-root-module-regression.md)）；生产机一次 bootloop 的代价已在 haydn 案例中发生过。
- **案例证据**：一加 Ace Pro 案为**预研/未实测**（[CASE-003](../cases/ace-pro-pgp110/README.md)）；不得把公开资料当本机实测。

## 3. 允许的替代

| 禁止动作 | 允许替代 |
|---|---|
| 直接解锁/刷机 | 先只读评估与 G-L0 准入（[MTH-012](../methodology/11-root-lab.md)）；不满足则换机或维持 A/A+ |
| 付费/漏洞解锁 | 官方深度测试/官方 fastboot 通道；等待账号条件满足或选择政策允许的机型 |
| 关闭 AVB/verity、改系统分区 | 使用 KernelSU LKM/APatch/Magisk 的 systemless/补丁 boot 方案，保留原厂镜像与回滚 |
| 卸载系统包 | `disable-user` + 保护名单（GRD-002） |
| 公网 root shell | 本地 console/受控 LAN + 跳板；维护后关闭 ADB |
| 闭源一键工具 | 官方 KernelSU/APatch/Magisk 发布物 + 哈希校验 + 可复现命令 |
| 降级救砖 | 只恢复**同版本或更新**的官方包；先查 ARB；不赌旧包 |

## 4. 检查方式

```bash
# 只读核对（无设备时跳过；有设备时先确认已授权）
adb shell getprop ro.boot.flash.locked
adb shell getprop ro.boot.verifiedbootstate
adb shell getprop ro.build.fingerprint
adb shell getprop ro.build.version.security_patch
adb shell getprop ro.boot.veritymode
adb shell getprop ro.boot.selinux
adb shell pm list packages | grep -E 'magisk|kernelsu|apatch'
```

人工逐项核对（缺一项即不得继续）：

1. 授权记录存在且覆盖本设备/本次动作；生产设备不在本次范围。
2. 救援包清单完整（匹配镜像/全量包/SHA-256/两条线/第二台电脑）。
3. 自动更新已关闭、版本与 ARB 状态已记录；无待装"禁止清单"更新。
4. 本次只改一项，且有快照与回滚命令。
5. 变更后运行恢复演练与验收，证据入库（[GRD-013](GRD-013-no-fake-acceptance.md)）。

## 5. 关联

- 护栏：[GRD-001](GRD-001-no-root-no-unlock-default.md) · [GRD-004](GRD-004-backup-before-change.md) · [GRD-005](GRD-005-tiered-ops-confirmation.md) · [GRD-014](GRD-014-firmware-freeze-ota.md)
- 方法论：[MTH-012 Root 实验设备](../methodology/11-root-lab.md) · [MTH-002 评估](../methodology/01-assessment.md) · [MTH-008 验收](../methodology/07-validation.md)
- 踩坑：[PIT-022](../pitfalls/PIT-022-oem-unlock-quota.md) · [PIT-023](../pitfalls/PIT-023-oneplus-arb-hard-brick.md) · [PIT-024](../pitfalls/PIT-024-flash-tool-supply-chain.md) · [PIT-025](../pitfalls/PIT-025-root-module-regression.md)
- 案例：[一加 Ace Pro 预研](../cases/ace-pro-pgp110/README.md)
