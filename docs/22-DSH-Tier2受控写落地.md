# 22 · DSH 控制平面 Tier2 受控写落地

> 范围：仅机器本地。Tier2 = "允许 DSH 通过 server-ops 做有确认/有快照/有审计的服务写操作"；外部服务/异地告警仍不做。
> 前置：docs/20（方案）、docs/21（P0 机器本地落地）。

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
| 服务/公网 | 12/12 RUNNING；48104/44904 health 均 200 |

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
- 备份恢复：按 docs/08/17 的恢复阶梯；Tier3 不在网页/DSH 开放。

---

## 5. 尚未做（机器本地/外部待定）

1. **DSH 蓝绿升级演练**：新版本 3083 验证 → 切 nginx upstream → 回滚；当前仅文档方案，未实际切换。
2. Console 展示 DSH/ops 审计（需改 console，涉及另一个会话正在改的 ui，暂缓）。
3. 外部告警/异地备份/MFA（按你的要求等本机经验完善后再接）。

---

## 6. 文件

- `scripts/server/server-ops`（v2）
- `scripts/server/AGENTS.md`（Tier2 策略）
- `scripts/server/install-dsh-control-plane.sh`
- docs/21（P0）、docs/22（本文，Tier2）
