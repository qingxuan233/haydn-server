"""probe：在 device-profile 上补齐 12 项 capabilities 与 verdicts。

命令全部只读（``test -r`` / ``test -w`` 只判断权限，不写设备；``unshare`` 只做
进程级临时实验，不修改系统；``dumpsys``/``cat`` 只读）。无 transport 且提供
``--base`` 时进入离线模式：只依据 profile 已有证据推断，状态可为 unknown。
"""

from __future__ import annotations

import copy
import re
from typing import Any

from .detect import parse_getprop, parse_namespaces
from .profile import CAPABILITY_IDS
from .util import get_nested, iso_now

PROBE_COMMANDS = (
    "ls -l /proc/self/ns",
    "cat /proc/self/cgroup",
    "ls /sys/fs/cgroup",
    "cat /sys/fs/cgroup/cgroup.controllers",
    "unshare -U true; echo rc=$?",
    "unshare -m true; echo rc=$?",
    "cat /proc/stat",
    "cat /proc/net/dev",
    "dumpsys battery",
    "dumpsys usagestats | head -n 4",
    "cmd appops get android GET_USAGE_STATS",
    "pm list packages com.termux",
    "test -r /sys/class/power_supply/battery/charge_control_limit && echo readable || echo missing_or_denied",
    "test -w /sys/class/power_supply/battery/charge_control_limit && echo writable || echo readonly",
    "ls /sys/class/power_supply/battery",
    "pm list features",
)
"""probe 的只读补充命令清单。"""


def _status(status: str, evidence: str) -> dict[str, str]:
    return {"status": status, "evidence": evidence}


def _bool_or_none(profile: dict[str, Any], path: str) -> bool | None:
    value = get_nested(profile, path)
    return value if isinstance(value, bool) else None


def _rc_of(output: str) -> int | None:
    match = re.search(r"rc=(\d+)", output)
    return int(match.group(1)) if match else None


def _has_numbers_after_cpu(text: str) -> bool:
    for line in text.splitlines():
        if not line.startswith("cpu "):
            continue
        parts = line.split()[1:]
        numbers = []
        for token in parts:
            try:
                numbers.append(int(token))
            except ValueError:
                return False
        return bool(numbers) and sum(numbers) > 0
    return False


def run_probe_commands(transport: Any, serial: str | None) -> dict[str, str]:
    """执行 probe 补充命令，返回 command -> 原始输出。"""
    outputs: dict[str, str] = {}
    for command in PROBE_COMMANDS:
        try:
            outputs[command] = transport.shell(command, serial)
        except Exception:
            outputs[command] = ""
    return outputs


def _apply_runtime_namespaces(profile: dict[str, Any], outputs: dict[str, str]) -> None:
    text = outputs.get("ls -l /proc/self/ns", "")
    names = parse_namespaces(text)
    if not names:
        return
    features = profile.setdefault("features", {})
    mapping = {
        "user_ns": "user",
        "pid_ns": "pid",
        "mount_ns": "mnt",
        "net_ns": "net",
        "uts_ns": "uts",
        "ipc_ns": "ipc",
    }
    for key, name in mapping.items():
        if features.get(key) is None:
            features[key] = name in names


def _apply_runtime_cgroup(profile: dict[str, Any], outputs: dict[str, str]) -> None:
    listing = outputs.get("ls /sys/fs/cgroup", "")
    controllers = outputs.get("cat /sys/fs/cgroup/cgroup.controllers", "").strip()
    mounts = outputs.get("cat /proc/self/cgroup", "")
    features = profile.setdefault("features", {})
    if "cgroup.controllers" in listing:
        if features.get("cgroup_v2") is None:
            features["cgroup_v2"] = True
        if features.get("cgroup_v2_delegation") is None:
            features["cgroup_v2_delegation"] = bool(controllers)
    if mounts.strip() and features.get("cgroup_v1") is None and re.search(r"^\d+:", mounts, re.MULTILINE):
        features["cgroup_v1"] = True


def _proot(profile: dict[str, Any], outputs: dict[str, str]) -> dict[str, str]:
    arch = get_nested(profile, "kernel.arch")
    ptrace = _bool_or_none(profile, "features.ptrace_allowed")
    if ptrace is False:
        return _status("fail", "ptrace 受限（features.ptrace_allowed=false），proot 可能无法工作")
    if arch in ("aarch64", "arm64", "arm64-v8a", "armeabi-v7a", "x86_64", "x86", "i686"):
        return _status(
            "pass",
            f"CPU 架构 {arch}；proot 为用户态 ptrace 方案，无需 Root/namespace（尚未真机验证 proot 安装）",
        )
    return _status("unknown", "CPU 架构未知，无法确认 proot 可运行")


def _containers(profile: dict[str, Any], outputs: dict[str, str]) -> dict[str, str]:
    user_ns = _bool_or_none(profile, "features.user_ns")
    pid_ns = _bool_or_none(profile, "features.pid_ns")
    delegation = _bool_or_none(profile, "features.cgroup_v2_delegation")
    unshare_u = _rc_of(outputs.get("unshare -U true; echo rc=$?", ""))
    missing = []
    if user_ns is False:
        missing.append("user_ns 未启用")
    if pid_ns is False:
        missing.append("pid_ns 未启用")
    if delegation is False:
        missing.append("cgroup v2 无委派")
    if missing:
        return _status("fail", "；".join(missing))
    if user_ns is True and pid_ns is True and delegation is True:
        return _status(
            "pass",
            "user_ns/pid_ns/cgroup v2 委派均满足；仍需 Docker/Podman 实跑验证",
        )
    if unshare_u is not None and unshare_u != 0:
        return _status("fail", "运行时 unshare -U 失败（当前内核/SELinux 不允许用户命名空间）")
    if unshare_u == 0 and user_ns is None:
        return _status("pass", "运行时 unshare -U 成功；其余前提仍需补证")
    return _status("unknown", "命名空间或 cgroup 委派未证实，容器可行性未知")


def _systemd(profile: dict[str, Any], outputs: dict[str, str]) -> dict[str, str]:
    delegation = _bool_or_none(profile, "features.cgroup_v2_delegation")
    root_state = get_nested(profile, "root.state")
    if root_state in ("magisk", "kernelsu", "apatch") or get_nested(profile, "root.su_available") is True:
        if delegation is True:
            return _status("pass", "有 Root 且 cgroup v2 可委派；chroot 内 systemd 可尝试（仍需实测）")
        if delegation is False:
            return _status("fail", "cgroup v2 无委派，systemd 不可靠；应改用 s6/supervisord/runit")
        return _status("unknown", "有 Root 但 cgroup 委派未证实，systemd 可用性未知")
    if root_state == "none":
        return _status("fail", "无 Root/PID1 环境，systemd 无法作为服务管理器")
    return _status("unknown", "Root 状态未知，systemd 可用性未证实")


def _native_linux(profile: dict[str, Any]) -> dict[str, str]:
    value = _bool_or_none(profile, "features.native_linux_port")
    if value is True:
        return _status("pass", "profile 记录存在设备移植（native_linux_port=true）")
    if value is False:
        return _status("fail", "无设备移植证据（native_linux_port=false）")
    return _status("unknown", "adbd 无法检测设备移植情况；需人工/社区文档补证")


def _precise_cpu(profile: dict[str, Any], outputs: dict[str, str]) -> dict[str, str]:
    stat_text = outputs.get("cat /proc/stat", "")
    if _has_numbers_after_cpu(stat_text):
        return _status(
            "pass",
            "adb shell 可读 /proc/stat 且数值非零（注意：App 层受 Android 限制，Bridge 不一定可读）",
        )
    if stat_text.strip():
        return _status("fail", "adb shell 读到 /proc/stat 但数值不可用（可能被替换为固定值）")
    root_state = get_nested(profile, "root.state")
    if root_state in ("magisk", "kernelsu", "apatch"):
        return _status("pass", "有 Root，可通过 root shell 读取全局 /proc/stat")
    return _status("unknown", "adb shell 不可读 /proc/stat；无 Root 时 App/Bridge 层通常拿不到")


def _raw_network_bytes(profile: dict[str, Any], outputs: dict[str, str]) -> dict[str, str]:
    text = outputs.get("cat /proc/net/dev", "")
    if "bytes" in text and re.search(r"^\s*\w+:\s*\d+", text, re.MULTILINE):
        return _status(
            "pass",
            "adb shell 可读 /proc/net/dev 原始字节（App 层仍可能受限制）",
        )
    if text.strip():
        return _status("fail", "/proc/net/dev 存在但格式不可用")
    root_state = get_nested(profile, "root.state")
    if root_state in ("magisk", "kernelsu", "apatch"):
        return _status("pass", "有 Root，可通过 root shell 读取 /proc/net/dev")
    return _status("unknown", "adb shell 不可读 /proc/net/dev；无 Root 时通常不可得")


def _battery_sysfs(profile: dict[str, Any], outputs: dict[str, str]) -> dict[str, str]:
    readable = "readable" in outputs.get(
        "test -r /sys/class/power_supply/battery/charge_control_limit && echo readable || echo missing_or_denied",
        "",
    )
    denied = "missing_or_denied" in outputs.get(
        "test -r /sys/class/power_supply/battery/charge_control_limit && echo readable || echo missing_or_denied",
        "",
    )
    nodes = outputs.get("ls /sys/class/power_supply/battery", "")
    if readable:
        return _status("pass", "charge_control_limit 对 shell 可读")
    if denied:
        if "charge_control_limit" in nodes:
            return _status("fail", "节点存在但 shell 被拒绝（Permission denied，需 Root）")
        return _status("fail", "charge_control_limit 节点不存在或不可读（该机型可能无此接口）")
    if nodes.strip():
        return _status("unknown", "battery sysfs 可列出但未取得读取权限结论")
    return _status("unknown", "无法读取 battery sysfs")


def _charge_limit_shell(profile: dict[str, Any], outputs: dict[str, str]) -> dict[str, str]:
    text = outputs.get(
        "test -w /sys/class/power_supply/battery/charge_control_limit && echo writable || echo readonly",
        "",
    )
    if "writable" in text:
        return _status("pass", "shell 可直接写 charge_control_limit（仍需验证取值是否生效）")
    if "readonly" in text:
        return _status("fail", "shell 无写权限（常见需 Root）；改用系统自带充电保护或 bypass charging")
    return _status("unknown", "未取得 charge_control_limit 写权限结论")


def _dumpsys(outputs: dict[str, str]) -> dict[str, str]:
    text = outputs.get("dumpsys battery", "")
    lowered = text.lower()
    if "permission denial" in lowered or "permission denied" in lowered:
        return _status("fail", "dumpsys 被权限拒绝（权限模型受限）")
    if text.strip() and ("level" in lowered or "battery" in lowered):
        return _status("pass", "adb shell 可读 dumpsys battery")
    return _status("unknown", "dumpsys 输出为空或不可用")


def _appops(outputs: dict[str, str]) -> dict[str, str]:
    text = outputs.get("cmd appops get android GET_USAGE_STATS", "")
    lowered = text.lower()
    if "permission denial" in lowered or "unknown command" in lowered or "error:" in lowered:
        return _status("fail", "cmd appops 不可用或被权限拒绝")
    if text.strip():
        return _status("pass", "adb shell 可查询 appops；App 层仍需对应权限")
    return _status("unknown", "cmd appops 输出为空或不可用")


def _usage_stats(outputs: dict[str, str]) -> dict[str, str]:
    text = outputs.get("dumpsys usagestats | head -n 4", "")
    lowered = text.lower()
    if "permission denial" in lowered or "permission denied" in lowered:
        return _status("fail", "usage stats 被权限拒绝")
    if text.strip():
        return _status(
            "pass",
            "dumpsys usagestats 可访问；App 层仍需 PACKAGE_USAGE_STATS 用户授权（MIUI 重启会回落 default）",
        )
    return _status("unknown", "usagestats 输出为空或不可用")


def _boot_autostart(profile: dict[str, Any], outputs: dict[str, str]) -> dict[str, str]:
    oem = get_nested(profile, "constraints.oem_autostart")
    packages = outputs.get("pm list packages com.termux", "")
    if oem == "supported":
        return _status("pass", "OEM 自启动策略支持（profile 证据）；仍需 5 次重启实测")
    if oem == "blocked":
        return _status("fail", "OEM 阻止自启动；需 Magisk service.d 或人工启动")
    if oem == "manual-required":
        return _status("pass", "自启机制可用但需人工配置 OEM 白名单；必须做 5 次重启验收")
    if "com.termux.boot" in packages:
        return _status("pass", "检测到 Termux:Boot；仍需 5 次重启实测自启")
    if packages.strip():
        return _status("unknown", "检测到 Termux 但未确认 Termux:Boot/自启策略")
    return _status("unknown", "未检测到 Termux 安装；自启能力需安装后验证")


def _offline_existing(profile: dict[str, Any], capability_id: str) -> dict[str, str] | None:
    capabilities = profile.get("capabilities")
    if not isinstance(capabilities, dict):
        return None
    item = capabilities.get(capability_id)
    if isinstance(item, dict) and item.get("status") in ("pass", "fail", "unknown"):
        return _status(str(item["status"]), str(item.get("evidence", "profile 已有结论")))
    return None


def evaluate_capabilities(profile: dict[str, Any], outputs: dict[str, str], online: bool) -> dict[str, dict[str, str]]:
    """计算 12 项 capabilities。"""
    if online:
        _apply_runtime_namespaces(profile, outputs)
        _apply_runtime_cgroup(profile, outputs)

    computed = {
        "proot": _proot(profile, outputs),
        "containers": _containers(profile, outputs),
        "systemd": _systemd(profile, outputs),
        "native_linux": _native_linux(profile),
        "precise_cpu": _precise_cpu(profile, outputs),
        "raw_network_bytes": _raw_network_bytes(profile, outputs),
        "battery_sysfs": _battery_sysfs(profile, outputs),
        "charge_limit_shell": _charge_limit_shell(profile, outputs),
        "dumpsys": _dumpsys(outputs),
        "appops": _appops(outputs),
        "usage_stats": _usage_stats(outputs),
        "boot_autostart": _boot_autostart(profile, outputs),
    }
    if not online:
        # 离线模式：只有 profile 明确证据的项可判定；其余保持 unknown，避免臆测。
        for capability_id in CAPABILITY_IDS:
            existing = _offline_existing(profile, capability_id)
            explicit = _explicit_offline_evidence(profile, capability_id)
            if existing is not None and existing["status"] != "unknown":
                computed[capability_id] = existing
            elif explicit is not None:
                computed[capability_id] = explicit
            elif computed[capability_id]["status"] != "unknown":
                # 从 features 推得的 pass/fail 在离线模式仍有效（如 containers/native/proot/systemd）
                continue
            else:
                computed[capability_id] = _status(
                    "unknown",
                    "离线模式：无 ADB 证据，仅依据 profile features，无法判定",
                )
    return computed


def _explicit_offline_evidence(profile: dict[str, Any], capability_id: str) -> dict[str, str] | None:
    """离线时允许从 profile features 直接推出的能力结论。"""
    if capability_id == "native_linux":
        value = _bool_or_none(profile, "features.native_linux_port")
        if value is not None:
            return _native_linux(profile)
    if capability_id == "containers":
        values = [
            _bool_or_none(profile, "features.user_ns"),
            _bool_or_none(profile, "features.pid_ns"),
            _bool_or_none(profile, "features.cgroup_v2_delegation"),
        ]
        if any(value is False for value in values):
            return _containers(profile, {})
        if all(value is True for value in values):
            return _containers(profile, {})
    if capability_id == "proot":
        if get_nested(profile, "kernel.arch") is not None:
            return _proot(profile, {})
    if capability_id == "systemd":
        if get_nested(profile, "root.state") == "none":
            return _systemd(profile, {})
    return None


def _route_hint(profile: dict[str, Any], capabilities: dict[str, dict[str, str]]) -> str:
    if capabilities.get("native_linux", {}).get("status") == "pass":
        return "D"
    root_state = get_nested(profile, "root.state")
    if root_state in ("magisk", "kernelsu", "apatch") or capabilities.get("containers", {}).get("status") == "pass":
        return "B"
    if get_nested(profile, "boot.bootloader_unlocked") is False:
        return "A"
    return "unknown"


def probe_profile(profile: dict[str, Any], transport: Any = None) -> tuple[dict[str, Any], str]:
    """在 profile 副本上补 capabilities/verdicts/probe 元数据。

    返回 ``(profile, mode)``；mode 为 ``adb`` / ``fixture`` / ``offline``。
    传入 transport 时要求 profile 的 source.mode 与 transport 类型一致（fixture 可回放）。
    """
    probed = copy.deepcopy(profile)
    online = transport is not None
    mode = "offline"
    outputs: dict[str, str] = {}
    serial = None
    if online:
        from .adb import FixtureTransport

        mode = "fixture" if isinstance(transport, FixtureTransport) else "adb"
        devices = transport.devices()
        online_devices = [device.get("serial") for device in devices if device.get("state") == "device"]
        if not online_devices:
            from .adb import AdbError

            raise AdbError("未发现已授权的在线设备：probe 需要 --adb-fixture 或可用设备")
        serial = online_devices[0] if len(online_devices) == 1 else None
        if serial is None:
            from .adb import AdbError

            raise AdbError("检测到多台在线设备：请设置 ANDROID_SERIAL 后重试 probe")
        outputs = run_probe_commands(transport, serial)

    capabilities = evaluate_capabilities(probed, outputs, online=online)
    counts = {"pass": 0, "fail": 0, "unknown": 0}
    items: dict[str, str] = {}
    for capability_id in CAPABILITY_IDS:
        status = capabilities[capability_id]["status"]
        counts[status] = counts.get(status, 0) + 1
        items[capability_id] = status
    probed["capabilities"] = capabilities
    probed["verdicts"] = {
        "summary": counts,
        "route_hint": _route_hint(probed, capabilities),
        "items": items,
    }
    probed["probe"] = {
        "probed_at": iso_now(),
        "mode": mode,
        "commands": [f"adb shell {command}" for command in PROBE_COMMANDS] if online else [],
    }
    probed["evidence_refs"] = list(probed.get("evidence_refs") or []) + (
        [f"adb shell {command}" for command in PROBE_COMMANDS] if online else []
    )
    if not online:
        probed.setdefault("warnings", []).append(
            "probe 处于离线模式：未执行任何 ADB 命令，capabilities 可能为 unknown"
        )
    return probed, mode


def format_probe_human(profile: dict[str, Any]) -> str:
    """probe 人类摘要。"""
    capabilities = profile.get("capabilities") or {}
    lines = ["能力探测结果（status: pass/fail/unknown）："]
    for capability_id in CAPABILITY_IDS:
        item = capabilities.get(capability_id) or {}
        lines.append(
            f"  [{item.get('status', 'unknown'):7s}] {capability_id} - {item.get('evidence', '')}"
        )
    verdicts = profile.get("verdicts") or {}
    summary = verdicts.get("summary") or {}
    lines.append("")
    lines.append(
        "汇总：pass={} fail={} unknown={}；路线提示={}".format(
            summary.get("pass", 0),
            summary.get("fail", 0),
            summary.get("unknown", 0),
            verdicts.get("route_hint", "unknown"),
        )
    )
    return "\n".join(lines)
