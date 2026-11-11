---
id: PIT-021
title: （模板示例）踩坑标题：症状一句话
type: pitfall
status: draft
audience: human, agent
tags: template, pitfall, replace-me
updated: 2026-11-11
agent_hint: 复制本模板后替换 id/title/tags；必须写明症状、根因、规避修复、验证与证据
severity: S2
domain: server
---

# （模板示例）踩坑标题

> 模板使用说明：`toolkit/templates/pitfall.md`，占位符 `<...>` 只在演示代码块中出现。
> 每条 PIT 必须来自真实案例或明确标注"通用风险"，不得编造。
> 额外 front matter 约定：`severity: S1|S2|S3|S4`、`domain: device|boot|server|bridge|security|ops|docs`
> （与 pitfalls/README.md 及 `toolkit/schema/frontmatter.schema.json` 一致），可选 `oem`。

## 1. 症状

```text
<用户可见现象：报错文本/服务中断/数值异常/时间点>
影响范围：<单服务 / 全部服务 / 设备 / 数据>
```

## 2. 触发场景

| 项 | 内容 |
|---|---|
| 设备/ROM | `<型号 / Android 版本 / OEM>` |
| 触发动作 | `<命令或操作>` |
| 频率 | `<一次 / 偶发 / 必现>` |

## 3. 根因

用可验证的机制解释，而不是"可能是 Bug"。区分：
- 已证实根因：`<证据/命令输出>`
- 推测部分：`<标注"待验证">`

## 4. 规避与修复

```text
规避（事前）：<配置/权限/白名单/顺序约束>
修复（事后）：<安全可回滚的操作步骤>
```

## 5. 验证

```bash
# 只读或安全可中断的验证命令（替换占位符）
<命令>
```

## 6. 关联

```text
相关护栏：<GRD-ID>
相关方法论：<MTH-ID>
相关工具：<toolkit 子命令或 termux 脚本>
同类踩坑：<PIT-ID>
```

## 7. 证据

| 证据 | 位置 | 备注 |
|---|---|---|
| `<日志/文档/截图>` | `<相对路径>` | `<脱敏；不写凭据/序列号>` |
