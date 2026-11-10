# 07 · 服务器 DSH 部署 + Linux 环境优化 + 手机 ADB 分析

> ⚠️ **后续状态**：本机已于 2026-11-10 因 bootloop 事故恢复出厂并**从备份重建服务器**（含 DSH）。最新状态、访问入口与开机自启验证见 [08-事故复盘与重置重建报告](08-事故复盘与重置重建报告.md)。

> 执行日期：2026-11-10 11:39–12:14（Asia/Shanghai）
> 执行方式：SSH（`root@192.168.10.143:2222`，proot Ubuntu 24.04 arm64）+ ADB（`2b3be151`）
> 脚本：[scripts/setup-dsh-server.ps1](../scripts/setup-dsh-server.ps1)（可在服务器重复执行、幂等）

---

## 1. 结论速览

| 项目 | 结果 |
|---|---|
| **DSH 是否部署成功** | ✅ 成功：`@deepseek-ai/dsh 0.2.2-rc.1`，supervisord 托管，`127.0.0.1:3081` |
| **当前服务数** | 9 → **10 个 RUNNING**（原有 9 个 + dsh） |
| **DSH 资源占用** | RSS 约 **264 MB**（预热后），磁盘 `/opt/node24` 205MB + `/opt/dsh` 797MB |
| **Linux 环境优化** | apt 缓存 401MB→11K；npm 缓存 234MB→0；Node 18→24；DSH 内存上限 768MB；`.dsh` 权限 700 |
| **手机 ADB 第二轮清理** | 活跃包 252→**248**（移除广告服务/米联/主题管理器），禁用 10 |
| **手机运行状态** | 无 FATAL/ANR；温度 27–34 °C；电池 100% GOOD；内存可用约 4.0 GiB |

---

## 2. DSH 部署（服务器自托管）

### 2.1 背景

- 你此前的 DSH 是从 **DSH App 的运行环境**（`/opt/node` + `/opt/dsh`）拷进容器的；2026-11-09 那轮"与 App 解耦"时被删除，`/root/server/README.md` 也写明"容器内不再有 DSH"。
- 官方桌面端只发布 `win-x64` feed，无 Linux 版；但 **npm 上有 `@deepseek-ai/dsh`**（需 Node ≥ 24.9），服务器网络可直连 nodejs.org 与 npm registry → 走 npm 安装路线。

### 2.2 安装内容与路径

| 组件 | 版本/路径 | 说明 |
|---|---|---|
| Node.js | **v24.22.2**（linux-arm64）→ `/opt/node24` | 仅 DSH 使用，替换容器原有 Node 18（不覆盖系统 node） |
| DSH | **@deepseek-ai/dsh 0.2.2-rc.1** → `/opt/dsh`（654 packages） | npm 全局前缀安装 |
| 原生依赖补丁 | `node-addon-require-builtin-linux-arm64-gnu@0.1.9` | npm 未自动装上的 arm64 预编译模块，手动补装 |
| supervisord 程序 | `[program:dsh]`（`/root/server/etc/supervisord.conf` 第 33 行起） | `127.0.0.1:3081`，`DSH_PROFILE=server`，独立 profile |
| 启动器 | `/usr/local/bin/dsh`（包装器，显式调用 Node 24） | 交互命令可用 |
| 运维命令 | `/root/server/bin/server-dsh`（软链 `/usr/local/bin/server-dsh`） | `status｜url｜restart｜start｜stop｜logs` |
| 日志 | `/root/server/logs/dsh.log` | supervisord 轮转（3MB×2） |
| Profile | `/root/.dsh/profiles/server`、全局存储 `/root/.dsh`（权限 700） | 与 App 的 profile 隔离 |

supervisord 关键环境：

```ini
[program:dsh]
command=/opt/node24/bin/node /opt/dsh/lib/node_modules/@deepseek-ai/dsh/lib/bin.js web --host 127.0.0.1 --port 3081 --no-open
environment=HOME="/root",PATH="/opt/node24/bin:...",DSH_PROFILE="server",DSH_PROFILE_DIR="/root/.dsh/profiles/server",NODE_OPTIONS="--max-old-space-size=768"
autostart=true
autorestart=true
```

### 2.3 验证结果

| 检查 | 结果 |
|---|---|
| `supervisorctl status dsh` | **RUNNING**（稳定 2 分 22 秒+，pid 26645） |
| `dsh --version` | `0.2.2-rc.1` |
| 端口 | `127.0.0.1:3081` 监听（外部不可直连） |
| 无 token 访问 `/` | `HTTP 401`（预期，鉴权生效） |
| 带 token + cookie 访问 | **`HTTP 200`** |
| `server-doctor` | 33 项通过 / 0 失败（原有服务不受影响） |

### 2.4 如何访问（复用原 8443 /app/ 公网入口）

```powershell
# 取最新带 token 的入口地址（重启后 token 会变）
ssh -i backup\ssh\id_haydn -p 2222 root@192.168.10.143 "server-dsh url"
# 输出形如：https://47.97.70.99:44904/app/?token=<token>
```

- **浏览器直接打开** `server-dsh url` 给出的地址即可（会先弹 Basic Auth：用户名 `dsh`，密码见服务器 `/root/server/etc/dsh-web-creds.txt`）。
- 局域网也可用：`https://192.168.10.143:8443/app/?token=<同一 token>`。
- 原入口、公网 frp（`47.97.70.99:44904`）、一键下线开关均已复用，详见 §2.7。
- **首次打开需要在 DSH 网页里配置模型/凭据**（profile=server 与 App 完全隔离）；Token 是敏感凭据，不要公开。

### 2.5 安全边界

- DSH 只监听 **127.0.0.1**，未新增 nginx 公网/内网路由；远程必须走 SSH 隧道。
- `/root/.dsh` 权限已收紧为 `700`（含 `.credentials.yaml`）。
- 与项目既有原则一致（不暴露公网端口，见 [docs/00 ADR-004](00-项目规划.md)）。

### 2.6 安装过程中踩到的坑（已修复）

| 问题 | 原因 | 修复 |
|---|---|---|
| `/usr/local/bin/dsh` 误写成软链后 `cat >` 穿透覆盖了 DSH 的 `bin.js` | 原路径是 npm 创建的符号链接，重定向会写到真实文件 | 删除软链 → 重装 `@deepseek-ai/dsh` → 改用真实包装器（显式 Node 24） |
| 启动报 `Cannot find module ... require_builtin.node` | npm 未自动安装 linux-arm64 平台预编译包 | `npm install node-addon-require-builtin-linux-arm64-gnu@0.1.9` |
| supervisord 进入 FATAL（retries 用尽） | 上述崩溃反复重启 | 修复依赖后 `supervisorctl start dsh` 恢复 |
| `dsh --version` 在交互 Shell 报 `parseEnv` 相关错误 | `#!/usr/bin/env node` 命中容器旧 Node 18 | `/usr/local/bin/dsh` 包装器固定 `/opt/node24/bin/node` |
| npm 11 的 `install-scripts` 审批提示（esbuild 等 postinstall 被跳过） | npm 新安全策略 | 目前服务正常；若后续某个工具（esbuild）不可用，执行：`/opt/node24/bin/npm install-scripts approve esbuild`（在 DSH 包目录内） |

---

### 2.7 复用原 8443 `/app/` 公网入口（2026-11-10 12:21–12:27）

**目标**：沿用原访问方式 `https://<手机IP>:8443/app/`（公网经 frp：`https://47.97.70.99:44904/app/`），把反代后端从已卸载的 App 引擎（3080）切到自托管 DSH（3081），保留原 Basic Auth 与一键下线开关。

| 位置 | 改动 |
|---|---|
| nginx `dsh-upstreams.conf` | 新增 `upstream dsh_upstream { server 127.0.0.1:3081; keepalive 16; ... }` |
| nginx `sites-available/dsh-tls` `/app/` | `proxy_pass http://dsh_upstream/`（前缀剥离）；**`Host $http_host`**（必须保留端口，否则 trusted-host 不匹配 → API 403）；`X-Forwarded-Proto https` / `X-Forwarded-Host`；WebSocket upgrade；`proxy_cookie_flags ~ secure` |
| nginx `/app-login` | 移除旧 App 引擎的签名 Cookie 注入；Basic Auth 后 302 到 `/app/` |
| DSH 启动参数 | `--public-url https://47.97.70.99:44904/app/ --trusted-host 47.97.70.99:44904 --trusted-host 192.168.10.143:8443`（并补无端口形式） |
| 保留 | Basic Auth（`dsh-web.htpasswd`）、`/sdcard/DSH/dsh-app-public.off` 一键下线、原 TLS 证书 |

**验证（公网入口实测）**：

| 检查 | 结果 |
|---|---|
| `server-dsh url` | 返回 `https://47.97.70.99:44904/app/?token=…` |
| 带 Basic Auth + token 打开 `/app/` | **HTTP 200**（公网与局域网均 200） |
| 无 Basic Auth | 401 |
| `/app-login` | 302 → `/app/` |
| 页面资源 `/app/assets/*.js` | **HTTP 200**（948KB 主 JS 正常） |
| 会话 Cookie | 303 响应下发 `dsh-auth-…`，authority=`47.97.70.99:44904`，HttpOnly + SameSite=Strict + **Secure** |
| `/app/api/` 无 cookie | 401（浏览器信任栅栏通过、待鉴权） |
| `/app/api/` 带 cookie | 404（鉴权通过，路径不存在属正常） |

**关键坑**：nginx 的 `$host` 会丢掉端口 → DSH 看到的 authority 是 `47.97.70.99`，与 `--trusted-host` 的 `47.97.70.99:44904` 不匹配，`/api` 全部 403。改用 **`$http_host`** 后才恢复正常。

**备份与回滚**：

```bash
ls /etc/nginx/sites-available/dsh-tls.bak-dsh-* /root/server/etc/supervisord.conf.bak-dsh-* /etc/nginx/conf.d/dsh-upstreams.conf.bak-dsh-*
# 回滚：用对应 .bak 覆盖后
nginx -t && nginx -s reload
supervisorctl -c /root/server/etc/supervisord.conf restart dsh
```
## 3. Linux 环境优化（proot Ubuntu 24.04）

| 优化项 | 优化前 | 优化后 | 说明 |
|---|---|---|---|
| apt 缓存 | 401 MB | **11 KB** | `apt-get clean` + 清理 `/var/cache/apt/archives/*.deb` |
| npm 缓存 | 234 MB | **0** | 安装完成后 `rm -rf /root/.npm` |
| Node 运行时 | v18.19.1 | **v24.22.2**（加装于 `/opt/node24`） | 系统 node18 保留，避免破坏现有脚本；DSH 专用 |
| DSH 内存上限 | 无 | **`--max-old-space-size=768`** | 防 Node 堆无限增长拖垮手机内存 |
| nginx gzip | 已开启 | 不变 | 检查 `/etc/nginx/nginx.conf` 已有 `gzip on`（跳过重复配置） |
| `.dsh` 权限 | 755/644 | **700 / 600** | 凭据文件收紧 |
| 服务数量 | 9 | **10** | 新增 dsh，全部 RUNNING |
| 磁盘 | 25 G / 226 G | **25 G / 226 G（剩 201 G）** | Node+DSH 约 1.0 G，apt/npm 清理抵消 |
| 内存 | — | MemAvailable **≈ 4.0 GiB**（proot 视角） | swap 699 MB 使用（Android zram） |

> 说明：容器内 root 是 proot "假 root"，无法调整内核参数（sysctl/zram/IO 调度），这些仍需 Android 侧或 Root；因此 Linux 侧优化以"清理 + 版本 + 限额 + 权限"为主。

---

## 4. 手机 ADB 分析（T5，2026-11-10 12:14）

### 4.1 第二轮定向清理（依据内存画像）

| 包名 | 原因 | 结果 |
|---|---|---|
| `com.miui.systemAdSolution` | 系统广告服务，常驻前台+推送服务（约 180 MB） | 已移除 |
| `com.milink.service` | 米联（跨设备互联）runtime（约 94 MB） | 已移除 |
| `com.android.thememanager` | 主题管理器（UI 应用，约 111 MB） | 已移除 |

### 4.2 当前指标

| 指标 | 数值 |
|---|---|
| 活跃包（--user 0） | **248**（初 390；累计 -142） |
| 已禁用包 | 10（受系统保护的 `Failure[-1000]` 项） |
| MemAvailable | **≈ 4.09 GiB**（MemTotal 7.13 GiB） |
| load average（1/5/15） | 2.94 / 2.71 / 2.80（含服务栈 + DSH） |
| CPU 大核 / 电池温度 | 33.8 °C / **27 °C** |
| 电池 | 100% · FULL · GOOD · AC 供电 |
| 监听端口 | 2222、3000、**3081（DSH）**、8000、8080、8083、8085、8088、8443、9001、41255 |
| 日志异常 | 最近 400 行**无 FATAL / ANR** |

### 4.3 内存大户（Android 侧 RSS Top）

| 进程 | RSS | 说明 |
|---|---|---|
| gitea web（proot 内） | 156 MB | 服务器栈，正常 |
| `com.google.android.webview:sandboxed_process0` | 141 MB | 由残留应用触发，**不建议删 WebView**（会破坏系统组件） |
| `com.android.settings:remote` | 109 MB | 由频繁 adb `settings` 调用触发，临时进程，会回收 |
| `com.google.android.documentsui` | 100 MB | 文件选择器，保留（应用/浏览器上传文件可能用到） |
| `com.miui.securitycore.remote` | 81 MB | 安全组件，**勿删** |
| `com.google.android.webview:webview_service` | 80 MB | WebView 服务 |
| `com.miui.core` | 76 MB | MIUI 核心，**勿删** |
| DSH（`node ... bin.js web`，proot 内） | 264–398 MB | 新增；已限制 Node 堆 768MB |

### 4.4 结论与建议

1. **手机侧已接近"纯服务器"状态**：活跃包 390→248，主要只剩系统核心 + Termux/Clash/ToDesk/MT/DSH App 依赖项；继续强删 WebView/documentsui 的收益与风险不成正比。
2. **负载健康**：load ≈2.7–2.9 主要来自服务器栈（gitea/syncthing/nginx/runner）+ DSH；CPU 33 °C、电池 27 °C，散热余量充足。
3. **建议**：① 手机 GUI 开「智能充电保护」；② 轮换之前会话暴露过的 SSH 私钥；③ 给 `phone-health.ps1` 配每日计划任务（需你确认后创建）；④ 重启后记得解锁一次屏幕以触发 Termux:Boot。

---

## 5. 运维手册（DSH 相关）

```bash
# 状态 / 取地址 / 重启 / 看日志
server-dsh status
server-dsh url
server-dsh restart
server-dsh logs

# 一次性查看进程与资源
ps -eo pid,rss,args | grep 'bin.js web'
free -m | head -3
```

**卸载/回滚 DSH**：

```bash
server-dsh stop
# 从 supervisord.conf 中删除 [program:dsh] 段（grep -n 'program:dsh' 定位）
supervisorctl -c /root/server/etc/supervisord.conf reread
supervisorctl -c /root/server/etc/supervisord.conf update
rm -rf /opt/dsh /opt/node24 /root/.dsh
rm -f /usr/local/bin/dsh /usr/local/bin/server-dsh /root/server/bin/server-dsh
```

**升级 DSH**：

```bash
rm -rf /opt/dsh/lib/node_modules/@deepseek-ai/dsh
/opt/node24/bin/npm install -g --prefix /opt/dsh @deepseek-ai/dsh@<版本> --no-audit --no-fund
server-dsh restart
server-dsh url
```

---

## 6. 复现方式

```powershell
# 一键部署（幂等，可重复执行）
powershell -ExecutionPolicy Bypass -File scripts\setup-dsh-server.ps1

# 或带自定义版本
powershell -ExecutionPolicy Bypass -File scripts\setup-dsh-server.ps1 -NodeVersion v24.22.2 -DshVersion 0.2.2-rc.1
```

---

## 7. 变更记录

| 时间 | 变更 | 结果 |
|---|---|---|
| 11:39–11:49 | 安装 Node 24.22.2 + `@deepseek-ai/dsh` 0.2.2-rc.1 | 成功（npm 654 packages，约 9 分钟） |
| 11:50 | 写入 supervisord `[program:dsh]`、`server-dsh` 工具、启动 | 首次 RUNNING，token 生成 |
| 11:51–12:12 | 修复 bin.js 被软链穿透覆盖 / arm64 原生模块缺失 / 服务 FATAL | 全部修复，稳定 RUNNING |
| 12:09–12:12 | Linux 清理：apt/npm 缓存、`.dsh` 权限、DSH 内存上限 | 释放约 640MB 缓存 |
| 11:49–12:14 | 手机 ADB 第二轮清理 + T5 分析 | 活跃包 252→248，无 FATAL/ANR |
| 12:21–12:27 | 适配原 8443 `/app/` 公网入口：nginx 前缀剥离反代切到 3081、DSH 加 `--public-url/--trusted-host`、修复 `$http_host` 端口丢失导致的 403 | 公网/局域网 `/app/`、资源、API 鉴权全部验证通过 |
