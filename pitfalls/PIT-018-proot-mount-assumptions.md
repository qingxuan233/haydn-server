---
id: PIT-018
title: proot 挂载假设错误导致服务全灭
type: pitfall
status: current
audience: human, agent
tags: proot, mounts, bind, sdcard, sigabrt, service-outage
depends: MTH-004
updated: 2026-11-11
agent_hint: 不绑定共享存储、启动做挂载断言、固定 Termux 启动上下文；服务消失先看 proot 断言日志
severity: S2
domain: server
---

## 症状

- 服务栈每隔几分钟整体消失，SSH 断开；日志出现 proot 路径断言（`compare_paths2 assertion length1 > 0` 类）与 SIGABRT。
- 绑定共享存储或使用软链后 proot 崩溃；重启后短暂正常，随后复发。
- 备份/服务写入路径失败或找不到目标目录；rootfs 内的路径假设与实际挂载不一致。
- 从 shell/run-as 上下文启动时表现不稳定，从 Termux App/开机脚本启动则正常。

## 触发场景

- 启动脚本绑定 `/sdcard`、`/storage` 等共享存储；
- rootfs 内使用指向宿主共享存储的软链；
- 服务脚本硬编码共享存储路径（备份、导出、媒体库）；
- 用 run-as/shell 上下文启动 proot 服务，而不是 Termux App/开机脚本上下文。

## 根因

- proot 对软链/路径做 sanitize，绑定含软链的共享存储会触发断言失败并 SIGABRT；这不是普通错误，重试无法恢复。
- Android 共享存储有单独的权限与命名视图；proot 内视角与宿主视角不同，路径假设容易失效。
- 从 run-as/shell 上下文启动时进程/SELinux 上下文不同，proot 稳定性下降。
- 启动脚本没有挂载/目录断言，错误延迟到运行时才暴露，表现为“服务周期性全灭”。

## 规避与修复

1. 最小绑定：只绑定必要目录（如 /dev、/proc、/sys 与必要的 fd），不绑定 `/sdcard`、`/storage` 等共享存储。
2. 路径契约：rootfs 内统一映射到宿主私有目录（如 `/hosthome`）；服务只读写私有目录，共享/备份需求走单独通道。
3. 启动断言：开机/启动脚本检查关键挂载与目录是否可用，缺失即失败退出并记录，不进入半可用状态。
4. 固定启动上下文：服务必须由 Termux App/开机脚本上下文启动，run-as/shell 只用于诊断。
5. 变更验证：每次改挂载/路径后至少重启 3 次并观察一个完整服务周期，确认无断言崩溃。
6. 恢复流程：服务消失时先查 proot 日志断言；按重启或开机脚本恢复；不要反复重试同一绑定配置。
7. 把“不绑定共享存储”写进启动脚本注释与部署文档，避免下次为了“方便备份”加回去。

## 验证

- 连续 3 次重启后服务全量 RUNNING，日志无 `compare_paths2`/SIGABRT。
- 启动断言在缺失挂载/目录时明确失败（负向验证），不进入半可用状态。
- 24h 内服务不出现周期性消失；备份/导出写入私有目录成功。
- 服务启动上下文符合约定（非 run-as/shell）。

## 关联

- 方法论：[MTH-004 服务器栈](../methodology/03-server-stack.md)（proot 启动链与挂载约定）
- 护栏：[GRD-004 变更前备份](../guardrails/GRD-004-backup-before-change.md)
- 同类：[PIT-007 proot 开销与热降频](PIT-007-proot-overhead-thermal.md)、[PIT-003 kill-all 服务全灭](PIT-003-kill-all-proot.md)

## 证据

- 案例实证：[08 事故复盘 §3.2/§6](../docs/20-server/08-事故复盘与重置重建报告.md)（`/sdcard` 绑定导致断言崩溃、修复与备份路径变化）
- 案例实证：[17 研究平台环境构建手册 §3 Phase 2](../docs/20-server/17-研究平台环境构建手册.md)（不绑定共享存储、软链与启动上下文要求）
- 案例实证：[04 风险与回滚 R-20](../docs/10-device/04-风险与回滚.md)（已发生多次的服务栈周期性全灭）
- 只读引用：[ubuntu.sh](../scripts/server/ubuntu.sh)（最小绑定与启动入口实现）
