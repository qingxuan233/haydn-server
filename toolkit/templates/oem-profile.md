---
id: CASE-004
title: （模板示例）OEM Profile：<OEM/ROM>
type: oem-profile
status: draft
audience: human, agent
tags: template, oem-profile, replace-me
updated: 2026-11-11
agent_hint: 复制本模板到 cases/<codename>/oem-profile.md；只写该 OEM 的差异步骤，核心能力保持通用
oem: example
---

# （模板示例）OEM Profile：`<OEM / ROM>`

> 模板使用说明：`toolkit/templates/oem-profile.md`。OEM 差异只允许放在 profile 层，
> 不得写进 Bridge/Server 核心逻辑。占位符 `<...>` 只在演示代码块中出现。

## 1. 基本信息

| 项 | 内容 |
|---|---|
| OEM / ROM | `<Xiaomi/HyperOS、Samsung/One UI ...>` |
| 适用版本 | `<Android 版本 / ROM 版本>` |
| 实测设备 | `<codename，脱敏>` |
| 证据等级 | `<实测 / 官方文档 / 社区证据 / 待验证>` |

## 2. 安装差异

```text
标准 adb install 是否可用：<是/否/需额外点按>
安装弹窗与未知来源限制：<描述>
卸载/重装保留数据：<是/否>
```

## 3. 自启动与保活

| 动作 | 操作路径（人工） | ADB 基线（只读/受控） | 验证 |
|---|---|---|---|
| 自启动 | `<设置路径>` | `<命令>` | `<5 次重启>` |
| 电池优化白名单 | `<设置路径>` | `<命令>` | `<重启后检查>` |
| 后台限制/省电 | `<设置路径>` | `<命令>` | `<长跑观察>` |
| 通知权限 | `<设置路径>` | `<命令>` | `<重启后检查>` |
| Usage 权限 | `<设置路径>` | `<命令>` | `<重启后检查>` |

> 命令必须是安全、可审计的；不写"绕过系统限制"的技巧，不硬改系统。

## 4. 已知重置行为（必须有实测）

| 项 | 重启后行为 | 证据 |
|---|---|---|
| POST_NOTIFICATIONS | `<保持/重置>` | `<路径>` |
| GET_USAGE_STATS | `<保持/重置>` | `<路径>` |
| 自启动白名单 | `<保持/重置>` | `<路径>` |

## 5. 验收步骤

```text
1) 安装并授权；
2) 人工配置 OEM 白名单；
3) 重启 5 次，记录每次恢复时间；
4) 24h soak 观察后台是否被杀；
5) 将差异写入本 profile，并更新案例 README。
```

## 6. 关联

```text
案例：cases/<codename>/README.md
方法论：<MTH-ID>
踩坑：<PIT-ID>
护栏：<GRD-ID>
```
