#!/usr/bin/env python3
# UAD-NG 清单只读比对（不做任何卸载/禁用）
# 用法:
#   python scripts/uad-compare.py [--json tools/uad_lists.json] [--adb tools/platform-tools/adb.exe]
# 输出: inventory/uad-compare-<timestamp>.md
import argparse
import datetime
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def adb_shell(adb, serial, cmd):
    args = [adb] + (["-s", serial] if serial else []) + ["shell", cmd]
    p = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return (p.stdout or "").strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default=os.path.join(ROOT, "tools", "uad_lists.json"))
    ap.add_argument("--adb", default=os.path.join(ROOT, "tools", "platform-tools", "adb.exe"))
    ap.add_argument("--serial", default="")
    ap.add_argument("--out", default="")
    a = ap.parse_args()

    if not os.path.exists(a.json):
        print("缺少 UAD 清单:", a.json)
        print("下载: https://cdn.jsdelivr.net/gh/Universal-Debloater-Alliance/universal-android-debloater-next-generation@main/resources/assets/uad_lists.json")
        sys.exit(1)
    if not os.path.exists(a.adb):
        print("缺少 adb:", a.adb)
        sys.exit(1)

    with open(a.json, encoding="utf-8") as f:
        uad = json.load(f)

    installed = set(x.replace("package:", "").strip()
                    for x in adb_shell(a.adb, a.serial, "pm list packages --user 0").splitlines() if x.strip())
    third = set(x.replace("package:", "").strip()
                for x in adb_shell(a.adb, a.serial, "pm list packages -3 --user 0").splitlines() if x.strip())
    disabled = set(x.replace("package:", "").strip()
                   for x in adb_shell(a.adb, a.serial, "pm list packages -d --user 0").splitlines() if x.strip())

    order = {"Unsafe": 0, "Recommended": 1, "Advanced": 2, "Expert": 3, "Replaced": 4, "None": 5}
    hits = []
    for pkg, info in uad.items():
        if pkg not in installed:
            continue
        removal = info.get("removal", "None")
        hits.append({
            "pkg": pkg,
            "removal": removal,
            "list": info.get("list", ""),
            "third": pkg in third,
            "disabled": pkg in disabled,
            "desc": (info.get("description", "") or "").splitlines()[0] if info.get("description") else "",
      })
    hits.sort(key=lambda x: (order.get(x["removal"], 99), x["pkg"]))

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    out = a.out or os.path.join(ROOT, "inventory", "uad-compare-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S") + ".md")
    os.makedirs(os.path.dirname(out), exist_ok=True)

    def counts(key):
        c = {}
        for h in hits:
            c[h[key]] = c.get(h[key], 0) + 1
        return c

    lines = []
    lines.append("# UAD-NG 清单只读比对报告\n")
    lines.append("- 时间: " + now)
    lines.append("- 已安装包: %d（第三方 %d，已禁用 %d）" % (len(installed), len(third), len(disabled)))
    lines.append("- UAD 清单条目: %d；其中在设备上已安装: %d\n" % (len(uad), len(hits)))
    lines.append("## 按 removal 分类（已安装包）\n")
    for k in ["Unsafe", "Recommended", "Advanced", "Expert", "Replaced", "None"]:
        lines.append("- %s: %d" % (k, counts("removal").get(k, 0)))
    lines.append("\n> ⚠️ 本报告只读，不执行任何卸载/禁用。系统包卸载在本机有 bootloop 前科（见 docs/08）。\n")

    lines.append("## Unsafe（绝对不要动）\n")
    for h in [x for x in hits if x["removal"] == "Unsafe"]:
        lines.append("- `%s` (%s) — %s" % (h["pkg"], h["list"], h["desc"]))
    lines.append("")

    lines.append("## Recommended（按 UAD 可删，但本机 MIUI 限制/风险需人工确认）\n")
    for h in [x for x in hits if x["removal"] == "Recommended"]:
        flags = []
        if h["third"]: flags.append("第三方")
        if h["disabled"]: flags.append("已禁用")
        line = "- `%s` (%s%s) — %s" % (h["pkg"], h["list"], ("，" + "，".join(flags)) if flags else "", h["desc"])
        lines.append(line)
    lines.append("")
    lines.append("## 已禁用包在 UAD 中的评级\n")
    for h in hits:
        if h["disabled"]:
            lines.append("- `%s` — removal=%s" % (h["pkg"], h["removal"]))
    lines.append("")

    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("报告已写入:", out)
    print("已安装包 %d / 第三方 %d / 已禁用 %d；UAD 命中 %d" % (len(installed), len(third), len(disabled), len(hits)))


if __name__ == "__main__":
    main()
