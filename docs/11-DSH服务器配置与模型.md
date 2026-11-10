# 11 · DSH 服务器配置与模型配置（按 desktop cordis.patch.yml 迁移）

> 日期：2026-11-10 16:00–16:10
> 目标：把已验证的 desktop 模型配置迁移到手机服务器的 DSH；完善服务器 DSH 的 profile / 凭据 / supervisor 环境。
> 依据：`C:\Users\69559\.dsh\profiles\desktop\cordis.patch.yml`（用户已验证；本次未重复做模型调用验证）。

---

## 1. 生效的 profile 与配置位置

| 项 | 值 |
|---|---|
| DSH 版本 | `@deepseek-ai/dsh 0.2.2-rc.1`（Node 24.22.2） |
| 启动命令 | `dsh web`（即 `--profile web`），监听 `127.0.0.1:3081` |
| 生效 profile | `/root/.dsh/profiles/web/`（DSH 自带的 web profile） |
| 用户补丁层 | `/root/.dsh/profiles/web/cordis.patch.yml` |
| supervisor 环境 | `DSH_PROFILE=web`、`DSH_PROFILE_DIR=/root/.dsh/profiles/web`、`DSH_HOME=/root/.dsh` |
| 凭据文件 | `/root/.dsh/.credentials.yaml`（600） |

> 说明：supervisord 命令是 `bin.js web`，即 web app + **web profile**；`DSH_PROFILE` 环境已同步为 `web`，避免之前的 `server` 命名不一致。

## 2. 迁移的配置内容

服务器补丁文件：[scripts/server/dsh-web-cordis.patch.yml](../scripts/server/dsh-web-cordis.patch.yml)（无密钥，可版本管理）。

| 条目 | 内容 |
|---|---|
| `agent-default-model` | **provider=open-design / model=deepseek-v4.1-flash-eco / reasoningEffort=max** |
| `llm-pi-ai` | 4 个 provider：`open-design`、`siliconflow`、`opencode-go`、`easy-cliproxyapi`，各自模型参数（contextWindow/maxTokens/vision/reasoningEfforts）完全按 desktop 文件 |
| `subagent-model-selection-settings` | 允许子代理选择 easy-cliproxyapi/gemini-3.8-flash-high、open-design 的 flash/mimo/glm/kimi 等 |
| `subagent` | `maxDepth: 2` |
| `ui-settings-account` / `ui-chat` / `ui-settings` | 账户引导完成、对话详情、设置面板开启 |
| `ui-theme` | `preference: dark` |
| `agent-preset-registry` | `default/selectedDefault: standard` |
| `plugin-market` | jsdelivr 插件市场索引 |
| `ui-settings-general` | 欢迎页版本，避免首次配置引导 |

**未迁移（服务器无对应插件）**：

- `web-ui-pet`（`@linxin666/dsh-pet` 未安装）
- `gemini-adapter`（`dsh-gemini-adapter` 未安装）

## 3. API Key 补齐

desktop 的 `.credentials.yaml` 中提供了一个共享的 `refs:` 层；服务器原来只有 2 个：

| Key 名 | 迁移前 | 迁移后 |
|---|---|---|
| `OPENCODE_GO_API_KEY` | ✅ | ✅ |
| `OPEN_DESIGN_API_KEY` | ✅ | ✅ |
| `SILICONFLOW_API_KEY` | ❌ | ✅（从 desktop `refs` 合并） |
| `EASYCLIPROXYAPI_API_KEY` | ❌ | ✅（从 desktop `refs` 合并） |

- 只合并所需 `refs`，未复制 desktop 的浏览器会话/设备记录；
- 文件权限保持 `600`；值不写入文档/仓库。

## 4. 配置校验（不调用模型）

按用户要求**不做模型调用验证**，仅做结构与组合校验：

```bash
cd /root
DSH_HOME=/root/.dsh dsh --profile web --dump-config > /tmp/dsh-dump.yml 2>/tmp/dsh-dump.err
# exit=0, 1701 行
```

`dump-config` 中确认：

```yaml
- id: agent-default-model
  name: '@deepseek-ai/dsh-agent-default-model'
  config:
    provider: open-design
    model: deepseek-v4.1-flash-eco
    reasoningEffort: max
```

以及 `llm-pi-ai` 的 4 个 provider 均按 desktop 配置出现。

## 5. 上线与回归

| 检查 | 结果 |
|---|---|
| `dsh --profile web --dump-config` | exit 0，1701 行，默认模型正确 |
| supervisor `dsh` | RUNNING（重启后正常打印新 token） |
| `/app-login`（LAN，Basic + cookie） | **200，1 次跳转** |
| `/app/`（无 token，自动登录） | **200，2 次跳转**（公网 200） |
| `dsh-login` broker | 升级为 2.2：同时下发 `dsh-auth` 会话 cookie + `dshbrk` 入口标记（现网 nginx `/app/` 以 `dshbrk` 判断是否已走登录入口），拿不到 token/DSH 未就绪 → **503 提示**，不再回退 token 跳转循环 |
| 服务总量 | 11/11 RUNNING |

## 6. 已知限制

- `easy-cliproxyapi` 的 `baseURL` 按 desktop 保留为 `http://127.0.0.1:8317/v1`：
  - 这是 **desktop 本机的本地代理**；手机服务器上默认没有该代理，选中该 provider 的模型会连接失败；
  - 默认模型是 `open-design`（公网 API），不受影响；
  - 如需在手机上使用，需要在本机运行同款代理并用 `adb reverse`/局域网地址可达，或把 baseURL 改为手机可达的地址。
- 其余 provider（open-design / siliconflow / opencode-go）为公网 API，凭据已补齐。
- 模型参数（上下文、vision、reasoningEfforts）按 desktop 文件原样迁移；用户已在 desktop 验证，本次不再复验。

## 7. 回滚

服务器上自动备份（`20261110-160358`）：

```bash
cp -a /root/.dsh/.credentials.yaml.bak-20261110-160358 /root/.dsh/.credentials.yaml
cp -a /root/.dsh/profiles/web/cordis.patch.yml.bak-20261110-160358 /root/.dsh/profiles/web/cordis.patch.yml
cp -a /root/server/etc/supervisord.conf.bak-dshprofile-20261110-160358 /root/server/etc/supervisord.conf
supervisorctl -c /root/server/etc/supervisord.conf reread
supervisorctl -c /root/server/etc/supervisord.conf update
supervisorctl -c /root/server/etc/supervisord.conf restart dsh
```

## 8. 变更记录

| 时间 | 变更 | 结果 |
|---|---|---|
| 16:00 | 读取 desktop cordis.patch.yml，筛选服务器可用条目 | 生成 server 补丁 |
| 16:02 | 合并 SILICONFLOW/EASYCLIPROXYAPI 凭据 | refs 4 项 |
| 16:03 | 上传 patch + credentials，supervisor env 改为 web | 备份 `bak-20261110-160358` |
| 16:04 | `--dump-config` 校验 | exit 0，默认模型 eco/max |
| 16:05 | 重启 dsh | 新 token 输出，服务 RUNNING |
| 16:08 | `/app-login` / `/app/` 回归 | LAN/公网均 200 |
| 16:09 | dsh-login 2.1（503 回退） | 启动瞬间不再循环 |
