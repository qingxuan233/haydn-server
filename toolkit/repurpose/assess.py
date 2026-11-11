"""离线路线评估：A/B/C/D 与门禁（G-A / G-B0 / G-B1 / G-B2 / G-C / G-D / G-RISK）。

设计原则：
- 只根据 profile 中**有证据**的字段判定；未知字段不臆测；
- 未知项进入 assumptions/unknowns 并下调 confidence；
- 输出 ``repurpose.assessment.v1``，字段稳定，供 Agent/文档/CI 消费。
"""

from __future__ import annotations

from typing import Any

from .profile import CAPABILITY_IDS
from .util import SCHEMA_ASSESSMENT, get_nested, iso_now

ROUTE_LABELS = {
    "A": "A · 无 Root（Termux + proot，含 A+ 优化）",
    "B": "B · 已解锁：Root + chroot/容器",
    "C": "C · 自定义内核/第三方 ROM（研究性）",
    "D": "D · 原生 Linux 移植（仅移植存在时）",
}
"""路线展示名；route 字段本身严格为 A/B/C/D。"""

ROOT_MANAGERS = ("magisk", "kernelsu", "apatch")

UNLOCK_CLOSED_POLICIES = ("closed",)
UNLOCK_OPEN_POLICIES = ("open", "available")

ROUTE_BLOCKED_BY_UNLOCK = (
    "B/C/D 路线不可用：Bootloader 未解锁或 OEM 官方解锁通道关闭（G-B0）"
)


def _bool_value(profile: dict[str, Any], path: str) -> bool | None:
    value = get_nested(profile, path)
    return value if isinstance(value, bool) else None


def _gate(gate_id: str, name: str, status: str, reason: str) -> dict[str, str]:
    return {"id": gate_id, "name": name, "status": status, "reason": reason}


def _root_state(profile: dict[str, Any]) -> str | None:
    state = get_nested(profile, "root.state")
    if isinstance(state, str):
        return state
    return None


def _su_available(profile: dict[str, Any]) -> bool | None:
    value = get_nested(profile, "root.su_available")
    return value if isinstance(value, bool) else None


def evaluate_gates(profile: dict[str, Any]) -> tuple[list[dict[str, str]], dict[str, str]]:
    """计算全部门禁，返回 ``(gates, gate_status_map)``。"""
    gates: list[dict[str, str]] = []

    arch = get_nested(profile, "kernel.arch")
    arch_supported = arch in ("aarch64", "arm64-v8a", "arm64", "armeabi-v7a", "x86_64", "x86")
    ptrace_allowed = _bool_value(profile, "features.ptrace_allowed")
    proot_capability = (profile.get("capabilities") or {}).get("proot") if isinstance(
        profile.get("capabilities"), dict
    ) else None
    proot_status = proot_capability.get("status") if isinstance(proot_capability, dict) else None

    if proot_status in ("pass", "fail", "unknown"):
        gates.append(
            _gate(
                "G-A",
                "无根路线（Termux + proot）可用性",
                proot_status,
                "probe 对 proot 能力的判定（用户态 ptrace 方案，不依赖 namespace/root）",
            )
        )
    elif ptrace_allowed is False:
        gates.append(
            _gate("G-A", "无根路线（Termux + proot）可用性", "fail", "ptrace 受限，proot 可能不可用")
        )
    elif arch_supported:
        gates.append(
            _gate(
                "G-A",
                "无根路线（Termux + proot）可用性",
                "pass",
                f"CPU 架构 {arch} 可运行 Termux/proot；无需 Root 与 namespace",
            )
        )
    else:
        gates.append(
            _gate("G-A", "无根路线（Termux + proot）可用性", "unknown", "CPU 架构未知，无法确认 proot 可运行")
        )

    unlock = _bool_value(profile, "boot.bootloader_unlocked")
    policy = get_nested(profile, "boot.oem_unlock_policy")
    policy = policy if isinstance(policy, str) else "unknown"
    if unlock is False or policy in UNLOCK_CLOSED_POLICIES:
        reasons = []
        if unlock is False:
            reasons.append("当前 Bootloader 仍为锁定")
        if policy in UNLOCK_CLOSED_POLICIES:
            reasons.append("OEM 官方解锁通道关闭")
        gates.append(_gate("G-B0", "解锁前置（B/C/D 硬门禁）", "fail", "；".join(reasons)))
    elif unlock is True and policy not in UNLOCK_CLOSED_POLICIES:
        gates.append(_gate("G-B0", "解锁前置（B/C/D 硬门禁）", "pass", "Bootloader 已解锁，可进入 Root/刷机路线"))
    else:
        gates.append(
            _gate(
                "G-B0",
                "解锁前置（B/C/D 硬门禁）",
                "unknown",
                "解锁状态或厂商解锁政策未证实（不臆测已解锁）",
            )
        )

    root_state = _root_state(profile)
    su_available = _su_available(profile)
    if root_state in ROOT_MANAGERS or su_available is True:
        manager = root_state if root_state in ROOT_MANAGERS else "su"
        gates.append(_gate("G-B1", "Root 管理器可用性（Magisk/KernelSU/APatch）", "pass", f"检测到 Root 管理器：{manager}"))
    elif root_state == "none":
        gates.append(_gate("G-B1", "Root 管理器可用性（Magisk/KernelSU/APatch）", "fail", "未检测到 Root 管理器，当前无 Root"))
    else:
        gates.append(
            _gate(
                "G-B1",
                "Root 管理器可用性（Magisk/KernelSU/APatch）",
                "unknown",
                "Root 状态未证实（不臆测已 Root）",
            )
        )

    user_ns = _bool_value(profile, "features.user_ns")
    pid_ns = _bool_value(profile, "features.pid_ns")
    cgroup_delegation = _bool_value(profile, "features.cgroup_v2_delegation")
    ns_values = (user_ns, pid_ns, cgroup_delegation)
    if all(value is True for value in ns_values):
        gates.append(_gate("G-B2", "容器运行时前提（user_ns + pid_ns + cgroup 委派）", "pass", "三项前提均为 true"))
    elif any(value is False for value in ns_values):
        missing = []
        if user_ns is False:
            missing.append("user_ns")
        if pid_ns is False:
            missing.append("pid_ns")
        if cgroup_delegation is False:
            missing.append("cgroup v2 委派")
        gates.append(
            _gate(
                "G-B2",
                "容器运行时前提（user_ns + pid_ns + cgroup 委派）",
                "fail",
                "缺少 " + " / ".join(missing),
            )
        )
    else:
        gates.append(
            _gate(
                "G-B2",
                "容器运行时前提（user_ns + pid_ns + cgroup 委派）",
                "unknown",
                "命名空间或 cgroup 委派未证实，容器可行性未知",
            )
        )

    custom_kernel = _bool_value(profile, "features.custom_kernel")
    b0_status = gates[1]["status"]
    if custom_kernel is True and b0_status == "pass":
        gates.append(_gate("G-C", "自定义内核/第三方 ROM 可行性", "pass", "存在自定义内核/ROM 证据且已解锁"))
    elif custom_kernel is False:
        gates.append(_gate("G-C", "自定义内核/第三方 ROM 可行性", "fail", "无社区内核/第三方 ROM 证据"))
    elif b0_status == "fail":
        gates.append(_gate("G-C", "自定义内核/第三方 ROM 可行性", "fail", "解锁前置不满足，C 路线不可用"))
    else:
        gates.append(_gate("G-C", "自定义内核/第三方 ROM 可行性", "unknown", "缺少社区内核/ROM 支持证据"))

    native_port = _bool_value(profile, "features.native_linux_port")
    if native_port is True and b0_status == "pass":
        gates.append(_gate("G-D", "原生 Linux 移植是否存在", "pass", "存在设备移植证据且已解锁"))
    elif native_port is False:
        gates.append(_gate("G-D", "原生 Linux 移植是否存在", "fail", "无设备移植证据（无端口）"))
    elif b0_status == "fail":
        gates.append(_gate("G-D", "原生 Linux 移植是否存在", "fail", "解锁前置不满足，D 路线不可用"))
    else:
        gates.append(_gate("G-D", "原生 Linux 移植是否存在", "unknown", "移植支持情况未证实"))

    integrity_required = get_nested(profile, "crypto.play_integrity_required")
    if integrity_required is True:
        gates.append(
            _gate(
                "G-RISK",
                "Play Integrity / Root 兼容性（软门禁）",
                "unknown",
                "用户声明需要 Play Integrity；Root/解锁路线需接受完整性校验风险，不改变路线选择",
            )
        )
    elif integrity_required is False:
        gates.append(_gate("G-RISK", "Play Integrity / Root 兼容性（软门禁）", "pass", "未要求 Play Integrity"))
    else:
        gates.append(
            _gate("G-RISK", "Play Integrity / Root 兼容性（软门禁）", "unknown", "Play Integrity 要求未声明")
        )

    status_map = {gate["id"]: gate["status"] for gate in gates}
    return gates, status_map


def select_route(profile: dict[str, Any], status_map: dict[str, str]) -> str:
    """按门禁与证据选择推荐路线（严格 A/B/C/D）。"""
    b0 = status_map.get("G-B0", "unknown")
    if b0 != "pass":
        # 未解锁/未证实：B/C/D 都不可执行，最保守地选择无根路线 A。
        return "A"
    native_port = _bool_value(profile, "features.native_linux_port")
    custom_kernel = _bool_value(profile, "features.custom_kernel")
    root_state = _root_state(profile)
    su_available = _su_available(profile)
    root_possible = root_state in ROOT_MANAGERS or su_available is True
    containers_possible = status_map.get("G-B2") == "pass"

    if native_port is True:
        return "D"
    if root_possible or containers_possible:
        return "B"
    if custom_kernel is True:
        return "C"
    # 已解锁但证据不足：默认 B（能力上限最高），置信度会因 unknown 下调。
    return "B"


def _collect_blocked(profile: dict[str, Any], status_map: dict[str, str], route: str) -> list[str]:
    blocked: list[str] = []
    if status_map.get("G-B0") == "fail":
        blocked.append(ROUTE_BLOCKED_BY_UNLOCK)
    if status_map.get("G-B2") != "pass":
        detail = "无法证明 user_ns/pid_ns/cgroup 委派同时可用"
        blocked.append(f"容器运行时：{detail}（G-B2，{status_map.get('G-B2', 'unknown')}）")
    if status_map.get("G-D") == "fail" and route != "D":
        blocked.append("D 原生 Linux：无设备移植证据（G-D fail）")
    if status_map.get("G-C") == "fail" and route != "C":
        blocked.append("C 自定义内核/ROM：解锁前置或社区支持不满足（G-C fail）")
    if status_map.get("G-B1") == "fail" and route in ("B", "C", "D"):
        blocked.append("G-B1：未检测到 Root 管理器，Root 路线无法直接执行")
    if status_map.get("G-A") == "fail":
        blocked.append("G-A：无根路线（proot）不可用，需改用已解锁设备的 B 路线")
    return blocked


def _collect_alternatives(profile: dict[str, Any], status_map: dict[str, str], route: str) -> list[str]:
    alternatives: list[str] = []
    if route != "A":
        alternatives.append("A：Termux + proot（无 Root 降级方案，能力受限但上线最快）")
    if route != "B" and status_map.get("G-B0") == "pass":
        alternatives.append("B：解锁后 Root + chroot（能力上限较高，需承担解锁/变砖风险）")
    if route != "C" and status_map.get("G-B0") == "pass" and status_map.get("G-C") == "pass":
        alternatives.append("C：自定义内核/第三方 ROM（研究路线，风险最高）")
    if route != "D" and status_map.get("G-D") == "pass":
        alternatives.append("D：原生 Linux 移植（能力最完整但依赖设备移植质量）")
    if not alternatives:
        alternatives.append("A：无 Root Termux + proot（当前唯一可执行路线）")
    if status_map.get("G-B0") == "unknown":
        alternatives.append("解锁状态未证实：如后续确认已解锁，可重跑 assess 比较 B/C/D")
    return alternatives


def _collect_risks(profile: dict[str, Any], route: str, status_map: dict[str, str]) -> list[str]:
    risks: list[str] = [
        "宿主长期插电：电池满电 + 高温会加速老化，需限充/旁路供电与散热",
    ]
    if get_nested(profile, "constraints.external_storage") == "none":
        risks.append("无 MicroSD/外接存储扩展，数据增长受内置存储限制，需规划备份与轮转")
    if get_nested(profile, "constraints.oem_autostart") == "manual-required":
        risks.append("OEM 自启动需人工白名单，重启后服务可能不自动恢复")
    if get_nested(profile, "constraints.background_execution") == "restricted":
        risks.append("OEM 后台限制可能清理 Termux/服务进程，需电池白名单与 wake-lock")
    if get_nested(profile, "crypto.play_integrity_required") is True:
        risks.append("已声明需要 Play Integrity：Root/解锁会破坏完整性校验，影响银行/支付类 App")
    if status_map.get("G-B2") == "fail":
        risks.append("容器不可用：服务需用 proot/chroot + supervisord/s6/runit 管理，不能依赖 Docker")
    if route == "A":
        risks.append("无 Root 硬边界：全局 /proc/stat、/proc/net/dev、dumpsys/appops、限充 sysfs 可能不可得")
    elif route == "B":
        risks.extend(
            [
                "解锁 Bootloader 必然抹除用户数据，且破坏 AVB/OTA 链",
                "Root 与刷机会引入 bootloop/变砖风险，必须有原厂镜像与救援链路",
                "Root 扩大攻击面：Bridge/控制面需最小权限、token 隔离与审计",
            ]
        )
    elif route == "C":
        risks.extend(
            [
                "自编译内核/第三方 ROM 风险最高：可能变砖、无 OTA、社区支持不确定",
                "修改内核/系统分区会触发 dm-verity 与 Play Integrity 问题",
            ]
        )
    elif route == "D":
        risks.extend(
            [
                "原生 Linux 移植通常 modem/相机/热管理不完善，不适合作为长期服务器",
                "无官方/社区移植时不可行；即便有移植，驱动稳定性仍需长跑验证",
            ]
        )
    return risks


def _collect_next_steps(profile: dict[str, Any], route: str, unknowns: list[str]) -> list[str]:
    steps: list[str] = []
    if unknowns:
        steps.append("先补齐 unknowns 中字段的证据（重跑 probe / 人工核对），再重跑 assess")
    if route == "A":
        steps.extend(
            [
                "改造前完成设备数据与关键配置备份，记录基线快照",
                "安装 Termux + Termux:Boot，按 OEM profile 配置自启动与电池优化白名单",
                "proot-distro 安装 Ubuntu，服务用 supervisord/s6/runit 管理（不要依赖 systemd）",
                "执行 5 次重启验证与 24h soak 观察（toolkit/termux/soak.sh）",
            ]
        )
    elif route == "B":
        steps.extend(
            [
                "先做 G-B0 解锁可行性验证；解锁前全量备份（解锁会抹除数据）",
                "选 Magisk/KernelSU/APatch 之一，保留原厂 boot.img 并验证可正常开机",
                "root + chroot 绑定 /proc /sys /dev，服务用 s6/supervisord（systemd 仅在 cgroup 委派可用时尝试）",
                "按需验证容器（G-B2）；不满足则退回 chroot 方案，不硬刚",
                "执行 5 次重启验证与 24h soak，并检查 Play Integrity 影响",
            ]
        )
    elif route == "C":
        steps.extend(
            [
                "先确认目标机型有可复现的自定义内核/第三方 ROM 与救砖链路",
                "下载并保留原厂完整固件与 boot.img，逐项变更、每次变更后验证开机",
                "只读验证内核特性（namespace/cgroup/overlay）达标后再决定是否刷入",
                "刷入后执行 5 次重启与 24h soak；记录 OTA/保修/完整性影响",
            ]
        )
    elif route == "D":
        steps.extend(
            [
                "确认是否存在 mainline/postmarketOS(Nura)/Ubuntu Touch 等设备移植",
                "若无移植或无维护者，放弃 D，回到 A/B 路线",
                "若有移植：先验证 Wi-Fi/充电/热管理/存储可用性，再做长跑测试",
                "保留原厂固件与恢复链路，记录与 A/B 路线的能力差异",
            ]
        )
    steps.append("按 plan 输出的 P0–P6 阶段执行；每阶段结束前通过 exit_criteria 再进入下一阶段")
    return steps


def _collect_assumptions(
    profile: dict[str, Any], status_map: dict[str, str], unknowns: list[str]
) -> list[str]:
    assumptions: list[str] = []
    for item in unknowns[:12]:
        assumptions.append(f"未证实：{item}（按 unknown 处理，不臆测）")
    if status_map.get("G-B0") == "unknown":
        assumptions.append("解锁状态/厂商政策未证实，按最保守的 A 路线规划")
    if get_nested(profile, "crypto.play_integrity_required") is None:
        assumptions.append("未声明 Play Integrity 要求，评估未计入该约束")
    if get_nested(profile, "constraints.oem_autostart") in (None, "unknown"):
        assumptions.append("OEM 自启动策略未证实，需在换机验收中做 5 次重启实测")
    if not profile.get("capabilities"):
        assumptions.append("尚未运行 probe：capabilities 为空，能力判断仅来自 features 字段")
    assumptions.append("confidence 为启发式指标（证据完整度），不是成功概率")
    return assumptions


def _compute_confidence(
    profile: dict[str, Any], route: str, status_map: dict[str, str], unknowns: list[str]
) -> float:
    score = 0.55
    unlock = _bool_value(profile, "boot.bootloader_unlocked")
    policy = get_nested(profile, "boot.oem_unlock_policy")
    if unlock is not None and policy not in (None, "unknown"):
        score += 0.15
    elif unlock is not None or policy not in (None, "unknown"):
        score += 0.07
    identity = profile.get("identity") if isinstance(profile.get("identity"), dict) else {}
    if identity.get("codename") and identity.get("android_version"):
        score += 0.08
    if profile.get("evidence_refs"):
        score += 0.05
    decisive = {
        "A": status_map.get("G-A") in ("pass", "fail"),
        "B": _root_state(profile) is not None and status_map.get("G-B2") in ("pass", "fail"),
        "C": status_map.get("G-C") in ("pass", "fail"),
        "D": status_map.get("G-D") in ("pass", "fail"),
    }
    if decisive.get(route):
        score += 0.10
    else:
        score -= 0.05
    score -= 0.04 * min(len(unknowns), 5)
    return round(max(0.10, min(0.95, score)), 2)


def _route_hint(route: str) -> str:
    return route


def assess_profile(profile: dict[str, Any]) -> dict[str, Any]:
    """对 profile 做离线评估，返回 ``repurpose.assessment.v1`` 对象。"""
    gates, status_map = evaluate_gates(profile)
    route = select_route(profile, status_map)
    unknowns = [item for item in profile.get("unknowns", []) if isinstance(item, str)]
    for path in (
        "boot.bootloader_unlocked",
        "boot.oem_unlock_policy",
        "root.state",
        "features.user_ns",
        "features.pid_ns",
        "features.cgroup_v2_delegation",
        "features.native_linux_port",
        "features.custom_kernel",
        "crypto.play_integrity_required",
    ):
        if get_nested(profile, path) is None and path not in unknowns:
            unknowns.append(path)

    capabilities = profile.get("capabilities") if isinstance(profile.get("capabilities"), dict) else {}
    filled = [capability_id for capability_id in CAPABILITY_IDS if capability_id in capabilities]

    source = profile.get("source") if isinstance(profile.get("source"), dict) else {}
    assessment = {
        "schema": SCHEMA_ASSESSMENT,
        "generated_at": iso_now(),
        "profile": {
            "schema": profile.get("schema"),
            "generated_at": profile.get("generated_at"),
            "source_mode": source.get("mode", "unknown"),
            "capabilities_present": len(filled),
        },
        "route": route,
        "route_hint": _route_hint(route),
        "route_label": ROUTE_LABELS[route],
        "confidence": _compute_confidence(profile, route, status_map, unknowns),
        "gates": gates,
        "blocked": _collect_blocked(profile, status_map, route),
        "alternatives": _collect_alternatives(profile, status_map, route),
        "risks": _collect_risks(profile, route, status_map),
        "next_steps": _collect_next_steps(profile, route, unknowns),
        "assumptions": _collect_assumptions(profile, status_map, unknowns),
        "unknowns": sorted(set(unknowns)),
    }
    if route in ("B", "C", "D") and get_nested(profile, "crypto.play_integrity_required") is True:
        assessment["risks"].insert(
            0,
            "已声明需要 Play Integrity：所选路线需要解锁/刷机/Root，完整性校验与相关 App 可能不可用",
        )
    return assessment


def format_assessment_human(assessment: dict[str, Any]) -> str:
    """人类摘要（不打印设备序列号等敏感值）。"""
    lines = [
        f"路线：{assessment['route']}（{assessment['route_label']}）",
        f"置信度：{assessment['confidence']}",
        "",
        "门禁：",
    ]
    for gate in assessment["gates"]:
        lines.append(f"  [{gate['status']:7s}] {gate['id']} {gate['name']} - {gate['reason']}")
    sections = (
        ("阻塞（blocked）", assessment["blocked"]),
        ("备选（alternatives）", assessment["alternatives"]),
        ("风险（risks）", assessment["risks"]),
        ("下一步（next_steps）", assessment["next_steps"]),
        ("假设（assumptions）", assessment["assumptions"]),
        ("未知（unknowns）", assessment["unknowns"]),
    )
    for title, items in sections:
        lines.append("")
        lines.append(f"{title}：")
        if items:
            for item in items:
                lines.append(f"  - {item}")
        else:
            lines.append("  - （无）")
    return "\n".join(lines)
