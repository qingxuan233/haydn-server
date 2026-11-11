---
id: CASE-003
title: （模板示例）设备案例：<codename>
type: case-study
status: draft
audience: human, agent
tags: template, case-study, replace-me
updated: 2026-11-11
agent_hint: 复制本模板到 cases/<codename>/README.md，同时补齐 profile.json 与 oem-profile.md
---

# （模板示例）设备案例：`<codename>`

> 模板使用说明：`toolkit/templates/case-study.md`。案例是**已发生的事实记录**，
> 结论来自实测或明确标注来源；不得写成"计划中的效果"。
> 占位符 `<...>` 只在演示代码块中出现。

## 1. 概况

| 项 | 值 |
|---|---|
| 市场名称 | `<market name>` |
| 型号 / 代号 | `<model> / <codename>` |
| SoC / 内存 / 存储 | `<soc> / <ram> / <storage>` |
| Android / OEM | `<version> / <OEM ROM>` |
| 改造路线 | `<A/B/C/D；见 assessment.v1>` |
| 改造状态 | `<运行中 / 研究中 / 已归档>` |
| 权威状态源 | `<相对路径>` |

## 2. 设备与能力基线

```text
profile.json：cases/<codename>/profile.json（repurpose.device-profile.v1，脱敏）
关键门禁：G-B0=<pass/fail/unknown>，G-B1=...，G-B2=...，G-D=...
assess 结论：route=<A/B/C/D>，confidence=<0-0.95>
```

## 3. 实施时间线与事实

| 阶段 | 时间 | 事实 | 证据 |
|---|---|---|---|
| P0 | `<日期>` | `<做了什么>` | `<相对路径/命令>` |
| P1 | `<日期>` | `<探测结论>` | `<profile/assessment>` |
| P2 | `<日期>` | `<服务栈落地>` | `<日志/文档>` |

## 4. 验收结果（区分实测/未实测）

| 项 | 结果 | 证据 |
|---|---|---|
| 5 次重启自启 | `<x/5>` | `<记录路径>` |
| 24h soak | `<可用率>` | `<记录路径>` |
| 故障注入 | `<通过/失败>` | `<记录路径>` |
| 恢复演练 | `<通过/失败>` | `<记录路径>` |

> 未执行项必须写"未实测"，不得用"应该可以"代替。

## 5. 限制与教训

- 无 Root 硬边界：`<列出不可得字段>`
- OEM 限制：`<权限重置/自启动/省电>`
- 硬件限制：`<存储/热/电池>`
- 沉淀的 PIT/GRD/MTH：`<ID 列表>`

## 6. 关联

```text
方法论：<MTH-ID>
踩坑：<PIT-ID>
护栏：<GRD-ID>
成本案例：<CASE-ID>
OEM profile：cases/<codename>/oem-profile.md
```
