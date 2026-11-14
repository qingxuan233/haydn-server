# 88frp 面板一次性创建清单（HTTPS-only）

> 用法：登录 88frp → 创建隧道，按下表逐项照填；字段名可能略有差异，括号内为等价说法。
> 前置：先在「节点信息」抄下 `serverAddr / serverPort / token`（本文件不记录真实值），并确认套餐隧道条数。

## 0. 创建前先记下（只记在本机密码管理器里，不写进仓库/聊天）

| 项 | 面板位置 | 你的取值 |
|---|---|---|
| 服务器地址 serverAddr | 节点信息 | （应与 47.97.70.99 一致，若不同以面板为准） |
| 服务器端口 serverPort | 节点信息 | ____________（实测 7000 不可达，勿照抄默认） |
| 认证 token | 节点信息 | ____________（写入设备 `/etc/frp/frpc.env`，权限 600） |
| 套餐隧道条数 / 流量 | 我的套餐 | 参考：2 元=5 条/288G，5 元=10 条/488G（以面板为准） |
| 是否要求备案/实名 | 创建页提示 | ____________ |

## 1. 逐项创建

| # | 隧道名称 | 类型（协议） | 本地 IP（内网主机） | 本地端口 | 绑定域名 | 路径/子域 | 远程端口 | 状态 | 备注 |
|---|---|---|---|---|---|---|---|---|---|
| M1 | `haydn-web` | HTTP | `127.0.0.1` | `18080` | `qingxuan.bbs0.cc` | 根路径 `/` | 不填 | **启用** | 唯一实际生效项；静态自检页，公网 HTTPS 入口 |
| R1 | `haydn-metrics` | HTTP | `127.0.0.1` | `9100` | `qingxuan.bbs0.cc` | `/metrics` | 不填 | 建好但 frpc 不启用 | 指标；启用前必须加 BasicAuth |
| R2 | `haydn-api` | HTTP | `127.0.0.1` | `18081` | `qingxuan.bbs0.cc` | `/api` | 不填 | 建好但 frpc 不启用 | 未来 API；本地服务需自带鉴权 |
| R3 | `haydn-dav` | HTTP | `127.0.0.1` | `18082` | `qingxuan.bbs0.cc` | `/dav` | 不填 | 建好但 frpc 不启用 | WebDAV；强制认证 + 只读 |

填表要点：
- **类型只能是 HTTP**（vhost），不要选 HTTPS（透传）——TLS 由 88frp 边缘终结；选 HTTPS 会要求设备侧证书。
- **本地 IP 一律 `127.0.0.1`**（现有服务都只在 loopback 监听，别填 192.168.31.50）。
- **不要填 80/8080 之类公网端口**；HTTP 类型隧道没有「远程端口」，只有域名。
- 若面板要求「子域名」而非完整域名：填 `qingxuan`（服务商域名 `bbs0.cc` 由面板带出）。
- R1/R2/R3 若因「同域名只能一条隧道」被拒：见 §3 回退方案，不要强行改用 TCP。

## 2. 不要创建的条目（明确排除）

| 想做 | 为什么不做 | 替代 |
|---|---|---|
| 80 端口 HTTP 映射 / 80→443 跳转 | 用户硬约束：域名只支持 HTTPS，服务端不提供 HTTP | 只保留 443 入口 |
| SSH(22) TCP 映射 | 公网 SSH 攻击面最大 | tailnet 访问 `haydn-pgp110` |
| node-exporter(9100) 直连公网 | 泄露主机画像 | tailnet 抓取；或 R1 + BasicAuth |
| tailscaled SOCKS5(1055) | 等于开放代理，会被滥用封号 | 永不暴露 |
| OEM 端口（10150/10152/46888/47888/20380/12121） | 非自建、与服务器无关 | 保持 iptables DROP |
| UDP 映射 | 当前无 UDP 服务需要入站 | 不申请 |

## 3. 若面板不支持同域按路径分流（C4 证伪）

R1/R2/R3 改为独立子域名，需要在「二级域名解析管理」里**逐条新增 A 记录**（实测无泛解析）：

| 用途 | 建议域名 | 记录类型 | 值 |
|---|---|---|---|
| 指标 | `metrics.bbs0.cc` 或 `m.qingxuan.bbs0.cc`（以面板可加的位置为准） | A | 面板给出的节点 IP |
| API | `api.bbs0.cc` | A | 同上 |
| WebDAV | `dav.bbs0.cc` | A | 同上 |

新增子域可能额外计费/占配额，先确认再建；不确定就只保留 M1。

## 4. 创建后验收（5 分钟）

```bash
# 1) HTTPS 可用
curl -sSI https://qingxuan.bbs0.cc/

# 2) 证书归属与有效期（判断是否为服务商边缘证书）
openssl s_client -connect qingxuan.bbs0.cc:443 -servername qingxuan.bbs0.cc < /dev/null \
  | openssl x509 -noout -subject -issuer -dates -ext subjectAltName

# 3) HTTP 应不可用（验证 HTTPS-only）
curl -sS -m 5 -o /dev/null -w '%{http_code}\n' http://qingxuan.bbs0.cc/
```

设备侧同时确认（只读）：

```bash
su -c "ss -tulnp | grep -E '18080|9100'"      # 仍应只有 127.0.0.1
su -c "ss -tnp | grep 47.97.70.99"            # 只应有 ESTABLISHED 出站，不应新增 LISTEN
```

验收通过标准：①HTTPS 200；②issuer 为公共 CA 且 SAN 命中域名（若为自签 → 改模型 B）；③HTTP 无站点；④设备无新增入站监听。

## 5. 出问题时先停哪一步

1. 面板停用 M1 → 公网立即不可达（本地服务不受影响）。
2. 设备执行 `supervisorctl stop haydn-frpc`（如已部署）→ 隧道下线。
3. 回滚不需要动 iptables：frpc 纯出站。
