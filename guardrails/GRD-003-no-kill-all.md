---
id: GRD-003
title: 禁止 kill-all 与误杀服务器进程
type: guardrail
status: current
audience: human, agent
tags: kill-all, force-stop, background-clean, server-process, availability
depends: MTH-004, MTH-006
updated: 2026-11-11
agent_hint: 禁止执行 kill-all/批量清后台；需要重启某个服务时只允许受控 CLI 单服务操作，并先确认目标不是服务器进程。
severity: blocker
scope: device
---

# GRD-003 · 禁止 kill-all 与误杀服务器进程

> 手机服务器把"后台存活"当作生命线。一次全局清理就可能同时杀掉 Termux、proot、supervisord 与 sshd，导致远程维护通道一起消失。

## 红线（MUST NOT）

1. **R1** **MUST NOT** 执行 `am kill-all`、`am kill`、`killall`、批量 `force-stop` 或任何"全局清后台/一键加速/内存清理"命令。
2. **R2** **MUST NOT** 对服务器相关进程使用 `force-stop`/`kill`：Termux 与 Termux:Boot、proot 与 rootfs、supervisord 及其子进程、sshd、控制面/遥测服务，以及承载自启链的组件。
3. **R3** **MUST NOT** 按宽泛模式（如匹配 "termux|proot|server"）批量杀进程；目标必须精确到单个进程或单个服务。
4. **R4** **MUST NOT** 用 `supervisorctl stopall` 或其他"全停"方式代替单服务操作；Tier3 级停机必须人工确认。
5. **R5** **MUST NOT** 以"清理内存/降负载"为理由改动保活配置（白名单、AppOps、唤醒锁）而不记录回滚；杀进程与降负载是两件事。

## 为什么（风险与案例）

- 案例事故：深度清理脚本末尾的 `am kill-all` 杀掉 Termux/proot/supervisord，SSH 与全部服务瞬断，之后必须重启并重新拉起（见 PIT-003、[06 A+ 优化方案](../docs/20-server/06-A+优化方案.md) 事故记录）。
- 手机没有带外管理：服务器进程被杀后，如果自启链（开机广播/看门狗）也失效，只能现场处理；无锁屏设备在 FBE 解锁前甚至无法自动恢复。
- 影响面不对称：清理目标通常只是某个无关 App，代价却可能是整台"服务器"离线；收益极低、风险极高。
- 案例实证：[04 风险与回滚](../docs/10-device/04-风险与回滚.md) R-17、[03 操作手册](../docs/20-server/03-操作手册.md) §3.7。

## 允许的替代（MUST/SHOULD/MAY）

- **MUST** 重启单个服务走受控 CLI（如 `server-ops restart <服务> --confirm`），由它做白名单校验、快照与审计；禁止直接 `kill`。
- **MUST** 只能对**单个非服务器目标 App** 使用 `am force-stop` 或 `pm suspend`，执行前核对它不在保护名单、不承载自启链。
- **SHOULD** 需要"降负载"时先停用非必需服务或降低轮询频率，保留 SSH/看门狗/遥测最小集。
- **MAY** 在维护窗口整体重启设备；重启后必须按自启验收清单验证全部服务恢复。

## 检查方式（Agent 可执行）

```bash
adb shell ps -A | grep -E 'supervisord|sshd|proot' 
adb shell dumpsys activity processes | grep -iE 'proot|supervisord|sshd'
server-ops status
server-ops health
```

- 变更脚本只读检查：`git grep -nE 'kill-all|killall|force-stop' -- <本次改动文件>` 逐条核对目标；出现批量/宽泛匹配即违规。
- 人工核对：本次操作的目标进程/服务是否在服务器与自启链保护清单内；命中保护清单即拒绝。
- 变更后核对：服务数是否全 RUNNING、SSH 是否仍可用、看门狗是否仍检测；任一缺失说明误杀且未恢复。
- 恢复演练：在演练窗口停单个服务并用受控 CLI 拉起，确认快照与审计记录存在。

## 关联

- 踩坑：[PIT-003 kill-all 杀掉 proot 服务器栈](../pitfalls/PIT-003-kill-all-proot.md)、[PIT-020 看门狗自愈级联](../pitfalls/PIT-020-watchdog-selfheal-cascade.md)
- 护栏：[GRD-004 变更前备份](GRD-004-backup-before-change.md)、[GRD-005 分级确认](GRD-005-tiered-ops-confirmation.md)、[GRD-012 Agent 行为](GRD-012-agent-operating-rules.md)
- 方法论：[MTH-004 服务器栈](../methodology/03-server-stack.md)、[MTH-006 控制面](../methodology/05-control-plane.md)
- 案例：[haydn K40 Pro 案例](../cases/haydn-k40pro/README.md)
