---
id: PIT-000
title: 踩坑库索引（Pitfalls Index）
type: pitfall
status: current
audience: human, agent
tags: index, pitfalls, severity, evidence
depends: MTH-001, GRD-013
updated: 2026-11-11
agent_hint: 先按严重度与域检索，再读对应 PIT；新增条目必须带可复现证据与验证步骤
severity: S4
domain: docs
---

# 踩坑库（Pitfalls）

> 这里是**证据层**：把真实改造过程中踩过的坑沉淀成可检索、可复现、可被 Agent 直接消费的条目。
> 每条 PIT 回答：**怎么坏掉的 / 为什么坏 / 怎么避免和修 / 怎么验证修好了**。上位与边界：[AGENTS.md](../AGENTS.md) · [MTH-011](../methodology/10-document-lifecycle.md)（归档与阅读预算）· [方法论文档地图](../methodology/README.md)。

## 1. 用途

- **反推规范**：每条坑对应一条应该存在的红线或规范；PIT 与 [GRD](../guardrails/README.md) / [MTH](../methodology/README.md) 交叉引用。
- **换机复用**：新设备/新 OEM 接入前先按严重度与域过滤，避免重蹈覆辙。
- **Agent 检索**：稳定 ID + flat front matter + 机器索引（`agent-manifest.d/pitfalls.json`）。
- **验收依据**：每条都有可执行验证步骤；不是故障流水账，只保留可迁移教训（换一台 Android 手机仍成立的部分）。

## 2. 严重度分级（S1–S4）

| 级别 | 含义 | 处理要求 |
|---|---|---|
| **S1** | 数据丢失 / 设备变砖 / 安全事故（含电池等硬件安全） | 必须先过 [GRD](../guardrails/README.md) 红线；不满足即停止 |
| **S2** | 服务中断 / 开机不自启 / 失联不可远程恢复 | 变更前设计回滚与恢复通道，变更后验证 |
| **S3** | 效率黑洞 / 返工 / 能力路线被否导致重做 | 记录决策门，先探测再动手 |
| **S4** | 质量 / 一致性 / 可维护性问题 | 纳入校验与索引，定期整理 |

> 严重度描述的是**这一条坑的风险等级**，不是事故已发生时的损失等级；已发生事故的证据统一放 `## 证据`。

## 3. 检索与格式

1. **按 ID**：`pitfalls/PIT-NNN-*.md`；ID 只增不复用；索引见 §5。
2. **按严重度**：先读 S1（PIT-002/011/015/017），再读 S2（服务中断类）。
3. **按域**：`domain` 取 `device / boot / server / bridge / security / ops / docs`；按 OEM 字段复核厂商相关条目。
4. **按机器索引**：`agent-manifest.d/pitfalls.json` 含 id/title/tags/severity/domain；不要手改生成物。
5. **格式**：文件名 ASCII；front matter 是**文件头部**（首行 `---` 到下一个 `---`）；必填 8 键 + **PIT 额外必需 `severity`、`domain`**；正文固定七个 H2：`症状 / 触发场景 / 根因 / 规避与修复 / 验证 / 关联 / 证据`；只用相对链接、禁止 `#anchor`、禁止绝对路径/IP/凭据/个人信息；建议 40–80 行。
6. **证据**：案例实证必须回链 `../docs/` 或 `../cases/`；无案例时写"通用风险，待案例验证"；不得编造。

## 4. 新增一条 PIT（步骤）

1. **找证据**：从案例文档、复盘、日志、命令输出中找可复现事实；没有证据只登记为"通用风险，待案例验证"。
2. **取号**：查本索引与 `agent-manifest`，取下一个未使用的 `PIT-NNN`；编号只增不复用。
3. **建文件**：按 [pitfall 模板](../toolkit/templates/pitfall.md) 新建 `pitfalls/PIT-NNN-*.md`，写 front matter + 七段。
4. **交叉链接**：至少关联一条 [GRD](../guardrails/README.md) 或 [MTH](../methodology/README.md)；同类互链；证据回链案例；更新 §5 索引。
5. **跑校验**：`python -m toolkit.repurpose validate --strict`、`python -m toolkit.repurpose index`、`python scripts/dev/check-links.py --strict-anchors` 全绿后，由 Lead 统一提交并记 CHANGELOG 当前窗口。

## 5. 索引（PIT-000 总表）

| ID | 标题 | 严重度 | 域 | 一句话 | 链接 |
|---|---|---|---|---|---|
| PIT-001 | 非 ASCII 路径导致 aapt2 构建失败 | S3 | docs | 仓库/构建路径必须纯 ASCII，junction 不是方案 | [PIT-001](PIT-001-ascii-path-aapt2.md) |
| PIT-002 | 卸载系统包导致 bootloop | S1 | device | 系统包只 disable，禁止 uninstall；误删即系统进程崩溃循环 | [PIT-002](PIT-002-system-package-uninstall-bootloop.md) |
| PIT-003 | kill-all 杀死 proot 服务栈 | S2 | server | 禁止 `am kill-all`/force-stop Termux，恢复慢且无远程入口 | [PIT-003](PIT-003-kill-all-proot.md) |
| PIT-004 | FBE 锁屏凭据阻断开机自启 | S2 | boot | 无人值守要求无锁屏凭据，否则重启后需人工解锁一次 | [PIT-004](PIT-004-fbe-lockscreen-boot.md) |
| PIT-005 | 无 Root 读不到全局 proc 指标 | S3 | device | 不可得字段用 null，禁止伪造 0；面板必须标来源与新鲜度 | [PIT-005](PIT-005-no-root-proc-metrics.md) |
| PIT-006 | 内核缺 USER_NS/PID_NS 容器不可用 | S3 | device | 先探测再决策；容器路线在多数 Android 内核上直接否 | [PIT-006](PIT-006-no-user-ns-containers.md) |
| PIT-007 | proot ptrace 税与热降频 | S2 | server | 常驻 19–33% 单核，高频看门狗会放大；需预算、散热与降频 | [PIT-007](PIT-007-proot-overhead-thermal.md) |
| PIT-008 | MIUI 重启重置通知/用量权限 | S3 | bridge | FGS 仍活但通知不可见、usage 字段为空；按能力降级而不是报故障 | [PIT-008](PIT-008-miui-permission-reset.md) |
| PIT-009 | OEM 后台清理杀死 FGS | S2 | bridge | 仅 appops/deviceidle 不够，必须 OEM 自启/省电白名单 + 重启验证 | [PIT-009](PIT-009-oem-fgs-killer.md) |
| PIT-010 | 国行/运营商 ROM 官方解锁关闭 | S3 | device | 先过解锁决策门再谈 Root；失败即转 A/A+，不做非官方解锁 | [PIT-010](PIT-010-cn-oem-unlock-closed.md) |
| PIT-011 | 电池 sysfs 不可读，无法脚本限充 | S1 | device | 长期插电只能靠厂商充电保护 + 物理散热，并按安全风险对待 | [PIT-011](PIT-011-battery-sysfs-unreadable.md) |
| PIT-012 | 厂商安装器弹窗让 ADB 安装脆弱 | S3 | device | UI 自动化依赖文案/分辨率；优先人工白名单，脚本必须有超时与回退 | [PIT-012](PIT-012-oem-installer-ui-automation.md) |
| PIT-013 | ADB 授权/无线调试脆弱 | S2 | ops | ADB 只作维护窗口通道；必须有第二条恢复路径与恢复步骤 | [PIT-013](PIT-013-adb-fragility.md) |
| PIT-014 | 未测试就 reload 配置导致自锁失联 | S2 | server | 先备份、离线 test、保留第二通道、失败自动回滚 | [PIT-014](PIT-014-config-reload-lockout.md) |
| PIT-015 | 明文凭据进入脚本/日志/历史 | S1 | security | 发现即轮换；秘密只进受控存储；历史泄露按已泄露处理 | [PIT-015](PIT-015-plaintext-credentials.md) |
| PIT-016 | 签名/TLS 密钥缺省生成导致不可复现 | S2 | bridge | 密钥是长期资产：生成一次、备份、固定口令策略、checksum 入档 | [PIT-016](PIT-016-generated-signing-keys-repro.md) |
| PIT-017 | 只做快照不回滚/不演练=假安全 | S1 | ops | 快照 + 恢复验证 + 定期演练，三者缺一不可 | [PIT-017](PIT-017-snapshot-without-rollback.md) |
| PIT-018 | proot 挂载假设错误导致服务全灭 | S2 | server | 最小绑定、启动断言、固定启动上下文；不要绑定共享存储 | [PIT-018](PIT-018-proot-mount-assumptions.md) |
| PIT-019 | "证书 pin"名不副实的安全承诺缺口 | S2 | security | 自签证书+静态口令+明文 token+无配对轮换≈伪加固；按上限说明 | [PIT-019](PIT-019-fake-pinning-bridge.md) |
| PIT-020 | 看门狗误判/自救级联重启风暴 | S2 | server | 状态机 + 宽限期 + 有界重启 + 退避 + 独立观测 | [PIT-020](PIT-020-watchdog-selfheal-cascade.md) |

## 6. 关系与冻结

- **[guardrails/](../guardrails/README.md)**：MUST NOT 红线；PIT 根因应反推是否有对应 GRD，没有则先补证据再提红线。
- **[methodology/](../methodology/README.md)**：规范正文；PIT 反推规范缺口，规范变更回链本库。
- **[toolkit/](../toolkit/README.md)**：模板/schema/校验/索引都走工具，不手写索引；新增条目上 §4。
- **冻结**：`docs/`、`scripts/` 与案例是历史证据，只允许事实纠错；偏差必须保留，不得为了"看起来完成"删除。

*检索入口：本文件 + `agent-manifest.d/pitfalls.json`；最后更新 2026-11-11。*
