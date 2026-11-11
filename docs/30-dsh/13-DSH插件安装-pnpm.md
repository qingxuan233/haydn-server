# 13 · DSH 插件安装环境（pnpm）修复与验证

| 项目 | 内容 |
|---|---|
| 文档 ID | `HB-DSH-013` |
| 版本 | v2.0（2026-11-11） |
| 状态 | 历史记录（2026-11-10 实现记录）；当前状态见 [当前状态](../00-overview/当前状态.md) |
| 关联 | [11 服务器配置与模型](11-DSH服务器配置与模型.md) · [12 性能优化](12-DSH性能优化.md) · [21 P0 落地手册](21-DSH控制平面落地手册.md) · [scripts/server/install-pnpm.sh](../../scripts/server/install-pnpm.sh) |

> **历史记录（2026-11-10）**：pnpm 与 codex 插件的安装结论仍有效；文中"11/11 RUNNING"、RSS、启动耗时等为**当时快照**。当前总服务数 **12/12**，最新状态见 [当前状态](../00-overview/当前状态.md)。

> 日期：2026-11-10 17:17–17:35
> 报错：`Command failed with ENOENT: pnpm add '@deepseek-ai/dsh-subagent-codex@0.2.2-rc.1' --save-exact`
> `spawn pnpm ENOENT`
> 结论：服务器只装了 Node/npm，没有 pnpm；DSH 插件管理器通过 `spawn('pnpm')` 安装插件，PATH 中找不到二进制即 ENOENT。**已安装 pnpm 并成功安装/加载 codex 插件**。

---

## 1. 根因

| 项 | 值 |
|---|---|
| DSH 运行方式 | Node 24.22.2（`/opt/node24`），DSH `0.2.2-rc.1` |
| supervisor 的 PATH | `/opt/node24/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin` |
| 缺失二进制 | `/opt/node24/bin/pnpm` 不存在（只有 npm） |
| DSH 插件管理器 | 通过 `pnpm add … --save-exact` 安装插件；spawn 时找不到 pnpm → ENOENT |

> 注意：直接 SSH 执行 `/opt/node24/bin/npm` 也会报 `env: 'node': No such file`，因为该 npm 是 `#!/usr/bin/env node`；安装 pnpm 时必须先让 PATH 包含 `/opt/node24/bin`。

## 2. 修复

```bash
export PATH=/opt/node24/bin:$PATH
npm install -g pnpm@10 --no-audit --no-fund
# 验证
command -v pnpm    # /opt/node24/bin/pnpm
pnpm -v            # 10.34.9
```

- pnpm 安装到 `/opt/node24/bin`，**正好在 DSH supervisor 的 PATH 中**；
- 重启 DSH 后，其进程 PATH 仍是同一路径，spawn `pnpm` 正常；
- 幂等脚本：[scripts/server/install-pnpm.sh](../../scripts/server/install-pnpm.sh)（Termux/proot 内执行）。

### 验证 DSH 能 spawn pnpm

```bash
export PATH=/opt/node24/bin:$PATH
dsh plugin --profile web --version
# 输出：10.34.9
```

### 实际安装用户报错的插件

```bash
export PATH=/opt/node24/bin:$PATH
cd /root/.dsh/profiles/web
dsh plugin --profile web add '@deepseek-ai/dsh-subagent-codex@0.2.2-rc.1' --save-exact
# Done in 46.6s using pnpm v10.34.9
```

结果：

- `/root/.dsh/profiles/web/package.json` 的 `dependencies` 增加 `@deepseek-ai/dsh-subagent-codex: 0.2.2-rc.1`；
- DSH 同时把 `@deepseek-ai/dsh-subagent-codex` 加入 `dsh.profile.bundles`；
- `dsh --profile web --dump-config` 出现 `subagent-codex` / `tool-subagent-codex`（provider: codex）。

## 3. 当时 profile 状态（性能与插件并存；历史快照 2026-11-10）

| 项 | 状态 |
|---|---|
| bundles | `dsh-base`、`dsh-web-app`、`dsh-experimental-agent-team-profile`、`dsh-experimental-session-titles-bundle`、**`dsh-subagent-codex`** |
| 移除项 | `inspector` / `forge` / `auto-review` / `plugin-market`（性能优化取舍；插件管理器可随时重新启用） |
| 启动耗时（重启→打印新 token） | **34 秒**（7 插件旧状态约 90 秒） |
| DSH RSS | **410MB**（无 codex 的精简状态 304MB；codex 插件增加约 100MB） |
| 客户端模块 | **222**（与精简前一致，codex 不额外增加客户端模块） |
| 登录 | LAN / 公网 `/app-login` 均 **200** |
| 服务（历史快照 2026-11-10） | **11/11 RUNNING**（当前 12/12） |

## 4. 使用

1. 回到 DSH 界面，**重试安装插件**即可（pnpm 已就绪；已安装的 codex 也可继续使用）；
2. 安装后按 DSH 提示重启插件/服务，或执行：
   ```bash
   supervisorctl -c /root/server/etc/supervisord.conf restart dsh
   ```
3. 如以后从普通 SSH shell 手动启动 DSH，请先 `export PATH=/opt/node24/bin:$PATH`，否则仍会 ENOENT。

## 5. 回滚

```bash
# 仅卸载 codex 插件（保留 pnpm）
export PATH=/opt/node24/bin:$PATH
cd /root/.dsh/profiles/web
dsh plugin --profile web remove '@deepseek-ai/dsh-subagent-codex'
# 如果 package.json 的 bundles 中还残留 codex，手动移除后重启 dsh
```

服务器备份：

- `/root/.dsh/profiles/web/package.json.bak-codex-20261110-172725`（安装 codex 前的精简版）
- 若需完全恢复旧状态，用备份覆盖 package.json 后 `supervisorctl restart dsh`。

## 6. 变更记录

| 时间 | 变更 | 结果 |
|---|---|---|
| 17:18 | 确认无 pnpm、npm 需 PATH 才能运行 | 定位为 PATH/缺二进制 |
| 17:19 | 安装 pnpm@10.34.9 到 `/opt/node24/bin` | `dsh plugin --version` 正常输出 |
| 17:20 | 安装 codex 插件 | 46.6s 完成，dependencies + bundles 更新 |
| 17:25 | 精简 bundles 保留 codex | dump exit 0，codex 条目出现 |
| 17:29 | 重启 DSH | 34s 就绪，RSS 410MB，登录 200 |
