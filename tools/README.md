# tools 本地工具目录

本目录存放**二进制工具/大文件**（Android SDK、platform-tools、侧载 APK、解锁/Root 工具、UAD 清单等）。**大部分内容 gitignored、不入库**；工具都能从官方渠道重新下载或重建，因此仓库只保留本说明。

> 原则：**工具不是源码**——只记录来源与版本，不提交二进制、不提交大文件、不提交私钥。

| 文档 ID | `HB-OPS-002` |
|---|---|
| 版本 | v1.0（2026-11-11 新建） |
| 状态 | 现行 |
| 关联 | [scripts 索引](../scripts/README.md) · [android-bridge/README.md](../android-bridge/README.md) · [17 研究平台环境构建手册](../docs/20-server/17-研究平台环境构建手册.md) |

## 1. 目录一览

| 路径 | 内容 | 入库 | 用途 | 获取 / 重建 |
|---|---|---|---|---|
| `tools/android-sdk/` | Android SDK：`cmdline-tools/latest`、`platforms/android-35`、`build-tools/35.0.0`、`platform-tools` | ❌ gitignored | **构建 Bridge APK 的前置**（`android-bridge/build.ps1` 自动探测） | 用 sdkmanager 重装（步骤见 [17 构建手册](../docs/20-server/17-研究平台环境构建手册.md)）；无需 ASCII junction |
| `tools/platform-tools/` | 独立副本：`adb.exe` / `fastboot.exe` / `sqlite3.exe` 等 | ❌ gitignored | `scripts/adb/` 默认 adb 定位路径 | `scripts\adb\get-platform-tools.ps1` 重新下载 |
| `tools/apks/` | 侧载 APK：`appmanager.apk`、`canta.apk`、`hail.apk`、`shizuku.apk`、`termux-api.apk` | ❌ gitignored | 设备侧无 Root 工具链（AppOps/冻结/卸载/ADB 特权） | 各自官方 GitHub/F-Droid 下载；用 `scripts/adb/miui-adb-install.ps1` 安装 |
| `tools/termux/` | `termux-app-arm64.apk` | ❌ gitignored | Termux 本体安装包 | F-Droid / Termux GitHub Releases |
| `tools/termux-boot/` | `termux-boot.apk` | ❌ gitignored | Termux:Boot 开机自启插件 | F-Droid |
| `tools/mi-unlock/` | 小米官方 Mi Unlock 工具（`miflash_unlock.exe`、驱动、`MiLoginTool`） | ❌ gitignored（体积大 + 账号相关） | B 路线解锁物料；**B 路线已取消**，仅历史保留 | miui.com/unlock 官方下载 |
| `tools/magisk/` | `Magisk-v31.1.apk` | ❌ gitignored | Root 方案物料；**设备无 Root、未使用**，仅历史保留 | Magisk 官方 GitHub Releases |
| `tools/uad_lists.json` | UAD-NG 包清单 | ❌ gitignored | `scripts/adb/uad-compare.py` 的数据源（只读比对） | UAD-NG 项目发布 |
| `tools/firmware/` | （如存在）原厂 fastboot 固件 | ❌ gitignored | 救砖 / B 路线回滚物料 | 小米官方 ROM（需校验版本与哈希） |
| `tools/*.zip` | 下载缓存（如 `platform-tools-*.zip`） | ❌ gitignored | 解压后可删除 | 重新下载 |

> 说明：`tools/` 里的东西**不是**项目运行必需。删掉整个目录后，设备/服务器仍可运行；只是重新构建 APK 或做设备操作前需要按上表恢复相应工具。

## 2. 规则

1. **不提交大文件**：APK / SDK zip / 固件 / 工具包一律 gitignored；需要时按官方渠道重下。
2. **不提交私钥/证书**：Bridge 的 `android-bridge/assets/bridge.p12`、`android-bridge/signing.p12`、`android-bridge/certs/` 都在 gitignore 里，同理不要放进 `tools/`。
3. **不放 token/口令**：tools 目录不保存任何凭据（服务器凭据在加密保险库/`/root/server/etc`）。
4. **不改 SDK 内容**：升级/重装 SDK 用 sdkmanager；`build.ps1` 每次构建会重新探测 SDK，无需手改路径。
5. **mi-unlock 涉及小米账号**：只在本机使用，不上传、不外发、不放进任何备份公开份。
6. 本目录是**本地环境**，换机/重置后按 [17 构建手册](../docs/20-server/17-研究平台环境构建手册.md) 重建。

## 3. 与构建链/脚本的关系

```text
tools/android-sdk        → android-bridge/build.ps1（自动探测 SDK/JDK）→ android-bridge/build/bridge.apk
tools/platform-tools     → scripts/adb/*.ps1（默认 adb 路径）→ 设备采集/安装/优化
tools/apks/*.apk         → adb install / miui-adb-install.ps1（侧载）
tools/uad_lists.json     → scripts/adb/uad-compare.py（只读对比）
tools/mi-unlock、magisk  → B 路线历史物料（B 路线已取消，不再使用）
```

相关文档：[android-bridge/README.md](../android-bridge/README.md)（构建/安装/测试）、[scripts/README.md](../scripts/README.md)（脚本索引）、[17 研究平台环境构建手册](../docs/20-server/17-研究平台环境构建手册.md)（从零重建环境）。
