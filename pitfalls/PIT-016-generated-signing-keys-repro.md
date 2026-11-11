---
id: PIT-016
title: 签名/TLS 密钥缺省生成导致不可复现
type: pitfall
status: current
audience: human, agent
tags: signing, keystore, tls, reproducibility, upgrade
depends: GRD-006
updated: 2026-11-11
agent_hint: 密钥是长期资产不是构建产物；缺失应失败而不是自动生成，构建后核对指纹与 checksum
severity: S2
domain: bridge
---

## 症状

- 构建脚本在密钥文件缺失时自动生成新的签名/TLS keystore：换机器、清理目录或新 clone 后重新构建，产出的 APK 签名与证书和线上不一致。
- 原地升级因签名不匹配失败，只能卸载重装：token、权限、配置丢失，需要重新配对。
- TLS 证书变化后服务端证书 pin 校验失败，遥测桥请求被拒或连接失败。
- 口令使用脚本内默认回退或环境变量传递不一致，不同人/不同机器构建结果不同。

## 触发场景

- 新机器/新 clone 首次构建，或构建目录被清理；
- keystore/证书没有备份，或只留在某一台机器的 gitignored 目录里；
- CI 每次干净构建；多人协作构建；
- 轮换口令/证书时没有固定策略与记录。

## 根因

- 把密钥材料当成“构建产物”：缺失即自动生成，导致环境一换身份就变。
- 签名 key 是 APK 更新身份的根：换 key 等于换 App，token/权限无法迁移；TLS 证书 pin 同理。
- 密钥与口令没有纳入受控资产：gitignore 排除（正确）但无备份、无指纹、无生成审计。
- 默认口令回退让轮换与审计失效：看起来能构建，实际无法确认用的是哪份密钥。

## 规避与修复

1. 密钥是长期资产：首次生成后立即备份到受控加密存储（另存离线一份），记录指纹/证书 SHA-256/生成时间。
2. 构建脚本：密钥缺失时**失败**而不是自动生成；若提供 bootstrap 生成模式，必须强制提示“立即备份”。
3. 口令策略：通过环境变量/秘密存储注入，禁止脚本内默认口令回退；轮换要有记录与回滚方案。
4. 同签名原地升级：升级用同一签名 key `install -r`，保留 token/权限；升级前备份 token 与证书配置。
5. 证书轮换：走维护窗口，服务端 pin 同步更新，失败可回滚；轮换后验证桥连接与字段。
6. checksum 入档：APK/证书/keystore 指纹写入构建记录与案例；构建后核对一致。
7. 验证：在干净环境用备份密钥重建，产物签名/证书与记录一致。

## 验证

- 新机器/干净目录用备份密钥构建：`apksigner verify --print-certs` 指纹与记录一致，证书 SHA-256 一致。
- 负向验证：删除密钥后构建应失败并提示，而不是静默生成新密钥。
- 升级 `install -r` 成功且 token 保留；证书变更时服务端 pin 同步、连接恢复。
- 密钥备份可从受控存储恢复并成功构建（演练一次）。

## 关联

- 护栏：[GRD-006 秘密卫生](../guardrails/GRD-006-secret-hygiene.md)
- 方法论：[MTH-005 宿主遥测桥](../methodology/04-telemetry-bridge.md)（证书/token 生命周期与构建产物）
- 同类：[PIT-015 明文凭据](PIT-015-plaintext-credentials.md)、[PIT-019 伪 pin 安全缺口](PIT-019-fake-pinning-bridge.md)

## 证据

- 案例实证：[33 Bridge MVP 实施记录 §2/§8.1](../docs/50-bridge/33-Android-Bridge-MVP实施记录.md)（构建材料自动生成、release 同签名原地升级与 token 保留）
- 案例实证：[android-bridge/README §1/§7](../android-bridge/README.md)（密钥首次构建自动生成、gitignored、口令环境变量覆盖）
- 案例实证：[28 全栈整体方案规范 §10.2/§10.3](../docs/00-overview/28-全栈整体方案规范.md)（产物与证书 pin、升级与轮换要求）
- 只读引用：[build.ps1](../android-bridge/build.ps1)（密钥生成/口令探测实现，不在此复述取值）
