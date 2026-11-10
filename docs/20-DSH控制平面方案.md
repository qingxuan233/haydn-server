# 20 · DSH 作为服务器控制平面（管理 / 控制 / 执行大脑）方案

> **落地状态（2026-11-10，机器本地 P0 已完成）**：见 [docs/21-DSH控制平面落地手册](21-DSH控制平面落地手册.md)。
>
> 定位：DSH 不只是"网页上的聊天工具"，而是这台手机服务器**对外操作的中心**：
> 外部入口（HTTPS/frp）→ DSH（决策/执行大脑）→ 受控工具层（server-ops）→ 服务器服务。
> 控制台（Console）负责观测/告警/备份校验，与 DSH 分工。本文给方案，不改服务器。

---

## 1. 当前 DSH 状态与缺口（实测）

| 项 | 现状 |
|---|---|
| DSH 服务 | `dsh` RUNNING，`127.0.0.1:3081`；Node24，RSS **279MB**，CPU 4.7%（约 2.5h 平均） |
| 稳定登录 | `dsh-login`（127.0.0.1:3082）正常；`/app-login`（Basic Auth）→ 302 |
| 公网入口 | `https://47.97.70.99:44904/app/?token=…`，token **每次重启变化** |
| 访问保护 | nginx Basic Auth + DSH token；有 `/sdcard/DSH/dsh-app-public.off` 维护开关（当前无文件=开启） |
| profile | `/root/.dsh/profiles/server` 仅 **3.5KB**；`profiles/web` **286MB（主要是 node_modules）**；`sessions` 22K、`storages` 31K |
| 备份 | `server-backup` **不包含 `/root/.dsh`** → **DSH 配置/会话/插件未持久化** |
| 工具层 | 无 `server-ops` 受控 CLI；DSH 目前只有 shell |
| 升级/回滚 | 手工；无蓝绿/回滚流程 |
| 审计 | DSH 会话日志有；但"DSH 执行了哪些服务器操作"没有统一审计 |
| 可用性 | console 探活包含 dsh(3081)/dsh-login(3082)，但无独立看门狗规则 |
| 安全 | 公网 Basic+token；无 `/app` 限流；token 会出现在 URL/日志；DevTools 会话会抬高 CPU |

---

## 2. 目标架构

```text
外部浏览器
  │ HTTPS 44904
  ▼
nginx (8443 TLS, /app/ Basic Auth, 限流, 维护开关)
  │  /app-login → dsh-login(3082) → 3081
  ▼
DSH (127.0.0.1:3081)                      ← 决策/执行大脑
  │  使用受控工具层
  ▼
server-ops（/root/server/ops/）             ← 执行层（allowlist + 审计 + 确认）
  ├── supervisorctl（服务重启/状态）
  ├── nginx -t / reload
  ├── server-backup / verify
  ├── logs / metrics / dsh url / dsh restart
  └── 审计：/root/server/logs/ops-audit.jsonl
        ▲
Console（观测/告警/校验）← 只读 API / 状态卡片 / 告警
```

**分工**：
- Console = 仪表盘/告警/备份校验/审计展示（人看）。
- DSH = 外部人机交互入口 + 诊断/决策/执行（LLM 大脑 + 工具）。
- server-ops = 唯一受控执行层，任何对服务器的变更都从这里走，便于审计与回滚。
- 底层仍是 supervisord/nginx/frp（不引入 systemd/root）。

---

## 3. 方案 A：访问与安全（DSH 对外入口）

1. **稳定入口**：只对外暴露 `https://47.97.70.99:44904/app-login`（302→cookie→`/app/`）；token 入口用于调试，不建议分发。
2. **传输与认证**：
   - 只允许 HTTPS（公网 HTTP 返回 403；已有规则）。
   - Basic Auth 密码定期轮换（`/root/server/etc/dsh-web.htpasswd`），与 DSH token 分离；**不要把 token 发到公开渠道**。
   - `/app/` 加 `limit_req`（如 5r/s burst 10），`/app-login` 更严格；记录 401/429 审计。
3. **可选增强**（P2）：
   - 固定公网 IP 允许列表（frps 侧或 nginx `allow/deny`）；
   - 2FA/OTP（nginx + auth_request 或前置反代）；
   - 更私密方案：Cloudflare Tunnel / Tailscale（不暴露公网端口；需注意 Android 上 VPN 与服务器网络共存）。
4. **维护开关**：`touch /sdcard/DSH/dsh-app-public.off` 立即 403；误操作/升级时使用。
5. **凭据**：DSH Basic 密码、console token、vault 分库存放（docs/15）；不写进文档/聊天。

---

## 4. 方案 B：可靠性与持久化

### 4.1 可用性
- supervisor：`autostart=true`、`autorestart=unexpected`、`startsecs=8`；dsh-login 同。
- 看门狗：在 `server-watch`（或 Termux 化看门狗，docs/18）增加规则：**DSH `/` 连续 2 次失败 → 重启 dsh**；dsh-login TCP 3082 同理。
- console 已有探活；页面显示 DSH/登录入口状态。
- 重启验证：`server-up` → dsh 启动；`/app-login` 302、token 200（每次重启 token 会变，用 `server-dsh url`）。
- DSH RSS 监控：>500MB 告警；DevTools 会话关闭；`--max-old-space-size=512` A/B（docs/18）。

### 4.2 升级/回滚（蓝绿思路）
1. 备份 `/root/.dsh`（本次先纳入 server-backup）。
2. 新版本装到 `/opt/dsh-next`（`npm --prefix`），在 3083 临时启动验证（`--port 3083`）。
3. 验证 `/app-login`/API 正常；修改 supervisor `dsh` 命令端口→3083 或切换 nginx upstream；观察 10 分钟。
4. 失败回滚：恢复 supervisor/nginx 配置 + 旧 `/opt/dsh`。
5. 固定 `@deepseek-ai/dsh@0.2.2-rc.1` 与 Node24；升级记录进 docs。

### 4.3 持久化范围（修正当前缺口）

`server-backup` 增加：
```
/root/.dsh/sessions
/root/.dsh/storages
/root/.dsh/profiles/server
/root/.dsh/profiles/web            # 排除 node_modules（可 pnpm 重装）
```
- `profiles/web` 的 `package.json`/`cordis*.yml`/`pnpm-lock.yaml` 必须包含；`node_modules` 排除（286MB → 备份体积大幅降低）。
- 恢复：解包后 `cd /root/.dsh/profiles/web && pnpm install --frozen-lockfile`（或按 docs/12/13 的安装流程）。
- 同时把 DSH 工作区/项目文件（如果放在 profile 内）确认在范围内；在 `server-manifest.json` 记录版本/锁文件 hash。
- 纳入每日备份 + PC/异地副本（docs/18 3-2-1）。

---

## 5. 方案 C：执行工具层（server-ops）——"大脑的手"

### 5.1 设计原则
- **唯一入口**：DSH 对服务器的变更只通过 `server-ops`，不直接 `rm/reboot/restore`。
- **分级权限**：
  - Tier 1 只读：status/health/services/logs/metrics/backups list/dsh url。
  - Tier 2 受控写：restart/start/stop 单服务、nginx -t+reload、run backup、rotate logs（要求 `--confirm`）。
  - Tier 3 危险：restore/升级/删除数据——**不进 server-ops**；只允许人工 SSH + 双重确认 + 备份。
- **审计**：每条命令写 `ops-audit.jsonl`（时间/调用者/命令/目标/结果/耗时），console 可展示。
- **可回滚**：Tier 2 变更前自动保存配置快照（supervisord/nginx）到 `/root/server/backups/config-snap-<ts>/`。
- **无注入**：固定子命令与白名单参数，不做 `eval`、不拼接用户输入到 shell。

### 5.2 命令草案

```bash
server-ops status                 # 服务/健康/版本/DSH 状态
server-ops services               # 列表+端口+健康
server-ops logs dsh --lines 200   # 白名单日志
server-ops health                 # 本机/公网/DSH/证书
server-ops dsh url                # 当前 token 入口（敏感，仅本地/管理）
server-ops restart nginx --confirm
server-ops nginx test --confirm && server-ops nginx reload --confirm
server-ops backup --confirm       # 调用 server-backup
server-ops backup verify-last     # 解密/tar/sqlite 校验
server-ops audit --limit 100
```

- 输出 JSON 模式 `--json` 供 DSH 解析；错误码明确。
- DSH 侧：创建 `/root/server/ops/README.md` + DSH 系统提示/技能说明：
  - "先读 status/logs；变更必须 `--confirm`；禁止操作 Android 宿主/宿主机 root；遇到 restore/升级/删除，要求人工确认。"
- 后续可增加 MCP/HTTP 工具网关（把 server-ops 暴露为受控 API），但 CLI 已够用且易审计。

### 5.3 与 Console 的集成
- Console 展示 DSH 状态、最近 ops 审计、备份校验状态；提供"打开 DSH"链接。
- DSH 只读 console API（若有需要）使用**只读 token**，不得拿 console 管理 token。
- 告警 → 人工/DSH 诊断；高风险动作仍需人工确认。

---

## 6. 安全威胁模型（必须面对）

DSH 对外暴露 = 外部拿到 DSH 就等于拿到服务器 root-in-proot 的 shell（可读写 `/root/server`、改配置、读备份密钥）。

| 威胁 | 缓解 |
|---|---|
| Basic/Token 泄露 | HTTPS only、定期轮换、限流、不记录 token 到公开日志、维护开关 |
| 暴力破解 | nginx limit_req、fail2ban（可选）、401 审计/告警 |
| DSH 被诱导执行破坏命令 | server-ops 白名单 + 确认 + Tier3 禁止；系统提示约束；审计 |
| 外部内容 prompt injection | 把网页/日志视为数据；server-ops 不接受自然语言任意命令；高风险动作人工确认 |
| DSH 进程被攻破 | 最小暴露（仅 44904 `/app-login`）；及时升级 DSH/Node；profile 备份；监控异常命令 |
| 单点 | DSH 宕机 → 控制台/SSH 仍可管理；备份/异地副本；外部门铃 |

> 结论：DSH 可以做"大脑"，但**必须把"手"（执行层）收在白名单工具层里**，并保留 SSH/console 作为旁路。

---

## 7. 路线图（建议）

### P0（1–2 天，低风险）
1. `server-backup` 纳入 `/root/.dsh` 的四个路径（排除 node_modules），跑一次备份 + verify。
2. 增加 DSH 看门狗规则（连续 2 次失败重启 dsh/dsh-login）。
3. `/app/` 加 nginx 限流；确认 HTTPS-only/维护开关；关闭 DevTools。
4. 建立 `server-ops` **只读版**（status/health/services/logs/backups/dsh url）+ 审计日志；DSH 系统提示接入。
5. 重启验证：`/app-login` 302、token 200、console 显示 DSH 状态。

### P1（3–5 天）
- server-ops Tier2（restart/nginx/backup，`--confirm` + 配置快照 + 审计）。
- DSH 升级蓝绿流程文档与一次演练；DSH heap 512MB A/B。
- Console 增加 DSH 卡片/ops 审计视图；备份校验 UI。
- 维护开关演练（403）。

### P2（按需）
- MFA/IP allowlist/Cloudflare/Tailscale；server-ops HTTP/MCP 网关；DSH 技能包（server runbooks）；外部门铃+DSH 诊断闭环。

---

## 8. 验收清单

- [ ] 外部 `/app-login` 302，token 200；HTTP 403；维护开关 403。
- [ ] 重启后 DSH/dsh-login 自动 RUNNING，入口可用；console 显示 DSH 健康。
- [ ] DSH profile（sessions/storages/profiles，不含 node_modules）进入备份且 `--verify` 通过；恢复演练可重建。
- [ ] `server-ops` 只读命令可用、写命令有确认/审计/快照；DSH 无法绕过（提示词约束+权限）。
- [ ] DSH 连续失败自动重启；RSS/CPU 在阈值内；DevTools 关闭后 CPU 回落。
- [ ] 失败回滚：supervisor/nginx/旧 /opt/dsh 恢复脚本可用。

---

## 9. 需要拍板的点

| 决策 | 建议 |
|---|---|
| 对外入口 | 保持 `/app-login`（302→cookie→`/app/`）；只 HTTPS |
| 认证增强 | 先限流+轮换；MFA 后续 |
| DSH 权限 | 保持 root-in-proot，但所有变更经 server-ops（推荐） |
| 备份范围 | profile 排除 node_modules；sessions/storages/server profile 必含 |
| 升级方式 | 蓝绿 3083 验证后切 upstream（推荐） |
| server-ops 形态 | Bash/Python CLI 先行；后续 MCP/HTTP |
| 外部门铃 | 独立于 DSH（手机宕机时仍可告警） |

> 本文只做方案设计，未改动服务器。若批准 P0，我按"先备份 profile → 加看门狗/限流 → 只读 server-ops → 重启验证"顺序执行。
