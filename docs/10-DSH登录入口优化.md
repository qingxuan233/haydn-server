# 10 · DSH 登录入口优化：/app/ 免 token 自动登录

> 日期：2026-11-10 14:57–15:05
> 现象：打开 `https://192.168.10.143:8443/app/` 完成 Basic Auth 后，页面提示
> `dsh web authentication required; reopen the URL printed by dsh web.`
> 结论：不是故障，而是 **DSH 要求 URL 携带一次性 token**；原入口 `/app-login` 只 302 到 `/app/`（无 token），所以必然落到该提示页。

---

## 1. 根因

- DSH `web` 每次启动会打印形如
  `https://…/app/?token=XXXX` 的入口；**token 每次重启都会变**。
- `/app/` 本身不是登录页：
  - 无 token → HTTP **401** + "dsh web authentication required"
  - 带 token → HTTP 200 并种下会话 cookie
- 原 nginx 的 `/app-login` 只是 `return 302 /app/`，没有 token，因此"登录后仍提示需要 token"。
- 直接抄旧 token 也不行：DSH 重启后旧 token 失效。

## 2. 解决方案

新增一个**仅监听 127.0.0.1:3082** 的小服务 `dsh-login`：

1. 每次请求读取 `/root/server/logs/dsh.log` 里**最新**的 `token=…`；
2. 返回 `302 Location: /app/?token=…`（相对路径，保持当前 Host/端口）；
3. nginx 侧：
   - `location = /app-login`：Basic Auth 后反代到 `127.0.0.1:3082`；
   - `location /app/`：`proxy_intercept_errors on; error_page 401 =302 /app-login;`
     → 用户直接打开 `/app/`（无 token）时，DSH 的 401 被 nginx 截获，自动跳到 `/app-login`，再拿当前 token 回到 `/app/`，**全程自动**。

### 使用方式

- 直接访问 / 收藏：`https://192.168.10.143:8443/app/` 或 `https://47.97.70.99:44904/app/`
- 输入 Basic Auth（用户名 `dsh`，密码见 `/root/server/etc/dsh-web-creds.txt`）即可自动登录；
- 不再需要复制 `dsh web` 打印的 token。
- 备用：`server-dsh url` 仍可输出当前 token 直链（调试用）。

## 3. 实测结果

| 场景 | 结果 |
|---|---|
| LAN `https://192.168.10.143:8443/app/`（无 token，Basic Auth） | 自动跳转 2 次 → **HTTP 200**（DSH 页面 40102 字节） |
| 公网 `https://47.97.70.99:44904/app/`（无 token） | 自动跳转 2 次 → **HTTP 200** |
| 直接 `/app-login`（带 cookie jar） | → **HTTP 200** |
| 无凭据访问 `/app/` | **401**（不会泄漏 token 跳转） |
| **`supervisorctl restart dsh` 后**（token 从旧变新） | `dsh-login` 自动读取新 token，`/app/` 仍 **200** |
| `/files/` 文件管理 | 不受影响 |

## 4. 组成与回滚

新增/修改：

| 文件 | 说明 |
|---|---|
| `/root/server/bin/dsh-login` | token 重定向小服务（Python 标准库） |
| supervisord `[program:dsh-login]` | 自动拉起/守护，日志 `dsh-login.log` |
| `/etc/nginx/sites-available/dsh-tls` | `/app-login` 改反代；`/app/` 增加 401 自动跳转 |
| 备份 | `/etc/nginx/sites-available/dsh-tls.bak-dshlogin-20261110-145917` |

回滚：

```bash
supervisorctl -c /root/server/etc/supervisord.conf stop dsh-login
cp -a /etc/nginx/sites-available/dsh-tls.bak-dshlogin-20261110-145917 /etc/nginx/sites-available/dsh-tls
nginx -t && nginx -s reload
# 从 supervisord.conf 删除 [program:dsh-login] 段后 reread/update
```

源码归档：
[scripts/server/dsh-login.py](../scripts/server/dsh-login.py)、
[scripts/server/patch-dsh-login-nginx.py](../scripts/server/patch-dsh-login-nginx.py)、
[scripts/server/dsh-login-program.conf](../scripts/server/dsh-login-program.conf)。

## 5. 安全说明

- `dsh-login` 仅监听 `127.0.0.1:3082`，外部只能经 nginx 的 **Basic Auth** 访问 `/app-login`；
- 未认证请求看不到 token（直接 `/app/` 返回 401，而不是 302 带 token）；
- token 仍随 DSH 重启轮换，但用户无感；泄露面与之前相同（Basic Auth + token 双层）；
- 建议不要公开分享带 token 的 URL（`server-dsh url` 仅供自己调试）。

## 6. 变更记录

| 时间 | 变更 | 结果 |
|---|---|---|
| 14:57 | 复现：`/app/` 无 token → 401 提示 | 确认机制 |
| 14:59 | 部署 dsh-login + nginx 补丁 + supervisor | 服务 RUNNING，nginx 配置通过 |
| 15:00 | LAN/公网 `/app/` 自动登录 | 均 200（2 跳转） |
| 15:03 | 重启 DSH 换 token 后复测 | 仍 200；跳转目标为新 token |
