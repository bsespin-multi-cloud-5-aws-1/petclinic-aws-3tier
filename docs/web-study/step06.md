<callout icon="🪶" color="blue_bg">
	**이 단계의 목표**: WEB 서버에서 실제로 돌아가는 `/etc/httpd/conf.d/petclinic.conf` 의 모든 줄을 "왜 있나" 로 설명할 수 있게. 이 파일은 `user_data/web.sh` 가 부팅 때 만든다. 하루 분량.
</callout>
# 0. 역할 — Apache 는 두 가지를 한다
<table header-row="true" fit-page-width="true">
	<tr>
		<td>경로</td>
		<td>Apache 가 하는 일</td>
		<td>이유</td>
	</tr>
	<tr>
		<td>`/` · `/static/*` · `/images/*` · `/health.html`</td>
		<td>**직접 서빙**(파일)</td>
		<td>랜딩 페이지·자산·헬스체크는 WAS 없이도 줘야 한다 (`/static/*` `/images/*` 는 지금 CloudFront → S3 가 먼저 받지만 Apache 에도 사본이 있어 폴백)</td>
	</tr>
	<tr>
		<td>`/petclinic/*`</td>
		<td>**리버스 프록시** → Internal ALB :8080 → Tomcat</td>
		<td>앱은 WAS 가. WEB 은 WAS 의 IP 를 모르고 Internal ALB 이름만 안다 → WAS 교체·증설 시 WEB 무변경</td>
	</tr>
</table>
# 1. 실제 파일 (web.sh 가 만드는 그대로 · 값은 mc-deploy)

```apache
ProxyPreserveHost On
RewriteEngine On
RewriteCond %{HTTP:X-Forwarded-Proto} =https
RewriteRule ^/petclinic/$ https://%{HTTP_HOST}/ [R=302,L]
RewriteRule ^/petclinic/$ / [R=302,L]
RewriteCond %{HTTP:X-Forwarded-Proto} =https
RewriteRule ^/petclinic$ https://%{HTTP_HOST}/petclinic/ [R=301,L]
RewriteRule ^/petclinic$ /petclinic/ [R=301,L]
ProxyPass        /health.html !
ProxyPass        /static/ !
ProxyPass        /images/ !
Alias            /images/ /var/www/html/static/images/
ProxyPass        /petclinic/ http://internal-mc-alb-internal-692352220.ap-northeast-2.elb.amazonaws.com:8080/petclinic/
ProxyPassReverse /petclinic/ http://internal-mc-alb-internal-692352220.ap-northeast-2.elb.amazonaws.com:8080/petclinic/
SetEnvIf Request_URI "^/health.html$" nolog
CustomLog /var/log/httpd/access_log combined env=!nolog
```

# 2. 한 줄씩
<table header-row="true" fit-page-width="true">
	<tr>
		<td>줄</td>
		<td>뜻</td>
		<td>없으면</td>
	</tr>
	<tr>
		<td>`ProxyPreserveHost On`</td>
		<td>프록시할 때 원래 `Host`(petclinic.mission-critical.site)를 그대로 넘김. 기본은 오리진 주소(Internal ALB 이름)로 바꿈</td>
		<td>Tomcat 이 만드는 리다이렉트·절대 링크가 `internal-mc-alb-…:8080` 이 되어 사용자 브라우저가 못 여는 주소를 받음</td>
	</tr>
	<tr>
		<td>`RewriteEngine On`</td>
		<td>mod_rewrite 켜기</td>
		<td>아래 RewriteRule 전부 무시</td>
	</tr>
	<tr>
		<td>`RewriteCond … X-Forwarded-Proto =https` + `RewriteRule ^/petclinic/$ https://%｛HTTP_HOST｝/ [R=302,L]`</td>
		<td>앱 홈 `/petclinic/` 로 오면 랜딩 `/` 로 302 — 단 원래 요청이 https 였으면 Location 도 https 로</td>
		<td>히어로 화면이 두 번(랜딩 + welcome.jsp) 보임 · https 조건 없으면 `Location: http://…` → CloudFront 가 다시 https 로 → **루프**</td>
	</tr>
	<tr>
		<td>`RewriteRule ^/petclinic/$ / [R=302,L]`</td>
		<td>위 조건이 안 맞을 때(평문 직접 접근)의 폴백</td>
		<td>—</td>
	</tr>
	<tr>
		<td>`^/petclinic$ → /petclinic/ [R=301]`</td>
		<td>슬래시 없는 `/petclinic` 을 `/petclinic/` 로(Tomcat 컨텍스트 경로 규칙). 마찬가지로 https 조건</td>
		<td>Tomcat 이 자기 주소로 301 을 만들어 위와 같은 문제</td>
	</tr>
	<tr>
		<td>`ProxyPass /health.html !`</td>
		<td>`!` = **프록시 제외**. 이 경로는 Apache 가 직접</td>
		<td>헬스체크가 WAS 까지 감 → 5단계의 '얕게' 가 깨짐</td>
	</tr>
	<tr>
		<td>`ProxyPass /static/ !` · `/images/ !`</td>
		<td>정적 자산도 제외 → 파일로 서빙</td>
		<td>정적 요청이 WAS 로 가서 404</td>
	</tr>
	<tr>
		<td>`Alias /images/ /var/www/html/static/images/`</td>
		<td>URL `/images/…` 를 디스크 `/var/www/html/static/images/…` 에 매핑. WAS 의 welcome.jsp 가 옛 경로 `/images/hero/hero.mp4` 를 쓰기 때문</td>
		<td>hero.mp4 404 (9/16 실제로 겪음)</td>
	</tr>
	<tr>
		<td>`ProxyPass /petclinic/ http://internal-…:8080/petclinic/`</td>
		<td>핵심. `/petclinic/` 이하를 Internal ALB 로 전달(mod_proxy_http)</td>
		<td>앱 없음</td>
	</tr>
	<tr>
		<td>`ProxyPassReverse …`</td>
		<td>WAS 응답의 `Location` 헤더 안 주소가 내부 주소면 바깥 주소로 되돌려 씀</td>
		<td>WAS 가 리다이렉트할 때 사용자에게 내부 주소가 노출</td>
	</tr>
	<tr>
		<td>`SetEnvIf Request_URI "^/health.html$" nolog` + `CustomLog … env=!nolog`</td>
		<td>헬스체크 요청은 `nolog` 표시 → 로그에서 제외</td>
		<td>10초마다 ALB 노드 2개가 찍는 줄로 access_log 가 가득 참</td>
	</tr>
</table>
순서가 중요: `ProxyPass … !`(제외)가 `ProxyPass /petclinic/`(전달)보다 **위**에 있어야 한다. mod_proxy 는 위에서부터 첫 매치를 쓴다.
# 3. mod_proxy_http 인가 mod_jk 인가
<table header-row="true" fit-page-width="true">
	<tr>
		<td></td>
		<td>mod_proxy_http (우리)</td>
		<td>mod_jk (AJP)</td>
	</tr>
	<tr>
		<td>프로토콜</td>
		<td>HTTP — 중간에 **ALB 를 둘 수 있다**</td>
		<td>AJP(바이너리) — ALB 가 못 알아들음 → WEB 이 WAS IP 를 직접 알아야 함</td>
	</tr>
	<tr>
		<td>WAS 교체·증설</td>
		<td>Internal ALB 가 흡수, WEB 무변경</td>
		<td>workers.properties 수정 + 재시작</td>
	</tr>
	<tr>
		<td>성능</td>
		<td>요즘 차이 미미(keep-alive 로 연결 재사용)</td>
		<td>약간 유리했던 시절의 선택</td>
	</tr>
	<tr>
		<td>결론</td>
		<td>3-Tier + ALB 구조면 mod_proxy_http</td>
		<td>ALB 없이 WEB↔WAS 1:1 고정일 때만</td>
	</tr>
</table>
# 4. 눈으로 확인 (Bastion 경유)

```bash
ssh -i infra/terraform-kdt5/.keys/mc-ssh.pem -J ec2-user@52.78.145.87 ec2-user@10.0.10.189
# 1) 파일 그대로
cat /etc/httpd/conf.d/petclinic.conf
# 2) 로드된 모듈 — proxy_http · rewrite · alias 가 있어야
httpd -M 2>/dev/null | grep -E "proxy_http|rewrite|alias|mpm"
# 3) 직접 서빙 vs 프록시 vs 리다이렉트
curl -si http://localhost/ | head -1                                   # 200 (index.html)
curl -si http://localhost/health.html | head -1                        # 200 (ok)
curl -si http://localhost/petclinic/ | grep -E "^HTTP|^Location"       # 302 Location: /   (평문이라 https 조건 불일치 → 폴백 규칙)
curl -si -H "X-Forwarded-Proto: https" -H "Host: petclinic.mission-critical.site" http://localhost/petclinic/ | grep -E "^HTTP|^Location"   # 302 Location: https://petclinic.mission-critical.site/
curl -si http://localhost/petclinic | grep -E "^HTTP|^Location"        # 301 → /petclinic/
curl -si http://localhost/petclinic/vets | head -1                     # 200 — Internal ALB 를 거쳐 Tomcat 이 답한 것
# 4) 헬스체크가 로그에 없는지
sudo tail -20 /var/log/httpd/access_log | grep -c health.html           # 0
```

# 5. 다음 단계 진입 기준
<details>
<summary>Q1. `ProxyPreserveHost On` 을 끄면 사용자가 어떤 증상을 보나?</summary>
	Tomcat 이 만드는 리다이렉트(예: 폼 제출 후)가 `http://internal-mc-alb-internal-…:8080/…` 로 와서 브라우저가 열지 못한다(내부 이름·사설망).
</details>
<details>
<summary>Q2. RewriteRule 앞의 RewriteCond(X-Forwarded-Proto) 를 지우면?</summary>
	Apache 는 평문으로 받으니 `Location: http://…/` 를 준다 → CloudFront 가 http→https 리다이렉트 → 다시 Apache → 무한 루프 또는 혼합 콘텐츠.
</details>
<details>
<summary>Q3. `ProxyPass /health.html !` 을 `ProxyPass /petclinic/` 아래로 옮기면?</summary>
	위에서 첫 매치라 `/health.html` 은 `/petclinic/` 과 안 겹쳐 사실 동작은 같다. 하지만 `/static/ !` 처럼 겹칠 수 있는 제외 규칙은 반드시 위에 — 습관적으로 제외를 먼저.
</details>
# 6. 읽을 자료
- Apache 문서 — *mod_proxy* (`ProxyPass`, `ProxyPassReverse`, `ProxyPreserveHost`, `!` 제외)
- Apache 문서 — *mod_rewrite* (`RewriteCond %｛HTTP:…｝`, 플래그 `R` `L`)
- 저장소 `infra/terraform-kdt5/modules/base/user_data/web.sh` (이 파일을 만드는 스크립트 · 콘솔 가이드 ⑤ 5-2)
<callout icon="🗺️" color="gray_bg">
	**로드맵 위치**: 0 VPC 입구 → 1 HTTP 기초 → 2 TLS 종료 지점 → 3 ALB 해부 → 4 오리진 보호(헤더) → 5 헬스체크 → **6 Apache 프록시(이 페이지)** → 7 분산·타임아웃 → 8 WEB 관측 → 9 장애 모드 → 10 ASG·AMI.
</callout>