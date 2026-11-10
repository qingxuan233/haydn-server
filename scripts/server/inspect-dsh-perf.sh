#!/bin/sh
echo "=== nginx gzip/http2 ==="
nginx -T > /tmp/nt.txt 2>/dev/null
grep -nE "gzip|http2" /tmp/nt.txt | head -12
grep -n "listen .*8443" /tmp/nt.txt | head -3
echo "=== page via nginx localhost ==="
curl -k -s -u dsh:dsh4abc8b6abcbce334 -o /tmp/page.html -w "status=%{http_code} size=%{size_download} ttfb=%{time_starttransfer}s total=%{time_total}s\n" --max-time 15 https://127.0.0.1:8443/app-login
echo "client.js 出现次数: $(grep -o client.js /tmp/page.html 2>/dev/null | wc -l)"
echo "页面大小: $(stat -c %s /tmp/page.html 2>/dev/null)"
rm -f /tmp/nt.txt /tmp/page.html
echo "=== profile files checksum ==="
md5sum /root/.dsh/profiles/web/package.json /root/.dsh/profiles/web/cordis.patch.yml /etc/nginx/sites-available/dsh-tls 2>/dev/null
