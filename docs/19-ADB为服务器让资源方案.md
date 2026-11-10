# 19 · ADB 为服务器让资源：方案矩阵

> 目标：在一台 Android 手机上长期跑 Termux + proot Ubuntu 服务器时，**用 ADB（无 Root）把 CPU/内存/网络/IO 资源尽量让给服务器**，同时不破坏 MIUI 日常功能和可恢复性。
> 定位：方案设计；所有写操作均标注"需实测/可回滚"；不执行不可逆操作。

---

## 1. 现状与判断依据（2026-11-10 实测）

### 1.1 服务器进程保护状态（好的方面）

| 检查 | 结果 |
|---|---|
| Termux 进程状态 | `prcp F/S/FGS`（前台 Service + 进程缓存，优先级已较高） |
| 电池白名单 | `com.termux`、`com.termux.boot` 均在 deviceidle whitelist |
| AppOps | `RUN_ANY_IN_BACKGROUND allow` |
| standby bucket | `com.termux` = 5（EXEMPTED） |
| wake-lock | Termux 前台服务持有（`termux-wake-lock`） |
| 结论 | **不要动 Termux/proot**；它们是受保护的 |

### 1.2 可回收对象（当前内存大户与后台）

| 对象 | 实测 RSS/内存 | 说明 |
|---|---|---|
| Shizuku 管理器 App | ~148MB RSS | 研究工具，不常驻需要；`shizuku_server` 另约 140MB |
| Hail | ~177MB RSS | 研究工具，打开后常驻 |
| AppManager | 约 200MB（视使用） | 研究工具；其 ADB 服务端用后应停 |
| Canta | 几十 MB | 研究工具，按需使用 |
| DSH node | 280–420MB | 服务器服务；可通过关闭 DevTools/限堆优化（docs/18） |
| MIUI 系统组件 | systemui 306MB、securitycenter 235MB、输入法 234MB 等 | 不可卸载/不可随意冻结 |
| 缓存应用 | Shizuku/Hail/Canta/安全中心等 | LMK 会回收，但内存紧张时也会挤压服务器 |

### 1.3 ADB 能力边界（实测）

| 能力 | 可用性 | 用途 |
|---|---|---|
| `cmd activity freeze/unfreeze <process>` | ✅ 存在（ADB shell） | 冻结**非关键进程**（研究 App/后台），解冻恢复；状态不持久 |
| `cmd activity compact some/full <process>` | ✅ 存在 | 单次内存压缩（谨慎，可能造成卡顿） |
| `cmd package suspend/unsuspend` | ✅ 可用且重启保持 | 冻结 App（交互/后台启动受限） |
| `cmd package trim-caches <free_space>` | ✅ 存在 | 清理缓存回收存储 |
| `pm clear --cache-only <pkg>` | ✅ 存在 | 清指定 App 缓存 |
| `cmd netpolicy restrict-background-*` | ✅ 存在 | 限制后台网络；**必须把 Termux UID 10250 加入白名单** |
| `pm disable-user`（系统包） | ❌ `Cannot disable system packages` | 不可用 |
| `am set-inactive / set-standby-bucket` | ❌ 静默忽略（MIUI 豁免） | 不可用 |
| `settings put global cached_apps_freezer` | ✅ 可写，但**重启被 MIUI 重置** | 辅助 |
| `logcat -G` | ✅ 可写，重启重置 | 辅助 |
| `device_config` 写 | ⚠️ 需实测（shell 通常有写权限；仅看到 compaction 相关键，无 max_cached_processes/phantom 默认项） | 实验 |
| CPU governor / zram / cgroup / oom_adj | ❌ 需 Root | 不做 |
| `am kill-all` | ❌ 禁止（会杀 Termux/proot，曾导致服务全灭） | 红线 |

> 结论：**最有效的 ADB 手段是"研究 App 静默/冻结 + 后台治理 + 缓存清理/网络策略"**，而不是改内核/调频。

---

## 2. 方案矩阵

### A. 服务器保护（先做，防误伤）

| ID | 方案 | 做法 | 收益 | 风险 | 优先级 |
|---|---|---|---|---|---|
| A1 | 固化 Termux 保护 | 复核：deviceidle whitelist、`RUN_ANY_IN_BACKGROUND allow`、bucket 5、wake-lock；`scripts/perf-adb-apply.ps1` 已含部分 | 防止 LMK 杀服务器 | 低 | P0 |
| A2 | 预先把 Termux UID 加入网络限制白名单 | `cmd netpolicy add restrict-background-whitelist 10250`（当前 global restrict=disabled，但为将来开启做准备） | 防止网络策略误伤服务器 | 低 | P0 |
| A3 | 保持省电策略关闭 | `settings get global low_power`（当前 0）；`cmd power set-adaptive-power-saver-enabled false`（若开启） | 防止 CPU 限频 | 低 | P1 |
| A4 | 保持 WiFi 不休眠 | `settings get global wifi_sleep_policy`（当前 2=never） | 降低网络延迟/断连 | 低 | P0 |
| A5 | 禁 `am kill-all` | 任何脚本不得执行 | 避免服务器进程全灭 | 红线 | 永久 |

### B. 内存回收（收益最大）

| ID | 方案 | 做法 | 预期收益 | 风险 | 优先级 |
|---|---|---|---|---|---|
| B1 | **研究 App 静默模式** | 不用研究工具时：`am force-stop moe.shizuku.privileged.api`（可保留 `shizuku_server`）、`am force-stop com.aistra.hail`、`io.github.samolego.canta`、`io.github.muntashirakon.AppManager`；AppManager 服务端用 `appmanager-adb-mode.ps1 -Stop` | **~300–500MB RSS** 可释放给服务器 | 研究工具需重新打开；Shizuku 管理器打开才授权 App | P0 |
| B2 | 扩大 suspend/appops 治理 | 基于 UAD 清单 + 实际运行，新增"确定不用"的系统 App：`cmd package suspend --user 0 pkg` + `cmd appops set pkg RUN_ANY_IN_BACKGROUND ignore` + `force-stop` | 减少后台重启/内存 | 中（MIUI 仍可能拉起；避免通话/短信/系统 UI） | P1 |
| B3 | 进程级冻结 | `cmd activity freeze <process>`（可 `--sticky`）；对研究 App/后台进程；恢复 `unfreeze` | 立即降低调度/内存 | 冻结系统进程可能破坏依赖；重启失效 | P1（试点） |
| B4 | 缓存应用冻结 | `settings put global cached_apps_freezer enabled`；`device_config` `use_freezer` 实验（如可写） | 减少缓存进程内存 | 重启后 MIUI 可能重置；需实测 | P1 |
| B5 | 限制缓存进程数 | `device_config put activity_manager max_cached_processes 16/24`、`max_phantom_processes 8/16`（**需先确认可写/存在**） | 释放 100–300MB | 后台 App 更易被回收；可能影响通知/体验；可 `device_config delete` 回滚 | P2（实验） |
| B6 | 清理缓存/压缩内存 | `cmd package trim-caches 1000`、`pm clear --cache-only` 指定 App；`cmd activity compact` 对**非关键大进程**（谨慎） | 回收存储/临时内存 | compact 可能造成卡顿；只对非关键 App | P2 |
| B7 | 日志缓冲 | `logcat -G 1M; logcat -c`（重启重置，需重放） | 省几 MB | 低 | P0（辅助） |

> **不建议**：为了给服务器让内存去杀/冻结 MIUI 核心组件（systemui/securitycenter/输入法/家庭启动器）；可能引发 UI/输入/安全功能异常。

### C. CPU 让渡

| ID | 方案 | 做法 | 收益 | 风险 | 优先级 |
|---|---|---|---|---|---|
| C1 | 研究 App 静默 | 同 B1（force-stop / freeze） | 降低后台 CPU/唤醒 | 低 | P0 |
| C2 | 关闭 DevTools/调试会话 | 关闭 DSH 浏览器 DevTools（CPU 9.5%→4.8% 实测） | 明显 | 无 | P0 |
| C3 | 限制后台网络/同步 | `cmd netpolicy add restrict-background-blacklist <uid>`（对确认无用的 UID）；Termux 10250 加白名单 | 减少唤醒/CPU | 误伤通知/同步；需逐 UID | P1 |
| C4 | Termux dex 优化 | `cmd package compile -m speed -f com.termux`（已做过） | 启动/执行略快 | 低 | 已完成 |
| C5 | 固定性能模式 | `cmd power set-fixed-performance-mode-enabled true` | 短时基准提升 | **发热/降频/耗电，不建议常开** | 仅基准测试 |

### D. 网络让渡/稳定

| ID | 方案 | 做法 | 收益 | 风险 | 优先级 |
|---|---|---|---|---|---|
| D1 | 关后台扫描/蓝牙/定位 | 已做（scan/ble/location/bluetooth/data） | 降唤醒 | 低 | 已完成 |
| D2 | 关 captive portal 探测 | `settings put global captive_portal_mode 0` | 减少周期性网络唤醒 | 低（公共 WiFi 登录提示失效） | P1 |
| D3 | WiFi 不休眠 | `wifi_sleep_policy=2`（已 2） | 延迟稳定 | 低 | 已完成 |
| D4 | 限制后台网络 | netpolicy 黑名单（见 C3） | 降后台流量/唤醒 | 中 | P1 |
| D5 | 关闭 WiFi 随机 MAC/静态租约 | 路由器侧设置（非 ADB） | IP 稳定 | 低 | 推荐 |

### E. 存储/IO 让渡

| ID | 方案 | 做法 | 收益 | 风险 | 优先级 |
|---|---|---|---|---|---|
| E1 | fstrim | `sm fstrim`（每月/每两周） | UFS 性能/寿命 | 极低 | P1 |
| E2 | 清缓存 | `cmd package trim-caches 1000`、指定 App `--cache-only` | 回收空间 | 低（会清缓存） | P1 |
| E3 | 服务器日志迁移 | 日志/TMP 放 `/hosthome`（docs/18 O4） | 减少 rootfs IO | 需改配置 | P2 |
| E4 | apt 清理 | `apt-get clean`（服务器内，已完成一次） | 释放空间 | 低 | P2 |

### F. 研究工具的资源纪律

| 工具 | 默认状态 | 使用建议 |
|---|---|---|
| Shizuku | `shizuku_server` 常驻 ~140MB | 不用 App 权限时保留 server；管理器 App 可 force-stop（打开时重启） |
| Canta/Hail | 打开后常驻，Hail ~177MB | 用完即 force-stop；Hail 冻结规则可在需要时再用 |
| AppManager | ADB 服务端 60001；主进程 ~200MB | 用 `appmanager-adb-mode.ps1 -Start` 临时开、`-Stop` 关；不要常驻 |
| UAD 清单 | 静态 JSON | 只读，不常驻进程 |

---

## 3. 推荐实施顺序

### P0（先做，低风险、收益明确）
1. **B1 研究 App 静默**：每次研究结束后 force-stop Shizuku 管理 App / Hail / Canta / AppManager（保留 `shizuku_server`，需要时再启动）。
2. **A1/A2/A4**：复核 Termux 保护；把 UID 10250 加入 netpolicy 白名单；确认 WiFi 不休眠。
3. **C2**：关闭 DSH DevTools 调试会话。
4. **B7**：logcat 1M + cached_apps_freezer enabled（重启后重放）。
5. 测一次 MemAvailable / proot CPU 对比。

### P1（需小范围验证）
1. **B2**：选 5–10 个"确认不用"的系统 App 扩充 suspend/appops（先列清单）。
2. **B3**：对研究 App 试 `cmd activity freeze`（验证解冻/重启行为）。
3. **B4/B5**：`use_freezer`/max_cached 实验（先确认 device_config 可写）。
4. **D2/C3**：captive portal 关闭 + netpolicy 逐 UID 黑名单（Termux 白名单）。

### P2（可选/实验）
- `cmd activity compact` 非关键大进程；rootfs 日志迁移；服务器侧 DSH 限堆/看门狗迁移（docs/18）。

---

## 4. 测量与验收

### 基线指标
- MemAvailable、MemFree；`dumpsys meminfo` 前列进程；`dumpsys activity lru` 中缓存数量。
- proot CPU（`dumpsys cpuinfo` 的 proot%）、node RSS、TTFB（LAN/公网）。
- Termux 的 `oom_score_adj` / 进程状态（必须保持 `prcp F/S/FGS`）。

### 验收阈值（建议）
- MemAvailable **≥4.6GB**（当前 ~4.49GB）；
- proot CPU 不升、最好 ≤18%；DSH RSS ≤350MB（配套 docs/18）；
- Termux/proot 在 24h 内无被杀/无重启；
- 公网/LAN health 200、TTFB 不退化；
- 研究工具需要时能正常重新启动/解冻。

### A/B 纪律
一次只改 1 项；改完等 2–5 分钟采样；异常立即回滚（`unfreeze`/`force-stop` 反转/设置复原）；记录到 `inventory/`。

---

## 5. 风险与红线

| 风险 | 说明 | 处置 |
|---|---|---|
| `am kill-all` | 会杀 Termux/proot（已发生过） | 禁止 |
| 冻结系统进程 | 可能导致 SystemUI/输入法/安全中心异常 | 只冻结非关键研究 App；不要动 systemui/securitycenter/输入法/phone |
| netpolicy 全局限制 | 可能断服务器网络 | 只做 UID 黑名单，务必先白名单 Termux 10250 |
| device_config 写缓存进程上限 | 后台 App 更易被杀 | 小步实验（32→24），记录回滚键值 |
| 研究 App 静默 | 下次用 Shizuku/AppManager 需重新启动/授权 | 属预期；不影响服务器 |
| 重启后 MIUI 重置 | freezer/logcat/appops 部分失效 | 用 `after-reboot-android.ps1 -Apply` 重放 |

---

## 6. 不可做（需 Root，明确排除）

- CPU governor/频率上限、I/O 调度、zram/swap、cgroup 内存限制、内核参数（swappiness）；
- 设置进程 `oom_score_adj`（`cmd activity` 无该命令；Termux 靠前台服务/白名单保护）；
- 温度墙/thermal override；
- 系统包 uninstall/disable（MIUI canBeDisabled + 事故教训）。

---

## 7. 建议的交付物（待批准后实现）

1. `scripts/adb-server-resource.ps1`：`-Status / -Quiet / -Restore`
   - Status：MemAvailable、后台大户、研究 App 进程、Termux 保护状态、netpolicy；
   - Quiet：B1 研究 App 静默 + B7 缓存/日志 + A2 白名单 + D2（可选），全部可逆；
   - Restore：恢复研究工具可打开（不动服务器）。
2. `after-reboot-android.ps1` 增加 `-ServerResourceQuiet` 可选步骤（重启后自动进入静默，减少对服务器挤占）。
3. 控制台增加"研究 App 占用/静默状态"卡片（可选，靠 ADB/console API）。

> 本文只做方案；未执行任何 freeze/force-stop/设置变更。建议先批准 P0（B1/A1-A4/C2），我按"一项一测"执行并给前后对比。
