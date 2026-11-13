---
id: ADR-0099
title: （模板示例）决策标题：一个决策一句话
type: adr
status: proposed
audience: human, agent
tags: template, adr, decision, replace-me
depends: ADR-0001
updated: 2026-11-13
agent_hint: 复制本模板到 adr/NNNN-kebab-slug.md，替换 id/title/depends/tags；必须写清备选方案与否决理由，决策完成后状态改 accepted 并登记 adr/README.md 索引。
---

# （模板示例）ADR 标题

> 模板使用说明：`toolkit/templates/adr.md`。占位符 `<...>` 只在演示代码块中出现；复制后替换示例 ID（ADR-0099 仅占位，正式编号查 [adr/README.md](../../adr/README.md)）。
> 规则：`adr/NNNN-slug.md` 四位连续编号、文件名与 `id` 一致；正文 H2 必含 状态/背景/决策/后果；重大决策加备选方案对比。[ADR-0001](../../adr/0001-adopt-agent-harness-v1-3.md) 与 [ADR-0002](../../adr/0002-protocol-versioning-and-regression.md) 可作写法参考。

## 状态

`proposed`（`<YYYY-MM-DD>`）。取代：无。`superseded_by: <待定>`（被取代时填新 ADR 号并保留本决策原文）。
修订：R1 `<YYYY-MM-DD>` 初版。

## 背景

```text
为什么现在要做这个决策：
- 问题与证据：<现象/命令输出/文档相对路径>
- 约束：<冻结区/规模/零依赖/授权范围>
- 触发：<事件、评审结论或协议 MAJOR 变更>
```

## 决策

```text
决定：<一句话可执行的选择>
范围：<改哪些目录/文件/命令，不改什么>
生效条件：<协议版本/日期/前置任务>
```

## 后果

| 维度 | 内容 |
|---|---|
| 正面 | `<收益：可追溯/可机检/降低风险>` |
| 代价 | `<新增维护面/迁移成本/检查时间>` |
| 风险 | `<最坏情况与兜底；触发回滚的条件>` |

## 备选方案对比（重大决策必填）

| 方案 | 优点 | 缺点 | 结论 |
|---|---|---|---|
| A `<保持现状>` | `<低成本>` | `<缺口持续>` | 否决 |
| B `<全量方案>` | `<覆盖最全>` | `<成本/不匹配>` | 否决 |
| C `<选定方案>` | `<…>` | `<一次性成本>` | 采纳 |

## 关联

```text
相关 ADR：<ADR-NNNN>
相关 MTH：<MTH-ID 相对路径>
相关 GRD/PIT：<GRD-ID / PIT-ID>
模板来源：toolkit/templates/adr.md
```
