#!/bin/bash
# WEB (Apache 2.4) — 첫 화면 = WAR 의 index.html (src/main/webapp/index.html) 을 Apache 가 직접 서빙.
# index.html 이 쓰는 자산(resources/·images/)은 같은 브랜치에서 /var/www/html/static/ 으로 복사해 Apache 가 직접 서빙(/static/* 은 CloudFront 캐시).
# 앱 링크(preview-info.html?route=/X)는 /petclinic/X 로. WAS 의 welcome.jsp 가 쓰는 /images/hero/hero.mp4 (옛 S3 경로) 는 Alias 로 같은 /static/images 를 서빙. WAR 에 index.html 이 없는 브랜치(main=Blue)면 / → 302 /petclinic/ 폴백.
# 왜 자산도 복사하나: Blue(main) WAR 에는 리디자인 css·영상이 없어 /petclinic/resources/… 로 보내면 404. 랜딩 페이지는 앱 브랜치와 독립이어야 함.
# /petclinic/ 만 Internal ALB 로 프록시. AL2023.
set -uo pipefail
exec > >(tee -a /var/log/mc-userdata.log) 2>&1

dnf install -y httpd git amazon-cloudwatch-agent

# ---- WAR 의 index.html 가져오기 (index_branch 가 비면 앱 브랜치와 동일) ----
INDEX_BRANCH="${index_branch}"
[ -z "$INDEX_BRANCH" ] && INDEX_BRANCH="${repo_branch}"
rm -rf /tmp/petclinic-src
git clone -q --depth 1 -b "$INDEX_BRANCH" "${repo_url}" /tmp/petclinic-src || echo "WARN: clone failed ($INDEX_BRANCH)"
ROOT_RULE=""
if [ -f /tmp/petclinic-src/src/main/webapp/index.html ]; then
  rm -rf /var/www/html/static && mkdir -p /var/www/html/static
  cp -r /tmp/petclinic-src/src/main/webapp/resources /var/www/html/static/resources
  [ -d /tmp/petclinic-src/src/main/webapp/images ] && cp -r /tmp/petclinic-src/src/main/webapp/images /var/www/html/static/images
  # 자산 상대 경로 → /static/… (Apache 직접) · preview-info.html?route=/X (디자인 패키지 스텁) → 실제 앱 경로 /petclinic/X
  sed -E \
    -e 's#(href|src|poster)="resources/#\1="/static/resources/#g' \
    -e 's#(href|src|poster)="images/#\1="/static/images/#g' \
    -e 's#href="preview-info\.html\?route=/#href="${app_context}/#g' \
    /tmp/petclinic-src/src/main/webapp/index.html > /var/www/html/index.html
  echo "index.html installed from $INDEX_BRANCH ($(wc -c < /var/www/html/index.html) bytes) · static $(du -sh /var/www/html/static | cut -f1)"
else
  rm -f /var/www/html/index.html
  ROOT_RULE='RewriteCond %%{HTTP:X-Forwarded-Proto} =https
RewriteRule ^/$ https://%%{HTTP_HOST}'"${app_context}"'/ [R=302,L]
RewriteRule ^/$ '"${app_context}"'/ [R=302,L]'
  echo "no index.html in $INDEX_BRANCH → / redirects to ${app_context}/"
fi
rm -rf /tmp/petclinic-src

cat > /etc/httpd/conf.d/petclinic.conf <<CONF
ProxyPreserveHost On
RewriteEngine On
$ROOT_RULE
RewriteCond %%{HTTP:X-Forwarded-Proto} =https
RewriteRule ^${app_context}$ https://%%{HTTP_HOST}${app_context}/ [R=301,L]
RewriteRule ^${app_context}$ ${app_context}/ [R=301,L]
ProxyPass        /health.html !
ProxyPass        /static/ !
ProxyPass        /images/ !
Alias            /images/ /var/www/html/static/images/
ProxyPass        ${app_context}/ http://${internal_alb_dns}:8080${app_context}/
ProxyPassReverse ${app_context}/ http://${internal_alb_dns}:8080${app_context}/
SetEnvIf Request_URI "^/health.html$" nolog
CustomLog /var/log/httpd/access_log combined env=!nolog
CONF

echo ok > /var/www/html/health.html

setsebool -P httpd_can_network_connect 1 || true
apachectl configtest && systemctl enable --now httpd && systemctl restart httpd

for i in $(seq 1 12); do
  /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl -a fetch-config -m ec2 -c "ssm:${cwagent_param}" -s && { echo "cwagent configured"; break; }
  echo "cwagent config retry $i/12"; sleep 10
done

curl -s -o /dev/null -w "root %%{http_code} -> %%{redirect_url}\n" http://localhost/
curl -s -o /dev/null -w "health %%{http_code}\n" http://localhost/health.html
