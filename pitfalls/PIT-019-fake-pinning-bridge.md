---
id: PIT-019
title: “证书 pin”名不副实的安全承诺缺口
type: pitfall
status: current
audience: human, agent
tags: tls, pinning, token, mtls, pairing, security-gap
depends: MTH-007
updated: 2026-11-11
agent_hint: 先逐条核对“安全承诺 vs 已落地实现”，未落地的 mTLS/配对/轮换/限流必须标为缺口
severity: S2
domain: security
---

## 症状

- 文档宣称“TLS + token + 证书 pin”，实际是构建期自签证书、私钥随 APK 打包；服务端校验的是这个自签证书本身（静态 pin），并非公信 CA 或双向认证。
- token 为静态 Bearer：首次生成后手动部署到服务端明文文件，没有配对/交换/轮换流程；release 重装后 token 可能丢失或需人工再部署。
- 构建期 keystore 口令存在默认回退；缺少请求限流、审计与轮换的落地；所谓“pin 保护”只覆盖很窄的一层。
- 换证书或重建 APK 后 pin 失效，恢复靠手工；交接/审计按文档验收会误以为安全项已完成。

## 触发场景

- MVP 交付/交接时用“安全已做”描述，验收只验证“能连上、401 生效”；
- 升级、重装、换机后证书/token 变化；
- 威胁模型扩展到“同机恶意 App 读取 token/私钥”或“本机进程伪造请求”；
- 默认口令回退、无速率限制、无轮换审计的部署上线。

## 根因

- 把“传输加密 + 静态凭据 + 自签证书固定”当成 mTLS/配对/密钥管理的等价物，安全承诺超出实现。
- 构建期密钥静态、无运行时生成/Keystore、无轮换流程；pin 只是单点校验，仍依赖明文 token 与手工部署。
- 缺少限流/审计/配对等纵深，凭据一旦泄露，滥用成本低。
- 文档没有“已实现/未实现”对照表，评审与交接无法据此判定。

## 规避与修复

1. 如实标注：写“自签 TLS + 静态 Bearer + 证书 pin（本机 MVP）”，并明确未实现 mTLS/配对/轮换/限流；禁止写“已安全”。
2. 补配对与 token 交换：一次性配对码/二维码 → token 下发 → 服务端保存哈希或受控文件；换机可重复配对。
3. 证书/密钥生命周期：运行时生成 keystore（Keystore/硬件-backed），证书轮换 + pin 更新走维护窗口与回滚。
4. 纵深防御：仅回环监听、GET-only、请求体上限、请求限流、审计与异常速率告警；不提供 shell/写端点。
5. token 不落明文：服务端受控文件权限 600；日志/聊天/备份不出现值；泄露即轮换。
6. 需要更强身份时升级 mTLS（或至少双向认证），并记录残余风险（同机恶意 App 仍可读取私有数据）。
7. 验收用安全清单：无 token/错误证书/非回环访问被拒、限流触发、换证书后按流程恢复，而不是只看“能连上”。

## 验证

- 无 token、错误证书、非回环访问均被拒绝；触发限流返回明确状态。
- 换证书后按维护流程完成 pin 更新与恢复，失败可回滚。
- 文档安全条款与实现逐条对照一致；交接评审能列出未落地项与残余风险。
- 旧 token 轮换后失效，新 token 只存在于受控存储。

## 关联

- 护栏：[GRD-006 秘密卫生](../guardrails/GRD-006-secret-hygiene.md)、[GRD-007 网络最小暴露](../guardrails/GRD-007-network-least-exposure.md)
- 方法论：[MTH-007 安全与密钥生命周期](../methodology/06-security.md)
- 同类：[PIT-016 密钥不可复现](PIT-016-generated-signing-keys-repro.md)、[PIT-015 明文凭据](PIT-015-plaintext-credentials.md)

## 证据

- 案例实证：[33 Bridge MVP 实施记录 §3/§6](../docs/50-bridge/33-Android-Bridge-MVP实施记录.md)（自签证书与私钥打包、静态 token、未做配对/mTLS）
- 案例实证：[28 全栈整体方案规范 §8.2/§8.3](../docs/00-overview/28-全栈整体方案规范.md)（MVP 安全控制与 Phase 2 未落地清单）
- 案例实证：[android-bridge/README §7/§10](../android-bridge/README.md)（token 部署方式、静态 TLS 私钥与已知限制）
- 案例实证：[31 拍板事项决策分析 D2](../docs/10-device/31-拍板事项决策分析与Root升级路线.md)（TLS+token+pin 取舍与 mTLS 延后）
