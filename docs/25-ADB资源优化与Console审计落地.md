# 25 · ADB 资源优化 + Console DSH/ops 审计落地

> 日期：2026-11-10 21:28–21:40
> 范围：机器本地；无外部依赖。

---

## Part 1：ADB 为服务器让资源（P0 执行）

### 1.1 执行内容

新增 `scripts/adb-server-resource.ps1`（`-Status / -Quiet / -Restore`），本次执行 `-Quiet`：

- 重放 P0 设置：`cached_apps_freezer=enabled`、`logcat -G 1M`、`low_power=0`、`adaptive power saver=false`、`wifi_sleep_policy=2`；
- `cmd netpolicy add restrict-background-whitelist 10250`（Termux UID 保护）；
- 静默研究 App：`com.aistra.hail`、`io.github.samolego.canta`、`io.github.muntashirakon.AppManager`、`moe.shizuku.privileged.api`（Shizuku **UI**）；
- **保留** `shizuku_server`（独立 shell 进程，未被杀）。

### 1.2 前后对比

| 指标 | 前 | 后 |
|---|---|---|
| MemAvailable | 3.76 GB | **3.87 GB** |
| MemFree | 755 MB | **844 MB** |
| Hail / Canta / Shizuku UI | 178 / 166 / 145 MB | 已退出 |
| shizuku_server | 134 MB | 134 MB（保留） |
| Termux 保护 | 白名单/bucket 5/appops allow | 不变 |
| netpolicy 白名单 | 10081 10125 | **+10250（Termux）** |
| Termux app 进程 | `prcp F/S/FGS` | 不变 |

> 说明：释放的 RSS 未等量体现在 MemAvailable（Android 共享页/缓存回收机制），但研究 App 进程已消失、内存压力下降。

### 1.3 未做/注意

- **未重启 DSH**：当前通过 DSH Web 对话，重启会中断会话并换 token；DevTools 会话需在浏览器侧关闭。
- Shizuku UI 被 force-stop 后，下次使用 Canta/Hail 需重新打开 Shizuku App（`shizuku_server` 仍在，`server-dsh` 无关）。
- `-Restore` 只恢复 freezer/logcat 辅助设置，不会自动启动研究 App。

---

## Part 2：Console 展示 DSH / ops 审计

### 2.1 实现

- **API**：`console-api.py` 增加只读 `GET /api/ops?n=20`，读取 `/root/server/logs/ops-audit.jsonl` 最近条目（默认 20，上限 200）。
- **UI**：首页新增分组 **「DSH 控制平面 / Ops 审计」**（`id=ops-audit-group`，避免与既有 `ops-group` 冲突），展示最近 12 条：
  `时间 / 命令 / 参数 / rc`；随 `/api/overview` 刷新一起拉取。
- 部署：备份原文件 `.bak-console-ops-20261110-2132`，`py_compile` 通过；用 `server-ops restart api --confirm` 重启（快照+审计）。

### 2.2 验证

| 检查 | 结果 |
|---|---|
| `GET /api/ops?n=5`（直连 8000 / 8080 / 公网 48108） | 200，返回最近 5 条审计 |
| 页面含「DSH 控制平面 / Ops 审计」 | ✅ |
| 页面 JS 引用 `ops-audit-list` / `ops-audit-count` | ✅（无 ID 冲突） |
| `api` / `nginx` | RUNNING |
| `/app-login`（DSH） | 302（未受影响） |

### 2.3 回滚

```bash
cp -p /root/server/api/app.py.bak-console-ops-20261110-2132 /root/server/api/app.py
cp -p /root/server/www/index.html.bak-console-ops-20261110-2132 /root/server/www/index.html
/root/server/bin/server-ops restart api --confirm
```

---

## 复用与文件

- `scripts/adb-server-resource.ps1`（ADB Quiet/Status/Restore）
- `scripts/server/console-api.py`（新增 `/api/ops`）
- `scripts/server/console/index.html`（Ops 审计卡片）
- 关联：[docs/19](19-ADB为服务器让资源方案.md)（方案）、[docs/21](21-DSH控制平面落地手册.md)/[docs/22](22-DSH-Tier2受控写落地.md)（server-ops 审计来源）

## 后续

- DSH 有新版本后按 docs/23 做真实升级；
- 外部告警/异地备份/MFA 按用户要求暂不接入。

---

## Part 3：重启验证（含 guard v1.2 修复）

### 3.1 两次重启对比

| 项目 | 第一次（旧 dsh-guard） | 第二次（guard v1.2） |
|---|---|---|
| ADB 在线 | 32s | **32s** |
| 8080 服务就绪 | 44s | **45s** |
| 12 服务 + DSH 登录完整就绪 | DSH 初始启动被 guard 误重启，约 2 分钟+ | **111s** |
| `/app-login` | 中途 503，恢复后 302 | **302** |
| dsh-guard 开机重启 | 有（STARTING 阶段被判定失败） | **无**（仅记录 1 次瞬时失败，未重启） |
| 12/12 RUNNING | 最终达成 | **达成** |

### 3.2 修复内容

`dsh-guard` v1.2：只有 `supervisorctl status` 为 **RUNNING** 时才做 HTTP 健康检查；
`STARTING/BACKOFF` 阶段不计数、不重启，避免开机时 DSH 还在启动就被误杀。

### 3.3 重启后 Android 优化项状态

| 项 | 重启后默认 | 处理 |
|---|---|---|
| `cached_apps_freezer` | **disabled**（MIUI 重置） | `adb-server-resource.ps1 -Quiet` 重放为 enabled |
| logcat | **2MiB**（重置） | 重放 `-G 1M` |
| netpolicy 白名单 | **持久**（含 Termux UID 10250） | 无需重做 |
| deviceidle 白名单 | **持久**（com.termux / Termux:Boot） | 无需重做 |
| 研究 App（Hail/Canta/Shizuku UI/AppManager） | **未自启** | 保持静默 |
| `shizuku_server` | **未自启**（需 ADB 启动） | 预期行为；需要研究工具时手动启动 |
| MemAvailable | 5.00GB（研究 App 未自启） | 重放 Quiet 后 ~4.99–5.22GB（视缓存） |

### 3.4 结论

- **开机自启链路稳定**：ADB 32s、8080 45s、完整服务+DSH 111s；
- **guard v1.2 消除了开机误重启**，DSH 启动更平稳；
- ADB 资源优化收益明显：研究 App 静默后 MemAvailable 从 3.76 → 5.0GB 级；
- DSH token 随重启变化，统一走 `/app-login`（302）即可；
- Console `/api/ops` 与 Ops 卡片重启后正常（公共入口 200）。

> 外部告警/异地备份/MFA 仍未接入（按用户要求）。