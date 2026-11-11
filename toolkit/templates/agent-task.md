---
id: TASK-001
title: （模板示例）Agent 任务单：<任务标题>
type: agent-task
status: draft
audience: agent
tags: template, agent-task, replace-me
updated: 2026-11-11
agent_hint: 复制本模板后替换 id/title/tags；写范围必须互斥，验收必须可执行
---

# （模板示例）Agent 任务单

> 模板使用说明：`toolkit/templates/agent-task.md`。任务单是给 subagent/新会话的
> 自包含上下文；禁止只给"帮忙优化一下"这类模糊目标。

## 1. 目标（可验收）

```text
目标：<一句话，能被命令或文件验证>
不做：<明确排除项，避免范围膨胀>
```

## 2. 输入与上下文

| 项 | 内容 |
|---|---|
| 相关文档 | `<MTH/PIT/GRD 相对路径>` |
| 当前状态 | `<profile/assessment/日志相对路径>` |
| 前置条件 | `<ADB/备份/工具版本/权限>` |

## 3. 写范围（互斥）

```text
允许写：<目录/文件前缀列表>
禁止写：<冻结目录/他人范围>
产物：<生成物路径，gitignored 需标注>
```

## 4. 步骤

1. 只读核对现状与影响面；
2. 在共享任务板 claim（多 Agent 时），记录 write_scopes；
3. 按最小步修改，每步可回滚；
4. 运行验收命令；
5. 更新索引/文档/backlog（如契约变化）。

## 5. 验收命令

```bash
python -m toolkit.repurpose validate --strict
python -m toolkit.repurpose index --json
python -m unittest discover -s toolkit/tests -t . -v
```

## 6. 报告格式

```text
改了什么：<文件清单 + 行数>
为什么：<与目标/规范的对应关系>
验证：<实际命令与结果摘要；不得写"应该通过">
风险/回滚：<具体路径>
未完成：<列出并说明原因>
```

## 7. 关联

```text
负责人：<agent 名称>
任务板 ID：<task-id>
依赖：<其他任务/文档>
```
