# Haydn（CASE-003 / 一加 Ace Pro）FRP 公网映射规划（HTTPS-only）

| 项 | 值 |
|---|---|
| 设备 | CASE-003，PGP110，aarch64，chroot = Ubuntu 24.04.5 LTS（`/data/server/rootfs`） |
| 内网 | wlan0 192.168.31.50/24；tailnet 节点 `haydn-pgp110`（tailscaled userspace 模式） |
| FRP 服务商 | 88frp，公网 47.97.70.99，二级域名 `qingxuan.bbs0.cc` |
| 硬约束 | 公网仅 HTTPS，不规划 80/HTTP，不以「80 跳 443」为方案 |
| 本轮性质 | **只读勘察 + 规划**；未改设备配置、未重启、未写入任何真实凭据 |
| 编制时间 | 2026-11-14（设备时间 UTC 06:43 ≈ 本地 14:43） |

事实分级：**[已核验]** = 本次命令输出/文档原文；**[推断]** = 依据给出但未直接验证；**[待核对]** = 需登录 88frp 面板或后续实测确认。

---

## 0. 结论摘要

1. 设备上真正值得公网的服务只有一个：chroot 内 `python3 -m http.server 18080`（静态只读自检页）。SSH、node-exporter、tailscaled SOCKS5 一律不直接公网暴露。[已核验]
2. 公网 HTTPS 建议采用 **服务商边缘 TLS 终结** 模型：`type = "http"` 隧道回源到 `127.0.0.1:18080`，证书在 88frp 边缘，设备侧不建 TLS。依据：443 是 SNI 选路的边缘代理（未绑定域名直接 `unrecognized_name`），80 上是 frps 的 vhost 404 页。[已核验：见 §2.2]
   > **2026-11-14 实施后更正**：本模型被实测推翻——该节点 `type = "https"` 是 **SNI 透传**，TLS 在设备侧终结；`type = "http"` 因 80/8080 被 ICP 拦截不可用。最终架构见本文 §11。
3. 预留项（`/metrics`、`/api`、`/dav`、TLS 透传）**在面板上一次创建、在 frpc 配置中默认注释不启用**；启用前提见 §4.2。
4. 安全底线：SSH 与监控走 tailnet；frpc 仅出站，设备侧不新增任何入站监听；token 用环境变量注入，不落配置。[已核验：INPUT 策略 DROP、仅放行 lo/established/DHCP]
5. 88frp 的技术细节（serverPort、token、隧道类型枚举、是否支持 `locations`、备案要求、证书归属）**公开渠道取不到**——其帮助页需登录（浏览器实测被 SPA 路由守卫弹回首页），全部列入 §7 待核对，并给出面板内逐步核对方法。

---

## 1. 端口清单（设备 + chroot，实测于 2026-11-14）

数据来源：`adb shell su -c 'ss -tulnp'`、`iptables -S`、`/proc/<pid>/root`、`/etc/supervisor/conf.d/haydn.conf`。[已核验]

| 端口 | 协议 | 绑定地址 | 服务（PID / 托管方式） | 需公网？ | 理由 |
|---|---|---|---|---|---|
| 22 | TCP | 127.0.0.1 | sshd（7489，supervisor `haydn-sshd`，密钥登录、禁密码） | 否 | 管理面走 tailnet；公网 SSH 是最高价值攻击面 |
| 18080 | TCP | 127.0.0.1 | python3 http.server（7484，supervisor `haydn-local-http`，root=/var/www/haydn） | **是（唯一）** | 唯一对外交付内容；静态只读自检页 |
| 9100 | TCP | 127.0.0.1 | prometheus-node-exporter（7485，supervisor `haydn-node-exporter`） | 否 | 指标泄露主机画像；tailnet/本机抓取足够 |
| 1055 | TCP | 127.0.0.1 | tailscaled SOCKS5（7491） | **绝对否** | 公网暴露等于开放代理，会被滥用并牵连账号 |
| 61245 | TCP | 127.0.0.1（lo） | tailscaled 内部 | 否 | 进程内部通信 |
| 46550 / 48127 | UDP | 0.0.0.0 / [::] | tailscaled（NAT 穿透出站） | 否 | 出站行为；frpc 也不需要 UDP 入站 |
| 10150 / 10151 | TCP+UDP | *（0.0.0.0 / 192.168.31.50） | eytap.accessory（6185，OPPO 系统组件） | 否 | 非自建 OEM 组件；入站已被 iptables 默认 DROP |
| 10152 / 46888 / 47888 | TCP | * | eytap.accessory（6185） | 否 | 同上，非自建 |
| 20380 | UDP | * | eytap.accessory（6185） | 否 | 同上，非自建 |
| 12121 | TCP | 127.0.0.1 | t.local.service（18699，OEM 本地服务） | 否 | 非自建 |

分类归并：

- **必须公网**：18080（经 FRP，HTTPS-only）。
- **经网关聚合后公网**：暂无。若未来需要对外提供多路径（`/api`、`/dav`），仍复用同一域名由 frps 按 path 聚合，**不新增端口**。
- **仅内网或 tailnet**：22（SSH）、9100（指标）、1055（SOCKS5）。
- **不暴露**：全部 OEM 端口（10150/10151/10152/20380/46888/47888/12121）与 tailscaled 内部端口。

防火墙事实（只读）：`iptables -S INPUT` → `-P INPUT DROP`，仅放行 `lo`、`RELATED,ESTABLISHED`、UDP/68（DHCP），另有 OEM BPF accept 规则；`OUTPUT` 默认 ACCEPT（除 uid 10343 REJECT）。因此 **LAN 入站当前同样被拦**，frpc 的出站连接不受影响。[已核验]

chroot 服务形态（决定 frpc 怎么接）：`/data/server/bin/start-supervisord.sh` → `chroot-enter.sh /usr/bin/supervisord -c /etc/supervisor/supervisord.conf`，程序定义在 `/etc/supervisor/conf.d/haydn.conf`，日志 `/var/log/haydn/*.log`（5MB×2 轮转）。[已核验]

---

## 2. 88frp 能力核对

### 2.1 公开文档可获取性

| 来源 | 结果 |
|---|---|
| `https://88frp.com/client/subscriptions` | 只返回营销页（套餐/节点/资质），无技术参数。[已核验] |
| `https://88frp.com/client/help-support/域名解析说明` | 直接抓取与真实浏览器均为 SPA；未登录被路由守卫弹回首页，页面正文提示「文档加载失败」。[已核验] |
| 站点 API 猜测（`/api/help…`、`/api/docs…`） | 均 404，非公开接口。[已核验] |

结论：**服务商侧的隧道类型枚举、远程端口分配规则、备案口径、证书归属，本轮无法取证**，一律 [待核对]，核对方式见 §7。

### 2.2 服务端边缘行为实测（可佐证 TLS 终结位置）

| 探测 | 结果 | 解读 |
|---|---|---|
| `curl -I --resolve qingxuan.bbs0.cc:80:47.97.70.99 http://qingxuan.bbs0.cc/` | `HTTP/1.1 404`，响应体为 frp 官方 404 页（"The server is powered by frp"） | 80 上是 frps 的 vhostHTTP；说明 HTTP 能力存在，但按用户约束**不使用**。[已核验] |
| TCP `47.97.70.99:443` | TCP 可连 | 443 有监听。[已核验] |
| `openssl s_client -connect 47.97.70.99:443 -servername qingxuan.bbs0.cc -tls1_3` | `alert number 112 (unrecognized_name)` | 边缘按 SNI 选证书/选后端，**未在面板绑定该域名的 SNI 直接拒绝** → TLS 在服务商侧终结，而非设备侧回源。[已核验] |
| 同上，SNI 换 `bbs0.cc`、随机子域 | 同样 `unrecognized_name` | 边缘无默认站点、无泛域名兜底；必须先建隧道/绑定域名才有站点。[已核验] |
| TCP `47.97.70.99:7000` | 连接失败 | 7000 **不是**该节点的 frps bindPort（或仅对已登记客户端放行）→ `serverPort` 必须从面板取。[已核验] |
| DNS `qingxuan.bbs0.cc A` | 47.97.70.99 | 解析已生效。[已核验] |
| DNS `bbs0.cc NS` | dns9/dns10.hichina.com（阿里云） | 解析由服务商在阿里云托管。[已核验] |
| DNS 随机子域 `zz-probe-….bbs0.cc` | 不解析 | **无泛解析**：新增子域名必须在面板/解析管理里加记录。[已核验] |

### 2.3 待核对项（服务商能力）

| # | 待核对内容 | 为什么重要 | 核对方式 |
|---|---|---|---|
| C1 | 节点 `serverAddr` / `serverPort` / `auth.token` | 没有这三项 frpc 连不上；实测 7000 不可达 | 面板 → 节点信息/我的隧道 → 客户端配置 |
| C2 | 隧道类型枚举：是否提供 `http`（vhost）与 `https`（TLS 透传）两种 | 决定 TLS 终结模型 A/B | 面板「创建隧道」→ 协议类型下拉框截图 |
| C3 | HTTPS 证书：通配符 `*.bbs0.cc` 还是按域名签发；是否自动续期 | 决定是否需要在设备侧管证书 | 建隧道后 `openssl s_client … \| openssl x509 -noout -issuer -dates -ext subjectAltName` |
| C4 | 是否支持同域名多隧道按 path（`locations`）分流 | 预留 `/metrics`、`/api`、`/dav` 是否要另买子域 | 面板建第二条同域名隧道是否被拒；或问客服 |
| C5 | 国内节点对域名备案/实名的要求 | 未备案可能直接被封 80/443 | 面板创建时的提示；`bbs0.cc` 备案主体可查工信部备案系统 |
| C6 | 远程端口分配规则（TCP/UDP 才需要） | 本方案当前不申请 TCP/UDP，仅影响未来 SSH 兜底 | 面板创建 TCP 隧道页的「远程端口」说明 |
| C7 | 套餐隧道条数/流量上限 | 预留隧道会占用配额（参考价目：2 元=5 条/288G，5 元=10 条/488G，仅作参考） | 面板「我的套餐」 |
| C8 | 服务端是否强制/支持 `transport.tls`（frp 传输层加密）与 frpc 版本要求 | 决定 `auth.token` 之外的第二层保护 | 面板帮助「客户端版本」；frpc 启动日志 |

---

## 3. TLS 终结模型对比与选型

| 模型 | frpc 类型 | 证书位置 | 明文段 | 前提 | 结论 |
|---|---|---|---|---|---|
| **A. 服务商边缘终结（选型）** | `http`（vhost） | 88frp 边缘（`*.bbs0.cc` 或按域名） | ①浏览器→边缘：HTTPS；②边缘→frps→frpc：frp 协议（可再套 `transport.tls`）；③frpc→127.0.0.1:18080：明文 HTTP，**仅 loopback** | 面板把 `qingxuan.bbs0.cc` 绑定到一个 http 隧道 | **采用**。设备零证书负担，续期由服务商负责；明文段只在设备内部回环 |
| B. 端到端透传 | `https` | 设备侧自建（chroot 内 nginx/caddy） | 仅 frpc→本地 TLS 服务，整链路加密到设备 | 需设备侧有效证书；ACME 需 DNS-01（阿里云 DNS API，意味着把 AK 放设备上，**不建议**）或 90 天人工续期；若服务商 `https` 隧道按 SNI 透传且不校验 | 仅在 A 不可行（如需 mTLS、需端到端加密）时启用 |

选型依据：443 的 `unrecognized_name` 表明边缘已有 SNI 路由与证书管理 [已核验]；A 模型下「服务商证书归属」仍须 C3 核实——若实测 `issuer` 为自签，则说明其证书不可信，回退 B 或换模型。

plaintext 可接受性说明（模型 A）：
- 段③只在设备内 `lo`，设备是单用户 root、无其他租户进程，无旁路窃听者；
- 段②由 frp token 认证；建议同时开 `transport.tls.enable = true`（C8），使 47.97.70.99 与设备之间也不裸奔；
- 因此「本地 18080 是明文」不构成公网链路上的明文。

---

## 4. 映射表

### 4.1 启用项（本轮唯一要生效的映射）

| ID | 名称 | 类型 | 本地 | 公网入口 | TLS 终结点 / 证书来源 | 鉴权与访问控制 | 需要暴露的理由 |
|---|---|---|---|---|---|---|---|
| M1 | `haydn-web` | `http` | 127.0.0.1:18080 | `https://qingxuan.bbs0.cc/` | 88frp 边缘 / 服务商证书（C3 待核对） | 无（静态只读页，无敏感数据）；如后续放文件则加 `httpUser`/`httpPassword` | 唯一需要外部访问的自检/交付页 |

### 4.2 预留项（面板先建、frpc 默认注释；每项写明启用前提）

| ID | 名称 | 类型 | 本地 | 公网入口 | TLS 终结点 | 启用前提（全部满足才启用） |
|---|---|---|---|---|---|---|
| R1 | `haydn-metrics` | `http` + `locations = ["/metrics"]` | 127.0.0.1:9100 | `https://qingxuan.bbs0.cc/metrics` | 88frp 边缘 | ①C4 支持同域 path 分流；②加 `httpUser`/`httpPassword`；③确认 node-exporter 指标不含敏感信息（主机名/容器名可接受） |
| R2 | `haydn-api` | `http` + `locations = ["/api"]` | 127.0.0.1:18081 | `https://qingxuan.bbs0.cc/api` | 88frp 边缘 | ①本地 18081 服务上线且实现自身鉴权（Bearer/mTLS）；②C4 支持；③有速率限制 |
| R3 | `haydn-dav` | `http` + `locations = ["/dav"]` | 127.0.0.1:18082 | `https://qingxuan.bbs0.cc/dav` | 88frp 边缘 | ①WebDAV 服务部署（如 rclone serve webdav，chroot 内已有 rclone）；②强制认证 + 只读或白名单路径；③C4 支持 |
| R4 | `haydn-tls-passthrough` | `https`（透传） | 127.0.0.1:18443 | 独立子域（需新解析记录） | **设备侧证书** | ①模型 A 被证伪（证书自签/不可信）或需要端到端加密；②C2 确认支持 `https` 类型；③证书方案定稿（见 §5.3） |
| R5 | `tcp-ssh-fallback` | `tcp`（远程端口由面板分配） | 127.0.0.1:22 | `47.97.70.99:<远程端口>` | 无（裸 TCP） | **默认永不启用**：仅当 tailnet 完全不可用且需紧急运维时临时开，用完立即删；启用前须改为仅密钥 + `AllowUsers` + fail2ban 类限制 |

不规划项（明确写死）：80/HTTP 映射、HTTP→HTTPS 跳转、UDP 映射、tailscaled SOCKS5(1055)、node-exporter 裸端口、OEM 端口。

配额提示：若套餐只有 5 条隧道，M1+R1+R2+R3 = 4 条已够，R4/R5 不建；若 10 条则余量充足。请先看 C7 再决定是否真的「一次性全建」。

---

## 5. 安全底线

### 5.1 SSH（22）
- 现状：仅 `127.0.0.1:22`，密钥登录、密码禁用。[已核验：supervisor 定义 + 监听地址]
- 公网方案：**不映射**。通过 tailnet（userspace 模式下 tailscaled 把入站转发到本机对应端口）或 `tailscale ssh` 访问。
- 替代方案：若确需非 tailnet 客户端，用模型 A 的路径分流到本地带认证的 Web SSH 网关（不推荐），或 R5 临时 TCP 且用完即删。

### 5.2 监控指标（9100）
- 不裸暴露。首选 tailnet 内 Prometheus 抓取；次选 R1（同域 `/metrics` + BasicAuth）。
- 禁止：把 9100 直接 `type=tcp` 映射到公网。

### 5.3 备份上传通道
- 现状：Quark 备份是**出站**（rclone/cron），不需要任何入站映射。[已核验：`backup-loop.sh` 存在；本轮未改]
- 因此公网映射不给备份留任何端口；如未来需要「外部推备份进来」，用 R3 WebDAV + 认证，或干脆走 tailnet。

### 5.4 凭据卫生
- `auth.token` 只经环境变量注入（`/etc/frp/frpc.env`，`chmod 600`，不入仓库、不进日志）；配置里用 `{{ .Envs.FRP_TOKEN }}`。
- 若服务商证书走 B 模型：私钥权限 600、目录 700；DNS API AK 不落设备（改用人工 DNS-01 或换服务商）。
- 文档/聊天中一律占位符；本文件不含真实 token、密码、私钥、完整序列号。

### 5.5 最小暴露复核
- 设备侧不新增任何入站监听（frpc 只发起出站）；`iptables` 保持现状，不因 FRP 放行任何入站端口。[设计约束]
- 公网只出现 1 个域名 + 1 个 HTTPS 入口，信息面最小。

---

## 6. 面板一次性创建清单

逐项字段与可直接照填的取值见 [panel-creation-checklist.md](panel-creation-checklist.md)。要点：4 条隧道全部为 `http` 类型、本地 IP 一律 `127.0.0.1`、域名一律 `qingxuan.bbs0.cc`（除路径不同），**不创建任何 80 端口/TCP/UDP 条目**。

---

## 7. 88frp 待核对项的核对路径（给用户照做）

1. 登录面板 → 「节点/我的隧道」→ 记录 `serverAddr`、`serverPort`、`token`（C1）；对照本文件 §2.2：7000 已实测不可达，不要照抄默认值。
2. 「创建隧道」→ 协议类型下拉框截图（C2）；确认是否只有 HTTP/HTTPS/TCP/UDP、是否有「子域名」输入框。
3. 建好 M1 后执行：
   ```
   curl -sSI https://qingxuan.bbs0.cc/
   openssl s_client -connect qingxuan.bbs0.cc:443 -servername qingxuan.bbs0.cc < /dev/null \
     | openssl x509 -noout -subject -issuer -dates -ext subjectAltName
   ```
   期望：200；`issuer` 为公共 CA（Let's Encrypt/ZeroSSL/阿里云等）且 SAN 命中域名 → 模型 A 成立（C3）。
4. 再执行 `curl -sS -m 5 http://qingxuan.bbs0.cc/`：期望不可用/无站点（验证 HTTPS-only 生效）。
5. 建第二条同域名、`locations=/metrics` 的隧道试提交（C4）：被拒 → 预留项改用独立子域，并在「二级域名解析管理」加 A 记录（无泛解析，已核验）。
6. 催办/查套餐配额（C7）与备案提示（C5）；C8 看面板帮助里的「客户端版本要求」。

---

## 8. frpc 常驻托管方案（本轮不部署）

### 8.1 二进制与放置
- 版本：`frp_<ver>_linux_arm64.tar.gz`（chroot 为 Ubuntu 24.04 aarch64 [已核验]），校验 sha256 后只取 `frpc`。
- 路径：`/usr/local/bin/frpc`（chmod 755）；配置 `/etc/frp/frpc.toml`（644）；环境文件 `/etc/frp/frpc.env`（**600**，含 `FRP_TOKEN=`）。
- chroot 内已有 `curl`/`openssl`/`ca-certificates`，若开 `transport.tls` 无需额外装包 [已核验]。

### 8.2 supervisor 托管（与现有 `haydn-*.conf` 同风格）
新增 `/etc/supervisor/conf.d/frpc.conf`：

```ini
[program:haydn-frpc]
command=/bin/sh -c 'set -a; . /etc/frp/frpc.env; exec /usr/local/bin/frpc -c /etc/frp/frpc.toml'
directory=/var/lib/frpc
autostart=true
autorestart=true
startsecs=5
startretries=10
stopsignal=TERM
stopasgroup=true
killasgroup=true
stdout_logfile=/var/log/haydn/frpc.out
stdout_logfile_maxbytes=5MB
stdout_logfile_backups=2
redirect_stderr=true
```

生效：`chroot-enter.sh /usr/bin/supervisorctl reread && … update`（先 `reread` 再 `update`，不改动其他 program）。

### 8.3 日志位置
- frpc 自身：`/var/log/haydn/frpc.log`（由 `log.to` 指定，`log.maxDays = 7`）；
- supervisor 捕获：`/var/log/haydn/frpc.out`（5MB×2）；
- 设备侧启动链日志：`/data/server/logs/boot.log`、`/data/server/logs/supervisord.out`（boot 时由 `service.sh` → `start-supervisord.sh` 写入 [已核验]）。

### 8.4 自启路径（已存在的链路，无需新改开机脚本）
`KernelSU module server-chroot/service.sh`（等 `sys.boot_completed` → 挂 chroot → `start-supervisord.sh`）→ `supervisord` → `frpc`。因此只要 frpc.conf 在 `conf.d` 里且 `autostart=true`，重启后自动恢复。

### 8.5 回滚路径
1. 面板：停用/删除隧道（M1）；
2. 设备：`supervisorctl stop haydn-frpc` → 删除 `/etc/supervisor/conf.d/frpc.conf` → `supervisorctl update`（program 消失）；
3. 清理二进制与配置：`rm /usr/local/bin/frpc /etc/frp/frpc.toml /etc/frp/frpc.env`；
4. 无需回滚网络：frpc 只出站，iptables/supervisor 其他 program 均未被改动（**不改配置**是回滚最简单的保证）；
5. 域名记录保留不会造成暴露（无客户端在线时边缘 404/拒绝，已核验同类表现）。

### 8.6 部署前须补的验证（本轮不做）
- `frpc -c ... --help` 校验配置语法（`frpc verify -c /etc/frp/frpc.toml`）；
- 首次启动后 `ss -tnp | grep 47.97.70.99` 应只有 ESTABLISHED 出站，**不应出现新的 LISTEN**；
- 断开 frpc 5 分钟，确认 18080/22/9100 本地访问不受影响。

---

## 9. 风险登记

| 风险 | 影响 | 缓解 |
|---|---|---|
| 88frp 技术参数未知（C1/C2/C3） | 首次启动可能连不上或类型不匹配 | 先只建 M1 + 用面板现值填 `serverPort`；失败即停，不反复试错 |
| 套餐隧道配额被预留项占满 | 后续无法新建 | 先查 C7；配额紧张就只建 M1（预留项写在配置注释里，随时建） |
| 静态站无认证、`http.server` 默认开目录列表 | 目录内容全公开 | 只放可公开文件；如需保护加 `httpUser/httpPassword`（frp 原生 BasicAuth） |
| 服务商合规条款（禁 VPN/DNS/NTP/影视等） | 隧道被永久关停 | 本方案只暴露静态自检页，符合；不上传 Proxy/WebDAV 大流量媒体 |
| token 泄漏 | 隧道被劫持 | 环境变量注入 + 600 权限；不写仓库/日志/聊天 |
| 边缘证书若为自签（C3 证伪） | 浏览器告警、MITM 风险 | 转模型 B（设备侧 ACME）或更换服务商 |
| 家庭网络 IP 漂移 | —（不影响） | frpc 出站连接，无需固定公网 IP 或端口映射 |

---

## 10. 关联产出

- [frpc.toml](frpc.toml)：客户端配置（占位符、启用/预留注释、HTTPS-only）
- [panel-creation-checklist.md](panel-creation-checklist.md)：面板逐项照填清单

---

## 11. 实施结果（已核验，2026-11-14）

### 11.1 最终架构（与 §3 模型 A 相反，实测为透传）

```
浏览器 --TLS--> 8.137.162.154:443 (frps, proxy type=https, 按 SNI 透传、不解密)
      --TLS 原样--> frpc --TLS 原样--> 127.0.0.1:18443 (stunnel, 设备侧 TLS 终结)
      --HTTP 明文--> 127.0.0.1:18080 (python3 -m http.server)
```

- 隧道类型：面板 **HTTPS** ↔ frpc `type = "https"`；`customDomains` 即 SNI 匹配项，无需额外 SNI/证书字段。[已核验]
- `type = "http"` 在本节点不可用：80/8080 返回 `403` 且 `Server: Beaver`（阿里云 ICP 未备案拦截页），故 HTTP 型隧道无法提供服务。[已核验]
- `transport.useEncryption/useCompression = true` 保持面板默认；`transport.tls` 未启用，端到端 TLS 由浏览器与 stunnel 协商。[已核验]

### 11.2 设备侧组件

| 项 | 值 |
|---|---|
| frpc | **0.72.0**（GitHub Release `fatedier/frp` 官方资产，包 sha256 `02180b85…5e95cf` 与官方 checksums 一致），`/usr/local/bin/frpc`，`root:root 755` |
| frpc 配置 | `/etc/frp/frpc.toml`（600 root），`serverAddr 8.137.162.154`、`serverPort 1210`、单代理 `43RHEU5l28eb` |
| frpc 托管 | supervisor `[program:haydn-frpc]`，`autostart/autorestart`，日志 `/var/log/haydn/frpc.log`（7 天）+ `.out`（5MB×2） |
| stunnel | **5.72**（apt `stunnel4`，仅新增该单包），配置 `/etc/stunnel/haydn-tls.conf` |
| stunnel 托管 | supervisor `[program:haydn-tls]`，日志 `/var/log/haydn/tls.log`（5MB×2） |
| 监听 | 仅 loopback：`127.0.0.1:18080`、`127.0.0.1:18443`、`127.0.0.1:9100`、`127.0.0.1:22` |

### 11.3 证书（阿里云免费 DV，DigiCert 签发）

| 项 | 值 |
|---|---|
| subject / SAN | `CN=qingxuan.bbs0.cc` / `DNS:qingxuan.bbs0.cc, DNS:www.qingxuan.bbs0.cc` |
| issuer | `DigiCert Inc / Encryption Everywhere DV TLS CA - G2` |
| 有效期 | `2026-11-14 00:00:00 GMT` → `2027-02-11 23:59:59 GMT` |
| 链深度 / 公钥 | 2（leaf + 中间证书，中间证书有效期至 2027-11-27）/ RSA 2048 |
| SHA-256 指纹 | `8C:95:6C:81:C2:09:A5:FC:AE:E3:E8:AB:77:7A:DE:72:99:6A:E3:B6:7A:97:BF:68:BB:8F:56:84:23:C8:77:08` |
| 私钥 / 证书路径 | `/etc/ssl/private/qingxuan.bbs0.cc.key`（600）/ `/etc/ssl/certs/qingxuan.bbs0.cc.fullchain.pem`（644） |

私钥与证书压缩包只存在于设备与本地 `inventory/`（gitignored），**不进仓库**。

### 11.4 公网验证

| 客户端 | 结果 |
|---|---|
| Chrome 浏览器 | **PASS**：`https://qingxuan.bbs0.cc/` 正常渲染，`document.title = haydn lab chroot`，无证书告警 |
| `openssl s_client` + 手发 GET | `HTTP/1.0 200 OK`，返回自检页 |
| Python `ssl` 客户端 | TLSv1.3 / TLS_AES_256_GCM_SHA384，链校验通过，`HTTP/1.0 200 OK` |
| 公网 443 证书 | 即设备这张（subject/issuer/指纹一致）→ **确认透传，无边缘第二张证书** |
| `curl`（Windows schannel / 设备 OpenSSL 3.0.13） | `(35) Connection reset`，ClientHello 后即被重置 → **待核对** |

`curl` 现象已排除 ALPN（h2 / http/1.1）、TLS 1.2/1.3、frp 压缩开关、DNS 四个因素；浏览器与 OpenSSL/Python 均正常，暂判定为链路对特定 ClientHello 的过滤特征，不影响实际使用，登记为待核对项。

### 11.5 续期与降级策略

- **不做自动续期提醒**（用户 2026-11-14 决定）。
- 到期或换证时：覆盖 §11.3 两个文件 → `supervisorctl restart haydn-tls`，结构不变。
- 若免费证书无法续签，**接受回退自签证书**（个人使用，可接受浏览器警告）：生成 CN/SAN 为 `qingxuan.bbs0.cc` 的自签证书替换同路径文件即可，其余不变。

### 11.6 回滚（严格按序）

1. `supervisorctl stop haydn-tls && rm /etc/supervisor/conf.d/haydn-tls.conf && supervisorctl update`
2. frpc `localPort` 改回 `18080` → `frpc verify -c /etc/frp/frpc.toml` → `supervisorctl restart haydn-frpc`
3. 面板改回 HTTP 类型 → 重新生成配置 → 本地 `type` 改回 `http` → `verify` → 重启

> 顺序不可颠倒：先停前置再改 localPort，否则 TLS 流量会持续打到 18080 产生 400；面板最后改，避免服务端先切换终结模型。
