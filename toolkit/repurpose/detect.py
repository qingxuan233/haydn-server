"""detect：通过只读 ADB 命令采集 ``repurpose.device-profile.v1`` 骨架。

命令全部为只读（getprop / cat / ls / dumpsys / wm / pm list），不写设备、不改设置。
无 adb / 无设备时抛出 PreconditionError（CLI 映射退出码 3）。
离线环境使用 ``--adb-fixture`` 回放样本，测试不依赖真机与网络。
"""

from __future__ import annotations

import re
from typing import Any

from .adb import FixtureTransport, resolve_device
from .util import SCHEMA_PROFILE, iso_now

DETECT_COMMANDS = (
    "getprop",
    "uname -a",
    "cat /proc/version",
    "cat /proc/meminfo",
    "cat /proc/cpuinfo",
    "df -k",
    "mount",
    "dumpsys battery",
    "wm size",
    "wm density",
    "getenforce",
    "id",
    "which su",
    "which magisk",
    "pm list packages",
    "pm list features",
    "ls -l /proc/self/ns",
    "cat /proc/filesystems",
    "cat /proc/self/cgroup",
    "grep Seccomp /proc/self/status",
    "ls /sys/fs/cgroup",
    "cat /sys/fs/cgroup/cgroup.controllers",
    "zcat /proc/config.gz",
    "cat /proc/sys/kernel/yama/ptrace_scope",
    "cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_available_governors",
    "ls /sys/class/thermal",
    "for z in /sys/class/thermal/thermal_zone*; do echo $(cat $z/type 2>/dev/null) $(cat $z/temp 2>/dev/null); done",
    "ls /sys/class/power_supply",
    "ls /sys/class/power_supply/battery",
    "for d in /sys/devices/system/cpu/cpufreq/policy*; do echo policy=$(basename $d) cpus=$(cat $d/affected_cpus 2>/dev/null) governor=$(cat $d/scaling_governor 2>/dev/null) max=$(cat $d/scaling_max_freq 2>/dev/null) hwmax=$(cat $d/cpuinfo_max_freq 2>/dev/null); done",
    "cat /proc/swaps",
    "ls /sys/block",
    "ls -l /dev/block/by-name",
    "cat /proc/stat",
    "cat /proc/net/dev",
)
"""detect 的只读命令清单（同时写入 source.commands / evidence_refs）。"""

_CONFIG_PATTERN = re.compile(r"CONFIG_[A-Z0-9_]+")
_CONFIG_SET = {
    "CONFIG_USER_NS": "user_ns",
    "CONFIG_PID_NS": "pid_ns",
    "CONFIG_NET_NS": "net_ns",
    "CONFIG_UTS_NS": "uts_ns",
    "CONFIG_IPC_NS": "ipc_ns",
    "CONFIG_OVERLAY_FS": "overlay_fs",
    "CONFIG_BINFMT_MISC": "binfmt_misc",
    "CONFIG_SECCOMP_FILTER": "seccomp_filter",
    "CONFIG_KALLSYMS": "kallsyms",
    "CONFIG_MODULES": "modules",
}

_NS_ALIASES = {
    "user": "user_ns",
    "pid": "pid_ns",
    "mnt": "mount_ns",
    "mount": "mount_ns",
    "net": "net_ns",
    "uts": "uts_ns",
    "ipc": "ipc_ns",
}

_ROOT_MANAGER_PATTERNS = (
    ("topjohnwu.magisk", "magisk"),
    ("magisk", "magisk"),
    ("me.weishu.kernelsu", "kernelsu"),
    ("kernelsu", "kernelsu"),
    ("me.bmax.apatch", "apatch"),
    ("apatch", "apatch"),
)

_BATTERY_HEALTH = {
    1: "UNKNOWN",
    2: "GOOD",
    3: "OVERHEAT",
    4: "DEAD",
    5: "OVER_VOLTAGE",
    6: "UNSPECIFIED_FAILURE",
    7: "COLD",
}
_BATTERY_STATUS = {
    1: "UNKNOWN",
    2: "CHARGING",
    3: "DISCHARGING",
    4: "NOT_CHARGING",
    5: "FULL",
}

_BATTERY_CONTROL_NODES = (
    "charge_control_limit",
    "charge_control_limit_max",
    "charge_full",
    "charge_full_design",
    "battery_charging_enabled",
    "cycle_count",
)


# ---------------------------------------------------------------------------
# 通用解析
# ---------------------------------------------------------------------------


def parse_getprop(text: str) -> dict[str, str]:
    """解析 ``getprop`` 的 ``[key]: [value]`` 输出。"""
    props: dict[str, str] = {}
    for line in text.splitlines():
        match = re.match(r"^\[([^\]]+)\]:\s*\[(.*)\]$", line.strip())
        if match:
            props[match.group(1).strip()] = match.group(2)
    return props


def _prop(props: dict[str, str], key: str) -> str | None:
    value = props.get(key)
    return value if value not in (None, "") else None


def _prop_bool(props: dict[str, str], key: str) -> bool | None:
    value = _prop(props, key)
    if value is None:
        return None
    lowered = value.strip().lower()
    if lowered in {"1", "true", "yes", "on"}:
        return True
    if lowered in {"0", "false", "no", "off"}:
        return False
    return None


def _prop_int(props: dict[str, str], key: str) -> int | None:
    value = _prop(props, key)
    if value is None:
        return None
    try:
        return int(value.strip())
    except ValueError:
        return None


def parse_uname(text: str) -> tuple[str | None, str | None, str | None]:
    """解析 ``uname -a``，返回 ``(release, version_string, arch)``。"""
    stripped = text.strip()
    if not stripped:
        return None, None, None
    fields = stripped.split()
    release = None
    for field in fields:
        if re.match(r"^[0-9]+\.[0-9]+[0-9A-Za-z._+-]*$", field):
            release = field
            break
    arch = None
    for candidate in ("aarch64", "arm64", "armv8l", "x86_64", "x86", "i686"):
        if candidate in fields:
            arch = candidate
            break
    return release, stripped, arch


def parse_meminfo(text: str) -> dict[str, int | None]:
    values: dict[str, int | None] = {
        "total_kb": None,
        "available_kb": None,
        "swap_total_kb": None,
    }
    for line in text.splitlines():
        match = re.match(r"^(MemTotal|MemAvailable|SwapTotal):\s*(\d+)\s*kB", line.strip())
        if not match:
            continue
        key = {
            "MemTotal": "total_kb",
            "MemAvailable": "available_kb",
            "SwapTotal": "swap_total_kb",
        }[match.group(1)]
        values[key] = int(match.group(2))
    return values


def parse_cpuinfo(text: str) -> int | None:
    count = len(re.findall(r"^processor\s*:", text, flags=re.MULTILINE))
    return count or None


def parse_df_data(text: str) -> dict[str, int | None]:
    """从 ``df -k`` 输出解析 /data 的总量/已用/可用（单位 kB）。"""
    result: dict[str, int | None] = {
        "data_total_kb": None,
        "data_used_kb": None,
        "data_available_kb": None,
    }
    for line in text.splitlines():
        parts = line.split()
        if len(parts) < 6 or not parts[-1].endswith("/data"):
            continue
        numbers = []
        for token in parts[1:-2]:
            try:
                numbers.append(int(token))
            except ValueError:
                numbers = []
                break
        if len(numbers) >= 3:
            result["data_total_kb"] = numbers[0]
            result["data_used_kb"] = numbers[1]
            result["data_available_kb"] = numbers[2]
            break
    return result


def parse_mount_fs(text: str) -> str | None:
    """解析 ``mount`` 输出中 /data 的文件系统类型。"""
    for line in text.splitlines():
        if " /data " in line or line.rstrip().endswith(" /data"):
            match = re.search(r"type\s+([A-Za-z0-9_]+)", line)
            if match:
                return match.group(1)
    return None


def parse_wm_size(text: str) -> tuple[int | None, int | None]:
    match = re.search(r"(?:Physical|Override) size:\s*(\d+)\s*x\s*(\d+)", text)
    if not match:
        return None, None
    return int(match.group(1)), int(match.group(2))


def parse_wm_density(text: str) -> int | None:
    match = re.search(r"(?:Physical|Override) density:\s*(\d+)", text)
    return int(match.group(1)) if match else None


def parse_dumpsys_battery(text: str) -> dict[str, Any]:
    fields: dict[str, str] = {}
    for line in text.splitlines():
        match = re.match(r"\s*([A-Za-z_]+)\s*:\s*(\S+)", line)
        if match:
            fields.setdefault(match.group(1).lower(), match.group(2))
    level = _int_or_none(fields.get("level"))
    temperature_raw = _int_or_none(fields.get("temperature"))
    voltage = _int_or_none(fields.get("voltage"))
    health_raw = _int_or_none(fields.get("health"))
    status_raw = _int_or_none(fields.get("status"))
    return {
        "level_pct": level,
        "temperature_c": round(temperature_raw / 10.0, 1) if temperature_raw is not None else None,
        "voltage_mv": voltage,
        "health": _BATTERY_HEALTH.get(health_raw) if health_raw is not None else None,
        "status": _BATTERY_STATUS.get(status_raw) if status_raw is not None else None,
    }


def _int_or_none(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value.strip())
    except ValueError:
        return None


def parse_namespaces(text: str) -> set[str]:
    """解析 ``ls -l /proc/self/ns``（或脚本输出），返回可见 namespace 名。"""
    names: set[str] = set()
    for match in re.finditer(r"([a-z_]+):\s*\[", text):
        names.add(match.group(1))
    for match in re.finditer(r"->\s*'?([a-z_]+):", text):
        names.add(match.group(1))
    return names


def parse_kernel_config(text: str) -> dict[str, bool]:
    """解析 kernel config 文本中的目标 CONFIG 项。"""
    result: dict[str, bool] = {}
    for line in text.splitlines():
        stripped = line.strip()
        match = _CONFIG_PATTERN.match(stripped)
        if not match:
            continue
        key = match.group(0)
        if key not in _CONFIG_SET:
            continue
        if stripped.startswith("#"):
            if "is not set" in stripped:
                result[key] = False
            continue
        value = stripped.split("=", 1)[1].strip() if "=" in stripped else ""
        result[key] = value in {"y", "m", "yes"}
    return result


def parse_cpufreq_clusters(text: str) -> list[dict[str, Any]]:
    clusters: list[dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("policy="):
            continue
        match = re.match(
            r"policy=(\S+)\s+cpus=([0-9 ]*)\s+governor=(\S*)\s+max=([0-9]*)\s+hwmax=([0-9]*)",
            line,
        )
        if not match:
            continue
        cpus = " ".join(match.group(2).split())
        clusters.append(
            {
                "policy": match.group(1),
                "cpus": cpus or None,
                "governor": match.group(3) or None,
                "scaling_max_freq_khz": int(match.group(4)) if match.group(4) else None,
                "hw_max_freq_khz": int(match.group(5)) if match.group(5) else None,
            }
        )
    return clusters


def parse_thermal_max_c(text: str) -> tuple[int | None, float | None]:
    """解析 thermal zone 循环输出，返回 ``(zone_count, max_temp_c)``。"""
    temperatures: list[float] = []
    lines = 0
    for line in text.splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        lines += 1
        raw = _thermal_to_celsius(parts[-1])
        if raw is not None and -40.0 <= raw <= 150.0:
            temperatures.append(raw)
    max_temp = round(max(temperatures), 1) if temperatures else None
    return (lines or None), max_temp


def _thermal_to_celsius(raw_value: str) -> float | None:
    value = _int_or_none(raw_value)
    if value is None:
        return None
    magnitude = abs(value)
    if magnitude >= 1000:
        return value / 1000.0
    if magnitude >= 50:
        return value / 10.0
    return float(value)


def _parse_swap_zram_kb(text: str) -> int | None:
    for line in text.splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[0].lower().startswith("zram"):
            value = _int_or_none(parts[2] if len(parts) >= 4 else parts[1])
            if value:
                return value
    return None


def _line_contains(text: str, needle: str) -> bool:
    return any(needle in line for line in text.splitlines())


def _has_binary(output: str) -> bool:
    stripped = output.strip()
    if not stripped:
        return False
    if stripped.lower().startswith(("which:", "which: no", "not found", "error")):
        return False
    return True


# ---------------------------------------------------------------------------
# profile 构建
# ---------------------------------------------------------------------------


def collect_profile(
    transport: Any,
    *,
    serial: str | None = None,
    include_serial: bool = False,
) -> dict[str, Any]:
    """采集 profile 骨架。transport 需实现 ``devices`` / ``shell``。"""
    device_serial = resolve_device(transport, serial)
    props = parse_getprop(transport.shell("getprop", device_serial))
    outputs: dict[str, str] = {}
    for command in DETECT_COMMANDS:
        if command == "getprop":
            continue
        try:
            outputs[command] = transport.shell(command, device_serial)
        except Exception:
            outputs[command] = ""

    fixture_mode = isinstance(transport, FixtureTransport)
    fixture_name = transport.fixture_name if fixture_mode else None

    profile = _build_profile(props, outputs, include_serial, device_serial)
    commands = [f"adb shell {command}" for command in DETECT_COMMANDS]
    source: dict[str, Any] = {
        "mode": "fixture" if fixture_mode else "adb",
        "commands": commands,
        "notes": f"离线回放 {fixture_name}" if fixture_mode else None,
    }
    profile["source"] = source
    fixture_evidence = [f"fixture:{fixture_name}"] if fixture_mode else []
    profile["evidence_refs"] = fixture_evidence + commands[:8] + [
        f"adb shell {command}"
        for command in DETECT_COMMANDS
        if command != "getprop" and outputs.get(command)
    ][:24]
    if not props:
        profile["warnings"].append("未能读取系统属性（getprop 输出为空），identity/verity 字段可能缺失")
    if fixture_mode:
        profile["warnings"].append("离线 fixture 结果仅用于测试/回放，不代表真机现状")
    if _prop(props, "sys.oem_unlock_allowed") is None and _prop(props, "ro.oem_unlock_supported") is None:
        profile["warnings"].append("厂商解锁政策无法由 adb 直接确认，已标记 unknown")
    return profile


def _build_profile(
    props: dict[str, str],
    outputs: dict[str, str],
    include_serial: bool,
    device_serial: str,
) -> dict[str, Any]:
    identity = _build_identity(props, include_serial, device_serial)
    boot = _build_boot(props, outputs)
    root = _build_root(props, outputs)
    kernel = _build_kernel(props, outputs)
    features, config_source, config_readable = _build_features(outputs)
    hardware = _build_hardware(props, outputs)
    storage = _build_storage(outputs)
    crypto = _build_crypto(props)
    constraints = _build_constraints(outputs)

    unknowns = _collect_unknowns(boot, root, features, crypto, constraints)
    warnings: list[str] = []
    if root["state"] == "unknown" and not outputs.get("pm list packages", "").strip():
        warnings.append("缺少 pm list packages 输出，无法确认 Root 管理器状态")
    if features.get("native_linux_port") is None:
        warnings.append("原生 Linux 移植情况无法由 adb 检测，需人工/文档补证（features.native_linux_port）")
    if features.get("custom_kernel") is None:
        warnings.append("自定义内核/第三方 ROM 支持无法由 adb 检测，需人工/文档补证（features.custom_kernel）")

    return {
        "schema": SCHEMA_PROFILE,
        "generated_at": iso_now(),
        "source": {"mode": "adb", "commands": [], "notes": None},
        "identity": identity,
        "boot": boot,
        "root": root,
        "kernel": {**kernel, "config_source": config_source, "config_readable": config_readable},
        "hardware": hardware,
        "storage": storage,
        "crypto": crypto,
        "features": features,
        "constraints": constraints,
        "unknowns": unknowns,
        "warnings": warnings,
    }


def _build_identity(props: dict[str, str], include_serial: bool, serial: str) -> dict[str, Any]:
    return {
        "codename": _prop(props, "ro.product.device"),
        "model": _prop(props, "ro.product.model"),
        "market_name": _prop(props, "ro.product.marketname"),
        "manufacturer": _prop(props, "ro.product.manufacturer"),
        "brand": _prop(props, "ro.product.brand"),
        "product": _prop(props, "ro.product.name"),
        "fingerprint": _prop(props, "ro.build.fingerprint"),
        "android_version": _prop(props, "ro.build.version.release"),
        "sdk": _prop_int(props, "ro.build.version.sdk"),
        "build_id": _prop(props, "ro.build.id"),
        "build_type": _prop(props, "ro.build.type"),
        "security_patch": _prop(props, "ro.build.version.security_patch"),
        "serial": serial if include_serial else None,
        "serial_redacted": not include_serial,
    }


def _build_boot(props: dict[str, str], outputs: dict[str, str]) -> dict[str, Any]:
    flash_locked = _prop_bool(props, "ro.boot.flash.locked")
    vbmeta_state = _prop(props, "ro.boot.vbmeta.device_state")
    if flash_locked is not None:
        unlocked: bool | None = not flash_locked
    elif vbmeta_state == "unlocked":
        unlocked = True
    elif vbmeta_state == "locked":
        unlocked = False
    else:
        unlocked = None

    allowed = _prop(props, "sys.oem_unlock_allowed")
    supported = _prop(props, "ro.oem_unlock_supported")
    if allowed in {"1", "true"} or supported in {"1", "true"}:
        policy = "available"
    elif allowed in {"0", "false"} or supported in {"0", "false"}:
        policy = "closed"
    else:
        policy = "unknown"
    evidence = (
        "基于 sys.oem_unlock_allowed / ro.oem_unlock_supported 属性"
        if policy != "unknown"
        else None
    )

    slot_suffix = _prop(props, "ro.boot.slot_suffix")
    by_name = outputs.get("ls -l /dev/block/by-name", "")
    if slot_suffix:
        partition_style = "A/B"
        has_init_boot = "init_boot" in by_name if by_name.strip() else None
    else:
        partition_style = None
        has_init_boot = False if by_name.strip() and "init_boot" not in by_name else None

    return {
        "bootloader_unlocked": unlocked,
        "verified_boot_state": _prop(props, "ro.boot.verifiedbootstate"),
        "vbmeta_device_state": vbmeta_state,
        "dm_verity_mode": _prop(props, "ro.boot.veritymode"),
        "selinux": (outputs.get("getenforce", "").strip() or None),
        "slot_suffix": slot_suffix or None,
        "partition_style": partition_style,
        "has_init_boot": has_init_boot,
        "oem_unlock_policy": policy,
        "oem_unlock_evidence": evidence,
    }


def _build_root(props: dict[str, str], outputs: dict[str, str]) -> dict[str, Any]:
    packages_text = outputs.get("pm list packages", "")
    root_packages: list[str] = []
    manager = None
    lowered_packages = packages_text.lower()
    for pattern, name in _ROOT_MANAGER_PATTERNS:
        if pattern in lowered_packages:
            manager = manager or name
    for line in packages_text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("package:"):
            continue
        package = stripped[len("package:") :]
        if any(token in package.lower() for token in ("magisk", "kernelsu", "apatch")):
            root_packages.append(package)

    su_available = _has_binary(outputs.get("which su", ""))
    magisk_available = _has_binary(outputs.get("which magisk", ""))
    if manager is None and magisk_available:
        manager = "magisk"
    if manager is not None:
        state = manager
    elif su_available:
        state = "unknown"
    elif packages_text.strip():
        state = "none"
    else:
        state = "unknown"

    return {
        "state": state,
        "su_available": su_available if (su_available or packages_text.strip()) else None,
        "root_manager_packages": root_packages,
        "adb_uid": (outputs.get("id", "").strip() or None),
        "ro_secure": _prop_bool(props, "ro.secure"),
        "ro_debuggable": _prop_bool(props, "ro.debuggable"),
    }


def _build_kernel(props: dict[str, str], outputs: dict[str, str]) -> dict[str, Any]:
    uname_text = outputs.get("uname -a", "") or outputs.get("cat /proc/version", "")
    release, version_string, arch = parse_uname(uname_text)
    if arch is None:
        abi = _prop(props, "ro.product.cpu.abilist")
        if abi:
            arch = abi.split(",")[0].strip() or None
    if release is None:
        release = _prop(props, "ro.kernel.version")
    lowered = (release or "").lower()
    if "qgki" in lowered or ("gki" in lowered and not lowered.startswith(("5.10", "5.15", "6."))):
        generation = "gki-1.x"
    elif "gki" in lowered:
        generation = "gki-2.x"
    elif lowered:
        generation = "legacy"
    else:
        generation = "unknown"
    return {
        "release": release,
        "version_string": version_string,
        "arch": arch,
        "gki_generation": generation,
    }


def _build_features(outputs: dict[str, str]) -> tuple[dict[str, Any], str, bool | None]:
    config = parse_kernel_config(outputs.get("zcat /proc/config.gz", ""))
    config_source = "unknown"
    config_readable: bool | None = None
    config_text = outputs.get("zcat /proc/config.gz", "")
    if config:
        config_source = "proc-config-gz"
        config_readable = True
    elif not config_text.strip():
        # 无输出无法区分"文件不存在"与"读取被拒"，保持 unknown。
        config_source = "unknown"
        config_readable = None
    else:
        config_source = "none"
        config_readable = False

    namespaces = parse_namespaces(outputs.get("ls -l /proc/self/ns", ""))
    mount_ns = bool(namespaces) and ("mnt" in namespaces or "mount" in namespaces)

    def config_or_runtime(config_key: str, runtime_value: bool | None) -> bool | None:
        if config_key in config:
            return config[config_key]
        if runtime_value is not None and namespaces:
            return runtime_value
        return None

    cgroup_ls = outputs.get("ls /sys/fs/cgroup", "")
    cgroup_controllers = outputs.get("cat /sys/fs/cgroup/cgroup.controllers", "").strip()
    cgroup_text = outputs.get("mount", "") + "\n" + outputs.get("cat /proc/self/cgroup", "")
    cgroup_v1: bool | None = None
    cgroup_v2: bool | None = None
    delegation: bool | None = None
    if "type cgroup2" in cgroup_text or "cgroup2" in cgroup_ls:
        cgroup_v2 = True
    elif "type cgroup " in cgroup_text or "cgroup" in cgroup_text:
        cgroup_v1 = True
    if "cgroup.controllers" in cgroup_ls:
        cgroup_v2 = True
        delegation = bool(cgroup_controllers)
    elif cgroup_ls.strip():
        cgroup_v2 = False
    if "type cgroup " in cgroup_text:
        cgroup_v1 = True

    filesystems = outputs.get("cat /proc/filesystems", "")
    overlay = config.get("CONFIG_OVERLAY_FS")
    if overlay is None and filesystems.strip():
        overlay = _line_contains(filesystems, "overlay")
    binfmt = config.get("CONFIG_BINFMT_MISC")
    if binfmt is None and filesystems.strip():
        binfmt = _line_contains(filesystems, "binfmt")

    seccomp = config.get("CONFIG_SECCOMP_FILTER")
    match = re.search(r"Seccomp\s*:\s*(\d+)", outputs.get("grep Seccomp /proc/self/status", ""))
    if match:
        seccomp = int(match.group(1)) != 0

    ptrace_text = outputs.get("cat /proc/sys/kernel/yama/ptrace_scope", "").strip()
    ptrace: bool | None = None
    if ptrace_text:
        try:
            ptrace = int(ptrace_text.split()[0]) == 0
        except ValueError:
            ptrace = None

    packages = outputs.get("pm list packages", "").lower()

    features = {
        "user_ns": config_or_runtime("CONFIG_USER_NS", "user" in namespaces),
        "pid_ns": config_or_runtime("CONFIG_PID_NS", "pid" in namespaces),
        "mount_ns": mount_ns if namespaces else None,
        "net_ns": config_or_runtime("CONFIG_NET_NS", "net" in namespaces),
        "uts_ns": config_or_runtime("CONFIG_UTS_NS", "uts" in namespaces),
        "ipc_ns": config_or_runtime("CONFIG_IPC_NS", "ipc" in namespaces),
        "cgroup_v1": cgroup_v1,
        "cgroup_v2": cgroup_v2,
        "cgroup_v2_delegation": delegation,
        "overlay_fs": overlay,
        "binfmt_misc": binfmt,
        "seccomp_filter": seccomp,
        "kallsyms": config.get("CONFIG_KALLSYMS"),
        "modules": config.get("CONFIG_MODULES"),
        "ptrace_allowed": ptrace,
        "native_linux_port": None,
        "custom_kernel": None,
        "termux_available": True if "com.termux" in packages else None,
        "shizuku_available": True if "moe.shizuku.privileged.api" in packages else None,
        "boot_completed_receiver": True if "com.termux.boot" in packages else None,
    }
    return features, config_source, config_readable


def _build_hardware(props: dict[str, str], outputs: dict[str, str]) -> dict[str, Any]:
    memory = parse_meminfo(outputs.get("cat /proc/meminfo", ""))
    cores = parse_cpuinfo(outputs.get("cat /proc/cpuinfo", ""))
    width, height = parse_wm_size(outputs.get("wm size", ""))
    density = parse_wm_density(outputs.get("wm density", ""))
    battery = parse_dumpsys_battery(outputs.get("dumpsys battery", ""))
    battery_dir = outputs.get("ls /sys/class/power_supply/battery", "")
    nodes = [name for name in _BATTERY_CONTROL_NODES if _line_contains(battery_dir, name)]
    zone_count, max_temp = parse_thermal_max_c(
        outputs.get(
            "for z in /sys/class/thermal/thermal_zone*; do echo $(cat $z/type 2>/dev/null) $(cat $z/temp 2>/dev/null); done",
            "",
        )
    )
    if zone_count is None:
        zone_count = len([line for line in outputs.get("ls /sys/class/thermal", "").splitlines() if "thermal_zone" in line]) or None

    clusters = parse_cpufreq_clusters(
        outputs.get(
            "for d in /sys/devices/system/cpu/cpufreq/policy*; do echo policy=$(basename $d) cpus=$(cat $d/affected_cpus 2>/dev/null) governor=$(cat $d/scaling_governor 2>/dev/null) max=$(cat $d/scaling_max_freq 2>/dev/null) hwmax=$(cat $d/cpuinfo_max_freq 2>/dev/null); done",
            "",
        )
    )
    governors_text = outputs.get(
        "cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_available_governors", ""
    )
    governors = governors_text.split() if governors_text.strip() else []
    abi_text = _prop(props, "ro.product.cpu.abilist")
    abi = [token for token in (abi_text or "").split(",") if token.strip()]

    return {
        "soc": {
            "manufacturer": _prop(props, "ro.soc.manufacturer"),
            "platform": _prop(props, "ro.board.platform"),
            "model": _prop(props, "ro.soc.model"),
            "marketing_name": None,
        },
        "cpu": {
            "cores": cores,
            "abi": abi,
            "governors": governors,
            "clusters": clusters,
        },
        "memory": memory,
        "display": {
            "width_px": width,
            "height_px": height,
            "density_dpi": density,
            "refresh_hz": None,
        },
        "battery": {
            "design_capacity_mah": None,
            "charge_full_mah": None,
            **battery,
            "charge_control_nodes": nodes,
        },
        "thermal": {
            "zone_count": zone_count,
            "status": None,
            "max_temp_c": max_temp,
        },
    }


def _build_storage(outputs: dict[str, str]) -> dict[str, Any]:
    df = parse_df_data(outputs.get("df -k", ""))
    filesystem = parse_mount_fs(outputs.get("mount", ""))
    block_text = outputs.get("ls /sys/block", "")
    zram = _line_contains(block_text, "zram") if block_text.strip() else None
    zram_total = _parse_swap_zram_kb(outputs.get("cat /proc/swaps", ""))
    pm_features = outputs.get("pm list features", "")
    if _line_contains(pm_features, "nosdcard"):
        external_sdcard: bool | None = False
    else:
        external_sdcard = None
    return {
        "data_total_kb": df["data_total_kb"],
        "data_used_kb": df["data_used_kb"],
        "data_available_kb": df["data_available_kb"],
        "data_filesystem": filesystem,
        "external_sdcard": external_sdcard,
        "external_expandable": False if external_sdcard is False else None,
        "zram": zram,
        "zram_total_kb": zram_total,
    }


def _build_crypto(props: dict[str, str]) -> dict[str, Any]:
    state = _prop(props, "ro.crypto.state") or ""
    if "encrypted" in state.lower():
        encrypted: bool | None = True
    elif state:
        encrypted = False
    else:
        encrypted = None
    crypto_type = (_prop(props, "ro.crypto.type") or "").lower()
    if crypto_type == "file":
        encryption_type = "FBE"
    elif crypto_type == "block":
        encryption_type = "FDE"
    elif crypto_type:
        encryption_type = "unknown"
    else:
        encryption_type = "unknown"

    keystore_hint = " ".join(
        filter(
            None,
            (
                _prop(props, "ro.hardware.keystore"),
                _prop(props, "ro.boot.keystore"),
                _prop(props, "ro.hardware"),
            ),
        ),
    ).lower()
    if "strongbox" in keystore_hint:
        keystore = "strongbox"
    elif any(token in keystore_hint for token in ("tee", "trusty", "keymaster", "keymint", "gatekeeper")):
        keystore = "tee"
    else:
        keystore = "unknown"
    return {
        "userdata_encrypted": encrypted,
        "encryption_type": encryption_type,
        "keystore": keystore,
        "play_integrity_required": None,
        "play_integrity_level": None,
    }


def _build_constraints(outputs: dict[str, str]) -> dict[str, Any]:
    return {
        "external_storage": "none"
        if _line_contains(outputs.get("pm list features", ""), "nosdcard")
        else "unknown",
        "oem_autostart": "unknown",
        "background_execution": "unknown",
        "battery_long_term_plugged": "unknown",
        "root_required_capabilities": [
            "precise_cpu",
            "raw_network_bytes",
            "battery_sysfs",
            "charge_limit_shell",
            "dumpsys",
            "appops",
        ],
        "notes": [],
    }


def _collect_unknowns(
    boot: dict[str, Any],
    root: dict[str, Any],
    features: dict[str, Any],
    crypto: dict[str, Any],
    constraints: dict[str, Any],
) -> list[str]:
    unknowns: list[str] = []
    if boot.get("bootloader_unlocked") is None:
        unknowns.append("boot.bootloader_unlocked")
    if boot.get("oem_unlock_policy") in (None, "unknown"):
        unknowns.append("boot.oem_unlock_policy")
    if root.get("state") == "unknown":
        unknowns.append("root.state")
    for key in ("user_ns", "pid_ns", "cgroup_v2_delegation", "native_linux_port", "custom_kernel"):
        if features.get(key) is None:
            unknowns.append(f"features.{key}")
    if crypto.get("play_integrity_required") is None:
        unknowns.append("crypto.play_integrity_required")
    if constraints.get("oem_autostart") in (None, "unknown"):
        unknowns.append("constraints.oem_autostart")
    return unknowns


def detect_profile(
    transport: Any,
    *,
    serial: str | None = None,
    include_serial: bool = False,
) -> dict[str, Any]:
    """对外入口：采集 profile（``source.mode`` 由 transport 类型决定）。"""
    return collect_profile(transport, serial=serial, include_serial=include_serial)
