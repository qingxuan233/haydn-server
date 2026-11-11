---
id: ACP-001
title: （模板示例）验收清单：改造完成判定
type: acceptance
status: draft
audience: human, agent
tags: template, acceptance, replace-me
updated: 2026-11-11
agent_hint: 复制本模板到案例/项目验收文档；每项必须有证据，未实测不得勾选
---

# （模板示例）验收清单

> 模板使用说明：`toolkit/templates/acceptance.md`。验收是"证据驱动"的：
> 每一项都要能指向命令输出/记录/相对路径，禁止"文档声称通过"。

## 1. 验收前提

| 项 | 要求 | 状态 |
|---|---|---|
| 备份与回滚 | 备份可恢复、回滚路径演练过 | `<pass/fail/pending>` |
| 基线 profile | `assess` 有结论、unknown 已标注 | `<pass/fail/pending>` |
| 变更范围 | 与批准范围一致，无冻结目录改动 | `<pass/fail/pending>` |

## 2. 功能与稳定性验收

| ID | 验收项 | 方法 | 通过标准 | 结果与证据 |
|---|---|---|---|---|
| A1 | 自启 | 重启 5 次 | 5/5 核心服务自动恢复 | `<结果 + 路径>` |
| A2 | 长跑 | 24h soak | 可用率 ≥ 目标、失败可归因 | `<结果 + 路径>` |
| A3 | 故障注入 | 断网/杀进程/超时 | 有降级/恢复，无数据损坏 | `<结果 + 路径>` |
| A4 | 恢复演练 | 从备份恢复 | 恢复成功且校验一致 | `<结果 + 路径>` |
| A5 | 观测真实性 | 对照可得/不可得字段 | 不可得字段为 null，不伪造 | `<结果 + 路径>` |
| A6 | 安全边界 | token/端口/权限检查 | 仅 loopback/局域网，凭据不落文档 | `<结果 + 路径>` |
| A7 | 升级/回滚 | 升级一次并回滚一次 | 可回滚到上一稳定版本 | `<结果 + 路径>` |
| A8 | 文档/索引 | `validate --strict` + `index` | 全绿且 manifest 无 warnings | `<结果 + 路径>` |

## 3. 未完成项处理

```text
未实测项：<列出>
原因：<缺设备/缺授权/时间不足>
后续：<backlog ID 或计划>
明确结论：不得把"未实测"写成"通过"。
```

## 4. 签署（人工/Agent）

| 角色 | 结论 | 日期 |
|---|---|---|
| 执行 Agent | `<pass/conditional/fail>` | `<YYYY-MM-DD>` |
| 用户/维护者 | `<pass/conditional/fail>` | `<YYYY-MM-DD>` |
