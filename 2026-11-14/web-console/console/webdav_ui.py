#!/usr/bin/env python3
"""WebDAV 浏览器界面（中文）：网关在 GET/HEAD 集合根路径且 Accept 含 text/html 时返回。

设计约束（与 README §15 一致）：
- 不改变 WebDAV 协议语义：页面自身只用标准方法（PROPFIND/PUT/MKCOL/MOVE/DELETE/GET）
  操作同一前缀下的资源，其余方法与客户端请求仍由网关原样透传给 rclone；
- 认证仍由网关 Basic 完成，页面不接触口令（浏览器复用已缓存的 Basic 凭据）；
- 上传受网关 `/dav` 请求体上限（64 MiB）约束，超限在发起前拦截并明确提示，不做静默截断。
"""

from __future__ import annotations

import html
import json

MAX_UPLOAD_BYTES = 64 * 1024 * 1024

_PAGE = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
:root{color-scheme:dark}
*{box-sizing:border-box}
body{margin:0;background:#0f1116;color:#d7dce5;font:14px/1.5 -apple-system,"Segoe UI",Roboto,"Helvetica Neue","Noto Sans SC",sans-serif}
header{display:flex;flex-wrap:wrap;align-items:center;gap:10px;padding:14px 20px;border-bottom:1px solid #1e2430;background:#131722}
h1{margin:0;font-size:16px;font-weight:600}
.hint{color:#8b96a8;font-size:12px}
main{padding:16px 20px 40px}
.bar{display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin-bottom:12px}
.bar input[type=text]{background:#0b0e14;border:1px solid #2a3242;color:#d7dce5;border-radius:6px;padding:6px 9px;min-width:180px}
.bar input[type=file]{color:#8b96a8;font-size:12px}
button,.btn{font:inherit;color:#d7dce5;background:#1b2230;border:1px solid #2c3547;border-radius:6px;padding:6px 10px;cursor:pointer;text-decoration:none;display:inline-block}
button:hover,.btn:hover{background:#232c3d}
button.primary{background:#2b5cff;border-color:#2b5cff;color:#fff}
button.primary:hover{background:#3f6bff}
button.danger{color:#ff8f8f;border-color:#5a2a2a}
button.danger:hover{background:#3a1e1e}
button:disabled{opacity:.5;cursor:default}
.crumbs{color:#9aa6b8;margin-bottom:12px;word-break:break-all}
.crumbs a{color:#8ab4ff;text-decoration:none}
.crumbs a:hover{text-decoration:underline}
.crumbs .sep{color:#4b5566;margin:0 4px}
.table-wrap{overflow:auto;border:1px solid #1e2430;border-radius:8px}
table{border-collapse:collapse;width:100%;min-width:620px}
th,td{padding:9px 12px;border-bottom:1px solid #1a212c;text-align:left;vertical-align:middle}
th{background:#151a24;color:#9aa6b8;font-weight:600;white-space:nowrap}
th button{background:none;border:none;padding:0;color:inherit;font:inherit;cursor:pointer}
th button.active{color:#fff}
tbody tr:hover{background:#151b26}
td.num{text-align:right;white-space:nowrap;color:#b9c3d3}
td.time{white-space:nowrap;color:#8b96a8;font-size:12px}
td.ops{white-space:nowrap}
td.ops .btn,td.ops button{padding:3px 8px;font-size:12px;margin-left:4px}
.name{color:#d7dce5;text-decoration:none;display:inline-flex;align-items:center;gap:6px}
.name:hover{color:#8ab4ff}
.tag{font-size:11px;padding:0 5px;border-radius:4px;border:1px solid #2c3547;color:#9aa6b8}
.tag.dir{color:#8ab4ff;border-color:#2b3f6b}
.empty{color:#8b96a8;text-align:center;padding:22px}
.msg{margin:12px 0 0;min-height:20px;font-size:13px;color:#9aa6b8}
.msg.ok{color:#5fd6a0}
.msg.err{color:#ff8f8f}
.dlg{position:fixed;inset:0;background:rgba(5,8,12,.66);display:flex;align-items:center;justify-content:center;padding:20px}
.dlg[hidden]{display:none}
.dlg-box{background:#141a24;border:1px solid #2c3547;border-radius:10px;padding:16px;width:min(480px,100%)}
.dlg-box h2{margin:0 0 6px;font-size:15px}
.dlg-box p{margin:0 0 10px;color:#8b96a8;font-size:12px}
.dlg-box input{width:100%;background:#0b0e14;border:1px solid #2a3242;color:#d7dce5;border-radius:6px;padding:8px 10px}
.dlg-actions{display:flex;justify-content:flex-end;gap:8px;margin-top:12px}
</style>
</head>
<body>
<header>
  <h1>__TITLE__</h1>
  <span class="hint">中文文件管理界面 · 标准 WebDAV 协议未改动 · 单文件上传上限 64 MiB</span>
</header>
<main>
  <div class="crumbs" id="crumbs"></div>
  <div class="bar">
    <button id="refresh">刷新</button>
    <input type="text" id="filter" placeholder="按文件名过滤">
    <input type="text" id="newdir" placeholder="新目录名">
    <button id="mkdir">新建目录</button>
    <input type="file" id="upload" multiple>
    <span class="hint" id="count"></span>
  </div>
  <div class="hint" style="margin-bottom:8px">
    上传：单文件不超过 64 MiB（网关请求体上限）；超过时界面会在发送前拒绝并说明，不会静默截断。
    更大的文件请用 WebDAV 客户端（系统挂载 / rclone / 同步工具）直传。
  </div>
  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th><button data-sort="name" data-label="名称">名称</button></th>
          <th style="width:110px"><button data-sort="size" data-label="大小">大小</button></th>
          <th style="width:170px"><button data-sort="time" data-label="修改时间">修改时间</button></th>
          <th style="width:230px">操作</th>
        </tr>
      </thead>
      <tbody id="tbody"></tbody>
    </table>
  </div>
  <div class="msg" id="msg"></div>
</main>
<div class="dlg" id="dlg" hidden>
  <div class="dlg-box">
    <h2 id="dlg-title"></h2>
    <p id="dlg-hint"></p>
    <input type="text" id="dlg-input">
    <div class="dlg-actions">
      <button id="dlg-cancel">取消</button>
      <button id="dlg-ok" class="primary">确定</button>
    </div>
  </div>
</div>
<script>
"use strict";
const PREFIX = __PREFIX__;
const MAX_UPLOAD = __MAX_UPLOAD__;
const state = { path: "/", items: [], sortKey: "name", sortDir: 1, filter: "" };
let dialogResolve = null;

const $ = (id) => document.getElementById(id);

function esc(v) {
  return String(v).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
function fmtSize(n) {
  if (n === null || n === undefined || n === "") return "—";
  if (Number(n) === 0) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let v = n, i = 0;
  while (v >= 1024 && i < units.length - 1) { v /= 1024; i += 1; }
  return (i === 0 ? String(v) : v.toFixed(v < 10 ? 1 : 0)) + " " + units[i];
}
function fmtTime(ms) {
  if (!ms) return "—";
  const d = new Date(ms);
  const p = (x) => String(x).padStart(2, "0");
  return d.getFullYear() + "-" + p(d.getMonth() + 1) + "-" + p(d.getDate()) + " " +
    p(d.getHours()) + ":" + p(d.getMinutes());
}
function setMsg(text, kind) {
  const el = $("msg");
  el.textContent = text || "";
  el.className = "msg " + (kind || "");
}
function reason(code) {
  return ({
    400: "请求无效", 401: "认证失败，请刷新页面重新输入账号口令",
    403: "无权操作", 404: "目标不存在", 405: "该操作不被支持",
    409: "父目录不存在", 412: "目标已存在，未覆盖", 413: "超过网关 64 MiB 请求体上限",
    423: "资源已被锁定", 500: "服务端错误", 507: "磁盘空间不足"
  })[code] || "未知错误";
}
function encPath(p) { return p.split("/").map(encodeURIComponent).join("/"); }
function urlOf(p) { return PREFIX + encPath(p); }
function join(dir, name) { return dir.replace(/\\/+$/, "") + "/" + name; }
function parentOf(p) {
  const clean = p.replace(/\\/+$/, "");
  const idx = clean.lastIndexOf("/");
  return idx <= 0 ? "/" : clean.slice(0, idx + 1);
}
function fullPathOf(hrefText) {
  let p = hrefText;
  try { p = new URL(hrefText, location.href).pathname; } catch (e) { /* 保留原值 */ }
  if (p.indexOf(PREFIX) === 0) p = p.slice(PREFIX.length);
  if (p.charAt(0) !== "/") p = "/" + p;
  return p.split("/").map((s) => {
    try { return decodeURIComponent(s); } catch (e) { return s; }
  }).join("/");
}

async function dav(method, path, opts) {
  opts = opts || {};
  const init = { method: method, credentials: "same-origin", cache: "no-store", headers: opts.headers || {} };
  if (opts.body !== undefined) init.body = opts.body;
  return fetch(urlOf(path), init);
}

async function load(path) {
  state.path = path.charAt(path.length - 1) === "/" ? path : path + "/";
  try { history.replaceState(null, "", urlOf(state.path)); } catch (e) { /* 忽略 */ }
  setMsg("正在读取目录…", "");
  const body = '<?xml version="1.0" encoding="utf-8"?>' +
    '<d:propfind xmlns:d="DAV:"><d:prop><d:displayname/><d:resourcetype/>' +
    '<d:getcontentlength/><d:getlastmodified/></d:prop></d:propfind>';
  let res;
  try {
    res = await dav("PROPFIND", state.path, {
      headers: { "Depth": "1", "Content-Type": "application/xml; charset=utf-8" },
      body: body
    });
  } catch (e) {
    setMsg("无法连接服务：" + e, "err");
    return;
  }
  if (res.status === 401) { setMsg("认证已失效，请刷新页面并重新输入 WebDAV 账号口令。", "err"); return; }
  if (res.status === 404) { setMsg("目录不存在：" + state.path, "err"); return; }
  if (res.status !== 207) { setMsg("读取目录失败：HTTP " + res.status + "（" + reason(res.status) + "）", "err"); return; }
  let doc;
  try {
    doc = new DOMParser().parseFromString(await res.text(), "application/xml");
  } catch (e) {
    setMsg("目录响应解析失败（不是合法 XML）。", "err");
    return;
  }
  const items = [];
  const nodes = doc.getElementsByTagNameNS("DAV:", "response");
  for (let i = 0; i < nodes.length; i += 1) {
    const node = nodes[i];
    const hrefNode = node.getElementsByTagNameNS("DAV:", "href")[0];
    if (!hrefNode) continue;
    const path = fullPathOf(hrefNode.textContent.trim());
    if (path === state.path) continue;
    const isDir = node.getElementsByTagNameNS("DAV:", "collection").length > 0;
    let ip = path;
    if (isDir && ip.charAt(ip.length - 1) !== "/") ip += "/";
    if (!isDir) ip = ip.replace(/\\/+$/, "");
    const nameNode = node.getElementsByTagNameNS("DAV:", "displayname")[0];
    let name = nameNode ? nameNode.textContent.trim() : "";
    if (!name) {
      const seg = ip.replace(/\\/+$/, "").split("/");
      name = seg[seg.length - 1] || "/";
    }
    const sizeNode = node.getElementsByTagNameNS("DAV:", "getcontentlength")[0];
    const timeNode = node.getElementsByTagNameNS("DAV:", "getlastmodified")[0];
    items.push({
      path: ip,
      name: name,
      isDir: isDir,
      size: sizeNode ? (Number(sizeNode.textContent) || 0) : 0,
      mtime: timeNode ? (Date.parse(timeNode.textContent) || 0) : 0
    });
  }
  state.items = items;
  setMsg("已加载 " + items.length + " 项。", "");
  render();
}

function visibleItems() {
  const needle = state.filter.trim().toLowerCase();
  const list = state.items.filter((it) => !needle || it.name.toLowerCase().indexOf(needle) >= 0);
  list.sort((a, b) => {
    if (a.isDir !== b.isDir) return a.isDir ? -1 : 1;
    let r = 0;
    if (state.sortKey === "name") r = a.name.localeCompare(b.name, "zh-Hans-CN", { numeric: true, sensitivity: "base" });
    else if (state.sortKey === "size") r = a.size - b.size;
    else r = a.mtime - b.mtime;
    if (r === 0) r = a.name.localeCompare(b.name, "zh-Hans-CN", { numeric: true });
    return r * state.sortDir;
  });
  return list;
}

function render() {
  const parts = state.path.replace(/\\/+$/, "").split("/").filter(Boolean);
  let cur = "/";
  let trail = '<a href="#" data-goto="/">根目录</a>';
  parts.forEach((seg) => {
    cur += seg + "/";
    trail += '<span class="sep">/</span><a href="#" data-goto="' + esc(cur) + '">' + esc(seg) + "</a>";
  });
  $("crumbs").innerHTML = trail;

  const list = visibleItems();
  if (!list.length) {
    $("tbody").innerHTML = '<tr><td colspan="4" class="empty">该目录为空或没有匹配的条目</td></tr>';
  } else {
    $("tbody").innerHTML = list.map((it) => {
      const tag = it.isDir ? '<span class="tag dir">目录</span>' : '<span class="tag">文件</span>';
      const nameCell = it.isDir
        ? '<a href="#" class="name" data-goto="' + esc(it.path) + '">' + tag + esc(it.name) + "</a>"
        : '<a href="' + esc(urlOf(it.path)) + '" class="name">' + tag + esc(it.name) + "</a>";
      const download = it.isDir ? "" : '<a class="btn" href="' + esc(urlOf(it.path)) + '" download>下载</a>';
      return "<tr><td>" + nameCell + "</td>" +
        '<td class="num">' + (it.isDir ? "—" : esc(fmtSize(it.size))) + "</td>" +
        '<td class="time">' + esc(fmtTime(it.mtime)) + "</td>" +
        '<td class="ops">' + download +
        '<button data-act="move" data-path="' + esc(it.path) + '">重命名/移动</button>' +
        '<button class="danger" data-act="del" data-path="' + esc(it.path) + '" data-dir="' + (it.isDir ? "1" : "0") + '">删除</button>' +
        "</td></tr>";
    }).join("");
  }
  $("count").textContent = "共 " + list.length + " 项";
  document.querySelectorAll("[data-sort]").forEach((el) => {
    const key = el.getAttribute("data-sort");
    const active = key === state.sortKey;
    el.classList.toggle("active", active);
    el.textContent = el.getAttribute("data-label") + (active ? (state.sortDir > 0 ? " ↑" : " ↓") : "");
  });
}

function ask(title, hint, value) {
  return new Promise((resolve) => {
    dialogResolve = resolve;
    $("dlg-title").textContent = title;
    $("dlg-hint").textContent = hint;
    $("dlg-input").value = value || "";
    $("dlg").hidden = false;
    $("dlg-input").focus();
    $("dlg-input").select();
  });
}
function closeDialog(value) {
  $("dlg").hidden = true;
  const resolve = dialogResolve;
  dialogResolve = null;
  if (resolve) resolve(value);
}

async function removeItem(path, isDir) {
  setMsg("正在删除 " + path + "…", "");
  let res;
  try {
    res = await dav("DELETE", path);
  } catch (e) {
    setMsg("删除失败：连接中断（" + e + "）。", "err");
    return;
  }
  if (res.status === 204 || res.status === 200) {
    setMsg("已删除：" + path + (isDir ? "（目录及其内容）" : ""), "ok");
    load(parentOf(path) || state.path);
  } else {
    setMsg("删除失败：HTTP " + res.status + "（" + reason(res.status) + "）", "err");
  }
}

async function moveItem(path) {
  const isDir = path.charAt(path.length - 1) === "/";
  const from = path.replace(/\\/+$/, "");
  const target = await ask("重命名 / 移动", "目标路径（从 WebDAV 根开始，含文件名；可改目录实现移动）", from);
  if (target === null) return;
  let to = target.trim();
  if (!to) { setMsg("目标路径不能为空。", "err"); return; }
  if (to.charAt(0) !== "/") to = "/" + to;
  if (isDir && to.charAt(to.length - 1) !== "/") to += "/";
  if (to === path) return;
  let res;
  try {
    res = await dav("MOVE", path, { headers: { "Destination": PREFIX + encPath(to), "Overwrite": "F" } });
  } catch (e) {
    setMsg("移动失败：连接中断（" + e + "）。", "err");
    return;
  }
  if (res.status === 201 || res.status === 204 || res.status === 200) {
    setMsg("已移动/重命名：" + from + " → " + to, "ok");
    load(state.path);
  } else if (res.status === 412 || res.status === 409) {
    setMsg("移动失败：目标已存在或父目录不存在（HTTP " + res.status + "）。", "err");
  } else {
    setMsg("移动失败：HTTP " + res.status + "（" + reason(res.status) + "）", "err");
  }
}

async function makeDir() {
  const name = ($("newdir").value || "").trim();
  if (!name) { setMsg("请先填写新目录名。", "err"); return; }
  if (name.indexOf("/") >= 0) { setMsg("目录名不能包含 /，多层目录请逐级创建。", "err"); return; }
  const target = join(state.path, name);
  setMsg("正在创建目录 " + target + "…", "");
  let res;
  try {
    res = await dav("MKCOL", target);
  } catch (e) {
    setMsg("创建失败：连接中断（" + e + "）。", "err");
    return;
  }
  if (res.status === 201) {
    $("newdir").value = "";
    setMsg("已创建目录：" + target, "ok");
    load(state.path);
  } else if (res.status === 405) {
    setMsg("创建失败：同名目录或文件已存在。", "err");
  } else {
    setMsg("创建失败：HTTP " + res.status + "（" + reason(res.status) + "）", "err");
  }
}

async function uploadFiles(files) {
  if (!files || !files.length) return;
  let ok = 0, fail = 0;
  for (let i = 0; i < files.length; i += 1) {
    const file = files[i];
    if (file.size > MAX_UPLOAD) {
      setMsg("“" + file.name + "”大小 " + fmtSize(file.size) +
        "，超过 64 MiB 网关请求体上限，已跳过（未发送）。请改用 WebDAV 客户端上传。", "err");
      fail += 1;
      continue;
    }
    const target = join(state.path, file.name);
    setMsg("正在上传 " + file.name + "（" + fmtSize(file.size) + "，第 " + (i + 1) + "/" + files.length + " 个）…", "");
    let res;
    try {
      res = await dav("PUT", target, { headers: { "Content-Type": "application/octet-stream" }, body: file });
    } catch (e) {
      setMsg("上传中断：" + file.name + "（" + e + "）。若文件接近 64 MiB，网关会因超限直接断开，文件不会保存。", "err");
      fail += 1;
      continue;
    }
    if (res.status === 200 || res.status === 201 || res.status === 204) {
      ok += 1;
    } else if (res.status === 413) {
      setMsg("“" + file.name + "”被网关拒绝：请求体超过 64 MiB 上限，文件未保存。", "err");
      fail += 1;
    } else {
      setMsg("上传失败：" + file.name + " HTTP " + res.status + "（" + reason(res.status) + "）", "err");
      fail += 1;
    }
  }
  $("upload").value = "";
  setMsg("上传完成：成功 " + ok + " 个，失败 " + fail + " 个。", fail ? "err" : "ok");
  load(state.path);
}

$("crumbs").addEventListener("click", (ev) => {
  const link = ev.target.closest("[data-goto]");
  if (!link) return;
  ev.preventDefault();
  load(link.getAttribute("data-goto"));
});
$("tbody").addEventListener("click", (ev) => {
  const goto = ev.target.closest("[data-goto]");
  if (goto) { ev.preventDefault(); load(goto.getAttribute("data-goto")); return; }
  const btn = ev.target.closest("[data-act]");
  if (!btn) return;
  const path = btn.getAttribute("data-path");
  if (btn.getAttribute("data-act") === "move") { moveItem(path); return; }
  const isDir = btn.getAttribute("data-dir") === "1";
  if (btn.dataset.armed === "1") {
    btn.dataset.armed = "0";
    removeItem(path, isDir);
    return;
  }
  btn.dataset.armed = "1";
  btn.textContent = isDir ? "确认删除目录？" : "确认删除？";
  setMsg(isDir ? "再次点击将递归删除目录“" + path + "”及其全部内容。" : "再次点击将删除“" + path + "”。", "err");
  setTimeout(() => {
    if (btn.dataset.armed === "1") { btn.dataset.armed = "0"; btn.textContent = "删除"; }
  }, 6000);
});
document.querySelectorAll("[data-sort]").forEach((el) => {
  el.addEventListener("click", () => {
    const key = el.getAttribute("data-sort");
    if (state.sortKey === key) state.sortDir = -state.sortDir;
    else { state.sortKey = key; state.sortDir = 1; }
    render();
  });
});
$("filter").addEventListener("input", (ev) => { state.filter = ev.target.value; render(); });
$("refresh").addEventListener("click", () => load(state.path));
$("mkdir").addEventListener("click", makeDir);
$("newdir").addEventListener("keydown", (ev) => { if (ev.key === "Enter") makeDir(); });
$("upload").addEventListener("change", (ev) => uploadFiles(ev.target.files));
$("dlg-ok").addEventListener("click", () => closeDialog($("dlg-input").value));
$("dlg-cancel").addEventListener("click", () => closeDialog(null));
$("dlg-input").addEventListener("keydown", (ev) => {
  if (ev.key === "Enter") closeDialog($("dlg-input").value);
  if (ev.key === "Escape") closeDialog(null);
});
$("dlg").addEventListener("click", (ev) => { if (ev.target === $("dlg")) closeDialog(null); });

load("/");
</script>
</body>
</html>
"""


def render_page(prefix: str, title: str) -> str:
    """返回中文 WebDAV 界面 HTML（prefix 形如 `/dav`，title 由配置注入）。"""
    return (
        _PAGE.replace("__TITLE__", html.escape(title or "Haydn WebDAV"))
        .replace("__PREFIX__", json.dumps(prefix))
        .replace("__MAX_UPLOAD__", str(MAX_UPLOAD_BYTES))
    )
