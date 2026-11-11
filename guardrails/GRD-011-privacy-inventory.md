---
id: GRD-011
title: 隐私数据采集与脱敏
type: guardrail
status: current
audience: human, agent
tags: privacy, serial, pii, redaction, gitignore, retention
depends: MTH-007
updated: 2026-11-11
agent_hint: 采集或引用设备数据前先判定是否含隐私字段；默认脱敏、默认不入库，报告中只写占位符与聚合结论。
severity: blocker
scope: repo
---

# GRD-011 · 隐私数据采集与脱敏

> 设备序列号、SSID、账号与应用清单看起来"只是技术字段"，组合起来足以识别个人与生活轨迹。方法论仓库默认不应保存它们。

## 红线（MUST NOT）

1. **R1** **MUST NOT** 把原始设备采集产物入库：序列号、IMEI/MEID、Android ID、SSID/BSSID、MAC、IP、位置、账号、联系人相关路径、完整应用清单、使用时长。
2. **R2** **MUST NOT** 在文档、报告、聊天或截图中展示可识别个人的原始值；必须脱敏或只写聚合结论。
3. **R3** **MUST NOT** 让运行期设备档案进入公开目录/版本库；`profiles/`、采集快照与备份必须被忽略，只有脱敏样例可入库。
4. **R4** **MUST NOT** 超范围采集或超期保留：只采集完成当前目标所需字段，并定义删除/复核周期；不得"先全采以后再说"。
5. **R5** **MUST NOT** 在快照中发现误写入的凭据/隐私后继续提交；应删除该快照、重新采集并轮换相关秘密（见 [GRD-006](GRD-006-secret-hygiene.md)）。
6. **R6** **MUST NOT** 把隐私字段交给未获同意的外部服务或第三方工具（见 [GRD-009](GRD-009-external-services-consent.md)）。

## 为什么（风险与案例）

- 案例采集快照明确包含设备序列号、指纹、WiFi IP/BSSID、已装应用清单等隐私字段，因此目录整体不入库、分享前必须裁剪或打码（见 [inventory 隐私说明](../inventory/README.md)）。
- 数据一旦进入仓库历史或聊天，就难以彻底回收；"脱敏后再入库"是唯一可控的路径。
- 新层文档需要可迁移的案例证据，但证据只需"字段、结论与时间"，不需要原始标识；脱敏不降低证据价值。
- 案例实证：[.gitignore](../.gitignore) 的采集/备份忽略规则、[28 全栈规范 §7.2](../docs/00-overview/28-全栈整体方案规范.md) 的 null/来源语义、[15 保险库](../docs/40-console/15-账号密码保险库.md) 的访问控制。

## 允许的替代（MUST/SHOULD/MAY）

- **MUST** 采集前写清字段清单与用途；采集后先脱敏再引用，原始产物只留本地受控目录。
- **MUST** 用占位符或不可逆哈希替代标识；报告默认展示型号级别信息与聚合统计。
- **MUST** 用忽略规则保护运行期档案/快照/备份；提交前用 `git check-ignore` 与 `git status` 复核。
- **SHOULD** 定义保留周期与删除流程；分享前二次审查，截图裁剪掉通知栏、账号与网络信息。
- **SHOULD** 在案例 profile 中提供"已脱敏"声明与字段来源，让读者知道哪些值被移除。
- **MAY** 需要长期证据时保存脱敏副本 + 采集时间 + 命令，而不是原始全量。

## 检查方式（Agent 可执行）

```bash
git check-ignore -v profiles/ inventory/ backup/ android-bridge/build/
git status --short --untracked-files=all
git ls-files | grep -iE 'profiles?/|inventory/|serial|bssid|ssid'
git grep -nE '([0-9]{1,3}\.){3}[0-9]{1,3}|[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}'
```

- 命中处理：在**本次变更范围/新层文件**内命中真实 IP/MAC/标识即判违规；案例旧文档为冻结证据，只做标注不据此改历史。
- 人工核对：本次新增/修改的采集脚本、报告、截图是否含可识别字段；是否已脱敏。
- 人工核对：运行期档案目录是否被忽略、是否误提交；`git status` 中是否出现采集/备份文件。
- 保留核对：是否有保留周期与删除记录；误写入秘密的快照是否已删除并触发轮换。

## 关联

- 踩坑：[PIT-015 明文凭据入库](../pitfalls/PIT-015-plaintext-credentials.md)、[PIT-008 OEM 重启重置权限](../pitfalls/PIT-008-miui-permission-reset.md)
- 护栏：[GRD-006 密钥卫生](GRD-006-secret-hygiene.md)、[GRD-009 外部服务同意](GRD-009-external-services-consent.md)、[GRD-013 不伪造验收](GRD-013-no-fake-acceptance.md)
- 方法论：[MTH-007 安全与密钥生命周期](../methodology/06-security.md)、[MTH-005 宿主遥测桥](../methodology/04-telemetry-bridge.md)
- 案例：[haydn K40 Pro 案例](../cases/haydn-k40pro/README.md)、[inventory 隐私说明](../inventory/README.md)
