---
id: PIT-003
title: kill-all 杀死 proot 服务栈
type: pitfall
status: current
audience: human, agent
tags: kill-all, force-stop, termux, proot, service-outage
depends: GRD-003
updated: 2026-11-11
agent_hint: 任何清理脚本执行前先 grep kill-all/force-stop；误杀后优先跑恢复脚本而不是反复重启
severity: S2
domain: server
---

## 症状

- 执行一次“清理后台/释放内存”后，SSH 立即断开，服务器所有服务消失：Termux、proot、supervisord 及其子进程全部不在。
- `adb shell ps` 看不到 proot/服务进程，日志无 crash 记录（进程是被系统杀的，不是自己崩的）。
- 恢复需要重新拉起 Termux 会话/重启手机，耗时数分钟到十几分钟，期间无远程入口。
- 若清理脚本被固化，重启后又会被执行一次，形成“服务周期性全灭”的假象。

## 触发场景

- debloat/优化脚本末尾带 `am kill-all` 或对 Termux 执行 `am force-stop`；
- 手工“一键清理内存”、使用第三方清理工具/一键优化；
- 在服务器运行期间做批量包治理或 AppOps 操作，顺带杀掉宿主应用；
- 把 `am kill-all` 误当成“只杀后台应用”的安全命令。

## 根因

- `am kill-all` 杀的是所有可杀的后台进程，Termux 及其子进程（proot → supervisord → 全部服务）都在范围内；
- `force-stop` 会终止整个应用进程组，Termux/Termux:Boot 被杀后，非 Root 环境没有系统级自启兜底；
- 服务恢复依赖 Termux App 上下文，被系统杀后只能由人工、开机脚本或专门的恢复脚本重新拉起；
- 脚本作者把“清后台”等同于“优化”，却没意识到这台手机的后台就是服务器本体。

## 规避与修复

1. 禁止 `am kill-all`，禁止 force-stop Termux / Termux:Boot 及服务器相关包；把这两条写进任何清理脚本的禁用清单与 review 项。
2. 后台治理只针对“明确无关”的第三方 App：用 suspend / disable-user / AppOps，逐批执行并立即验证服务仍全量 RUNNING。
3. 保活三件套保持有效：电池优化白名单 + `termux-wake-lock` + OEM 自启动白名单；否则被系统回收的概率同样很高。
4. 准备恢复通道：优先用可脚本化的“重启 Termux 服务”脚本（基于 Termux 的可调试状态），其次依赖 Termux:Boot 开机脚本，最后才是重启手机。
5. 变更纪律：每批清理后检查 `supervisorctl status` 是否全量 RUNNING；失败先恢复，不要继续下一批。
6. 事后固化：把事故写进治理脚本注释与本文档，避免“下次脚本再来一遍”。

## 验证

- 用文本检索确认脚本中不存在 `am kill-all`、不存在对 Termux 的 force-stop。
- 执行一次包治理后：服务全量 RUNNING、SSH 可达、关键入口健康检查通过。
- 恢复演练一次（可人为停服务模拟）：恢复脚本能在可接受时间内把服务拉回 RUNNING。
- 重启手机后自启链路正常，服务不依赖人工会话。

## 关联

- 护栏：[GRD-003 禁止 kill-all](../guardrails/GRD-003-no-kill-all.md)
- 方法论：[MTH-004 服务器栈](../methodology/03-server-stack.md)（启动链与保活）
- 同类：[PIT-020 看门狗级联重启](PIT-020-watchdog-selfheal-cascade.md)

## 证据

- 案例实证：[06 A+ 优化方案 §3.4](../docs/20-server/06-A+优化方案.md)（首轮清理脚本 `am kill-all` 误杀服务、修复与固化）
- 案例实证：[03 操作手册 §3.7](../docs/20-server/03-操作手册.md)（永久禁止、恢复脚本入口）
- 案例实证：[14 安卓深度操作调研 §4.4](../docs/20-server/14-安卓深度操作调研与技能沉淀.md)（无 Root 下 suspend + appops + force-stop 的边界）
- 案例实证：[04 风险与回滚 R-17](../docs/10-device/04-风险与回滚.md)（已发生一次的风险条目与恢复方式）
