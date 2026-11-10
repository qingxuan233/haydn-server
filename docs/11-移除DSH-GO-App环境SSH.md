# 11 · 移除 DSH-GO App 环境 SSH（2224 / 57166）

> 时间：2026-11-10 15:44–15:48
> 需求：控制台主页「远程访问」里的 **App 环境 SSH**（`ssh -p 2224 root@…` / 公网 `57166`）是 2026-11-09 用 **DSH-GO APP** 拉起的旧容器入口；现在不再使用该方案和 APP，可以删除。
> 结论：已删除页面卡片、frp 隧道（2224→57166）与相关配置；剩余远程入口保持正常。

---

## 1. 变更内容

| 对象 | 变更 |
|---|---|
| `/root/server/www/index.html` | 删除「App 环境 SSH」卡片；「远程访问」计数由 **4 项 → 3 项**；删除 `cmd-app-lan` / `cmd-app-pub` 两条 JS 赋值（避免空元素报错导致后续脚本中断） |
| `/root/server/frp/frpc.toml` | 删除 `[[proxies]]` 块 **NSrvrJfZyOPC**（`localPort=2224` → `remotePort=57166`）；隧道数 **7 → 6** |
| `/root/server/etc/services.d/frpc.json` | 更新 notes：6 条隧道，去掉 2224→57166 描述 |
| 手机 App | 检查 `pm list packages`：**DSH-GO / deepseek 类应用已不存在**（恢复出厂后未恢复），无需卸载 |

> 2224 原本由旧 DSH-GO App 的容器 sshd 提供；该容器与 App 均已不在本机，当前 `127.0.0.1:2224` 无监听。

### 备份（服务器上）

```
/root/server/www/index.html.bak-remove-appenv-20261110-1546
/root/server/frp/frpc.toml.bak-remove-appenv-20261110-1546
/root/server/etc/services.d/frpc.json.bak-remove-appenv-20261110-1546
```

## 2. 验证结果

| 检查 | 结果 |
|---|---|
| 主页 `/`（LAN / 公网 48108） | HTTP 200，25551 字节；**无 App 环境 SSH / 2224 / 57166 / cmd-app**；远程访问显示 **3 项** |
| frpc 配置校验 | `frpc verify -c frpc.toml` → syntax OK |
| frpc 重启后日志 | 6 个 proxy 全部 start success，无 `NSrvrJfZyOPC` |
| 公网 57166 | **关闭**（False） |
| 公网 13872 / 48108 / 44904 | 正常（True） |
| LAN 2222 SSH | 正常 |
| 2224 本地监听 | 无（容器已不存在） |

## 3. 回滚

```bash
# 恢复页面与 frp 配置
cp -a /root/server/www/index.html.bak-remove-appenv-20261110-1546 /root/server/www/index.html
cp -a /root/server/frp/frpc.toml.bak-remove-appenv-20261110-1546 /root/server/frp/frpc.toml
cp -a /root/server/etc/services.d/frpc.json.bak-remove-appenv-20261110-1546 /root/server/etc/services.d/frpc.json
supervisorctl -c /root/server/etc/supervisord.conf restart frpc
nginx -s reload
```

> 回滚仅恢复配置/页面；如果确实不再使用 DSH-GO，无需回滚。旧的 2224 容器本身已随 App 不复存在。

## 4. 后续远程入口（保留）

| 入口 | 地址 |
|---|---|
| 容器 SSH（局域网） | `ssh -p 2222 root@192.168.10.143`（密钥 `backup/ssh/id_haydn`） |
| 容器 SSH（公网） | `ssh -p 13872 root@47.97.70.99` |
| DSH 网页版 | `https://192.168.10.143:8443/app-login` / `https://47.97.70.99:44904/app-login` |
| Gitea SSH | 公网 26249（frp 2223→26249，保留） |

## 5. 变更记录

| 时间 | 变更 | 结果 |
|---|---|---|
| 15:44 | 定位页面/配置：`www/index.html`、`frp/frpc.toml`、`services.d/frpc.json` | 确认 2224 来源 |
| 15:46 | 删除卡片/JS、frp 隧道、notes；服务器备份后部署 | frpc verify OK |
| 15:47 | `supervisorctl restart frpc` | 6 条隧道 RUNNING，无 NSrvrJfZyOPC |
| 15:48 | 公网/页面/2224 验证 | 57166 关闭，页面 3 项，其余正常 |
