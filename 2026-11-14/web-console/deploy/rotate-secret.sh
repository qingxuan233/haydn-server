#!/bin/sh
# rotate-secret.sh — 网关 Basic 凭据轮换（改口令 → 写文件 → 回读校验 → 生效验证 → 失败回滚）
#
# 用法：
#   rotate-secret.sh <route>                 # 生成 24 位随机口令并轮换
#   rotate-secret.sh <route> --stdin         # 从标准输入读取新口令（≥12 位）
#   rotate-secret.sh vaultwarden             # 轮换 Vaultwarden 管理员 token（argon2 PHC）
#   rotate-secret.sh --check                 # 仅检查 /opt/haydn/secrets 权限与条目
#
# 说明：
# - 只改 <route> 对应的 Basic 凭据文件（默认 /opt/haydn/secrets/<route>.json），
#   网关按 mtime 热加载，无需重启；口令明文只写 600 文件，不打印、不入日志。
# - vaultwarden 分支：明文写 vaultwarden-admin-token.txt，PHC 写 vaultwarden-admin-token，
#   重启 haydn-vaultwarden 后用 /admin 登录验证；失败恢复两个文件并重启。
# - 失败时回滚旧文件，并用旧口令验证可继续访问；退出码 0 成功 / 2 失败已回滚。
set -eu

SECRET_DIR=/opt/haydn/secrets
AUDIT=/var/log/haydn/secret-rotate.log
TS=$(date -u +%Y%m%dT%H%M%SZ)

log() {
  mkdir -p "$(dirname "$AUDIT")"
  printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" >>"$AUDIT"
}

usage() {
  sed -n '2,15p' "$0" | sed 's/^# \{0,1\}//'
  exit 1
}

check_dir() {
  st=$(stat -c '%a %U %G' "$SECRET_DIR" 2>/dev/null || echo "missing")
  echo "secrets dir: $SECRET_DIR ($st)"
  find "$SECRET_DIR" -maxdepth 1 -type f -printf '%m %u %g %s %p\n' 2>/dev/null | sort || true
}

[ $# -ge 1 ] || usage

if [ "$1" = "--check" ]; then
  check_dir
  exit 0
fi

ROUTE=$1
shift || true
FROM_STDIN=0
for arg in "$@"; do
  case "$arg" in
    --stdin) FROM_STDIN=1 ;;
    *) usage ;;
  esac
done

[ "$(id -u)" = "0" ] || { echo "must run as root" >&2; exit 1; }
mkdir -p "$SECRET_DIR"
chmod 700 "$SECRET_DIR"

# ---- Vaultwarden 管理员 token 轮换（明文 + argon2 PHC，重启服务后登录验证）----
VW_PLAIN=$SECRET_DIR/vaultwarden-admin-token.txt
VW_PHC=$SECRET_DIR/vaultwarden-admin-token
SUPERVISORCTL="/usr/bin/supervisorctl -c /etc/supervisor/supervisord.conf"

rotate_vaultwarden() {
  command -v script >/dev/null 2>&1 || { echo "refusing: script(1) required for argon2 hashing" >&2; exit 1; }
  [ -x /opt/haydn/bin/vaultwarden ] || { echo "refusing: vaultwarden binary not found" >&2; exit 1; }

  if [ "$FROM_STDIN" = "1" ]; then
    IFS= read -r NEW_PASSWORD || true
  else
    NEW_PASSWORD=$(python3 -c 'import secrets,string;a=string.ascii_letters+string.digits;print("".join(secrets.choice(a) for _ in range(40)))')
  fi
  [ "${#NEW_PASSWORD}" -ge 12 ] || { echo "refusing: token must be at least 12 characters" >&2; exit 1; }

  vw_plain_backup="$VW_PLAIN.bak-$TS"
  vw_phc_backup="$VW_PHC.bak-$TS"
  [ -f "$VW_PLAIN" ] && cp -p "$VW_PLAIN" "$vw_plain_backup"
  [ -f "$VW_PHC" ] && cp -p "$VW_PHC" "$vw_phc_backup"

  vw_rollback() {
    reason=$1
    [ -f "$vw_plain_backup" ] && cp -p "$vw_plain_backup" "$VW_PLAIN"
    [ -f "$vw_phc_backup" ] && cp -p "$vw_phc_backup" "$VW_PHC"
    $SUPERVISORCTL restart haydn-vaultwarden >/dev/null 2>&1 || true
    log "ROTATE FAIL route=vaultwarden reason=$reason rolled_back=1"
    echo "FAILED ($reason); 旧 token 已回滚" >&2
    exit 2
  }

  HASH=$(printf '%s\n%s\n' "$NEW_PASSWORD" "$NEW_PASSWORD" \
    | script -qec '/opt/haydn/bin/vaultwarden hash --preset owasp' /dev/null 2>&1 \
    | tr -d '\r' | sed -n "s/^ADMIN_TOKEN='\(.*\)'$/\1/p")
  [ -n "$HASH" ] || vw_rollback "argon2_hash"

  ( umask 077; printf '%s\n' "$NEW_PASSWORD" >"$VW_PLAIN" )
  ( umask 077; printf '%s\n' "$HASH" >"$VW_PHC" )
  chmod 600 "$VW_PLAIN" "$VW_PHC"

  $SUPERVISORCTL restart haydn-vaultwarden >/dev/null || vw_rollback "supervisor_restart"
  sleep 6

  python3 - "$VW_PLAIN" <<'PY' || vw_rollback "admin_login_verify"
import http.client, sys, urllib.parse
token = open(sys.argv[1]).read().strip()
conn = http.client.HTTPConnection("127.0.0.1", 18084, timeout=20)
conn.request("POST", "/admin", body=urllib.parse.urlencode({"token": token}),
             headers={"Content-Type": "application/x-www-form-urlencoded"})
r = conn.getresponse()
ok = r.status == 200 and "VW_ADMIN" in (r.getheader("Set-Cookie") or "")
r.read()
conn.close()
raise SystemExit(0 if ok else 1)
PY

  log "ROTATE OK route=vaultwarden admin_login=200"
  echo "rotated: vaultwarden admin token"
  echo "new plaintext: $VW_PLAIN (600; 读取后请删除或转存)"
  echo "backup: ${vw_phc_backup:-none}"
  exit 0
}

if [ "$ROUTE" = "vaultwarden" ]; then
  rotate_vaultwarden
fi

CONFIG=${HAYDN_GATEWAY_CONFIG:-/etc/haydn-console/gateway.json}
GATEWAY=/opt/haydn/console/gateway.py
[ -f "$CONFIG" ] || { echo "config not found: $CONFIG" >&2; exit 1; }

# 解析路由：secret_file / auth_user
META=$(python3 - "$CONFIG" "$ROUTE" <<'PY'
import json, sys
cfg = json.load(open(sys.argv[1], encoding="utf-8"))
name = sys.argv[2]
for r in cfg.get("upstreams", []):
    if r.get("name") == name:
        print(r.get("secret_file") or f"/opt/haydn/secrets/{name}.json")
        print(r.get("auth_user") or "haydn")
        print(r.get("path") or "")
        break
PY
)
[ -n "$META" ] || { echo "refusing: no upstream named $ROUTE" >&2; exit 1; }
SECRET_FILE=$(printf '%s\n' "$META" | sed -n 1p)
AUTH_USER=$(printf '%s\n' "$META" | sed -n 2p)
ROUTE_PATH=$(printf '%s\n' "$META" | sed -n 3p)
PLAIN_FILE=${SECRET_FILE%.json}-password.txt

if [ "$FROM_STDIN" = "1" ]; then
  IFS= read -r NEW_PASSWORD || true
else
  NEW_PASSWORD=$(python3 - <<'PY'
import sys
sys.path.insert(0, "/opt/haydn/console")
import auth
print(auth.generate_password(24))
PY
)
fi
[ "${#NEW_PASSWORD}" -ge 12 ] || { echo "refusing: password must be at least 12 characters" >&2; exit 1; }

OLD_PASSWORD=""
[ -f "$PLAIN_FILE" ] && OLD_PASSWORD=$(cat "$PLAIN_FILE")

backup=""
[ -f "$SECRET_FILE" ] && backup="$SECRET_FILE.bak-$TS" && cp -p "$SECRET_FILE" "$backup"
plain_backup=""
[ -f "$PLAIN_FILE" ] && plain_backup="$PLAIN_FILE.bak-$TS" && cp -p "$PLAIN_FILE" "$plain_backup"

rollback() {
  reason=$1
  if [ -n "$backup" ] && [ -f "$backup" ]; then
    cp -p "$backup" "$SECRET_FILE"
  fi
  if [ -n "$plain_backup" ] && [ -f "$plain_backup" ]; then
    cp -p "$plain_backup" "$PLAIN_FILE"
  elif [ -z "$plain_backup" ]; then
    rm -f "$PLAIN_FILE"
  fi
  log "ROTATE FAIL route=$ROUTE reason=$reason rolled_back=1"
  echo "FAILED ($reason); 旧凭据已回滚" >&2
  exit 2
}

# 1) 写入新凭据
printf '%s\n' "$NEW_PASSWORD" | python3 "$GATEWAY" --config "$CONFIG" --set-basic "$ROUTE" >/dev/null \
  || rollback "gateway_set_basic"

# 2) 明文文件（600，仅设备侧）
( umask 077; printf '%s\n' "$NEW_PASSWORD" >"$PLAIN_FILE" )
chmod 600 "$PLAIN_FILE"

# 3) 回读校验：文件里的哈希必须能验证新口令
python3 - "$SECRET_FILE" "$NEW_PASSWORD" <<'PY' || rollback "readback_verify"
import sys
sys.path.insert(0, "/opt/haydn/console")
import auth
record = auth.load_secret(sys.argv[1])
if not record or not auth.verify_password(record.get("password") or {}, sys.argv[2]):
    raise SystemExit(1)
PY

# 4) 生效验证：新口令可通过网关，旧口令必须 401（网关按 mtime 热加载）
HTTP_RESULT=$(python3 - "$AUTH_USER" "$NEW_PASSWORD" "$OLD_PASSWORD" "$ROUTE_PATH" <<'PY'
import base64, sys, urllib.error, urllib.request

user, new, old, path = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4] or "/"
url = "http://127.0.0.1:18080" + path

def code(password):
    token = base64.b64encode(f"{user}:{password}".encode()).decode()
    req = urllib.request.Request(url, headers={"Authorization": "Basic " + token, "Host": "qingxuan.bbs0.cc"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return 0

new_code = code(new)
old_code = code(old) if old else 401
print(f"{new_code} {old_code}")
ok = new_code not in (0, 401, 403, 500) and old_code in (401, 0)
raise SystemExit(0 if ok else 1)
PY
) || rollback "http_verify new/old=$HTTP_RESULT"

log "ROTATE OK route=$ROUTE user=$AUTH_USER new_http=$(echo "$HTTP_RESULT" | cut -d' ' -f1) old_http=$(echo "$HTTP_RESULT" | cut -d' ' -f2)"
echo "rotated: route=$ROUTE user=$AUTH_USER"
echo "new plaintext: $PLAIN_FILE (600; 读取后请删除)"
echo "backup: ${backup:-none}"
