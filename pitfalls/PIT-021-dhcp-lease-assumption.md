---
id: PIT-021
title: 把方案建立在固定 IP / DHCP 静态租约上
type: pitfall
status: current
audience: human, agent
tags: network, wifi, dhcp, discovery, static-ip, multi-ssid
depends: GRD-007, MTH-004
updated: 2026-11-11
agent_hint: 先确认这是"地址漂移"而非服务故障；不要要求用户路由器做租约；用动态地址+发现机制修复
severity: S2
domain: ops
oem: generic
---

## 症状

- 服务本身正常，但换 Wi-Fi、重启路由器或隔天再访问时，旧 IP/URL/脚本全部失效；SSH/控制台"突然不可达"。
- 方案评审里出现"给手机 MAC 做 DHCP 静态租约/设静态 IP"作为前置条件，但用户路由器没有该功能、或设备会连不同网络。
- 文档/脚本里硬编码 `192.168.x.x`、旧 LAN IP、固定 host 白名单；地址变化后需要人工改脚本。

## 触发场景

- 家庭/公司/酒店/访客网络切换，网段与地址由 DHCP 分配且不可控；
- 路由器是运营商/酒店/公司托管，无法进入管理页做租约或端口控制；
- 访客网络 AP isolation、Captive portal、MAC 随机化/设备识别变化；
- 设备同时使用多个 Wi-Fi 配置或多 SSID 漫游。

## 根因

- 把"固定地址"当成可获得的**基础设施能力**，而事实上移动设备的地址由网络环境决定，且不是所有路由器都支持静态租约。
- Android 的"静态 IP"是**按网络**手填的、切换网络即失效；关 MAC 随机化也只能提高租约稳定性，不能保证地址。
- 方案把"固定地址"写成门禁/验收前提，导致换网场景直接判失败，而不是把它当正常状态处理。

## 规避与修复

1. **取消前置条件**：固定租约/静态 IP/路由器管理权限只作为**可选优化**，不作为路线门禁或验收前提（MTH-002 §5.3.1）。
2. **服务端动态地址**：运行期读取当前地址（默认路由/接口），API/控制台展示并随网络变化刷新；禁止硬编码。
3. **发现机制兜底**（优先级）：页面/控制台展示当前地址 → 扫码/人工抄录 → 局域网 mDNS/广播发现 → 用户批准的受控隧道。
4. **脚本与文档去硬编码**：只存主机名/发现入口；脚本先发现再连接；`assess`/runbook 不将"租约可用"设成 pass 条件。
5. **换网验收**：换 Wi-Fi/路由器重启/断线重连后重新发现；把"地址变化"写入正常状态与限制清单。
6. **受限网络处理**：AP 隔离/Captive portal 视为不可达，改走受控隧道或用户批准入口；不得假设同网段可互访。
7. **有隧道需求先授权**：Tailscale/WireGuard/frp 等按用户批准接入，复用受控入口，不新增暴露面。

## 验证

- 切换至少 2 个不同 Wi-Fi（含一个不可管理租约的网络）后，按文档的发现步骤能重新访问服务；
- 路由器重启/租约过期后无需改脚本即可重新发现；
- 全仓 `grep` 无当前地址硬编码（历史/归档证据除外）；
- `validate --strict`、`check-links --strict-anchors` 全绿。

## 关联

- 护栏：[GRD-007 网络最小暴露与不依赖固定地址](../guardrails/GRD-007-network-least-exposure.md)
- 方法论：[MTH-004 服务器栈 §4/§4.1](../methodology/03-server-stack.md)、[MTH-002 评估 §5.3.1](../methodology/01-assessment.md)、[MTH-001 适用前提](../methodology/00-foundations.md)
- 同类：[PIT-009 OEM 后台清理](../pitfalls/PIT-009-oem-fgs-killer.md)、[PIT-013 ADB 脆弱](../pitfalls/PIT-013-adb-fragility.md)
- 计划：[MTH-003 路线图网络步骤](../methodology/02-roadmap.md)

## 证据

- 案例实证（历史建议，已被本治理修订）：[03 操作手册](../docs/20-server/03-操作手册.md)、[06 A+ 优化方案](../docs/20-server/06-A+优化方案.md)、[17 构建手册](../docs/20-server/17-研究平台环境构建手册.md)、[01 设备档案](../docs/10-device/01-设备档案.md) 曾建议路由器 DHCP 静态租约/静态 IP。
- 案例实证（事实）：[当前状态](../docs/00-overview/当前状态.md) §11 记录 LAN IP 为"动态 DHCP，以页面/接口实时值为准"；[39 控制台功能](../docs/40-console/13-控制台功能分析与完善.md) 已实现动态 LAN IP 兼容。
- 通用风险：不同路由器能力差异、多 SSID 漫游与访客隔离为常见移动场景；待更多设备案例验证。
