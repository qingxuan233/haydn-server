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
| 2026-11-15 | v1.79 | **控制台入口收敛与交互统一**：①主站判定：`GET /` 实测为 302 B 占位自检页（无实际内容）→ 移除"主站"入口，网关根路径改为 302 → `/console/`（静态站保留为未匹配路径兜底）；②`entries[]` 移除与底部按钮重复的"局域网省流入口"，由 7 条收敛为 5 条；③"当前入口"改读 `/api/lan` 的 `lan_url` 与新增 `public_root`，不再回显 `location.host`，失效域名不再出现在面板；④Prometheus 指标：`node_exporter` 仅绑 `127.0.0.1:9100`、iptables 默认 DROP 且无 9100 放行（局域网表现为超时）→ 新增会话鉴权代理 `GET /console/api/metrics`（未登录 401、登录后 200 `text/plain`），不开端口、不改 iptables；⑤服务启停与备份按钮改用页内两步确认（`armConfirm`，5 秒窗口），`stop`/`restart` 文案写明中断影响，执行中与成功/失败原因均可见；验证：根路径 302 → `/console/`、5 条入口 `available` 全 True、指标 401/200、仅重启可控目标 `haydn-local-http`（未触碰网关/隧道/备份管线）；设备配置改动前备份 `gateway.json.bak-20261115T…`；[web-console README](2026-11-14/web-console/README.md) §13.1/§13.7 同步；v1.71 归档至 [changelog/2026-11.md](changelog/2026-11.md)（窗口 8 条、归档 72 条）；验证：preflight 全绿；未完成：指标页为纯文本导出，未做图表化。 |
| 2026-11-15 | v1.78 | **凭据状态口径改为"当前"并修复控制台两处交互故障**：①`console_credentials.py` 新增 `vault_reason()`/`stamp_vault_state()`，`credential-state.json` 每服务分开记 `rotation={at,ok,error}` 与 `vault={at,ok,skipped,error}`；`sync_all()` 每次运行刷新全部服务并落盘（成功即清除历史失败），`rotate()` 失败也落 `rotation.ok=false`，`summary()` 输出 `vault_at`/`rotation_ok` 并兼容旧字符串状态；页面拆为"上次轮换（服务验证）"与"密码库同步"两列，失败显示原因摘要（如"写库客户端不可用"）且不含口令；②修 `unknown console endpoint`：下载跳转改用接口返回的 `path`（已含 `/console` 前缀），原先把前缀拼了两次成 `/console/console/...`；③轮换按钮改页内两步确认（原生 `confirm` 被浏览器"阻止更多对话框"后静默返回 false＝点击无反应），失败在 `#cred-msg` 显示 `error` 与失败步骤；验证：`--vault-sync` 5 条 ok / `device-root` skipped、独立回读 5 条 `password_match`/`username_match` 全 True、WebDAV 库内条目与生效口令逐字符一致且 `PROPFIND /dav/` 207；下载链路 令牌 200→下载 200/1208 B/6 行→二次 410、旧双前缀路径 404；轮换 forgejo 200/三步 True/`rotated_at` 16:51:21Z/库内同步，轮换 device-root 400+原因；7 个入口 `available` 全 True；[web-console README](2026-11-14/web-console/README.md) §13.3/§13.4/§13.5 同步；v1.70 归档至 [changelog/2026-11.md](changelog/2026-11.md)（窗口 8 条、归档 71 条）；验证：preflight 全绿；未完成：设备上仍用原生 `confirm` 的启停/备份按钮存在同类静默风险（本轮未改）。 |
| 2026-11-15 | v1.77 | **凭据 CSV 入库校验与本机明文清理**：`--vault-sync` 幂等复跑 `console/webdav/forgejo/vaultwarden/vaultwarden-admin: ok`、`device-root: skipped`、`vault_sync: ok`；独立回读 folder 内 **5 条、无重名、`password_match` 全 True**（`device-root` 无明文口令不入库，只留 CSV 备注）；备份覆盖实测：手动触发同一 03:30 管线（`backup-loop` 轮询触发文件 → `haydn-backup.sh`），新 `haydn-backup-20261114T163047Z.tar.gz.enc`（97.8 MB）经 `haydn_crypt.py decrypt` 后确认含 `opt/haydn/secrets/vaultwarden-master.txt`（`secrets/` 共 9 项），三来源（haydn/forgejo/vaultwarden）均上传成功并 `DONE ok`，临时解密文件已删；设备侧主密码文件复核 600 root:root 66 B；删除本机 `inventory/haydn-credentials.csv`（经回收站，`git status` 不含；全盘扫描 Desktop/Downloads/Documents/e:\git_code 无其他副本，**回收站需用户手动清空**）；[web-console README](2026-11-14/web-console/README.md) §13.3 同步；未重启整机、未提交 git；验证：preflight 全绿。 |
| 2026-11-15 | v1.76 | **控制台入口去域名化与文档口径统一**：核查设备 `entries[]` 已无 `qingxuan.bbs0.cc` / `vault.qingxuan.bbs0.cc` 入口（仅 `cert_file` 与 `NODE_EXTRA_CA_CERTS` 含域名，是证书文件路径），主站/控制台/WebDAV/Forgejo 保持站内相对路径（随 origin 解析为 `https://8.137.162.154:60875/...` 或局域网 `http://<lan_ip>:18090/...`），Vaultwarden 固定 `https://8.137.162.154:60177/`；验证 `GET /api/entries` 7 条 `available` 全 True，`{lan_ip}`=192.168.31.50、`{lan_root}`=http://192.168.31.50:18090，与 `/api/lan`（wlan0）及 `/srv/haydn/run/lan-subnet`（192.168.31.0/24）一致；**域名入口口径唯一来源**定为 [frp-public-mapping](2026-11-14/frp-public-mapping/outputs/frp-public-mapping.md) §12.1（公网不可用=备案按 SNI 拦截/明文 HTTP 403 `Server: Beaver`；两条 https 隧道保留作回滚；控制台不展示），[web-console README](2026-11-14/web-console/README.md) §4/§12.1/§12.2/§12.5/§13.1 与 [ADR-0008](adr/0008-public-entry-after-icp-sni-block.md)（R3）改为引用、不再复述计数；未改 frpc/stunnel/证书，未重启整机、未重启 gateway（无配置变更），未提交 git；验证：preflight 全绿。 |
| 2026-11-14 | v1.75 | **Vaultwarden 账号重建与写库链路打通（BL-039）**：按用户确认删除旧用户 `admin@haydn.local` 与库数据、删设备侧失效的 `vaultwarden-initial-account.txt`；临时开注册→新版两步接口（`register/send-verification-email` + `register/finish`，服务端 `PBKDF2(masterKey, 盐=password)`、HKDF 单块 Expand、`encryptedPrivateKey` 用原始 PKCS8 DER）重建专用账号，32 位主密码落 `/opt/haydn/secrets/vaultwarden-master.txt`（600），完成后恢复并回读 `disableUserRegistration=true`；`bw` 升级 2026.10.1（`/opt/haydn/bwnew`，走既有 stunnel `https://127.0.0.1:18445` + `NODE_EXTRA_CA_CERTS`，新 CLI 拒绝 http 且无法绕过），`credentials.vault.enabled=true`，`--vault-sync` 写入 folder `haydn-server` 5 条并逐条回读一致（`device-root` 无明文口令跳过）；验证：WebDAV 轮换 `steps` 三项全 True 且库内同步、停服务轮换 400/`rolled_back:True`、`vault.client=/bin/false` 时 200+`password_present:True`（一次性展示保留）；凭据 CSV 重新导出（一次性令牌下载 200/1208 B/6 行、二次 410、含 32 位新主密码且与本机副本一致），拉到 gitignored `inventory/haydn-credentials.csv`，设备侧 `/srv/haydn/run`、`/tmp`、`/data/local/tmp` 明文副本与本次诊断脚本已删；v1.67 归档至 [changelog/2026-11.md](changelog/2026-11.md)（窗口 8 条、归档 68 条）；[web-console README](2026-11-14/web-console/README.md) §13.3/§13.5 更新；验证：preflight 全文见 backlog BL-039 result；未完成：Vaultwarden 主密码/管理令牌仍不支持服务端轮换、写库失败后的条目自愈需人工 `--vault-sync`。 |
| 2026-11-14 | v1.74 | **控制台服务入口、凭据导出与按钮化轮换（BL-039）**：新增 `console/console_credentials.py`（`credentials.services[]` 为唯一事实来源，CSV 与密码库条目共用）；首页“服务入口”由 `gateway.json` 的 `entries[]` 注入（7 个入口，`{lan_ip}`/`{lan_root}` 服务端解析，模板零地址）；`GET /api/entries`、`POST /api/credentials/token`（CSRF，一次性令牌 120 s）、`GET /api/credentials/download`（用后即失效、600 临时文件即删、审计不记内容）、`POST /api/rotate`（生成→写入→回读→真实协议验证→一次性展示→时间戳，失败按快照回滚；控制台口令热重载不重启）；验证：webdav 207、forgejo API 200、console 新口令 200/旧口令 401、令牌二次访问 410、CSV 6 行已拉至 gitignored `inventory/haydn-credentials.csv`（设备侧已删）；Vaultwarden 写库**阻塞**：已有用户 `admin@haydn.local`，设备侧 24 位主密码实测无法登录（identity 400），按要求未重置/未重注册/未改库数据，`credentials.vault.enabled=false`，`bw` 2025.1.3 已装 `/opt/haydn/bw/bin/bw`；[web-console README](2026-11-14/web-console/README.md) §13 补端到端加密说明；验证：preflight 全绿；未完成：待用户提供主密码后启用写库并回归。 |
| 2026-11-14 | v1.73 | **公网入口选型定稿（BL-038）**：[ADR-0008](adr/0008-public-entry-after-icp-sni-block.md) 由 `proposed` 转 **`accepted`**——用户选定**大陆节点 IP 直连 + 非标端口**（主站/控制台/Git `https://8.137.162.154:60875/`，密码库 `https://8.137.162.154:60177/`，接受证书告警；`ROOT_URL`/`DOMAIN` 仍为域名、客户端需按 IP 重配=未实测）；理由：大陆节点 200 Mbps、零额外成本、IP 直连实测 10/10 返回 200；放弃：域名 443（备案拦截）、域名 + 非标端口（SNI 1/10）、境外节点、Cloudflare Tunnel（需 `bbs0.cc` NS 迁入 CF，**方案未采用**，7844 连通性不再深挖）、Tailscale Funnel（仅 `*.ts.net`、3 端口、带宽不可配）、ICP 备案（暂不启动）；保留原两条 `type="https"` 隧道作 443 回滚，DNS 未改；复议触发点=备案完成 / 自有域名 / IP 或端口被封 / 客户端原生支持成硬需求；[web-console README](2026-11-14/web-console/README.md) §12.1 入口表改为 IP 主入口并写明证书告警处理（局域网 `:18090` 仍定位"同网段省流"），[frp-public-mapping](2026-11-14/frp-public-mapping/outputs/frp-public-mapping.md) §12 标题/§12.2/§12.4/§12.6 同步；v1.65 归档至 [changelog/2026-11.md](changelog/2026-11.md)（窗口 8 条、归档 66 条）；验证：preflight 全绿；未完成：IP 入口下 Vaultwarden 手机端/浏览器扩展与 Git 客户端兼容性未实测。 |
| 2026-11-14 | v1.72 | **Forgejo 入备份 + RST 归因更正 + TCP 非标端口预案**：①新增 [backup-forgejo.sh](2026-11-14/web-console/deploy/backup-forgejo.sh)（SQLite backup API + `repositories/` + `data/` 子目录 + `app.ini`，输出 `forgejo-backup-<UTC>.tar.gz`），[haydn-backup.sh](2026-11-14/web-console/deploy/haydn-backup.sh) 扩为三来源（haydn/forgejo/vaultwarden）各自加密→解密自检→上传→按来源保留 7 份；②更正 [frp-public-mapping](2026-11-14/frp-public-mapping/outputs/frp-public-mapping.md) §11.4：公网 443 已出现阿里云备案拦截（403 `Server: Beaver`、`Non-compliance ICP Filing`），原「curl RST 已定位为 ClientHello 特征阻断」降级为**推断**且与拦截的关系**未证实**；新增 §12 TCP 非标端口**已实施**（`HJtApRGYMHvn`:60875、`0mP2rpGpthc0`:60177；四条代理均 `start proxy success`；证书 DigiCert `8C:95…08` / 自签 `2E:7B…76`；结论：拦截按 **SNI 域名**而非端口——域名 SNI 1/10 通、IP SNI 10/10、中性 SNI 5/5，故非标端口不能可靠绕过）；验证：三来源手工全链路 `RC=0`、forgejo 密文解密恢复 `integrity ok / users 1 / journal_mode wal`、源权限未变、`frpc verify` 接受 tcp 段与 `useEncryption/useCompression`；frpc.toml 备份于 `/data/server/backups/frpc.toml.20261114T142644Z`；v1.64 归档至 [changelog/2026-11.md](changelog/2026-11.md)（窗口 8 条）；未完成：`/git/` 公网结论仍受 SNI 拦截阻塞（本地与 IP 直连已 200）。 |

## 4. 归档索引

| 月份 | 条目 | 文件 |
|---|---|---|
| 2026-11 | 72 条（v1.0–v1.71） | [changelog/2026-11.md](changelog/2026-11.md) |
