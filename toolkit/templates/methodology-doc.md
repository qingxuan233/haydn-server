---
id: MTH-011
title: （模板示例）方法论条目标题
type: methodology
status: draft
audience: human, agent
tags: template, methodology, replace-me
depends:
updated: 2026-11-11
agent_hint: 复制本模板后替换 id/title/tags 与正文占位符，再运行 index 与 validate
---

# （模板示例）方法论条目标题

> 模板使用说明：本文件是 `toolkit/templates/methodology-doc.md` 模板，正文中的
> `<...>` 均为占位符（下列代码块演示替换方式），请勿保留在正式文档中。
> 正式文档必须：结论先行、区分 MUST/SHOULD/MAY、给验证方式、给证据来源。

## 1. 结论先行（MUST 可执行）

用 3–6 条短句给出结论，每条都能被后文证据或验证方式支撑。

```text
结论 1：<设备/场景> 下采用 <做法>，理由是 <证据>。
结论 2：<不可行/不推荐>，除非 <前提>；否则退回 <替代方案>。
结论 3：未实测项：<列出>，不得标记为完成。
```

## 2. 适用范围与前置条件

| 项 | 内容 |
|---|---|
| 适用设备 | `<Android 版本 / 架构 / 是否 Root>` |
| 前置条件 | `<ADB / 备份 / 解锁 / 工具版本>` |
| 不适用 | `<明确写出不适用的设备或场景>` |

## 3. 规范用语

- **必须（MUST）**：`<不可验收通过的动作>`
- **应当（SHOULD）**：`<默认动作；偏离需记录理由>`
- **可以（MAY）**：`<可选优化>`

## 4. 流程与门禁

```text
阶段/步骤 → 检查项 → 通过标准 → 失败回退
<步骤 1> → <检查> → <标准> → <回退>
```

## 5. 证据

| 证据 | 类型 | 位置/命令 |
|---|---|---|
| `<事实>` | 实测/官方文档/社区证据 | `<相对路径或只读命令>` |

> 证据不得包含序列号、IP、token、口令等敏感值；需要引用时使用脱敏 profile。

## 6. 验证方式

```bash
# 只读验证示例（替换占位符）
python -m toolkit.repurpose assess --profile profiles/<codename>-probed.json --json
bash toolkit/termux/healthcheck.sh --once
```

## 7. 关联

```text
依赖：<MTH-ID>
相关踩坑：<PIT-ID>
相关护栏：<GRD-ID>
相关案例：<CASE-ID>
工具：<toolkit 命令>
```
