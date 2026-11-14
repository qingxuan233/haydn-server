---
id: ADR-0008
title: 公网入口采用大陆节点 IP + 非标端口（放弃域名 443、境外节点、CF Tunnel 与 Tailscale Funnel）
type: adr
status: accepted
audience: human, agent
tags: network, frp, icp, sni, public-entry, ip-port, cloudflare-tunnel, tailscale-funnel, adr
depends: ADR-0002, MTH-013, MTH-016
updated: 2026-11-15
agent_hint: 公网入口现状=IP+非标端口（60875/60177），域名入口公网不可用（备案按 SNI 拦截，HTTP 明文 403）但隧道保留、控制台不展示；改入口/证书/DNS 前先读本文与复议触发点，计数与证据只在 frp-public-mapping §11.4/§12.4，回滚顺序见同文 §12.7。
---

# ADR-0008 · 公网入口：IP + 非标端口（已选定）

## 状态

`accepted`（2026-11-14，用户选型）。取代：无。修订：R1 2026-11-14 初版（proposed，只列候选）；R2 2026-11-14 用户选定 IP + 非标端口，补理由、放弃项与复议触发点；R3 2026-11-15 统一域名入口口径（不可用/隧道保留/控制台不展示），计数与证据改为引用 [frp-public-mapping](../2026-11-14/frp-public-mapping/outputs/frp-public-mapping.md) §11.4/§12.4，不复述数字。
关联 [frp-public-mapping](../2026-11-14/frp-public-mapping/outputs/frp-public-mapping.md) §11.4/§12、[web-console README](../2026-11-14/web-console/README.md) §12。

## 背景

**已核验事实**（2026-11-14，设备侧命令输出，详见 frp-public-mapping §11.4/§12）：

- 公网 443 被阿里云备案拦截：明文 HTTP 403，响应头 `Server: Beaver`、正文 `Not-compliance ICP Filing`；TLS 握手被 RST，且 RST 早于本地 stunnel、TTL/IP-ID 与本机不符 → 非设备侧问题。
- 成都节点 frps `8.137.162.154:1210` 上四条代理（`43RHEU5l28eb`、`3U6GYwayApgh` 两条 https；`HJtApRGYMHvn`→60875、`0mP2rpGpthc0`→60177 两条 tcp）均 `start proxy success`；证书：主站 DigiCert（CN=`qingxuan.bbs0.cc`）、密码库自签（CN=`vault.qingxuan.bbs0.cc`），指纹与有效期见 frp §12.4。
- **判据实验**：同一 IP 同一端口，IP 直连与中性 SNI 全通；域名 SNI 多数被 RST。逐次计数见 frp §12.4，本文不复述。
- stunnel 仍在 `127.0.0.1:18443`/`18445` 本地终结 TLS（`ss -lntp` 已核验）。

**推断**：拦截判据是 ClientHello 的 **SNI 域名**，与端口、路径无关（少数例外未解释）；443 的 RST 与该拦截**可能相关但未证实**。

## 决策（R2 定稿）

**选定：保留大陆成都节点，用 IP 直连 + 非标端口作为当前公网主入口，接受证书告警。**

| 用途 | 当前公网入口 | 隧道 | 证书（浏览器会告警） |
|---|---|---|---|
| 主站 / 控制台 / Git | `https://8.137.162.154:60875/`、`/console/`、`/git/` | `HJtApRGYMHvn` → 18443（stunnel 终结 TLS） | DigiCert，CN=`qingxuan.bbs0.cc` ≠ IP → 名称不匹配告警 |
| 密码库 | `https://8.137.162.154:60177/` | `0mP2rpGpthc0` → 18445（stunnel 终结 TLS） | 自签，CN=`vault.qingxuan.bbs0.cc` → 不受信 + 名称不匹配 |

1. **理由**：大陆节点 200 Mbps（延迟与带宽最佳）、零额外成本、不改 DNS、不需备案、不动证书与 stunnel；IP 直连**已实测稳定返回 200**（含 `/console/`、`/`、`/git/`、`:60177/alive`；计数见 frp §12.4）。
2. **证书告警处理**：不新增/不替换证书、不做 `IP SAN` 重签（会牵动 stunnel 与现有域名证书）；用户逐站点"高级 → 继续"，并在浏览器/客户端侧显式信任自签证书。告警是预期行为，不作为故障上报。
3. **域名 + 非标端口不作入口**：浏览器必然发送域名 SNI，实测不可用，故弃用；域名入口公网不可用（备案按 SNI 判定，HTTP 明文 403），**不在控制台 `entries[]` 展示**。
4. **保留回滚路径**：原两条 `type="https"` 隧道（`43RHEU5l28eb`、`3U6GYwayApgh`）**不删不改**，DNS 未改；一旦 443 恢复即可直接回到域名入口（步骤见 frp-public-mapping §12.7）。
5. **被放弃项**：境外 frp 节点（带宽低、用户否决）；Cloudflare Tunnel（需把 `bbs0.cc` 的 NS 迁入 Cloudflare，用户不愿让出域名控制）；Tailscale Funnel（仅 `*.ts.net`、只能 443/8443/10000、带宽不可配）；ICP 备案（流程与资质成本，暂不启动）。

## 后果

| 维度 | 内容 |
|---|---|
| 正面 | 带宽与延迟最优、零成本、无第三方依赖；设备侧与 443 时期相比只多两段 tcp 代理，stunnel/证书/网关零改动；判据实验可复核，后续排障不必重推设备侧 |
| 代价 | 入口带端口、URL 不可书签化为裸域名；证书告警成为常态（易被习惯化，需自控"只在自己入口点继续"）；`ROOT_URL`/`DOMAIN` 仍按域名配置 |
| 风险 | ① 拦截策略若改为按 IP/端口封堵，该入口会整体失效；② 公网直连 stunnel，无 WAF，防爆破只靠网关全局限流与各服务自身限流；③ Vaultwarden 手机端/浏览器扩展若按域名配置会走 443（被拦），需按 IP 重配（**未实测**）；④ 部分企业/公共网络只放行 80/443 |
| 回滚 | 删除两段 tcp → `frpc verify` → `restart haydn-frpc`，即回到 443 域名入口（若那时已解封）；文件级 `/data/server/backups/frpc.toml.20261114T142644Z` |

## 复议触发点（满足任一即重开本决策，另立 ADR）

1. `bbs0.cc` 完成 ICP 备案或备案拦截消失（443 域名入口恢复 → 直接回滚到域名入口）。
2. 取得可自主托管的自有域名（CF Tunnel 可重新评估，无需让出既有域名控制）。
3. IP 直连被封 / frps 出口 IP 变更 / 端口被回收（入口失效）。
4. 客户端原生支持成为硬需求（Vaultwarden 移动端与浏览器扩展、Git 凭据管理）导致 IP 方案不可接受。
5. 需要对外长期稳定服务或对外身份可信（证书告警不可接受）。

## 备选方案对比（R1 调研，结论保留）

| 方案 | 利 | 弊 | 结论 |
|---|---|---|---|
| **IP + 非标端口（选定）** | 带宽最优、零成本、已实测 10/10 | 带端口、证书告警、无 WAF | **采纳** |
| 域名 + 非标端口 | 无告警 | 域名 SNI 1/10，不可用 | 否决 |
| 境外 frp 节点 | 绕开备案 | 带宽低、成本 | 放弃 |
| Cloudflare Tunnel | 自有域名、WS、免费 | 需 `bbs0.cc` NS 迁入 CF；大陆延迟未知 | 放弃 |
| Tailscale Funnel | 零成本、复用 tailnet | 仅 `*.ts.net`、3 端口、带宽不可配 | 放弃 |
| ICP 备案 | 合规、恢复 443 | 流程与资质成本 | 暂不启动 |

CF 方案未采用；`region1.v2.argotunnel.com:7844` 的连通性探查（`curl` rc=60）与本方案无关，不再深挖。

## 关联

- 证据：[frp-public-mapping](../2026-11-14/frp-public-mapping/outputs/frp-public-mapping.md) §11.4（RST 归因更正）、§12（TCP 非标端口实施、SNI 判据、回滚）
- 入口与验证：[web-console README](../2026-11-14/web-console/README.md) §12.1/§12.2/§12.4
- 相关：[ADR-0002](0002-protocol-versioning-and-regression.md)、[MTH-013](../methodology/12-delivery-governance.md)、[MTH-016](../methodology/16-release-compatibility-data.md)
- 外部依据（R1 调研留档）：Cloudflare Tunnel 下载页/Protocols/WebSockets/413 文档、Tailscale Funnel 与 Userspace Networking 文档
