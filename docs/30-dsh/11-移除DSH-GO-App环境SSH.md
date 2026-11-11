# 11 · 移除 DSH-GO App 环境 SSH（2224 / 公网旧端口）

| 项目 | 内容 |
|---|---|
| 文档 ID | `HB-DSH-011b` |
| 版本 | v2.0（2026-11-11） |
| 状态 | 已归档（2026-11-10 历史结论）；当前状态见 [当前状态](../00-overview/当前状态.md) |
| 关联 | [07 DSH 部署](07-DSH与Linux优化.md) · [03 操作手册](../20-server/03-操作手册.md) · [20 控制平面方案](20-DSH控制平面方案.md) |

> **已归档（2026-11-10）**：DSH-GO App 环境的 `2224`（本地）/ 公网旧端口（见私密记录）入口已删除、方案不再使用；本文仅保留当时的变更与验证证据。当前远程入口以 [03 操作手册](../20-server/03-操作手册.md) 与 [当前状态](../00-overview/当前状态.md) 为准。

> 时间：2026-11-10 15:44–15:48
> 需求：控制台主页「远程访问」里的 **App 环境 SSH**（`ssh -p 2224 root@…` / 公网旧端口，见私密记录）是 2026-11-09 用 **DSH-GO APP** 拉起的旧容器入口；现在不再使用该方案和 APP，可以删除。
> 结论：已删除页面卡片、frp 隧道（2224→公网旧端口，见私密记录）与相关配置；剩余远程入口保持正常。

---

## 1. 变更内容

| 对象 | 变更 |
|---|---|
| `/root/server/www/index.html` | 删除「App 环境 SSH」卡片；「远程访问」计数由 **4 项 → 3 项**；删除 `cmd-app-lan` / `cmd-app-pub` 两条 JS 赋值（避免空元素报错导致后续脚本中断） |
| `/root/server/frp/frpc.toml` | 删除 `[[proxies]]` 块 **NSrvrJfZyOPC**（`localPort=2224` → `remotePort=<公网旧端口>`，见私密记录）；隧道数 **7 → 6** |
| `/root/server/etc/services.d/frpc.json` | 更新 notes：6 条隧道，去掉 2224→公网旧端口的描述 |
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
| 主页 `/`（LAN / 公网只读入口） | HTTP 200，25551 字节；**无 App 环境 SSH / 2224 / 公网旧端口 / cmd-app**；远程访问显示 **3 项**（公网入口见私密记录） |
| frpc 配置校验 | `frpc verify -c frpc.toml` → syntax OK |
| frpc 重启后日志 | 6 个 proxy 全部 start success，无 `NSrvrJfZyOPC` |
| 公网旧端口（见私密记录） | **关闭**（False） |
| 公网 SSH / HTTP / HTTPS 入口 | 正常（True）（端口见私密记录） |
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

## 4. 后续远程入口（保留；历史快照 2026-11-10）

> 完整入口清单与操作以 [03 操作手册](../20-server/03-操作手册.md) 为准；当前状态见 [当前状态](../00-overview/当前状态.md)。

| 入口 | 地址 |
|---|---|
| 容器 SSH（局域网） | `ssh -p 2222 root@192.168.10.143`（密钥 `backup/ssh/id_haydn`） |
| 容器 SSH（公网） | `ssh -p <公网SSH端口> root@<公网入口>`（具体值见运维私密记录） |
| DSH 网页版 | LAN `https://192.168.10.143:8443/app-login` / 公网 `https://<公网入口>/app-login`（见私密记录） |
| Gitea SSH | 公网端口（见私密记录，frp 2223 转发，保留） |

## 5. 变更记录

| 时间 | 变更 | 结果 |
|---|---|---|
| 15:44 | 定位页面/配置：`www/index.html`、`frp/frpc.toml`、`services.d/frpc.json` | 确认 2224 来源 |
| 15:46 | 删除卡片/JS、frp 隧道、notes；服务器备份后部署 | frpc verify OK |
| 15:47 | `supervisorctl restart frpc` | 6 条隧道 RUNNING，无 NSrvrJfZyOPC |
| 15:48 | 公网/页面/2224 验证 | 公网旧端口关闭，页面 3 项，其余正常 |
