#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check-secrets.py — 仓库内秘密/凭据模式扫描（质量门配套，只读）。

用途：在 CI 与本地质量门中拦截**明显泄露的秘密**（私钥块、云厂商/平台
固定格式令牌、授权码等）。只报告「模式命中」，不解析内容、不联网、
不写仓库文件。

用法：
    python scripts/dev/check-secrets.py [options]

选项：
    --json           机器可读 JSON 摘要（单对象）
    --output PATH    同时把报告写到 PATH（UTF-8）
    --root PATH      仓库根覆盖（默认按 __file__ 自动定位）
    --include GLOB   追加扫描的路径/目录（相对仓库根，可多次）
    --quiet          不打印逐条命中明细（仍有汇总）

退出码：0=未发现命中 / 1=发现命中。
扫描范围默认与 check-links.py 对齐（README/AGENTS/CHANGELOG + 内容层目录 + 脚本层），
并跳过 `.git`、`node_modules`、`__pycache__`、`inventory`、`profiles`、`backup`、
`tools` 等不入库或含运行期数据的目录。

设计约束：
- **规则只增不减**：删除/放行已有规则必须走 ADR 并说明理由（与 GRD-016 一致）。
- 命中行只输出「路径:行号 + 规则名」，**不输出命中的原文**，避免二次泄露。
- 允许在库内放置**明显占位值**（如 `sk-xxxxxxxx`、说明性示例），由规则宽紧度控制。
"""
from __future__ import print_function

import argparse
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))).replace("\\", "/")

DEFAULT_ROOTS = [
    "README.md", "AGENTS.md", "CHANGELOG.md",
    "methodology", "pitfalls", "guardrails", "adr", "toolkit",
    "cases", "docs", "scripts", "android-bridge",
    "2026-11-14",
]
SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", "inventory", "profiles", "backup",
    "tools", "build", "dist", ".screenshots",
}
SCAN_EXTS = {
    ".md", ".json", ".py", ".yml", ".yaml", ".sh", ".ps1", ".cjs", ".js",
    ".ts", ".txt", ".cfg", ".ini", ".conf", ".env", ".example", ".html",
    ".properties",
}
MAX_BYTES = 3_000_000

# 每条：(规则名, 正则, 说明)。正则用 re.compile；命中即报告。
RULES = [
    ("private-key-block",
     re.compile(r"-----BEGIN(?: [A-Z0-9]+)? PRIVATE KEY-----"),
     "PEM/OpenSSH 私钥块"),
    ("aws-access-key-id",
     re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
     "AWS access key id"),
    ("aws-secret-key",
     re.compile(r"(?i)aws.{0,20}secret.{0,20}[\"'=:\s]{1,5}[A-Za-z0-9/+]{40}"),
     "AWS secret access key 赋值"),
    ("github-token",
     re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36}\b"),
     "GitHub 个人/应用令牌"),
    ("github-fine-grained-pat",
     re.compile(r"\bgithub_pat_[A-Za-z0-9_]{50,}\b"),
     "GitHub 细粒度 PAT"),
    ("slack-token",
     re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b"),
     "Slack 令牌"),
    ("google-api-key",
     re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b"),
     "Google API key"),
    ("stripe-live-key",
     re.compile(r"\b(?:sk|rk)_live_[0-9A-Za-z]{16,}\b"),
     "Stripe live key"),
    ("openai-like-key",
     re.compile(r"\bsk-[A-Za-z0-9]{40,}\b"),
     "形如 sk- 的长密钥（模型/云服务）"),
    ("tailscale-authkey",
     re.compile(r"\btskey-(?:auth|client)-[A-Za-z0-9]{10,}"),
     "Tailscale 授权密钥"),
    ("quark-agent-authcode",
     re.compile(r"\bCAC-[0-9a-f]{20,}\b"),
     "夸克 AI 技能授权码"),
    ("jwt-token",
     re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
     "JWT（可能含 bearer 凭据）"),
    ("basic-auth-url",
     re.compile(r"(?i)\bhttps?://[A-Za-z0-9._%+-]+:[^\s/@]{6,}@"),
     "URL 内嵌账号口令"),
    ("password-assignment",
     re.compile(r"(?i)(?:password|passwd|secret|token|api[_-]?key|access[_-]?key)\s*[:=]\s*[\"'`][^\"'`\s]{16,}[\"'`]"),
     "疑似明文口令/令牌赋值（≥16 字符）"),
]


def iter_files(roots):
    for base in roots:
        path = os.path.join(ROOT, base)
        if os.path.isfile(path):
            yield path
            continue
        if not os.path.isdir(path):
            continue
        for dirpath, dirnames, filenames in os.walk(path):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for name in filenames:
                ext = os.path.splitext(name)[1].lower()
                if ext in SCAN_EXTS:
                    yield os.path.join(dirpath, name)


def scan(roots):
    findings = []
    scanned = 0
    for path in iter_files(roots):
        try:
            if os.path.getsize(path) > MAX_BYTES:
                continue
            with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                text = fh.read()
        except OSError:
            continue
        scanned += 1
        rel = os.path.relpath(path, ROOT).replace("\\", "/")
        for name, rx, _desc in RULES:
            for match in rx.finditer(text):
                line = text.count("\n", 0, match.start()) + 1
                findings.append({"rule": name, "path": rel, "line": line})
                if len(findings) > 200:
                    return findings, scanned, True
    return findings, scanned, False


def render_text(result, quiet=False):
    lines = []
    rules = sorted({f["rule"] for f in result["findings"]})
    lines.append("SECRET SCAN  files=%d  findings=%d  rules=%d%s"
                 % (result["files_scanned"], len(result["findings"]),
                    len(rules), "  (truncated)" if result["truncated"] else ""))
    for name in rules:
        hits = [f for f in result["findings"] if f["rule"] == name]
        lines.append("  %-24s %d" % (name, len(hits)))
    if result["findings"] and not quiet:
        lines.append("")
        lines.append("命中明细（只给路径与行号，不输出原文）：")
        for f in result["findings"]:
            lines.append("  %s:%d  [%s]" % (f["path"], f["line"], f["rule"]))
    if result["findings"]:
        lines.append("")
        lines.append("FAIL: 发现疑似秘密命中，请移出仓库并轮换凭据")
    else:
        lines.append("")
        lines.append("OK: 未发现秘密模式命中")
    return "\n".join(lines)


def main():
    global ROOT
    parser = argparse.ArgumentParser(description="repository secret-pattern scanner")
    parser.add_argument("--json", action="store_true", help="JSON summary output")
    parser.add_argument("--output", default=None, help="write report to this path")
    parser.add_argument("--root", default=None, help="repository root override")
    parser.add_argument("--include", action="append", default=[],
                        help="extra path/dir to scan (relative to repo root)")
    parser.add_argument("--quiet", action="store_true",
                        help="do not print per-hit detail lines")
    args = parser.parse_args()
    if args.root:
        ROOT = args.root.replace("\\", "/").rstrip("/")

    roots = list(DEFAULT_ROOTS) + list(args.include)
    findings, scanned, truncated = scan(roots)
    result = {
        "files_scanned": scanned,
        "findings": findings,
        "truncated": truncated,
        "rules": [name for name, _rx, _d in RULES],
    }
    text = render_text(result, quiet=args.quiet)
    print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else text)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write((json.dumps(result, ensure_ascii=False, indent=2)
                      if args.json else text) + "\n")
        print("report written to %s" % args.output)
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
