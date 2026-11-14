"""argparse CLI：子命令、退出码与输出约定。

退出码：
- 0 成功 / preflight 全绿
- 2 用法/输入错误（argparse 或 profile/参数错误）
- 3 前置条件不满足（无 adb / 无设备 / fixture 不可用）；preflight 存在 SKIPPED 步骤
  （--skip-tests/--skip-links/--no-index 或 check-links 脚本缺失）；
- 4 校验失败（validate 发现 error；rootcheck --strict 非 tech-ready；rescue-kit --verify
  不一致；index --check 生成物不一致；preflight 任一步 FAILED；--strict 下 warning 也算失败）
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable

from .adb import AdbTransport, make_transport
from .assess import assess_profile, format_assessment_human
from .detect import detect_profile
from .plan import build_plan, format_plan_markdown
from .probe import format_probe_human, probe_profile
from .rescuekit import (
    format_manifest_human,
    format_verify_human,
    verify_manifest,
    write_manifest,
)
from .rootcheck import build_rootcheck, format_rootcheck_human
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
    check_bundle,
    format_index_check_human,
    format_index_summary,
    write_bundle,
)

EXIT_OK = 0
EXIT_USAGE = 2
EXIT_PRECONDITION = 3
EXIT_VALIDATION = 4

SCHEMA_PREFLIGHT = "repurpose.preflight.v1"
"""``preflight --json`` 报告 schema。"""

PREFLIGHT_CHECK_LINKS_SCRIPT = "scripts/dev/check-links.py"
"""仍与其他步骤串联的相对链接质量门（冻结例外，可随文档结构维护）。"""

EPILOG = """退出码：
  0  成功 / preflight 全绿
  2  用法/输入错误（argparse 或 profile/参数错误）
  3  前置条件不满足（无 adb / 无设备 / fixture 不可用）；preflight 存在 SKIPPED 步骤
  4  校验失败（validate 发现 error / rootcheck --strict 非 tech-ready / rescue-kit --verify 不一致 /
     index --check 不一致 / preflight 任一步 FAILED；--strict 下 warning 也算失败）

示例：
  python -m toolkit.repurpose detect --adb-fixture toolkit/tests/fixtures/adb-haydn.json
  python -m toolkit.repurpose probe --base profiles/haydn.json --adb-fixture toolkit/tests/fixtures/adb-haydn.json --out profiles/haydn-probed.json
  python -m toolkit.repurpose assess --profile profiles/haydn-probed.json --json
  python -m toolkit.repurpose plan --profile profiles/haydn-probed.json --format md
  python -m toolkit.repurpose rootcheck --profile cases/ace-pro-pgp110/profile.json --json
  python -m toolkit.repurpose rescue-kit --dir backup/rescue --init
  python -m toolkit.repurpose rescue-kit --dir backup/rescue --verify
  python -m toolkit.repurpose index
  python -m toolkit.repurpose index --check
  python -m toolkit.repurpose validate --strict
  python -m toolkit.repurpose preflight
  python -m toolkit.repurpose preflight --no-index --json
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

    rootcheck_parser = subparsers.add_parser(
        "rootcheck",
        help="离线检查 Root 实验设备技术姿态（不替代授权/演练人工确认）",
        description=(
            "消费 repurpose.device-profile.v1，输出 repurpose.rootcheck.v1："
            "bootloader/AVB/verity/SELinux/Root 管理器/管理器唯一性/内核前提/分区布局/"
            "ARB 禁止批次等技术项 + 授权/救援/数据/固件冻结/演练/su 与网络基线等人工项。"
            "只读、离线；不改变 assess 的路线与门禁顺序。--strict 在非 tech-ready 时退出 4。"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    rootcheck_parser.add_argument("--profile", required=True, help="device-profile JSON 路径（必填）")
    rootcheck_parser.add_argument("--json", action="store_true", help="打印 JSON（缺省人类摘要）")
    rootcheck_parser.add_argument(
        "--strict",
        action="store_true",
        help="tech_ready=false 时退出 4（供 CI/门禁消费）",
    )
    rootcheck_parser.set_defaults(handler=cmd_rootcheck)

    rescue_parser = subparsers.add_parser(
        "rescue-kit",
        help="离线生成/校验救援包 SHA-256 清单（G-L1 辅助）",
        description=(
            "对指定目录生成 rescue-manifest.json（相对路径 + sha256），或校验目录与清单一致。"
            "只读文件/只写清单，不连接设备；--verify 发现缺失/新增/哈希不一致时退出 4。"
            "清单不存绝对路径/凭据；版本匹配与救援演练仍需人工核对。"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    rescue_parser.add_argument("--dir", required=True, help="救援包目录（必填）")
    rescue_group = rescue_parser.add_mutually_exclusive_group(required=True)
    rescue_group.add_argument("--init", action="store_true", help="生成清单（覆盖已有清单）")
    rescue_group.add_argument("--verify", action="store_true", help="按清单校验目录")
    rescue_parser.add_argument("--notes", default="", help="--init 时写入清单的备注（不得含凭据）")
    rescue_parser.add_argument("--force", action="store_true", help="--init 时允许覆盖已存在清单（先核对来源/版本）")
    rescue_parser.add_argument("--json", action="store_true", help="打印 JSON（init 摘要/verify 报告）")
    rescue_parser.set_defaults(handler=cmd_rescue_kit)

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
        help="重建根摘要 agent-manifest.json + agent-manifest.d/ 四层分片",
        description=(
            "扫描 methodology/、pitfalls/、guardrails/、cases/ 下 .md 的 front matter，"
            "生成根摘要（repurpose.agent-manifest.v1，≤160 行，含 shards 映射）与按层分片"
            "（agent-manifest.d/{methodology,pitfalls,guardrails,case-studies}.json，"
            "repurpose.manifest-shard.v1，≤300 行/≤32KB/≤40 条）。目录缺失时跳过且不失败；"
            "旧分片（本工具 schema 标记）会被清理。"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    index_parser.add_argument("--root", help="仓库根目录（默认当前仓库根）")
    index_parser.add_argument("--out", help="manifest 输出路径（默认 <root>/agent-manifest.json）")
    index_parser.add_argument(
        "--check",
        action="store_true",
        help="只读比较：内存重建生成物并与磁盘 agent-manifest.json/分片比对（不写盘，不一致 exit 4）",
    )
    index_parser.add_argument("--json", action="store_true", help="打印 JSON 摘要")
    index_parser.set_defaults(handler=cmd_index)

    validate_parser = subparsers.add_parser(
        "validate",
        help="校验 front matter/ID/相对链接/JSON/协议/命名/PIT/ADR/backlog/归档/manifest",
        description=(
            "检查新层 Markdown 的必需 front matter 键（id,title,type,status,audience,tags,"
            "updated,agent_hint）、ID 唯一、相对 Markdown 链接目标存在（不检查 anchor）、"
            "JSON 可解析、AGENTS.md 协议章节/版本/哨兵/体积、新层命名、PIT/ADR/CHANGELOG 归档/"
            "backlog schema 与语义、agent-manifest.json 与分片一致性。发现问题退出码 4。"
            "索引一致性以内容机检为准，不依赖文件 mtime（CI 安全）；本地调试可加 --mtime-check。"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    validate_parser.add_argument("--root", help="仓库根目录（默认当前仓库根）")
    validate_parser.add_argument("--strict", action="store_true", help="将 warning 视为失败")
    validate_parser.add_argument(
        "--mtime-check",
        action="store_true",
        help="额外按文件 mtime 判定 manifest 过期（MANIFEST_STALE；默认关闭，CI/新 checkout 不应开启）",
    )
    validate_parser.add_argument("--json", action="store_true", help="打印 JSON 报告")
    validate_parser.set_defaults(handler=cmd_validate)

    preflight_parser = subparsers.add_parser(
        "preflight",
        help="统一质量门：index → validate --strict → unittest → check-links",
        description=(
            "串联质量门并输出步骤表（name/status/耗时/摘要）：index（--no-index 可跳过）→ "
            "validate --strict → python -m unittest discover -s toolkit/tests -t . → "
            "python scripts/dev/check-links.py --strict-anchors（脚本缺失时 SKIPPED）。"
            "退出码三态契约：0 全绿 / 3 存在 SKIPPED（CI 可裁剪）/ 4 任一步 FAILED。"
            "只读检查（除 index 写生成物）；不连接设备、不打印敏感值。"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    preflight_parser.add_argument("--root", help="仓库根目录（默认当前仓库根）")
    preflight_parser.add_argument("--no-index", action="store_true", help="跳过 index 步骤（CI 用已提交生成物）")
    preflight_parser.add_argument("--skip-tests", action="store_true", help="跳过 unittest 步骤（快速编排检查）")
    preflight_parser.add_argument("--skip-links", action="store_true", help="跳过 check-links 步骤")
    preflight_parser.add_argument("--json", action="store_true", help="打印 repurpose.preflight.v1 JSON")
    preflight_parser.set_defaults(handler=cmd_preflight)

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


def cmd_rootcheck(args: argparse.Namespace, *, transport: Any = None) -> int:
    _ = transport  # rootcheck 离线：不接触设备
    profile = load_and_validate(args.profile)
    report = build_rootcheck(profile)
    if args.json:
        _print_json(report)
    else:
        print(format_rootcheck_human(report))
    if args.strict and not report["tech_ready"]:
        return EXIT_VALIDATION
    return EXIT_OK


def cmd_rescue_kit(args: argparse.Namespace, *, transport: Any = None) -> int:
    _ = transport  # rescue-kit 只操作本地目录
    if args.init:
        target, manifest = write_manifest(args.dir, notes=args.notes, force=args.force)
        if args.json:
            _print_json(manifest)
        else:
            print(format_manifest_human(manifest))
            print(f"已写入：{_display(target)}")
        return EXIT_OK
    report = verify_manifest(args.dir)
    if args.json:
        _print_json(report)
    else:
        print(format_verify_human(report))
    return EXIT_OK if report["ok"] else EXIT_VALIDATION


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
    if getattr(args, "check", False):
        report = check_bundle(root)
        if args.json:
            _print_json(report)
        else:
            print(format_index_check_human(report))
        return EXIT_OK if report["ok"] else EXIT_VALIDATION
    info = write_bundle(root, args.out)
    manifest = info["manifest"]
    if args.json:
        summary = {
            "schema": manifest["schema"],
            "generated_at": manifest["generated_at"],
            "written": info.get("written", True),
            "output": info["root"]["path"],
            "root": info["root"],
            "shards": info["shards"],
            "counts": manifest["counts"],
            "removed_shards": info["removed_shards"],
            "warnings": info["warnings"],
            "errors": info["errors"],
        }
        _print_json(summary)
    else:
        print(format_index_summary(info))
    return EXIT_OK


def cmd_validate(args: argparse.Namespace, *, transport: Any = None) -> int:
    root = find_repo_root(args.root)
    report = validate_repo(root, strict=args.strict, mtime_check=getattr(args, "mtime_check", False))
    if args.json:
        _print_json(report)
    else:
        print(format_validation_human(report))
    return EXIT_OK if report["ok"] else EXIT_VALIDATION


# ---------------------------------------------------------------------------
# preflight：统一质量门（index → validate --strict → unittest → check-links）
# ---------------------------------------------------------------------------


def _run_external(command: list[str], cwd: Path, *, timeout: int = 900) -> tuple[int, str]:
    """运行外部步骤（unittest / check-links），捕获 stdout+stderr 文本。

    使用 ``sys.executable`` 保证与当前解释器一致；UTF-8 环境变量避免 Windows cp936
    管道把中文测试输出变成非法编码。执行失败（脚本不存在/超时）按非零返回。
    """
    env = dict(os.environ)
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    try:
        completed = subprocess.run(
            command,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            timeout=timeout,
        )
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        return EXIT_VALIDATION, f"无法执行外部步骤：{exc.__class__.__name__}"
    return completed.returncode, (completed.stdout or "") + (completed.stderr or "")


def _tail_summary(output: str, *, lines: int = 3, limit: int = 200) -> str:
    content = [line.strip() for line in output.splitlines() if line.strip()]
    if not content:
        return "无输出"
    return " / ".join(content[-lines:])[:limit]


def _validate_step_summary(report: dict[str, Any]) -> str:
    summary = (
        f"errors={report['error_count']} warnings={report['warning_count']} "
        f"advisories={report.get('advisory_count', 0)} strict={report['strict']}"
    )
    if report["issues"]:
        first = report["issues"][0]
        summary += f"；首条：{first['code']} {first['path']}"
    return summary


def _unittest_step_summary(returncode: int, output: str) -> str:
    match = re.search(r"Ran (\d+) tests?", output)
    count = match.group(1) if match else "?"
    if returncode == 0:
        return f"{count} 项测试 OK"
    tail = _tail_summary(output)
    return f"{count} 项测试 FAILED；{tail}" if tail else f"{count} 项测试 FAILED"


def _preflight_step(name: str, status: str, started: float, summary: str) -> dict[str, Any]:
    return {
        "name": name,
        "status": status,
        "duration_ms": int((time.perf_counter() - started) * 1000),
        "summary": summary,
    }


def format_preflight_human(report: dict[str, Any]) -> str:
    """人类可读 preflight 步骤表：name/status/耗时/摘要 + 失败定位。"""
    status = "OK" if report["ok"] else ("FAILED" if report["failed"] else "SKIPPED")
    lines = [f"preflight 结果：{status}（0=全绿 / 3=有跳过 / 4=失败）"]
    lines.append(f"  {'步骤':<12}{'状态':<9}{'耗时':>8}  摘要")
    for step in report["steps"]:
        lines.append(
            f"  {step['name']:<12}{step['status']:<9}{step['duration_ms']:>6}ms  {step['summary']}"
        )
    if report["failed"]:
        lines.append("失败详情：")
        for step in report["steps"]:
            if step["status"] == "FAILED":
                lines.append(f"  - {step['name']}: {step['summary']}")
    lines.append(
        f"结论：skipped={report['skipped']} failed={report['failed']} exit={report['exit_code']}"
    )
    return "\n".join(lines)


def cmd_preflight(args: argparse.Namespace, *, transport: Any = None) -> int:
    _ = transport  # preflight 只读本地仓库，不接触设备
    root = find_repo_root(args.root)
    steps: list[dict[str, Any]] = []
    failed = 0
    skipped = 0

    # 1) index（除非 --no-index；CI 用已提交生成物）
    started = time.perf_counter()
    if args.no_index:
        steps.append(_preflight_step("index", "SKIPPED", started, "按 --no-index 跳过（CI 用已提交生成物）"))
        skipped += 1
    else:
        info = write_bundle(root)
        status = "FAILED" if info.get("errors") else "OK"
        summary = (
            f"根摘要 {info['root']['lines']} 行 / 分片 {sum(len(item['parts']) for item in info['shards'].values())} 个"
            + ("；内容未变，未重写（保留原 generated_at）" if info.get("written") is False else "")
            + (f"；errors：{_tail_summary(' / '.join(info['errors']))}" if info.get("errors") else "")
        )
        steps.append(_preflight_step("index", status, started, summary))
        if status == "FAILED":
            failed += 1

    # 2) validate --strict（--no-index 时仍检查提交版 manifest 的内容一致性）
    started = time.perf_counter()
    report = validate_repo(root, strict=True)
    status = "OK" if report["ok"] else "FAILED"
    steps.append(_preflight_step("validate", status, started, _validate_step_summary(report)))
    if status == "FAILED":
        failed += 1

    # 3) unittest（--skip-tests 可裁剪）
    started = time.perf_counter()
    if args.skip_tests:
        steps.append(_preflight_step("unittest", "SKIPPED", started, "按 --skip-tests 跳过"))
        skipped += 1
    else:
        code, output = _run_external(
            [sys.executable, "-m", "unittest", "discover", "-s", "toolkit/tests", "-t", "."],
            root,
        )
        status = "OK" if code == 0 else "FAILED"
        steps.append(_preflight_step("unittest", status, started, _unittest_step_summary(code, output)))
        if status == "FAILED":
            failed += 1

    # 4) check-links（--skip-links 可裁剪；脚本缺失降级 SKIPPED）
    started = time.perf_counter()
    script = root / PREFLIGHT_CHECK_LINKS_SCRIPT
    if args.skip_links:
        steps.append(_preflight_step("check-links", "SKIPPED", started, "按 --skip-links 跳过"))
        skipped += 1
    elif not script.is_file():
        steps.append(
            _preflight_step("check-links", "SKIPPED", started, f"脚本不存在：{PREFLIGHT_CHECK_LINKS_SCRIPT}")
        )
        skipped += 1
    else:
        code, output = _run_external(
            [sys.executable, PREFLIGHT_CHECK_LINKS_SCRIPT, "--strict-anchors"], root
        )
        status = "OK" if code == 0 else "FAILED"
        summary = "相对链接全部有效" if code == 0 else "check-links 失败：" + _tail_summary(output)
        steps.append(_preflight_step("check-links", status, started, summary))
        if status == "FAILED":
            failed += 1

    exit_code = EXIT_VALIDATION if failed else (EXIT_PRECONDITION if skipped else EXIT_OK)
    payload: dict[str, Any] = {
        "schema": SCHEMA_PREFLIGHT,
        "generated_at": iso_now(),
        "root": ".",
        "ok": exit_code == EXIT_OK,
        "exit_code": exit_code,
        "steps": steps,
        "skipped": skipped,
        "failed": failed,
    }
    if args.json:
        _print_json(payload)
    else:
        print(format_preflight_human(payload))
    return exit_code


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


_ = iso_now, load_json, rel_posix, write_json, validate_profile
