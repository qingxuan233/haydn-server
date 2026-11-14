#!/usr/bin/env python3
"""控制台页面模板（内联 CSS/JS，无外部资源，可在手机窄屏使用）。"""

LOGIN_HTML = """<!doctype html>
<html lang="zh-CN"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__ · 登录</title>
<style>
  :root { color-scheme: dark; }
  * { box-sizing: border-box; }
  body { margin: 0; min-height: 100vh; display: flex; align-items: center; justify-content: center;
         background: #0f1116; color: #d7dce5; font: 15px/1.5 -apple-system, "Segoe UI", Roboto, sans-serif; }
  .card { width: min(380px, 92vw); background: #171b23; border: 1px solid #262c38; border-radius: 10px;
          padding: 28px 24px; box-shadow: 0 12px 40px rgba(0,0,0,.45); }
  h1 { font-size: 18px; margin: 0 0 4px; letter-spacing: .3px; }
  p.sub { margin: 0 0 22px; color: #7d8899; font-size: 13px; }
  label { display: block; font-size: 12px; color: #8b96a8; margin-bottom: 6px; }
  input[type=password] { width: 100%; padding: 11px 12px; border-radius: 7px; border: 1px solid #2e3543;
          background: #0f1219; color: #e6ebf3; font-size: 15px; }
  input:focus { outline: none; border-color: #3f7bd9; }
  button { width: 100%; margin-top: 18px; padding: 11px; border: 0; border-radius: 7px;
           background: #2f6fd0; color: #fff; font-size: 15px; cursor: pointer; }
  button:disabled { opacity: .6; cursor: default; }
  .err { margin-top: 14px; color: #f0736a; font-size: 13px; min-height: 18px; }
  .foot { margin-top: 18px; color: #5f6a7b; font-size: 12px; }
</style></head>
<body>
<form class="card" method="post" action="__CONSOLE_PATH__/api/login" id="login">
  <h1>__TITLE__</h1>
  <p class="sub">__HOST_LABEL__ · 需要口令</p>
  <label for="pw">口令</label>
  <input id="pw" name="password" type="password" autocomplete="current-password" autofocus required>
  <button type="submit">登录</button>
  <div class="err" id="err">__ERROR__</div>
  <div class="foot">失败尝试会被记录并限流；会话 12 小时后过期。</div>
</form>
<script>
document.getElementById('login').addEventListener('submit', async function (ev) {
  ev.preventDefault();
  const btn = this.querySelector('button');
  const err = document.getElementById('err');
  btn.disabled = true; err.textContent = '';
  try {
    const res = await fetch('__CONSOLE_PATH__/api/login', {
      method: 'POST', credentials: 'same-origin',
      headers: {'Content-Type': 'application/json', 'X-Haydn-Client': 'console'},
      body: JSON.stringify({password: document.getElementById('pw').value})
    });
    const data = await res.json().catch(function () { return {}; });
    if (res.ok) { location.replace('__CONSOLE_PATH__/'); return; }
    err.textContent = data.error || ('登录失败（HTTP ' + res.status + '）');
  } catch (e) {
    err.textContent = '网络错误：' + e.message;
  }
  btn.disabled = false;
});
</script>
</body></html>
"""

APP_HTML = """<!doctype html>
<html lang="zh-CN"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
  :root { color-scheme: dark; }
  * { box-sizing: border-box; }
  body { margin: 0; background: #0f1116; color: #d7dce5;
         font: 14px/1.55 -apple-system, "Segoe UI", Roboto, "Noto Sans CJK SC", sans-serif; }
  header { display: flex; align-items: center; gap: 12px; padding: 14px 18px;
           border-bottom: 1px solid #222834; background: #12151c; position: sticky; top: 0; z-index: 2; }
  header h1 { font-size: 16px; margin: 0; font-weight: 600; letter-spacing: .3px; }
  header .meta { color: #6f7a8c; font-size: 12px; margin-left: auto; }
  header button { background: #222836; color: #b9c2d0; border: 1px solid #2e3543; border-radius: 6px;
                  padding: 6px 10px; font-size: 12px; cursor: pointer; }
  main { padding: 16px; display: grid; gap: 16px; max-width: 1100px; margin: 0 auto; }
  section { background: #151920; border: 1px solid #222834; border-radius: 10px; padding: 14px 16px; }
  section h2 { font-size: 13px; text-transform: uppercase; letter-spacing: .8px;
               color: #7f8b9e; margin: 0 0 12px; font-weight: 600; }
  table { width: 100%; border-collapse: collapse; font-size: 13px; }
  th, td { text-align: left; padding: 7px 6px; border-bottom: 1px solid #1e2430; vertical-align: middle; }
  th { color: #6f7a8c; font-weight: 500; font-size: 12px; }
  tr:last-child td { border-bottom: 0; }
  .state-RUNNING { color: #55c27d; }
  .state-STOPPED, .state-EXITED, .state-FATAL, .state-ERROR { color: #f0736a; }
  .state-STARTING, .state-BACKOFF { color: #e0b341; }
  .btns { white-space: nowrap; }
  .btns button { background: #1f2532; color: #aeb8c7; border: 1px solid #2b3240; border-radius: 5px;
                 padding: 3px 8px; font-size: 12px; margin-left: 4px; cursor: pointer; }
  .btns button:hover { border-color: #3f7bd9; color: #cfe0ff; }
  .btns button:disabled { opacity: .45; cursor: default; }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; }
  .kv { background: #10141b; border: 1px solid #1d2430; border-radius: 8px; padding: 9px 11px; }
  .kv .k { color: #6f7a8c; font-size: 11px; letter-spacing: .4px; }
  .kv .v { font-size: 16px; margin-top: 2px; font-variant-numeric: tabular-nums; }
  .kv .v small { font-size: 11px; color: #7f8b9e; }
  .row { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; margin-bottom: 10px; }
  select, input[type=number] { background: #10141b; color: #d7dce5; border: 1px solid #2b3240;
                border-radius: 6px; padding: 5px 8px; font-size: 13px; }
  pre { background: #0c0f14; border: 1px solid #1d2430; border-radius: 8px; padding: 10px 12px;
        overflow: auto; max-height: 420px; font-size: 12px; line-height: 1.45; margin: 0; }
  .msg { min-height: 18px; font-size: 12px; color: #7f8b9e; }
  .msg.ok { color: #55c27d; }
  .msg.err { color: #f0736a; }
  .bar { height: 6px; border-radius: 3px; background: #1d2430; overflow: hidden; margin-top: 6px; }
  .bar > i { display: block; height: 100%; background: #3f7bd9; }
  .warn { color: #e0b341; }
  .entries { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 8px; }
  .entries a, .entries span.off { display: block; padding: 10px 12px; border-radius: 8px; border: 1px solid #2b3240;
          background: #10141b; color: #cfe0ff; text-decoration: none; font-size: 13px; }
  .entries a:hover { border-color: #3f7bd9; }
  .entries span.off { color: #6f7a8c; border-style: dashed; }
  .entries small { display: block; color: #6f7a8c; font-size: 11px; margin-top: 3px; }
  .pwbox { margin-top: 10px; border: 1px solid #6b5426; background: #1d1a12; border-radius: 8px; padding: 10px 12px; }
  .pwbox code { display: block; font-size: 16px; letter-spacing: .5px; word-break: break-all; color: #ffd479;
          background: #0c0f14; border: 1px solid #2b3240; border-radius: 6px; padding: 8px 10px; margin: 6px 0; }
</style></head>
<body>
<header>
  <h1>__TITLE__</h1>
  <span class="meta" id="updated">加载中…</span>
  <button id="logout" type="button">退出</button>
</header>
<main>
  <section>
    <h2>服务入口</h2>
    <div class="entries" id="entries"><span class="off">加载中…</span></div>
    <div class="msg" id="entries-msg"></div>
  </section>

  <section>
    <h2>服务（白名单启停）</h2>
    <table>
      <thead><tr><th>服务</th><th>状态</th><th>PID / Uptime</th><th></th></tr></thead>
      <tbody id="services"><tr><td colspan="4">加载中…</td></tr></tbody>
    </table>
    <div class="msg" id="svc-msg"></div>
  </section>

  <section>
    <h2>概览</h2>
    <div class="grid" id="overview"></div>
  </section>

  <section>
    <h2>访问入口（公网 / 局域网）</h2>
    <div class="grid" id="access"></div>
    <div class="row" style="margin-top:10px">
      <button id="lan-go" type="button" style="display:none;background:#243a5e;color:#cfe0ff;border:1px solid #31507f;border-radius:6px;padding:7px 12px;cursor:pointer">切到局域网（省流）</button>
      <span class="msg" id="lan-msg"></span>
    </div>
  </section>

  <section>
    <h2>遥测与 soak</h2>
    <div class="grid" id="telemetry"></div>
    <div class="msg" id="soak"></div>
  </section>

  <section>
    <h2>凭据与轮换</h2>
    <div class="row">
      <button id="cred-download" type="button" style="background:#243a5e;color:#cfe0ff;border:1px solid #31507f;border-radius:6px;padding:7px 12px;cursor:pointer">下载凭据 CSV（一次性链接）</button>
      <span class="msg" id="cred-msg"></span>
    </div>
    <table>
      <thead><tr><th>服务</th><th>账号</th><th>上次轮换（服务验证）</th><th>密码库同步</th><th></th></tr></thead>
      <tbody id="cred-services"><tr><td colspan="5">加载中…</td></tr></tbody>
    </table>
    <div class="pwbox" id="newpw" style="display:none">
      <div class="row" style="margin:0">
        <b id="newpw-title">新口令</b>
        <span class="msg" id="newpw-ttl"></span>
      </div>
      <code id="newpw-value"></code>
      <div class="row" style="margin:0">
        <button id="newpw-copy" type="button" style="background:#1f2532;color:#aeb8c7;border:1px solid #2b3240;border-radius:6px;padding:5px 10px;cursor:pointer">复制</button>
        <button id="newpw-hide" type="button" style="background:#1f2532;color:#aeb8c7;border:1px solid #2b3240;border-radius:6px;padding:5px 10px;cursor:pointer">关闭</button>
        <span class="msg">只显示这一次；关闭后无法再取回，请立即保存。</span>
      </div>
    </div>
    <div class="msg" id="vault-msg"></div>
  </section>

  <section>
    <h2>凭据文件（仅存在与权限）</h2>
    <table>
      <thead><tr><th>名称</th><th>状态</th><th>更新时间</th><th>权限</th></tr></thead>
      <tbody id="secrets"><tr><td colspan="4">加载中…</td></tr></tbody>
    </table>
    <div class="msg">明文只在设备侧 600 文件，接口与页面不返回完整口令（轮换结果仅展示一次）。</div>
  </section>

  <section>
    <h2>日志</h2>
    <div class="row">
      <select id="log-name"></select>
      <input id="log-lines" type="number" min="20" max="2000" step="20" value="200" style="width:90px">
      <button id="log-refresh" type="button" style="background:#1f2532;color:#aeb8c7;border:1px solid #2b3240;border-radius:6px;padding:5px 10px;cursor:pointer">刷新</button>
      <span class="msg" id="log-msg"></span>
    </div>
    <pre id="log-body">（选择日志后显示末尾内容）</pre>
  </section>

  <section>
    <h2>备份</h2>
    <div class="row">
      <button id="backup-now" type="button" style="background:#243a5e;color:#cfe0ff;border:1px solid #31507f;border-radius:6px;padding:7px 12px;cursor:pointer">立即触发一次备份</button>
      <span class="msg" id="backup-msg"></span>
    </div>
    <pre id="backup-status">（读取 backup.log）</pre>
  </section>
</main>
<script>
const P = "__CONSOLE_PATH__";
const $ = function (s) { return document.querySelector(s); };
const fmtBytes = function (n) {
  if (n === null || n === undefined) return '—';
  const u = ['B','KiB','MiB','GiB','TiB']; let i = 0; let v = n;
  while (v >= 1024 && i < u.length - 1) { v /= 1024; i++; }
  return (i === 0 ? v : v.toFixed(1)) + ' ' + u[i];
};
const fmtDur = function (s) {
  if (s === null || s === undefined) return '—';
  s = Math.max(0, Math.round(s));
  const d = Math.floor(s / 86400); const h = Math.floor(s % 86400 / 3600); const m = Math.floor(s % 3600 / 60);
  if (d) return d + 'd ' + h + 'h'; if (h) return h + 'h ' + m + 'm'; return m + 'm';
};
async function api(path, options) {
  const opts = Object.assign({credentials: 'same-origin',
    headers: {'Content-Type': 'application/json', 'X-Haydn-Client': 'console'}}, options || {});
  const res = await fetch(P + path, opts);
  if (res.status === 401) { location.reload(); throw new Error('会话已过期'); }
  const data = await res.json().catch(function () { return {}; });
  if (!res.ok) {
    const err = new Error(data.error || ('HTTP ' + res.status));
    err.data = data;
    throw err;
  }
  return data;
}
function kv(k, v, sub) {
  return '<div class="kv"><div class="k">' + k + '</div><div class="v">' + v +
         (sub ? ' <small>' + sub + '</small>' : '') + '</div></div>';
}
function renderServices(items) {
  const body = $('#services');
  if (!items.length) { body.innerHTML = '<tr><td colspan="4">无数据</td></tr>'; return; }
  body.innerHTML = items.map(function (s) {
    const cls = 'state-' + s.state;
    const meta = (s.pid ? s.pid : '—') + (s.uptime ? ' / ' + s.uptime : '');
    const btns = s.actionable
      ? ['start','restart','stop'].map(function (v) {
          return '<button data-svc="' + s.name + '" data-verb="' + v + '">' + v + '</button>';
        }).join('')
      : '<span class="msg">只读</span>';
    return '<tr><td>' + s.name + '</td><td class="' + cls + '">' + s.state +
           '</td><td>' + meta + '</td><td class="btns">' + btns + '</td></tr>';
  }).join('');
  body.querySelectorAll('button[data-svc]').forEach(function (b) {
    b.addEventListener('click', function () { return act(b.dataset.svc, b.dataset.verb, b); });
  });
}
const pendingConfirm = {};
// 页内两步确认：原生 confirm 会被浏览器“阻止更多对话框”静默吞掉（点了没反应），
// 首次点击只进入确认态并说明影响，5 秒内再次点击才执行。
function armConfirm(key, btn, label, prompt, msgEl) {
  if (Date.now() > (pendingConfirm[key] || 0)) {
    pendingConfirm[key] = Date.now() + 5000;
    btn.dataset.label = btn.dataset.label || btn.textContent;
    btn.textContent = '确认 ' + label;
    msgEl.className = 'msg warn';
    msgEl.textContent = prompt + '（5 秒内再次点击执行）';
    setTimeout(function () {
      if (pendingConfirm[key] && Date.now() >= pendingConfirm[key]) {
        delete pendingConfirm[key];
        if (btn.isConnected) btn.textContent = btn.dataset.label || label;
      }
    }, 5200);
    return false;
  }
  delete pendingConfirm[key];
  btn.textContent = btn.dataset.label || label;
  return true;
}
async function act(name, verb, btn) {
  const msg = $('#svc-msg');
  const effect = verb === 'stop' ? '会让该服务立即中断，直到再次 start'
    : verb === 'restart' ? '会让该服务短暂中断（数秒）后恢复'
    : '会启动该服务';
  if (!armConfirm('svc:' + name + ':' + verb, btn, verb,
      '即将 ' + verb + ' ' + name + '：' + effect, msg)) return;
  btn.disabled = true;
  msg.className = 'msg'; msg.textContent = '执行中：' + name + ' ' + verb + '…';
  try {
    const data = await api('/api/service', {method: 'POST', body: JSON.stringify({name: name, action: verb})});
    msg.className = 'msg ok'; msg.textContent = name + ' ' + verb + ' 成功：' + (data.output || 'ok');
  } catch (e) {
    msg.className = 'msg err'; msg.textContent = name + ' ' + verb + ' 失败：' + e.message;
  } finally {
    btn.disabled = false;
    loadStatus();
  }
}
function renderSecrets(items) {
  const body = $('#secrets');
  if (!items || !items.length) { body.innerHTML = '<tr><td colspan="4">无凭据条目</td></tr>'; return; }
  body.innerHTML = items.map(function (s) {
    return '<tr><td>' + s.name + '</td><td class="state-RUNNING">存在</td><td>' +
           (s.updated || '—') + '</td><td>' + (s.mode || '—') + '</td></tr>';
  }).join('');
}
function renderCredentials(cred) {
  const body = $('#cred-services');
  const items = cred.services || [];
  const esc = function (t) {
    return String(t === null || t === undefined ? '' : t).replace(/[&<>"]/g, function (c) {
      return {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c];
    });
  };
  if (!items.length) {
    body.innerHTML = '<tr><td colspan="5">未配置服务凭据</td></tr>';
  } else {
    body.innerHTML = items.map(function (s) {
      const rot = s.rotated_at
        ? ((s.rotation_ok === false ? '<span class="state-ERROR">失败</span> ' : '<span class="state-RUNNING">通过</span> ') + esc(s.rotated_at))
        : '—';
      let vault = '—';
      if (s.vault === 'ok') {
        vault = '<span class="state-RUNNING">已同步</span>' +
          (s.vault_at ? ' <span class="msg">' + esc(s.vault_at) + '</span>' : '');
      } else if (s.vault === 'fail') {
        vault = '<span class="state-ERROR">失败</span>' +
          (s.vault_error ? ' <span class="msg">' + esc(s.vault_error) + '</span>' : '');
      } else if (s.vault === 'skipped') {
        vault = '<span class="warn">未写入</span>' +
          (s.vault_error ? ' <span class="msg">' + esc(s.vault_error) + '</span>' : '');
      }
      const btn = s.rotatable
        ? '<button class="rot" data-id="' + esc(s.id) + '">轮换</button>'
        : '<span class="msg">不可服务端轮换</span>';
      return '<tr><td>' + esc(s.name) + '</td><td>' + esc(s.username || '—') + '</td><td>' +
        rot + '</td><td>' + vault + '</td><td class="btns">' + btn + '</td></tr>';
    }).join('');
    body.querySelectorAll('button.rot').forEach(function (b) {
      b.addEventListener('click', function () { rotate(b.dataset.id, b); });
    });
  }
  const v = cred.vault || {};
  const vm = $('#vault-msg');
  vm.className = 'msg' + (v.ready ? ' ok' : ' warn');
  vm.textContent = v.enabled
    ? (v.ready ? '密码库写入已启用（bw 客户端可用）；“密码库同步”显示最近一次写入/同步结果，重跑 --vault-sync 即刷新。' : '密码库写入阻塞：' + (v.reason || '未就绪'))
    : '密码库写入未启用：' + (v.reason || '');
}
let pwTimer = null;
function hideOnce() {
  $('#newpw').style.display = 'none';
  $('#newpw-value').textContent = '';
  if (pwTimer) { clearInterval(pwTimer); pwTimer = null; }
}
function showOnce(name, password) {
  $('#newpw').style.display = '';
  $('#newpw-title').textContent = name + ' 的新口令';
  $('#newpw-value').textContent = password;
  let left = 120;
  const ttl = $('#newpw-ttl');
  ttl.textContent = left + ' 秒后自动隐藏';
  if (pwTimer) clearInterval(pwTimer);
  pwTimer = setInterval(function () {
    left -= 1;
    if (left <= 0) { hideOnce(); return; }
    ttl.textContent = left + ' 秒后自动隐藏';
  }, 1000);
}
const rotatePending = {};
async function rotate(id, btn) {
  const msg = $('#cred-msg');
  // 两步确认放在页面内：原生 confirm 会被浏览器“阻止更多对话框”静默吞掉，
  // 表现为点按钮完全没反应，因此不再依赖原生对话框。
  if (Date.now() > (rotatePending[id] || 0)) {
    rotatePending[id] = Date.now() + 5000;
    btn.textContent = '确认轮换';
    msg.className = 'msg warn';
    msg.textContent = '再次点击“确认轮换”执行 ' + id + ' 轮换（旧口令将立即失效，5 秒内有效）。';
    setTimeout(function () {
      if (rotatePending[id] && Date.now() >= rotatePending[id]) {
        delete rotatePending[id];
        if (btn.isConnected) btn.textContent = '轮换';
      }
    }, 5200);
    return;
  }
  delete rotatePending[id];
  btn.textContent = '轮换';
  btn.disabled = true;
  msg.className = 'msg';
  msg.textContent = '轮换中（写入 → 回读 → 验证 → 密码库）…';
  try {
    const d = await api('/api/rotate', {method: 'POST', body: JSON.stringify({service: id})});
    msg.className = d.vault_error ? 'msg err' : 'msg ok';
    msg.textContent = d.name + ' 已轮换并验证（' + (d.rotated_at || '') + '）。' +
      (d.vault_error ? ' 密码库条目未更新：' + d.vault_error + '。请用下方一次性口令到客户端手动更新。' : '');
    if (d.password) showOnce(d.name, d.password);
    loadStatus();
  } catch (e) {
    msg.className = 'msg err';
    let text = '轮换失败：' + (e.message || '未知错误');
    if (e.data && e.data.steps) {
      const failed = e.data.steps.filter(function (s) { return !s.ok; })
        .map(function (s) { return s.name + (s.detail ? '（' + s.detail + '）' : ''); });
      if (failed.length) text += '；失败步骤：' + failed.join('、');
    }
    if (e.data && e.data.rollback) text += '；' + e.data.rollback;
    msg.textContent = text;
  } finally {
    btn.disabled = false;
  }
}
async function loadEntries() {
  const box = $('#entries');
  const msg = $('#entries-msg');
  try {
    const data = await api('/api/entries');
    const items = data.entries || [];
    if (!items.length) { box.innerHTML = '<span class="off">未配置服务入口</span>'; return; }
    box.innerHTML = items.map(function (e) {
      if (!e.available) {
        return '<span class="off" title="' + (e.reason || '') + '">' + e.name + '<small>当前不可用</small></span>';
      }
      const ext = /^https?:/i.test(e.url);
      return '<a href="' + e.url + '"' + (ext ? ' target="_blank" rel="noopener noreferrer"' : '') + '>' +
        e.name + (e.note ? '<small>' + e.note + '</small>' : '') + '</a>';
    }).join('');
    msg.textContent = '';
  } catch (e) {
    msg.className = 'msg err';
    msg.textContent = '入口加载失败：' + e.message;
  }
}
function renderStatus(data) {
  renderServices(data.services);
  renderSecrets(data.secrets);
  renderCredentials(data.credentials || {});
  const ov = data.overview || {};
  const cert = data.cert || {};
  const mem = ov.memory || {};
  const disk = ov.disk || {};
  $('#overview').innerHTML =
    kv('Uptime', fmtDur(ov.uptime_seconds)) +
    kv('Load', (ov.load || []).join(' / ') || '—') +
    kv('内存', mem.used_percent !== null ? mem.used_percent + '%' : '—',
       fmtBytes(mem.available) + ' 可用') +
    kv('磁盘 (rootfs)', disk.used_percent !== null ? disk.used_percent + '%' : '—',
       fmtBytes(disk.free) + ' 可用') +
    kv('证书剩余', cert.ok ? cert.days_left + ' 天' : '—',
       cert.ok && cert.days_left < 21 ? '<span class="warn">即将到期</span>' : '');

  const tel = data.telemetry || {};
  if (tel.ok) {
    const last = tel.last || {};
    const batt = last.batt_level !== null ? last.batt_level + '%' : '—';
    $('#telemetry').innerHTML =
      kv('最后采样', last.ts || '—', (tel.samples || 0) + ' 样本') +
      kv('负载', last.load1 || '—') +
      kv('电池', batt, last.batt_status || '') +
      kv('温度', last.batt_temp_raw ? (Number(last.batt_temp_raw) / 10).toFixed(1) + ' °C' : '—') +
      kv('服务可用率', tel.availability_percent + '%') +
      kv('重启次数', tel.reboots);
  } else {
    $('#telemetry').innerHTML = kv('遥测', '不可用', tel.error || '');
  }
  const soak = data.soak || {};
  if (soak.ok) {
    const progress = soak.target_seconds ? Math.min(100, Math.round(soak.elapsed_seconds / soak.target_seconds * 100)) : 0;
    $('#soak').innerHTML = 'soak 起点 <b>' + (soak.start_utc || '—') + '</b>，已运行 ' + fmtDur(soak.elapsed_seconds) +
      (soak.remaining_seconds > 0 ? '，剩余 ' + fmtDur(soak.remaining_seconds) : '') +
      (soak.samples_since_start !== undefined ? '，本窗口样本 ' + soak.samples_since_start : '') +
      '<div class="bar"><i style="width:' + progress + '%"></i></div>' +
      '<span style="color:#6f7a8c;font-size:12px">控制台只展示观测值，不判定验收通过。</span>';
  } else {
    $('#soak').textContent = '';
  }
  if (!window.__logInit) {
    window.__logInit = true;
    const sel = $('#log-name');
    sel.innerHTML = (data.logs || []).map(function (n) {
      return '<option value="' + n + '">' + n + '</option>';
    }).join('');
    sel.addEventListener('change', loadLog);
    $('#log-refresh').addEventListener('click', loadLog);
    loadLog();
  }
  $('#updated').textContent = '更新于 ' + new Date().toLocaleTimeString();
}
async function loadStatus() {
  try {
    renderStatus(await api('/api/status'));
  } catch (e) {
    $('#updated').textContent = '状态获取失败：' + e.message;
  }
}
async function loadLog() {
  const name = $('#log-name').value;
  if (!name) return;
  const lines = Math.max(20, Math.min(2000, Number($('#log-lines').value) || 200));
  const msg = $('#log-msg'); msg.className = 'msg'; msg.textContent = '读取中…';
  try {
    const data = await api('/api/log?name=' + encodeURIComponent(name) + '&lines=' + lines);
    $('#log-body').textContent = data.content || '（空）';
    msg.textContent = data.path + ' · ' + (data.bytes || 0) + ' B';
  } catch (e) {
    msg.className = 'msg err'; msg.textContent = '读取失败：' + e.message;
  }
}
async function refreshBackup() {
  try {
    const data = await api('/api/backup');
    const lines = [];
    if (data.status && data.status.last_done) lines.push('最近成功：' + data.status.last_done);
    if (data.status && data.status.last_start) lines.push('最近开始：' + data.status.last_start);
    if (data.status && data.status.last_fail) lines.push('最近失败：' + data.status.last_fail);
    if (data.status && data.status.error) lines.push('错误：' + data.status.error);
    $('#backup-status').textContent = lines.length ? lines.join('\\n') : '（backup.log 中暂无备份记录）';
  } catch (e) {
    $('#backup-status').textContent = '读取失败：' + e.message;
  }
}
$('#backup-now').addEventListener('click', async function () {
  const btn = this;
  const msg = $('#backup-msg');
  if (!armConfirm('backup', btn, '备份',
      '即将立即触发一次备份（快照 → 加密 → 上传）：会占用 CPU/IO 与网络，不要重复触发', msg)) return;
  btn.disabled = true;
  msg.className = 'msg'; msg.textContent = '已提交，等待 backup-loop 拾取…';
  try {
    const data = await api('/api/backup', {method: 'POST', body: '{}'});
    msg.className = 'msg ok'; msg.textContent = (data.message || '已提交');
    setTimeout(refreshBackup, 3000);
    setTimeout(refreshBackup, 12000);
    const st = await api('/api/backup');
    const s = st.status || {};
    msg.textContent += '；最近开始 ' + (s.last_start || '—') + '，最近成功 ' + (s.last_done || '—') +
      (s.last_fail ? '，最近失败 ' + s.last_fail : '');
  } catch (e) {
    msg.className = 'msg err'; msg.textContent = '触发失败：' + e.message;
  } finally {
    btn.disabled = false;
  }
});
$('#logout').addEventListener('click', async function () {
  try { await api('/api/logout', {method: 'POST', body: '{}'}); } catch (e) {}
  location.replace(P + '/');
});
// ---- 访问入口：公网 / 局域网 ----
let LAN = {ok: false};
let LANProbe = 'unknown';
function onLanListener() {
  return location.protocol === 'http:' && LAN.lan_port && location.port === String(LAN.lan_port);
}
async function probeLan(data) {
  if (!data.ok || !data.lan_ip || !data.lan_port) return 'unknown';
  const ctrl = new AbortController();
  const timer = setTimeout(function () { ctrl.abort(); }, 2500);
  try {
    const url = 'http://' + data.lan_ip + ':' + data.lan_port + P + '/lan-probe';
    const res = await fetch(url, {cache: 'no-store', signal: ctrl.signal});
    const body = await res.json().catch(function () { return {}; });
    return body.same_subnet ? 'same' : 'different';
  } catch (e) {
    // HTTPS 页面会拦截 http 探测（混合内容），此时无法判定，按“未知”处理
    return 'unknown';
  } finally {
    clearTimeout(timer);
  }
}
function renderAccess() {
  const lan = onLanListener();
  const here = lan ? '局域网' : '公网';
  // 显示真实可用入口：局域网显示 lan_url，公网显示配置的 IP 入口（不再回显失效域名）
  const hereUrl = lan ? (LAN.lan_url || '') : (LAN.public_root || location.origin);
  const state = !LAN.ok ? '未探测到'
    : (LANProbe === 'same' ? '同网段可达' : LANProbe === 'different' ? '不同网段' : '未知（浏览器限制）');
  $('#access').innerHTML =
    kv('当前入口', here, hereUrl) +
    kv('局域网地址', LAN.lan_url ? (LAN.lan_ip + ':' + LAN.lan_port) : '—', LAN.lan_subnet || '') +
    kv('探测时间', LAN.updated_at || '—', '每 ' + (LAN.probe_interval_seconds || 30) + 's 刷新') +
    kv('同网段判定', state);
  const btn = $('#lan-go');
  const msg = $('#lan-msg');
  msg.className = 'msg';
  if (!LAN.ok) {
    btn.style.display = 'none';
    msg.textContent = '设备当前未探测到局域网地址' + (LAN.error ? '（' + LAN.error + '）' : '') + '。';
    return;
  }
  if (onLanListener()) {
    btn.style.display = 'none';
    msg.textContent = '当前已在局域网入口，不再消耗公网流量。';
    return;
  }
  if (LANProbe === 'different') {
    btn.style.display = 'none';
    msg.textContent = '当前网络与设备不同网段，已隐藏跳转按钮。';
    return;
  }
  btn.style.display = '';
  msg.textContent = LANProbe === 'same'
    ? '已检测为同网段，可切换到局域网入口。'
    : '未能自动探测同网段（HTTPS 页面限制），点击将尝试跳转。';
}
async function loadLan() {
  try { LAN = await api('/api/lan'); } catch (e) { LAN = {ok: false}; }
  LANProbe = await probeLan(LAN);
  renderAccess();
}
$('#lan-go').addEventListener('click', async function () {
  const btn = this;
  const msg = $('#lan-msg');
  btn.disabled = true; msg.className = 'msg'; msg.textContent = '生成一次性票据…';
  try {
    const data = await api('/api/lan-ticket', {method: 'POST', body: '{}'});
    if (!data.url) throw new Error('未返回局域网地址');
    msg.textContent = '票据 ' + data.expires_in + ' 秒内有效，正在跳转…';
    location.href = data.url;
  } catch (e) {
    msg.className = 'msg err'; msg.textContent = '跳转失败：' + e.message;
    btn.disabled = false;
  }
});
$('#cred-download').addEventListener('click', async function () {
  const msg = $('#cred-msg');
  msg.className = 'msg';
  msg.textContent = '生成一次性链接…';
  try {
    const d = await api('/api/credentials/token', {method: 'POST', body: '{}'});
    msg.textContent = '一次性链接 ' + d.expires_in + ' 秒内有效，下载一次后失效。';
    // 服务端返回的 path 已含控制台前缀（如 /console/api/...），此处不能再拼 P
    location.href = d.path;
  } catch (e) {
    msg.className = 'msg err';
    msg.textContent = '获取下载链接失败：' + e.message;
  }
});
$('#newpw-copy').addEventListener('click', async function () {
  const value = $('#newpw-value').textContent;
  if (!value) return;
  try {
    await navigator.clipboard.writeText(value);
    $('#newpw-ttl').textContent = '已复制';
  } catch (e) {
    $('#newpw-ttl').textContent = '复制失败，请长按选择';
  }
});
$('#newpw-hide').addEventListener('click', hideOnce);
loadEntries();
window.addEventListener('beforeunload', hideOnce);
loadStatus();
refreshBackup();
loadLan();
setInterval(loadStatus, 10000);
setInterval(refreshBackup, 30000);
setInterval(loadLan, 15000);
setInterval(loadEntries, 30000);
</script>
</body></html>
"""


def render_login(title: str, console_path: str, host_label: str, error: str = "") -> str:
    return (
        LOGIN_HTML.replace("__TITLE__", title)
        .replace("__CONSOLE_PATH__", console_path)
        .replace("__HOST_LABEL__", host_label)
        .replace("__ERROR__", error)
    )


def render_app(title: str, console_path: str) -> str:
    return APP_HTML.replace("__TITLE__", title).replace("__CONSOLE_PATH__", console_path)
