---
id: PIT-026
title: 诊断 tailscale 身份时 dump tailscaled.state 导致节点私钥与 network-lock 密钥进入日志
type: pitfall
status: current
audience: human, agent
tags: tailscale, secrets, redaction, state-file, chroot, diagnostics
updated: 2026-11-14
agent_hint: 查 tailscale 登录身份只用 `status --json` / `debug prefs` / `whois`；禁止 cat/strings/grep/hexdump 原始 `tailscaled.state`（含节点私钥与 network-lock 密钥）；已 dump 按泄露处理并轮换节点 key。
severity: S1
domain: ops
---
# PIT-026 · dump `tailscaled.state` 导致私钥进日志

## 1. 症状
- 为回答"服务器上 tailscaled 登录的是哪个账号"，对 chroot 内的 `/var/lib/tailscale/tailscaled.state` 执行 `strings … | grep -i operator|LoginName`，命令把整个文件的可打印字符串打到终端。
- 输出中除 `LoginName` 外还包含 `privkey:…`（节点私钥）与 `network-lock … PrivateKey/Key` 等明文键值；该输出留存于终端回显、会话记录与操作日志中。
- 影响面：节点私钥泄露等价于他人可冒充该节点接入 tailnet（受 ACL 限制），network-lock 私钥泄露可影响 tailnet 锁定一致性；按 [GRD-006](../guardrails/GRD-006-secret-hygiene.md) 属必须处置事件。

## 2. 触发场景
- 排查"当前登录账号/tailnet/设备名"类问题，且 tailscale CLI 不在 PATH（本次在 chroot `/data/server/rootfs` 内，需经 `/proc/<pid>/root/...` 调用）时，容易退化为"直接翻状态文件"。
- 任何"看一眼状态文件里有什么"的临时命令（`strings`、`grep -a`、`cat`、`hexdump -C`）都会命中。

## 3. 根因
- `tailscaled.state` 是 JSON 序列化的持久状态，本就保存 `PrivateKey`（`privkey:` 前缀）、`network-lock` 密钥、用户 profile 与控制面信息；文件权限 0600 只保证"不被其他用户读"，不保证"被读后自动脱敏"。
- `strings`/`grep` 不做字段级脱敏；而 `tailscale debug prefs` 对私钥做了打码——两者差异未被意识到。
- CLI 与状态文件混用：把"CLI 看不到"误判为"只能读文件"，实际 `status --json` 已包含账号、tailnet、设备名、地址、KeyExpiry 等全部所需字段。

## 4. 规避与修复
- **只用不含私钥的接口**：账号/身份用 `tailscale status` / `status --json`（`Self.DNSName`、`Self.UserID`、`User[].LoginName`、`CurrentTailnet`）、`tailscale whois <100.x>`；参数与运行模式用 `tailscale debug prefs`（私钥打码）；连通性用 `tailscale netcheck` / `ping`。
- **禁止**对 `tailscaled.state`、`tailscaled.log` 及任何密钥类文件执行 `cat`/`strings`/`grep`/`hexdump`/`dd`；必须确认存在性时只用 `stat`/`ls -l`（只看 mode/owner/size/mtime）。
- 设备侧 CLI 不在 PATH 时，用 `--socket=/proc/<pid>/root/run/tailscale/tailscaled.sock` 调 chroot 内二进制，而不是读状态文件。
- **已 dump 按泄露处理**：①在管理台对该节点 revoke key（或 `tailscale logout` 后重新登录，轮换机器 key）；②清理终端历史/日志副本；③在报告中写明泄露字段范围与处置时间，不复制原值。
- **输出打码**：任何粘贴到文档、聊天、提交信息的终端输出，必须把 `privkey:`、`PrivateKey`、`network-lock`、`tskey-*`、`authkey` 等字段整行替换为 `<REDACTED>`；只保留判断所需的最小字段。
- **处置闭环（2026-11-14，用户授权执行，已核验）**：本机 `tailscale logout` 移除旧 machine key → 设备以**新账号 `695598532@qq.com`** 重新登录（新 tailnet、新 `100.x` 地址），并回读确认 `BackendState=Running`、`RunSSH=false`、`--hostname`/`--accept-dns` 已还原 → 旧 tailnet（`qingxuan233@gmail.com`）中的残留节点 `haydn-pgp110` 已由**用户在管理台删除**。自此旧节点密钥在旧 tailnet 中不再有效，本机不再持有旧账号凭据；泄露面收敛。

## 5. 验证
- 仓库自查：`grep -rIl --exclude-dir=.git -E 'privkey:|tskey-(auth|scal|api)-' .` 必须无命中；gitignored 目录（`inventory/`、`tools/`）的近期产物同样抽查。
- 提交前：`git diff --cached | grep -E 'privkey:|tskey-(auth|scal)-'` 必须为空。
- 流程自查：检查自己的命令历史——凡出现对 `tailscaled.state` 的读取动作即判定违规；合规动作的报告里只会出现 `stat` 输出与 CLI 字段，不会出现文件内容片段。

## 6. 关联
- [GRD-006](../guardrails/GRD-006-secret-hygiene.md)（敏感值不进仓库/日志/文档/聊天，发现泄露先轮换再清历史）
- [GRD-013](../guardrails/GRD-013-no-fake-acceptance.md)（处置结果必须给证据，不得声称"已清理"）
- [MTH-014](../methodology/13-agent-sop.md) §14（单一事实源与提示词/纪律落点）

## 7. 证据
- 2026-11-14 本轮操作：在 chroot 内对 `tailscaled.state` 执行 `strings … | grep -i -E "operator|LoginName|UserProfile"`，实际输出包含 `privkey:` 与 network-lock 密钥字段（本条目不复制原值）。
- 同一会话改用 `tailscale status --json` + `tailscale debug prefs` + `tailscale whois` 即取得全部所需信息（账号邮箱、UserID、tailnet、DNSName、100.x、KeyExpiry、RunSSH），证明"读文件"不是必要路径。
- 设备侧确认：该文件位于 `/data/server/rootfs/var/lib/tailscale/tailscaled.state`（0600 root），Android 根下 `/var/lib/tailscale` 不存在；`debug prefs` 输出中私钥字段为打码状态。
- 切换后回读（2026-11-14）：新节点 `haydn-pgp110.taild6b629.ts.net`（账号 `695598532@qq.com`、UserID `5987551613657351`）、`BackendState=Running`、`PeerCount=3`、`KeyExpiry=2027-05-13T11:29:50Z`；业务进程（supervisord/frpc/stunnel/tailscaled）pid 全程未变；旧节点 `haydn-pgp110.tail379578.ts.net` 已由用户在旧 tailnet 管理台删除（用户确认，CLI 侧无法验证删除动作本身）。
