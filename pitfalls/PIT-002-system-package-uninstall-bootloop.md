---
id: PIT-002
title: 卸载系统包导致 bootloop
type: pitfall
status: current
audience: human, agent
tags: system-package, bootloop, rescueparty, debloat
depends: GRD-002
updated: 2026-11-11
agent_hint: 系统包只 disable 不 uninstall；出现无限开机动画先查系统必需包缺失，不要在线硬修
severity: S1
domain: device
oem: xiaomi
---

## 症状

- 重启后进入无限开机动画，设备反复重启；启动原因出现 RescueParty 类标记。
- 系统进程（system_server）每数秒崩溃一次，`adb shell pm` 报 `Can't find service: package`。
- crash buffer/logcat 出现 `Required services extension package is missing`、`check config_servicesExtensionPackage` 等关键字。
- 在线恢复手段全部失效，最终只能恢复出厂（清数据），整机数据与 Termux/proot 服务器栈一起丢失。

## 触发场景

- 用 `pm uninstall --user 0` 批量移除“看起来没用”的系统包，尤其是 Google 扩展包（ext.services / ext.shared）等；
- 使用第三方 debloat 清单或“一键优化”脚本，按包名而非引用关系判断可否移除；
- 一次性移除大批系统组件，且没有“每批重启验证”；
- 误以为系统包“卸载后还能 install-existing 救回来”。

## 根因

- 部分系统包被系统配置（如 `config_servicesExtensionPackage`）在 PackageManagerService 初始化阶段硬引用；包缺失会直接抛 FATAL，system_server 崩溃并循环，触发 RescueParty。
- 崩溃发生在 PackageManagerService 注册之前，`pm` 服务根本来不及注册，导致 `install-existing`/在线重装等恢复路径不可用。
- 厂商通常只对 `disable-user` 做白名单保护，`uninstall` 可以绕过这层保护，风险最高。
- 根因是**把“未使用”当成“可删除”**：看得见的功能可以禁用，看不见的启动链依赖不能赌。

## 规避与修复

1. 红线：禁止 uninstall 任何系统包；只允许 `pm disable-user`（包仍处于“已安装”状态，缺失检查不会触发）。
2. 维护保护名单：ext.services、ext.shared、providers、systemui、settings、网络栈、电话/短信、安全中心、电源管理、桌面等；名单固化到治理脚本，未知包默认不动。
3. 清理以第三方数据安装 App 为主；系统包按“3–5 个一批”推进，**每批重启验证**，禁止一次大批量。
4. 动手前先评估恢复能力：全量备份可用、恢复出厂后重建物料（APK/rootfs/服务器备份）齐备、RTO 已估算。
5. 用只读工具做清单比对与风险评级，不直接执行卸载；Unsafe 等级一律不动。
6. 若已误删：不要在 bootloop 中反复尝试在线恢复；进恢复模式清数据，再按重建手册恢复，并复盘补名单。

## 验证

- 每批包治理后重启一次：正常进系统、无 FATAL/RescueParty、`pm` 服务可用。
- 治理脚本 dry-run 输出“将被 disable 的包”，确认不含保护名单。
- 抽查 logcat 无 `Required services extension` 类崩溃关键字。
- 恢复演练一次：从备份重建服务与数据，确认名单已随脚本入库。

## 关联

- 护栏：[GRD-002 禁止卸载系统包](../guardrails/GRD-002-no-system-package-uninstall.md)
- 方法论：[MTH-002 评估与可行性决策](../methodology/01-assessment.md)（先探测能力再改系统）
- 同类：[PIT-003 禁止 kill-all](PIT-003-kill-all-proot.md)、[PIT-012 厂商安装器交互](PIT-012-oem-installer-ui-automation.md)

## 证据

- 案例实证：[08 事故复盘与重置重建报告 §1](../docs/20-server/08-事故复盘与重置重建报告.md)（crash buffer 原文、处置与红线）
- 案例实证：[04 风险与回滚 R-19](../docs/10-device/04-风险与回滚.md)（风险登记与恢复路径）
- 案例实证：[14 安卓深度操作调研 §4.4/§9.1](../docs/20-server/14-安卓深度操作调研与技能沉淀.md)（UAD 评级把 ext.services 标为 UNSAFE）
- 案例实证：[06 A+ 优化方案 §3.4](../docs/20-server/06-A+优化方案.md)（保护名单、事故与修复记录）
