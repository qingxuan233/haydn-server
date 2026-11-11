"""argparse CLI：子命令、退出码与输出约定。

退出码：
- 0 成功
- 2 用法/输入错误（argparse 或 profile/参数错误）
- 3 前置条件不满足（无 adb / 无设备 / fixture 不可用）
- 4 校验失败（validate 发现 error；--strict 下 warning 也算失败）
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable

from .adb import AdbTransport, make_transport
from .assess import assess_profile, format_assessment_human
from .detect import detect_profile
from .plan import build_plan, format_plan_markdown
from .probe import format_probe_human, probe_profile
from .profile import build_new_profile, load_and_validate, validate_profile, write_profile
from .util import (
    PreconditionError,
    RepurposeError,
    UsageError,
    find_repo_root,
    iso_now,
    load_json,
    rel_posix,
    write_json,
)
from .validate import format_validation_human, validate_repo
from .indexgen import (
    build_manifest,
    default_manifest_path,
    format_index_summary,
    write_manifest,
)

EXIT_OK = 0
EXIT_USAGE = 2
EXIT_PRECONDITION = 3
EXIT_VALIDATION = 4

EPILOG = """退出码：
  0  成功
  2  用法/输入错误（argparse 或 profile/参数错误）
  3  前置条件不满足（无 adb / 无设备 / fixture 不可用）
  4  校验失败（validate 发现 error；--strict 下 warning 也算失败）

示例：
  python -m toolkit.repurpose detect --adb-fixture toolkit/tests/fixtures/adb-haydn.json
  python -m toolkit.repurpose probe --base profiles/haydn.json --adb-fixture toolkit/tests/fixtures/adb-haydn.json --out profiles/haydn-probed.json
  python -m toolkit.repurpose assess --profile profiles/haydn-probed.json --json
  python -m toolkit.repurpose plan --profile profiles/haydn-probed.json --format md
  python -m toolkit.repurpose index --json
  python -m toolkit.repurpose validate --strict
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m toolkit.repurpose",
        description=(
            "安卓手机改造通用工具链：只读探测设备能力、离线评估改造路线（A/B/C/D）、"
            "生成阶段计划、维护 Agent 机器索引并校验内容层。零第三方依赖，不写设备。"
        ),
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--verbose", action="store_true", help="打印详细过程信息到 stderr")
    subparsers = parser.add_subparsers(dest="command", metavar="<command>", title="子命令")

    detect_parser = subparsers.add_parser(
        "detect",
        help="只读采集设备 profile 骨架（默认脱敏，默认打印 JSON）",
        description=(
            "通过只读 ADB 命令采集 identity/boot/root/kernel/hardware/storage/crypto/"
            "features/constraints 等字段，输出 repurpose.device-profile.v1 JSON。"
            "无 adb 或设备时退出码 3；--adb-fixture 可离线回放。"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    detect_parser.add_argument("--serial", help="指定目标设备序列号（多设备时必填）")
    detect_parser.add_argument("--out", help="写入 profile JSON 文件（缺省打印到 stdout）")
    detect_parser.add_argument(
        "--include-serial",
        action="store_true",
        help="在 profile 中保留设备序列号（默认脱敏为 null）",
    )
    detect_parser.add_argument("--adb-fixture", help="离线回放 fixture JSON（不连接设备）")
    detect_parser.set_defaults(handler=cmd_detect)

    probe_parser = subparsers.add_parser(
        "probe",
        help="在 profile 上补 capabilities/verdicts（只读命令）",
        description=(
            "补齐 12 项 capabilities（proot/containers/systemd/native_linux/precise_cpu/"
            "raw_network_bytes/battery_sysfs/charge_limit_shell/dumpsys/appops/usage_stats/"
            "boot_autostart）及 verdicts。无 adb 且提供 --base 时进入离线模式。"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    probe_parser.add_argument("--base", help="基础 profile JSON（可选；缺省先运行 detect）")
    probe_parser.add_argument("--out", help="写入补齐后的 profile JSON")
    probe_parser.add_argument("--adb-fixture", help="离线回放 fixture JSON")
    probe_parser.add_argument("--json", action="store_true", help="向 stdout 打印完整 JSON")
    probe_parser.set_defaults(handler=cmd_probe)

    assess_parser = subparsers.add_parser(
        "assess",
        help="离线路线评估（A/B/C/D + 门禁 + 风险 + 下一步）",
        description=(
            "根据 profile 中已证实字段输出 repurpose.assessment.v1：route/route_label/"
            "confidence/gates/blocked/alternatives/risks/next_steps/assumptions。"
            "未知字段不臆测，进入 assumptions/unknowns 并降低 confidence。"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    assess_parser.add_argument("--profile", required=True, help="device-profile JSON 路径（必填）")
    assess_parser.add_argument("--json", action="store_true", help="打印 JSON（缺省人类摘要）")
    assess_parser.set_defaults(handler=cmd_assess)

    plan_parser = subparsers.add_parser(
        "plan",
        help="生成 P0–P6 阶段计划（json/md）",
        description="按路线（auto 使用 assess 结论）输出 P0–P6：actions/deliverables/gate/exit_criteria/rollback。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    plan_parser.add_argument("--profile", required=True, help="device-profile JSON 路径（必填）")
    plan_parser.add_argument(
        "--route",
        choices=("auto", "A", "B", "C", "D"),
        default="auto",
        help="路线；auto 使用 assess 推荐（默认 auto）",
    )
    plan_parser.add_argument(
        "--format",
        choices=("json", "md"),
        default="md",
        help="输出格式（默认 md）",
    )
    plan_parser.set_defaults(handler=cmd_plan)

    new_profile_parser = subparsers.add_parser(
        "new-profile",
        help="从模板生成可编辑 profile JSON（含 unknowns 提示）",
        description="基于 toolkit/templates/device-profile.json 生成人工可填写的 profile 骨架。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    new_profile_parser.add_argument("--codename", required=True, help="设备代号（如 haydn）")
    new_profile_parser.add_argument("--out", help="写入文件（缺省打印到 stdout）")
    new_profile_parser.set_defaults(handler=cmd_new_profile)

    index_parser = subparsers.add_parser(
        "index",
        help="扫描新层 Markdown 并生成 agent-manifest.json",
        description=(
            "扫描 methodology/、pitfalls/、guardrails/、cases/ 下 .md 的 front matter，"
            "生成 repurpose.agent-manifest.v1（默认写入 <root>/agent-manifest.json）。"
            "目录缺失时跳过且不失败。"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    index_parser.add_argument("--root", help="仓库根目录（默认当前仓库根）")
    index_parser.add_argument("--out", help="manifest 输出路径（默认 <root>/agent-manifest.json）")
    index_parser.add_argument("--json", action="store_true", help="打印 JSON 摘要")
    index_parser.set_defaults(handler=cmd_index)

    validate_parser = subparsers.add_parser(
        "validate",
        help="校验 front matter/ID 唯一/相对链接/JSON/manifest 过期",
        description=(
            "检查新层 Markdown 的必需 front matter 键（id,title,type,status,audience,tags,"
            "updated,agent_hint）、ID 唯一、相对 Markdown 链接目标存在（不检查 anchor）、"
            "JSON 可解析、agent-manifest.json 是否过期。发现问题退出码 4。"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    validate_parser.add_argument("--root", help="仓库根目录（默认当前仓库根）")
    validate_parser.add_argument("--strict", action="store_true", help="将 warning 视为失败")
    validate_parser.add_argument("--json", action="store_true", help="打印 JSON 报告")
    validate_parser.set_defaults(handler=cmd_validate)

    return parser


# ---------------------------------------------------------------------------
# 输出辅助
# ---------------------------------------------------------------------------


_STDIO_UTF8 = False
"""stdio 是否已成功切换为 UTF-8（决定 JSON 输出是否可安全使用 ensure_ascii=False）。"""


def _configure_stdio() -> None:
    """把 stdout/stderr 统一为 UTF-8。

    Windows 中文环境的管道/重定向默认继承 cp936，会让包含中文的 JSON 输出不是合法
    UTF-8（下游 json.load 失败）。在 CLI 入口统一 reconfigure 为 UTF-8；跨 Python 版本
    用 try/except 兜底（StringIO 等对象没有 reconfigure）。
    """
    global _STDIO_UTF8
    utf8_ok = True
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, ValueError, OSError):
            utf8_ok = False
    _STDIO_UTF8 = utf8_ok


def _print_json(payload: Any) -> None:
    """打印 JSON。

    已成功切到 UTF-8 时保留中文（ensure_ascii=False）；无法切换时退回纯 ASCII
    （ensure_ascii=True），保证任何编码的管道都能解析。
    """
    print(json.dumps(payload, ensure_ascii=not _STDIO_UTF8, indent=2))


def _display(path: Path) -> str:
    """尽量以相对路径显示输出文件（不打印绝对路径）。"""
    try:
        return path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except (ValueError, OSError):
        return path.name


def _log(args: argparse.Namespace, message: str) -> None:
    if getattr(args, "verbose", False):
        print(f"[verbose] {message}", file=sys.stderr)


def _resolve_transport(
    adb_fixture: str | None,
    injected: Any,
    injected_factory: Callable[[], Any] | None,
) -> Any:
    """解析 transport：fixture 优先，其次测试注入，最后真实 adb。"""
    if adb_fixture:
        return make_transport(adb_fixture)
    if injected is not None:
        return injected
    if injected_factory is not None:
        return injected_factory()
    return make_transport(None)


# ---------------------------------------------------------------------------
# 子命令实现
# ---------------------------------------------------------------------------


def cmd_detect(args: argparse.Namespace, *, transport: Any = None) -> int:
    resolved = _resolve_transport(args.adb_fixture, transport, None)
    _log(args, "detect：开始只读采集")
    profile = detect_profile(
        resolved,
        serial=args.serial,
        include_serial=args.include_serial,
    )
    if args.out:
        target = write_profile(args.out, profile)
        print(f"detect 完成：已写入 {_display(target)}（serial_redacted={profile['identity']['serial_redacted']}）")
    else:
        _print_json(profile)
    return EXIT_OK


def cmd_probe(args: argparse.Namespace, *, transport: Any = None) -> int:
    base = None
    if args.base:
        base = load_and_validate(args.base)
    if args.adb_fixture:
        online_transport = make_transport(args.adb_fixture)
    elif transport is not None:
        online_transport = transport
    else:
        candidate = AdbTransport()
        online_transport = candidate if candidate.available else None

    if base is None and online_transport is None:
        raise PreconditionError(
            "probe 需要 ADB 设备，或提供 --base（离线模式）与/或 --adb-fixture",
        )
    if base is None:
        _log(args, "probe：无 --base，先执行 detect")
        base = detect_profile(online_transport)
    _log(args, f"probe：模式={'online' if online_transport is not None else 'offline'}")
    probed, mode = probe_profile(base, online_transport)
    errors = validate_profile(probed)
    if errors:
        raise UsageError("probe 结果结构校验失败：" + "；".join(errors[:5]))
    if args.out:
        target = write_profile(args.out, probed)
        _log(args, f"probe：已写入 {_display(target)}（mode={mode}）")
        if not args.json:
            print(format_probe_human(probed))
            print(f"\n已写入：{_display(target)}（probe mode={mode}）")
            return EXIT_OK
    if args.json:
        _print_json(probed)
    else:
        if args.out:
            _print_json(probed)
        else:
            print(format_probe_human(probed))
    return EXIT_OK


def cmd_assess(args: argparse.Namespace, *, transport: Any = None) -> int:
    profile = load_and_validate(args.profile)
    assessment = assess_profile(profile)
    if args.json:
        _print_json(assessment)
    else:
        print(format_assessment_human(assessment))
    return EXIT_OK


def cmd_plan(args: argparse.Namespace, *, transport: Any = None) -> int:
    profile = load_and_validate(args.profile)
    plan = build_plan(profile, args.route)
    if args.format == "json":
        _print_json(plan)
    else:
        print(format_plan_markdown(plan), end="")
    return EXIT_OK


def cmd_new_profile(args: argparse.Namespace, *, transport: Any = None) -> int:
    profile = build_new_profile(args.codename)
    if args.out:
        target = write_profile(args.out, profile)
        print(f"new-profile 完成：已写入 {_display(target)}（请补证后运行 assess）")
    else:
        _print_json(profile)
    return EXIT_OK


def cmd_index(args: argparse.Namespace, *, transport: Any = None) -> int:
    root = find_repo_root(args.root)
    target, manifest = write_manifest(root, args.out)
    if args.json:
        summary = {
            "schema": manifest["schema"],
            "generated_at": manifest["generated_at"],
            "output": rel_posix(target, root),
            "counts": manifest["counts"],
            "warnings": manifest["warnings"],
            "errors": manifest["errors"],
        }
        _print_json(summary)
    else:
        print(format_index_summary(manifest, target))
    return EXIT_OK


def cmd_validate(args: argparse.Namespace, *, transport: Any = None) -> int:
    root = find_repo_root(args.root)
    report = validate_repo(root, strict=args.strict)
    if args.json:
        _print_json(report)
    else:
        print(format_validation_human(report))
    return EXIT_OK if report["ok"] else EXIT_VALIDATION


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------


def main(
    argv: list[str] | None = None,
    *,
    transport: Any = None,
    transport_factory: Callable[[], Any] | None = None,
) -> int:
    """CLI 主入口。``transport`` / ``transport_factory`` 仅用于测试注入。"""
    _configure_stdio()
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:  # argparse 已输出 help/错误
        code = exc.code if isinstance(exc.code, int) else EXIT_USAGE
        return code

    handler = getattr(args, "handler", None)
    if handler is None:
        parser.print_help()
        return EXIT_USAGE

    _log(args, f"运行子命令：{args.command}")
    try:
        if args.command == "detect":
            return handler(args, transport=transport)
        if args.command == "probe":
            return handler(args, transport=transport)
        return handler(args)
    except RepurposeError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return exc.exit_code
    except KeyboardInterrupt:
        print("已中断（未写设备；输出可能未完整落盘）", file=sys.stderr)
        return 130


_ = iso_now, load_json, build_manifest, default_manifest_path, validate_profile
