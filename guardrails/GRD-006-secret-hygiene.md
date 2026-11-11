---
id: GRD-006
title: 密钥与凭据卫生
type: guardrail
status: current
audience: human, agent
tags: secrets, token, private-key, rotation, gitignore, logging
depends: MTH-007
updated: 2026-11-11
agent_hint: 发现任何真实 token/口令/私钥/证书/备份口令时，先停止复制与回显，按生命周期处理并要求轮换；文档中只保留占位符。
severity: blocker
scope: repo
---

# GRD-006 · 密钥与凭据卫生

> 秘密的价值在于"只出现一次、只存在一处"。任何进入日志、聊天或仓库的历史，都应视为已泄露，先轮换再清理。

## 红线（MUST NOT）

1. **R1** **MUST NOT** 把任何真实秘密写入仓库、文档、日志、聊天、截图、公网页面或 URL：token、登录口令、私钥、证书与配套密钥、备份口令、保险库密钥、签名密钥、ADB 密钥。
2. **R2** **MUST NOT** 回显或复述用户粘贴的秘密；发现聊天/工单中出现秘密时，提醒用户轮换，并在后续记录中只写 `<redacted>` 或"已轮换"。
3. **R3** **MUST NOT** 提交备份、设备采集快照、签名材料与密钥库；构建产物与证书目录必须被忽略；签名密钥要可复现生成（用文档化流程），不得入库保管。
4. **R4** **MUST NOT** 记录带凭据的 URL 或请求头；日志/审计只保留操作类型、目标、时间、来源与脱敏结果，不保留 Authorization 值或 token。
5. **R5** **MUST NOT** 复用同一秘密于多服务，或让控制面（DSH/网页）持有遥测桥/设备 token；不同信任域必须分离凭据。
6. **R6** **MUST NOT** 把"以后删除某次提交"当作补救；历史仍可恢复。正确顺序是：先轮换/吊销，再评估是否清理历史。
7. **R7** **MUST NOT** 让明文导出物（保险库导出、调试配置、临时凭据文件）留在共享目录；用完即删，密钥与密文分开保管。

## 为什么（风险与案例）

- 案例中曾在会话里出现 SSH 私钥，处置建议是"重新生成并替换"，而不是假定没人看到；这是最典型的泄露面（见 [08 事故复盘](../docs/20-server/08-事故复盘与重置重建报告.md) 遗留事项）。
- 服务端存在多份明文凭据配置文件（权限受限但仍是明文）；保险库设计用 AES + HMAC 加密落盘，管理 token 与保险库密钥分离（见 [15 账号密码保险库](../docs/40-console/15-账号密码保险库.md)）。
- 凭据一旦进入备份、日志或 URL，会随复制扩散；轮换缺验证会造成"以为换了、旧值仍可用"的假安全感（见 PIT-015、PIT-016、PIT-019）。
- 案例实证：[28 全栈规范 §8 安全](../docs/00-overview/28-全栈整体方案规范.md)、[inventory 隐私说明](../inventory/README.md)。

## 允许的替代（MUST/SHOULD/MAY）

- **MUST** 用加密随机数生成秘密；落盘权限最小化（如 600），集中存放于受控目录/Keystore/加密保险库，并记录"位置与保管责任"，不记录值。
- **MUST** 备份加密且口令与密钥分离保管；备份校验和轮换都要有记录。
- **MUST** 轮换走维护窗口：新旧并存过渡 → 验证新值可用、旧值被拒 → 吊销/销毁旧值 → 更新审计记录。
- **SHOULD** 在 CI/本地做秘密扫描与逐条分级（命中字段名/文件名不算违规，命中真实值才算）。
- **SHOULD** 每个秘密记录生命周期：生成、存储、备份、轮换、吊销、事故处置；定期复核未使用的旧凭据。
- **MAY** 用短时效 token、一次性配对码或 mTLS 降低长期凭据价值；接入前评估成本与失败模式。

## 检查方式（Agent 可执行）

```bash
git ls-files | grep -iE '\.(pem|key|p12|jks|keystore)$|token|credential|secret'
git check-ignore -v backup/ profiles/ inventory/ android-bridge/build/ android-bridge/certs/
git grep -nE 'BEGIN (OPENSSH|RSA|EC|PGP|PRIVATE) KEY|Authorization: Bearer'
git grep -nE '(password|passwd|secret|token)[[:space:]]*=[[:space:]]*[A-Za-z0-9+/=_-]{16,}'
```

- 命中处理：上面命令的输出必须逐条判定；出现真实值即按泄露处置（轮换 + 记录），字段名/文件名命中不算违规。
- 人工核对：`.gitignore` 是否覆盖备份、采集、构建产物、证书与签名材料；仓库中是否有明文凭据文件被跟踪。
- 人工核对：日志与审计是否含 Authorization/带 token 的 URL；截图是否打码。
- 轮换核对：最近一次轮换记录是否包含"旧值被拒/新值可用"的实测结果与时间；缺验证视为未完成轮换。

## 关联

- 踩坑：[PIT-015 明文凭据入库](../pitfalls/PIT-015-plaintext-credentials.md)、[PIT-016 生成密钥可复现](../pitfalls/PIT-016-generated-signing-keys-repro.md)、[PIT-019 伪证书 pin](../pitfalls/PIT-019-fake-pinning-bridge.md)
- 护栏：[GRD-004 变更前备份](GRD-004-backup-before-change.md)、[GRD-011 隐私与脱敏](GRD-011-privacy-inventory.md)、[GRD-007 网络最小暴露](GRD-007-network-least-exposure.md)
- 方法论：[MTH-007 安全与密钥生命周期](../methodology/06-security.md)、[MTH-001 边界与原则](../methodology/00-foundations.md)
- 案例：[haydn K40 Pro 案例](../cases/haydn-k40pro/README.md)
