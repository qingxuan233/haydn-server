"""plan：根据 profile/assess 生成 P0–P6 阶段计划（json 或 markdown）。

计划是**生成物**：阶段动作按路线（A/B/C/D）不同，每阶段带门禁、退出标准与回滚方式。
``--route auto`` 使用 assess 的推荐路线；显式指定路线时仍会读取 profile 做防呆提示。
"""

from __future__ import annotations

from typing import Any

from .assess import ROUTE_LABELS, assess_profile, select_route, evaluate_gates
from .util import SCHEMA_PLAN, get_nested, iso_now

STAGE_IDS = ("P0", "P1", "P2", "P3", "P4", "P5", "P6")
"""阶段 ID 固定为 P0–P6。"""

_COMMON_P0 = {
    "id": "P0",
    "title": "P0 · 立项、边界与备份",
    "objective": "确认改造用途与不可回滚项，完成可验证备份，明确不做清单。",
    "actions": [
        "写下目标用途与最小成功标准（例如：SSH + 1 个自托管服务 + 可远程恢复）",
        "确认设备当前状态（型号/系统/解锁/Root/存储/电池健康），记录快照",
        "备份照片、文档、应用数据与关键配置，并做一次恢复校验",
        "阅读 guardrails/ 红线与 pitfalls/ 相关条目，列出本机不做的操作",
    ],
    "deliverables": [
        "改造目标与不做清单",
        "备份完成与恢复校验记录",
        "设备基线快照（profile 或人工记录）",
    ],
    "gate": "P0 门禁：备份可恢复 + 边界（不 Root/不刷机/不卸载系统包）已确认",
    "exit_criteria": [
        "备份可被验证恢复（至少抽查 1 个样本）",
        "已记录基线：机型、系统版本、解锁状态、Root 状态",
        "已列出不允许执行的高风险操作",
    ],
    "rollback": ["本阶段无系统改动；中止时只需保留备份并停止后续阶段"],
}

_COMMON_P1 = {
    "id": "P1",
    "title": "P1 · 取证、能力探测与路线确认",
    "objective": "用 detect/probe/assess 建立可复核的设备档案，锁定改造路线。",
    "actions": [
        "运行 detect 生成脱敏 profile：python -m toolkit.repurpose detect --out profiles/<codename>.json",
        "运行 probe 补齐 capabilities：python -m toolkit.repurpose probe --base profiles/<codename>.json --out profiles/<codename>-probed.json",
        "运行 assess：python -m toolkit.repurpose assess --profile profiles/<codename>-probed.json --json",
        "人工核对 unknowns/assumptions，逐项补证据后重跑 assess",
        "确认 G-B0/G-B1/G-B2/G-D 等关键门禁结论与人工判断一致",
    ],
    "deliverables": [
        "device-profile.v1 JSON（脱敏，含 capabilities/verdicts）",
        "assessment.v1 JSON（路线/门禁/风险/下一步）",
        "unknowns/assumptions 补证清单",
    ],
    "gate": "P1 门禁：路线结论有证据支撑，unknown 项已标注（不得臆测）",
    "exit_criteria": [
        "profile 通过结构校验（assess 不报 schema 错误）",
        "路线与门禁结论可解释（每条 fail/unknown 有原因）",
        "敏感信息（序列号/IP/token）未进入 profile 与文档",
    ],
    "rollback": ["本阶段仅读设备；中止不产生设备改动，删除/废弃 profile 副本即可"],
}

_COMMON_P5 = {
    "id": "P5",
    "title": "P5 · 验收与稳定性观察",
    "objective": "用可复现实验证明自启、服务与长期运行达标，不以文档声称替代实测。",
    "actions": [
        "执行 5 次重启，记录每次服务恢复时间与失败次数（目标全部可自启）",
        "执行 24h soak：toolkit/termux/soak.sh 记录可用率/失败/重启次数",
        "故障注入：断网、杀进程、服务异常、Bridge/控制面不可用时的降级路径",
        "恢复演练：从备份恢复一次关键配置或服务，验证回滚路径",
    ],
    "deliverables": [
        "5 次重启记录",
        "24h soak 记录（可用率 ≥ 目标值；失败计数与原因）",
        "故障注入与恢复演练记录",
        "验收清单（对照 methodology/07-validation.md）",
    ],
    "gate": "P5 门禁：5 次重启 + 24h soak + 恢复演练全部通过（未实测不得标记完成）",
    "exit_criteria": [
        "5/5 重启后核心服务自动恢复",
        "24h soak 可用率达到目标且失败有归因",
        "至少 1 次恢复演练成功并有记录",
        "已知失败模式写入 pitfalls/ 或文档限制",
    ],
    "rollback": [
        "按阶段快照回退配置；服务回滚走 server-ops Tier2（--confirm + 快照 + 审计）",
        "设备无法启动时按救援链路（原厂镜像/fastboot/官方刷机包）处理",
    ],
}

_COMMON_P6 = {
    "id": "P6",
    "title": "P6 · 沉淀、交接与持续改进",
    "objective": "把结论固化为方法论/护栏/踩坑/工具/案例，让下一个 Agent 可复现。",
    "actions": [
        "更新案例文档与 profile（脱敏），标注实测与未实测项",
        "把失败模式提炼为 pitfalls/ 条目，把红线提炼为 guardrails/ 条目",
        "运行 python -m toolkit.repurpose index 重建 agent-manifest.json",
        "运行 validate --strict 与全量单元测试，确保基线全绿",
        "更新 backlog.json 状态/result，并在 CHANGELOG.md 记录契约变化",
    ],
    "deliverables": [
        "案例 README/profile/oem-profile（如适用）",
        "新增/修订 PIT、GRD 条目",
        "agent-manifest.json（重建）",
        "backlog/CHANGELOG 更新",
    ],
    "gate": "P6 门禁：validate --strict 与 toolkit unittest 全绿，索引与内容一致",
    "exit_criteria": [
        "agent-manifest.json 无 warnings",
        "validate --strict 通过",
        "python -m unittest discover -s toolkit/tests -t . -v 全绿",
        "未完成项已进入 backlog 并标注原因",
    ],
    "rollback": ["文档/索引变更可 revert；设备侧不再改动"],
}

_ROUTE_STAGES: dict[str, list[dict[str, Any]]] = {
    "A": [
        {
            "id": "P2",
            "title": "P2 · Termux + proot 服务器栈",
            "objective": "在无 Root 约束下建立可用的 Linux 用户态环境与服务栈。",
            "actions": [
                "从可信来源安装 Termux（F-Droid/GitHub release；不用来路不明的 APK）",
                "安装 proot-distro，创建 Ubuntu/Debian 发行版（aarch64）",
                "在 proot 内用 supervisord 或 s6 管理服务（不要依赖 systemd）",
                "配置 SSH/Web/自托管服务，端口仅绑 loopback 或局域网",
                "验证 /proc 与 /sdcard 绑定限制（避免 proot 崩溃，参考 PIT 记录）",
            ],
            "deliverables": [
                "proot 发行版与包清单",
                "supervisord/s6 配置与启动脚本",
                "服务端口与访问路径清单",
            ],
            "gate": "P2 门禁：proot 内核心服务可启动、可重启、无系统级写操作",
            "exit_criteria": [
                "proot 内至少 1 个服务可通过 supervisord/s6 启停",
                "SSH 或 Web 入口可从局域网访问（按需）",
                "未使用 systemd/Docker 等不可用依赖",
            ],
            "rollback": ["删除 proot 发行版或恢复其备份；Termux 应用可卸载重装"],
        },
        {
            "id": "P3",
            "title": "P3 · 自启、保活与电源/热管理",
            "objective": "保证无 Root 环境下重启可自启、后台不被清理、长期插电可控。",
            "actions": [
                "安装 Termux:Boot，配置启动脚本（wait 网络/延迟/幂等/日志）",
                "按 oem-profile 配置电池优化白名单、自启动、后台弹出与 appops",
                "启用 termux-wake-lock；关闭屏幕常亮并降低刷新率/亮度",
                "配置充电保护/限充（系统自带或旁路供电；无 Root 不硬改 sysfs）",
                "5 次重启验证自启链路（Termux:Boot → 启动脚本 → 服务健康检查）",
            ],
            "deliverables": [
                "Termux:Boot 启动脚本",
                "OEM 白名单与电池优化配置记录",
                "5 次重启自启记录",
            ],
            "gate": "P3 门禁：断电重启后服务自动恢复，且无 OEM 清理导致的反复掉线",
            "exit_criteria": [
                "5/5 重启后 Termux 服务可用",
                "电池优化白名单与自启项已配置并可复核",
                "长期插电温度/电池策略已记录（有条件的做限充）",
            ],
            "rollback": ["禁用 Termux:Boot 启动脚本并手动启动服务；恢复 OEM 设置"],
        },
        {
            "id": "P4",
            "title": "P4 · 遥测、观测与控制面（无 Root 边界）",
            "objective": "在无 Root 限制下建立可用的观测数据与远程控制面，明确不可得字段。",
            "actions": [
                "部署 Bridge/宿主机遥测采集（App 可访问字段；不可得字段返回 null）",
                "实现采集回退：Bridge 不可用时回退 Termux 采集并标注 source",
                "配置自托管控制面（仅 loopback，鉴权 + token 隔离 + 审计）",
                "接入 healthcheck/soak 观测，定义可用率口径",
                "记录无 Root 下不可得字段清单，避免拿假数据当真实时指标",
            ],
            "deliverables": [
                "观测字段清单（可得/不可得/回退来源）",
                "控制面访问路径与鉴权说明（不含凭据值）",
                "healthcheck/soak 观测输出",
            ],
            "gate": "P4 门禁：观测数据来源可解释，不可得字段不伪造；控制面不暴露公网",
            "exit_criteria": [
                "所有展示字段有 source 标记（bridge/termux/null）",
                "控制面鉴权与限流已配置",
                "无 token/口令进入日志或文档",
            ],
            "rollback": ["停用控制面/遥测服务并使用只读采集；回滚到上一版配置快照"],
        },
    ],
    "B": [
        {
            "id": "P2",
            "title": "P2 · 解锁与 Root 环境（高风险阶段）",
            "objective": "在明确授权与可救援前提下完成解锁/Root，建立 chroot/容器服务基座。",
            "actions": [
                "执行 G-B0 解锁可行性复核：官方解锁政策、账号门槛、数据抹除风险",
                "全量备份并确认设备不再作日常主力机（解锁会抹除 userdata）",
                "解锁 Bootloader；保留原厂完整固件与 boot.img，验证可进入 fastboot/recovery",
                "安装 Magisk/KernelSU/APatch 之一，修补 boot 并验证可正常开机",
                "chroot 挂载 /proc /sys /dev，用 s6/supervisord 管理服务；systemd 仅在 cgroup 委派可用时尝试",
            ],
            "deliverables": [
                "解锁/救援记录（含原厂镜像校验值）",
                "Root 管理器与版本、boot 镜像备份",
                "chroot 挂载脚本与服务管理配置",
            ],
            "gate": "P2 门禁：可正常开机 + Root 可验证 + 救援链路可用",
            "exit_criteria": [
                "解锁与 Root 后 5 次重启可进系统",
                "原厂 boot.img 已备份且校验通过",
                "chroot 内服务可启动并绑定受限端口",
            ],
            "rollback": [
                "fastboot flash 原厂 boot.img 恢复无 Root 状态",
                "无法开机时用官方完整包/MiFlash 或等价工具恢复（可能需授权账号）",
            ],
        },
        {
            "id": "P3",
            "title": "P3 · Root 自启与服务持久化",
            "objective": "用 Root 常驻机制保证重启自启，并处理 OTA/完整性/安全代价。",
            "actions": [
                "用 Magisk service.d/post-fs-data.d（或等价机制）拉起服务器启动脚本",
                "配置电池白名单与 termux-wake-lock（Root 不等于不受 OEM 限制）",
                "关闭自动 OTA 或制定升级前备份/还原 boot 的流程",
                "评估 Play Integrity/银行类 App 与保修影响，必要时保留双设备方案",
                "5 次重启验证自启与 Root 保留情况",
            ],
            "deliverables": [
                "Root 自启脚本与服务守护配置",
                "OTA/完整性影响评估记录",
                "5 次重启记录",
            ],
            "gate": "P3 门禁：重启后 Root 与服务器服务均自动恢复，且 OTA 风险已记录",
            "exit_criteria": [
                "5/5 重启后服务可用",
                "自启脚本可幂等重入（不会重复启动/死锁）",
                "OTA 升级与 Root 失效的恢复流程已文档化",
            ],
            "rollback": ["禁用 service.d 脚本并手动启动；OTA 前先备份 boot，必要时还原原厂镜像"],
        },
        {
            "id": "P4",
            "title": "P4 · 特权遥测与容器评估（Root 能力上限）",
            "objective": "在 Root 下补齐全局遥测，并在门禁 G-B2 满足时尝试容器；不满足就退回 chroot。",
            "actions": [
                "验证 root shell 可读 /proc/stat、/proc/net/dev、dumpsys、appops、settings",
                "如 G-B2 通过，安装 Docker/Podman 并跑 hello-world + 实际服务验证",
                "若容器不可用，退回 chroot + s6/supervisord，不修改内核硬刚",
                "控制面加固：mTLS/配对/token 轮换/限流，Bridge 仅 loopback",
                "记录特权面攻击面与最小权限边界",
            ],
            "deliverables": [
                "特权遥测字段与验证记录",
                "容器可行性实测结论（pass/fail + 原因）",
                "控制面加固清单",
            ],
            "gate": "P4 门禁：特权遥测不用于越权；容器结论有实测证据；控制面仅 loopback",
            "exit_criteria": [
                "全局遥测字段可读且数值合理",
                "容器路线有明确 go/no-go 结论",
                "无 token/证书/口令进入日志、文档或聊天",
            ],
            "rollback": ["停容器改用 chroot；撤销特权采集并保留只读回退；回滚配置快照"],
        },
    ],
    "C": [
        {
            "id": "P2",
            "title": "P2 · 自定义内核/第三方 ROM（研究性阶段）",
            "objective": "在可复制、可救援的前提下验证社区内核/ROM 是否补齐容器所需能力。",
            "actions": [
                "确认目标机型存在可复现的第三方 ROM/自编译内核与明确救砖链路",
                "保留原厂完整固件、boot/DTBO 备份与当前 slot 信息",
                "先只读验证内核能力（namespace/cgroup/overlay/iptables）是否达标",
                "逐项变更并每次验证可开机；严禁一次性刷入未验证组合",
                "记录对 modem/相机/热管理/OTA 的影响",
            ],
            "deliverables": [
                "内核/ROM 来源与校验值、构建或下载记录",
                "内核能力验证记录（对照 G-B2）",
                "回滚与救砖步骤",
            ],
            "gate": "P2 门禁：可正常开机 + 内核能力达标 + 救援链路可用",
            "exit_criteria": [
                "5 次重启可进系统",
                "容器前提（若目标为容器）实测通过",
                "关键硬件功能（Wi-Fi/充电/温度）验证通过",
            ],
            "rollback": [
                "fastboot 恢复原厂 boot/DTBO 并刷回完整固件",
                "无法开机时走官方救援/EDL（需授权账号或售后）",
            ],
        },
        {
            "id": "P3",
            "title": "P3 · 自定义系统上的自启与兼容性",
            "objective": "在第三方系统上重建自启、服务与电源管理，并评估长期维护成本。",
            "actions": [
                "按该 ROM 的机制配置自启（Magisk service.d 或 init 脚本）",
                "验证 Wi-Fi/热点/充电限制/热管理在第三方内核下的行为",
                "记录 OTA/维护状态：无更新、无社区支持时标记为不可长期使用",
                "5 次重启与 24h 空载稳定性验证",
            ],
            "deliverables": [
                "自启配置与重启记录",
                "硬件兼容性验证表",
                "维护性评估（更新频率/社区支持/风险）",
            ],
            "gate": "P3 门禁：重启自启稳定且硬件兼容性无阻塞问题",
            "exit_criteria": [
                "5/5 重启后服务可用",
                "Wi-Fi/充电/温度至少各 1 项长跑验证通过",
                "维护性结论明确（可长期/仅研究）",
            ],
            "rollback": ["回退原厂固件；禁用自启脚本；停止使用第三方内核"],
        },
        {
            "id": "P4",
            "title": "P4 · 容器/服务栈与研究性验证",
            "objective": "验证容器能力与工作负载，量化收益与风险，决定是否值得保留。",
            "actions": [
                "若 G-B2 通过：跑 Docker/Podman hello-world 与实际容器化服务",
                "对比 chroot/proot 方案的性能与稳定性（编译、I/O、网络）",
                "建立观测与回滚：服务快照、配置版本化、日志轮转",
                "明确研究性边界：不用于承载不可恢复的业务",
            ],
            "deliverables": [
                "容器/服务栈实测结论",
                "性能与稳定性对比记录",
                "研究性使用边界声明",
            ],
            "gate": "P4 门禁：收益/风险结论有实测数据；不满足则回退 A/B",
            "exit_criteria": [
                "容器或服务栈至少 1 个工作负载长跑通过",
                "性能/稳定性结论可复核",
                "已明确不建议生产使用的范围",
            ],
            "rollback": ["恢复原厂/Root 方案与快照；停止实验性内核/容器组合"],
        },
    ],
    "D": [
        {
            "id": "P2",
            "title": "P2 · 原生 Linux 移植验证（仅移植存在时）",
            "objective": "确认设备是否真有可用的 mainline/发行版移植，并验证服务器所需硬件链路。",
            "actions": [
                "确认目标设备在 mainline/postmarketOS(Nura)/Ubuntu Touch 等是否有移植与维护者",
                "无移植或无维护者时立即停止 D 路线，回到 A/B",
                "保留原厂固件与恢复链路；先做只读/可回滚验证",
                "逐项验证 Wi-Fi、充电/电池、热管理、存储、USB 网络",
                "记录相机/modem 等非服务器关键功能的缺失",
            ],
            "deliverables": [
                "移植来源、维护状态与版本记录",
                "服务器关键硬件验证表",
                "回滚/救砖步骤",
            ],
            "gate": "P2 门禁：存在可维护移植 + 关键硬件可用 + 救援链路可用",
            "exit_criteria": [
                "Wi-Fi/充电/热管理/存储至少各 1 项实测通过",
                "系统可从备份/原厂固件恢复",
                "缺失功能已列入限制清单",
            ],
            "rollback": ["刷回原厂完整固件；保留 boot/分区备份；必要时走 EDL/售后"],
        },
        {
            "id": "P3",
            "title": "P3 · 原生系统上的服务化与电源管理",
            "objective": "在原生 Linux 上建立自启、服务管理与长期供电策略。",
            "actions": [
                "使用发行版原生 init（systemd/OpenRC 等）管理服务，确认 PID1 正常",
                "配置开机自启、看门狗、日志轮转与磁盘水位",
                "验证长期插电的电池策略（限充/旁路，取决于移植质量）",
                "5 次重启验证与 24h 空载稳定性",
            ],
            "deliverables": [
                "服务单元/自启配置",
                "电源与热管理策略",
                "5 次重启与空载稳定性记录",
            ],
            "gate": "P3 门禁：重启自启稳定、电源/热管理无阻塞问题",
            "exit_criteria": [
                "5/5 重启后服务与网络可用",
                "电池/温度在 24h 内无异常",
                "日志轮转与磁盘水位监控生效",
            ],
            "rollback": ["回退上一版系统镜像；停用自启服务；恢复原厂固件"],
        },
        {
            "id": "P4",
            "title": "P4 · 观测与控制面（原生 Linux）",
            "objective": "在无 Android 框架的环境下重建观测/控制面，验证与 A/B 路线的差异。",
            "actions": [
                "用标准 Linux 手段采集 /proc/stat、/proc/net/dev、温度与电池",
                "建立 SSH/控制面仅内网访问，禁用公网默认入口",
                "与 A/B 路线对比能力、稳定性、维护成本",
                "记录移植缺陷导致的观测盲区",
            ],
            "deliverables": [
                "观测字段与采集方式",
                "控制面访问与鉴权说明",
                "A/B/C/D 能力对比结论",
            ],
            "gate": "P4 门禁：观测完整可解释，控制面不暴露公网",
            "exit_criteria": [
                "全局 CPU/网络/温度/电源字段可读",
                "控制面鉴权与最小暴露检查通过",
                "对比结论可复核",
            ],
            "rollback": ["停用控制面；恢复原厂系统/上一版镜像"],
        },
    ],
}


def _common_stages() -> list[dict[str, Any]]:
    return [
        _COMMON_P0,
        _COMMON_P1,
        _COMMON_P5,
        _COMMON_P6,
    ]


def build_plan(profile: dict[str, Any], route: str | None = None) -> dict[str, Any]:
    """生成计划对象；route 为 None/"auto" 时使用 assess 推荐路线。"""
    if route in (None, "", "auto", "AUTO"):
        assessment = assess_profile(profile)
        selected = assessment["route"]
    else:
        selected = str(route).strip().upper()
        if selected not in ("A", "B", "C", "D"):
            from .util import UsageError

            raise UsageError("--route 必须是 auto/A/B/C/D")
        gates, status_map = evaluate_gates(profile)
        auto_route = select_route(profile, status_map)
        if selected != auto_route:
            # 显式指定路线不禁止，但 plan 里记录偏离提示。
            pass

    if selected not in _ROUTE_STAGES:
        from .util import UsageError

        raise UsageError("--route 必须是 auto/A/B/C/D")

    stages: list[dict[str, Any]] = []
    route_stages = _ROUTE_STAGES[selected]
    by_id = {stage["id"]: stage for stage in route_stages}
    for stage_id in STAGE_IDS:
        if stage_id == "P0":
            stages.append(_COMMON_P0)
        elif stage_id == "P1":
            stages.append(_COMMON_P1)
        elif stage_id in by_id:
            stages.append(by_id[stage_id])
        elif stage_id == "P5":
            stages.append(_COMMON_P5)
        elif stage_id == "P6":
            stages.append(_COMMON_P6)

    warnings: list[str] = []
    if selected != select_route(profile, evaluate_gates(profile)[1]):
        warnings.append(
            f"显式指定路线 {selected} 与 assess 推荐路线不同：请确认评估门禁后仍选择该路线"
        )
    if get_nested(profile, "boot.bootloader_unlocked") is False and selected in ("B", "C", "D"):
        warnings.append(f"profile 显示 Bootloader 未解锁：路线 {selected} 缺少 G-B0 前提，计划不可执行")

    return {
        "schema": SCHEMA_PLAN,
        "generated_at": iso_now(),
        "route": selected,
        "route_label": ROUTE_LABELS[selected],
        "profile": {
            "schema": profile.get("schema"),
            "generated_at": profile.get("generated_at"),
            "source_mode": get_nested(profile, "source.mode", "unknown"),
            "unknowns": list(profile.get("unknowns") or []),
        },
        "warnings": warnings,
        "stages": stages,
    }


def format_plan_markdown(plan: dict[str, Any]) -> str:
    """渲染 markdown 计划。"""
    lines = [
        f"# 改造计划（路线 {plan['route']}）",
        "",
        f"- 路线说明：{plan['route_label']}",
        f"- profile source：{plan['profile'].get('source_mode', 'unknown')}",
        f"- 生成时间：{plan['generated_at']}",
        "- 本计划为生成物：阶段门禁未通过时不得进入下一阶段；未实测不得标记完成。",
        "",
    ]
    if plan.get("warnings"):
        lines.append("> 注意：")
        for warning in plan["warnings"]:
            lines.append(f"> - {warning}")
        lines.append("")
    for stage in plan["stages"]:
        lines.append(f"## {stage['id']} · {stage['title'].split('·', 1)[-1].strip()}")
        lines.append("")
        lines.append(f"**目标**：{stage['objective']}")
        lines.append("")
        lines.append("**动作**：")
        for action in stage["actions"]:
            lines.append(f"- {action}")
        lines.append("")
        lines.append("**交付物**：")
        for deliverable in stage["deliverables"]:
            lines.append(f"- {deliverable}")
        lines.append("")
        lines.append(f"**门禁**：{stage['gate']}")
        lines.append("")
        lines.append("**退出标准**：")
        for criterion in stage["exit_criteria"]:
            lines.append(f"- {criterion}")
        lines.append("")
        lines.append("**回滚**：")
        for step in stage["rollback"]:
            lines.append(f"- {step}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
