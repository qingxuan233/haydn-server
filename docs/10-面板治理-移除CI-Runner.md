# 10 · 面板治理：移除 CI Runner 卡片 + 按需启用

> 日期：2026-11-10 17:42–17:50
> 背景：面板"代码与 CI"里有三个卡片（Gitea / CI Runner / Git SSH 克隆）。实际检查发现 CI Runner 长期闲置、且 `:host` 模式在 proot 里以 root 执行 workflow，安全收益比不划算。用户决定：**删除卡片，Runner 保留但默认停用，之后按需启用**。

---

## 1. 结论依据（为什么移除卡片）

| 检查项 | 情况 |
|---|---|
| 注册标签 | `ubuntu-latest:host` / `linux:host` / `node:host` —— **宿主机执行，不是容器**（原卡片文案"容器内"不准确） |
| 运行记录 | Gitea DB 仅 1 条初始化测试运行（`add ci workflow`），之后无任务；runner 日志长期只有 declare |
| 资源 | 常驻约 **11 MB RAM**、CPU 0.1%、二进制 16 MB，supervisord 第 N 个常驻服务 |
| 安全 | `:host` 模式 workflow 以 root 直接在服务器 proot 内执行，可访问 Gitea DB、`etc/secrets`、备份口令、SSH 密钥 |
| 展示价值 | 面板卡片原本只是静态"已启用"，不反映真实任务/队列 |

结论：**默认停用，保留二进制与注册信息，需要时 `server-runner on` 一键启用**。

## 2. 实际变更

| 文件/对象 | 变更 | 备份 |
|---|---|---|
| `/root/server/etc/conf.d/dsh-server.conf` | `[program:runner]` 的 `autostart=true` → **false**（默认开机不启动） | `dsh-server.conf.bak-runner-off-20261110-1745` |
| `/root/server/www/index.html` | 删除 CI Runner 卡片；`代码与 CI 3 项` → **2 项**（剩 Gitea / Git SSH 克隆） | `index.html.bak-runner-off-20261110-1745` |
| `/root/server/etc/services.d/runner.json` | 备注更新为"默认停用，按需 `server-runner on`" | `runner.json.bak-runner-off-20261110-1745` |
| 新增 `/root/server/bin/server-runner` | 提供 `on / off / status / logs` 子命令，并软链到 `/usr/local/bin/server-runner` | — |
| 运行时 | `supervisorctl stop runner` + `reread/update` | 可随时 `start` 恢复 |

### 按需启用 / 关闭

```bash
server-runner on      # 启动（立即生效，本次开机内）
server-runner off     # 停止
server-runner status  # 查看状态
server-runner logs    # 查看 runner 日志
```

> 注意：`autostart=false` 只影响**开机**；手动 `server-runner on` 后如果中途重启手机，Runner 不会自动恢复，需要再次 `on`。若想恢复"开机自启+面板卡片"，按 §3 回滚即可。

## 3. 回滚（恢复原状）

```bash
# 1) 恢复 supervisor 配置（autostart=true）
cp -a /root/server/etc/conf.d/dsh-server.conf.bak-runner-off-20261110-1745 /root/server/etc/conf.d/dsh-server.conf
supervisorctl -c /root/server/etc/supervisord.conf reread
supervisorctl -c /root/server/etc/supervisord.conf update
supervisorctl -c /root/server/etc/supervisord.conf start runner

# 2) 恢复面板卡片
cp -a /root/server/www/index.html.bak-runner-off-20261110-1745 /root/server/www/index.html
cp -a /root/server/etc/services.d/runner.json.bak-runner-off-20261110-1745 /root/server/etc/services.d/runner.json
```

## 4. 验证结果（2026-11-10 17:47）

| 检查 | 结果 |
|---|---|
| `supervisorctl status runner` | **STOPPED**（其余 10 个服务 RUNNING） |
| 面板 LAN `http://192.168.10.159:8080/` | "CI Runner" 出现 **0** 次；"代码与 CI **2 项**" |
| 面板公网 `http://47.97.70.99:48108/` | 同上（0 次 / 2 项） |
| `server-runner on` | `runner: started` → RUNNING |
| `server-runner off` | `runner: stopped` → STOPPED |
| 其他服务 | api/dsh/dsh-login/fileui/frpc/gitea/nginx/sshd/syncthing/webdav 全部 RUNNING |

## 5. 备注

- 手机 DHCP IP 在本次变更时变为 **192.168.10.159**（此前 .143）。公网入口不受影响；建议路由器给手机做 **静态租约**，否则面板/SSH 地址会随 DHCP 变化。
- 修改后的面板与 `server-runner` 源码已归档到项目：
  [scripts/server/www/index.html](../scripts/server/www/index.html)、[scripts/server/bin/server-runner](../scripts/server/bin/server-runner)
- 若以后真要用 Gitea Actions：启用 Runner 前先评估 `:host` 执行的权限边界（建议只允许私有仓库、限制可推送 workflow 的成员）。
