---
id: GRD-007
title: 网络最小暴露
type: guardrail
status: current
audience: human, agent
tags: network, loopback, firewall, adb, public-entry, exposure
depends: MTH-007
updated: 2026-11-11
agent_hint: 新增监听/入口/隧道前先判定是否必要；默认只允许回环与受控局域网，公网只留一个受控入口，ADB 维护结束必须关闭。
severity: blocker
scope: server
---

# GRD-007 · 网络最小暴露

> 每多一个监听地址，就多一个被扫描、爆破与横向移动的机会。手机服务器的默认姿态是"谁都不该看见我"。

## 红线（MUST NOT）

1. **R1** **MUST NOT** 把服务绑定到公网或"所有地址"；默认只监听回环地址，确有局域网需求时使用受控的专用监听。
2. **R2** **MUST NOT** 新增公网端口、隧道或对外入口；公网访问只允许复用既有的**单一受控入口**（TLS + 认证 + 限流），且需变更记录。
3. **R3** **MUST NOT** 在维护结束后保持无线调试/ADB 网络通道开启；ADB 维护面用完即关，优先 USB 直连。
4. **R4** **MUST NOT** 把遥测桥、管理 API、控制面或备份接口暴露到局域网/公网；遥测桥只允许回环，控制面不得持有遥测凭据。
5. **R5** **MUST NOT** 关闭防火墙/允许列表、降级认证（如改用明文 HTTP 管理）、或向公开渠道分发入口与 token。
6. **R6** **MUST NOT** 让临时调试工具（文件传输、特权 helper、端口转发、抓包代理）跨维护窗口运行；临时监听必须在结束后停止并复核。

## 为什么（风险与案例）

- 公网控制面约等于把服务器 shell 放到互联网；已有案例入口依赖"TLS + 认证 + 限流 + 单一入口"才勉强可接受，多开一个端口就是多一份风险。
- ADB 网络通道与特权 helper 是最容易被忽略的暴露面：案例中临时特权服务会监听所有接口，验证后必须显式停止（见 PIT-013 的维护通道失效模式）。
- 遥测桥的安全模型建立在"仅回环 + TLS + token + 证书 pin"之上；一旦允许局域网监听，同网段设备即可发起重放或伪造请求（见 PIT-019）。
- 案例实证：[04 风险与回滚](../docs/10-device/04-风险与回滚.md) R-09/R-11/R-18、[14 安卓深度操作调研](../docs/20-server/14-安卓深度操作调研与技能沉淀.md)、[28 全栈规范 §8](../docs/00-overview/28-全栈整体方案规范.md)。

## 允许的替代（MUST/SHOULD/MAY）

- **MUST** 维护"监听地址与入口清单"：每个监听项注明用途、协议、认证方式、是否回环/局域网、责任人；变更后立即复核。
- **MUST** 公网入口保持唯一且受控：强制 TLS、认证、限流、审计与维护开关；不新增旁路。
- **MUST** ADB 只作为维护通道：优先 USB；确需网络调试时限定可信局域网、记录开启与关闭时间，结束立即恢复 USB 模式。
- **SHOULD** 防火墙默认拒绝入站，只放行明确入口；管理面优先回环/局域网。
- **MAY** 用 VPN/私网替代公网入口，但必须先取得用户同意（[GRD-009](GRD-009-external-services-consent.md)）并验证与宿主网络的共存。
- **MAY** 对外部可达性做定期只读探测与告警，探测本身不携带 token。

## 检查方式（Agent 可执行）

```bash
ss -ltnp
netstat -ln
adb devices -l
adb shell getprop service.adb.tcp.port
adb shell getprop ro.debuggable
```

- 人工核对：`ss -ltnp` 输出与"监听清单"逐项对比；出现计划外监听或非回环绑定即判违规，立即关闭并记录。
- 人工核对：确认公网入口仍只有一个受控入口、TLS/认证/限流/审计开启；无明文 HTTP 管理面。
- 人工核对：ADB 网络通道状态（`service.adb.tcp.port` 非空或设备列表出现网络传输）必须在维护结束后恢复；无线调试开关为关闭。
- 人工核对：临时 helper/端口转发/抓包进程是否仍在运行；维护窗口外不得存在。
- 变更核对：本次变更若新增/修改监听、入口、隧道，是否有记录、认证与限流配置、回滚方式。

## 关联

- 踩坑：[PIT-013 ADB 维护通道脆弱](../pitfalls/PIT-013-adb-fragility.md)、[PIT-019 伪证书 pin](../pitfalls/PIT-019-fake-pinning-bridge.md)
- 护栏：[GRD-006 密钥卫生](GRD-006-secret-hygiene.md)、[GRD-009 外部服务同意](GRD-009-external-services-consent.md)、[GRD-011 隐私与脱敏](GRD-011-privacy-inventory.md)
- 方法论：[MTH-007 安全与密钥生命周期](../methodology/06-security.md)、[MTH-004 服务器栈](../methodology/03-server-stack.md)
- 案例：[haydn K40 Pro 案例](../cases/haydn-k40pro/README.md)
