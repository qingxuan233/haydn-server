# haydn-server 文档索引

> **这是全部文档的唯一导航入口。** 项目概览与快速命令见 [根 README](../README.md)；权威状态见 [当前状态](00-overview/当前状态.md)。
> 文档按主题分组、按编号前缀排序；文件名保留中文，目录一律英文（跨平台/工具安全）。

---

## 1. 文档体系

| 概念 | 约定 |
|---|---|
| 分组目录 | `00-overview`（规划/规范/入口）、`10-device`（设备与可行性）、`20-server`（服务器构建运维）、`30-dsh`（DSH 控制面）、`40-console`（Console）、`50-bridge`（Android Bridge）、`90-archive`（已归档） |
| 文档 ID | 每篇头部元数据表带 `HB-XXX-NNN`，跨文档引用优先给“短标签 + 相对链接” |
| 状态 | **现行**（当前有效）/ **历史记录**（实现过程，证据保留）/ **已归档**（不再维护，仅参考） |
| 变更记录 | 全部历史变更集中在 [CHANGELOG.md](../CHANGELOG.md)，不在文档内散落 |
| 状态数字 | 只在 [当前状态](00-overview/当前状态.md) 维护；其他文档引用，不复制 |
| 链接校验 | `python scripts\dev\check-links.py --strict-anchors`（0 error 才提交） |

---

## 2. 推荐阅读路径

| 场景 | 读序 |
|---|---|
| **新会话接手（约 15 分钟）** | [当前状态](00-overview/当前状态.md) → [30 接手指南](00-overview/30-新会话接手指南.md) → [28 全栈规范](00-overview/28-全栈整体方案规范.md)（§2 目标 / §4 架构 / §5–§11）→ [27 Bridge 调研](50-bridge/27-Android-Bridge-APK架构调研.md)（可选） |
| **日常运维** | [03 操作手册](20-server/03-操作手册.md) → [22 Tier2 受控写](30-dsh/22-DSH-Tier2受控写落地.md) → [15 保险库](40-console/15-账号密码保险库.md) |
| **重建/换机** | [17 研究平台环境构建手册](20-server/17-研究平台环境构建手册.md) → [32 多厂商适配](10-device/32-多厂商Android适配与迁移指南.md) → [04 风险与回滚](10-device/04-风险与回滚.md) |
| **排障/事故** | [08 bootloop 复盘](20-server/08-事故复盘与重置重建报告.md) → [04 风险与回滚](10-device/04-风险与回滚.md) → [09 性能优化](20-server/09-性能优化方案与可行性分析.md) |
| **构建 Bridge APK** | [android-bridge/README](../android-bridge/README.md) → [33 Bridge 实施记录](50-bridge/33-Android-Bridge-MVP实施记录.md) → [27 调研](50-bridge/27-Android-Bridge-APK架构调研.md) |
| **只想知道现在怎么样** | [当前状态](00-overview/当前状态.md)（单页） |

---

## 3. 分组索引

### 3.1 `00-overview` — 规划、规范、入口

| 文档 | 说明 | 状态 |
|---|---|---|
| [00-项目规划](00-overview/00-项目规划.md) | 愿景/目标/硬约束/路线决策/P0–P6 阶段/WBS/ADR | 现行 |
| [28-全栈整体方案规范](00-overview/28-全栈整体方案规范.md) | **规范总纲**：三轨架构/接口/数据/安全/可靠性/部署/验收/ADR（v1.5） | 现行 |
| [29-项目文档评审报告](00-overview/29-项目文档评审报告.md) | 2026-11-10 历史评审 + 2026-11-11 结构与命名重构评审 | 历史记录（含现行结论） |
| [30-新会话接手指南](00-overview/30-新会话接手指南.md) | **新会话入口**：状态、读序、下一步、护栏、验收门禁 | 现行 |
| [当前状态](00-overview/当前状态.md) | **权威状态单页**（设备/服务/Bridge/构建/限制/决策） | 现行 |

### 3.2 `10-device` — 设备、可行性、风险、厂商适配

| 文档 | 说明 | 状态 |
|---|---|---|
| [01-设备档案](10-device/01-设备档案.md) | 基线快照 T0：硬件/系统/属性/存储/电池/热区 | 现行（快照） |
| [02-可行性分析](10-device/02-可行性分析.md) | 路线论证与实测证据；B/D 路线已否决 | 历史分析（结论仍有效） |
| [04-风险与回滚](10-device/04-风险与回滚.md) | 风险登记册、回滚手册、阶段准入检查表 | 现行 |
| [31-拍板事项决策分析与Root升级路线](10-device/31-拍板事项决策分析与Root升级路线.md) | D1–D10 决策（已批准）+ Root 后优化清单 | 现行 |
| [32-多厂商Android适配与迁移指南](10-device/32-多厂商Android适配与迁移指南.md) | OEM 自启/省电/安装矩阵、换机迁移 | 现行 |

### 3.3 `20-server` — 服务器构建、运维、优化、复盘

| 文档 | 说明 | 状态 |
|---|---|---|
| [03-操作手册](20-server/03-操作手册.md) | 分阶段操作步骤与命令 | 现行 |
| [06-A+优化方案](20-server/06-A+优化方案.md) | 无 Root A+ 优化（已执行项 + 待办 + 回滚） | 历史记录（待办现行） |
| [08-事故复盘与重置重建报告](20-server/08-事故复盘与重置重建报告.md) | bootloop 事故根因与恢复/重建过程 | 历史记录 |
| [09-性能优化方案与可行性分析](20-server/09-性能优化方案与可行性分析.md) | ADB 视角性能优化：可做/不可做清单 | 历史分析（结论参考） |
| [14-安卓深度操作调研与技能沉淀](20-server/14-安卓深度操作调研与技能沉淀.md) | Shizuku/AppManager/cmd 能力与脚本 | 参考（历史调研） |
| [17-研究平台环境构建手册](20-server/17-研究平台环境构建手册.md) | **从零重建服务器 runbook** | 现行 |
| [18-控制台持久化与容器优化方案](20-server/18-控制台持久化与容器优化方案.md) | SQLite 持久化、3-2-1 备份、看门狗方案 | 历史方案（部分落地） |
| [19-ADB为服务器让资源方案](20-server/19-ADB为服务器让资源方案.md) | ADB 资源让渡方案矩阵 | 历史方案（P0 已执行） |
| [25-ADB资源优化与Console审计落地](20-server/25-ADB资源优化与Console审计落地.md) | ADB 资源 P0 + Console 审计落地记录 | 历史记录 |

### 3.4 `30-dsh` — DSH 控制面

| 文档 | 说明 | 状态 |
|---|---|---|
| [07-DSH与Linux优化](30-dsh/07-DSH与Linux优化.md) | DSH 自托管部署 + Linux 优化 + 手机 ADB 分析 | 历史记录 |
| [10-DSH登录入口优化](30-dsh/10-DSH登录入口优化.md) | `/app/` 免 token 自动登录（cookie broker） | 历史记录 |
| [11-DSH服务器配置与模型](30-dsh/11-DSH服务器配置与模型.md) | desktop → 服务器 profile/模型迁移 | 历史记录 |
| [11-移除DSH-GO-App环境SSH](30-dsh/11-移除DSH-GO-App环境SSH.md) | 移除旧 DSH-GO SSH 隧道（已归档操作） | 历史记录（归档） |
| [12-DSH性能优化](30-dsh/12-DSH性能优化.md) | gzip/长缓存/profile 精简，RSS/JS 体积 | 历史记录 |
| [13-DSH插件安装-pnpm](30-dsh/13-DSH插件安装-pnpm.md) | pnpm 缺失导致插件安装失败 → 修复 | 历史记录 |
| [20-DSH控制平面方案](30-dsh/20-DSH控制平面方案.md) | 控制平面定位/边界/威胁模型/升级思路 | 现行（方案） |
| [21-DSH控制平面落地手册](30-dsh/21-DSH控制平面落地手册.md) | P0 落地步骤（文件/备份/看门狗/限流） | 历史记录（可复用） |
| [22-DSH-Tier2受控写落地](30-dsh/22-DSH-Tier2受控写落地.md) | Tier2 `--confirm` + 快照 + 审计机制 | 现行机制 |
| [23-DSH蓝绿升级演练](30-dsh/23-DSH蓝绿升级演练.md) | 蓝绿切换/验证/回滚演练 | 历史演练（可复用） |
| [24-DSH-sessions持久化补全](30-dsh/24-DSH-sessions持久化补全.md) | sessions 备份接入 server-backup | 历史记录 |

### 3.5 `40-console` — Console 控制台

| 文档 | 说明 | 状态 |
|---|---|---|
| [09-文件管理-文件夹打包下载](40-console/09-文件管理-文件夹打包下载.md) | `/files/api/zip` 文件夹打包下载 | 历史记录 |
| [10-面板治理-移除CI-Runner](40-console/10-面板治理-移除CI-Runner.md) | 移除 Runner 卡片（保留按需 runner） | 历史记录 |
| [13-控制台功能分析与完善](40-console/13-控制台功能分析与完善.md) | Console v2：API/服务/日志/备份/趋势 | 现行功能说明 |
| [15-账号密码保险库](40-console/15-账号密码保险库.md) | AES+HMAC 加密保险库与审计 | 现行 |
| [17-控制台移动端适配](40-console/17-控制台移动端适配.md) | 390px 无溢出、折叠、吸顶导航 | 现行 |
| [26-Console手机状态补全](40-console/26-Console手机状态补全.md) | 手机状态字段补全（Termux:API 时代） | 历史记录（Bridge 已取代） |
| [34-Console总览详情改版](40-console/34-Console总览详情改版.md) | 最新信息架构：总览 + `?view=details` | 现行（最新界面） |

### 3.6 `50-bridge` — Android Bridge

| 文档 | 说明 | 状态 |
|---|---|---|
| [27-Android-Bridge-APK架构调研](50-bridge/27-Android-Bridge-APK架构调研.md) | 方案对比、Android 14/15 证据、实施建议 | 历史调研（结论现行依据） |
| [33-Android-Bridge-MVP实施记录](50-bridge/33-Android-Bridge-MVP实施记录.md) | Phase 0/1 MVP → release 加固 → Phase 2 字段 | 历史记录（最新进展） |

### 3.7 `90-archive` — 已归档（仅历史参考）

| 文档 | 说明 | 状态 |
|---|---|---|
| [05-B路线执行手册](90-archive/05-B路线执行手册.md) | 解锁+Root+chroot 执行手册（B 路线已取消） | 已归档 |
| [16-非官方Root路径可行性与风险研究](90-archive/16-非官方Root路径可行性与风险研究.md) | 非官方 Root 路径历史研究 | 已归档 |
| [README-2026-11-10](90-archive/README-2026-11-10.md) | 旧版 README（重构前归档） | 已归档 |
| [raw-notes](90-archive/raw-notes.md) | Android/Bridge 调研原始笔记 | 已归档 |

### 3.8 `assets` — 文档截图

`assets/` 存放 Console 总览/详情、移动端、v2 等截图，被 [34](40-console/34-Console总览详情改版.md) 等文档引用。

---

## 4. 旧编号对照（兼容历史对话引用）

> 2026-11-11 前的文档统一在 `docs/` 平铺并带 `NN-` 编号（其中 09/10/11/13/17 存在重号）。重构后按主题分组，编号前缀保留，旧引用按下表转换。

| 旧路径 | 新路径 |
|---|---|
| `docs/00-项目规划.md` | [00-overview/00-项目规划](00-overview/00-项目规划.md) |
| `docs/28-全栈整体方案规范.md` | [00-overview/28-全栈整体方案规范](00-overview/28-全栈整体方案规范.md) |
| `docs/29-项目文档评审报告.md` | [00-overview/29-项目文档评审报告](00-overview/29-项目文档评审报告.md) |
| `docs/30-新会话接手指南.md` | [00-overview/30-新会话接手指南](00-overview/30-新会话接手指南.md) |
| `docs/01-设备档案.md` | [10-device/01-设备档案](10-device/01-设备档案.md) |
| `docs/02-可行性分析.md` | [10-device/02-可行性分析](10-device/02-可行性分析.md) |
| `docs/04-风险与回滚.md` | [10-device/04-风险与回滚](10-device/04-风险与回滚.md) |
| `docs/31-拍板事项…Root升级路线.md` | [10-device/31-拍板事项决策分析与Root升级路线](10-device/31-拍板事项决策分析与Root升级路线.md) |
| `docs/32-多厂商Android适配…md` | [10-device/32-多厂商Android适配与迁移指南](10-device/32-多厂商Android适配与迁移指南.md) |
| `docs/03-操作手册.md` | [20-server/03-操作手册](20-server/03-操作手册.md) |
| `docs/06-A+优化方案.md` | [20-server/06-A+优化方案](20-server/06-A+优化方案.md) |
| `docs/08-事故复盘…报告.md` | [20-server/08-事故复盘与重置重建报告](20-server/08-事故复盘与重置重建报告.md) |
| `docs/09-性能优化…分析.md` | [20-server/09-性能优化方案与可行性分析](20-server/09-性能优化方案与可行性分析.md) |
| `docs/14-安卓深度操作…沉淀.md` | [20-server/14-安卓深度操作调研与技能沉淀](20-server/14-安卓深度操作调研与技能沉淀.md) |
| `docs/17-研究平台环境构建手册.md` | [20-server/17-研究平台环境构建手册](20-server/17-研究平台环境构建手册.md) |
| `docs/18-控制台持久化…方案.md` | [20-server/18-控制台持久化与容器优化方案](20-server/18-控制台持久化与容器优化方案.md) |
| `docs/19-ADB为服务器让资源方案.md` | [20-server/19-ADB为服务器让资源方案](20-server/19-ADB为服务器让资源方案.md) |
| `docs/25-ADB资源优化…落地.md` | [20-server/25-ADB资源优化与Console审计落地](20-server/25-ADB资源优化与Console审计落地.md) |
| `docs/07-DSH与Linux优化.md` | [30-dsh/07-DSH与Linux优化](30-dsh/07-DSH与Linux优化.md) |
| `docs/10-DSH登录入口优化.md` | [30-dsh/10-DSH登录入口优化](30-dsh/10-DSH登录入口优化.md) |
| `docs/11-DSH服务器配置与模型.md` | [30-dsh/11-DSH服务器配置与模型](30-dsh/11-DSH服务器配置与模型.md) |
| `docs/11-移除DSH-GO-App环境SSH.md` | [30-dsh/11-移除DSH-GO-App环境SSH](30-dsh/11-移除DSH-GO-App环境SSH.md) |
| `docs/12-DSH性能优化.md` | [30-dsh/12-DSH性能优化](30-dsh/12-DSH性能优化.md) |
| `docs/13-DSH插件安装-pnpm.md` | [30-dsh/13-DSH插件安装-pnpm](30-dsh/13-DSH插件安装-pnpm.md) |
| `docs/20-DSH控制平面方案.md` | [30-dsh/20-DSH控制平面方案](30-dsh/20-DSH控制平面方案.md) |
| `docs/21-DSH控制平面落地手册.md` | [30-dsh/21-DSH控制平面落地手册](30-dsh/21-DSH控制平面落地手册.md) |
| `docs/22-DSH-Tier2受控写落地.md` | [30-dsh/22-DSH-Tier2受控写落地](30-dsh/22-DSH-Tier2受控写落地.md) |
| `docs/23-DSH蓝绿升级演练.md` | [30-dsh/23-DSH蓝绿升级演练](30-dsh/23-DSH蓝绿升级演练.md) |
| `docs/24-DSH-sessions持久化补全.md` | [30-dsh/24-DSH-sessions持久化补全](30-dsh/24-DSH-sessions持久化补全.md) |
| `docs/09-文件管理-文件夹打包下载.md` | [40-console/09-文件管理-文件夹打包下载](40-console/09-文件管理-文件夹打包下载.md) |
| `docs/10-面板治理-移除CI-Runner.md` | [40-console/10-面板治理-移除CI-Runner](40-console/10-面板治理-移除CI-Runner.md) |
| `docs/13-控制台功能分析与完善.md` | [40-console/13-控制台功能分析与完善](40-console/13-控制台功能分析与完善.md) |
| `docs/15-账号密码保险库.md` | [40-console/15-账号密码保险库](40-console/15-账号密码保险库.md) |
| `docs/17-控制台移动端适配.md` | [40-console/17-控制台移动端适配](40-console/17-控制台移动端适配.md) |
| `docs/26-Console手机状态补全.md` | [40-console/26-Console手机状态补全](40-console/26-Console手机状态补全.md) |
| `docs/34-Console总览详情改版.md` | [40-console/34-Console总览详情改版](40-console/34-Console总览详情改版.md) |
| `docs/27-Android-Bridge-APK架构调研.md` | [50-bridge/27-Android-Bridge-APK架构调研](50-bridge/27-Android-Bridge-APK架构调研.md) |
| `docs/33-Android-Bridge-MVP实施记录.md` | [50-bridge/33-Android-Bridge-MVP实施记录](50-bridge/33-Android-Bridge-MVP实施记录.md) |
| `docs/05-B路线执行手册.md` | [90-archive/05-B路线执行手册](90-archive/05-B路线执行手册.md) |
| `docs/16-非官方Root路径…研究.md` | [90-archive/16-非官方Root路径可行性与风险研究](90-archive/16-非官方Root路径可行性与风险研究.md) |
| `docs/archive/README-2026-11-10.md` | [90-archive/README-2026-11-10](90-archive/README-2026-11-10.md) |
| `docs/research/raw-notes.md` | [90-archive/raw-notes](90-archive/raw-notes.md) |

脚本目录对照：`scripts/*.ps1|*.py|*.sh` → `scripts/adb/`（PC 侧设备脚本）、`scripts/termux/`（Termux 侧 shell）、`scripts/server/finalize-dsh-server.sh`；详见 [scripts/README](../scripts/README.md)。

---

## 5. 维护规则

1. **新增文档**：放入对应分组目录（文件名 `NN-中文标题.md`，编号唯一且不复用）；同步本索引与 [CHANGELOG.md](../CHANGELOG.md)。
2. **修改现行事实**：先改 [当前状态](00-overview/当前状态.md)，再检查引用它的文档；`28` 规范变更需在其 ADR 段记录。
3. **历史文档**：只允许补链接/加归档标注/纠正误导性“当前”表述，不改写历史结论。
4. **链接检查**：`python scripts\dev\check-links.py --strict-anchors`；新增/移动文件必须同步相对链接。
5. **敏感信息**：token/密码/证书/备份口令一律不入库、不入文档、不入日志。
6. **提交**：一次提交包含结构与内容变更，提交信息写清“docs restructure / rename / build”范围。

---

*最后更新：2026-11-11（文档结构与命名重构同日完成）。*
