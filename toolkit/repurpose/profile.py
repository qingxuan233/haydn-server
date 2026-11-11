"""device-profile.v1 的读取、结构校验、模板生成与默认值。

profile 是 detect 的产物，也是 assess/plan 的输入，同时被 ``cases/*/profile.json``
复用。校验器只做结构性检查（不依赖 jsonschema 库），语义判断属于 assess 的职责。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .util import (
    SCHEMA_PROFILE,
    TEMPLATES_DIR,
    JsonFileError,
    UsageError,
    ensure_parent,
    iso_now,
    load_json,
    merge_dict,
    parse_iso,
    write_json,
)

PROFILE_TOP_KEYS = (
    "schema",
    "generated_at",
    "source",
    "identity",
    "boot",
    "root",
    "kernel",
    "hardware",
    "storage",
    "crypto",
    "features",
    "constraints",
    "unknowns",
    "evidence_refs",
    "warnings",
)
"""profile 顶层必需键（顺序即 detect 输出顺序）。"""

OPTIONAL_TOP_KEYS = ("capabilities", "verdicts", "probe")
"""probe 之后才出现的扩展键。"""

SOURCE_MODES = ("adb", "fixture", "documented", "manual")
ROUTE_IDS = ("A", "B", "C", "D")
GATE_STATUS = ("pass", "fail", "unknown")
CAPABILITY_IDS = (
    "proot",
    "containers",
    "systemd",
    "native_linux",
    "precise_cpu",
    "raw_network_bytes",
    "battery_sysfs",
    "charge_limit_shell",
    "dumpsys",
    "appops",
    "usage_stats",
    "boot_autostart",
)
"""probe 必须补齐的 12 项能力（顺序固定，便于 diff 与文档引用）。"""


def load_profile(path: str | Path) -> dict[str, Any]:
    """读取 profile JSON；文件/JSON/结构错误抛 UsageError（退出码 2）。"""
    try:
        payload = load_json(path)
    except JsonFileError as exc:
        raise UsageError(f"无法加载 profile：{exc}") from exc
    if not isinstance(payload, dict):
        raise UsageError("profile 顶层必须是 JSON object")
    return payload


def load_and_validate(path: str | Path) -> dict[str, Any]:
    """读取并做结构校验；错误合并为一条 UsageError。"""
    profile = load_profile(path)
    errors = validate_profile(profile)
    if errors:
        raise UsageError("profile 结构校验失败：" + "；".join(errors[:8]))
    return profile


def validate_profile(profile: Any) -> list[str]:
    """结构校验，返回错误列表（空列表 = 通过）。"""
    errors: list[str] = []
    if not isinstance(profile, dict):
        return ["profile 顶层必须是 JSON object"]

    schema = profile.get("schema")
    if schema != SCHEMA_PROFILE:
        errors.append(f"schema 必须为 {SCHEMA_PROFILE}（当前：{schema!r}）")

    for key in PROFILE_TOP_KEYS:
        if key not in profile:
            errors.append(f"缺少顶层键 '{key}'")

    if errors:
        return errors

    if not isinstance(profile.get("source"), dict):
        errors.append("'source' 必须是 object")
    else:
        mode = profile["source"].get("mode")
        if mode is not None and mode not in SOURCE_MODES:
            errors.append(f"source.mode 必须是 {SOURCE_MODES} 之一（当前：{mode!r}）")
        commands = profile["source"].get("commands")
        if commands is not None and not isinstance(commands, list):
            errors.append("source.commands 必须是字符串数组")

    for key in ("identity", "boot", "root", "kernel", "hardware", "storage", "crypto",
                "features", "constraints"):
        if not isinstance(profile.get(key), dict):
            errors.append(f"'{key}' 必须是 object")

    for key in ("unknowns", "evidence_refs", "warnings"):
        if not isinstance(profile.get(key), list):
            errors.append(f"'{key}' 必须是数组")
        elif not all(isinstance(item, str) for item in profile[key]):
            errors.append(f"'{key}' 数组元素必须是字符串")

    generated_at = profile.get("generated_at")
    if not isinstance(generated_at, str):
        errors.append("'generated_at' 必须是 ISO-8601 字符串")
    elif parse_iso(generated_at) is None:
        errors.append("'generated_at' 不是合法的 ISO-8601 时间")

    boot = profile.get("boot") if isinstance(profile.get("boot"), dict) else {}
    unlock = boot.get("bootloader_unlocked")
    if unlock is not None and not isinstance(unlock, bool):
        errors.append("boot.bootloader_unlocked 必须是 bool 或 null")
    policy = boot.get("oem_unlock_policy")
    if policy is not None and policy not in ("open", "available", "closed", "unknown"):
        errors.append("boot.oem_unlock_policy 必须是 open/available/closed/unknown")

    root = profile.get("root") if isinstance(profile.get("root"), dict) else {}
    state = root.get("state")
    if state is not None and state not in ("none", "magisk", "kernelsu", "apatch", "unknown"):
        errors.append("root.state 必须是 none/magisk/kernelsu/apatch/unknown")

    features = profile.get("features") if isinstance(profile.get("features"), dict) else {}
    for key, value in features.items():
        if value is not None and not isinstance(value, bool):
            errors.append(f"features.{key} 必须是 bool 或 null")

    crypto = profile.get("crypto") if isinstance(profile.get("crypto"), dict) else {}
    integrity = crypto.get("play_integrity_required")
    if integrity is not None and not isinstance(integrity, bool):
        errors.append("crypto.play_integrity_required 必须是 bool 或 null")

    capabilities = profile.get("capabilities")
    if capabilities is not None:
        if not isinstance(capabilities, dict):
            errors.append("'capabilities' 必须是 object")
        else:
            for capability_id, item in capabilities.items():
                if capability_id not in CAPABILITY_IDS:
                    errors.append(f"capabilities 含未定义的项：{capability_id}")
                    continue
                if not isinstance(item, dict):
                    errors.append(f"capabilities.{capability_id} 必须是 object")
                    continue
                if item.get("status") not in GATE_STATUS:
                    errors.append(
                        f"capabilities.{capability_id}.status 必须是 pass/fail/unknown"
                    )
                if "evidence" not in item:
                    errors.append(f"capabilities.{capability_id} 缺少 evidence")

    verdicts = profile.get("verdicts")
    if verdicts is not None and not isinstance(verdicts, dict):
        errors.append("'verdicts' 必须是 object")
    probe_meta = profile.get("probe")
    if probe_meta is not None and not isinstance(probe_meta, dict):
        errors.append("'probe' 必须是 object")

    return errors


def write_profile(path: str | Path, profile: dict[str, Any]) -> Path:
    """写 profile JSON（原子写入），返回目标路径。"""
    return write_json(path, profile, indent=2)


def load_template_profile() -> dict[str, Any]:
    """读取 ``toolkit/templates/device-profile.json`` 作为 new-profile 基底。"""
    template_path = TEMPLATES_DIR / "device-profile.json"
    try:
        payload = load_json(template_path)
    except JsonFileError as exc:
        raise UsageError(f"无法读取 profile 模板：{exc}") from exc
    if not isinstance(payload, dict):
        raise UsageError("profile 模板顶层必须是 JSON object")
    return payload


def build_new_profile(codename: str) -> dict[str, Any]:
    """从模板生成可编辑的新 profile（含 unknowns 提示）。"""
    codename = (codename or "").strip()
    if not codename:
        raise UsageError("--codename 不能为空")
    template = load_template_profile()
    profile = merge_dict(
        template,
        {
            "generated_at": iso_now(),
            "source": {
                "mode": "manual",
                "commands": [],
                "notes": f"new-profile 模板生成（codename={codename}），待按实际证据填写",
            },
            "identity": {"codename": codename},
            "unknowns": [
                "boot.bootloader_unlocked",
                "boot.oem_unlock_policy",
                "root.state",
                "features.user_ns",
                "features.pid_ns",
                "features.cgroup_v2_delegation",
                "features.native_linux_port",
                "crypto.play_integrity_required",
                "constraints.oem_autostart",
            ],
            "warnings": ["new-profile 骨架：除 codename 外均为占位值，请逐项补证据后再 assess"],
        },
    )
    # 模板中的示例值在 new-profile 中必须回归 unknown，避免把示例当结论。
    profile["boot"]["bootloader_unlocked"] = None
    profile["boot"]["oem_unlock_policy"] = "unknown"
    profile["boot"]["verified_boot_state"] = None
    profile["root"]["state"] = "unknown"
    profile["identity"]["serial"] = None
    profile["identity"]["serial_redacted"] = True
    for feature_key in profile.get("features", {}):
        profile["features"][feature_key] = None
    profile["crypto"]["play_integrity_required"] = None
    profile["capabilities"] = {
        capability_id: {"status": "unknown", "evidence": "尚未 probe"}
        for capability_id in CAPABILITY_IDS
    }
    profile["verdicts"] = {
        "summary": {"pass": 0, "fail": 0, "unknown": len(CAPABILITY_IDS)},
        "route_hint": "unknown",
        "items": {capability_id: "unknown" for capability_id in CAPABILITY_IDS},
    }
    profile["probe"] = {"probed_at": None, "mode": "none", "commands": []}
    return profile


def capabilities_or_empty(profile: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """返回 capabilities dict；不存在时返回空 dict（assess 用）。"""
    capabilities = profile.get("capabilities")
    return capabilities if isinstance(capabilities, dict) else {}


def capability_status(profile: dict[str, Any], capability_id: str) -> str | None:
    """读取某项 capability 的 status；不存在返回 None。"""
    item = capabilities_or_empty(profile).get(capability_id)
    if isinstance(item, dict):
        status = item.get("status")
        if status in GATE_STATUS:
            return status
    return None


def ensure_out_parent(path: str | Path) -> Path:
    """确保 --out 的父目录存在。"""
    return ensure_parent(Path(path))
