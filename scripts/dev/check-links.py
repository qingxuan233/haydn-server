#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check-links.py — Markdown relative-link / anchor / bare-path validator (T5 v2).

Scans repository Markdown files and validates every relative link target
(file/directory existence) and, optionally, heading anchors.  External URLs,
absolute paths and anchor-only links are classified (never errors).

Usage:
    python scripts/dev/check-links.py [options]

Options:
    --strict-anchors   Missing `#anchor` in a target .md becomes an ERROR
                       (default: WARN).
    --bare-paths       Additionally scan non-link text for legacy bare paths
                       (old repo name / old docs numbering / old script paths /
                       old junction paths).  Reported as WARN only.
    --json             Machine-readable JSON summary (single object).
    --output PATH      Also write the text/JSON report to PATH (UTF-8).
    --quiet            Do not print the per-group table (findings still print).
    --root PATH        Repository root override (default: auto from __file__).

Exit code: 0 if there is no missing link target (and no anchor error in strict
mode), 1 otherwise.

Notes:
 - Fenced code blocks (``` / ~~~) and inline code spans are ignored.
 - Angle-bracket targets `[x](<path with space>)` and optional `"title"` are
   supported; image links are checked too (assets must exist).
 - Anchor generation follows GitHub's rule for headings (CJK kept, punctuation
   dropped, spaces -> '-', duplicate headings get -1/-2 suffixes).

The script never writes anything except the optional --output report.
"""
from __future__ import print_function

import argparse
import json
import os
import re
import sys
import urllib.parse
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))).replace("\\", "/")

SCAN_ROOTS = ["README.md", "AGENTS.md", "CHANGELOG.md", "docs", "android-bridge",
              "scripts", "methodology", "pitfalls", "guardrails", "toolkit", "cases",
              "adr", "changelog", "tools/README.md", "inventory/README.md"]
SKIP_DIR_NAMES = {".git", "backup", "inventory", "tools", "node_modules",
                  "__pycache__", "build", "android-sdk", "platform-tools",
                  "apks", "termux", "termux-boot", "mi-unlock", "magisk"}

FENCE_RE = re.compile(r"^\s*(```|~~~)")
HEADING_RE = re.compile(r"^#{1,6}\s+(.*)$")
INLINE_CODE_RE = re.compile(r"`[^`]*`")
COMMENT_RE = re.compile(r"<!--.*?-->")
SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.\-]*:")
WIN_ABS_RE = re.compile(r"^[A-Za-z]:[\\/]")
LINK_START_RE = re.compile(r"\]\(")
DOC_GROUPS = ("00-overview", "10-device", "20-server", "30-dsh",
              "40-console", "50-bridge", "90-archive", "assets")


def rel_of(path):
    return os.path.relpath(path, ROOT).replace(os.sep, "/")


def group_of(relpath):
    parts = relpath.split("/")
    if parts[0] == "docs":
        if len(parts) >= 2 and parts[1] in DOC_GROUPS:
            return "docs/" + parts[1]
        return "docs"
    if parts[0] == "android-bridge":
        return "android-bridge"
    if parts[0] == "scripts":
        if len(parts) >= 3:
            return "scripts/" + parts[1]
        return "scripts"
    if parts[0] in ("tools", "inventory"):
        return parts[0]
    if parts[0] in ("methodology", "pitfalls", "guardrails", "toolkit", "cases", "adr"):
        return parts[0]
    return "repo-root"


def md_files():
    found = []

    def add(p):
        if p.lower().endswith(".md") and os.path.isfile(p):
            found.append(p)

    for base in SCAN_ROOTS:
        p = os.path.normpath(os.path.join(ROOT, base))
        if os.path.isfile(p):
            add(p)
        elif os.path.isdir(p):
            for dirpath, dirnames, filenames in os.walk(p):
                dirnames[:] = [d for d in dirnames if d not in SKIP_DIR_NAMES]
                for fn in filenames:
                    if fn.lower().endswith(".md"):
                        found.append(os.path.join(dirpath, fn))
    return sorted(set(found))


def strip_code(line):
    """Remove inline code spans and single-line HTML comments."""
    line = COMMENT_RE.sub(lambda m: " " * len(m.group(0)), line)
    line = INLINE_CODE_RE.sub(lambda m: " " * len(m.group(0)), line)
    return line


def find_links(line):
    """Return [(url, is_image)] for inline Markdown links on one line."""
    results = []
    for m in LINK_START_RE.finditer(line):
        is_image = m.start() > 0 and line[m.start() - 1] == "!"
        i = m.end()
        n = len(line)
        while i < n and line[i] in " \t":
            i += 1
        if i >= n:
            continue
        if line[i] == "<":
            j = line.find(">", i + 1)
            if j == -1:
                continue
            url = line[i + 1:j]
            i = j + 1
        else:
            start = i
            depth = 0
            while i < n:
                c = line[i]
                if c == "\\":
                    i += 2
                    continue
                if c == "(":
                    depth += 1
                    i += 1
                    continue
                if c == ")":
                    if depth == 0:
                        break
                    depth -= 1
                    i += 1
                    continue
                if c in " \t":
                    break
                i += 1
            url = line[start:i]
        j = i
        while j < n and line[j] in " \t":
            j += 1
        if j < n and line[j] in "\"'":
            quote = line[j]
            k = line.find(quote, j + 1)
            if k != -1:
                j = k + 1
        while j < n and line[j] in " \t":
            j += 1
        if j < n and line[j] == ")" and url:
            results.append((url, is_image))
    return results


def anchor_of(text):
    """Normalise heading text into the GitHub anchor slug."""
    text = text.strip()
    text = re.sub(r"<!--.*?-->", "", text)
    text = re.sub(r"<[^>]*>", "", text)
    text = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"[*_~`#]", "", text)
    text = text.lower()
    out = []
    for ch in text:
        if ch.isalnum() or ch in "_-" or ord(ch) > 127:
            out.append(ch)
        elif ch == " ":
            out.append("-")
    return "".join(out)


def anchors_of(path):
    """Set of anchors GitHub would generate for this Markdown file."""
    base_count = defaultdict(int)
    res = set()
    in_fence = False
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            lines = fh.read().split("\n")
    except OSError:
        return res
    for line in lines:
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = HEADING_RE.match(line)
        if not m:
            continue
        base = anchor_of(m.group(1))
        if not base:
            continue
        n = base_count[base]
        base_count[base] += 1
        res.add(base if n == 0 else "%s-%d" % (base, n))
    return res


def classify_target(current_rel, url):
    """Classify a link target -> dict(kind=anchor|external|absolute|internal)."""
    if url.startswith("#"):
        return {"kind": "anchor", "anchor": urllib.parse.unquote(url[1:])}
    if url.startswith("//") or SCHEME_RE.match(url):
        return {"kind": "external", "url": url}
    if url.startswith("/") or url.startswith("\\\\") or WIN_ABS_RE.match(url):
        return {"kind": "absolute", "url": url}
    raw, _, anchor = url.partition("#")
    raw = raw.split("?", 1)[0]
    anchor = urllib.parse.unquote(anchor) if anchor else ""
    if not raw and anchor:
        return {"kind": "anchor", "anchor": anchor}
    backslash = "\\" in raw
    raw = raw.replace("\\", "/")
    raw = urllib.parse.unquote(raw)
    target_rel = os.path.normpath(
        os.path.join(os.path.dirname(current_rel), raw)).replace(os.sep, "/")
    return {"kind": "internal", "target": target_rel, "anchor": anchor,
            "raw": raw, "backslash": backslash}


def check(strict_anchors=False, bare_paths=False):
    groups = defaultdict(lambda: defaultdict(int))
    errors, warnings, infos = [], [], []
    anchor_cache = {}
    md_list = md_files()

    for path in md_list:
        current_rel = rel_of(path)
        g = group_of(current_rel)
        groups[g]["files"] += 1
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                text = fh.read()
        except OSError as exc:
            errors.append("%s: cannot read (%s)" % (current_rel, exc))
            continue
        in_fence = False
        in_comment = False
        for lineno, line in enumerate(text.split("\n"), 1):
            if FENCE_RE.match(line):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            if in_comment:
                if "-->" in line:
                    in_comment = False
                continue
            if "<!--" in line:
                before, _, after = line.partition("<!--")
                if "-->" not in after:
                    in_comment = True
                line = before
            scan = strip_code(line)
            links = find_links(scan)
            for url, is_image in links:
                groups[g]["links"] += 1
                if is_image:
                    groups[g]["images"] += 1
                kind = classify_target(current_rel, url)
                if kind["kind"] == "external":
                    groups[g]["external"] += 1
                    continue
                if kind["kind"] == "absolute":
                    groups[g]["absolute"] += 1
                    warnings.append("%s:%s: absolute path link (ignored) %s"
                                    % (current_rel, lineno, url))
                    continue
                if kind["kind"] == "anchor":
                    groups[g]["anchor_only"] += 1
                    key = kind.get("anchor")
                    if key:
                        if current_rel not in anchor_cache:
                            anchor_cache[current_rel] = anchors_of(path)
                        if key not in anchor_cache[current_rel]:
                            msg = ("%s:%s: missing local anchor #%s"
                                   % (current_rel, lineno, key))
                            (errors if strict_anchors else warnings).append(msg)
                        else:
                            groups[g]["ok_anchors"] += 1
                    continue
                target_rel = kind["target"]
                groups[g]["internal"] += 1
                target_abs = os.path.join(ROOT, target_rel)
                if kind.get("backslash"):
                    warnings.append("%s:%s: backslash in relative link %s"
                                    % (current_rel, lineno, url))
                if not os.path.isfile(target_abs):
                    if os.path.isdir(target_abs):
                        groups[g]["dir_ok"] += 1
                        infos.append("%s:%s: link to directory %s"
                                     % (current_rel, lineno, url))
                        continue
                    groups[g]["missing"] += 1
                    errors.append("%s:%s: missing target %s  (resolved: %s)"
                                  % (current_rel, lineno, url, target_rel))
                    continue
                groups[g]["ok_targets"] += 1
                if kind.get("anchor") and target_rel.lower().endswith(".md"):
                    if target_rel not in anchor_cache:
                        anchor_cache[target_rel] = anchors_of(target_abs)
                    if kind["anchor"] not in anchor_cache[target_rel]:
                        groups[g]["bad_anchors"] += 1
                        msg = ("%s:%s: missing anchor #%s in %s"
                               % (current_rel, lineno, kind["anchor"],
                                  target_rel))
                        (errors if strict_anchors else warnings).append(msg)
                    else:
                        groups[g]["ok_anchors"] += 1
            if bare_paths and not links:
                for note in scan_bare_paths(current_rel, lineno, scan):
                    warnings.append(note)
                    groups[g]["bare_paths"] += 1

    return {
        "root": ROOT,
        "md_files": len(md_list),
        "strict_anchors": strict_anchors,
        "bare_paths": bare_paths,
        "groups": {k: dict(v) for k, v in sorted(groups.items())},
        "errors": errors,
        "warnings": warnings,
        "infos": infos,
    }


LEGACY_BARE_PATTERNS = [
    ("old-repo-name", re.compile("\u624b\u673a\u4f18\u5316")),
    ("old-junction", re.compile(r"D:[\\/]+(?:android-sdk|bridge-src)",
                                re.IGNORECASE)),
    ("old-doc-dir", re.compile(r"docs[\\/]+(?:images|archive|research)[\\/]+")),
    ("old-doc-file", re.compile(
        r"docs[\\/]+(\d{2})-(?!(?:overview|device|server|dsh|console|bridge|archive)\b)")),
    ("bare-doc-number", re.compile(
        r"docs[\\/]+(\d{2})(?![\w-]|-(?:overview|device|server|dsh|console|bridge|archive))")),
    ("old-script-root", re.compile(r"scripts[\\/]+([A-Za-z0-9_-]+\.[A-Za-z]+)")),
]


def scan_bare_paths(current_rel, lineno, line):
    notes = []
    for name, rx in LEGACY_BARE_PATTERNS:
        m = rx.search(line)
        if not m:
            continue
        if name == "old-script-root":
            ext = m.group(1).rsplit(".", 1)[-1].lower()
            if ext not in ("ps1", "py", "sh"):
                continue
        txt = line.strip()
        if len(txt) > 120:
            txt = txt[:117] + "..."
        notes.append("%s:%s: [%s] %s" % (current_rel, lineno, name, txt))
    return notes


def render_text(result, quiet=False):
    lines = ["scanned %d markdown files" % result["md_files"]]
    groups = result["groups"]
    if groups and not quiet:
        cols = ("files", "links", "internal", "ok_targets", "missing",
                "bad_anchors", "external", "absolute")
        header = ("group",) + cols
        rows = []
        totals = defaultdict(int)
        for g in sorted(groups):
            rows.append((g,) + tuple(groups[g].get(c, 0) for c in cols))
            for c in cols:
                totals[c] += groups[g].get(c, 0)
        rows.append(("TOTAL",) + tuple(totals[c] for c in cols))
        widths = [max(len(str(r[i])) for r in [header] + rows)
                  for i in range(len(header))]
        lines.append("")
        lines.append("per-group stats:")
        for r in [header] + rows:
            lines.append("  " + "  ".join(str(r[i]).ljust(widths[i])
                                          for i in range(len(header))))
    if result["warnings"]:
        lines.append("")
        lines.append("%d warning(s):" % len(result["warnings"]))
        for w in result["warnings"]:
            lines.append("  WARN " + w)
    if result["errors"]:
        lines.append("")
        lines.append("%d error(s):" % len(result["errors"]))
        for e in result["errors"]:
            lines.append("  ERR  " + e)
    if not result["errors"]:
        lines.append("")
        lines.append("OK: no missing link targets")
    return "\n".join(lines)


def main():
    global ROOT
    ap = argparse.ArgumentParser(description="Markdown relative-link validator")
    ap.add_argument("--strict-anchors", action="store_true",
                    help="treat missing anchors as errors")
    ap.add_argument("--bare-paths", action="store_true",
                    help="also scan non-link text for legacy bare paths (warn)")
    ap.add_argument("--json", action="store_true", help="JSON summary output")
    ap.add_argument("--output", default=None, help="write report to this path")
    ap.add_argument("--quiet", action="store_true",
                    help="only summary + findings, no group table")
    ap.add_argument("--root", default=None, help="repository root override")
    args = ap.parse_args()
    if args.root:
        ROOT = args.root.replace("\\", "/").rstrip("/")

    result = check(strict_anchors=args.strict_anchors, bare_paths=args.bare_paths)
    text = render_text(result, quiet=args.quiet)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(text)
    if args.output:
        out = (json.dumps(result, ensure_ascii=False, indent=2)
               if args.json else text)
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(out + "\n")
        print("report written to %s" % args.output)
    return 1 if result["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
