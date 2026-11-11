# 22 · DSH 控制平面 Tier2 受控写落地

| 项目 | 内容 |
|---|---|
| 文档 ID | `HB-DSH-022` |
| 版本 | v2.0（2026-11-11） |
| 状态 | 现行（Tier2 能力已落地；演练快照 2026-11-10） |
| 关联 | [20 控制平面方案](20-DSH控制平面方案.md) · [21 P0 落地手册](21-DSH控制平面落地手册.md) · [23 蓝绿升级演练](23-DSH蓝绿升级演练.md) · [24 sessions 持久化](24-DSH-sessions持久化补全.md) · [当前状态](../00-overview/当前状态.md) |

> **文档定位**：本文记录 `server-ops` 从 Tier1 只读升级到 **Tier2 受控写**的落地与演练；方案见 [20](20-DSH控制平面方案.md) §5，P0 前置见 [21](21-DSH控制平面落地手册.md)。当前 `server-ops` 为 **v2（Tier2）**，Tier3 仍不开放；最新状态见 [当前状态](../00-overview/当前状态.md)。

> 范围：仅机器本地。Tier2 = "允许 DSH 通过 server-ops 做有确认/有快照/有审计的服务写操作"；外部服务/异地告警仍不做。
> 前置：[20 控制平面方案](20-DSH控制平面方案.md)（方案）、[21 P0 落地手册](21-DSH控制平面落地手册.md)（P0 机器本地落地）。

---

## 1. Tier2 能力

`server-ops` 从 v1.1（只读）升级到 **v2**：

| 命令 | 说明 |
|---|---|
| `restart <svc> --confirm` | 重启白名单服务；自动配置快照；等待 RUNNING |
| `start <svc> --confirm` / `stop <svc> --confirm` | 启停 |
| `nginx test --confirm` / `nginx reload --confirm` | 先 `nginx -t`，再 reload；自动快照 |
| `backup --confirm` | 立即 `server-backup 5` + 解密/tar 自检 |
| `rotate --confirm` | `server-rotate` 日志轮转 |
| `backup-verify` | 只读校验最新加密备份（调用 `server-restore --verify`） |

**安全属性**：
- 缺少 `--confirm` → 直接拒绝（rc=2）；
- 服务名不在白名单 → 拒绝（rc=1）；
- 写操作前自动复制 `supervisord.conf`、`dsh-tls`、`dsh-upstreams.conf`、`server-watch`、`conf.d/` 到
  `/root/server/config-snapshots/<ts>-<cmd>/`；
- 每次调用写 `ops-audit.jsonl`（含 `snapshot=` 路径）；
- **Tier3（restore/升级/删数据）不开放**，只能人工 SSH + 双重确认。

允许的服务：`api fileui frpc gitea nginx runner sshd syncthing webdav dsh dsh-login dsh-guard`。

---

## 2. 本机演练记录（2026-11-10 20:39–20:40）

| 测试 | 结果 |
|---|---|
| 无 `--confirm` 重启 dsh-guard | rc=2，被拒绝 |
| 非法服务 `nope --confirm` | rc=1，被拒绝 |
| `restart dsh-guard --confirm` | 成功；快照 `config-snapshots/20261110-203943-dsh-guard-restart`；dsh-guard RUNNING |
| `nginx test --confirm` / `reload --confirm` | `nginx -t` 通过；快照 `...nginx-test` / `...nginx-reload`；reload 成功 |
| `backup --confirm` | 备份 6.6M → `server-20261110-2039.tar.gz.enc`；解密+tar 自检通过 |
| `backup-verify` | `server-restore --verify` 通过（264 个条目） |
| 审计 | 8 条记录可见，含 snapshot 路径 |
| 快照目录 | 3 个（restart/nginx test/nginx reload） |
| 服务/公网 | 12/12 RUNNING；公网 HTTP/HTTPS health 均 200（端口见私密记录） |

---

## 3. 复用

1. 更新设备上的 `/root/server/bin/server-ops`（仓库 `scripts/server/server-ops` 为 v2）。
2. 允许写操作前，确认 `/root/AGENTS.md` 已包含 Tier2 策略（仓库 `scripts/server/AGENTS.md`）。
3. 演练：
   ```bash
   server-ops restart dsh-guard --confirm
   server-ops nginx test --confirm
   server-ops nginx reload --confirm
   server-ops backup --confirm
   server-ops backup-verify
   server-ops audit 8
   ```

---

## 4. 回滚

- 单项变更回滚：从对应 `config-snapshots/<ts>-<cmd>/` 复制回原位置（supervisord.conf / nginx 站点 / conf.d），再 `nginx -t && nginx -s reload`、`supervisorctl update`。
- 禁用 Tier2：恢复旧版 `/root/server/bin/server-ops`（如有备份），或从仓库切回 v1.1 脚本。
- 备份恢复：按 [08 事故复盘与重置重建](../20-server/08-事故复盘与重置重建报告.md) 与 [17 研究平台环境构建手册](../20-server/17-研究平台环境构建手册.md) 的恢复阶梯；Tier3 不在网页/DSH 开放。

---

## 5. 后续（截至 2026-11-11）

1. ~~DSH 蓝绿升级演练~~ → ✅ 已完成，见 [23 蓝绿升级演练](23-DSH蓝绿升级演练.md)。
2. ~~Console 展示 DSH/ops 审计~~ → ✅ 已实现：Console 详情视图（`?view=details`）的 DSH/ops 审计区，见 [34 Console 总览/详情改版](../40-console/34-Console总览详情改版.md)。
3. 外部告警/异地备份/MFA：等本机经验完善后再接（见 [20 方案](20-DSH控制平面方案.md) §7 P2）。

---

## 6. 文件

- `scripts/server/server-ops`（v2）
- `scripts/server/AGENTS.md`（Tier2 策略）
- `scripts/server/install-dsh-control-plane.sh`
- [21 P0 落地手册](21-DSH控制平面落地手册.md)（P0）、本文（Tier2 受控写）、[23 蓝绿升级演练](23-DSH蓝绿升级演练.md)（升级流程）
