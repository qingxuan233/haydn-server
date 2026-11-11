---
id: PIT-012
title: 厂商安装器弹窗让 ADB 安装脆弱
type: pitfall
status: current
audience: human, agent
tags: installer, adb-install, ui-automation, miui, uiautomator
depends: MTH-003
updated: 2026-11-11
agent_hint: 优先人工一次性安装；若用 UI 自动化必须有超时/失败判定/恢复屏幕设置，不能只看命令返回码
severity: S3
domain: device
oem: xiaomi
---

## 症状

- `adb install` 返回 `INSTALL_FAILED_USER_RESTRICTED: Install canceled by user`，实际是厂商安装器弹窗在等待用户确认。
- 用 uiautomator 轮询 + 点击“继续安装”的脚本偶发失败：点不到、点错按钮、安装卡在弹窗、输入法/权限弹窗抢焦点。
- 换语言、分辨率、主题或系统版本后文案变化，脚本直接失效；禁用厂商安装 Activity 被系统拒绝。
- 自动化失败时包并未安装，但后续脚本继续执行，形成“半完成”状态且难以发现。

## 触发场景

- MIUI/HyperOS 等厂商 ROM 拦截 ADB 安装，要求用户在私有安装界面确认；
- 设备息屏/锁屏、亮度超时、前台被其他弹窗占用；
- 复用其他机型/其他语言环境的 UI 自动化脚本；
- 无人值守批量安装多个 APK。

## 根因

- 厂商安全中心拦截标准 `adb install`，用私有 Activity 要求用户确认；这是安全设计，不能用标准命令或 appops 绕过。
- UI 自动化依赖按钮文案、坐标/分辨率与前台焦点，天然脆弱；厂商更新即可让它失效。
- 脚本缺少“安装结果校验”（包是否真的装上）与失败回退（恢复屏幕超时/关闭弹窗），失败被掩盖。
- 试图禁用安装器组件会被系统保护拒绝，绕过路径风险高且不可维护。

## 规避与修复

1. 优先人工一次性安装/授权；把 UI 自动化定位为“可选辅助”，不作为唯一交付路径。
2. 若必须自动化：唤醒并临时延长亮屏；固定分辨率/语言/主题；按钮文案白名单（继续安装/安装/允许/确定）；设置超时与重试上限；结束后恢复屏幕设置。
3. 失败判定以事实为准：安装后用 `pm list packages`/`dumpsys` 校验包存在与版本，而不是只看命令返回码。
4. 不尝试 root/设备所有者绕过安装限制——那是更高风险的路线，且不可持续。
5. 记录 OEM profile 与验证结果（文案、分辨率、版本），换机/升级后重新验证。
6. 失败时保留截图与 logcat，作为下次更新白名单与排障的证据。
7. 批量安装串行执行，前一个失败即停止并报告，避免连续半完成状态。

## 验证

- 连续 3 次安装成功，且每次用包查询校验版本正确。
- 人为改语言/分辨率后，脚本应明确失败并报告，而不是误判成功。
- 失败后屏幕亮度/超时设置已恢复，设备状态无残留弹窗。
- 安装流程有日志与失败证据，换机后可按 profile 重新验证。

## 关联

- 方法论：[MTH-003 路线图与阶段](../methodology/02-roadmap.md)（设备准备阶段的安装与门禁）
- 护栏：[GRD-012 Agent 行为规则](../guardrails/GRD-012-agent-operating-rules.md)（不越权、不引入高风险绕过）
- 同类：[PIT-009 OEM 清理 FGS](PIT-009-oem-fgs-killer.md)、[PIT-013 ADB 维护通道脆弱](PIT-013-adb-fragility.md)

## 证据

- 案例实证：[14 安卓深度操作调研 §3.1/§4.1](../docs/20-server/14-安卓深度操作调研与技能沉淀.md)（MIUI 拦截根因、UI 自动确认方案与局限）
- 案例实证：[32 多厂商 Android 适配 §3/§8](../docs/10-device/32-多厂商Android适配与迁移指南.md)（安装矩阵与当前设备专用 profile）
- 案例实证：[17 研究平台环境构建手册 §5](../docs/20-server/17-研究平台环境构建手册.md)（安装弹窗经验与脚本入口）
- 案例实证：[33 Bridge MVP 实施记录 §4.1](../docs/50-bridge/33-Android-Bridge-MVP实施记录.md)（APK 安装与授权步骤）
