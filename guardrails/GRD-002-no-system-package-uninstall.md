---
id: GRD-002
title: 禁止卸载系统包，只允许受控禁用
type: guardrail
status: current
audience: human, agent
tags: system-package, debloat, disable-user, protection-list, bootloop
depends: MTH-004, MTH-008
updated: 2026-11-11
agent_hint: 任何 debloat/清理需求只允许 disable-user 或 suspend；系统包 uninstall 一律拒绝，并要求保护名单与变更前后包状态证据。
severity: blocker
scope: device
---

# GRD-002 · 禁止卸载系统包，只允许受控禁用

> "卸载了没用"是错觉：系统包可能被框架以包名硬引用，缺失会在 system_server 启动阶段直接崩溃，且此时在线修复通道往往已不可用。

## 红线（MUST NOT）

1. **R1** **MUST NOT** 对 system/vendor/product/odm 分区内的包执行 `pm uninstall`（含 `--user 0` 形式），包括"看起来无用"的扩展包、框架包与厂商服务。
2. **R2** **MUST NOT** 使用去预装工具（Canta、UAD 类、AppManager 等）的"实际卸载"模式处理系统包；只允许只读清单比对。
3. **R3** **MUST NOT** 卸载或禁用保护名单中的包：系统扩展/框架、SystemUI、Settings、Providers、网络栈、电话/短信、安全中心、电源与自启相关组件；保护名单须随设备档案维护。
4. **R4** **MUST NOT** 在未采集变更前后包状态（enabled/disabled/uninstalled）与未重启验证的情况下，继续下一批清理。
5. **R5** **MUST NOT** 把"卸载失败/被系统保护拒绝"当成成功，或换工具反复绕过 OEM 的 `canBeDisabled` 限制。

## 为什么（风险与案例）

- 案例事故：误用 `pm uninstall --user 0` 移除系统扩展包后，system_server 因 `Required services extension package is missing` 崩溃并触发 RescueParty；`pm` 服务尚未注册，无法在线 `install-existing` 恢复，只能清数据重建（见 PIT-002、[08 事故复盘](../docs/20-server/08-事故复盘与重置重建报告.md)）。
- 系统包的依赖关系不透明：包名可能出现在 framework 配置或 OEM 私有引用中，卸载前无法穷举。
- `disable-user` 保留包仍"已安装"，不会触发缺失检查，且可用 `pm enable` 回滚；风险显著低于 uninstall。
- 案例实证：[14 安卓深度操作调研](../docs/20-server/14-安卓深度操作调研与技能沉淀.md)、[06 A+ 优化方案](../docs/20-server/06-A+优化方案.md)、[inventory 隐私说明](../inventory/README.md)。

## 允许的替代（MUST/SHOULD/MAY）

- **MUST** 对允许处理的应用只使用 `pm disable-user --user 0 <包名>` 或 `pm suspend`，并记录回滚命令（包名 + `pm enable`/`unsuspend`）。
- **MUST** 只处理明确无用的**数据安装第三方 App**；系统包默认不动，OEM 拒绝禁用时接受限制、不绕过。
- **SHOULD** 每批 3–5 个包，变更后重启并验证服务与自启；保护名单与批次记录随设备档案维护。
- **MAY** 用只读工具输出可禁用候选清单，人工复核后再决定；工具评级"unsafe"的包绝对不动。

## 检查方式（Agent 可执行）

```bash
adb shell pm list packages -e > packages-enabled-before.txt
adb shell pm list packages -d > packages-disabled-before.txt
adb shell pm list packages -u | grep <包名>
adb shell dumpsys package <包名> | grep -E 'enabled=|installed=|suspended='
```

- 变更脚本只读检查：`git grep -n 'pm uninstall' -- <本次改动文件>` 必须无系统包卸载路径；案例历史脚本已冻结，不作为新操作依据。
- 人工核对：保护名单是否存在且覆盖系统扩展/框架/SystemUI/Settings/Providers/网络栈/电话/安全与电源组件。
- 人工核对：每批变更是否记录了"包名、动作、回滚命令、重启验证结果"；缺少重启验证即判违规。
- 恢复演练：对一个已禁用包执行 `pm enable` 并确认状态恢复，证明回滚路径可用。

## 关联

- 踩坑：[PIT-002 系统包卸载导致 bootloop](../pitfalls/PIT-002-system-package-uninstall-bootloop.md)、[PIT-008 OEM 重启重置权限](../pitfalls/PIT-008-miui-permission-reset.md)
- 护栏：[GRD-004 变更前备份](GRD-004-backup-before-change.md)、[GRD-011 隐私与采集](GRD-011-privacy-inventory.md)
- 方法论：[MTH-004 服务器栈](../methodology/03-server-stack.md)、[MTH-008 验收](../methodology/07-validation.md)
- 案例：[haydn K40 Pro 案例](../cases/haydn-k40pro/README.md)、[保护名单与优化脚本](../scripts/adb/optimize-server-profile.ps1)
