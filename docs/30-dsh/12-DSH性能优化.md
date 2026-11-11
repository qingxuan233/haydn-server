# 12 · DSH 服务器运行环境分析与性能优化

| 项目 | 内容 |
|---|---|
| 文档 ID | `HB-DSH-012` |
| 版本 | v2.0（2026-11-11） |
| 状态 | 历史记录（2026-11-10 性能优化实施记录）；当前状态见 [当前状态](../00-overview/当前状态.md) |
| 关联 | [07 DSH 部署](07-DSH与Linux优化.md) · [10 登录入口](10-DSH登录入口优化.md) · [11 服务器配置与模型](11-DSH服务器配置与模型.md) · [13 插件安装 pnpm](13-DSH插件安装-pnpm.md) · [21 P0 落地手册](21-DSH控制平面落地手册.md) |

> **历史记录（2026-11-10）**：本文的 gzip/长缓存/broker 超时等改动仍在线上生效，但 RSS/体积/服务数等数字均为**当时快照**；当前总服务数 **12/12**（含 `dsh-guard`），最新状态见 [当前状态](../00-overview/当前状态.md)。

> 日期：2026-11-10 16:45–17:15
> 反馈："有点卡"
> 结论：**不是手机 CPU/内存瓶颈**（Android 负载 ~1.8/8 核、CPU 大量 idle、DSH 进程 CPU ~4%），主要卡在：
> ① nginx 虽然 `gzip on`，但 **`gzip_types` 全被注释** → JS/CSS 不压缩；
> ② 所有 `/app/` 响应带 `Cache-Control: no-store` → 每次打开都重下约 1.8MB 资源；
> ③ profile 里挂着 inspector / forge / auto-review / 插件市场等重插件（客户端模块 240 个）；
> ④ 登录 broker 的 token 交换超时 6s 会偶发 503。
> 已全部处理，首屏体积与重复访问成本大幅下降。

---

## 1. 基线与瓶颈定位

### 1.1 运行环境

| 项目 | 数值 |
|---|---|
| 设备 | Redmi K40 Pro（骁龙 888，8 核，7.1GB + 6GB zram） |
| Android 负载 | `1.79 / 2.38 / 1.79`，top: 31% sys、759% idle（800% 总） |
| DSH 进程（优化前） | **RSS 463MB，12 线程**；5s 内 utime+40 / stime+21（≈12% 单核） |
| DSH 版本 | `@deepseek-ai/dsh 0.2.2-rc.1`，Node 24.22.2，`127.0.0.1:3081` |
| 页面 HTML | 43,355 B；HTML 内 **`client.js` 出现 240 次**（大量客户端插件模块） |
| 静态资源（未压缩） | `index.js` 970,770 B；`vendor.js` 741,528 B；两组 CSS 27,312 B + 87,126 B ≈ **1.8MB** |
| 缓存头 | 资源响应同时带 `cache-control: no-cache`（DSH）与 `Cache-Control: no-store`（nginx `/app/ add_header`） |
| gzip | `nginx.conf` 有 `gzip on`，但 `gzip_types` 被 **注释**，实际只压缩 `text/html` |
| 登录耗时 | LAN `/app-login` 约 0.20s；公网约 0.33–0.38s（HTML 首包） |

### 1.2 瓶颈判断

| 现象 | 判断 |
|---|---|
| 手机整体空闲 | 不是 CPU/内存或热降频问题 |
| 每次打开 UI 都慢 | `no-store` + 未压缩 JS/CSS，每次全量重传 |
| 首次加载尤其慢 | JS/CSS 约 1.8MB（未 gzip）+ 插件的客户端模块 240 个 |
| 偶发 503 | broker token 交换 6s 超时（DSH 启动/负载瞬间） |
| DSH 进程 RSS 463MB | 插件过多（inspector/forge/auto-review/插件市场/agent-team 等） |

## 2. 已实施的优化

### 2.1 nginx：gzip 真正生效

新增 `/etc/nginx/conf.d/zz-dsh-gzip.conf`（`nginx.conf` 已有 `gzip on`）：

```nginx
gzip_types text/plain text/css application/json application/javascript text/javascript
           application/xml application/xml+rss application/manifest+json image/svg+xml;
gzip_vary on;
gzip_proxied any;
gzip_comp_level 5;
gzip_min_length 1024;
```

> 归档：[scripts/server/nginx-zz-dsh-gzip.conf](../../scripts/server/nginx-zz-dsh-gzip.conf)

### 2.2 nginx：静态资源/插件包长缓存

在 `/app/` 内新增两个嵌套 location（HTML 入口仍保留 `no-store`，避免缓存旧页面导致空白）：

```nginx
location ^~ /app/assets/  { ... proxy_pass http://dsh_upstream/assets/;  add_header Cache-Control "public, max-age=31536000, immutable"; }
location ^~ /app/plugins/ { ... proxy_pass http://dsh_upstream/plugins/; add_header Cache-Control "public, max-age=31536000, immutable"; }
```

- 这两个路径的资源带 hash / `rev=` 版本号，可安全长缓存；
- `proxy_hide_header Cache-Control` 隐藏 DSH 的 `no-cache`，由 nginx 下发 `public, immutable`；
- 公共代理指令收敛到 `/etc/nginx/snippets/dsh-proxy-common.conf`（[归档](../../scripts/server/nginx-dsh-proxy-common.conf)）。

### 2.3 DSH profile 精简 + 禁用 HMR

`/root/.dsh/profiles/web/package.json` 的 bundles 从 8 个减为 4 个：

| 保留 | 移除 |
|---|---|
| `dsh-base` | `dsh-experimental-plugin-market-bundle` |
| `dsh-web-app` | `dsh-experimental-inspector-profile` |
| `dsh-experimental-agent-team-profile`（Team 功能） | `dsh-experimental-auto-review` |
| `dsh-experimental-session-titles-bundle` | `dsh-experimental-forge-bundle` |

补丁层同时：

- 删除 `plugin-market` 配置项（与移除 bundle 对应）；
- 禁用 `hmr` / `client-hmr`（生产 Web 不需要热更新 watcher）；
- 修正默认模型为 desktop 配置：`open-design / deepseek-v4.1-flash-eco / reasoningEffort: max`。

归档：[dsh-web-profile-package.json](../../scripts/server/dsh-web-profile-package.json)、[dsh-web-cordis.patch.yml](../../scripts/server/dsh-web-cordis.patch.yml)

### 2.4 broker 稳定性

`dsh-login` 的 token 交换超时 6s → **10s**，并**重试一次**；仍失败才返回 503（不产生重定向循环）。归档：[dsh-login.py](../../scripts/server/dsh-login.py)。

## 3. 优化前后对比

| 指标 | 优化前 | 优化后 |
|---|---|---|
| DSH RSS | 463MB | **304MB（-34%）** |
| DSH 线程 | 12 | 11 |
| 页面 HTML | 43,355 B | **40,252 B（-7%）** |
| 客户端 `client.js` 模块数 | 240 | **222（-18）** |
| `index.js` 下载体积 | 970,770 B（未压缩） | **332,576 B（gzip，-66%）** |
| `vendor.js` 下载体积 | 741,528 B（未压缩） | **210,244 B（gzip，-72%）** |
| 静态资源缓存 | `no-store`，每次重下 | **`public, max-age=31536000, immutable`**（重复访问不再下载） |
| 插件包 | 未缓存 | 同上，长缓存 + gzip |
| 登录耗时（LAN） | ~0.20s，偶发 503 | **0.18–0.24s，5/5 成功** |
| 登录耗时（公网） | ~0.33–0.38s | **0.33–0.35s，2/2 成功** |
| `--dump-config` | exit 0 | **exit 0，1470 行，默认模型 eco/max** |
| 浏览器 | - | Edge fresh profile 正常进入（DOM 716,152 B） |
| 服务（历史快照 2026-11-10） | 11/11 RUNNING | **11/11 RUNNING**（当前 12/12，见 [当前状态](../00-overview/当前状态.md)） |

> 首次打开仍需下一次全量资源（已压缩），之后浏览器命中长缓存，刷新/重进明显更快。若浏览器此前缓存了旧 `no-store` 页面，**首次建议 Ctrl+F5 强刷一次**。

## 4. 回滚

服务器上已自动备份：

```bash
# nginx
cp -a /etc/nginx/sites-available/dsh-tls.bak-perf-20261110-165717 /etc/nginx/sites-available/dsh-tls
rm -f /etc/nginx/conf.d/zz-dsh-gzip.conf
nginx -t && nginx -s reload

# profile
cp -a /root/.dsh/profiles/web/package.json.bak-perf-20261110-165806 /root/.dsh/profiles/web/package.json
cp -a /root/.dsh/profiles/web/cordis.patch.yml.bak-perf-20261110-165806 /root/.dsh/profiles/web/cordis.patch.yml
supervisorctl -c /root/server/etc/supervisord.conf restart dsh
```

## 5. 进一步可选项（按需）

- **HTTP/2**：8443 当时是 HTTP/1.1（2026-11-10）；可加 `listen 8443 ssl http2;` 让浏览器并行加载更顺（frp 为 TCP 透传，ALPN 可透传）；有兼容性风险，未默认启用。
- **降低 UI 渲染细节**：`ui-chat.transcriptView: detailed` / `performanceUsage: detailed` 是效果优先设置；若长会话滚动仍卡，可改 compact 类设置。
- **移除 Team/会话标题 bundle**：可再减模块，但会失去 Team/自动标题功能，不建议默认做。
- **切换 LAN 访问**：公网经 frp 首包会多 ~100–200ms；在家优先用 `https://192.168.10.143:8443/app-login`。

## 6. 变更记录

| 时间 | 变更 | 结果 |
|---|---|---|
| 16:57 | nginx 增加 gzip_types + assets/plugins 长缓存 | JS 压缩 66–72%，缓存头 immutable |
| 17:00 | 精简 profile bundles，禁用 HMR，移除 plugin-market | 模块 240→222，RSS 463→304MB |
| 17:05 | 修正默认模型 eco/max | dump exit 0 |
| 17:09 | broker 超时 6→10s + 重试 | LAN 登录 5/5、公网 2/2 成功 |
| 17:12 | Edge/服务回归 | 11/11 RUNNING（当时），DOM 716KB 正常 |

## 7. 后续：安装 codex 插件后的状态（2026-11-10 17:25）

插件管理器把 `inspector/forge` 等 bundles 重新加回后，重启 DSH 需要约 90 秒。为保持性能，已再次精简为 **base/web-app/agent-team/session-titles + subagent-codex**：

| 指标 | 数值 |
|---|---|
| bundles | 5 个（4 核心 + codex） |
| 启动（重启→新 token） | **34s** |
| RSS | **410MB**（codex 比精简态多约 100MB） |
| 客户端模块 | 222 |
| 登录 LAN/公网 | 200 / 200 |
| 服务（历史快照 2026-11-10） | 11/11 RUNNING |

> 需要 inspector/forge 面板时，可在 DSH 插件管理器中重新启用；代价是启动时间与内存回升（约 90s / 更高 RSS）。pnpm 安装细节见 [13-DSH插件安装-pnpm](13-DSH插件安装-pnpm.md)。
