#!/bin/bash
# WEB (Apache 2.4) — 정적 페이지(index.html) 직접 서빙 + /petclinic/ 만 Internal ALB 로 프록시. AL2023.
set -uo pipefail
exec > >(tee -a /var/log/mc-userdata.log) 2>&1

rpm -q httpd >/dev/null 2>&1 || dnf install -y httpd

# ProxyPreserveHost: 리다이렉트 URL이 내부 ALB 주소로 바뀌지 않게. RewriteRule: /petclinic(슬래시 없음) 404 방지
cat > /etc/httpd/conf.d/petclinic.conf <<CONF
ProxyPreserveHost On
RewriteEngine On
RewriteRule ^${app_context}$ ${app_context}/ [R=301,L]
ProxyPass        ${app_context}/ http://${internal_alb_dns}:8080${app_context}/
ProxyPassReverse ${app_context}/ http://${internal_alb_dns}:8080${app_context}/
SetEnvIf Request_URI "^/health.html$" nolog
CustomLog /var/log/httpd/access_log combined env=!nolog
CONF

echo ok > /var/www/html/health.html
[ -f /var/www/html/index.html ] || cat > /var/www/html/index.html <<'HTML'
<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>KDT 3-Tier Project</title></head>
<body style="font-family:Arial,sans-serif;text-align:center;margin-top:120px">
<h1>Mission Critical Pet Clinic</h1>
<a href="${app_context}/" style="display:inline-block;margin-top:30px;padding:14px 28px;background:#1976d2;color:#fff;text-decoration:none;border-radius:6px">진료 시스템 입장</a>
</body></html>
HTML

# AL2023 SELinux: Apache 아웃바운드(→ Internal ALB) 허용. 없으면 502
setsebool -P httpd_can_network_connect 1 || true
apachectl configtest && systemctl enable --now httpd && systemctl restart httpd
