"""ADB 访问层：真实 adb 与离线 fixture 两种 Transport。

设计要点：
- 前端可注入 transport（``cli.main(argv, transport=...)`` / 各命令函数的
  ``transport`` 参数），因此单元测试与无真机环境可完全离线；
- detect/probe 只执行**只读** shell 命令，不做任何写设备操作；
- transport 输出的原始文本不打印、不落盘；profile 只保存解析后的结构化值；
- fixture JSON 属测试/离线回放数据，格式见 ``toolkit/tests/fixtures/adb-haydn.json``。
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from .util import JsonFileError, PreconditionError, SCHEMA_FIXTURE, load_json

DEFAULT_ADB_TIMEOUT = 30.0
"""单条 adb shell 命令超时（秒）。"""

_DEVICE_ERROR_MARKERS = (
    "no devices/emulators found",
    "device unauthorized",
    "unauthorized",
    "device offline",
    "error: device",
    "more than one device",
    "cannot connect",
    "not found",
)


class AdbError(PreconditionError):
    """ADB 不可用 / 无设备 / 设备错误（映射退出码 3）。"""


class AdbTransport:
    """基于本机 ``adb`` 可执行文件的只读 transport。"""

    name = "adb"

    def __init__(self, adb_path: str | None = None, timeout: float = DEFAULT_ADB_TIMEOUT) -> None:
        self.adb_path = adb_path or shutil.which("adb")
        self.timeout = timeout

    @property
    def available(self) -> bool:
        return bool(self.adb_path)

    def _run(self, argv: list[str]) -> str:
        if not self.available:
            raise AdbError("未找到 adb 可执行文件：请安装 platform-tools 或设置 PATH / ADB_PATH")
        try:
            completed = subprocess.run(
                argv,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.timeout,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise AdbError(f"adb 调用失败（{exc.__class__.__name__}），请检查 platform-tools") from exc
        stderr = (completed.stderr or "").strip()
        lowered = stderr.lower()
        if stderr and any(marker in lowered for marker in _DEVICE_ERROR_MARKERS):
            raise AdbError(_translate_adb_error(stderr))
        return (completed.stdout or "").strip("\r\n")

    def devices(self) -> list[dict[str, str]]:
        """返回 ``[{"serial", "state", "model", ...}]``；不含任何敏感值的额外打印。"""
        output = self._run([self.adb_path or "adb", "devices", "-l"])
        devices: list[dict[str, str]] = []
        for line in output.splitlines():
            line = line.strip()
            if not line or line.startswith("List of devices"):
                continue
            parts = line.split()
            if len(parts) < 2:
                continue
            entry: dict[str, str] = {"serial": parts[0], "state": parts[1]}
            for token in parts[2:]:
                if ":" in token:
                    key, value = token.split(":", 1)
                    entry[key] = value
            devices.append(entry)
        return devices

    def shell(self, command: str, serial: str | None = None) -> str:
        """执行 ``adb shell <command>`` 并返回原始 stdout（不做敏感值过滤）。"""
        argv = [self.adb_path or "adb"]
        if serial:
            argv.extend(["-s", serial])
        argv.extend(["shell", command])
        return self._run(argv)


class FixtureTransport:
    """离线回放 transport：从 fixture JSON 读取设备属性与命令输出。

    fixture 结构（``repurpose.adb-fixture.v1``）::

        {
          "fixture_schema": "repurpose.adb-fixture.v1",
          "captured_at": "2026-11-11T...Z",
          "devices": [{"serial": "...", "state": "device"}],
          "props": {"ro.product.device": "haydn", ...},
          "commands": {"uname -a": "Linux ...", "df -k": "..."}
        }
    """

    name = "fixture"

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        try:
            payload = load_json(self.path)
        except JsonFileError as exc:
            raise PreconditionError(f"无法加载 adb fixture（{exc}）") from exc
        if not isinstance(payload, dict):
            raise PreconditionError("adb fixture 顶层必须是 JSON object")
        self.payload: dict[str, Any] = payload
        fixture_schema = payload.get("fixture_schema")
        if fixture_schema and fixture_schema != SCHEMA_FIXTURE:
            raise PreconditionError(
                f"adb fixture schema 不受支持：{fixture_schema}（期望 {SCHEMA_FIXTURE}）"
            )
        self._devices = _normalize_devices(payload.get("devices"))
        self._props = payload.get("props") if isinstance(payload.get("props"), dict) else {}
        commands = payload.get("commands") if isinstance(payload.get("commands"), dict) else {}
        self._commands: dict[str, str] = {
            str(key): "" if value is None else str(value) for key, value in commands.items()
        }

    @property
    def available(self) -> bool:
        return True

    @property
    def captured_at(self) -> str | None:
        value = self.payload.get("captured_at")
        return value if isinstance(value, str) else None

    @property
    def fixture_name(self) -> str:
        return self.path.name

    def devices(self) -> list[dict[str, str]]:
        return [dict(device) for device in self._devices]

    def shell(self, command: str, serial: str | None = None) -> str:
        serials = {device["serial"] for device in self._devices}
        if serial and serial not in serials:
            raise AdbError("指定的 --serial 不在 fixture 设备列表中")
        normalized = command.strip()
        if normalized == "getprop":
            return self._render_getprop()
        if normalized.startswith("getprop "):
            key = normalized.split(None, 1)[1].strip()
            return str(self._props.get(key, ""))
        if normalized in self._commands:
            return self._commands[normalized]
        # 兼容把 "adb shell " 前缀写进 fixture 的情况
        if normalized.startswith("adb shell "):
            inner = normalized[len("adb shell ") :]
            return self.shell(inner, serial=serial)
        return ""

    def _render_getprop(self) -> str:
        lines = [f"[{key}]: [{value}]" for key, value in self._props.items()]
        return "\n".join(lines)


def _normalize_devices(raw: Any) -> list[dict[str, str]]:
    """把 fixture 中 devices 的多种写法归一到 dict 列表。"""
    if not isinstance(raw, list) or not raw:
        return [{"serial": "fixture-device", "state": "device"}]
    normalized: list[dict[str, str]] = []
    for item in raw:
        if isinstance(item, str):
            normalized.append({"serial": item, "state": "device"})
        elif isinstance(item, dict):
            entry = {str(key): str(value) for key, value in item.items()}
            entry.setdefault("state", "device")
            entry.setdefault("serial", "fixture-device")
            normalized.append(entry)
    return normalized or [{"serial": "fixture-device", "state": "device"}]


def _translate_adb_error(stderr: str) -> str:
    """把 adb 英文错误翻译成可操作的中文提示（不包含设备序列号）。"""
    lowered = stderr.lower()
    if "unauthorized" in lowered:
        return "设备未授权：请在手机上确认「允许 USB 调试」后重试"
    if "offline" in lowered:
        return "设备处于 offline 状态：请重新插拔 USB 或重启 adb server"
    if "more than one device" in lowered:
        return "检测到多台设备：请用 --serial 指定目标设备"
    if "no devices" in lowered or "not found" in lowered:
        return "未发现已连接的 Android 设备：请检查数据线、USB 调试开关与驱动"
    return "adb 返回错误（已过滤设备敏感信息）"


def resolve_device(transport: Any, serial: str | None = None) -> str:
    """选择唯一在线设备；多设备且未指定 serial 时抛 AdbError。"""
    devices = transport.devices()
    online = [device for device in devices if device.get("state") == "device"]
    serials = [device.get("serial", "") for device in online]
    if serial:
        if serial not in serials:
            raise AdbError("指定的 --serial 不在当前在线设备列表中")
        return serial
    if not online:
        raise AdbError("未发现已授权的在线设备：请检查 USB 调试授权与数据线")
    if len(online) > 1:
        raise AdbError("检测到多台在线设备：请用 --serial 指定目标设备")
    return online[0]["serial"]


def make_transport(adb_fixture: str | None = None, *, adb_path: str | None = None) -> Any:
    """按参数构造 transport；fixture 优先（离线可重复）。"""
    if adb_fixture:
        fixture_path = Path(adb_fixture)
        if not fixture_path.is_file():
            raise PreconditionError("--adb-fixture 文件不存在")
        return FixtureTransport(fixture_path)
    transport = AdbTransport(adb_path=adb_path)
    if not transport.available:
        raise PreconditionError(
            "未找到 adb：无法连接设备。可改用 --adb-fixture 回放离线样本（无真机/无 adb 环境）"
        )
    return transport


def read_fixture_command(fixture: FixtureTransport, command: str) -> str:
    """读取 fixture 中某条命令的原始输出（缺失时返回空串）。"""
    return fixture.shell(command)


_ = json  # 保持 typing/序列化意图说明；本模块不直接 dump 敏感原文
