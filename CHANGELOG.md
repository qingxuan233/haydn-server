# 变更记录（CHANGELOG）

> 本文件是**当前迭代对外可感知变更摘要**，不是工作日志。当前窗口最多 **8 条**；更早条目按月归档到 `changelog/YYYY-MM.md`（**归档默认不读**，只在追溯时读单个文件）。
> 记录边界见 [MTH-011](methodology/10-document-lifecycle.md)，归档窗口与上下文预算规则见 [MTH-015](methodology/15-archive-and-context-budget.md)；归档索引见 §4。

| 项目 | 内容 |
|---|---|
| 文档 ID | HB-CHANGELOG-001 |
| 版本 | v2.0（2026-11-11 归档规范化） |
| 状态 | 现行 |
| 关联 | [MTH-011](methodology/10-document-lifecycle.md) · [MTH-015](methodology/15-archive-and-context-budget.md) · [changelog/README.md](changelog/README.md) · [当前状态](docs/00-overview/当前状态.md) · [README](README.md) · [AGENTS](AGENTS.md) |

## 1. 记录边界

| 内容 | 唯一位置 |
|---|---|
| 当前方法/规范/边界 | `methodology/`（MTH-001..018） |
| 红线与必须检查项 | `guardrails/`（GRD-001..016） |
| 踩坑证据与修复 | `pitfalls/`（PIT-001..025） |
| 当前任务/未完成/需要授权 | [backlog.json](backlog.json) |
| 对外可感知变更摘要 | 本文件（当前窗口 ≤8 条） |
| 历史变更 | `changelog/YYYY-MM.md`（归档，默认不读） |
| 原始过程/逐条命令输出 | git commit（本仓库无 PR/远程时由 commit message 承载） |
| 设备案例事实 | [cases/](cases/README.md) 与旧 `docs/`（冻结证据） |
| 机器索引 | `agent-manifest.json` 摘要 + `agent-manifest.d/` 分片 |

## 2. 硬上限

1. **每条最多一行**（三要素：变更 / 验证 / 未完成；无未完成可省略），禁止原始日志、测试计数明细、临时账号与清理记录。
2. **当前窗口最多 8 条**；新增第 9 条时，立即把最旧条目移入对应 `changelog/YYYY-MM.md`，不等月末。
3. 归档文件**只读不改**、按时间倒序追加；同一能力的后续修补并入原条目，不重复开条。
4. 归档索引在 §4 维护；`CHANGELOG.md` 体积与条数由 `toolkit validate` 机检（见 [doc-policy](toolkit/schema/doc-policy.json)）。

## 3. 当前变更（最新在上，最多 8 条）

| 日期 | 版本 | 变更 |
|---|---|---|
| 2026-11-15 | v1.83 | **控制台走读审查修复、运行环境加固与界面汉化（三阶段）**：①阶段一确证 3 高/12 中/10 低并单独汇报——WebDAV 轮换验证恒真（直连 18082 对任意 Basic 回 207）、`/api/status` 的 `telemetry.last` 无 `ts` 致最后采样恒空、Vaultwarden `DOMAIN` 指向不可达域名致 Web 客户端登录回路断；②阶段二：`_verify_basic()` 改经网关 `PROPFIND`（错误口令 401，直连 207 留作根因证据）；页面改用 `last_ts` 并统一空值/证书过期/soak 本地时间；`DOMAIN=https://8.137.162.154:60177`、Forgejo `ROOT_URL=https://8.137.162.154:60875/git/` 备份后重启并实测（公网 `/api/config` 200、日志回显新 AppURL）；`supervisor.protected=[haydn-frpc,haydn-tls,haydn-sshd]` 禁止控制台 stop（400+原因，页面置灰并说明）；`/api/logout` 补同源校验、`lan-probe` 不再回传网段、登录先验口令再记限流、代理剥离 `haydn_session`、请求体 2MiB/`/dav` 64MiB（3MiB→413）、凭据写盘加锁与 `bw --passwordenv`（登录后解锁补一次重试，`--vault-sync` 5 ok/1 skipped）；运行环境：目录 777→755、审计与 CSV 640、logrotate 加 `maxsize` 并对 CSV 日轮转（`-d` 无 duplicate）、healthcheck 增内存水位与异常服务自动拉起并用 `.stopped-<svc>` 区分人工停止（实测 RECOVER/跳过）；③阶段三 Forgejo `[i18n] LANGS=zh-CN,en-US` + `NAMES` 后无 `Accept-Language` 即 `zh-CN`（只写 LANGS 会 panic）、`zh-CN`/`en-US` 各自正确；Vaultwarden 无服务端开关，已按 `locales/zh_CN` 写清 Web 客户端语言路径；[web-console README](2026-11-14/web-console/README.md) §13.11/§14 新增“新服务接入一页”、语言口径与备份恢复入口；回滚备份 `/data/server/backups/{console-p2,p2-runtime,p2-upstream,console-p2b}-*`；v1.75 归档至 [changelog/2026-11.md](changelog/2026-11.md)（窗口 8 条、归档 76 条）；验证：preflight 全绿、内联 JS `node --check` 通过、`reread/update` 后 13 个服务全 RUNNING；未完成：浏览器 DOM 级点击仍以接口+页面代码核验（无 Playwright），Vaultwarden 语言选择未做客户端实点。 |
| 2026-11-15 | v1.82 | **凭据查看口令 + 概览/遥测合并**：①新增只读接口 `POST /api/credential/reveal`（登录态 + 同源校验、响应 `no-store`、不写缓存/文件），按服务取设备侧明文（`plain_file`；Vaultwarden 用 `account_file` 的 `password=`），每次调用审计 `credentials.reveal`（服务名/文件路径/来源地址，不含口令），`device-root` 无明文 → 400；②页面凭据表 `has_password` 行新增“查看/收起”，就地插入等宽口令与复制按钮，Vaultwarden 查看前复用 `armConfirm()` 二次确认，CSV 下载逻辑未改；③“概览”与“遥测与 soak”合并为“概览与设备遥测”，上层主机（运行时长（主机）/负载/内存/磁盘/证书）、下层遥测（最后采样+样本/电池+状态/温度/可用率/重启），负载只出现一次，soak 改为底部独立行（本轮起点/已运行/剩余/样本），放电中与可用率 <100% 用黄色，保留“只展示观测值、不判定验收通过”，仅复用现有 `/api/status` 字段；④实测：五个服务 reveal 200 且与设备文件逐字符一致、`no-store`、无会话 401、`device-root` 400，审计 5 条 `ok` + 1 条 `refused` 且追加区不含任何口令；`/api/status` 键不变（`overview.load=[3.07,3.18,3.29]`、`telemetry.samples=327`/`availability=98.17`/`reboots=11`、`soak.elapsed=16969`/`remaining=69430`/`samples_since_start=56`），页面不再含“遥测与 soak”；入口 5 条、lan/backup/metrics（187661 B）/restart heartbeat/rotate 失败路径/CSV 令牌均正常；[web-console README](2026-11-14/web-console/README.md) §13.10 同步；v1.74 归档至 [changelog/2026-11.md](changelog/2026-11.md)（窗口 8 条、归档 75 条）；验证：preflight 全绿、内联 JS `node --check` 通过；未完成：浏览器 DOM 级点击仍以接口+页面代码核验（无 Playwright）。 |
| 2026-11-15 | v1.81 | **轮换时间就地刷新、时间显示本地化、移除凭据文件/日志面板**：①定位“轮换 WebDAV/Forgejo 后上次轮换时间不变”：审计 `credentials.rotate` 显示 webdav `17:24:23Z`、forgejo `17:23:44Z` 均到达且 `ok`，`credential-state.json` 的 `rotation.at` 已写入 → 属“请求到了、状态也写了、页面没重新拉取”，非服务端丢写；②前端 `rotate()` 成功后就地 `patchCredRow()` 改写该行并 `loadStatus()` 兜底，失败分支同样刷新，`api()` 加 `cache:'no-store'`；实测 console 轮换 200、`rotated_at` `17:21:17Z`→`17:30:17Z`、同会话 `GET /api/status` 该行已变（`changed: True`），失败路径 `device-root` → 400 + 原因；③时间统一 `fmtTs()` 转本地并标注时区（UTC 原值留 `title`）；④移除页面“凭据文件（仅存在与权限）”表格与“日志”面板及只服务它们的 `GET /api/log`（`_api_log`）、`/api/status` 的 `secrets`/`logs` 字段、`actions.secrets_summary()`、配置项 `secrets_dir`（`logs` 映射保留，仅供 `--check-config` 打印路径）；日志改在设备直接看（路径见 README §13.9）；⑤依赖确认：新控制台内仅 `console_ui.py` 用过 `/api/log`；`scripts/server/webui/app.py` 为冻结旧系统自带 `/api/logs`；`inventory/console-selftest.py`（gitignored）仍引用旧接口，属测试脚本非运行时依赖；⑥移除后实测：页面 200 且 `log-body`/`log-name`/`secrets`/`renderSecrets`/`loadLog` 均不存在，`/api/log` 与 `/api/secrets` 404，`/api/status` 键为 `services/overview/telemetry/soak/cert/credentials/backup/now/ok`，入口 5 条、restart `haydn-heartbeat` 200（`stopped/started`）、`/api/lan`/`/api/backup`/`/api/metrics`（187685 B）均 200、凭据令牌 200→下载 200/1208 B/6 行、局域网 18090 登录页 200；[web-console README](2026-11-14/web-console/README.md) §13.9 同步；v1.73 归档至 [changelog/2026-11.md](changelog/2026-11.md)（窗口 8 条、归档 74 条）；验证：preflight 全绿；未完成：浏览器 DOM 级自动点击仍以接口+页面代码核验（无 Playwright）。 |
| 2026-11-15 | v1.80 | **控制台自轮换时间戳与会话提示、局域网切换按钮上移**：①定位"控制台行时间停在 16:16:18Z"：`credential-state.json` 该条目只有旧 `rotated_at`、无任务 D 之后的 `rotation` 字段，期间没有一次走到状态写入的轮换（审计无对应请求）；新代码实测 `POST /api/rotate {service:"console"}` → 200、`rotation.at=17:21:17Z`、`rotation.ok=true`、`steps` 四项全 True（写入/回读/登录验证/写入密码库）；②轮换兜底异常由 `RotationError` 放宽为 `Exception`，任何写入/回读/验证失败都回滚并落 `rotation={at,ok:false,error}`（摘要截断、不含口令），接口 400 由页面显示；失败路径实测 `{service:"device-root"}` → 400 + "该服务不支持服务端轮换（见说明）"；③控制台轮换只替换 `secret.json` 的 `password`/`updated`，`session_key` 不变：实测轮换后同一 cookie `GET /api/status` 仍 200，页面明确提示"控制台登录口令已更新、当前会话保持有效、下次登录用下方新口令"；④"切到局域网（省流）"按钮移到页面顶部"局域网省流入口"卡片，底部"访问入口"只保留信息网格（全页唯一 `id="lan-go"`，页内顺序 lan-go→服务入口→访问入口），非同一网段时按钮置灰并写明原因；[web-console README](2026-11-14/web-console/README.md) §13.7/§13.8 同步；v1.72 归档至 [changelog/2026-11.md](changelog/2026-11.md)（窗口 8 条、归档 73 条）；验证：preflight 全绿；未完成：非同一网段置灰仅代码路径核验（未改网络实测）。 |
| 2026-11-15 | v1.79 | **控制台入口收敛与交互统一**：①主站判定：`GET /` 实测为 302 B 占位自检页（无实际内容）→ 移除"主站"入口，网关根路径改为 302 → `/console/`（静态站保留为未匹配路径兜底）；②`entries[]` 移除与底部按钮重复的"局域网省流入口"，由 7 条收敛为 5 条；③"当前入口"改读 `/api/lan` 的 `lan_url` 与新增 `public_root`，不再回显 `location.host`，失效域名不再出现在面板；④Prometheus 指标：`node_exporter` 仅绑 `127.0.0.1:9100`、iptables 默认 DROP 且无 9100 放行（局域网表现为超时）→ 新增会话鉴权代理 `GET /console/api/metrics`（未登录 401、登录后 200 `text/plain`），不开端口、不改 iptables；⑤服务启停与备份按钮改用页内两步确认（`armConfirm`，5 秒窗口），`stop`/`restart` 文案写明中断影响，执行中与成功/失败原因均可见；验证：根路径 302 → `/console/`、5 条入口 `available` 全 True、指标 401/200、仅重启可控目标 `haydn-local-http`（未触碰网关/隧道/备份管线）；设备配置改动前备份 `gateway.json.bak-20261115T…`；[web-console README](2026-11-14/web-console/README.md) §13.1/§13.7 同步；v1.71 归档至 [changelog/2026-11.md](changelog/2026-11.md)（窗口 8 条、归档 72 条）；验证：preflight 全绿；未完成：指标页为纯文本导出，未做图表化。 |
| 2026-11-15 | v1.78 | **凭据状态口径改为"当前"并修复控制台两处交互故障**：①`console_credentials.py` 新增 `vault_reason()`/`stamp_vault_state()`，`credential-state.json` 每服务分开记 `rotation={at,ok,error}` 与 `vault={at,ok,skipped,error}`；`sync_all()` 每次运行刷新全部服务并落盘（成功即清除历史失败），`rotate()` 失败也落 `rotation.ok=false`，`summary()` 输出 `vault_at`/`rotation_ok` 并兼容旧字符串状态；页面拆为"上次轮换（服务验证）"与"密码库同步"两列，失败显示原因摘要（如"写库客户端不可用"）且不含口令；②修 `unknown console endpoint`：下载跳转改用接口返回的 `path`（已含 `/console` 前缀），原先把前缀拼了两次成 `/console/console/...`；③轮换按钮改页内两步确认（原生 `confirm` 被浏览器"阻止更多对话框"后静默返回 false＝点击无反应），失败在 `#cred-msg` 显示 `error` 与失败步骤；验证：`--vault-sync` 5 条 ok / `device-root` skipped、独立回读 5 条 `password_match`/`username_match` 全 True、WebDAV 库内条目与生效口令逐字符一致且 `PROPFIND /dav/` 207；下载链路 令牌 200→下载 200/1208 B/6 行→二次 410、旧双前缀路径 404；轮换 forgejo 200/三步 True/`rotated_at` 16:51:21Z/库内同步，轮换 device-root 400+原因；7 个入口 `available` 全 True；[web-console README](2026-11-14/web-console/README.md) §13.3/§13.4/§13.5 同步；v1.70 归档至 [changelog/2026-11.md](changelog/2026-11.md)（窗口 8 条、归档 71 条）；验证：preflight 全绿；未完成：设备上仍用原生 `confirm` 的启停/备份按钮存在同类静默风险（本轮未改）。 |
| 2026-11-15 | v1.77 | **凭据 CSV 入库校验与本机明文清理**：`--vault-sync` 幂等复跑 `console/webdav/forgejo/vaultwarden/vaultwarden-admin: ok`、`device-root: skipped`、`vault_sync: ok`；独立回读 folder 内 **5 条、无重名、`password_match` 全 True**（`device-root` 无明文口令不入库，只留 CSV 备注）；备份覆盖实测：手动触发同一 03:30 管线（`backup-loop` 轮询触发文件 → `haydn-backup.sh`），新 `haydn-backup-20261114T163047Z.tar.gz.enc`（97.8 MB）经 `haydn_crypt.py decrypt` 后确认含 `opt/haydn/secrets/vaultwarden-master.txt`（`secrets/` 共 9 项），三来源（haydn/forgejo/vaultwarden）均上传成功并 `DONE ok`，临时解密文件已删；设备侧主密码文件复核 600 root:root 66 B；删除本机 `inventory/haydn-credentials.csv`（经回收站，`git status` 不含；全盘扫描 Desktop/Downloads/Documents/e:\git_code 无其他副本，**回收站需用户手动清空**）；[web-console README](2026-11-14/web-console/README.md) §13.3 同步；未重启整机、未提交 git；验证：preflight 全绿。 |
| 2026-11-15 | v1.76 | **控制台入口去域名化与文档口径统一**：核查设备 `entries[]` 已无 `qingxuan.bbs0.cc` / `vault.qingxuan.bbs0.cc` 入口（仅 `cert_file` 与 `NODE_EXTRA_CA_CERTS` 含域名，是证书文件路径），主站/控制台/WebDAV/Forgejo 保持站内相对路径（随 origin 解析为 `https://8.137.162.154:60875/...` 或局域网 `http://<lan_ip>:18090/...`），Vaultwarden 固定 `https://8.137.162.154:60177/`；验证 `GET /api/entries` 7 条 `available` 全 True，`{lan_ip}`=192.168.31.50、`{lan_root}`=http://192.168.31.50:18090，与 `/api/lan`（wlan0）及 `/srv/haydn/run/lan-subnet`（192.168.31.0/24）一致；**域名入口口径唯一来源**定为 [frp-public-mapping](2026-11-14/frp-public-mapping/outputs/frp-public-mapping.md) §12.1（公网不可用=备案按 SNI 拦截/明文 HTTP 403 `Server: Beaver`；两条 https 隧道保留作回滚；控制台不展示），[web-console README](2026-11-14/web-console/README.md) §4/§12.1/§12.2/§12.5/§13.1 与 [ADR-0008](adr/0008-public-entry-after-icp-sni-block.md)（R3）改为引用、不再复述计数；未改 frpc/stunnel/证书，未重启整机、未重启 gateway（无配置变更），未提交 git；验证：preflight 全绿。 |

## 4. 归档索引

| 月份 | 条目 | 文件 |
|---|---|---|
| 2026-11 | 76 条（v1.0–v1.75） | [changelog/2026-11.md](changelog/2026-11.md) |
