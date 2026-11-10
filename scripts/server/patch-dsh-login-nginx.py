#!/usr/bin/env python3
"""把 nginx 的 dsh-tls 配置改成"稳定登录入口"：

- location = /app-login：Basic Auth 后反代到 127.0.0.1:3082（dsh-login 自动 302 到当前 token）
- location /app/：DSH 返回 401 时自动跳 /app-login，用户打开 /app/ 即可无感登录

用法：python3 patch-dsh-login-nginx.py [配置文件路径]
默认路径 /etc/nginx/sites-available/dsh-tls；修改前自动备份。
"""
import re
import shutil
import sys
import time

DEFAULT = "/etc/nginx/sites-available/dsh-tls"
path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT
with open(path, encoding="utf-8") as fh:
    src = fh.read()

bak = path + ".bak-dshlogin-" + time.strftime("%Y%m%d-%H%M%S")
shutil.copy2(path, bak)

NEW_LOGIN = '''    # --- DSH 稳定登录入口：从 dsh.log 取当前 token 后 302 到 /app/?token=... ---
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

work, n_err = re.subn(
    r'(    location /app/ \{\n(?:.*?\n)*?        auth_basic_user_file [^\n]+\n)',
    r'\1        proxy_intercept_errors on;\n        error_page 401 =302 /app-login;\n',
    work, count=1, flags=re.S)
if n_err == 0:
    sys.exit("未找到 location /app/ 的 auth_basic_user_file，未修改")

if "proxy_intercept_errors on" not in work:
    sys.exit("error_page 插入失败，未修改")

with open(path, "w", encoding="utf-8") as fh:
    fh.write(work)
print("OK: 已更新", path)
print("备份:", bak)
