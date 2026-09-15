#!/bin/bash
# WEB (Apache 2.4) — 정적 index.html 없음. / 은 WAS 의 홈(/petclinic/ = Spring welcome)으로 보내고 /petclinic/ 만 Internal ALB 로 프록시. AL2023.
# 왜: WEB 이 자체 index.html 을 가지면 화면이 두 곳(Apache·WAS)에 나뉘어 AMI/ASG 갱신 때 불일치. 첫 화면도 WAS 가 책임지게 해서 단일 소스 유지
set -uo pipefail
exec > >(tee -a /var/log/mc-userdata.log) 2>&1

rpm -q httpd >/dev/null 2>&1 || dnf install -y httpd

# ProxyPreserveHost: 리다이렉트 URL이 내부 ALB 주소로 바뀌지 않게
# RewriteRule ^/$ : 루트 요청은 WAS 홈으로 302 (Apache 의 index.html 대신). 302 인 이유: 경로가 Phase 2 에서 바뀔 수 있어 브라우저 영구 캐시(301) 회피
# RewriteRule ^/petclinic$ : 슬래시 없는 요청 404 방지
# /health.html 만 Apache 가 직접 응답(Public ALB 헬스체크 — / 는 302 라 헬스체크로 못 씀)
cat > /etc/httpd/conf.d/petclinic.conf <<CONF
ProxyPreserveHost On
RewriteEngine On
RewriteRule ^/$ ${app_context}/ [R=302,L]
RewriteRule ^${app_context}$ ${app_context}/ [R=301,L]
ProxyPass        /health.html !
ProxyPass        ${app_context}/ http://${internal_alb_dns}:8080${app_context}/
ProxyPassReverse ${app_context}/ http://${internal_alb_dns}:8080${app_context}/
SetEnvIf Request_URI "^/health.html$" nolog
CustomLog /var/log/httpd/access_log combined env=!nolog
CONF

# 이전 콘솔 구축본·AMI 에 남아 있을 수 있는 Apache 자체 index.html 제거 → 첫 화면은 WAS(/petclinic/) 가 담당
rm -f /var/www/html/index.html
echo ok > /var/www/html/health.html

# AL2023 SELinux: Apache 아웃바운드(→ Internal ALB) 허용. 없으면 502
setsebool -P httpd_can_network_connect 1 || true
apachectl configtest && systemctl enable --now httpd && systemctl restart httpd

# 확인: / 는 302 → /petclinic/, health.html 은 200
curl -s -o /dev/null -w "root %%{http_code} -> %%{redirect_url}\n" http://localhost/
curl -s -o /dev/null -w "health %%{http_code}\n" http://localhost/health.html
