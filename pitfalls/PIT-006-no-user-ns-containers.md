---
id: PIT-006
title: 内核缺 USER_NS/PID_NS 容器不可用
type: pitfall
status: current
audience: human, agent
tags: container, namespace, kernel-config, docker, capability
depends: MTH-002
updated: 2026-11-11
agent_hint: 先 probe 再决策；USER_NS/PID_NS 为 not set 时直接否决容器路线，不要用 root 再试
severity: S3
domain: device
---

## 症状

- Docker/Podman/containerd 启动或运行容器失败；`unshare -U` 报 `Invalid argument`，`/proc/self/ns` 里只有 cgroup/mnt/net/uts，没有 user/pid。
- 即使拿到 root，容器仍无法创建命名空间；重装 runtime、换镜像、改配置都无效。
- 依赖容器生态（compose、数据库容器、systemd 容器）的计划全部不可执行。
- 常见误判：看到“某机型能跑 Docker”就认为本机也行，换机/同 SoC 兄弟机型上直接失败。

## 触发场景

- 接入新设备时未做内核能力探测，直接照抄“Android 跑 Docker”的教程；
- 把容器作为服务栈默认前提（例如计划用 compose 管理全部服务）；
- 认为 root/解锁/关 SELinux/关 verity 能绕过容器限制；
- 路线评估只看 CPU/内存，不看内核编译期配置。

## 根因

- 容器运行需要 user/pid 命名空间做隔离与 rootless 基础；厂商内核按 Android 安全模型裁剪，`CONFIG_USER_NS`、`CONFIG_PID_NS` 常为 `not set`（**编译期**配置）。
- cgroup v2 往往被 Android 自用且无委派，部分 netfilter 模块缺失，进一步限制容器网络与资源控制。
- 编译期配置无法在运行时热改；`root` 只改变权限，不改变内核已编译进去的能力。
- 唯一可能的出路是自定义内核/第三方 ROM（C 路线），风险高、非默认，不能当作常规方案。

## 规避与修复

1. 接入第一天先探测：读 `/proc/config.gz`（若存在）检查 USER_NS/PID_NS/NAMESPACES/CGROUPS/OVERLAY 等项，再跑 `unshare -U` 与命名空间列表，把结果写入设备档案与能力矩阵。
2. 探测未通过即固定结论：**不使用容器**，不做“再试一次”；在路线评估中直接否决容器分支。
3. 选择替代实现：无 Root → Termux + proot（用户态，无隔离）；有 Root → chroot + s6/runit/supervisord；明确接受“无镜像层、无隔离”的代价。
4. 若业务确实必须容器：换设备（准入时实测内核能力）或走自定义内核/ROM（高风险 C 路线，需单独评估与回滚），不默认承诺。
5. 拒绝“先 root 再试容器”的赌法：root 不改变已编译内核，失败会消耗解锁代价却仍不可用。
6. 把探测命令、输出与结论沉淀到案例，让下一个人不必重复试。

## 验证

- 探测输出明确：USER_NS/PID_NS 为 `not set`、`unshare` 失败 → 判定容器不可用。
- 路线评估/计划输出不包含容器前提；服务栈在 proot + supervisord 下全量 RUNNING。
- 换机验收把“内核能力实测”列为准入项，而不是按品牌/型号猜测。

## 关联

- 方法论：[MTH-002 评估与可行性决策](../methodology/01-assessment.md)（能力探测与路线判定）
- 护栏：[GRD-001 不 Root/不解锁默认](../guardrails/GRD-001-no-root-no-unlock-default.md)
- 同类：[PIT-007 proot 开销与热降频](PIT-007-proot-overhead-thermal.md)、[PIT-005 无 Root 指标缺失](PIT-005-no-root-proc-metrics.md)

## 证据

- 案例实证：[02 可行性分析 §5.2/§13.1](../docs/10-device/02-可行性分析.md)（容器所需特性对照、实测命名空间缺失）
- 案例实证：[00 项目规划 §1.2/ADR-002](../docs/00-overview/00-项目规划.md)（容器为明确非目标、否决决策）
- 案例实证：[04 风险与回滚 R-07](../docs/10-device/04-风险与回滚.md)（已实测确认必然不可用）
- 案例实证：[当前状态 §7](../docs/00-overview/当前状态.md)（容器不可用列入已知限制）
