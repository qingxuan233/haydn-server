# toolkit 测试覆盖与 fixture 说明

> 本文件承接 [toolkit/README.md](../README.md) §10 的覆盖清单，只描述测试范围与离线 fixture；命令、退出码与工具契约仍以 README §3/§10 与各子命令 `--help` 为准。测试全部离线，不依赖真机与网络。

## 1. 覆盖范围

- **front matter**：BOM/CRLF/列表/引号/错误分支。
- **profile**：结构校验与模板/schema 一致性。
- **assess**：四条路线与门禁/软门禁/未知降置信度。
- **plan**：P0–P6 与 A/B 差异。
- **index**：根摘要 ≤160 行/≤16KB；四层分片字段与限额；counts 一致；旧分片清理；缺失目录/front matter 半成品容错；`index --check` 一致/篡改分片/篡改根摘要/generated_at 无关；两次重建仅 generated_at 不同（AR-06 幂等）。
- **validate**：重复 ID/断链/anchor/绝对路径/JSON/manifest 一致性与 legacy content；doc-policy 行数/CHANGELOG 窗口 ≤8/归档字节/状态段落；`--mtime-check` 默认关闭语义；policy 缺失回退；strict 升级；**TOOL 登记表一致性**（一致全绿；CLI 命令漏登记/多登记、编号断号、manifest `commands` 漂移、缺 README 跳过）；**updated 新鲜度**（临时 git 仓库：新鲜无提示、滞后报 advisory 且 strict 不失败、未跟踪文件跳过）。
- **governance**：协议缺章节/缺哨兵/版本行非法/320 硬上限与 201~320 不算失败；命名大写/中文/状态词/前缀/README 豁免；PIT 跳号/缺段/超 40；ADR 文件名/ID/状态/缺段/superseded 回链/索引孤儿；CHANGELOG 归档条数/文件缺失/版本范围/未登记；backlog 缺字段/非法枚举/done 缺 result/ID 跳号/depends 断链/outputs 绝对路径；AR-02/AR-03；以及 **AR-04 反例自证**（构造 6 类违规后 validate 报 error 且 CLI exit 4）。
- **preflight**：全绿 0 / `--skip-*` 出 SKIPPED=3 / validate 失败=4 / unittest 失败=4 / check-links 失败=4 / 脚本缺失降级 SKIPPED；步骤表与 `--json` 字段。
- **CLI**：`--help`/退出码；fixture 离线 detect/probe/assess/plan/rootcheck/rescue-kit/new-profile/index/validate/preflight；Cp936 管道 JSON 合法 UTF-8。
- **rootcheck**：三态/人工项/AVB 矛盾/verity/SELinux/多管理器/GKI/KALLSYMS/分区/ARB。
- **rescue-kit**：清单/相对路径/自排除/修改/缺失/新增/空目录/CLI 0/4/2。

## 2. 离线 fixture

- [adb-haydn.json](fixtures/adb-haydn.json)
- [profile-haydn-locked.json](fixtures/profile-haydn-locked.json)
- [profile-root-lab-ready.json](fixtures/profile-root-lab-ready.json)
- [repo_builder.py](fixtures/repo_builder.py)：生成含 AGENTS/backlog/CHANGELOG/adr 的完整最小仓库，另有 helper 构造违规样本与 preflight stub。
