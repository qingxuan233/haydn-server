# 23 · DSH 蓝绿升级演练报告与复用手册

| 项目 | 内容 |
|---|---|
| 文档 ID | `HB-DSH-023` |
| 版本 | v2.0（2026-11-11） |
| 状态 | 历史记录（2026-11-10 演练报告；§4 真实升级流程仍现行） |
| 关联 | [20 控制平面方案](20-DSH控制平面方案.md) · [21 P0 落地手册](21-DSH控制平面落地手册.md) · [22 Tier2 受控写](22-DSH-Tier2受控写落地.md) · [24 sessions 持久化](24-DSH-sessions持久化补全.md) · [当前状态](../00-overview/当前状态.md) |

> **历史记录（2026-11-10）**：本文是**同版本多实例**的演练报告（未真正升级版本），数字为当时快照；§4 的升级流程可照做。当前 DSH 为 `dsh`+`dsh-login`+`dsh-guard`，服务器 **12/12 RUNNING**，最新状态见 [当前状态](../00-overview/当前状态.md)。

> 时间：2026-11-10 20:58–21:06（Asia/Shanghai）
> 范围：机器本地；无外部依赖。
> 目标：验证 DSH 升级/切换/回滚流程（蓝绿思路），为后续真正升级 DSH 版本做准备。

---

## 1. 架构与思路

```text
当前稳定实例 Green：/opt/dsh  + profile=web + 127.0.0.1:3081  （线上）
候选实例 Blue：       同包/新包 + profile=bgdrill + 127.0.0.1:3083（验证）
                          │
dsh-login(3082) 读取 dsh.log / DSH_PORT → 决定登录后指向哪个实例
nginx dsh_upstream    → 127.0.0.1:3081 或 3083
```

- 用**独立 profile**（`bgdrill`）避免与线上 profile 争锁。
- 同包演练不升级版本；真实升级时把新版本装到 `/opt/dsh-next` 并替换 `command` 路径。
- 切换只改两处：`dsh_upstream`、`dsh-login` 的 `DSH_LOG/DSH_PORT`；验证通过后保留，失败立即恢复。

---

## 2. 本次演练步骤（已实际执行）

> 切换/回滚用的 `server-ops nginx reload --confirm` 属 **Tier2 受控写**（快照 + 审计），见 [22 Tier2 受控写](22-DSH-Tier2受控写落地.md)。

1. **准备 Blue 实例**
   - 新增 `/root/server/etc/conf.d/dsh-next.conf`：`port 3083`、`DSH_PROFILE=bgdrill`、`DSH_PROFILE_DIR=/root/.dsh/profiles/bgdrill`；
   - `supervisorctl reread/update; start dsh-next`；3083 返回 401（服务在）、日志输出新 token。
2. **备份切换点**
   - `supervisord.conf.bak-bgdrill-<ts>`、`dsh-upstreams.conf.bak-bgdrill-<ts>`。
3. **切换（cutover）**
   - `dsh-login` env 改为 `DSH_LOG=/root/server/logs/dsh-next.log`、`DSH_PORT="3083"`；
   - `dsh_upstream` 从 3081 → 3083；
   - `supervisorctl reread/update; restart dsh-login`；`server-ops nginx reload --confirm`（快照+审计）。
4. **验证**
   - `/app-login` 跟随登录：**200**
   - `/app/`（带 cookie）：**200**
   - dsh-next RUNNING；dsh-login RUNNING；nginx RUNNING
5. **回滚**
   - 恢复两份 `.bak-bgdrill-*`；`supervisorctl reread/update; restart dsh-login`；`server-ops nginx reload --confirm`；
   - `/app-login` 跟随：**200**；`/app/`：**200**（Green 3081）
6. **清理**
   - `supervisorctl stop dsh-next`、删除 `dsh-next.conf`、`reread/update`；
   - 删除 `/root/.dsh/profiles/bgdrill`、`/opt/dsh-next`；
   - 最终 **12/12 RUNNING**；公网 HTTP/HTTPS health = 200（端口/入口见私密记录）。

---

## 3. 关键经验/坑

1. **不要用直连 token URL 做验证**：对 3081/3083 直连 `/?token=` 都会 401——DSH 的 token 登录依赖 nginx/dsh-login 的 token 交换；应验证 `/app-login` 跟随后的 200。
2. **dsh-login 有两处要同步切**：`DSH_LOG`（读哪个实例的 token）和 `DSH_PORT`（连接哪个实例）；只切 nginx upstream 会导致登录与页面不一致。
3. **备份 bond**：切换前必须同时备份 `supervisord.conf` 与 `dsh-upstreams.conf`；回滚只需恢复这两份 + 重启 dsh-login + reload。
4. **profile 隔离**：Blue 用独立 profile，避免与 Green 争锁；空 profile 能启动并出 token，说明蓝绿验证可行。
5. **清理要彻底**：停 Blue、删 conf、`supervisorctl update`、删 profile；避免残留 supervisor 服务/端口。

---

## 4. 真正升级 DSH 版本的复用流程

1. 在 `/opt/dsh-next` 安装新版本（Node24）：
   ```bash
   PATH=/opt/node24/bin:$PATH npm install -g --prefix /opt/dsh-next @deepseek-ai/dsh@<新版本>
   cd /opt/dsh-next/lib/node_modules/@deepseek-ai/dsh
   npm install --no-save node-addon-require-builtin-linux-arm64-gnu@0.1.9
   ```
2. 新增临时 `dsh-next` supervisor 程序，`command` 指向 `/opt/dsh-next/.../bin.js`，端口 3083，独立 profile。
3. 启动并只验证 3083 进程/日志/401；**不要**直接切公网。
4. 切换（同本文步骤 3：dsh_log/dsh_port + upstream），验证 `/app-login` 200、页面 200。
5. 稳定观察一段时间（建议 10–30 分钟：日志无错误、内存正常）。
6. 若失败：恢复两份备份配置；若成功：把 `/opt/dsh` 与 `/opt/dsh-next` 的角色互换（旧版保留为回滚副本）。

---

## 5. 验收/回滚

- 验收：`/app-login` 200、`/app/` 200、12/12 RUNNING、公网 health 200、日志无持续报错。
- 回滚：`.bak-bgdrill-*` 两份配置 + `restart dsh-login` + `nginx reload`；蓝实例停用/删除。
- 注意：切换期间 DSH token 会随实例变化；用户用 `/app-login` 重新登录即可。

---

## 6. 本次结论

- **蓝绿切换/回滚机制已验证可行**；DSH 升级不再高风险。
- 本次为**同版本、独立 profile**演练，未升级版本；真实升级按 §4 执行。
- 全程无外部依赖；未改动 Android 宿主。
