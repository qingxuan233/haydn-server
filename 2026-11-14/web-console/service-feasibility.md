# 接入 AList / Uptime Kuma / Netdata 可行性分析（只读评估）

> 范围：**本轮不安装、不改任何服务与配置**，只做只读采集与方案。
> 设备：OnePlus Ace Pro（CASE-003，Ubuntu 24.04 chroot + Root，supervisord 托管，**无 systemd**）。
> 约束：公网仅 IP + 两个非标端口，**不新增暴露面**；ARM64；不打印任何凭据；文档改动跑 `preflight`。
> 事实分级：**已核验**＝有命令输出/文件行号；**推断**＝有依据未实测；**待验证**＝未知项。

## 1. 资源账

### 1.1 设备当前水位（已核验，2026-11-15 现场采集）

| 项 | 实测值 | 采集方式 |
|---|---|---|
| 总内存 | 15,583,572 kB ≈ 14.86 GiB | `cat /proc/meminfo` |
| 可用内存 | 10,846,580 kB ≈ 10.34 GiB（69.6%） | `/proc/meminfo` MemAvailable |
| 空闲内存 | 782,792 kB ≈ 764 MiB | `MemFree`（大量页在 cache/buff，不作为判据） |
| CPU 核数 | 7 | `nproc` |
| 负载 | 3.17 / 3.15 / 3.18 | `cat /proc/loadavg`（≈ 7 核的 45%，含 Android 宿主进程） |
| 存储 | 224 G 总 / 16 G 用 / **208 G 可用**（8%） | `df -h /data`（同一 `dm-70`） |
| Node | v24.16.0（`/opt/node24/bin/node`） | `node --version` |

### 1.2 现有 13 个服务实际 RSS（已核验）

| 服务 | RSS | 服务 | RSS |
|---|---|---|---|
| forgejo | 160,268 kB | node_exporter | 17,028 kB |
| rclone（webdav） | 65,216 kB | stunnel4（haydn-tls） | 11,440 kB |
| vaultwarden | 35,216 kB | stunnel4（haydn-vault-tls） | 9,648 kB |
| tailscaled | 33,744 kB | sshd | 4,996 kB |
| gateway.py | 27,416 kB | haydn-heartbeat | 3,132 kB |
| frpc | 20,804 kB | cron | 2,080 kB |
| python http.server（静态站） | 18,740 kB | **合计** | **≈ 391 MB** |

> RSS 求和会重复计算共享页（libc 等），真实增量略低于此值；作为上限估计足够。

### 1.3 三者内存/磁盘估算

| 服务 | 常驻内存 | 峰值 | 依据与分级 |
|---|---|---|---|
| AList（Go 单二进制） | 60–90 MB | 150–250 MB（大文件经本机代理中转时的缓冲） | **推断**：Go 服务 + SQLite 的常见量级；官方无公布数字；装后实测校准 |
| Uptime Kuma 2.x（Node） | 150–250 MB | 300 MB+（历史数据整理/`VACUUM`） | **推断**：官方站点基线是"最低 1 GB / 建议 2 GB"（含 Node+SQLite 的保守整机建议，非单进程），社区实测单实例多在 150–250 MB；以上限计 |
| Netdata（静态构建） | 100–200 MB（官方 RAM 文档口径）；本机生产型到 250–350 MB | 350 MB | **已核验（官方文档）**+ **推断**（本机采集项多，按 250–350 MB 计） |
| 磁盘 | Netdata 默认 **约 4 GiB**（3 tier × 1 GiB + SQLite 元数据，官方 Disk & Retention 文档）；AList 二进制 ~40 MB + 数据；Kuma 约 300–500 MB（含 `node_modules`） | | 208 G 可用下占比 <3% |

**"装完还剩多少"**：MemAvailable 10.34 GiB − (0.09 + 0.25 + 0.35 GiB) ≈ **9.6–9.9 GiB 可用**；即使三者峰值同时叠加（≈1.1 GiB），仍剩 ≈9.2 GiB。相对当前 69.6% 的可用率，三者合计约占总量 6%–7%，**内存不构成瓶颈**。
**但**：Android 侧 LMK 的内存压力判据不等于 MemAvailable 10% 阈值，真正的风险是"突发峰值把 Forgejo 等大服务挤出"（见 §6）。

## 2. ARM64 构建与维护状态

| 服务 | 最新版本（本轮核验） | 发布方式 | ARM64 | 维护状态 |
|---|---|---|---|---|
| AList | **v3.66.0**（2026-10-21） | GitHub Releases 按平台 tarball（`android-arm64` 已核实；`linux-arm64` 为同批标准产物，本页渲染未取到文件名 → 待验证） | 单二进制静态编译，无运行时依赖 | 活跃；社区另有分叉 **OpenList v4.2.9**（2026-10-24），两者均可用 |
| Uptime Kuma | **2.5.11**（2026-11-12，含上游依赖 RCE 安全修复） | GitHub Releases 仅 `dist.tar.gz`（前端产物）+ `npm install` 构建后端 | **无官方 arm64 二进制**，靠 Node 跑 JS，原生模块（better-sqlite3）需本机编译或有 arm64 预编译 | 活跃（3 天前发版） |
| Netdata | 2.12.x（Arch Linux ARM 打包 2.12.1；官方 latest 未直取 → 推断） | 官方**静态构建**（kickstart `--static-only`），平台支持页明列 **AArch64** | 有（官方静态构建覆盖 arm64） | 活跃 |

**Node 兼容性（关键）**：Kuma v2 最低 **Node ≥ 20.4**（官方 v1→v2 迁移文档明确弃用 14/16/18）。设备 `/opt/node24` 是 v24.16.0，**满足下限**，但官方 CI 目标为 20/22，Node 24 属"高于已验证范围" → **待验证**。
建议：**给 Kuma 独立运行时**（`/opt/node22` 解压官方 linux-arm64 tarball 或复用 node24 但独立 `node_modules`），**绝不动 `/opt/node24`**——夸克备份 CLI 依赖它（[haydn-backup.sh](deploy/haydn-backup.sh) 用 `node "$QUARK_CLI"`）。
另一处真实门槛：`better-sqlite3` 需要预编译产物或本机 `python3/make/g++`；chroot 内工具链是否齐备**待验证**，这是三者中唯一有"装不上"风险的一项。

## 3. 汉化结论

| 服务 | 是否有中文 | 切换路径 | 是否需改配置默认中文 |
|---|---|---|---|
| AList | **有 i18n**，含简体中文；中文项目，Web 端首次进入通常即中文 | 页面内语言选择（设置/右上角） | 不需要；语言存浏览器侧，无服务端默认语言项（**推断**，装后核验） |
| Uptime Kuma | **有 i18n**，20+ 语言含简体中文 | 设置页 → 语言/外观 | **没有**默认语言环境变量（环境变量表无此项，**推断**）；每个浏览器需手选一次 |
| Netdata | **无 i18n**，Dashboard 全英文 | — | 无。只能做"中文入口页/中文说明"：控制台 `entries[]` 的 `note` 写中文，或网关给 `/netdata` 根路径加一页中文说明（做法同 `/dav` 的 `browser_ui`，但会遮住 dashboard，不推荐） |

## 4. 控制台集成方案

### 4.1 网关现状（已核验）

- 路由能力：`path`/`upstream`（仅 loopback）/`strip_prefix`/`preserve_host`/`websocket`/`auth`（`none|session|basic`），见 [gateway.py](console/gateway.py) 与 [README](README.md) §3。
- **CSP 只作用于网关自己的页面**（[gateway.py](console/gateway.py) L189–207 的 `_html`）；代理响应逐条复制上游头、**不注入 CSP**（同文件 L1014–1020）→ **CSP 不会挡三者的前端**，但也意味着代理页面没有 CSP 保护。
- 网关**不重写 `Location`**（代理段未见 Location 处理），上游若发绝对路径 302 会跳出前缀 → 这是 subpath 落地的首要验证点。
- 转发上游前会**剥离 `haydn_session` cookie**（同文件 L967–976），避免会话串到上游。
- 已监听端口：18080 网关、18081 静态站、18082 rclone、18083 forgejo、18084 vaultwarden、18090 局域网控制台、9100 node_exporter、18443/18445 stunnel、22 sshd、tailscaled 1055/33118。**18085–18089 与 19999 空闲**（已核验 `ss -ltnp`）。

### 4.2 逐个判定

| 服务 | subpath 支持 | 前端是否绝对路径 | 建议路径 | 结论 |
|---|---|---|---|---|
| AList | **支持**：官方配置项 `site_url` 明确用于"反向代理至二级目录" | 待验证（`site_url` 影响后端生成的链接；前端资源是否相对路径需装后查 `index.html`） | `/alist`，`strip_prefix: true`，`auth: session` | **可挂**；需实测登录 302 与静态资源 |
| Uptime Kuma | **不支持**：官方 wiki 明确"不支持子目录，须独立域名/子域"；社区一致 | — | — | **不能挂 `/kuma`**，见 4.3 替代 |
| Netdata | **支持**：官方 nginx/apache/haproxy/caddy 均给出 subpath 示例（前缀剥离 + `proxy_redirect off`） | 官方示例即按"剥离前缀"工作 → dashboard 侧为相对路径（**推断**，需实测） | `/netdata`，`strip_prefix: true`，上游 `127.0.0.1:19999` | **可挂**；须先把 `[web] bind to` 改为 `127.0.0.1` |

WebSocket：网关 `websocket: true` 走原始 TCP 双向隧道，Kuma（socket.io）必需；AList / Netdata 主界面不依赖（**推断**）。

### 4.3 Kuma 的替代（不新增公网暴露面）

1. **独立 loopback 端口 + Tailscale 访问**：绑 `127.0.0.1:18086`，经 tailnet 访问（tailscaled 为 `--tun=userspace-networking`，入站转发到 loopback 是否可用**待验证**）。公网 60875 与 60177 两条既有链路零改动。
2. **局域网直连端口**：仿 `18090` 模式（`lan-fw-loop.sh` 按探测网段幂等放行 + 网关侧二次网段校验），但 Kuma 自身不认网段 → 只靠 iptables，鉴权全靠 Kuma 口令。
3. **不挂 UI，只吃它的探测**：仅把 Kuma 当定时探针，结果通过通知渠道发；控制台不加入口。

> 不新增暴露面的理由：三者一律只绑 loopback，公网只复用既有 `frpc → stunnel(18443) → gateway(18080)` 链路；新路径是"同一入口下的新前缀"，不新开端口、不改 frpc/stunnel/证书。Kuma 走 1/2 时只在内网或 tailnet 可达。

### 4.4 入口表与鉴权复用

- 入口表：`gateway.json` 的 `entries[]` 追加 `{name, url, note}`，`url` 用占位符 `{public_host}`/`{lan_ip}`/`{lan_port}`，由控制台按当前入口替换（[README](README.md) §13.1）；改后 `supervisorctl restart haydn-console-gateway`（秒级，现存连接会断一次）。
- 鉴权：新路由统一 `"auth": "session"`，直接复用控制台会话与登录限流；AList 自身的 admin 口令仍然必须设置（双闸），且**不要**启用 AList 自带 WebDAV 端点（避免绕过网关再出现一条数据通路）。上游自身无鉴权的 Netdata 依赖网关 session 即可，但需 `bind 127.0.0.1` 兜底。

## 5. 数据与运维

| 项 | AList | Uptime Kuma | Netdata |
|---|---|---|---|
| 持久化目录 | `/opt/alist/data`（配置 + SQLite + 缩略图） | `/opt/uptime-kuma/data`（`kuma.db`） | `/opt/netdata/etc/netdata`（配置）；`/opt/netdata/var/lib/netdata`（dbengine，可再生） |
| 是否进备份 | **应进**（含网盘凭据，但落在既有加密链路内）；当前 `device-make-backup.sh` 快照清单**不含** `/opt/alist` → 需显式加一行 | **应进**；SQLite 必须一致性快照（复用 `backup-forgejo.sh` 的 sqlite backup 思路） | **只备配置**，dbengine 排除（4 GiB 可再生，备了浪费配额） |
| 日志 | `/srv/haydn/logs/alist.log`（supervisor stdout） | `/srv/haydn/logs/uptime-kuma.log` | `/srv/haydn/logs/netdata.log`；另在 `netdata.conf` 关 access log |
| 轮转 | 复用 `/etc/logrotate.d/haydn`（`*.log` 周轮转 + 10M） | 同左 | 同左 |
| supervisord | `haydn-alist.conf`，`autorestart=true`、`startretries=3` | `haydn-uptime-kuma.conf`，`environment=NODE_ENV=production`、独立 node 路径 | `haydn-netdata.conf`，`stopasgroup/killasgroup=true`（会起子进程插件） |
| 健康检查 | 加 `curl -fsS 127.0.0.1:18085/api/public/settings` 探针 | 加 `curl -fsS 127.0.0.1:18086/` 探针 | 加 `curl -fsS 127.0.0.1:19999/api/v1/info` 探针 |
| 无 systemd 自恢复 | supervisor `autorestart` 为主；`haydn-healthcheck.sh` 对 FATAL/BACKOFF/EXITED/非人工 STOPPED 自动 `start` 并写 `RECOVER` | 同左 | 同左 |

> 健康检查现状（已核验，[haydn-healthcheck.sh](deploy/haydn-healthcheck.sh)）：cron 每 5 分钟；判据=supervisor 状态 + 18080/9100/sshd 探针 + 磁盘 ≥90% + MemAvailable <10%。**只对"进程不在"有效**，"进程在但卡死"不覆盖 → 三者接入时应同时考虑补一条"HTTP 探针失败则 restart"的规则（本轮不改）。

## 6. 稳定性风险与回滚

| 风险 | 影响面 | 缓解 | 回滚 |
|---|---|---|---|
| 内存挤压（尤其 Netdata 首个 5 分钟建库、Kuma 首次 `VACUUM`） | Forgejo/网关可能被 Android LMK 杀掉 | 一次只上一个；观察 24h；Netdata 把 tier 降到 1 档（`dbengine tier 1/2 = 0`） | 停服务 + 删 conf |
| **Node 运行时冲突**（Kuma） | 误动 `/opt/node24` 会让夸克备份上传失败 | 独立运行时目录，`/opt/node24` 只读不改 | 删除独立目录即恢复 |
| 原生模块编译失败（better-sqlite3） | Kuma 装不上 | 先用 `npm ci --omit=dev` 试预编译；失败再看工具链 | 放弃 Kuma，不影响其余 |
| 端口/路径冲突 | 18085–18087、19999 已核验空闲 | 固定用这三个端口，写进 conf | 换端口 |
| **AList 单 `site_url` 无法同时满足公网与局域网两种入口** | 局域网访问时部分链接跳到公网地址 | 以公网地址为 `site_url`；局域网只读浏览可接受；或局域网走独立端口直连 | 改回 `enabled:false` |
| 网关不改写 `Location` | 上游 302 到 `/xxx` 会跳出 `/alist`、`/netdata` 前缀 | 上线前实测登录跳转与资源加载；必要时给网关加"前缀补写"（属代码变更，需单独立项） | 路由 `enabled:false` |
| 网关重启与现有服务互相影响 | restart 时全部连接断一次（WebDAV 同步/控制台会话） | 放在低峰；一次只改一组路由 | 还原 `gateway.json` 备份 + restart |
| **AList 安全面** | 公网可达 + 网盘凭据；项目历史有 CVE，2025 年发生社区分叉（供应链关注点） | 强口令 + 仅网关 session 可达 + 关闭自带 WebDAV + 校验发布 sha256；可优先评估 OpenList | 停服并 `enabled:false` |
| Netdata 默认 `0.0.0.0:19999` + 云连接/匿名统计 | 多一条监听面与出站 | 装后立即改 `bind to = 127.0.0.1`，关闭 cloud/telemetry | 恢复默认或卸载 |
| Netdata `apps.plugin` 在 Android 容器内采集异常 | 指标缺失或告警噪音 | 先禁 `apps` 组，只留 system/cgroups | 改回默认 |

统一回滚骨架：`supervisorctl stop <svc>` → 删 `/etc/supervisor/conf.d/haydn-<svc>.conf` → `reread`+`update` → `gateway.json` 对应路由 `enabled:false` 并重启网关 → 删 `entries[]` 该行。数据目录与 `/data/server/backups/<svc>-<ts>/` 保留不动。

## 7. 结论与建议

| 服务 | 结论 | 理由 |
|---|---|---|
| **Netdata** | **建议上（第一步）** | 只读、无业务耦合、官方支持 subpath 与 arm64 静态构建、回滚成本最低；能立刻为后两个提供内存/CPU 观测基线。已知代价：内存 250–350 MB、磁盘 ~4 GiB、全英文 |
| **AList** | **建议上（第二步），但先做单机验证** | 唯一带来新能力（多网盘聚合 + 统一 WebDAV）；风险集中在 subpath 跳转、`site_url` 双入口、安全加固三处；这三点都能在不上公网的情况下先行验证 |
| **Uptime Kuma** | **本轮不建议上** | 硬性不支持 subdirectory → 挂不进控制台；Node 原生模块构建是三者中唯一"可能装不上"的项；能力上与现有 `haydn-healthcheck.sh` + node_exporter + soak 高度重叠。若确有外部可用性探测需求，按 §4.3 方案 1 以内网/tailnet 独立端口试运行两周再定 |

**建议顺序**：Netdata（观测基线）→ 观察 24h → AList（单机验证 subpath 与登录跳转，再开公网路由）→ 视结果为 Kuma 立项。
每一步都遵循：改前备份 → 只加一个服务 → 观察窗 → 记录到 `backlog`/`CHANGELOG` → 失败按 §6 骨架回滚。

**待验证清单（实施前补齐）**：

1. AList `linux-arm64` 资产名与前端的资源是否相对路径；
2. Netdata dashboard 在本网关下（无 `proxy_redirect`、无 HTML 改写）能否正常加载 `/netdata/api/v1/*`；
3. Kuma 在 Node 24 下 `better-sqlite3` 是否有可用预编译，或 chroot 内是否有编译工具链；
4. Kuma 默认语言是否只能逐浏览器手选；
5. tailscaled userspace 模式的入站是否转发到 loopback（决定 §4.3 方案 1 是否成立）。
