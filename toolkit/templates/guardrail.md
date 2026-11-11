---
id: GRD-015
title: （模板示例）护栏标题：一条不可协商红线
type: guardrail
status: draft
audience: human, agent
tags: template, guardrail, replace-me
depends:
updated: 2026-11-11
agent_hint: 复制本模板后替换 id/title/tags；红线必须可执行、可检查，并给出允许的替代
severity: blocker
scope: device
---

# （模板示例）护栏标题

> 模板使用说明：`toolkit/templates/guardrail.md`，占位符 `<...>` 只在演示代码块中出现。
> 护栏是 MUST NOT；任何 Agent 不得为"方便"破例，只能用"允许的替代"。
> 额外 front matter 约定：`severity: blocker|warning`、`scope: device|server|agent|repo`（与
> guardrails/README.md 及 `toolkit/schema/frontmatter.schema.json` 一致）。

## 1. 红线（MUST NOT）

```text
禁止：<具体动作，尽量写成可被检查的命令/文件/配置>
永不允许：<即使看起来是临时修复也不允许>
```

## 2. 为什么

- 影响面：`<数据 / 启动链 / 安全 / 硬件 / 可回滚性>`
- 真实代价：`<最坏结果与历史案例>`
- 案例证据：`<相对路径，标注实测/官方文档/社区证据>`

## 3. 允许的替代

| 禁止动作 | 允许替代 |
|---|---|
| `<危险动作>` | `<只读/可回滚/最小暴露的替代>` |
| `<危险动作>` | `<需要用户明确授权的例外流程>` |

## 4. 检查方式

```bash
# 可执行检查（只读；替换占位符）
<命令>
```

也应当：

1. 在改造前自检清单中逐条确认；
2. 在复盘/交接文档中记录例外（若有）及用户授权；
3. 发现红线被破例时，先停止、再报告、不要自行"补证据"。

## 5. 关联

```text
相关踩坑：<PIT-ID>
相关方法论：<MTH-ID>
相关工具检查：<toolkit validate / healthcheck 等>
```
