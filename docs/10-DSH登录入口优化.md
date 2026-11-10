# 10 · DSH 登录入口优化：/app/ 免 token 自动登录（含浏览器 cookie 兼容）

> 日期：2026-11-10 14:57 → 15:30
> 现象：打开 `https://192.168.10.143:8443/app/`（或 `/app-login`）后，浏览器提示
> `dsh web authentication required; reopen the URL printed by dsh web.`
> 或 `192.168.10.143 将您重定向的次数过多`。
> 结论：DSH 的 `/app/` 需要带 token；且 DSH 种的 cookie 是 `SameSite=Strict; Secure`，
> 在**自签证书/部分浏览器策略**下会被拒绝——浏览器每次都无 cookie 访问，于是
> `/app/ 302 token → token 303 ./ → /app/ 无 cookie …` 形成无限跳转。
> curl 的 cookie jar 不校验这些浏览器规则，所以自动化测试"看起来是通的"，属于误判。

---

## 1. 最终方案（v2：服务端 cookie broker）

新增 `dsh-login`（仅监听 `127.0.0.1:3082`），nginx `/app-login` 在 Basic Auth 后反代到它：

1. 从 `/root/server/logs/dsh.log` 读取**最新 token**；
2. 用**浏览器当前 Host**（如 `192.168.10.143:8443`）在服务端请求 DSH 根入口 `/?token=…`，拿到 DSH 的 `Set-Cookie`；
3. 返回 `302 /app/`，同时下发浏览器兼容的 cookie：
   ```
   dsh-auth-…=…; Path=/app; Max-Age=2592000; HttpOnly; SameSite=Lax   # 不再带 Secure
   dsh-auth-…=;   Path=/; Max-Age=0; Expires=…                        # 清掉旧的 Path=/ cookie
   ```
4. nginx `/app/`：
   - 请求没有 `dsh-auth` cookie ⇒ **一次** 302 到 `/app-login`（相对 Location，无重复跳转）
   - 有 cookie ⇒ 正常反代到 DSH（携带 cookie 的请求直接 200）
   - DSH 返回 401 时兜底转 `/app-login`

这样浏览器最多 2 次跳转即可登录，**不会再出现重定向循环**。

### 使用方式

1. **先清一次该站点的旧 cookie**（或直接开"无痕/隐私窗口"）——旧版本可能留下 `Path=/` 的 DSH 严格 cookie；
2. 打开 **`https://192.168.10.143:8443/app-login`**（或先开 `/app/`，它会自动跳到 `/app-login`）；
3. Basic Auth 输入用户名 `dsh`、密码（见服务器 `/root/server/etc/dsh-web-creds.txt`）；
4. 自动进入 DSH；之后收藏 `/app-login` 或 `/app/` 均可，无需再管 token。
- 公网同理：`https://47.97.70.99:44904/app-login`。
- 备用：`server-dsh url` 仍可输出当前 token 直链（调试用）。

## 2. 实测结果（v2）

| 场景 | 结果 |
|---|---|
| LAN `/app/`（无 cookie） | **单个 302 → `/app-login`**（不再双 Location） |
| LAN `/app-login`（Basic Auth） | 302 `/app/` + 兼容 cookie + 清除旧 cookie，**HTTP 200** 落地 |
| LAN `/app/` 完整跟随（无 token） | **200，2 次跳转**（DSH 页面 43KB） |
| 公网 `/app/` 完整跟随 | **200，2 次跳转** |
| Edge（真实浏览器，fresh profile）打开 `/app-login` | **DOM 751070 字节，正常进入 DSH** |
| 无凭据访问 `/app/` | 302 → `/app-login`（普通 401 提示，不暴露 token） |
| DSH 重启换 token 后 | broker 自动读取新 token，仍可登录 |
| `fileui` / `/files/` | 不受影响 |
| 服务 | **11/11 RUNNING**（新增 dsh-login） |

## 2.2 空白页加固（2026-11-10 16:00）

现象：浏览器打开公网 `/app/` 后**页面空白**（服务器 curl 返回 200、HTML 43KB；真实 Edge 注入正确 Basic 后渲染 795K 完整界面）。

判断：不是服务端故障，而是浏览器里 **旧的 DSH cookie / 旧 HTML 缓存** 让 `/app/` 走了错误的跳转链。加固措施：

1. `dsh-login` 在成功换 cookie 时额外下发 **broker 标记 cookie**：`dshbrk=1; Path=/app; Max-Age=86400; HttpOnly; SameSite=Lax`；
2. nginx `/app/` 只认这个标记：`if ($cookie_dshbrk = "") { return 302 /app-login; }`——旧 `dsh-auth` cookie 不再能直接放行，会被强制走一次登录入口，换取**全新 cookie**并清掉旧 `Path=/` cookie；
3. `/app/` 的 HTML 增加 `Cache-Control: no-store`，避免浏览器缓存旧前端壳。

验证：

| 检查 | 结果 |
|---|---|
| `/app/` 无 cookie | 302 → `/app-login` |
| `/app/` 带旧 `dsh-auth` 但没有 `dshbrk` | **302 → `/app-login`**（强制刷新登录态） |
| `/app-login` | 302 `/app/` + 3 条 Set-Cookie（会话 + dshbrk + 清除旧 Path=/） |
| 完整跟随公网 `/app/` | **200，2 次跳转** |
| 真实 Edge（header Basic，无 URL userinfo）打开公网 `/app/` | **DOM 795593，工作区/欢迎语正常渲染** |
| 页面头 | `Cache-Control: no-store` |

> 浏览器处理：**清除 `47.97.70.99` 的站点数据（cookie/缓存）或开无痕窗口**，打开 `/app-login` 输入 Basic 账号；之后 `/app/` 会自动通过 broker 登录，不再空白。
## 3. 组成与回滚

| 文件 | 说明 |
|---|---|
| `/root/server/bin/dsh-login` | token + cookie broker（Python 标准库） |
| supervisord `[program:dsh-login]` | 守护 `dsh-login`，日志 `dsh-login.log` |
| `/etc/nginx/sites-available/dsh-tls` | `/app-login` 反代 3082；`/app/` 无 cookie 单次跳转 |
| nginx 备份 | `dsh-tls.bak-broker-20261110-152336` 等 |
| 源码归档 | [scripts/server/dsh-login.py](../scripts/server/dsh-login.py)、[scripts/server/patch-dsh-login-nginx.py](../scripts/server/patch-dsh-login-nginx.py)、[scripts/server/dsh-login-program.conf](../scripts/server/dsh-login-program.conf) |

回滚：

```bash
supervisorctl -c /root/server/etc/supervisord.conf stop dsh-login
cp -a /etc/nginx/sites-available/dsh-tls.bak-broker-20261110-152336 /etc/nginx/sites-available/dsh-tls
nginx -t && nginx -s reload
# 从 supervisord.conf 删除 [program:dsh-login] 段后 reread/update
```

## 4. 安全说明

- `dsh-login` 只监听 `127.0.0.1:3082`，外部必须经 nginx 的 **Basic Auth** 才能访问 `/app-login`；
- 未认证请求不会拿到含 token 的跳转；
- 兼容 cookie 因去掉 `Secure`、`Path=/app`：只随 `/app` 前缀发送；站点内 `/app` 之外不会携带（且 DSH 仅在 8443 的 `/app/` 暴露）；
- 旧 `Path=/` cookie 会在登录入口被主动清除，避免新旧双份 cookie 混淆；
- token 仍随 DSH 重启轮换，但用户无感；token 直链仍只应私下使用。

## 5. 变更记录

| 时间 | 变更 | 结果 |
|---|---|---|
| 14:57 | 复现 `/app/` 无 token → 401 提示 | 确认 DSH token 机制 |
| 14:59 | v1：`/app-login` 302 到 token URL | curl 测试通过，浏览器仍可能循环 |
| 15:23 | v2：服务端 broker + cookie 兼容处理 | `/app-login` 302 `/app/` + Set-Cookie |
| 15:24 | 修正 broker 请求路径（DSH 根 `/`，非 `/app/`） | 成功拿到 cookie |
| 15:25 | 去掉重复 `proxy_intercept_errors` / 双 Location | `/app/` 单次跳转 |
| 15:26 | 兼容 cookie 清旧 `Path=/` + 相对跳转 | 完整跟随 200 |
| 15:29 | Edge fresh profile 验证 | DOM 751070，正常进入 |
| 16:00 | 空白页加固：dshbrk 标记 + no-store | 旧 cookie 强制走登录，公网 Edge 渲染 795593 |
