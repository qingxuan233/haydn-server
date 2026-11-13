"""rootcheck：离线检查 Root 实验设备的**技术姿态**（repurpose.rootcheck.v1）。

设计边界：
- 只消费 profile 中已有证据的字段，不连接设备、不写设备、不改变 assess 的路线/门禁顺序；
- 技术检查全 pass 只表示"技术姿态可进入人工复核"，**不代表授权/救援/演练已完成**；
- 人工项（授权、救援包、数据边界、固件冻结、演练、su/网络基线）单独列出，必须人工确认。

对应规范：[MTH-012](../../methodology/11-root-lab.md)、[GRD-015](../../guardrails/GRD-015-root-lab-controlled.md)。
"""

from __future__ import annotations

import re
from typing import Any

from .util import SCHEMA_ROOTCHECK, get_nested, iso_now

ROOT_MANAGERS = ("magisk", "kernelsu", "apatch")
"""可接受的 Root 管理器（与 assess 保持一致）。"""

ARB_SUFFIX_RE = re.compile(r"(?:[._]|^)(500|501|503)(?=$|[^0-9])")
"""已知 ARB 触发批次启发式：版本号里出现 .500/.501/.503（如 ColorOS 16.0.3.500）。"""

STATUSES = ("pass", "fail", "unknown")


def _check(
    check_id: str,
    name: str,
    status: str,
    reason: str,
    *,
    action: str = "",
    blocking: bool = True,
) -> dict[str, Any]:
    if status not in STATUSES:  # 防御式：内部只会传三态
        raise ValueError(f"非法 rootcheck 状态：{status}")
    return {
        "id": check_id,
        "name": name,
        "status": status,
        "blocking": blocking,
        "reason": reason,
        "action": action,
    }


def _as_bool(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None


def _as_text(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _root_state(profile: dict[str, Any]) -> str | None:
    state = _as_text(get_nested(profile, "root.state"))
    if state in ROOT_MANAGERS or state in ("none", "unknown"):
        return state
    return None


def _arb_suffix(profile: dict[str, Any]) -> str | None:
    """返回命中的 ARB 后缀（'' 表示未命中，None 表示无证据）。

    只做启发式匹配；最终以厂商公告/版本说明为准，不把"未命中"当成绝对安全。
    """
    raws = [
        _as_text(get_nested(profile, "identity.build_id")),
        _as_text(get_nested(profile, "identity.fingerprint")),
    ]
    present = [raw for raw in raws if raw]
    if not present:
        return None
    for raw in present:
        match = ARB_SUFFIX_RE.search(raw)
        if match:
            return f".{match.group(1)}"
    return ""


def _check_unlock(profile: dict[str, Any]) -> dict[str, Any]:
    unlocked = _as_bool(get_nested(profile, "boot.bootloader_unlocked"))
    policy = _as_text(get_nested(profile, "boot.oem_unlock_policy"))
    if unlocked is True:
        return _check(
            "RC-T01",
            "Bootloader 已解锁",
            "pass",
            "bootloader_unlocked=true（G-L4 的直接证据）",
        )
    if unlocked is False:
        detail = "，且 oem_unlock_policy=closed" if policy == "closed" else ""
        return _check(
            "RC-T01",
            "Bootloader 已解锁",
            "fail",
            f"bootloader 仍锁定{detail}：不能进入 Root 轨",
            action="先走 G-L4 官方解锁；不可用则换机或维持 A/A+，不要用付费/漏洞通道",
        )
    return _check(
        "RC-T01",
        "Bootloader 已解锁",
        "unknown",
        "bootloader 状态未采集/未证实",
        action="用 detect 只读采集，或现场核对开发者选项与 fastboot 状态",
    )


def _check_verified_boot(profile: dict[str, Any]) -> dict[str, Any]:
    unlocked = _as_bool(get_nested(profile, "boot.bootloader_unlocked"))
    state = _as_text(get_nested(profile, "boot.verified_boot_state"))
    if state is None:
        return _check(
            "RC-T02",
            "Verified Boot 状态一致",
            "unknown",
            "verified_boot_state 未采集",
            action="用 detect 只读采集 ro.boot.verifiedbootstate",
        )
    if state == "green":
        if unlocked is True:
            return _check(
                "RC-T02",
                "Verified Boot 状态一致",
                "fail",
                "已解锁却报告 green：解锁/完整性状态矛盾",
                action="重新核对 bootloader 与 AVB 状态；不要继续刷写",
            )
        return _check(
            "RC-T02",
            "Verified Boot 状态一致",
            "unknown",
            "green 只说明当前系统未改；解锁状态仍未证实",
            action="先确认 bootloader 状态，再判断是否满足 Root 轨前提",
        )
    if state in ("orange", "yellow"):
        return _check(
            "RC-T02",
            "Verified Boot 状态一致",
            "pass",
            f"verified_boot_state={state}（解锁后的预期状态）",
        )
    if state == "red":
        return _check(
            "RC-T02",
            "Verified Boot 状态一致",
            "fail",
            "verified_boot_state=red：启动校验失败",
            action="先按救援阶梯恢复原厂镜像，不继续 Root/刷写",
        )
    return _check(
        "RC-T02",
        "Verified Boot 状态一致",
        "unknown",
        f"未识别的 verified_boot_state={state}",
        action="核对 getprop ro.boot.verifiedbootstate 与解锁状态",
    )


def _check_verity(profile: dict[str, Any]) -> dict[str, Any]:
    mode = _as_text(get_nested(profile, "boot.dm_verity_mode"))
    if mode is None:
        return _check(
            "RC-T03",
            "dm-verity 未被关闭",
            "unknown",
            "dm_verity_mode 未采集",
            action="只读核对 ro.boot.veritymode；不得为 Root 关闭 verity",
        )
    lowered = mode.lower()
    if lowered in ("disabled", "off", "none"):
        return _check(
            "RC-T03",
            "dm-verity 未被关闭",
            "fail",
            f"dm_verity_mode={mode}：完整性校验被关闭（GRD-015 R4）",
            action="恢复原厂镜像/官方系统；不要用关闭 verity 换 Root",
        )
    if lowered in ("enforcing", "verified", "verifying"):
        return _check("RC-T03", "dm-verity 未被关闭", "pass", f"dm_verity_mode={mode}")
    return _check(
        "RC-T03",
        "dm-verity 未被关闭",
        "unknown",
        f"未识别的 dm_verity_mode={mode}",
        action="只读核对 ro.boot.veritymode",
    )


def _check_selinux(profile: dict[str, Any]) -> dict[str, Any]:
    value = _as_text(get_nested(profile, "boot.selinux"))
    if value is None:
        return _check(
            "RC-T04",
            "SELinux 为 Enforcing",
            "unknown",
            "selinux 字段未采集",
            action="只读核对 getprop ro.boot.selinux",
        )
    if value == "Enforcing":
        return _check("RC-T04", "SELinux 为 Enforcing", "pass", "SELinux=Enforcing")
    if value in ("Permissive", "Disabled"):
        return _check(
            "RC-T04",
            "SELinux 为 Enforcing",
            "fail",
            f"SELinux={value}：禁止全局放宽（GRD-015 R4）",
            action="恢复 Enforcing；只在明确的短时调试中使用 permissive，且不得作为常态",
        )
    return _check(
        "RC-T04",
        "SELinux 为 Enforcing",
        "unknown",
        f"未识别的 SELinux 状态={value}",
        action="只读核对 getprop ro.boot.selinux",
    )


def _check_root_manager(profile: dict[str, Any]) -> dict[str, Any]:
    state = _root_state(profile)
    su = _as_bool(get_nested(profile, "root.su_available"))
    if state in ROOT_MANAGERS:
        if su is True:
            return _check(
                "RC-T05",
                "Root 管理器与 su 可用",
                "pass",
                f"root.state={state} 且 su_available=true",
            )
        if su is False:
            return _check(
                "RC-T05",
                "Root 管理器与 su 可用",
                "fail",
                f"root.state={state} 但 su_available=false：Root 不可用",
                action="按官方安装文档重装/排查管理器；失败则恢复原厂 boot",
            )
        return _check(
            "RC-T05",
            "Root 管理器与 su 可用",
            "unknown",
            f"root.state={state}，su_available 未证实",
            action="用 Root 管理器自检/`su -c id` 只读验证",
        )
    if state == "none":
        return _check(
            "RC-T05",
            "Root 管理器与 su 可用",
            "fail",
            "root.state=none：当前没有 Root",
            action="先过 G-L4/G-L5，再按官方方案安装 KernelSU LKM 或 APatch",
        )
    return _check(
        "RC-T05",
        "Root 管理器与 su 可用",
        "unknown",
        "root.state 未采集/未识别",
        action="用 detect 只读采集 Root 管理器与 su 状态",
    )


def _check_manager_uniqueness(profile: dict[str, Any]) -> dict[str, Any]:
    packages = get_nested(profile, "root.root_manager_packages")
    if not isinstance(packages, list):
        return _check(
            "RC-T06",
            "Root 管理器唯一",
            "unknown",
            "root_manager_packages 未采集",
            action="只读核对 `pm list packages`，确认没有多套管理器共存",
        )
    valid = [item for item in packages if isinstance(item, str) and item.strip()]
    if len(valid) > 1:
        return _check(
            "RC-T06",
            "Root 管理器唯一",
            "fail",
            "检测到多个 Root 管理器：" + "、".join(valid[:5]),
            action="只保留一个管理器；先回退到原厂 boot，再重装单一方案",
        )
    if len(valid) == 1:
        return _check("RC-T06", "Root 管理器唯一", "pass", f"检测到管理器：{valid[0]}")
    return _check(
        "RC-T06",
        "Root 管理器唯一",
        "unknown",
        "root_manager_packages 为空或未采集",
        action="只读核对管理器包名；若 root.state 有值但包名为空，记录为待验证",
    )


def _check_kernel_compat(profile: dict[str, Any]) -> dict[str, Any]:
    state = _root_state(profile)
    if state == "kernelsu":
        gki = _as_text(get_nested(profile, "kernel.gki_generation"))
        if gki == "gki-2.x":
            return _check(
                "RC-T07",
                "KernelSU/GKI 匹配",
                "pass",
                "gki_generation=gki-2.x（KernelSU LKM 前提）",
            )
        if gki in ("gki-1.x", "legacy"):
            return _check(
                "RC-T07",
                "KernelSU/GKI 匹配",
                "fail",
                f"gki_generation={gki}：不满足 KernelSU LKM 前提",
                action="改用 APatch/Magisk 或自编译内核方案；不要强装 KernelSU",
            )
        return _check(
            "RC-T07",
            "KernelSU/GKI 匹配",
            "unknown",
            "gki_generation 未证实",
            action="只读核对内核版本/KMI，再决定 KernelSU LKM 是否可用",
        )
    if state == "apatch":
        kallsyms = _as_bool(get_nested(profile, "features.kallsyms"))
        if kallsyms is True:
            return _check("RC-T07", "APatch/KALLSYMS 匹配", "pass", "kallsyms=true（APatch 前提）")
        if kallsyms is False:
            return _check(
                "RC-T07",
                "APatch/KALLSYMS 匹配",
                "fail",
                "kallsyms=false：APatch 不可用",
                action="改用 KernelSU/Magisk 或自编译内核方案",
            )
        return _check(
            "RC-T07",
            "APatch/KALLSYMS 匹配",
            "unknown",
            "features.kallsyms 未证实（通常需 root 读 /proc/config.gz）",
            action="在已 Root 环境只读核对 CONFIG_KALLSYMS；不要臆测",
        )
    if state == "magisk":
        return _check(
            "RC-T07",
            "Root 方案与内核匹配",
            "pass",
            "root.state=magisk：不依赖 GKI/KALLSYMS 检查",
        )
    return _check(
        "RC-T07",
        "Root 方案与内核匹配",
        "unknown",
        "尚未确定 Root 管理器，无法核对内核前提",
        action="先按 MTH-012 §4 选型（优先 KernelSU LKM），再补证据",
    )


def _check_partition(profile: dict[str, Any]) -> dict[str, Any]:
    style = _as_text(get_nested(profile, "boot.partition_style"))
    has_init_boot = _as_bool(get_nested(profile, "boot.has_init_boot"))
    if style in ("A/B", "A-only") and has_init_boot is not None:
        target = "init_boot" if has_init_boot else "boot"
        return _check(
            "RC-T08",
            "分区布局已知（补丁目标可判定）",
            "pass",
            f"partition_style={style}，has_init_boot={str(has_init_boot).lower()} → 补丁目标 {target}",
        )
    return _check(
        "RC-T08",
        "分区布局已知（补丁目标可判定）",
        "unknown",
        "分区布局/init_boot 未证实：无法确定补丁 boot 还是 init_boot",
        action="从匹配版本全量包解包/只读核对分区布局；G-L5 前必须确定",
    )


def _check_arb(profile: dict[str, Any]) -> dict[str, Any]:
    suffix = _arb_suffix(profile)
    if suffix is None:
        return _check(
            "RC-T09",
            "ARB 禁止批次检查",
            "unknown",
            "build_id/fingerprint 未采集：无法检查 ARB 禁止清单",
            action="记录 build 指纹与安全补丁；核对厂商公告/社区熔断报告",
        )
    if suffix:
        return _check(
            "RC-T09",
            "ARB 禁止批次检查",
            "fail",
            f"build 命中已知 ARB 批次（{suffix}）：禁止降级/刷旧镜像",
            action="保持当前构建、冻结更新；按 PIT-023 与厂商公告核对，不尝试旧包/EDL",
        )
    return _check(
        "RC-T09",
        "ARB 禁止批次检查",
        "pass",
        "启发式未命中已知 ARB 批次（.500/.501/.503）；仍需核对厂商公告",
    )


MANUAL_CHECKS = [
    {
        "id": "RC-M01",
        "name": "授权记录",
        "required": True,
        "reason": "GRD-015 R1：设备型号/授权范围/风险确认/日期，写入案例或运行期记录",
        "action": "补齐授权记录后再执行任何解锁/Root 动作",
    },
    {
        "id": "RC-M02",
        "name": "救援包与哈希",
        "required": True,
        "reason": "G-L1：匹配版本 boot/init_boot、完整 OFP、SHA-256、两条线、第二台电脑",
        "action": "逐项核对救援包；缺一项不得解锁",
    },
    {
        "id": "RC-M03",
        "name": "数据与生产边界",
        "required": True,
        "reason": "GRD-015 R2：实验机无个人账号/唯一副本/生产服务；生产数据已在 haydn",
        "action": "确认实验机无个人数据；割接前不承载生产服务",
    },
    {
        "id": "RC-M04",
        "name": "固件冻结与 OTA",
        "required": True,
        "reason": "G-L3/GRD-014：自动更新已关闭、版本/补丁已记录、无待装禁止清单构建",
        "action": "关闭自动更新并记录 build；命中 .500/.501/.503 禁止清单不得安装",
    },
    {
        "id": "RC-M05",
        "name": "救援演练记录",
        "required": True,
        "reason": "MTH-008 G-R3：至少 3 轮可恢复故障 → 恢复 → 服务复验",
        "action": "补齐 3 轮演练记录；未演练不得进入生产割接",
    },
    {
        "id": "RC-M06",
        "name": "su 与网络基线",
        "required": True,
        "reason": "MTH-012 §8.1/GRD-015 R7：su 白名单+审计、无公网 root shell/ADB、规则可回滚",
        "action": "按 G-L6 收紧 su/ADB/网络规则并留审计",
    },
    {
        "id": "RC-M07",
        "name": "管理器来源与哈希",
        "required": True,
        "reason": "GRD-015 R7/PIT-024：只用官方发布物，记录版本与 SHA-256",
        "action": "记录管理器/镜像来源、版本与哈希；不使用闭源一键工具作为唯一路径",
    },
]
"""人工确认项：rootcheck 不会替用户签授权/演练；未确认不得进入生产。"""


def build_rootcheck(profile: dict[str, Any]) -> dict[str, Any]:
    """根据 profile 生成 ``repurpose.rootcheck.v1`` 报告。"""
    checks = [
        _check_unlock(profile),
        _check_verified_boot(profile),
        _check_verity(profile),
        _check_selinux(profile),
        _check_root_manager(profile),
        _check_manager_uniqueness(profile),
        _check_kernel_compat(profile),
        _check_partition(profile),
        _check_arb(profile),
    ]
    fails = [item["id"] for item in checks if item["status"] == "fail" and item["blocking"]]
    unknowns = [item["id"] for item in checks if item["status"] == "unknown" and item["blocking"]]
    tech_ready = not fails and not unknowns
    verdict = "tech-ready" if tech_ready else ("blocked" if fails else "insufficient-evidence")
    next_steps = [f"{item['id']}：{item['action']}" for item in checks if item["status"] != "pass" and item["action"]]
    next_steps.extend(f"{item['id']}：{item['action']}" for item in MANUAL_CHECKS)
    if tech_ready:
        next_steps.append("技术姿态通过：按 GRD-015 完成人工确认后再进入 G-L6/验收")

    source = profile.get("source") if isinstance(profile.get("source"), dict) else {}
    summary = {
        "pass": sum(1 for item in checks if item["status"] == "pass"),
        "fail": len(fails),
        "unknown": len(unknowns),
        "total": len(checks),
        "manual": len(MANUAL_CHECKS),
    }
    return {
        "schema": SCHEMA_ROOTCHECK,
        "generated_at": iso_now(),
        "profile": {
            "schema": profile.get("schema"),
            "generated_at": profile.get("generated_at"),
            "source_mode": source.get("mode", "unknown"),
        },
        "verdict": verdict,
        "tech_ready": tech_ready,
        "manual_review_required": True,
        "summary": summary,
        "checks": checks,
        "manual_checks": [dict(item) for item in MANUAL_CHECKS],
        "blocking_failures": fails,
        "blocking_unknowns": unknowns,
        "next_steps": next_steps,
    }


def format_rootcheck_human(report: dict[str, Any]) -> str:
    """人类摘要（不打印设备序列号等敏感值）。"""
    lines = [
        f"Root 实验姿态：{report['verdict']}（tech_ready={str(report['tech_ready']).lower()}）",
        f"profile source：{report['profile'].get('source_mode', 'unknown')}",
        "",
        "技术检查：",
    ]
    for item in report["checks"]:
        lines.append(f"  [{item['status']:7s}] {item['id']} {item['name']} - {item['reason']}")
    summary = report["summary"]
    lines.extend(
        [
            "",
            f"技术汇总：pass={summary['pass']} fail={summary['fail']} unknown={summary['unknown']} "
            f"（共 {summary['total']} 项）",
            "",
            "人工确认（必须，rootcheck 不能替代）：",
        ]
    )
    for item in report["manual_checks"]:
        lines.append(f"  - {item['id']} {item['name']}：{item['reason']}")
    lines.extend(["", "下一步："])
    for step in report["next_steps"]:
        lines.append(f"  - {step}")
    return "\n".join(lines)
