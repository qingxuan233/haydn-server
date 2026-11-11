# 21 · DSH 控制平面 P0 落地手册（仅机器本地）

| 项目 | 内容 |
|---|---|
| 文档 ID | `HB-DSH-021` |
| 版本 | v2.0（2026-11-11） |
| 状态 | 现行（P0 落地 / 换机复用手册；实施快照 2026-11-10） |
| 关联 | [20 控制平面方案](20-DSH控制平面方案.md) · [22 Tier2 受控写](22-DSH-Tier2受控写落地.md) · [23 蓝绿升级演练](23-DSH蓝绿升级演练.md) · [24 sessions 持久化](24-DSH-sessions持久化补全.md) · [当前状态](../00-overview/当前状态.md) |

> **文档定位**：20 号是**方案**（现状/目标/边界），本文是 **P0 落地操作手册**（改动、验证、回滚、换机复用）；Tier2 受控写见 [22](22-DSH-Tier2受控写落地.md)，蓝绿升级见 [23](23-DSH蓝绿升级演练.md)，sessions 备份见 [24](24-DSH-sessions持久化补全.md)，最新状态见 [当前状态](../00-overview/当前状态.md)。
> 文中数字为 **2026-11-10 实施快照**；当前仍为 **12/12 服务 RUNNING**（`dsh`/`dsh-login`/`dsh-guard` 均在）。

> 范围：**只做手机服务器自身能完成的优化**；外部告警（Uptime Kuma/PC）、异地备份、MFA/Tailscale 等"需要外部配合"的部分**暂不做**。
> 依据：[20 控制平面方案](20-DSH控制平面方案.md) 的方案 P0；本文记录实际改动、验证、回滚与复用方式。

---

## 1. 已落地变更

| # | 变更 | 结果 |
|---|---|---|
| 1 | **DSH profile 持久化** | `server-backup` 现包含：`/root/.dsh/storages`、`/root/.dsh/profiles/server`、`/root/.dsh/profiles/web`（排除 `node_modules`），并包含 `/root/server/bin`、`/root/server/ops` |
| 2 | **DSH 看门狗** | 新增 supervisor 服务 `dsh-guard`：每 30s 检查 3081/3082，连续 2 次失败自动重启 dsh/dsh-login |
| 3 | **nginx 限流** | `/app/` 5r/s burst10；`/app-login` 2r/s burst5；拒绝码 **429** |
| 4 | **只读执行层** | 新增 `/root/server/bin/server-ops`（Tier1）+ 审计 `logs/ops-audit.jsonl` + `/root/AGENTS.md` 策略 |
| 5 | **备份补全** | 修复 `bin` 未备份的问题；最近备份 6.6MB / 264 条目，含 `bin/server-ops`、`ops/AGENTS.md`、DSH profile/storages |

> 注意：`/root/.dsh/sessions` 在 P0 时**暂不备份**——proot `link2symlink` 产生 `.l2s.*` 伪链接，tar 会 `Cannot stat/Too many levels of symbolic links`。**该缺口已由 [24 sessions 持久化补全](24-DSH-sessions持久化补全.md) 修复**：`server-backup` 末尾调用 `server-backup-sessions`，每日只打包普通文件。

---

## 2. 验证记录（2026-11-10 本机快照）

| 检查 | 结果 |
|---|---|
| DSH 服务 | `dsh` / `dsh-login` / `dsh-guard` 均 RUNNING（总服务数 12/12） |
| 看门狗自愈 | `supervisorctl stop dsh` → 约 40s 后自动 RUNNING，guard 日志记录"连续失败→已重启" |
| nginx 限流 | 并发 20 次 `/app-login`：**6×302 + 14×429**；冷却后单请求 302 |
| 公网入口 | `/app-login` 302；token URL 200（token 在 dsh 重启后会变化） |
| `server-ops` | `status`/`health`/`logs dsh --lines 8`/`backups`/`audit` 正常；每次调用写审计 |
| 备份 | `server-backup 5` 成功 6.6MB；解密 tar 校验含 `bin/server-ops`、`ops/AGENTS.md`、`.dsh/profiles/web/package.json`、`.dsh/storages`；`node_modules=0` |
| LAN/公网 health | 8080/8443 及公网 HTTP/HTTPS（端口见私密记录）均 200；DSH 3081=401（正常）、dsh-login 3082=302 |

---

## 3. 复用步骤（换机/重置后）

1. 将仓库 `scripts/server/` 中以下文件放到设备 `/root/_tmp_dshcp/`：
   `dsh-guard`、`dsh-guard.conf`、`server-ops`、`AGENTS.md`、
   `patch-server-backup-dsh.py`、`patch-nginx-dsh-ratelimit.py`、`install-dsh-control-plane.sh`。
2. 在 proot Ubuntu 内执行：
   ```bash
   bash /root/_tmp_dshcp/install-dsh-control-plane.sh
   /root/server/bin/server-backup 5
   ```
3. 验证：
   ```bash
   server-ops status
   server-ops health
   # 并发 20 次 /app-login 应出现 429（用 Basic 认证）
   ```
4. 确认 `/root/AGENTS.md` 已生成（DSH 工作目录 `/root`，用于约束 agent 行为）。

**前置条件**：proot Ubuntu、supervisord、nginx、`server-backup` 已存在；`/root/server/bin` 可写。

---

## 4. 回滚

```bash
# 1) 配置回滚（改动前已备份 .bak-dshcp-<时间>）
cp -p /root/server/bin/server-backup.bak-dshcp-* /root/server/bin/server-backup
cp -p /root/server/bin/server-watch.bak-dshcp-* /root/server/bin/server-watch
cp -p /etc/nginx/sites-available/dsh-tls.bak-dshcp-* /etc/nginx/sites-available/dsh-tls
cp -p /etc/nginx/conf.d/dsh-upstreams.conf.bak-dshcp-* /etc/nginx/conf.d/dsh-upstreams.conf
nginx -t && nginx -s reload

# 2) 停用 DSH 看门狗
rm -f /root/server/etc/conf.d/dsh-guard.conf
supervisorctl -c /root/server/etc/supervisord.conf update
# 或 supervisorctl stop dsh-guard

# 3) 停用 server-ops（可选）
rm -f /root/server/bin/server-ops /usr/local/bin/server-ops
rm -rf /root/server/ops
# AGENTS.md 可保留/删除

# 4) 恢复后重新跑一次备份
/root/server/bin/server-backup 5
```

> 回滚后 dsh-guard 删除，服务数回到 11；nginx 限流移除后 `/app` 恢复无限流（不建议）。

---

## 5. 已知限制

1. **sessions 备份**：P0 时未入备份（proot `.l2s.*` 伪链接问题），现已由 [24](24-DSH-sessions持久化补全.md) 补全（`server-backup` 每日自动调用 `server-backup-sessions`）。
2. **profile/web 的 node_modules 未备份**：恢复后需 `cd /root/.dsh/profiles/web && pnpm install --frozen-lockfile`（按 [12 性能优化](12-DSH性能优化.md)/[13 插件安装](13-DSH插件安装-pnpm.md) 流程）。
3. **dsh-guard 是新增服务**：控制台服务计数从 11→12，属预期。
4. **DSH 重启会换 token**：浏览器需走 `/app-login` 重新登录（`dsh-login` 已处理）。
5. **server-ops 权限分级**：P0 时为只读（Tier1）；现已升级 **v2（Tier2 受控写：`--confirm` + 配置快照 + 审计）**，Tier3 仍不开放（见 [22](22-DSH-Tier2受控写落地.md)）。
6. **无外部依赖**：本轮未接外部告警、PC 拉取、异地备份、MFA/私网通道。

---

## 6. 后续与剩余项（截至 2026-11-11）

已完成：
- Tier2 写操作 + 配置快照 + 审计 → [22](22-DSH-Tier2受控写落地.md)；
- DSH 蓝绿升级演练 → [23](23-DSH蓝绿升级演练.md)；
- sessions 备份 → [24](24-DSH-sessions持久化补全.md)；
- Console 展示 DSH/ops 审计 → [34](../40-console/34-Console总览详情改版.md) 详情视图。

仍待（需要外部条件）：
- 外部告警/异地备份/MFA（按 [18 方案](../20-server/18-控制台持久化与容器优化方案.md) 与 [20 方案](20-DSH控制平面方案.md) 的 P1/P2）。

---

## 7. 文件与提交

复用文件（仓库）：
- `scripts/server/server-ops`
- `scripts/server/dsh-guard`
- `scripts/server/dsh-guard.conf`
- `scripts/server/AGENTS.md`
- `scripts/server/patch-server-backup-dsh.py`
- `scripts/server/patch-nginx-dsh-ratelimit.py`
- `scripts/server/install-dsh-control-plane.sh`

文档：[20 控制平面方案](20-DSH控制平面方案.md)（方案）→ 本文（P0 落地）→ [22 Tier2 受控写](22-DSH-Tier2受控写落地.md) → [23 蓝绿升级演练](23-DSH蓝绿升级演练.md) → [24 sessions 备份](24-DSH-sessions持久化补全.md)。
