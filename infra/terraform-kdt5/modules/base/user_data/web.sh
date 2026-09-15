#!/bin/bash
# WEB (Apache 2.4) — index.html 없음: / 는 WAS 홈(/petclinic/)으로 302. /petclinic/ 만 Internal ALB 로 프록시. AL2023.
# CloudFront(HTTPS) 뒤에서는 리다이렉트를 https 절대 URL 로, ALB 직접(http) 테스트에서는 상대 경로로.
set -uo pipefail
exec > >(tee -a /var/log/mc-userdata.log) 2>&1

dnf install -y httpd amazon-cloudwatch-agent

cat > /etc/httpd/conf.d/petclinic.conf <<CONF
ProxyPreserveHost On
RewriteEngine On
RewriteCond %%{HTTP:X-Forwarded-Proto} =https
RewriteRule ^/$ https://%%{HTTP_HOST}${app_context}/ [R=302,L]
RewriteRule ^/$ ${app_context}/ [R=302,L]
RewriteCond %%{HTTP:X-Forwarded-Proto} =https
RewriteRule ^${app_context}$ https://%%{HTTP_HOST}${app_context}/ [R=301,L]
RewriteRule ^${app_context}$ ${app_context}/ [R=301,L]
ProxyPass        /health.html !
ProxyPass        ${app_context}/ http://${internal_alb_dns}:8080${app_context}/
ProxyPassReverse ${app_context}/ http://${internal_alb_dns}:8080${app_context}/
SetEnvIf Request_URI "^/health.html$" nolog
CustomLog /var/log/httpd/access_log combined env=!nolog
CONF

rm -f /var/www/html/index.html
echo ok > /var/www/html/health.html

setsebool -P httpd_can_network_connect 1 || true
apachectl configtest && systemctl enable --now httpd && systemctl restart httpd

# CloudWatch Agent: 루트가 만든 SSM 파라미터(${cwagent_param}) 로 설정. 파라미터·인라인 정책이 아직 없을 수 있어 재시도
for i in $(seq 1 12); do
  /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl -a fetch-config -m ec2 -c "ssm:${cwagent_param}" -s && { echo "cwagent configured"; break; }
  echo "cwagent config retry $i/12"; sleep 10
done

curl -s -o /dev/null -w "root %%{http_code} -> %%{redirect_url}\n" http://localhost/
curl -s -o /dev/null -w "health %%{http_code}\n" http://localhost/health.html
