# 便携服务器 Web 控制台（第一版）

> 设备：OnePlus Ace Pro（CASE-003，PGP110，Ubuntu 24.04 chroot + KernelSU）
> 公网入口：`https://8.137.162.154:60875/console`（IP + 非标端口，浏览器证书告警为预期行为；域名入口公网不可用——备案按 SNI 判定拦截（HTTP 明文 403 `Server: Beaver`），隧道仍保留作回滚备胎但不在控制台展示；证据与计数见 [frp-public-mapping](../frp-public-mapping/outputs/frp-public-mapping.md) §11.4/§12.4，[ADR-0008](../../adr/0008-public-entry-after-icp-sni-block.md)）。
> 形态：Python 3 标准库实现的多上游反向代理 + 内置控制台，零第三方依赖，由 supervisor 托管。

## 1. 为什么是"网关"而不是单独的 nginx/caddy

- frp 的 `customDomains` 只接受主机名，路径分流必须在设备侧做。
- chroot 内没有 nginx/caddy，安装需要拉包；因此用 Python 标准库实现网关（单进程，既是代理也是控制台）。
- 公网链路保持"frpc → stunnel(18443) → 127.0.0.1:18080"不变，**stunnel / frpc 配置零改动**；
  网关接管 18080，原静态站后移到 18081。

```
浏览器 --443--> frps --> frpc --> stunnel:18443 --TLS终止--> 127.0.0.1:18080 haydn-console-gateway
                                                                     ├─ /console...  -> 内置控制台（会话鉴权）
                                                                     ├─ /            -> 302 /console/（原静态站仅作未匹配路径兜底 18081）
                                                                     └─ /ui (预留)   -> 127.0.0.1:3080 DeepSeek Harness UI
```

## 2. 仓库与设备路径

| 仓库（可评审副本） | 设备路径（chroot 内） | 说明 |
|---|---|---|
| `console/gateway.py` | `/opt/haydn/console/gateway.py` | 入口：路由、反向代理、WebSocket 隧道 |
| `console/auth.py` | `/opt/haydn/console/auth.py` | PBKDF2 口令、HMAC 会话、登录限流 |
| `console/console_actions.py` | `/opt/haydn/console/console_actions.py` | 白名单动作、日志尾、证书/遥测/磁盘 |
| `console/console_credentials.py` | `/opt/haydn/console/console_credentials.py` | 凭据定义、一次性导出、轮换与回滚（§13） |
| `console/console_ui.py` | `/opt/haydn/console/console_ui.py` | 登录页与控制台页面（内联资源） |
| `console/lan_access.py` | `/opt/haydn/console/lan_access.py` | 局域网网段探测、网段文件、一次性票据 |
| `console/webdav_ui.py` | `/opt/haydn/console/webdav_ui.py` | WebDAV 中文文件管理界面（§15，由网关在浏览器 GET 时返回） |
| `deploy/lan-fw-loop.sh` | `/data/server/bin/lan-fw-loop.sh` | 宿主侧：按网段文件幂等维护 18090 放行规则 |
| `console/config.example.json` | `/etc/haydn-console/gateway.json` | 路由与白名单配置 |
| `deploy/haydn-console.conf` | `/etc/supervisor/conf.d/haydn-console.conf` | supervisor 程序定义 |
| `deploy/haydn-alist.conf` | `/etc/supervisor/conf.d/haydn-alist.conf` | AList 程序定义（§17） |
| `deploy/haydn-netdata.conf` | `/etc/supervisor/conf.d/haydn-netdata.conf` | Netdata 程序定义（§16） |
| deploy/haydn-dsh.conf | /etc/supervisor/conf.d/haydn-dsh.conf | DSH Web UI 程序定义（2026-11-16 部署；loopback 3080，经网关 /ui 会话鉴权访问，§11.8） |
| `deploy/chroot-enter.sh` | `/data/server/bin/chroot-enter.sh` | 追加 `/srv/haydn/{logs,run}` 绑定挂载 |
| `deploy/backup-loop.sh` | `/data/server/bin/backup-loop.sh` | 追加"控制台手动触发"轮询 |
| `deploy/haydn-backup.sh` | `/data/server/bin/haydn-backup.sh` | 逐来源：加密→解密自检→上传→保留 7 份 |
| `deploy/backup-vaultwarden.sh` | `/data/server/bin/backup-vaultwarden.sh` | Vaultwarden 数据一致性快照（SQLite backup API） |
| `deploy/backup-forgejo.sh` | `/data/server/bin/backup-forgejo.sh` | Forgejo 数据一致性快照（SQLite backup API + 仓库目录） |
| `deploy/device-make-backup.sh` | `/data/server/bin/device-make-backup.sh` | 整机配置快照（排除可重建大二进制）；2026-11-16 起把观测证据归档到 `meta/observability/`（soak 摘要 + watchdog/alerts/wifi-guard 日志） |
| `deploy/install.sh` | `/data/local/tmp/web-console/deploy/install.sh` | 幂等安装脚本（自动备份原配置） |
| `deploy/haydn-healthcheck.sh` | `/usr/local/bin/haydn-healthcheck.sh` | 周期健康检查（磁盘/内存水位 + 异常服务自动拉起，§14.3） |
| `deploy/haydn-observe.sh` | `/usr/local/bin/haydn-observe.sh` | 24 小时观察采样：每小时 host 汇总 + 每服务 RSS（§18） |
| `deploy/cron.d-haydn-observe` | `/etc/cron.d/haydn-observe` | 观察采样定时（每小时第 7 分钟，§18） |
| `deploy/cron.d-haydn-health` | `/etc/cron.d/haydn-health` | 健康检查定时（每 5 分钟，设备侧已生效、仓库补登） |
| `deploy/wifi-guard.sh` | `/data/server/bin/wifi-guard.sh` | Wi-Fi 省电态纠正 + 掉线告警/计数 + 重连后复查（§11.6） |
| `deploy/watchdog-loop.sh` | `/data/server/bin/watchdog-loop.sh` | 观测循环看门狗：每 300s 检查 telemetry-loop 进程与数据新鲜度（≤900s），失效即重启；宿主侧由 KernelSU 模块 `service.sh` 自启（§11.7） |
| `deploy/logrotate.d-haydn` | `/etc/logrotate.d/haydn` | 日志轮转（仅 `*.log` 周轮转 + 10M 上限；不匹配 CSV） |
| `deploy/logrotate.d-haydn-csv` | `/etc/logrotate.d/haydn-csv` | CSV 轮转：普通 CSV 日轮转 20M；`observe.csv`/`telemetry.csv` **移出日轮转**（仅 20M 大小兜底，§14.3/§18） |
| `deploy/vaultwarden-run.sh` | `/opt/haydn/bin/vaultwarden-run.sh` | 读 env 与 600 token 后降权启动 Vaultwarden |
| `deploy/haydn-vaultwarden.conf` | `/etc/supervisor/conf.d/haydn-vaultwarden.conf` | supervisor 程序定义 |
| `deploy/vaultwarden.env.example` | `/etc/haydn/vaultwarden.env` | 非敏感配置模板（部署后 600） |

设备侧另有两个不变量：

- `/etc/haydn-console/secret.json`（600）：口令派生值与会话密钥，**只存在于设备**；
- `/etc/haydn-console/admin-password.txt`（600）：首次初始化生成的明文口令，
  **读取后应立即删除**，仓库与聊天中不出现口令。

## 3. 多上游路由（为 `/ui` 预留）

`upstreams` 每条独立配置，按最长前缀匹配，新增上游不需要改代码：

```json
{
  "name": "deepseek-harness-ui",
  "path": "/ui",
  "upstream": "127.0.0.1:3080",
  "strip_prefix": true,
  "preserve_host": true,
  "websocket": true,
  "auth": "session",
  "enabled": false
}
```

| 字段 | 语义 |
|---|---|
| `path` | 匹配前缀（按段匹配，`/ui` 不会命中 `/uix`） |
| `upstream` | `host:port`，仅允许 loopback |
| `strip_prefix` | 转发前剥离前缀，`/ui/a` → `/a` |
| `preserve_host` | 保留原始 `Host: qingxuan.bbs0.cc`（上游做虚拟主机/回调时需要） |
| `websocket` | 允许 `Upgrade: websocket` 走原始 TCP 双向隧道 |
| `auth` | `none` / `session` / `basic`，每条路由独立 |
| `browser_ui` | 可选 `{title}`：该前缀根路径的浏览器 GET 返回自建中文页（目前仅 `/dav`，见 §15）；缺省不启用 |
| `enabled` | 关闭时不参与匹配 |

启用 `/ui` 的步骤：本机 `127.0.0.1:3080` 起来后，把该条 `enabled` 改为 `true`，
`supervisorctl restart haydn-console-gateway` 即可；无需动 frpc/stunnel。
上游会收到 `X-Forwarded-For/Proto/Host/Prefix`，便于其生成正确的前端资源路径。

## 4. 安全模型

- **鉴权**：所有页面与 API 需要会话 cookie（`haydn_session`，HttpOnly/Secure/SameSite=Lax，12h）；
  口令仅以 PBKDF2-HMAC-SHA256（20 万次）派生值存设备文件，仓库不含口令。
- **限流**：链路经 stunnel，远端地址恒为 loopback，无法按 IP 区分，因此采用**全局失败窗口**：
  15 分钟内 5 次失败即锁定 15 分钟，期间登录接口返回 429。
- **动作白名单**：只允许对配置内服务执行 `supervisorctl start/stop/restart`（固定参数、无 shell 拼接），
  只允许读取配置内登记的日志文件尾，备份只写一个触发文件；网关自身不在可操作名单内。
- **审计**：登录成功/失败/限流、服务操作、日志读取、备份触发均追加 JSONL 到
  `/var/log/haydn/console-audit.log`（含时间、动作、目标、结果、客户端地址、UA）。
- **CSRF**：写操作要求 `X-Haydn-Client: console` 头，并在存在 `Origin` 时校验与 `Host` 同源。
- **无任意执行**：没有 shell 端点、没有文件浏览端点、日志路径不能来自请求参数（只接受日志名）。
- **最小暴露**：公网入口仍是既有 443 链路（网关 `127.0.0.1:18080`）；局域网入口
  `0.0.0.0:18090` 由 iptables 只放行**运行时探测到的网段**，且网关自身再做一次来源网段校验（双重）。

## 5. 部署（已完成，命令可复用）

```sh
adb push 2026-11-14/web-console /data/local/tmp/web-console
adb shell su -c "sh /data/local/tmp/web-console/deploy/install.sh /data/local/tmp/web-console"
adb shell su -c "/data/server/bin/chroot-enter.sh /usr/bin/python3 /opt/haydn/console/gateway.py \
  --config /etc/haydn-console/gateway.json --init-admin"          # 只生成，不打印口令
adb shell su -c "/data/server/bin/chroot-enter.sh /usr/bin/supervisorctl \
  -c /etc/supervisor/supervisord.conf reread"
adb shell su -c "/data/server/bin/chroot-enter.sh /usr/bin/supervisorctl \
  -c /etc/supervisor/supervisord.conf update"
```

首次登录：在 PC 上执行 `adb shell su -c "cat /data/server/rootfs/etc/haydn-console/admin-password.txt"`
读取口令，登录后删除该文件；改口令用
`... gateway.py --config /etc/haydn-console/gateway.json --set-password`（从 stdin 读入）。

## 6. 回滚

安装脚本把原配置备份到 `/data/server/backups/console-20261114/`（带 UTC 时间戳）。回滚步骤：

```sh
su -c "cp /data/server/backups/console-20261114/haydn.conf.<TS> /data/server/rootfs/etc/supervisor/conf.d/haydn.conf"
su -c "cp /data/server/backups/console-20261114/chroot-enter.sh.<TS> /data/server/bin/chroot-enter.sh"
su -c "cp /data/server/backups/console-20261114/backup-loop.sh.<TS> /data/server/bin/backup-loop.sh"
su -c "rm -f /data/server/rootfs/etc/supervisor/conf.d/haydn-console.conf"
su -c "/data/server/bin/chroot-enter.sh /usr/bin/supervisorctl -c /etc/supervisor/supervisord.conf reread"
su -c "/data/server/bin/chroot-enter.sh /usr/bin/supervisorctl -c /etc/supervisor/supervisord.conf update"
```

回滚后静态站回到 18080，stunnel 未改过，公网 443 自动恢复。

## 7. 验证记录（2026-11-14）

事实分级：已核验 = 有命令输出；推断 = 有依据但未实测；未知 = 待验证。

| 项 | 结果 | 证据 |
|---|---|---|
| 本地自测（19 项：路由/鉴权/限流/白名单/CSRF/日志/审计/WebSocket） | 已核验 | `inventory/console-selftest.py` 全部 PASS |
| 阶段 1（18090 独立实例，静态站不动） | 已核验 | `/`、`/console/` 200，无会话 API 401，登录 200 |
| 阶段 2（18080 网关 + 18081 静态站） | 已核验 | chroot 内 `18081/`、`18080/`、`/index.html`、`/console/` 均 200；`/nope` 404 |
| 经 stunnel 本地 TLS（18443） | 已核验 | `/console/` 返回登录页、`/` 返回静态站标题 |
| 公网 `https://qingxuan.bbs0.cc/console/` | 已核验（历史快照，当日 22:11 前） | 200，登录页 2777 B；`/` 200 静态站；`/nope` 404；未鉴权 API 401。域名入口现已公网不可用，见 §12.2 |
| 会话登录（设备侧 curl 带口令） | 已核验 | 200；`/api/status` 200，返回 9 个服务 |
| 证书剩余天数 | 已核验 | `notAfter=2027-02-11`，剩余 89 天 |
| 遥测/soak 摘要 | 已核验 | soak 起点 2026-11-14T10:45:00Z，样本与可用率可解析 |
| 控制台触发备份 | **未知** | 代码与触发文件路径已就绪，但验证时 adb 断开，未做端到端触发 |
| 真实服务启停（非白名单拒绝） | 已核验 | 白名单拒绝已测；2026-11-15 控制台 `POST /api/service` restart `haydn-heartbeat` 返回 200（`stopped / started`），状态 RUNNING |
| 重启后 bind mount 与自启 | **未知** | 未重启设备验证；若 `/srv/haydn/logs` 未挂上，遥测会为空、日志文件不可读（页面本身不受影响，日志已改为设备侧直接查看） |

## 8. 已知限制与后续

1. 网关是公网唯一入口，异常时整站不可用；supervisor `autorestart=true` 兜底，回滚路径见 §6。
2. 登录限流是全局的（受 stunnel 隐去客户端地址所限），不能按来源 IP 区分。
3. 备份触发的真实执行依赖设备侧 `backup-loop.sh`（≤60s 轮询）；控制台只写触发文件，不直接跑脚本。
4. `/ui` 路由已预留但 `enabled=false`；DeepSeek Harness UI 上线后按 §3 打开即可。
5. 未做 HTTPS 层的额外防护（WAF/2FA）；公网暴露面收敛仍需依赖口令强度与限流。

## 9. 局域网省流入口（2026-11-14）

### 9.1 结构

| 组件 | 说明 |
|---|---|
| 监听 | `0.0.0.0:18090`（HTTP），只服务局域网；公网 443 链路与 frpc/stunnel **未改** |
| 网段探测 | 每 30s：`ip route get <target>` 取默认路由接口 → 读该接口 IPv4/前缀；失败回退首个 scope global 非 lo 接口。**不写死任何网段** |
| 网段文件 | `/srv/haydn/run/lan-subnet`（原子写），默认值仅供宿主防火墙读取 |
| 防火墙 | 宿主 `lan-fw-loop.sh`（15s）读取网段文件，幂等维护 `INPUT -s <CIDR> --dport 18090 ACCEPT`；文件缺失/非法即删除规则（fail closed） |
| 二次校验 | 局域网监听上，来源不在当前探测网段一律 403（即使 iptables 规则失效也不会放行） |
| 票据 | HMAC-SHA256，≤60s、单次（进程内 nonce 去重）、绑定签发时的设备网段；`/console/lan-login?ticket=` 校验后种会话并 302 回原页面 |
| Cookie | 局域网监听下会话 cookie **不带 Secure**（HTTP），公网监听保持 Secure；按监听区分 |
| 接口 | `GET /console/api/lan`（lan_ip/lan_subnet/lan_iface/updated_at/lan_port/lan_url）、`POST /console/api/lan-ticket`、`GET /console/lan-probe`（带 CORS，判定 same_subnet） |
| 前端 | "访问入口"区显示当前入口、局域网地址、网段、探测时间；探测成功→显示"切到局域网"；`/lan-probe` 明确返回不同网段→隐藏；HTTPS 页面被浏览器拦截探测时标"未知"并保留按钮 |

端口/探测参数在 `gateway.json` 的 `lan` 段（`enabled/listen/probe_target/probe_interval_seconds/ticket_ttl_seconds/subnet_file`）。

### 9.2 验证（2026-11-14）

| 项 | 结果 | 证据 |
|---|---|---|
| 局域网探测 | 已核验 | `/api/lan` → `192.168.31.50` / `192.168.31.0/24` / `wlan0`，`updated_at` 每 30s 前进 |
| 局域网可达（真实跨主机） | 已核验 | Windows `192.168.31.194` 访问 `:18090`，`/lan-probe` 200 `same_subnet=true` |
| 票据签发→兑换→会话 | 已核验 | 302 → `/console/`，`Set-Cookie` 无 Secure；用该会话 `/api/status` 200（11 服务） |
| 重放 | 已核验 | 同一票据第二次兑换 409，审计 `lan.ticket replay` |
| 过期 | 已核验 | 等待 62s 后兑换 401，审计 `expired` |
| 网段不符 | 已核验 | 从 loopback 兑换 → 403，审计 `subnet-mismatch` |
| 网段变化→规则重建 | 已核验 | 冻结网关后手写 `10.0.0.0/8`，15s 内规则改为该网段；写非法值后规则被删除；恢复后 35s 内自动回到 `192.168.31.0/24` |
| 防火墙实际生效 | 已核验 | 规则删除期间 Windows 探测超时；恢复后 200 |
| 公网侧不受影响 | 已核验（历史快照，当日 22:11 前） | `https://qingxuan.bbs0.cc/console/` 200；`/` 200。现域名入口公网不可用，公网走 IP:60875，见 §12.2 |
| 真实换 Wi-Fi / DHCP 换址后的页面刷新 | **未实测** | 需改变设备网络（破坏性）；代码路径为每 30s 重探 + 页面每 15s 拉 `/api/lan`（`no-store`） |
| mDNS（`haydn.local`） | **不可行（未实施）** | chroot 内需自建 mDNS 应答器并绑定 UDP 5353；Android 的 mdnsd 按需占用 5353，且 Android 系统解析不走 mDNS。客户端侧（Windows/macOS/iOS）支持但服务端不稳，故不做 |

### 9.3 回滚

```sh
# 1) 停防火墙同步 + 删规则
su -c "kill \$(cat /data/server/run/lan-fw.pid)"
su -c "iptables -S INPUT | grep haydnlab_allow_lan18090"   # 逐条 -D 删除
# 2) 关局域网监听（配置即回滚，不删代码）
su -c "/data/server/bin/chroot-enter.sh /usr/bin/python3 - <<'EOF'
import json; p='/etc/haydn-console/gateway.json'; c=json.load(open(p)); c['lan']['enabled']=False
json.dump(c, open(p,'w'), indent=2, ensure_ascii=False)
EOF"
su -c "/data/server/bin/chroot-enter.sh /usr/bin/supervisorctl -c /etc/supervisor/supervisord.conf restart haydn-console-gateway"
# 3) 恢复开机钩子
su -c "cp /data/adb/modules/server-chroot/service.sh.bak-lan-<TS> /data/adb/modules/server-chroot/service.sh"
```

代码级回滚：`/data/server/backups/console-lan-<TS>/` 保留部署前的 `gateway.json` 与 `console/` 全量副本。

### 9.4 已知限制

1. 公网页面是 HTTPS，浏览器会拦截对 `http://<lan_ip>:18090` 的探测（混合内容），此时按钮保留并标"未知"；
   局域网页面（HTTP）下探测正常。
2. 局域网是明文 HTTP（同网段内），不适合在不可信 Wi-Fi 下登录；口令登录仍可用，票据只避免重复登录。
3. 网段切换后最长 30s（探测）+15s（防火墙）才生效；旧页面签发的票据会因网段不符被拒（需刷新重试）。
4. `tailscale serve` 未实施：userspace 网络模式下无 tun，且会与客户端第三方 VPN 冲突，仅作可选记录。

## 10. Vaultwarden 密码库（2026-11-14，公网基线可用）

### 10.1 结构

| 组件 | 说明 |
|---|---|
| 二进制 | `/opt/haydn/bin/vaultwarden`（1.37.5，取自 ghcr 镜像层 arm64，glibc 2.39；补装 `libmariadb3/libpq5` 仅为满足 DT_NEEDED，实际用 SQLite） |
| web-vault | `/opt/haydn/vaultwarden-web-vault`（2026.6.0，162 MB） |
| 数据 | `/srv/haydn/vaultwarden`（SQLite；`rsa_key.pem`、`db.sqlite3*` 为 600，启动时 `umask 077`） |
| 配置 | `/etc/haydn/vaultwarden.env`（600）：`DOMAIN=https://vault.qingxuan.bbs0.cc`、`ROCKET_ADDRESS=127.0.0.1`、`ROCKET_PORT=18084`、`SIGNUPS_ALLOWED=false` |
| 启动 | supervisor `haydn-vaultwarden` → `vaultwarden-run.sh`（root 读 600 env/token 后 `setpriv` 降权到 `vaultwarden`） |
| TLS | 新增独立 stunnel 实例 `haydn-vault-tls`：`127.0.0.1:18445` → `127.0.0.1:18084`（自签证书；主实例 18443 与其 DigiCert 证书未动） |
| 隧道 | frpc `[[proxies]] 3U6GYwayApgh`：`type=https`、`localPort=18445`、`customDomains=["vault.qingxuan.bbs0.cc"]`；主块保持 `type=https`、`localPort=18443` |
| 凭据 | `/opt/haydn/secrets/`：`vaultwarden-admin-token`（argon2id PHC，服务读）、`vaultwarden-admin-token.txt`（明文，供 `/admin` 登录）、`vaultwarden-initial-account.txt`（初始账号 email/口令），均 600 |
| 轮换 | `rotate-secret.sh vaultwarden`：生成 token → argon2 PHC → 写 600 文件 → 重启 → `/admin` 登录验证 → 失败回滚两文件并重启 |

自签证书：CN=`vault.qingxuan.bbs0.cc`，O=`haydn self-signed`，SAN `DNS:vault.qingxuan.bbs0.cc, DNS:localhost, IP:127.0.0.1`，
RSA3072/SHA256，`SHA256 2E:7B:76:F3:96:52:B7:50:5C:52:6A:B6:D9:91:F8:C3:8D:8D:B9:73:BA:62:A8:26:6A:A8:39:1A:D0:15:A5:76`，
有效期 2026-11-14 → **2029-02-16 13:43:12 GMT**；私钥 `/etc/ssl/private/vault.qingxuan.bbs0.cc.key`（600）。

### 10.2 客户端影响（如实）

| 客户端 | 预期 | 分级 |
|---|---|---|
| 浏览器网页版 | 首次访问需手动信任自签证书，之后正常 | 已核验（证书链自签、页面 200） |
| Bitwarden 移动端 App | **预计不可用**：官方 App 通常只信任公共 CA，不接受自签/用户 CA | 推断（未实测） |
| 桌面端 / 浏览器扩展 | 可能可用，但需把该证书加入系统/浏览器信任库 | 推断（未实测） |

### 10.3 验证（2026-11-14）

| 项 | 结果 | 证据 |
|---|---|---|
| 本地 `/alive`、`/api/config`、`/`、`/admin` | 已核验 | 均 200；`/` 23139 B（web-vault）；admin 登录 200 且下发 `VW_ADMIN` cookie |
| 初始账号创建 + 登录 | 已核验 | `/identity/accounts/register/send-verification-email` → `/register/finish` 200；`/identity/connect/token` 返回 `access_token` |
| 关闭自助注册 | 已核验 | `SIGNUPS_ALLOWED=false` 后注册端点拒绝（400/「Registration not allowed」）；既有账号仍可登录 |
| admin token 为 argon2 PHC | 已核验 | 启动日志不再出现 plaintext ADMIN_TOKEN 警告；PHC 长度 119 |
| token 轮换脚本 | 已核验 | `rotate-secret.sh vaultwarden` 成功并回滚点生成 `.bak-20261114T140042Z` |
| 公网 `https://vault.qingxuan.bbs0.cc/` | 已核验 | 443 呈现自签证书（指纹与设备一致）、`/` 200、`/api/config` 200 |
| 主站未受影响 | 已核验 | `https://qingxuan.bbs0.cc/console/` 200、`/` 200，443 仍是 DigiCert `8C:95:…:C8:77:08` |
| frpc 两条隧道 | 已核验 | 日志 `proxy added: [3U6GYwayApgh 43RHEU5l28eb]`、两条 `start proxy success`，无 `port not allowed`/`type mismatch`/`cannot bind` |
| 移动端 App 实际可用性 | **未知** | 需真机安装后验证；按预期不可用 |
| 重启后自启 | **未知** | 未重启整机；supervisor `autostart=true` 已配置 |

占用：`vaultwarden` RSS ≈ 32 MB；磁盘 ≈ 162 MB（web-vault）+ 42 MB（二进制）+ 0.3 MB（数据）；
服务总数 13（原 11 + `haydn-vault-tls` + `haydn-vaultwarden`）。

### 10.4 回滚

```sh
# 只停服务（数据与配置保留）
su -c "/data/server/bin/chroot-enter.sh /usr/bin/supervisorctl -c /etc/supervisor/supervisord.conf stop haydn-vaultwarden"
# 彻底移除自启（数据仍在 /srv/haydn/vaultwarden）
su -c "rm /data/server/rootfs/etc/supervisor/conf.d/haydn-vaultwarden.conf"
su -c "/data/server/bin/chroot-enter.sh /usr/bin/supervisorctl -c /etc/supervisor/supervisord.conf reread && \
       /data/server/bin/chroot-enter.sh /usr/bin/supervisorctl -c /etc/supervisor/supervisord.conf update"
# 隧道回滚：删 frpc.toml 中 [[proxies]] 3U6GYwayApgh 块后重启 haydn-frpc
# frpc 备份：/data/server/rootfs/etc/frp/frpc.toml.bak-20261114T134219Z
```

### 10.5 已知限制

1. 自签证书 2029-02-16 到期，续签需重生成并在文档更新指纹；移动端 App 预期不可用（见 §10.2）。
2. 二进制来自镜像层（GitHub release 无附件、registry 直连不可达），升级需重走镜像层提取并在设备上复验。
3. 密码库数据已纳入 03:30 定时备份（见 §11），但尚未纳入 soak/遥测面板；管理员 token 与初始账号口令只存在于设备 600 文件。
4. 网关不代理 `/vault`：vault 走独立 stunnel/隧道直连 18084，因此控制台会话与 Basic 凭据与其无关。

## 11. 备份集成：Vaultwarden 数据（2026-11-14）

### 11.1 改造点

| 文件 | 变化 |
|---|---|
| `deploy/haydn-backup.sh` | 由"单来源"改为 `process_archive <archive> <label>`：每个来源各自加密→解密自检→上传→按来源保留 7 份；主流程依次处理 `haydn`、`forgejo`、`vaultwarden` |
| `deploy/backup-forgejo.sh` | 新增：Git 数据一致性快照 `forgejo-backup-<UTC>.tar.gz`（db 走 backup API，仓库/附件/jwt/app.ini 直接复制） |
| `deploy/backup-vaultwarden.sh` | 新增：生成密码库一致性快照 `vaultwarden-backup-<UTC>.tar.gz` |
| `deploy/device-make-backup.sh` | 新增排除 `opt/haydn/bin/{vaultwarden,forgejo}` 与 `opt/haydn/vaultwarden-web-vault`（可重建，约 313 MB） |

SQLite 一致性方式（主机无 `sqlite3` CLI，用 chroot 内 python3 3.45.1 的 backup API）：

```python
src = sqlite3.connect("file:/srv/haydn/vaultwarden/db.sqlite3?mode=ro", uri=True)
dst = sqlite3.connect("<stage>/.../db.sqlite3")
src.backup(dst)                                # 在线一致性快照（含 WAL 已提交内容）
dst.execute("PRAGMA wal_checkpoint(TRUNCATE)") # 只作用于副本
dst.commit()
ok = dst.execute("PRAGMA integrity_check").fetchone()[0]
```

- **不需要短暂停写**：backup API 在源库可继续读写时取得一致视图，checkpoint 只作用副本，因此 03:30 定时无需改时刻、无停服窗口。
- 一并收录 `rsa_key.pem`、`config.json`；`attachments/`、`sends/` 仅在存在时复制（当前为空，未创建）。
- 包内写 `meta.txt`（source/snapshot_at/db_mode=sqlite-backup-api）与 `MANIFEST.sha256`；脚本 `umask 077`。

加密与上传完全复用原路径：`haydn_crypt.py`（HYDNBK1）→ 解密回读比对 sha256 → `quark-drive.cjs` 上传到同一父目录 `夸克网盘/haydn-server-backup`；失败按 300/900 秒退避重试 3 次。文件名前缀区分来源：`haydn-backup-*.tar.gz.enc`、`forgejo-backup-*.tar.gz.enc`、`vaultwarden-backup-*.tar.gz.enc`。

### 11.2 手工全链路验证（2026-11-14 14:21–14:22Z，已核验）

| 步骤 | 结果 | 证据 |
|---|---|---|
| haydn 快照 | 已核验 | `snapshot label=haydn sha=9e07923d…`（整机配置/代码，已排除 3 个可重建大目录） |
| haydn 加密 + 解密自检 | 已核验 | `encrypt+verify ok ... bytes=70099070`，回读 `plain_sha256=9e07923d…` 一致 |
| haydn 上传 | 已核验 | `upload ok attempt=1`，fids `0ad779f8…` / `7d514d89…` |
| forgejo 快照 | 已核验 | `sqlite backup integrity_check=ok`、`manifest_lines=15`、`SIZE=48253` |
| forgejo 加密 + 自检 + 上传 | 已核验 | `bytes=48560`、sha256 一致、`upload ok attempt=1`（fids `551291ac…` / `77bb134f…`） |
| forgejo 解密 + 恢复演练 | 已核验 | 包内 `forgejo.db`、`repositories/`、`data/{avatars,jwt,home,actions_id_token}`、`app.ini`；`integrity: ok`、`users 1`（haydn/admin）、`journal_mode wal`；db 清单哈希 `OK` |
| vaultwarden 快照 | 已核验 | `sqlite backup integrity_check=ok`、`manifest_lines=3`、`SIZE=12334` |
| vaultwarden 加密 + 自检 + 上传 | 已核验 | `bytes=12645`、sha256 一致、`upload ok attempt=1`（fids `e89cc994…` / `08963d6c…`） |
| vaultwarden 解密 + 恢复演练 | 已核验 | `integrity: ok`、`users 1`、`devices 3`、`journal_mode wal`；恢复出的 `rsa_key.pem` 为 `600 997:992` |
| 源权限未被放宽 | 已核验 | vault：`db.sqlite3`/`rsa_key.pem` 600 997:992、目录 755；forgejo：目录 750、`app.ini` 600 999:993、`forgejo.db` 644（均与备份前一致） |
| 整链退出码 | 已核验 | `RC=0`，日志末行 `DONE ok` |

### 11.3 体积与保留

- 设备快照：113.4 MB → **70.1 MB**（排除 forgejo 109 MB / vaultwarden 42 MB / web-vault 162 MB 后；其余内容与改造前一致）。
- 每来源独立保留最近 **7** 份（`KEEP=7`，按 mtime + 前缀分来源 prune），本地密文在 `/var/backups/haydn/`。
- 本轮为手工触发验证；03:30 定时尚未等到自动执行（`backup-loop` pid 7607 存活、boot_id 未变，下一次 03:30 起按新流程运行）。

### 11.4 回滚

```sh
su -c "cp /data/server/backups/backup-script-20261114T140547Z/haydn-backup.sh /data/server/bin/haydn-backup.sh"
su -c "cp /data/server/backups/backup-script-20261114T140547Z/device-make-backup.sh /data/server/bin/device-make-backup.sh"
su -c "rm -f /data/server/bin/backup-vaultwarden.sh"
```

回滚只影响之后的备份行为，已上传密文与本地密文不动。仓库副本对应 `deploy/` 下四个文件（`haydn-backup.sh`、`device-make-backup.sh`、`backup-vaultwarden.sh`、`backup-forgejo.sh`，新增的 `backup-forgejo.sh` 直接删除即可）。

### 11.5 已知残留

1. 恢复演练只做了解密/解包/库完整性/权限校验，未在独立实例上做"真实登录 + 客户端同步"回归。
2. 恢复 Forgejo 时需补一次属主/权限：备份副本的 `forgejo.db` 为 `600 root:root`（stage 以 `umask 077` 生成），放回原路径后应 `chown 999:993` 并 `chmod 644`；`app.ini` 已按原 600/999:993 保留。
3. 未等到 03:30 自动定时执行，已验证的是手工全链路。

### 11.6 上传失败定位与备份/网络加固（2026-11-15）

**根因（已核验）**：11-15 03:30（本地）定时备份在**上传**这一步失败——`snapshot` 与 `encrypt+verify` 均成功，`upload` 三次（`19:39:54Z`/`19:44:55Z`/`19:59:56Z`）返回 `{"code":1007,"msg":"getaddrinfo EAI_AGAIN open-api-drive.quark.cn"}`，末行 `FAIL`。同一窗口 `frpc` 用 **IP 直连**（`8.137.162.154:1210`，不经 DNS）持续报 `network is unreachable`（18:1x–21:3x 每 10 分钟 30 条＝每 20 秒全失败），`console-gateway` 记录 wlan0 `18:17:30` 失去地址、`18:38`/`19:39`/`21:39` 各恢复 30–60 秒、`21:42:38` 起稳定 → 判定为**设备侧 Wi-Fi 链路中断**，非夸克侧、非 resolver 配置。当前实测：`getent hosts/ahostsv4/ahostsv6` 全 rc=0、原始 UDP/53 三个上游（192.168.31.1 / 223.5.5.5 / 119.29.29.29）全 `rcode=0`、`getaddrinfo` 5/5、`node dns.lookup` 双栈、TCP 443 握手 58 ms、夸克 `get-user-info` `code=0`。省电态在每次重连后被系统重新打开（`wifi-guard` 逐次 `CORRECTED power_save on->off`），与掉线的因果仍属**推断**（未做 A/B）。为何报 `EAI_AGAIN` 而非 `ENETUNREACH`：node 上传走 `getaddrinfo`，链路断时上游不可达；frpc 走 IP 直连故报路由不可达，两者同源。

| 文件 | 变化 |
|---|---|
| `deploy/haydn-backup.sh` | ① 上传前 `precheck`（chroot 内 `getaddrinfo` + TCP/443，`PRECHECK_TIMEOUT` 默认 6 s）：不通则记 `upload precheck fail` 立即返回，密文留在 `/var/backups/haydn/` 待补传，不再空转 300+900 秒；② 三来源改为 `run_source` 循环，逐来源 `source ok/fail` 并汇总 `SUMMARY ok=N fail=M failed=[…]`，单来源失败不再中断其余（原为 `\|\| fail` 直接退出）；③ `SOURCES` 环境变量选择来源（如 `SOURCES=vaultwarden` 手工单来源） |
| `deploy/wifi-guard.sh` | 掉线（无 IPv4）记 `FAIL … downs=N` 并写 `alerts.log` + `cmd notification`，首次翻转及每 12 次（约 1 小时）告警；状态存 `run/wifi-guard.state`；`down/missing → up` 记 `RECOVER` 并立即复查省电态 |

**验证（2026-11-15，已核验）**

| 项 | 结果 | 证据 |
|---|---|---|
| 预检快速失败 | rc=1，耗时 **2 s**（改造前为 300+900 s 退避） | `SOURCES=vaultwarden PRECHECK_HOST=no-such-host.invalid.` → `upload precheck fail label=vaultwarden rc=2 dns-fail gaierror` + `upload skipped … keep=…vaultwarden-backup-20261115T053032Z…enc` |
| 预检通过路径 | 正常连通时 `precheck ok` 后继续上传 | `upload precheck ok label=haydn ok ips=203.119.175.186,2408:4001:f00::2ec` → `upload ok attempt=1`（97,871,170 B） |
| 单来源失败不阻断 | `chmod 644 backup-forgejo.sh` 后跑全量：haydn `upload ok`（97.87 MB/2 文件）、forgejo `source fail … stage=snapshot rc=126`、vaultwarden `upload ok`、`SUMMARY ok=2 fail=1 failed=[ forgejo ]`，退出码 1；脚本权限已还原 755 | 05:42:41Z–05:42:45Z |
| wifi-guard 告警落盘 | `WIFI_FORCE_DOWN=1` 演练：`FAIL wlan0 down no-ipv4 downs=1/2`；`alerts.log` 记 `ALERT_NOTIFY wifi link down dev=wlan0 downs=1`（第 2 次不重复告警）；恢复后 `RECOVER wlan0 link up after downs=2` 且 `Power save: off`；演练计数已归零 | 05:31:03Z |
| 小文件连通性 | 117 B 测试文件上传 `code:0`，远端 117 B 与本地一致 | `haydn-upload-probe-20261115.txt` |
| 补传昨晚归档 | `code:0 successCount=2 totalSize=97807035`（＝97,806,928 + 107 字节目录），远端检索到同名的 97,806,928 与 107 两个大小，与本地逐项一致 | 05:37Z |

**回滚**（两个脚本均由 cron/loop 调用，无常驻进程，回滚后下一周期即生效，无需重启服务）：

```sh
su -c "cp /data/server/backups/backup-harden-20261115T053017Z/haydn-backup.sh /data/server/bin/haydn-backup.sh"
su -c "cp /data/server/backups/backup-harden-20261115T053017Z/wifi-guard.sh /data/server/bin/wifi-guard.sh"
```

**仍未解决**

1. 省电态被系统反复重置的根因未定位（每次重连后 `Power save: on`），目前靠每 5 分钟纠正；与掉线的因果为推断。
2. 远端内容未做字节级回读：`download` 需要 fid，`browse --parent-fid` 返回 `-100` 未取到列表，已核验的是大小与 `.sha256` 伴随文件的字节数。
3. 上传失败时保留的密文只在成功路径 prune，连续多日失败会累积（约 98 MB/天），需人工清理。
4. 测试小文件 `haydn-upload-probe-20261115.txt`（117 B）仍留在 `夸克网盘/haydn-server-backup`：该 CLI 没有删除远端文件的命令（`download delete` 只删任务记录），需在网盘客户端手工删除。

### 11.7 观测循环看门狗（2026-11-16）

**问题**：遥测循环 `telemetry-loop.sh` 由模块 `service.sh` 以 `nohup` 启动一次，**无外部看门狗**；循环一旦静默退出（曾因脚本语法错误），遥测与告警只会滞后到下一次开机。

**实现**（`deploy/watchdog-loop.sh` → 设备 `/data/server/bin/watchdog-loop.sh`）：

| 项 | 内容 |
|---|---|
| 判定 | ①`pgrep -f telemetry-loop.sh` 无进程 → `reason=process_missing`；②`telemetry.csv` 末行距今 > 900s → `reason=stale_data`。任一命中即重启循环 |
| 动作 | kill 残留实例 → `setsid` 启动 → 8s 后复查进程 → 写 `watchdog.log`（`OK`/`STALE`/`RESTARTED`/`RESTART_FAILED`） |
| 日志 | `/data/server/logs/watchdog.log`（每 300s 一条 `OK alive=1 age=Ns`） |
| 自启 | KernelSU 模块 `service.sh` 追加 `watchdog-loop.sh --loop 300`（**宿主侧**启动：supervisord 在 chroot 内看不到 `/data/server/bin`） |
| 回滚 | 从 `service.sh` 删除 watchdog 段 → `kill $(cat /data/server/run/watchdog.pid)`；模块脚本改动前已备份到 `/data/server/backups/module-<ts>/service.sh` |

**实测（2026-11-16，已核验）**

1. 健康路径：`watchdog.log` 每 300s 追加 `OK alive=1 age=…`（11:03:49Z、11:06:32Z）。
2. 故障注入两次：`kill -9` 遥测循环 → 看门狗记 `STALE alive=0 … reason=process_missing` → `RESTARTED pid=…`，8s 后循环恢复单实例。
3. 重启验证：`service.sh` 自启链输出 `watchdog started pid=9166`，重启后 `telemetry=1`、`watchdog=1`、supervisor 15 个服务 RUNNING、`boot.log` 顺序正常（supervisord → 遥测 → backup → lan-fw → watchdog）。
4. 顺带清理：排查中发现**重复遥测实例**（曾有 3 个并发写入同一 CSV）——初次排查时 `pgrep` 匹配到正在退出的僵尸 shell 造成误判，已 `kill -9` 收敛为 1 个，并在看门狗里保留单实例语义（重启前先 kill 全部）。

**设计取舍**：未把看门狗放进 supervisord——supervisord 在 chroot 内运行，只能看到 `/srv/haydn/{logs,run}` 绑定，`/data/server/bin/*.sh` 与 `/proc` 语义都在宿主侧；宿主侧自启链（模块 `service.sh`）才是正确位置。曾试挂 supervisor 的 `haydn-watchdog` 程序，因 `can't find command '/data/server/bin/watchdog-loop.sh'` 立即 FATAL，已回滚删除该配置并重启 supervisord 清理残留条目。

### 11.8 DSH Web UI 部署与控制台鉴权桥接（2026-11-16，已核验）

| 项 | 值 |
|---|---|
| 组件 | `@deepseek-ai/dsh` **0.2.2-rc.1**（npm 最新版），654 包，安装到 chroot `/opt/dsh`（**804 MB**）；运行时 Node **v24.16.0**（`/opt/node24`，195 MB，满足 `engines.node>=24.9`） |
| 守护 | supervisor `[program:haydn-dsh]`：`--profile web --host 127.0.0.1 --port 3080 --no-open`，`NODE_OPTIONS=--max-old-space-size=768`，日志 `/srv/haydn/logs/dsh.log`，`autostart`+`autorestart`+`stopasgroup` |
| 入口 | 网关 `upstreams[{name:deepseek-harness-ui, path:/ui, strip_prefix:true, preserve_host:true, websocket:true, auth:session}]` 由 `enabled:false` 改为 `true`；入口表新增「DSH 控制台 → /ui/」 |
| **鉴权桥接（关键）** | DSH 对**每个请求**校验 authority 绑定的签名 cookie（`dsh-auth-<b64url(sha256(authority))>` = `v1.<body>.<hmac>`）。launch token 每进程随机，但**签名密钥持久**（DSH 凭据库 `client-connection/browser-session`）。故新增 [console/dsh_auth.py](console/dsh_auth.py)，由网关在**控制台会话通过后**按实际转发的 Host 现场铸造 cookie（[gateway.py](console/gateway.py) `_proxy` 与 `_tunnel` 两处），浏览器无需再碰 DSH 的 `?token=` 链接；密钥按文件 mtime 缓存，失败显式 503（不再让用户撞看不懂的 401） |
| **`--trusted-host`** | `/api` 另有 browser-trust 围栏：Host 只接受 loopback / 绑定地址 / `--trusted-host` 声明的 authority。未声明时 `/api/remote.mux`（WebSocket mux）返回 **403**；已声明 `qingxuan.bbs0.cc` 与 `192.168.31.50:18090` |
| 鉴权实测 | 未登录 `/ui/` → **401**（网关）；带控制台会话 → **200 / 40,102 B HTML**（公网 Host 与局域网 Host 两种 authority 均通过）；`/api/remote.mux` WS 升级 → **101 Switching Protocols**；页面 JS/CSS/插件 bundle 均 200 |
| 资源 | 安装期可用内存 3,304 MB → **448 MB**（npm 峰值）；supervisor **16/16 RUNNING**（新增 haydn-dsh）；磁盘 206 G 可用 |
| 回滚 | `stop haydn-dsh` → 删除 `haydn-dsh.conf` + `reread/update`；网关 `/ui`.enabled 置回 false 并重启网关；`rm -rf /opt/dsh`（`/opt/node24` 删除前先确认是否被复用） |
| **pnpm（2026-11-16）** | 经 corepack 安装 **pnpm 12.21.0** 到 `/opt/node24/bin/pnpm`（Node24 官方 shim 目录，已在 supervisor PATH 内）；实测 DSH 插件管理器可调用：`dsh plugin --profile web add --help` 返回 pnpm 帮助、`.plugin-manager/logs/operation-*/pnpm.log` 正常创建；**真实插件安装未实测**（会改动 profile，本轮不冒险） |
| **健康检查（2026-11-16）** | `haydn-healthcheck.sh` 增加 DSH 探针：`127.0.0.1:3080` 返回 **401 或 200** 均视为存活（DSH 未登录固定 401），连不上记 `FAIL dsh`；进程 RUNNING 但 HTTP 卡死时限频 15 分钟重启一次并记 `RECOVER dsh-http`（与 netdata 同口径）；实测：supervisor 停止后健康检查记 `RECOVER haydn-dsh` 并拉起、失败分支（临时副本探 3081）记 `FAIL dsh` |
| **备份纳入 DSH（2026-11-16）** | `device-make-backup.sh` 打包 chroot `/root/.dsh`（profiles/sessions/storages + `.credentials.yaml` 600）；实测备份包内含 **27 条 `.dsh` 条目**、凭据权限 `-rw-------` 保留、验证后删除明文包；该目录含 DSH 签名密钥，只随**加密备份**入库（与 Vaultwarden 主密码同口径，见 BL-046） |
| **内存现状（2026-11-16）** | DSH RSS **280–330 MB**（`NODE_OPTIONS=--max-old-space-size=768`）；整机 `/proc/meminfo` **MemAvailable ≈ 10.3–10.5 GiB / MemTotal 15.6 GiB**（约占 67%，远高于 healthcheck 的 10% 阈值），zram swap 9.9 GB 当前已用约 1.5 GB。**勘误**：早期按 `free -m` 列位误读为"仅剩 180–450 MB"，改以 `/proc/meminfo` 为准后**不存在内存告急**；本轮未调参 |
| 未完成（不写通过） | 浏览器 DOM 级实际渲染未核验（需人工打开确认）；DSH 模型凭据（LLM key）未配置；WebSocket **长连接稳定性**未压测；真实插件安装未实测；**Android 内核未升级**（见 §11.8 末注） |

> 部署与重建步骤见 [deploy/haydn-dsh.conf](deploy/haydn-dsh.conf) 注释；`dsh_auth` 的算法与缓存行为有单测（`toolkit/tests/test_console_dsh_auth.py`，13 项）。**排障要点**：控制台给了 401 才是会话问题；已登录却仍报 "dsh web authentication required" = 网关未注入 DSH cookie；`/api` 报 403 = `--trusted-host` 缺当前 authority。

## 12. Git 服务 Forgejo 挂 `/git`（2026-11-14）

## 12. Git 服务 Forgejo 挂 `/git`（2026-11-14）

### 12.1 结构与鉴权选择

| 项 | 值 |
|---|---|
| 版本 | Forgejo 17.0.1+gitea-1.22.0（arm64 单二进制，113,764,224 B） |
| 监听 | `127.0.0.1:18083`（HTTP，仅 loopback） |
| 配置 | `/etc/haydn/forgejo/app.ini`（600 git:git）：`ROOT_URL=https://qingxuan.bbs0.cc/git/`、`DOMAIN=qingxuan.bbs0.cc`、`DB_TYPE=sqlite3`、`INSTALL_LOCK=true`、`DISABLE_REGISTRATION=true`、`START_SSH_SERVER=false` |
| 数据 | `/srv/haydn/forgejo`（750 git:git）：`data/forgejo.db` 1.2 MB + `forgejo.db-wal` 4.1 MB、`repositories/`、`log/` |
| supervisor | `haydn-forgejo` RUNNING（13 个服务之一，未新增端口/隧道条目） |
| 网关 | `{name:"forgejo", path:"/git", upstream:"127.0.0.1:18083", strip_prefix:true, websocket:true, auth:"none"}` |

**当前公网入口（2026-11-14 选定，ADR-0008 `accepted`）**

| 入口 | 地址 | 状态 |
|---|---|---|
| 根路径 → 控制台 / 控制台 / Git（**主入口**） | `https://8.137.162.154:60875/`（302 → `/console/`）、`/console/`、`/git/` | **可用**；TCP 隧道 `HJtApRGYMHvn` → 18443（stunnel 终结 TLS） |
| 密码库（**主入口**） | `https://8.137.162.154:60177/` | **可用**；TCP 隧道 `0mP2rpGpthc0` → 18445（stunnel 终结 TLS） |
| 域名入口（443 与域名 + 非标端口） | `https://qingxuan.bbs0.cc/`、`https://vault.qingxuan.bbs0.cc/` | **公网不可用**：备案按 SNI 判定拦截；隧道 `43RHEU5l28eb`/`3U6GYwayApgh` 保留作回滚，控制台不展示 |
| 局域网 | `http://<lan_ip>:18090/` | **同网段省流**（定位不变，不作为公网替代，见 §9） |

域名入口的判据实验、计数与证书指纹只在 [frp-public-mapping](../frp-public-mapping/outputs/frp-public-mapping.md) §11.4/§12.4 维护，本文不复述；选型见 [ADR-0008](../../adr/0008-public-entry-after-icp-sni-block.md)。

证书告警是预期行为：`:60875` 是 DigiCert 证书但 CN=`qingxuan.bbs0.cc` ≠ IP，`:60177` 是自签证书 → 浏览器会提示"连接非私密/名称不匹配"，按"高级 → 继续前往"处理；客户端（Vaultwarden 扩展/App）需显式信任自签证书并改写服务地址为 `https://8.137.162.154:60177`（**未实测**）。

**鉴权选 Forgejo 自身账号体系（网关 `auth="none"`）**，理由：
1. 网关 `basic` 是**共享凭据**，会让 `git clone https://…/git/x.git` 与网页登录各弹一次，且 Basic 头会与 Forgejo 自己的会话/表单登录相互干扰；
2. 代码托管需要按人区分与审计（提交作者、仓库权限、API token），共享凭据做不到；
3. Forgejo 自带账号口令、会话、API token 与可选 2FA，且已完成 `INSTALL_LOCK=true` + `DISABLE_REGISTRATION=true`（关闭公开注册，现有 1 个管理员账号 `haydn`）。

代价：`/git/` 登录页公网可达，防爆破依赖 Forgejo 自身限流；当前未启用 2FA/验证码。

### 12.2 验证

**本地链路（已核验，22:1x，Host 伪装公网）**

| 路径 | 结果 |
|---|---|
| `/git/` | 200，14760 B |
| `/git/user/login` | 200，12478 B，`<title>Sign in - Haydn Git</title>`，含 `user_name`/`password` 表单 |
| `/git/explore/repos` | 200，16431 B |
| `/git/assets/css/index.css` | 200，421259 B（`strip_prefix` 后静态资源可加载） |
| `/git/api/v1/version` | 200，34 B |
| `/git/api/healthz` | 200，289 B |
| `/git/api/v1/user`（未登录） | 401 |
| `/git/<owner>/<repo>.git/info/refs`（未登录） | 401 |
| TLS `127.0.0.1:18443` + Host → `/git/` | 200，14760 B（公网链路设备侧末段正常） |
| 直连 `127.0.0.1:18083/git/` | 404；`/` 200 —— 前缀由网关剥离，符合设计 |

**公网入口（结论）**

- **域名入口公网不可用**：备案按 SNI 判定拦截——明文 HTTP 返回 403 `Server: Beaver`（`Non-compliance ICP Filing`），TLS 握手被 RST；域名 + 非标端口同样受影响。
- **当前主入口为 IP 直连**：主站 / 控制台 / Git 走 `https://8.137.162.154:60875/`，密码库走 `https://8.137.162.154:60177/`。
- 判据实验、计数、证书指纹与事实分级只在 [frp-public-mapping](../frp-public-mapping/outputs/frp-public-mapping.md) §11.4/§12.4 维护，本文不复述；原两条 https 隧道不删不改，保留作回滚（步骤见同文 §12.7）。

已选型（2026-11-14）：IP + 非标端口为当前主入口；域名隧道保留作回滚备胎，**不在控制台 `entries[]` 展示**。复议触发点（备案完成、取得自有域名、IP/端口被封、客户端原生支持成为硬需求）见 [ADR-0008](../../adr/0008-public-entry-after-icp-sni-block.md)。

### 12.3 占用

| 项 | 值 |
|---|---|
| 内存 | RSS 178–183 MB（pid 12577，VSZ ≈ 1476 MB） |
| 磁盘 | 数据 6 MB（db 1.2 MB + WAL 4.1 MB）+ repositories 1 MB + 配置 1 MB + 二进制 108.5 MB ≈ **121 MB** |
| 端口/隧道 | 监听 `127.0.0.1:18083`；frpc 四条代理（2 https + 2 tcp），TCP 段不增加设备监听 |

### 12.4 回滚

**隧道（回 443）**：删除 `frpc.toml` 末尾两段 `type="tcp"` → `frpc verify -c /etc/frp/frpc.toml` → `supervisorctl restart haydn-frpc`；原两条 https 一直在，DNS 未改。文件级恢复：`cp /data/server/backups/frpc.toml.20261114T142644Z /data/server/rootfs/etc/frp/frpc.toml`。

**Forgejo**：

```sh
su -c "/data/server/bin/chroot-enter.sh /usr/bin/supervisorctl -c /etc/supervisor/supervisord.conf stop haydn-forgejo"
su -c "rm /data/server/rootfs/etc/supervisor/conf.d/haydn-forgejo.conf"
su -c "/data/server/bin/chroot-enter.sh /usr/bin/supervisorctl -c /etc/supervisor/supervisord.conf reread && \
       /data/server/bin/chroot-enter.sh /usr/bin/supervisorctl -c /etc/supervisor/supervisord.conf update"
# 网关：先备份 gateway.json，再把 /git 这条 upstream 的 enabled 改 false（或删除），重启网关
su -c "cp /data/server/rootfs/etc/haydn-console/gateway.json /data/server/backups/gateway.json.bak-\$(date -u +%Y%m%dT%H%M%SZ)"
su -c "/data/server/bin/chroot-enter.sh /usr/bin/supervisorctl -c /etc/supervisor/supervisord.conf restart haydn-console-gateway"
```

数据保留在 `/srv/haydn/forgejo`（不随回滚删除）；二进制可重建，删除不影响数据。

### 12.5 已知限制

1. 域名入口公网不可用（备案按 SNI 判定拦截，见 §12.2 与 frp §11.4）：**非标端口同样受影响**，仅按 IP 直连（不带域名 SNI）稳定可用。
2. `START_SSH_SERVER=false`，只支持 HTTPS clone，无 SSH 方式。
3. 未配置 SMTP（`ENABLE_NOTIFY_MAIL=false`，`[mailer]` 为空），口令找回/邮件通知不可用（管理员可重置）。
4. 数据已纳入定时备份（`forgejo-backup-*`，见 §11）。
5. 未启用 2FA，登录限流沿用 Forgejo 默认值。

## 13. 服务入口、凭据导出与轮换（2026-11-14）

### 13.1 服务入口

控制台首页"服务入口"由服务端配置注入，模板不含任何地址：

| 项 | 位置 |
|---|---|
| 配置键 | `gateway.json` → `entries[]`（`name` / `url` / `note`） |
| 接口 | `GET /console/api/entries`（登录后） |
| 占位符 | `{lan_ip}`、`{lan_port}`、`{lan_root}`、`{public_host}` 由服务端按当前配置与探测结果替换 |
| 改端口/改地址 | 只改 `entries`（或 `lan.listen`）一处，无需改代码/模板 |

默认覆盖（2026-11-15 调整后 7 条）：控制台 `/console/`、WebDAV `/dav/`、Forgejo `/git/`、Vaultwarden `https://8.137.162.154:60177/`、Prometheus `/console/api/metrics`、Netdata `/netdata/`、AList `/alist/`。原"主站 `/`"与"局域网省流 `{lan_root}/console/`"两条已移除：`/` 改为 302 到控制台（判定见 §13.6），局域网切换只保留 §10 的一次性票据按钮。未探测到局域网地址时对应入口显示"当前不可用"而不是死链。

**入口地址口径（2026-11-15）**：`entries[]` 不展示任何域名入口（`qingxuan.bbs0.cc` / `vault.qingxuan.bbs0.cc` 公网不可用，见 §12.2；隧道保留仅作回滚）。主站/控制台/WebDAV/Forgejo 用站内相对路径，随当前 origin 解析——公网即 `https://8.137.162.154:60875/...`，局域网即 `http://<lan_ip>:18090/...`，不写死主机；Vaultwarden 固定 `https://8.137.162.154:60177/`。设备侧配置中仅 `cert_file` 与 `NODE_EXTRA_CA_CERTS` 保留域名（是证书文件路径，不是入口）。

**已核验（2026-11-15）**：`GET /api/entries` 返回 7 条且 `available` 全为 True（第 6 条 Netdata 见 §16，第 7 条 AList 见 §17）；指标入口为站内相对路径 `/console/api/metrics`（登录后可看，经控制台代理 `127.0.0.1:9100`，不新增对外端口）；`/api/lan` 返回 `public_root=https://8.137.162.154:60875`，用于"当前入口"展示。

### 13.2 凭据定义（单一事实来源）

`gateway.json` → `credentials.services[]` 是唯一凭据定义；**CSV 导出与密码库条目都由它生成**，不另写一套。每条含 `id`、`name`、`username`、`login_uri`、`rotate`、明文来源（`plain_file` 或 `account_file`）、`notes`。

- CSV 表头：`folder,name,login_uri,login_username,login_password,notes`（Bitwarden 可直接导入），folder 固定 `haydn-server`。
- 明文只在设备侧 600 文件；页面与接口不返回完整口令（轮换结果除外，且只展示一次）。
- 当前 7 条：控制台、WebDAV、Forgejo、Vaultwarden 主密码、Vaultwarden 管理令牌、AList 管理员、设备 root/su（仅提示，不保存口令）。
- 新增 `rotate:"alist"` 模式：`alist admin set <新口令> --data /opt/alist/data` → `supervisorctl restart haydn-alist`（进程缓存口令哈希，不重启不生效）→ 直连 loopback `POST /alist/api/auth/login` 校验 `code=200` 并轮询最多 10 秒；失败按快照回滚（§17.3）。

### 13.3 下载（一次性令牌）

1. 控制台点"下载凭据 CSV"→ `POST /console/api/credentials/token`（CSRF 校验）签发一次性令牌，TTL 120 s。
2. 浏览器随即请求 `GET /console/api/credentials/download?t=<token>`：令牌在校验时即被消费，**同一链接第二次访问返回 410**。
   - 跳转必须直接用接口返回的 `path`（已含 `/console` 前缀）；前端再拼一次前缀会请求 `/console/console/api/...`，返回 `{"error":"unknown console endpoint"}`（2026-11-15 已修：`console_ui.py` 改为 `location.href = d.path`）。
3. 服务端在 `credentials.export_dir` 生成 600 临时文件后立即删除，仅流式返回；审计只记文件名与行数，不记内容。
4. 命令行导出（供 `adb pull`）：`gateway.py --export-credentials <path>`，文件 600、内容含明文，复制到本机后应删除。

本机副本曾位于仓库外的 `inventory/haydn-credentials.csv`（`/inventory/*` 已被 `.gitignore` 忽略，未进入 git）；**2026-11-15 已按用户要求删除**（导出入口保留，需要时重新下载），设备侧持久副本此前已删除。

**已核验（2026-11-14 重建账号后重新导出）**：令牌签发 200 → 下载 200 / 1208 B / `text/csv`；二次访问同一令牌 410；CSV 6 行、6 列、表头正确；"Vaultwarden 主密码"行口令长度 32 且与 `/opt/haydn/secrets/vaultwarden-master.txt` 逐字一致；设备侧 `/srv/haydn/run/haydn-credentials.csv`、旧 `/tmp/console-credentials.csv` 与 `/data/local/tmp` 暂存副本均已删除；`git status` 不含该文件（`inventory/` 被忽略）。

> 设备侧不保留明文 CSV：导出只在内存中生成并流式返回；命令行路径 `gateway.py --export-credentials <path>` 如需使用，拉到本机后应立即删除该文件。

### 13.4 轮换（按钮化）

流程（任一步失败按快照回滚并如实报错）：

```
生成新口令（默认 24 位）
  → 写入服务凭据文件（600）+ 更新明文文件
  → 重载/回读对应服务
  → 真实协议验证（控制台 POST 登录；WebDAV PROPFIND；Forgejo /api/v1/user）
  → 一次性返回新口令（页面展示 120 s，可复制）
  → 写密码库条目（见 13.5；失败明确报错且保留一次性口令）
  → 更新轮换时间戳（/etc/haydn-console/credential-state.json，600）
```

**状态口径（"当前值"，2026-11-15）**：`credential-state.json` 为每个服务分开记两件事，页面也分成两列：

| 列 | 状态键 | 语义 | 刷新时机 |
|---|---|---|---|
| 上次轮换（服务验证） | `rotation={at,ok,error}` | 最近一次按钮轮换是否通过服务侧验证 | 仅 `POST /api/rotate` 成功/失败时写；CLI 改口令不写 |
| 密码库同步 | `vault={at,ok,skipped,error}` | 最近一次写库/同步的结果（"当前"语义） | 每次 `--vault-sync` 与轮换后的写库步骤都会刷新，**成功即清除历史失败标记** |

- 失败只展示原因摘要（如"写库客户端不可用""缺少主密码文件""写库登录失败"），由 `vault_reason()` 折叠底层错误，**不含口令与条目内容**；`skipped` 单独显示为"未写入 + 原因"（如 `device-root` 的"设备侧无明文口令"）。
- 旧状态文件里的字符串 `vault`（`ok`/`fail`/`skipped`）仍可读，`summary()` 会兼容并给出空 `vault_at`，下次同步后自动改写为新结构。
- 轮换按钮改为**页内两步确认**（首击变"确认轮换"，5 秒内再击执行）：原生 `confirm()` 被浏览器"阻止此页面创建更多对话框"后会静默返回 false，表现为点击完全没反应；失败时在 `#cred-msg` 显示 `error` 摘要与失败步骤（不含口令），成功则刷新时间戳并展示一次性口令。

| 服务 | 方式 | 已验证 |
|---|---|---|
| 控制台 | 重写 `secret.json` + 进程内热重载口令（不重启网关）+ 新口令登录 200 | 是（旧口令 401，新口令 200） |
| WebDAV | 写 `webdav.json` + `webdav-password.txt`，经网关 Basic PROPFIND | 是（207） |
| Forgejo | `forgejo admin user change-password --must-change-password=false`（以 git 身份）+ API Basic 校验 | 是（200） |
| Vaultwarden 主密码 | 不支持服务端轮换 | 见 13.5 |
| Vaultwarden 管理令牌 | 仍用 `deploy/rotate-secret.sh vaultwarden`（会重启 Vaultwarden） | 未在本轮改动 |

回滚：控制台/WebDAV 恢复旧 `secret.json` 与旧明文文件；Forgejo 在已知旧明文时改回，否则明确报"回滚未完成（旧明文未知，请人工核对）"。

**注意**：本轮端到端验证实际轮换了 WebDAV、Forgejo、控制台三个口令（旧口令已失效），新口令在导出的 CSV 里；控制台自身口令同时写入 `/etc/haydn-console/admin-password.txt`。

### 13.5 Vaultwarden：端到端加密，服务端不能代改条目

**Vaultwarden 条目的内容由客户端加密后上传，服务端只保存密文**。因此设备侧（包括本控制台与 `bw` 客户端脚本）**无法修改条目内容的明文语义**——它能做的是按条目名更新 `login.password` 字段的密文（需用户主密码解锁会话），但**当主密码未知时，只能由用户在客户端里粘贴新口令**。控制台对"Vaultwarden 主密码"条目不提供轮换按钮；轮换其他服务后，如果密码库条目未能更新，页面会明确报错并保留新口令的一次性展示，避免"服务已换、密码库还是旧的"。

当前状态（**阻塞已解除，2026-11-14 重建账号后已核验**）：

| 项 | 事实 |
|---|---|
| 库用户 | 1 个：`admin@haydn.local`（旧账号与其数据已删除后重新注册；库内无历史条目） |
| 主密码文件 | `/opt/haydn/secrets/vaultwarden-master.txt`（600，root only；`email=` + 32 位随机 `password=`） |
| 注册入口 | 重建时临时开 `SIGNUPS_ALLOWED`，完成后已恢复并回读 `/api/config` 确认 `disableUserRegistration=true`；旧 `vaultwarden-initial-account.txt` 已删除 |
| 写库开关 | `credentials.vault.enabled=true`（设备侧 `/etc/haydn-console/gateway.json`） |
| 客户端 | `bw` 2026.10.1：`/opt/haydn/bwnew/node_modules/.bin/bw`（Node 24 在 `/opt/node24`，经 `extra_path` 注入）；服务端走既有 stunnel `https://127.0.0.1:18445`（新 CLI 拒绝 http），用 `NODE_EXTRA_CA_CERTS` 显式信任证书，未关闭全局校验 |
| 非交互路径 | `bw login <email> <主密码> --raw`（已登录则跳过 `config server`）→ `bw unlock <主密码> --raw` → `BW_SESSION` → `bw create/edit item <base64 JSON>` → 每条 `bw get item` 回读比对 → `finally bw lock` |
| folder | `haydn-server`（id `1a9d5c5d-15d3-45e3-8598-34006e15377f`），5 条条目（`device-root` 无明文口令，跳过） |

**已核验的写库与轮换**：

- `gateway.py --vault-sync`：`console/webdav/forgejo/vaultwarden/vaultwarden-admin: ok`、`device-root: skipped`、`vault_sync: ok`；独立回读 5 条 `password_match: True`。
- 轮换回归（WebDAV）：`steps=[写入凭据文件 True, Basic 验证 True, 写入密码库 True]`，一次性口令 24 位，库内条目与新口令一致。
- 回滚回归：停 `haydn-webdav` 后轮换 → 400、`ok:False`、`rolled_back:True`；恢复服务后旧口令仍 207。
- 写库失败回归：`vault.client=/bin/false` → 轮换 200、`写入密码库 False`、`vault_error: 设置服务器地址失败`、`password_present:True`（一次性展示保留）；还原配置后重新 `--vault-sync` 对齐。
- 状态口径与现状纠正（2026-11-15）：16:16Z 两条红色"失败"来自被中断的写库实验；`--vault-sync` 复跑后 `console/webdav/forgejo/vaultwarden/vaultwarden-admin: ok`（`vault_at` 16:54–16:55Z）、`device-root: skipped`，页面"密码库同步"列显示"已同步 + 时间"，历史失败标记清除；独立回读 5 条 `password_match` / `username_match` 全 True、无重名。
- WebDAV 专项（2026-11-15）：库内"Haydn WebDAV"条目的 `login.username` / `login.password` 与设备当前生效（`webdav.json` 的 user + `webdav-password.txt` 明文）**逐字符一致**；`auth.verify_password` 通过，`PROPFIND /dav/` 返回 207。
- 轮换实测（2026-11-15）：`POST /api/rotate {service:"forgejo"}` → 200、`steps` 三项全 True、`rotated_at` 16:51:21Z、库内条目同步；`{service:"device-root"}` → 400 + "该服务不支持服务端轮换（见说明）"，界面显示失败原因而非无反应。
- 另记（事实，未归因）：16:47:34Z 控制台 `secret.json` 与 `admin-password.txt` 被改写（哈希校验通过），审计日志无对应 `credentials.rotate`，属 CLI 改口令路径；随后 `--vault-sync` 已把库内控制台条目对齐（`vault_at` 16:54:42Z）。

密码库为**本服务器专用**（只放服务凭据），不存放个人账号；主密码与解锁会话不写入日志、不进仓库、不在页面完整展示。

### 13.6 配置与回滚

- 新增配置块：`entries[]`、`credentials{...}`（设备侧已合并进 `/etc/haydn-console/gateway.json`，合并前备份为 `gateway.json.bak-<ts>`）。
- 源码：`console/console_credentials.py`（新增）、`console/gateway.py`、`console/console_ui.py`、`console/config.example.json`。
- 回滚：恢复 `gateway.json.bak-<ts>`，把 `console/*.py` 换回旧版，`supervisorctl restart haydn-console-gateway`；轮换后的服务口令仍以设备侧 600 文件为准（回滚代码不等于回滚口令）。
- 未重启整机，未改 frpc/stunnel/证书。

### 13.7 主站判定、入口去重与指标代理（2026-11-15）

- **主站判定（只读实测）**：`GET /` 经网关落到 `127.0.0.1:18081`，响应 302 字节占位页（"haydn lab chroot" 自检页，正文声明不对局域网/公网开放），无实际内容 → 删除"主站"入口，并把 `/` 改为 **302 → `/console/`**；静态站保留为"未匹配路径"的兜底上游（回滚即恢复 `gateway.json` 旧备份）。
- **入口去重**：`entries[]` 移除"局域网省流入口"，局域网切换只保留页面顶部带一次性票据的按钮（`{lan_root}` 占位符仍可供其他入口使用）；调整后共 5 条。
- **当前入口**：不再回显 `location.host`；局域网显示 `/api/lan` 的 `lan_url`，公网显示配置的 `public_root`（`https://8.137.162.154:60875`），失效域名不会出现在面板里。
- **Prometheus 指标**：`node_exporter` 仅绑 `127.0.0.1:9100`，iptables `INPUT` 默认 DROP 且无 9100 放行（LAN 访问为超时而非拒绝）。按"不新增暴露面"原则，入口改为站内 `/console/api/metrics`：会话鉴权后由网关代理 loopback 采集，未登录 401、登录后 200 `text/plain`；未改绑定地址、未加 iptables 规则。
- **交互统一**：服务启停（start/restart/stop）与备份按钮改为页内两步确认（`armConfirm()`，5 秒窗口），`stop` 写明"立即中断直到 start"、`restart` 写明"短暂中断数秒"；执行中与执行结果（成功/失败原因摘要）均写入 `#svc-msg` / `#backup-msg`。实测只重启了可控目标 `haydn-local-http`（返回 `stopped / started`，状态 RUNNING），未触碰网关、隧道或备份管线。

### 13.8 控制台自轮换与会话、局域网切换按钮上移（2026-11-15）

- **时间戳停更的现状**：`credential-state.json` 里 `console` 只有旧 `rotated_at=16:16:18Z`，没有任务 D 之后才引入的 `rotation` 字段——说明这期间没有一次走到状态写入的轮换；本次实测（新代码）`POST /api/rotate {service:"console"}` → 200，`steps=[写入凭据文件 ok, 回读 ok, 登录验证 ok, 写入密码库 ok]`，`rotation.at=17:21:17Z`、`rotation.ok=true`、库内条目同步，页面刷新后该行时间随之为新值。
- **失败必留痕**：`rotate()` 的兜底异常由 `RotationError` 放宽为 `Exception`，任何写入/回读/验证异常都会回滚并写 `rotation={at,ok:false,error}`（摘要截断 120 字符，不含口令），接口返回 400；页面在 `#cred-msg` 显示 `error` 与失败步骤。失败路径实测：`{service:"device-root"}` → 400 + "该服务不支持服务端轮换（见说明）"。
- **会话不被踢出**：控制台轮换只替换 `secret.json` 的 `password`/`updated`，`session_key` 保持不变；实测轮换后同一 cookie 请求 `GET /api/status` 仍 200。页面在成功后明确提示"控制台登录口令已更新，当前会话保持有效；下次登录请使用下方一次性口令"，一次性口令框同时展示。
- **局域网切换按钮上移**：按钮移到页面顶部"局域网省流入口"卡片，底部"访问入口（公网 / 局域网）"只保留信息网格（当前入口/局域网地址/探测时间/同网段判定），全页唯一 `id="lan-go"`；非同一网段时按钮保留但 `disabled` 并写明原因（不再直接隐藏），同网段判定、文案与一次性票据跳转逻辑未改。
- 本轮控制台自身口令已再次轮换（`17:21:17Z`），新口令同时写入 `/etc/haydn-console/admin-password.txt`（600）与库内 `Haydn 控制台` 条目；未重启整机、未改 frpc/stunnel/证书。

### 13.9 轮换时间就地刷新与时间显示、移除凭据文件/日志面板（2026-11-15）

- **"时间没变"定位（已核验）**：审计 `/var/log/haydn/console-audit.log` 中 `credentials.rotate` 记录显示 webdav `17:24:23Z`、forgejo `17:23:44Z` **均到达服务端且 `result=ok`**，`credential-state.json` 对应条目 `rotation.at` 已写入 → 属"请求到了、状态也写了，只是页面没有重新拉取"，不是服务端丢写（webdav 那次仅"写入密码库=fail"，重跑 `--vault-sync` 后 `vault=ok`）。
- **前端就地刷新**：`rotate()` 成功分支调用 `patchCredRow()` 就地改写该行（轮换时间/验证/密码库三列），随后 `loadStatus()` 兜底；失败分支同样 `loadStatus()`，让"失败+时间"可见；`api()` 统一加 `cache:'no-store'`。实测：`POST /api/rotate {service:"console"}` → 200、`rotated_at` 前 `17:21:17Z` → 后 `17:30:17Z`、`rotation.ok=true`、`vault=ok`，同一会话 `GET /api/status` 该行已为新值（`changed: True`）；失败路径 `{service:"device-root"}` → 400 + 原因。
- **时间显示**：服务端仍是 UTC（`Z`），页面统一经 `fmtTs()` 转本地时间并标注时区（如 `2026-11-15 01:30:17（UTC+08:00）`），UTC 原值保留在 `title` 悬浮提示，避免把 UTC 误读成本地时间。
- **移除两个区块**：删除"凭据文件（仅存在与权限）"表格与"日志"面板，连同只服务它们的 `GET /api/log`（`_api_log`）、`/api/status` 的 `secrets`/`logs` 字段、`actions.secrets_summary()`、配置项 `secrets_dir`；`logs` 映射保留，仅用于 `--check-config` 打印文件路径与存在性。页面其余区块（局域网省流入口、服务入口、服务启停、概览、访问入口、遥测与 soak、凭据与轮换、备份）不变。
- **依赖确认**：仓库内新控制台仅 `console_ui.py` 用过 `/api/log`（本轮已删）；`scripts/server/webui/app.py` 是冻结的旧系统、自带 `/api/logs`，不依赖新网关；`inventory/console-selftest.py`（gitignored 的本地自测脚本）仍引用 `/console/api/log`，属**测试脚本非运行时依赖**，需要时随接口变更另行更新。
- **日志改在设备直接看**（chroot 内路径；从 adb shell 访问需加前缀 `/data/server/rootfs`，`--check-config` 实测 12 个路径均 `exists=True`）：
  - 审计：`/var/log/haydn/console-audit.log`（JSONL，含 `credentials.rotate`/`service`/`log.read` 历史）
  - 网关/进程：`/srv/haydn/logs/supervisord.out`、`/var/log/haydn/http.log`、`/var/log/haydn/tls.log`、`/var/log/haydn/frpc.log`、`/var/log/haydn/health.log`
  - 业务：`/srv/haydn/logs/webdav.log`、`/srv/haydn/logs/forgejo.log`、`/srv/haydn/logs/alerts.log`
  - 任务：`/srv/haydn/logs/backup.log`、`/srv/haydn/logs/backup-loop.out`、`/srv/haydn/logs/telemetry-loop.out`、`/srv/haydn/logs/telemetry.csv`
- **移除后实测**：页面 200（`log-body`/`log-name`/`secrets`/`renderSecrets`/`loadLog` 均不存在）；`GET /api/status` 200 且键为 `services/overview/telemetry/soak/cert/credentials/backup/now/ok`；`/api/log` 与 `/api/secrets` 均 404；服务入口 5 条 `available` 全 True；`POST /api/service` restart `haydn-heartbeat` 200（`stopped / started`）；`/api/lan` 200（`192.168.31.0/24`）、`/api/backup` 200、`/api/metrics` 200（187685 B，含 `node_` 指标）、凭据令牌 200 → 下载 200 / 1208 B / 6 行；局域网监听 `http://192.168.31.50:18090/console/` 登录页 200。
- **部署与回滚**：`console_ui.py`/`gateway.py`/`console_actions.py` 覆盖到 `/opt/haydn/console/`（644）、chroot `py_compile` 通过、`--check-config` 退出 0，仅 `supervisorctl restart haydn-console-gateway`（未重启整机、未改 frpc/stunnel/证书）；回滚为恢复旧三个 `.py` 并重启网关，设备 `gateway.json` 里的 `logs`/`secrets_dir` 键留着也不影响运行。

### 13.10 凭据"查看口令"与概览/遥测合并（2026-11-15）

- **查看口令（新增只读接口）**：`POST /console/api/credential/reveal`，JSON `{"service":"<id>"}`，仅登录态 + `X-Haydn-Client`/Origin 同源校验可用；响应 `Cache-Control: no-store`，不写文件、不缓存。口令按服务定义取设备侧明文（`plain_file`，Vaultwarden 走 `account_file` 的 `password=` 行），`device-root` 无明文 → 400。每次调用写审计 `credentials.reveal`（`ts/action/target=服务名/result/detail=文件路径/peer=来源地址`），**不含口令内容**。
- **页面交互**：`has_password=true` 的行显示"查看"按钮（默认不展示口令），点击后就地插入一行 `#cred-services` 下的等宽 `<code>` + "复制"按钮（`navigator.clipboard`，失败回退 `execCommand`），再次点击"收起"移除该行；Vaultwarden 主密码查看前复用 `armConfirm()` 做一次 5 秒页内确认；`device-root` 行无按钮。原"下载凭据 CSV（一次性链接）"逻辑未改。
- **实测（已核验）**：console/webdav/forgejo/vaultwarden/vaultwarden-admin 五次 `reveal` 均 200 且与设备文件逐字符一致（脚本内比对，不打印口令），响应头 `no-store`；`device-root` → 400"该服务在设备侧没有可读取的明文口令"；无会话 → 401；审计新增 5 条 `ok` + 1 条 `refused`（`peer=127.0.0.1`），对追加区做子串检查确认**未出现任何口令**。
- **概览/遥测合并**：两张卡片并为"概览与设备遥测"，上层主机资源（`运行时长（主机）`、负载 1/5/15、内存、磁盘、证书剩余），下层设备遥测（最后采样+样本数、电池与状态、温度、服务可用率、重启次数）；`负载` 只在主机层出现一次；soak 改为卡片底部独立状态行，文案为"本轮 soak：起点/已运行/剩余/样本"，与"主机运行时长"口径分开；放电中与可用率 <100% 用 `warn` 黄色，证书 <21 天沿用 `warn`；卡片保留"只展示观测值，不判定验收通过"。数据全部来自现有 `/api/status`（`overview/telemetry/soak`），未新增采集。
- **实测**：`/api/status` 200，键仍为 `backup/cert/credentials/now/ok/overview/services/soak/telemetry`；`overview.load=[3.07,3.18,3.29]`、`uptime=17062.46`；`telemetry.samples=327`、`availability=98.17`、`reboots=11`、最后采样含 `batt_level/batt_status/batt_temp_raw`；`soak.elapsed=16969`、`remaining=69430`、`samples_since_start=56`；页面含"概览与设备遥测/主机资源/设备遥测/运行时长（主机）/本轮 soak/只展示观测值，不判定验收通过"，且不再含"遥测与 soak"与重复负载渲染。其余接口回归：入口 5 条全可用、`/api/lan` 200、`/api/backup` 200、`/api/metrics` 200（187661 B 含 `node_`）、restart `haydn-heartbeat` 200、`/api/rotate` 失败路径 400、CSV 令牌 200。
- **部署与回滚**：`console_ui.py`/`gateway.py` 覆盖 `/opt/haydn/console/`（644）、chroot `py_compile` 通过、`--check-config` 退出 0，仅重启 `haydn-console-gateway`；回滚为恢复旧两个 `.py` 并重启网关。页面内联 JS 另用 `node --check` 做过语法校验。

### 13.11 走读修复与运行环境加固（2026-11-15，阶段二）

- **H1 WebDAV 验证恒真**：`_verify_basic()` 原来直连 `127.0.0.1:18082`，而 rclone 没有启用 `--user/--pass`，对任意 Authorization 都回 207，等于"轮换验证永远通过"。改为经网关 `http://127.0.0.1:18080/<prefix>/` 做 `PROPFIND`（`Depth: 0`）：200/207 通过、401/403 失败。实测：正确口令 → `(True, '')`；错误口令 → `(False, '网关拒绝新口令（HTTP 401）')`；直连 18082 仍回 207（保留为根因证据）。
- **H2 最后采样时间**：`/api/status` 的 `telemetry.last` 里没有 `ts`，页面取 `tel.last` 的时间恒为空。改用顶层 `last_ts` 并统一 `fmtTs()`；`null` 一律显示 `—`（内存/磁盘/电池/重启次数/可用率/soak 剩余）。
- **H3 Vaultwarden 登录回路**：`DOMAIN` 原为不可达的 `https://vault.qingxuan.bbs0.cc`，Web 客户端按该地址拼 API 会断。备份后改为 `https://8.137.162.154:60177`，重启 `haydn-vaultwarden`；实测公网 `60177/api/config` 200 且 `environment.{api,identity,notifications}` 均为新地址。
- **M8 Forgejo 外部地址**：`app.ini` 的 `ROOT_URL` 改为 `https://8.137.162.154:60875/git/`（`DOMAIN=8.137.162.154`），重启后日志回显 `AppURL(ROOT_URL): https://8.137.162.154:60875/git/`，经网关页面内链接已使用新地址；`app.ini` 保持 `600 999:993`（`sed -i` 后重新 `chown`）。
- **服务保护**：`gateway.json` 的 `supervisor.protected = [haydn-frpc, haydn-tls, haydn-sshd]`；`service_action()` 对 `stop` 返回 `refused`，`/api/status` 每行带 `protected`，页面把停止按钮置灰并在区块底部说明"承载公网入口/远程登录，仅允许重启，设备侧仍可维护"。实测三个服务 `stop` 均为 400 + 原因。
- **登录/会话/同源**：`/api/logout` 补 `X-Haydn-Client`/Origin 校验（无头 403）；`_api_login` 改为**先验口令、失败才记限流**（正确口令永不被匿名尝试锁死，无 record 时 503 + `Retry-After: 1`）；`/console/lan-probe` 不再回传 `lan_ip/lan_subnet/client_ip/listener/updated_at`，未登录 403（实测响应体仅 `{"ok":false,"error":"forbidden"}`）。
- **代理与会话隔离**：向上游转发前剥离 `haydn_session` cookie（`/dav`、`/git`、WebSocket 隧道一致）；`X-Forwarded-Proto` 按 `lan_mode` 取 `http/https`；请求体上限 2 MiB，`/dav` 64 MiB（路由可覆盖 `max_body_bytes`），超限 413 + 审计 `request.body`，分段编码超限同样显式抛错。
- **凭据并发与密码库**：状态写盘加 `RLock` + 每线程临时文件；`secret` 热加载改为整体替换（消除 `clear()` 窗口）；`bw login/unlock` 改用 `--passwordenv`，主密码不进 argv；Vaultwarden 重启后客户端可能先报"未登录"，`_vault_session()` 增加一次 login+unlock 重试（实测 `--vault-sync` 6 条中 5 ok / 1 skipped，`vault_sync: ok`）。
- **页面口径**：错误/成功消息不再被轮询覆盖（确认态在 5 秒窗口内保持文案、展开的口令行刷新后不丢、轮换成功即清本地展开态）；`renderStatus()` 刷新失败时显示"本次刷新失败，上方数值可能已过期"；证书过期显示 `已过期 N 天`；soak 起点与备份时间均转本地时间并标注时区。
- **运行环境**：
  - 权限：`/var/log/haydn`、`/srv/haydn/logs`、`/srv/haydn/run` 由 777 收紧为 755；`console-audit.log`、`heartbeat.csv`、`telemetry.csv` 为 640。
  - 轮转：`/etc/logrotate.d/haydn` 保持 `*.log` 周轮转并加 `maxsize 10M`；新增 `/etc/logrotate.d/haydn-csv` 对 `*.csv` 日轮转（`copytruncate` + `maxsize 20M`）。`logrotate -d` 解析无 duplicate/error。
  - 水位与自恢复：`haydn-healthcheck.sh` 新增内存水位（`MemAvailable/MemTotal < 10%` → `mem_Npct`），磁盘沿用 `stat -f` 的 ≥90% 口径；对 `STOPPED/FATAL/BACKOFF/EXITED` 且**无** `/srv/haydn/run/.stopped-<svc>` 标记的服务执行一次 `supervisorctl start`，并记 `RECOVER <svc>`。标记由控制台 `service_action()` 维护（stop 写入、start 删除）。
  - supervisor 配置：设备侧 `haydn-forgejo.conf` 与仓库一致（含 `environment=`），此前 791B/876B 漂移已消除。
  - 告警判据修正（2026-11-15）：`04:56:21Z FAIL supervisor` 来自人工停止演练——`haydn-heartbeat` 于 `04:56:21.357Z` 被 `supervisorctl stop`、`04:56:38.353Z` 才重新 start，期间 `.stopped-haydn-heartbeat` 标记存在，旧判据 `grep -E 'FATAL|BACKOFF|STOPPED|EXITED'` 把“预期的人工停止”也算成故障（控制台审计无对应请求，属设备侧手工演练；v1.83 记录“实测 RECOVER/跳过”）。改为用 `awk '$2'` 精确取状态列：`FATAL/BACKOFF/EXITED` 一律算故障，`STOPPED` 仅**无**标记才算；实测「标记 + 停止 → `OK` 且不拉起」「去标记 → `RECOVER` 并拉起」「伪造 `FATAL` → 仍 `FAIL supervisor`」；回滚 `/data/server/backups/healthcheck-20261115T055821Z/`。`health.log` 以 chroot 内 `/var/log/haydn/health.log` 为准（宿主 `/data/server/rootfs/var/log/haydn/health.log`），不在 `/srv/haydn/logs/`。
- **实测（阶段二）**：`/console/` 200、登录 200、`/api/status` 200（`protected` 三行）、无会话 `lan-probe` 403 且无网段泄露、无头 `logout` 403、三个链路服务 `stop` 400、3 MiB 请求 → 413、心跳 stop/start 标记按预期写入/删除、`sleep 3` 后 `haydn-console-gateway RUNNING`。回滚：`/data/server/backups/console-p2-*`（四个 `.py` + `gateway.json`）、`/data/server/backups/p2-runtime-*`（healthcheck + logrotate）、`/data/server/backups/p2-upstream-*`（`vaultwarden.env` + `app.ini`）。

## 14. 新服务接入（一页）

新增一个上游（示例：`/pad`）**不用改代码**，只动配置与三处运维项。全程保持单槽运行，只重启受影响的服务。

1. **上游进程**：写 `/etc/supervisor/conf.d/haydn-<name>.conf`（照抄现有文件结构：`command` 只用绝对路径、`stdout_logfile` 放 `/srv/haydn/logs/<name>.log`、`environment=` 里的变量一行一个、`autostart/autorestart=true`），然后 `supervisorctl -c /etc/supervisor/supervisord.conf reread && update`，再用 `status <name>` 确认 `RUNNING`。
2. **路由**：在 `/etc/haydn-console/gateway.json` 的 `upstreams` 追加一条
   `{"name":"<name>","path":"/pad","upstream":"127.0.0.1:18085","auth":"none","strip_prefix":true}`。
   `path` 决定对外前缀；上游若以 `--baseurl /pad` 自服务则 `strip_prefix` 设 `false`；需要 Basic 时 `auth:"basic"`（网关校验，上游不要再配一份）。
3. **入口与凭据**：`entries` 加展示项（`{title,url,desc}`，公网地址用 `{public_root}` 占位），`credentials.services` 加一条（`id/name/login_uri/plain_file 或 account_file`，`secret_file` 指到 `/etc/haydn-console/secrets/<name>.json`），`credentials.services` 之外不要写口令。
4. **启停白名单**：`supervisor.services` 加 `<name>` 才会出现按钮；承载公网入口/远程登录的服务加进 `supervisor.protected`（只允许重启）。
5. **运维三件套**：
   - 日志：`/srv/haydn/logs/<name>.log` 已被 `/etc/logrotate.d/haydn`（`*.log`）覆盖；若是 CSV/JSONL 明细，放进 `/srv/haydn/logs/*.csv` 或另加规则，避免与现有 glob 重复（logrotate 会报 duplicate）。
   - 健康：在 `haydn-healthcheck.sh` 增加一条 `curl -fsS -m 5 http://127.0.0.1:<port>/<health>`，失败写 `FAIL <name>`；异常退出会被自动拉起，控制台主动停止请走页面（写 `.stopped-<svc>` 标记）。
   - 备份：数据目录若需进备份，参考 `backup-vaultwarden.sh` 的 SQLite 一致性快照写法，在 `haydn-backup.sh` 里加一次 `process_archive <archive> "<label>"`，并补进"恢复演练"记录。
6. **落地顺序**：`--check-config` 退出 0 → 仅 `supervisorctl restart haydn-console-gateway` → 浏览器无痕窗口验证登录、入口、启停、`/api/status`；回滚是还原 `gateway.json` 备份并重启网关。

### 14.1 界面语言（服务端默认 vs 用户级）

- **Forgejo（服务端默认中文，已核验）**：`app.ini` 的 `[i18n]` 必须同时给 `LANGS` 与 `NAMES`（只写 `LANGS` 会让进程启动时 panic：`index out of range`）。当前配置 `LANGS = zh-CN,en-US` / `NAMES = 简体中文,English`——**第一项即默认语言**。实测无 `Accept-Language` → `<html lang="zh-CN">`；`zh-CN` → `zh-CN`；`en-US` → `en-US`。已登录用户仍可在个人设置里切换，优先级高于浏览器。
- **Vaultwarden（无服务端开关，只能在客户端选）**：官方 Web 保险库不带服务端语言配置，语言存在用户/浏览器侧。可用中文已随包提供（`/opt/haydn/vaultwarden-web-vault/locales/zh_CN`）。操作路径：登录 Web 保险库 → 右上角账号菜单 → **Account settings**（账户设置）→ **Options**（选项）→ **Language**（语言）→ 选择 **中文/简体中文** 并保存；只影响当前账号，换浏览器需再选一次。CLI（`bw`）语言由终端环境决定，服务端口令轮换不依赖界面语言。

### 14.2 备份覆盖面与恢复入口

- **覆盖面**：`haydn`（整机配置/代码，排除可重建大二进制）、`forgejo`（`forgejo.db` + `repositories/` + `data/` + `app.ini`）、`vaultwarden`（`db.sqlite3` + `rsa_key.pem` + attachments + sends），三份各自加密上传，各保留 7 份；每日由 `backup-loop.sh` 触发，也可在控制台点"立即备份"（写触发文件）。
- **恢复入口**：从夸克网盘取回 `<label>-backup-*.tar.gz.enc` 与 `.sha256` → 设备上 `python3 /opt/haydn/haydn_crypt.py decrypt <enc> <tar.gz> /root/.haydn-backup-pass` → `sha256sum` 对齐 → 解包到暂存区 → 按来源放回：Forgejo 的 `forgejo.db` 需 `chown 999:993 && chmod 644`（`app.ini` 保持 `600 999:993`）、Vaultwarden 的 `rsa_key.pem` 需 `600 997:992`。恢复演练口径见 §11（解密/解包/库完整性/权限已核验，未做独立实例的真实登录回归）。

## 15. WebDAV 浏览器界面（2026-11-15，中文 + 常用操作）

`/dav` 由 rclone 提供，自带目录页为英文且无语言开关。做法是**网关只替换浏览器看到的那一个 GET**，其余请求与方法照旧透传，WebDAV 协议语义不变。

### 15.1 触发条件与不变量

- 新模块 `console/webdav_ui.py`（内联 HTML/CSS/JS，无外部资源）；网关在以下条件**全部**满足时返回它，否则原样代理给 rclone：
  1. 该路由配置了 `"browser_ui": {"title": "…"}`（缺省不启用）；
  2. 方法为 `GET` 或 `HEAD`；
  3. 路径严格等于该路由前缀根（`/dav/`，子目录与文件不受影响）；
  4. 请求头 `Accept` 含 `text/html`（浏览器会带；WebDAV 客户端多为 `*/*` 或 `application/xml`）。
- 认证不变：仍由网关 Basic 校验，未认证返回 `401 + WWW-Authenticate`，通过后才给页面；页面本身不接触口令，浏览器复用已缓存的 Basic 凭据。
- 页面只用标准方法操作同一前缀：`PROPFIND` 列目录、`PUT` 上传、`MKCOL` 建目录、`MOVE` 重命名/移动、`DELETE` 删除、`GET` 下载；`/dav`（无尾斜杠）仍是 `301 → /dav/`。
- 未新增监听端口，未改 frpc/stunnel/证书；局域网 18090 与控制台同源复用同一份配置。
- 启用方式：在 `gateway.json` 的 webdav 路由加 `browser_ui` 字段（示例见 `config.example.json`）后 `supervisorctl restart haydn-console-gateway`。

### 15.2 界面能力

列目录（名称/大小/修改时间，时间按设备本地时区）、按名称/大小/时间升降序排序（目录恒在前）、按文件名过滤、多选上传、下载、新建目录、重命名/移动（目标路径从 WebDAV 根写起，改目录即移动）、删除（页内二次确认，目录递归删除）。排序与过滤在前端完成，不额外打上游。

### 15.3 上传边界（不静默截断）

- 单文件上限 **64 MiB**，与网关对 `/dav` 的既有请求体上限一致（`MAX_DAV_BODY_BYTES`，对客户端 PUT 同样生效，不是本界面新增的限制）。
- 超过上限时页面在**发送前**拒绝并提示改用 WebDAV 客户端；传输中触达上限则服务端返回 `413`，页面按"文件未保存"提示；若网关直接断开连接，页面提示"若文件接近 64 MiB…不会保存"，不会假装成功。

### 15.4 实测（2026-11-15，设备侧 loopback 18080）

- 浏览器路径：`GET /dav/`（`Accept: text/html` + Basic）→ `200`、`text/html; charset=utf-8`、19,096 B，含中文标识、无 rclone 英文页；无认证 → `401`；`Accept: */*` → 仍为 rclone 英文页（透传未变）。
- 操作路径：`PROPFIND` 207、`MKCOL` 201、`PUT` 201、`GET` 回读内容一致、`MOVE` 201（`Destination: /dav/...` 路径式）、移动后列表命中新名、下载 200、`DELETE` 文件与目录均 204。
- 边界：65 MiB `PUT` → `413` 且未落盘（随后 `DELETE` 404）。
- 未做：浏览器 DOM 级自动点击（环境无 Playwright），页面交互以接口行为 + 页面代码 + 内联 JS `node --check` 核验；未跑第三方客户端（QuarkPC/系统挂载）回归，仅验证其依赖的标准方法未被改动。

### 15.5 回滚

设备侧备份在 `/data/server/backups/webdav-ui-<TS>/`（`gateway.py` + `gateway.json`）：还原这两个文件并 `supervisorctl restart haydn-console-gateway` 即回到 rclone 英文页；`webdav_ui.py` 不被引用时不影响运行。

## 16. Netdata 监控（2026-11-15，只监听 loopback）

### 16.1 结构与接入点

| 项 | 值 |
|---|---|
| 版本/来源 | 官方 aarch64 静态构建 **v2.12.3**（`netdata-aarch64-v2.12.3.gz.run`）；整包 sha256 `3deeb94a…c127b4` 与官方 `sha256sums.txt` 一致（下载经 `gh-proxy` 镜像，供应链风险由官方 sha256 兜底） |
| 安装路径 | `/opt/netdata`（二进制 `/opt/netdata/bin/netdata`，配置 `/opt/netdata/etc/netdata/`） |
| 监听 | `127.0.0.1:19999`（`[web] bind to` + `allow connections from = localhost`） |
| 网关路由 | `{name:"netdata", path:"/netdata", upstream:"127.0.0.1:19999", strip_prefix:true, websocket:true, auth:"session"}` |
| 控制台入口 | `entries[]`：`Netdata 监控` → `/netdata/`，说明"服务器实时监控与告警（界面为英文，无官方中文）" |
| 数据 | dbengine 只留 tier0，`retention size = 512MiB`，tier1/2 `off`；页缓存 32MiB |
| 日志 | `/var/log/haydn/netdata-{error,collector,health,debug}.log`（`access = off`）由 `/etc/logrotate.d/haydn` 周轮转；supervisor stdout `/srv/haydn/logs/netdata.log`（10MB×3） |
| 托管 | `/etc/supervisor/conf.d/haydn-netdata.conf`，`autorestart=true`、`stopasgroup/killasgroup=true` |
| 健康检查 | `haydn-healthcheck.sh` 增 `GET /api/v1/info` 探针；**进程在但 HTTP 失败**时限频 15 分钟重启一次（`RECOVER netdata-http`） |
| 备份 | `device-make-backup.sh` 只快照 `/opt/netdata/etc`；`/opt/netdata/var/cache/netdata`（dbengine）不入快照 |

### 16.2 实测（2026-11-15，设备侧）

- 内存：启动 20 秒 RSS **52.1 MB**；运行 10 分钟 RSS **66.8 MB**；`MemAvailable` 装前 10.28 GiB → 装后 10.31 GiB（波动范围内，无净下降）。
- 磁盘：`/opt/netdata/var/cache/netdata` 首 10 分钟 **12 MB**（上限 512 MiB）。
- 监听面：仅 `127.0.0.1:19999`（`ss -ltn` 核验），无 0.0.0.0 监听。
- 代理链路（带控制台会话 cookie，经 `127.0.0.1:18080`）：`/netdata/` → `200 text/html` 102,613 B；`/netdata/v3/index.html` → `200`；`/netdata/api/v1/info` → `200`；`/netdata/api/v3/info` → `200`；`/netdata/v3/<chunk>.js` → `200`；无会话 → `401`。
- 控制台：`GET /console/api/entries` 返回 6 条，新增项 `available=true`、`note` 含"界面为英文，无官方中文"。
- 健康检查：部署新版 `haydn-healthcheck.sh` 后立即执行，`health.log` 记 `OK`。
- **未做**：浏览器 DOM 级渲染核验。原因：网关会话 cookie 带 `Secure`，adb 转发的 `http://127.0.0.1:18080` 浏览器不留存会话；本机也无法直连公网入口。判定"页面可打开"目前是 HTTP 层证据（HTML + 全部静态资源 + v1/v3 API 均 200），属**已验证链路、未验证渲染**。

### 16.3 已知限制

- **无 i18n**：Netdata 无官方中文，Dashboard 全英文；中文仅存在于控制台入口标题与说明。
- 首屏是 Netdata Cloud 的登录/claim 页面；本机未 claim，无云端依赖、无出站连接。
- 出于容器兼容关闭 `apps`/`cgroups`/`tc` 插件：没有"按应用拆分"的内存/CPU 曲线，只有系统级、磁盘、网络、进程数等。
- 错误日志有固定噪音（不影响采集）：`system-info.sh` 解析 CPU 核心行失败、`CLAIM` 的 `AGENT_UNCLAIMED` 状态、时区 `/UTC` 被判定不安全而忽略。
- 静态包安装器在本机自解压校验阶段会长期占满单核（实测 10 分钟无进展），本次改为按 gzip 偏移手工解包后再跑官方 `install-or-update.sh`；升级时沿用同一手法。

### 16.4 回滚

```sh
supervisorctl -c /etc/supervisor/supervisord.conf stop haydn-netdata
rm /etc/supervisor/conf.d/haydn-netdata.conf
supervisorctl -c /etc/supervisor/supervisord.conf update
# 网关：gateway.json 中 /netdata 路由 enabled:false（备份 /etc/haydn-console/gateway.json.bak-netdata）后 restart haydn-console-gateway
# 入口：删 entries[] 中 "Netdata 监控" 一项
# 彻底移除：rm -rf /opt/netdata
```

改动前快照：`/data/server/backups/netdata-pre-20261115.tgz`（`passwd/group/shadow`、`haydn-console`、`supervisor/conf.d`、`logrotate.d/haydn`、`haydn-healthcheck.sh`）与 `/data/server/backups/netdata-pre-host-20261115.tgz`（`device-make-backup.sh`、`chroot-enter.sh`）。

## 17. AList 文件管理（2026-11-15，只监听 loopback）

### 17.1 结构与接入点

| 项 | 值 |
|---|---|
| 版本/来源 | 官方 **v3.66.0** `alist-linux-arm64.tar.gz`（42,239,119 B）；sha256 `675d8cb6…f83d3` 与 GitHub release 的 `digest` 一致（下载经 `gh-proxy` 镜像） |
| 安装路径 | `/opt/alist/alist`（109 MB 单二进制，前端内嵌）；数据 `/opt/alist/data/`（`config.json`、`data.db`、`log/`、`temp/`） |
| 监听 | `127.0.0.1:5244`（`config.json` 的 `scheme.address`；`ss -ltn` 无 0.0.0.0） |
| `site_url` | **只配一个**：`https://8.137.162.154:60875/alist`（公网入口；AList 只支持单值） |
| 网关路由 | `{name:"alist", path:"/alist", upstream:"127.0.0.1:5244", strip_prefix:false, websocket:true, auth:"session"}` |
| 控制台入口 | `entries[]`：`AList 文件管理` → `/alist/`，说明"网盘聚合文件管理（中文界面）；局域网可直接访问，分享/直链的绝对地址取自 site_url" |
| 托管 | `/etc/supervisor/conf.d/haydn-alist.conf`（`autorestart=true`、`stopasgroup/killasgroup=true`） |
| 日志 | AList 自身 `/var/log/haydn/alist.log`（`max_size 10MB × 3`，应用内轮转）+ supervisor stdout `/srv/haydn/logs/alist.log`（10MB × 3）；未加入 logrotate，避免与应用内轮转叠加 |
| 凭据 | `credentials.services[]` 的 `id=alist`：明文 `/opt/haydn/secrets/alist-admin.txt`（600），`rotate:"alist"`；控制台"查看"、轮换、密码库、一次性 CSV 共用这份定义 |
| 备份 | `device-make-backup.sh` 快照 `data/config.json` + `data.db` + `data.db-wal` + `data.db-shm`（WAL 三件套一起拷）；`temp/`、`log/`、109 MB 二进制不入包 |

**为什么不剥前缀**：`site_url` 带 `/alist` 子路径时，AList 把页面、静态资源和 API 全挂在同一前缀下（实测 `/alist/assets/...` 200、`/alist/api/public/settings` 200），且 `GET /` 会 `302 → /alist`。网关若剥前缀，浏览器 `/alist/` 会与上游的 `302 /alist` 形成循环；保持原路径直传即可。

### 17.2 实测（2026-11-15，设备侧）

| 场景 | 结果 |
|---|---|
| 直连 `127.0.0.1:5244` | `/ping` 200；`/alist/` 200；`/` 302 → `Location: /alist` |
| 公网口径（经网关 18080，带会话） | `/alist` → **301 → `/alist/`**（相对路径，不是跳公网域名）；`/alist/` 200 / 3,916 B；`/alist/api/public/settings` 200 / 1,888 B；`/alist/assets/polyfills-legacy.*.js` 200 / 125,830 B |
| 局域网口径（源地址 `192.168.31.50` → `18090`） | `/alist` 301 → `/alist/`；`/alist/` **200 / 3,916 B**（与公网同字节数）；`/alist/api/public/settings` 200；静态资源 200 —— **未出现跳到公网 site_url 的 302，也未出现静态资源 404** |
| 非局域网源访问 18090 | `403 {"error":"not in lan subnet"}`（网关既有设计，非 AList 行为） |
| 无会话 | `/alist/` → **401**（网关会话鉴权生效） |
| 登录 | 经网关 `POST /alist/api/auth/login` → `code=200` 且返回 token（与 `site_url` 无关） |
| 内存/磁盘 | RSS **68,536 kB（66.9 MB）**；`/opt/alist/data` 1 MB、`/opt/alist` 105 MB；`MemAvailable` 10.74 GiB（Netdata 后为 10.35 GiB，下降主要来自 page cache/快照 staging，未做长稳结论） |
| 控制台 | `GET /console/api/entries` **7 条**，`AList 文件管理` `available=true` |

**直链地址（2026-11-15 补充实测）**：挂载本地存储后 `fs/get` 已能生成 `raw_url`，形如 `https://8.137.162.154:60875/alist/p/<name>?sign=…`——绝对地址按 `site_url` 落到**公网入口**，此前"代码层推断"由此证实；设备侧把该 URL 的主机替换为 loopback 后 GET 200 且字节一致。局域网浏览器点"下载"是否被指到公网仍**未做 DOM 级核验**。

### 17.3 凭据与轮换（实测）

| 动作 | 结果 |
|---|---|
| 首次随机口令 | 设备侧 `python3 secrets` 生成 24 位，写 `/opt/haydn/secrets/alist-admin.txt`（600）；`alist admin set` 写入 DB（安装器打印的初始 8 位口令随即失效） |
| 写入密码库 | `gateway.py --vault-sync`：`alist: ok`；folder `haydn-server` 条目 `AList 管理员` |
| 独立回读 | `bw get item` 与明文逐字符一致（`password_match=True`），`username=admin`，uri `https://8.137.162.154:60875/alist/` |
| 控制台"查看" | `POST /console/api/credential/reveal`（公网 Host 与局域网 Host 两种）均 200、`Cache-Control: no-store`、与明文一致；无会话 401 |
| 轮换 | `POST /api/rotate {service:"alist"}` → 200，三步全 True（写入服务账号 / 登录 API 验证 / 写入密码库）；旧口令登录 `code=400`、新口令 `code=200`；一次性口令 24 位；`rotated_at` 落 `credential-state.json` |
| CSV | `build_csv` 7 行，含 `AList 管理员` 与登录地址 |

**AList 侧改口令后的同步方式**：网页改口令在 AList 内部立即生效，但设备侧明文与密码库会过期。同步有两条路：①在控制台点一次"轮换"（同时改 AList、明文、密码库，最稳）；②手工 `alist admin set '<新口令>' --data /opt/alist/data` 后同步更新 `/opt/haydn/secrets/alist-admin.txt`（600）并重跑 `gateway.py --vault-sync`。

**进程缓存口令哈希（实测坑）**：AList 运行中把 admin 口令哈希留在内存里，`alist admin set` 改库后登录仍报 `code=400`，且 CLI 的 `del_user_cache_online` 因按 `site_url` 回连公网入口而失败。控制台轮换已内置"改密后 `supervisorctl restart haydn-alist` 再验证（最多轮询 10 秒）"。

### 17.4 已知限制与后续选项

- **单 `site_url`**：AList 只接受一个 `site_url`，直链/分享等由它派生的绝对地址固定指向公网入口；局域网看图/浏览不受影响（实测 200，静态资源正常）。
  - 若后续确认局域网点击下载被指去公网：选项 A 改 `site_url` 为局域网地址（代价：公网侧链接指向内网，不可取）；选项 B 起第二个 AList 实例专供局域网（代价：双份数据与端口、备份翻倍）；选项 C 网关改写 JSON 响应里的绝对地址（代价：需改响应体、风险高）。三者本轮均**不实现**。
- 存储：已挂载本地存储 `/` → `/srv/haydn/webdav`（与 `/dav` 同一份文件，§17.6）；夸克网盘因凭据形态不匹配仍阻塞（§17.7）。
- 未做浏览器 DOM 级渲染核验：原因同 §16.2（会话 cookie 带 `Secure`、本机连不到公网入口）。
- 日志：AList 应用内轮转 + supervisor 轮转两套并存，`/var/log/haydn/alist.log` 与 `/srv/haydn/logs/alist.log` 是不同文件（前者是应用日志，后者是进程 stdout）。

### 17.5 回滚

```sh
supervisorctl -c /etc/supervisor/supervisord.conf stop haydn-alist
rm /etc/supervisor/conf.d/haydn-alist.conf
supervisorctl -c /etc/supervisor/supervisord.conf update
# 网关：/etc/haydn-console/gateway.json 中 /alist 路由 enabled:false（备份 gateway.json.bak-alist）
#       并删 entries[] 的 "AList 文件管理"、credentials.services[] 的 alist 后 restart haydn-console-gateway
rm -f /opt/haydn/secrets/alist-admin.txt
rm -rf /opt/alist /var/log/haydn/alist.log /srv/haydn/logs/alist.log*
```

改动前快照：`/data/server/backups/alist-20261115/`（`console_credentials.py.bak`、`gateway.json.bak`），以及各次 `gateway.json.bak-alist*`。

### 17.6 本地存储挂载（2026-11-15 实测）

| 项 | 结果 |
|---|---|
| 方式 | 管理 API：`POST /alist/api/admin/storage/create`（先 `POST /alist/api/auth/login` 取 token；未走页面点击） |
| 参数 | `mount_path=/`、`driver=Local`、`root_folder_path=/srv/haydn/webdav`（与 `/dav` 同一目录）、`thumbnail=false`、`webdav_policy=302_redirect`、`status=work` |
| 结果 | `storages` 0 → 1（id=1）；**未重启 AList，也未重启网关**（AList uptime 连续） |
| 选目录理由 | `/srv/haydn/webdav` 非空（`YiCiYuan`、`阅读` 两个真实目录），符合"与 WebDAV 同一份文件"；未新建空目录 |
| 目录一致 | `POST /alist/api/fs/list {path:"/"}` 返回上述两个目录，与 `ls /srv/haydn/webdav` 一致 |
| 上传 | `PUT /alist/api/fs/put`（`File-Path` 头）200，文件立即出现在 `/srv/haydn/webdav/`，`fs/get` 的 size 与写入字节一致 |
| 下载 | `fs/get.raw_url` 主机换成 loopback 后 GET 200、内容逐字节一致（原 URL 指向公网入口） |
| 清理 | `POST /alist/api/fs/remove` 200，磁盘同步消失；3 个自测文件均已删净 |
| 权限 | `config.json` 600（原已 600，属主 root = AList 运行用户）；`data.db`/`-wal`/`-shm` 644 → **600**、`config.json.orig` 666 → **600**（含 `jwt_secret`）；`temp/` 仍 777（AList 自建，本轮未改） |
| 备份范围 | `device-make-backup.sh` 只打包 `opt/alist/data/{config.json,data.db,data.db-wal,data.db-shm}`，**不含** `/srv/haydn/webdav`；挂载只写路径且关了缩略图 → **无重复打包**。反向缺口：新设备恢复后该存储指向的目录不在快照内，需另行恢复 `webdav/` 内容 |
| 局域网口径 | `/alist` 的 `site_url` 单值结论不变：列表/浏览走相对路径正常，`raw_url` 仍是公网绝对地址 |
| 回滚 | `DELETE /alist/api/admin/storage/delete?id=1`（或管理页删除）；整目录回滚：停 AList 后用 `/data/server/backups/alist-storage-20261115T123420Z/alist-data.tar.gz`（改前 4 文件，600）覆盖 `/opt/alist/data`，再启 AList |

### 17.7 夸克网盘存储（阻塞，仅报告未实施）

- **驱动入参（实测 `GET /alist/api/admin/driver/info`）**：`Quark` 必填 `cookie`（浏览器会话串）+ `root_folder_id`；`QuarkTV` 必填 `root_folder_id`，可选 `refresh_token`/`device_id`/`query_token`。
- **现有凭据**：`/root/.quark-drive/deepseek/config.json`（600）为 quark-drive.cjs 的 **OAuth 令牌形态**——`accessToken`(502 字符)、`refreshToken`(239)、`deviceId`、`currentUserId`、`platform`，**不是浏览器 cookie**，与两个驱动的入参都不匹配。
- **处置**：按要求**先停下报告**——未创建夸克存储、未写入任何凭据、未刷新或重新登录。三条可选路径（均待用户选择）：①浏览器登录夸克后提供 `cookie`（代价：有效期短、自动化访问易被风控）；②`QuarkTV` + `refreshToken`/`deviceId` 试挂（代价：是否还需 `query_token`、PC 令牌能否用于 TV 接口均未验证，存在账号风控风险）；③维持现状（夸克仅由 `quark-drive.cjs` 用于备份，不进 AList）。
- **失效表现（待验证，推断）**：cookie/令牌失效后 AList 列表接口返回上游 401/403，页面提示加载失败，需重新获取 cookie 并更新存储配置；不影响 AList 其他存储。
- **QuarkTV 有界实验（2026-11-15T12:49–12:51Z，已回滚，只跑一次）**：用 `refreshToken`+`deviceId`+`root_folder_id=0` 建 `/quark`（create `code=200`），单次 `fs/list` 返回 `code=500`，原文：`failed get objs: failed to list objs: Post "http://api.extscreen.com/quarkdrive/token": context deadline exceeded`。判定为**驱动依赖的第三方 token 交换服务请求超时**——既不是"缺少 root_folder_id"，也不是"令牌被拒绝"（匹配/校验阶段尚未到达，无上游 401/403）。补充证据：设备直连 `api.extscreen.com` 返回 `403`（**可达**），故是 AList 内部该请求超时，而非域名不可达。按"失败即停"删除存储，`storages` 回到 1（仅 Local），未换参数重试、未轮询刷新令牌、未重新登录。
- **令牌残留清理（实验副作用）**：实验期间 refreshToken 被写入过 `data.db`；删存储后 SQLite 页内未清零的残留仍可检索到，`PRAGMA secure_delete=ON` + `VACUUM` 未能清除 → 改用 `VACUUM INTO` 生成新库，**停 AList 后替换**（`2026-11-15T12:51:33Z` 停、即时启；这是本次唯一一次 AList 重启，网关未重启），复检 `data.db`/`data.db-wal` 均不含令牌；旧库另存 `/data/server/backups/alist-quarktv-20261115T124908Z/data.db.residual`（600）。

## 18. 24 小时观察（2026-11-15 起，Netdata + AList 并存）

### 18.1 采样结构

| 项 | 值 |
|---|---|
| 脚本 | `/usr/local/bin/haydn-observe.sh`（仓库 `deploy/haydn-observe.sh`） |
| 定时 | `/etc/cron.d/haydn-observe`：`7 * * * * root /usr/local/bin/haydn-observe.sh`（cron 守护进程由 supervisor 的 `haydn-cron` 托管，无 systemd） |
| 输出 | `/var/log/haydn/observe.csv`（**不参与** `logrotate.d/haydn-csv` 日轮转，仅 20M 大小兜底，避免切分观察基线）；每小时 **17 行** = 1 host 汇总 + 15 个 supervisor 程序各 1 行 |
| 字段 | `ts_utc,kind,name,rss_kb,load1/5/15,mem_avail_kb,mem_total_kb,disk_used,uptime_s`；`kind=host` 行才有负载/内存/磁盘/uptime，`kind=svc` 行只有 `rss_kb` |
| 起点标记 | `/var/log/haydn/observe-start.txt`；基线偏移量 `/var/log/haydn/observe-baseline.txt`（各日志行数与网关错误计数） |
| RSS 口径 | 读 `/proc/<pid>/status` 的 `VmRSS`，只对 `RUNNING` 且能取到 pid 的程序计数，否则记 0（用于识别"进程在但取不到"） |

### 18.2 观察起点与判据

- **起点**：`2026-11-15T10:11:37Z`（设备本地 18:11:37），观察窗口 24 小时至 `2026-11-16T10:11:37Z`。
- **基线偏移（起点值）**：`alerts.log` 7 行、`health.log` 44 行、`console-gateway.log` 5,851 行（其中 `ERROR|Traceback` 292 行）、`backup.log` 152 行、`observe.csv` 17 行。
- **对比维度**（到期逐项给数，不接受"运行正常"式结论）：
  1. 内存与负载：`MemAvailable` / `load1/5/15` 的起点、最低点、均值；
  2. 15 个服务的 RSS 变化（重点 `haydn-netdata`、`haydn-alist` 两个新增项）；
  3. 告警增量：`alerts.log` 与 `health.log` 新增行数及内容（基线行数之后的部分）；
  4. 备份三来源：本窗口内的一次 03:30 定时管线（设备本地时区）是否 `SUMMARY ok=3`；
  5. 网关：`haydn-console-gateway` 是否出现非人工重启（`uptime` 中断）与错误行增量。
- **口径澄清（易错）**：03:30 定时由宿主 `backup-loop.sh` 用**设备本地时区**判定（`date +%H:%M`），但 `backup.log` 时间戳是 **UTC**——本地 03:30 = UTC 前一日 19:30，排查时不要误判为"漏跑"。

### 18.3 已知限制

- 采样频率为每小时一次，瞬时峰值（如备份 gzip 期间的 IO/负载）会被平均掉；需要更细粒度时只能查 Netdata 的 dbengine 或手工采样。
- `rss_kb` 是单进程 `VmRSS`，不含子进程与 page cache；Netdata 的 dbengine、AList 的 mmap 会把一部分内存记在缓存而非 RSS。
- 观察不等于验收：本轮只观测"是否引入退化"，不构成 24h soak 结论（soak 口径见 [cases](../../cases/ace-pro-pgp110/README.md)）。

### 18.4 回滚

```sh
rm -f /etc/cron.d/haydn-observe /usr/local/bin/haydn-observe.sh
rm -f /var/log/haydn/observe.csv /var/log/haydn/observe-start.txt /var/log/haydn/observe-baseline.txt
# 观察脚本只读 /proc 与 supervisorctl status，删除不影响任何被观察服务
```
