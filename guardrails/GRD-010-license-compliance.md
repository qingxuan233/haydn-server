---
id: GRD-010
title: 开源许可合规
type: guardrail
status: current
audience: human, agent
tags: license, gpl, notice, third-party, supply-chain
depends: MTH-001, MTH-007
updated: 2026-11-11
agent_hint: 引入任何第三方代码/依赖/资产前先确认许可证与来源；GPL 只参考语义不复制代码；发布前必须完成许可审查。
severity: warning
scope: repo
---

# GRD-010 · 开源许可合规

> "参考实现"和"复制代码"之间只差一次 Ctrl+C。许可证污染往往在发布时才被发现，回滚成本远高于提前登记。

## 红线（MUST NOT）

1. **R1** **MUST NOT** 把 GPL/AGPL 或其他强 copyleft 项目的代码复制进本仓库或产品；只允许阅读文档、理解语义后自行实现。
2. **R2** **MUST NOT** 删除或改写第三方文件的版权声明、许可证头与 NOTICE；引入即保留归属与来源。
3. **R3** **MUST NOT** 引入许可证不明、来源不明或禁止再分发的依赖、二进制、字体、图标与模型文件。
4. **R4** **MUST NOT** 在未完成许可审查前发布或对外分发（含 APK、文档打包、镜像与示例工程）。
5. **R5** **MUST NOT** 以"个人自用/不商用"为由忽略许可证义务；公开仓库、分享、交付同样可能构成分发。
6. **R6** **MUST NOT** 把"另一个项目也这么做"当作授权依据；每个依赖都要有自己的许可证记录。

## 为什么（风险与案例）

- 项目规范明确：不复制 GPL 代码，第三方选型优先 Apache/BSD/MIT；Bridge 自建而非 fork GPL 项目的决策正与此相关（见 [28 全栈规范 §13](../docs/00-overview/28-全栈整体方案规范.md)）。
- 参考类项目（去预装工具、API 语义、桥接模式）多数是 GPL 或不同许可证；混用代码会让整个分发物的许可义务失控。
- 许可审查是发布门禁的一部分：依赖清单、传递依赖、二进制资产都要覆盖，遗漏常见于 APK 原生库与前端资源。
- 案例实证：[27 Bridge 架构调研](../docs/50-bridge/27-Android-Bridge-APK架构调研.md) 的开源对比、ADR-009 许可决策。

## 允许的替代（MUST/SHOULD/MAY）

- **MUST** 维护第三方清单：名称、版本、许可证、来源链接、使用方式（运行时/构建时/仅参考）、义务（NOTICE/源码提供）。
- **MUST** 优先选用 Apache-2.0 / BSD / MIT；引入时保留版权与许可文本，必要时生成 NOTICE。
- **MUST** 发布前执行许可审查：直接依赖 + 传递依赖 + 二进制资产 + 文档引用，结论记录到发布清单。
- **SHOULD** 以"参考语义 + 独立实现"替代复制；对 GPL 工具仅作为独立进程/外部工具使用，并记录边界。
- **MAY** 为自研代码声明许可证与 SPDX 标识；对不确定项先咨询用户/维护者，不自行下结论。

## 检查方式（Agent 可执行）

```bash
git ls-files | grep -iE '^(LICEN[CS]E|NOTICE|COPYING)|licen[cs]e|notice'
git grep -nE 'SPDX-License-Identifier|Copyright \(c\)|GNU (General|Affero) Public License'
git ls-files | grep -iE '\.(aar|jar|so|dll|wasm|ttf|otf|woff2?)$'
```

- 人工核对：第三方清单是否存在且与依赖/资产一一对应；缺许可证或来源的条目即判违规。
- 人工核对：本次新增代码是否与 GPL 项目源码高度相似；无法证明独立实现时按违规处理。
- 发布核对：发布清单中是否有许可审查结论、NOTICE 文件、必要源码提供方式。
- 资产核对：APK/前端/文档中的字体、图标、图片、模型是否有可用许可与署名要求。

## 关联

- 踩坑：[../pitfalls/README.md 踩坑索引](../pitfalls/README.md)（许可类问题尚未形成独立 PIT，按通用风险对待）
- 护栏：[GRD-006 密钥卫生](GRD-006-secret-hygiene.md)、[GRD-012 Agent 行为](GRD-012-agent-operating-rules.md)
- 方法论：[MTH-001 边界与原则](../methodology/00-foundations.md)、[MTH-007 安全与密钥生命周期](../methodology/06-security.md)
- 案例：[haydn K40 Pro 案例](../cases/haydn-k40pro/README.md)、[28 规范 §13](../docs/00-overview/28-全栈整体方案规范.md)
