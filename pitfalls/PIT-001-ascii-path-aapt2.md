---
id: PIT-001
title: 非 ASCII 路径导致 aapt2 构建失败
type: pitfall
status: current
audience: human, agent
tags: build, aapt2, windows, ascii-path
depends: MTH-005
updated: 2026-11-11
agent_hint: 构建报 aapt2 路径错误时先验证仓库与 SDK 路径字符集，禁止用 junction 绕行
severity: S3
domain: docs
---

## 症状

- 在 Windows 上构建 Android APK 时 aapt2 阶段失败：报 `Failed to stat ... android.jar`、或者 manifest/assets 路径解析错误，而源码与 JDK 均正常。
- 同一个工程换到另一个目录（路径全英文）后一次构建成功，形成“本地能构建、换机器就失败”的错觉。
- 历史项目出现过：仓库目录为中文名时构建必败；改名为英文仓库后同一条命令直接通过。
- 有人用 ASCII junction/符号链接把工程或 SDK “映射”到英文路径后暂时可用，但清理/换机/备份恢复后链接丢失，问题再次出现。

## 触发场景

- 仓库目录或任意父目录含中文、全角符号、空格等非 ASCII 字符；
- Android SDK 安装/拷贝在含中文的路径，或通过 `ANDROID_HOME` 指向非 ASCII 目录；
- 为绕过路径问题创建 junction/软链接，或把工程复制到临时中文目录再构建；
- 换机、清理临时目录、从备份恢复后，旧的链接方案静默失效。

## 根因

- aapt2 是平台相关的原生工具，在 Windows 上对非 ASCII 路径的编码处理不可靠：资源与 manifest 链接时路径解析失败，最终以 `android.jar` 无法 stat 或 assets 路径错乱的形式暴露。
- 问题出在路径字符集，与 JDK 版本、源码、是否使用 Gradle 无关（本项目用 aapt2 + javac + d8 直编，同样受限）。
- junction/软链接并没有解决“路径字符集”问题，只是把风险换成**固定外部依赖**：不可复现、易残留、换机即失效，属于反面方案。
- 构建脚本若不显式校验路径，错误只在 aapt2 阶段以晦涩方式暴露，浪费大量排障时间并诱导“再绕一次”。

## 规避与修复

1. 仓库与 SDK 目录一律 ASCII：目录名只用英文/数字/连字符，避免中文、空格、全角符号；父目录同样要求 ASCII。
2. 构建脚本启动即做路径守卫：检测仓库根与 SDK 路径中的非 ASCII 字符，命中直接失败并提示“移动/改名到 ASCII 路径后重试”，不要自动兜底。
3. 删除并禁止恢复 junction 方案：旧链接不要保留，不要为了省事重建；换机、清理、恢复备份后它必然断链。
4. 若当前目录无法改名（受管目录/共享盘），把工程克隆/复制到 ASCII 路径再构建，而不是在原路径硬绕。
5. 把“路径必须 ASCII”写进构建文档与前置检查清单，并增加“干净目录完整构建一次”的发布前门禁。
6. 记录构建环境（JDK/SDK 定位顺序与路径约束）到构建文档，避免下一位接手者重新踩。

## 验证

- 在干净目录从头构建成功：产出 APK 与证书，且 `apksigner verify` 通过。
- 负向验证：把仓库复制到含中文字符的路径运行构建脚本，必须在 aapt2 之前失败并给出明确路径错误。
- 检查构建脚本中无 junction 创建逻辑；构建文档无“用 junction 解决”的残留指引。

## 关联

- 方法论：[MTH-005 宿主遥测桥](../methodology/04-telemetry-bridge.md)（APK 构建链、产物与安全边界）
- 护栏：[GRD-012 Agent 行为规则](../guardrails/GRD-012-agent-operating-rules.md)（不引入隐藏外部依赖）
- 工具：[toolkit 索引](../toolkit/README.md)（构建/校验入口）

## 证据

- 案例实证：[29 项目文档评审报告 §8.1/§8.4](../docs/00-overview/29-项目文档评审报告.md)（中文路径是 aapt2 失败根因；去 junction 决策）
- 案例实证：[33 Bridge MVP 实施记录 §9](../docs/50-bridge/33-Android-Bridge-MVP实施记录.md)（改名前后构建对比与验证）
- 案例实证：[当前状态 §6](../docs/00-overview/当前状态.md)（ASCII 路径为当前硬约束）
- 只读引用：[build.ps1](../android-bridge/build.ps1)（路径守卫实现，不在此复述细节）
