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
| `deploy/lan-fw-loop.sh` | `/data/server/bin/lan-fw-loop.sh` | 宿主侧：按网段文件幂等维护 18090 放行规则 |
| `console/config.example.json` | `/etc/haydn-console/gateway.json` | 路由与白名单配置 |
| `deploy/haydn-console.conf` | `/etc/supervisor/conf.d/haydn-console.conf` | supervisor 程序定义 |
| `deploy/chroot-enter.sh` | `/data/server/bin/chroot-enter.sh` | 追加 `/srv/haydn/{logs,run}` 绑定挂载 |
| `deploy/backup-loop.sh` | `/data/server/bin/backup-loop.sh` | 追加"控制台手动触发"轮询 |
| `deploy/haydn-backup.sh` | `/data/server/bin/haydn-backup.sh` | 逐来源：加密→解密自检→上传→保留 7 份 |
| `deploy/backup-vaultwarden.sh` | `/data/server/bin/backup-vaultwarden.sh` | Vaultwarden 数据一致性快照（SQLite backup API） |
| `deploy/backup-forgejo.sh` | `/data/server/bin/backup-forgejo.sh` | Forgejo 数据一致性快照（SQLite backup API + 仓库目录） |
| `deploy/device-make-backup.sh` | `/data/server/bin/device-make-backup.sh` | 整机配置快照（排除可重建大二进制） |
| `deploy/install.sh` | `/data/local/tmp/web-console/deploy/install.sh` | 幂等安装脚本（自动备份原配置） |
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
| `auth` | `none` / `session`（共享控制台会话），每条路由独立 |
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
| 真实服务启停（非白名单拒绝） | **未知** | 白名单拒绝已测；对真实服务的 restart 未在控制台点击验证 |
| 重启后 bind mount 与自启 | **未知** | 未重启设备验证；若 `/srv/haydn/logs` 未挂上，遥测/日志面板会为空（页面本身不受影响） |

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

默认覆盖（2026-11-15 调整后 5 条）：控制台 `/console/`、WebDAV `/dav/`、Forgejo `/git/`、Vaultwarden `https://8.137.162.154:60177/`、Prometheus `/console/api/metrics`。原"主站 `/`"与"局域网省流 `{lan_root}/console/`"两条已移除：`/` 改为 302 到控制台（判定见 §13.6），局域网切换只保留 §10 的一次性票据按钮。未探测到局域网地址时对应入口显示"当前不可用"而不是死链。

**入口地址口径（2026-11-15）**：`entries[]` 不展示任何域名入口（`qingxuan.bbs0.cc` / `vault.qingxuan.bbs0.cc` 公网不可用，见 §12.2；隧道保留仅作回滚）。主站/控制台/WebDAV/Forgejo 用站内相对路径，随当前 origin 解析——公网即 `https://8.137.162.154:60875/...`，局域网即 `http://<lan_ip>:18090/...`，不写死主机；Vaultwarden 固定 `https://8.137.162.154:60177/`。设备侧配置中仅 `cert_file` 与 `NODE_EXTRA_CA_CERTS` 保留域名（是证书文件路径，不是入口）。

**已核验（2026-11-15）**：`GET /api/entries` 返回 5 条且 `available` 全为 True；指标入口为站内相对路径 `/console/api/metrics`（登录后可看，经控制台代理 `127.0.0.1:9100`，不新增对外端口）；`/api/lan` 返回 `public_root=https://8.137.162.154:60875`，用于"当前入口"展示。

### 13.2 凭据定义（单一事实来源）

`gateway.json` → `credentials.services[]` 是唯一凭据定义；**CSV 导出与密码库条目都由它生成**，不另写一套。每条含 `id`、`name`、`username`、`login_uri`、`rotate`、明文来源（`plain_file` 或 `account_file`）、`notes`。

- CSV 表头：`folder,name,login_uri,login_username,login_password,notes`（Bitwarden 可直接导入），folder 固定 `haydn-server`。
- 明文只在设备侧 600 文件；页面与接口不返回完整口令（轮换结果除外，且只展示一次）。
- 当前 6 条：控制台、WebDAV、Forgejo、Vaultwarden 主密码、Vaultwarden 管理令牌、设备 root/su（仅提示，不保存口令）。

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
- **入口去重**：`entries[]` 移除"局域网省流入口"，局域网切换只保留底部带一次性票据的按钮（`{lan_root}` 占位符仍可供其他入口使用）；调整后共 5 条。
- **当前入口**：不再回显 `location.host`；局域网显示 `/api/lan` 的 `lan_url`，公网显示配置的 `public_root`（`https://8.137.162.154:60875`），失效域名不会出现在面板里。
- **Prometheus 指标**：`node_exporter` 仅绑 `127.0.0.1:9100`，iptables `INPUT` 默认 DROP 且无 9100 放行（LAN 访问为超时而非拒绝）。按"不新增暴露面"原则，入口改为站内 `/console/api/metrics`：会话鉴权后由网关代理 loopback 采集，未登录 401、登录后 200 `text/plain`；未改绑定地址、未加 iptables 规则。
- **交互统一**：服务启停（start/restart/stop）与备份按钮改为页内两步确认（`armConfirm()`，5 秒窗口），`stop` 写明"立即中断直到 start"、`restart` 写明"短暂中断数秒"；执行中与执行结果（成功/失败原因摘要）均写入 `#svc-msg` / `#backup-msg`。实测只重启了可控目标 `haydn-local-http`（返回 `stopped / started`，状态 RUNNING），未触碰网关、隧道或备份管线。
