---
id: ADR-0005
title: MTH-013 拆分：治理流程留 MTH-013，发布/兼容/数据/许可归 MTH-016
type: adr
status: accepted
audience: human, agent
tags: documentation, capacity, single-source-of-truth, mth-013, mth-016, adr
depends: ADR-0002, ADR-0004, MTH-013
updated: 2026-11-14
agent_hint: 改风险分级/需求基线/G0–G7/用户验收读 MTH-013；改发布就绪/兼容弃用/数据隐私/依赖许可读 MTH-016。
---

# ADR-0005 · MTH-013 拆分

## 状态

accepted（2026-11-14）。取代：无。关联 [ADR-0002](0002-protocol-versioning-and-regression.md)、[ADR-0004](0004-mth-011-split.md)、[MTH-013](../methodology/12-delivery-governance.md)、[MTH-016](../methodology/16-release-compatibility-data.md)。

## 背景

- `methodology/12-delivery-governance.md` 达 290/300 行，仅余 10 行；继续补充交付治理规则没有写入余量。
- 原文包含两类读者与触发频率不同的内容：**项目治理流程**（风险分级、角色/DRI、需求基线、G0–G7、用户验收、健康度）与 **发布/运行检查项**（部署与观测、runbook/Go-No-Go、兼容/弃用、数据隐私、依赖许可/制品来源）。
- 约束：拆分不得删规则、不得复制抄写；引用、索引、manifest、ADR 与 backlog 必须同步；不得弱化任何既有检查。

## 决策

1. **拆分边界**：[MTH-013](../methodology/12-delivery-governance.md) 保留风险分级 L/M/H、角色与 DRI、需求基线卡与变更控制、阶段门 G0–G7、用户验收、Continue/Pivot/Stop、落地清单与交付前自检；新增 [MTH-016](../methodology/16-release-compatibility-data.md)《发布就绪、兼容与数据治理》，承接原 §7–§10（部署/观测/runbook/Go-No-Go、兼容矩阵与弃用、数据地图与六问、依赖许可/SBOM/制品来源）。
2. **单一事实源**：原 §7–§10 正文只保留在 MTH-016；MTH-013 的 G5/G6 行、落地清单与自检清单只留一句检查要求 + 指向 MTH-016 对应节的链接，不复制细则。
3. **门禁归属不变**：G0–G7 的定义与通过标准仍在 MTH-013；MTH-016 只给"如何满足 G5/G6 与长期维护"的检查项，不新增或降低门禁。
4. **引用同步**：AGENTS、README、methodology/README、MTH-008/009/010/011/014/015、backlog 的 pending 任务 acceptance 与 outputs 一并改指正确篇章；历史 ADR 与已归档 CHANGELOG 不改写。
5. **版本与回归**：属方法论文档结构性分流，红线与权威顺序不变；按 ADR-0002 跑 `preflight`（index + validate --strict + unittest + check-links），不修改任何检查器与测试断言。

## 后果

- 正面：两篇回到健康档（MTH-013 187 行、MTH-016 150 行）；治理流程与发布检查各自演进，互不挤占。
- 负面/风险：发布相关规则分处两篇，读者需按 G5/G6 指针跳转；两篇边界漂移会重新重复，由 MTH-013 §9 自检与 `preflight` 兜底。
- 迁移：旧引用 `MTH-013 §7` → MTH-016 §2；`§8` → §3；`§9` → §4；`§10` → §5。MTH-013 自身 §11–§14 随正文前移重编号为 §7–§10（§1–§6 编号不变）。
- 回滚：将 MTH-016 合回 MTH-013 并恢复原 §7–§14 编号；不影响工具与校验器。

## 备选方案

| 方案 | 利 | 弊 | 结论 |
|---|---|---|---|
| A. 拆为 MTH-013 + MTH-016 | 职责单一、两篇均留余量 | 多一层跳转 | 采纳 |
| B. 压缩原文到 ≤200 行 | 不增文件 | 必然删规则或丢证据 | 否决 |
| C. 放宽 doc-policy 单文件上限 | 零改动 | 掩盖膨胀，违背容量治理 | 否决 |
