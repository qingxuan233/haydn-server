#!/usr/bin/env python3
"""更新 nginx dsh-tls，使其配合 dsh-login v2（cookie broker）：

- /app-login：Basic Auth 后反代 127.0.0.1:3082（dsh-login 服务端换取 cookie 后 302 /app/）
- /app/：没有 dsh-auth cookie 时直接 302 /app-login；DSH 若仍返回 401 也转 /app-login

幂等：会先清掉 /app/ 内旧的 proxy_intercept_errors / if-cookie / error_page 行再插入，
可重复执行，不会产生重复指令。

用法：python3 patch-dsh-login-nginx.py [配置文件路径]；修改前自动备份。
"""
import re
import shutil
import sys
import time

DEFAULT = "/etc/nginx/sites-available/dsh-tls"
path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT
with open(path, encoding="utf-8") as fh:
    src = fh.read()

bak = path + ".bak-broker-" + time.strftime("%Y%m%d-%H%M%S")
shutil.copy2(path, bak)

NEW_LOGIN = '''    # --- DSH 稳定登录入口：dsh-login broker（服务端取 cookie 后 302 /app/） ---
    location = /app-login {
        access_log off;
        absolute_redirect off;
        auth_basic "DSH App";
        auth_basic_user_file /root/server/etc/dsh-web.htpasswd;
        proxy_pass http://127.0.0.1:3082/login;
        proxy_http_version 1.1;
        proxy_set_header Host $http_host;
        proxy_set_header X-Forwarded-Proto https;
    }
'''

work, n_login = re.subn(r'    location = /app-login \{.*?\n    \}', NEW_LOGIN, src, count=1, flags=re.S)
if n_login == 0:
    sys.exit("未找到 location = /app-login 块，未修改")


def clean_app_block(match):
    body = match.group(1)
    drop = re.compile(r'^        (?:(?:proxy_intercept_errors on;)|(?:if \(\$http_cookie !~ "dsh-auth"\) \{ return 302 /app-login; \})|(?:error_page 401 =302 /app-login;)|(?:error_page 302 =302 /app-login;))\s*$', re.M)
    body = drop.sub('', body)
    insert = (
        '        proxy_intercept_errors on;\n'
        '        absolute_redirect off;\n'
        '        if ($http_cookie !~ "dsh-auth") { return 302 /app-login; }\n'
        '        error_page 401 =302 /app-login;\n'
    )
    # 插入到 auth_basic_user_file 之后
    body = re.sub(r'(        auth_basic_user_file [^\n]+\n)', lambda m: m.group(1) + insert, body, count=1)
    return '    location /app/ {\n' + body + '\n    }'


work, n_app = re.subn(r'    location /app/ \{\n(.*?)\n    \}', clean_app_block, work, count=1, flags=re.S)
if n_app == 0:
    sys.exit("未找到 location /app/ 块，未修改")

if 'if ($http_cookie !~ "dsh-auth")' not in work:
    sys.exit("cookie 检查插入失败，未修改")

with open(path, "w", encoding="utf-8") as fh:
    fh.write(work)
print("OK: 已更新", path)
print("备份:", bak)
