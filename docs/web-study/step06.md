<callout icon="🪶" color="blue_bg">
	**이 단계의 목표**: WEB 서버에서 실제로 돌아가는 `/etc/httpd/conf.d/petclinic.conf` 의 모든 줄을 "왜 있나 · 없으면 어떻게 되나" 로 설명할 수 있게. 이 파일은 `user_data/web.sh` 가 부팅 때 만든다. 하루 분량. 값은 2026-09-17 mc-deploy 실측(경로별 응답 코드는 CloudFront 경유로 확인).
</callout>
# 0. 그림 한 장

```text
ALB ──평문 80──▶ Apache 2.4.68 (AL2023) ──┬── ① 직접 서빙: /  /health.html  /static/*  /images/*      ← 파일 (/var/www/html)
                                          └── ① 프록시:   /petclinic/* ──④ ProxyPass──▶ http://internal-mc-alb-internal-….elb.amazonaws.com:8080/petclinic/ ──▶ Tomcat
   ② ProxyPreserveHost On (Host 그대로)   ③ Rewrite: /petclinic/ → /  (302) · /petclinic → /petclinic/ (301) · 둘 다 X-Forwarded-Proto 조건   ⑤ 로그: 헬스체크 제외(의도) · mod_proxy_http
```

Apache 는 여기서 **두 가지**를 한다: 랜딩·자산·헬스체크는 **파일로 직접**, 앱은 **Internal ALB 로 넘김**. WEB 은 WAS 의 IP 를 모르고 Internal ALB **이름만** 안다 — WAS 를 교체·증설해도 WEB 은 무변경.
# 1. 딱 필요한 다섯 가지 — 한 표
<table header-row="true" fit-page-width="true">
	<tr>
		<td>#</td>
		<td>항목</td>
		<td>무슨 일이 일어나나</td>
		<td>우리 값 (실측)</td>
	</tr>
	<tr>
		<td>①</td>
		<td>두 역할 — 직접 서빙 vs 프록시</td>
		<td>경로로 갈린다. 파일이 있는 경로는 Apache 가 직접, `/petclinic/` 이하는 리버스 프록시</td>
		<td>`/` 200(index.html 8,133B) · `/health.html` 200 `ok` · `/petclinic/vets` 200(Tomcat) · `/nope` 404(Apache)</td>
	</tr>
	<tr>
		<td>②</td>
		<td>`ProxyPreserveHost On`</td>
		<td>프록시할 때 원래 `Host`(petclinic.mission-critical.site)를 그대로 넘김. 기본값은 오리진 주소(Internal ALB 이름)로 바꿈</td>
		<td>WAS 로그·Tomcat 이 만드는 리다이렉트가 바깥 주소 — 실측 `/petclinic/` 302 `location: https://petclinic.mission-critical.site/`</td>
	</tr>
	<tr>
		<td>③</td>
		<td>Rewrite 규칙 3쌍</td>
		<td>`/petclinic/`→`/` 302(히어로 한 번만) · `/petclinic`→`/petclinic/` 301(슬래시) · 각각 **`X-Forwarded-Proto =https` 조건 + 평문 폴백**</td>
		<td>`/petclinic` → 301 `https://…/petclinic/` · `/petclinic/` → 302 `https://…/` — Location 이 전부 https</td>
	</tr>
	<tr>
		<td>④</td>
		<td>`ProxyPass` · `!` 제외 · `Alias` · `ProxyPassReverse`</td>
		<td>전달할 것 / 전달에서 뺄 것 / 디스크 경로 매핑 / 응답 Location 되돌리기. **제외가 전달보다 위**</td>
		<td>`ProxyPass /petclinic/ http://internal-…:8080/petclinic/` · 제외 3줄(health · static · images) · `Alias /images/ /var/www/html/static/images/`</td>
	</tr>
	<tr>
		<td>⑤</td>
		<td>로그 · 모듈</td>
		<td>헬스체크를 로그에서 빼는 `SetEnvIf nolog` + `CustomLog env=!nolog`. 프록시는 mod_proxy_http(HTTP) — mod_jk(AJP) 가 아님</td>
		<td>**오늘 발견: 제외가 안 됨**(기본 CustomLog 중복 · 5단계) · `server: Apache/2.4.68 (Amazon Linux)`</td>
	</tr>
</table>
# 2. 자세히 — 항목마다 "무슨 일 · 우리 값 · 없으면 · 눈으로 확인"
## 2-1. ① 두 역할 — 실제 파일 그대로
**무슨 일이 일어나나**
1. web.sh 가 부팅 때 `dnf install httpd git amazon-cloudwatch-agent` → 저장소(test 브랜치)에서 `src/main/webapp/index.html` 과 `resources/` · `images/` 를 `/var/www/html/` · `/var/www/html/static/` 로 복사 → `sed` 로 index.html 의 자산 경로를 `/static/resources/…` 로, 앱 링크를 `/petclinic/…` 로 바꿈 → `petclinic.conf` 생성 → `echo ok › health.html` → `apachectl configtest && systemctl enable --now httpd`.
2. 요청이 오면 Apache 는 **conf.d 의 지시문을 위에서부터** 본다. `ProxyPass … !` 에 걸리면 프록시 안 함 → 파일 서빙(DocumentRoot `/var/www/html`). `ProxyPass /petclinic/` 에 걸리면 Internal ALB 로.
3. 실제 파일 (web.sh 가 만드는 그대로 · 값은 mc-deploy):

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

4. 지금은 CloudFront 가 `/static/*` · `/images/*` · `/maintenance.html` 을 **S3 로 먼저** 보내므로 Apache 의 정적 서빙은 **폴백**(CloudFront 없이 붙거나 S3 장애 때). `/petclinic/resources/*` 는 오리진 그룹(ALB → 실패 시 S3)이라 Apache 를 거쳐 Tomcat 이 준다.

**우리 값 — 경로별 담당 (실측)**
<table header-row="true" fit-page-width="true">
	<tr>
		<td>경로</td>
		<td>CloudFront 가 보내는 곳</td>
		<td>Apache 가 하는 일</td>
		<td>실측 코드 · server</td>
	</tr>
	<tr>
		<td>`/`</td>
		<td>ALB</td>
		<td>직접 — `/var/www/html/index.html`</td>
		<td>200 · Apache · 8,133B</td>
	</tr>
	<tr>
		<td>`/health.html`</td>
		<td>ALB (헬스체크는 노드 직접)</td>
		<td>직접 — `ok`</td>
		<td>200 · Apache · 3B</td>
	</tr>
	<tr>
		<td>`/static/resources/css/petclinic.css`</td>
		<td>**S3** `mc-static` (`/static/*` 동작)</td>
		<td>(폴백) 직접 — `/var/www/html/static/resources/…`</td>
		<td>200 · AmazonS3</td>
	</tr>
	<tr>
		<td>`/images/hero/hero.mp4`</td>
		<td>**S3** (`/images/*` → origin_path `/static`)</td>
		<td>(폴백) Alias → `/var/www/html/static/images/hero/hero.mp4`</td>
		<td>200 · AmazonS3</td>
	</tr>
	<tr>
		<td>`/petclinic/vets`</td>
		<td>ALB</td>
		<td>프록시 → Internal ALB → Tomcat</td>
		<td>200 · Apache(헤더) · WAS 로그에 `HEAD /petclinic/vets`</td>
	</tr>
	<tr>
		<td>`/petclinic/resources/css/petclinic.css`</td>
		<td>ALB (오리진 그룹 · 실패 시 S3)</td>
		<td>프록시 → Tomcat 이 정적 자원 서빙</td>
		<td>200 · Apache · WAS 로그에 있음</td>
	</tr>
	<tr>
		<td>`/nope`</td>
		<td>ALB</td>
		<td>직접 — 파일 없음</td>
		<td>404 · Apache</td>
	</tr>
	<tr>
		<td>`/maintenance.html`</td>
		<td>**S3** `mc-maintenance`</td>
		<td>(Apache 에 안 옴)</td>
		<td>200 · AmazonS3</td>
	</tr>
</table>
**없으면 · 오해**
- index.html 이 없는 브랜치(main)면 web.sh 가 `/` → `/petclinic/` 302 폴백 규칙을 대신 넣는다(ROOT_RULE 분기). 즉 랜딩은 **브랜치 의존**.
- "정적 파일은 S3 가 주니 Apache 의 static 은 필요 없다" — CloudFront 없이 붙는 경우(내부 테스트)와 S3 장애 폴백 때 쓰인다. 두 벌이 같은 브랜치에서 나오므로 불일치는 없다.
- `/petclinic/resources/*` 를 S3 로 안 보내는 이유: JSP 가 만드는 상대 경로라 앱 버전과 묶여 있어 Tomcat 이 주는 게 안전(오리진 그룹은 장애 폴백만).

**눈으로 확인**

```bash
# 1) 경로별 코드와 담당 — CloudFront 경유 (Apache 인지 S3 인지 server 헤더로)
for p in / /health.html /static/resources/css/petclinic.css /images/hero/hero.mp4 /petclinic/vets /petclinic/resources/css/petclinic.css /nope /maintenance.html; do printf "%-45s " "$p"; curl -sI "https://petclinic.mission-critical.site$p" | grep -iE "^HTTP|^server" | tr -d '\r' | tr '\n' ' '; echo; done
# 2) Apache 가 실제로 받은 것 — CloudWatch Logs (S3 로 간 경로는 여기 없다)
aws logs tail /petclinic/web/access --since 5m --profile mc-deploy --region ap-northeast-2 --format short | grep -v health.html | awk '{print $7, $8, $10}' | sort | uniq -c
# 3) 프록시로 Tomcat 까지 간 것 — WAS 로그
aws logs tail /petclinic/was/access --since 5m --profile mc-deploy --region ap-northeast-2 --format short | grep -v '"GET /petclinic/ ' | awk '{print $7, $8, $10}' | sort | uniq -c
# 4) 파일이 만들어지는 과정 — web.sh 원문 (복사 · sed · conf)
sed -n '10,60p' infra/terraform-kdt5/modules/base/user_data/web.sh
```

기대: 1) `/ 200 Apache` · `/health.html 200 Apache` · `/static/… 200 AmazonS3` · `/images/… 200 AmazonS3` · `/petclinic/vets 200 Apache` · `/petclinic/resources/… 200 Apache` · `/nope 404 Apache` · `/maintenance.html 200 AmazonS3` 2) `GET / 200` · `HEAD /petclinic/vets 200` · `HEAD /nope 404` … (static · maintenance 없음) 3) `HEAD /petclinic/vets 200` · `HEAD /petclinic/resources/css/petclinic.css 200` 4) 위 파일 내용
## 2-2. ② ProxyPreserveHost — Host 를 바꾸지 마라
**무슨 일이 일어나나**
1. mod_proxy 의 기본 동작: 뒤로 넘길 때 `Host` 헤더를 **ProxyPass 의 목적지 이름**으로 바꾼다 → Tomcat 은 `Host: internal-mc-alb-internal-692352220.ap-northeast-2.elb.amazonaws.com:8080` 을 본다.
2. Tomcat(Spring)은 절대 URL 이 필요할 때 — 폼 제출 후 `redirect:` · `‹c:url›` · 에러 페이지 링크 — **Host 헤더로 자기 주소를 만든다**. 기본대로 두면 `http://internal-…:8080/petclinic/owners/1` 같은 **내부 이름**이 브라우저로 나간다 → 사용자는 못 연다(사설망 · 내부 DNS).
3. `ProxyPreserveHost On` 이면 원래 Host(`petclinic.mission-critical.site`)를 그대로 넘긴다. Internal ALB 는 Host 를 안 건드리므로 Tomcat 까지 도달(1단계 ①).
4. 그래도 스킴(http/https)은 별개 문제 — Tomcat 은 평문 8080 으로 받으니 `http://petclinic.…` 를 만들 수 있다. 그건 `X-Forwarded-Proto` 를 Tomcat 이 보게 하거나(RemoteIpValve), Apache 의 `ProxyPassReverse`(④)로 되돌리거나, CloudFront 의 http→https 로 한 번 더 튕긴다.

**우리 값**
<table header-row="true" fit-page-width="true">
	<tr>
		<td>항목</td>
		<td>값</td>
	</tr>
	<tr>
		<td>지시문</td>
		<td>`ProxyPreserveHost On` (petclinic.conf 첫 줄)</td>
	</tr>
	<tr>
		<td>Tomcat 이 보는 Host</td>
		<td>`petclinic.mission-critical.site` (ALB → Apache → Internal ALB 전 구간 유지)</td>
	</tr>
	<tr>
		<td>증거</td>
		<td>Tomcat 이 만든 리다이렉트가 바깥 주소로 온다 — 예: 폼 제출 후 `/petclinic/owners/｛id｝`(상대) · 실측 `/petclinic/` 302 도 `https://petclinic.mission-critical.site/`</td>
	</tr>
	<tr>
		<td>기본값이었다면</td>
		<td>`Host: internal-mc-alb-internal-692352220.ap-northeast-2.elb.amazonaws.com:8080`</td>
	</tr>
</table>
**없으면 · 오해**
- Off 면: 폼 제출(새 주인 등록) 뒤 302 의 Location 이 내부 이름 → 브라우저 `ERR_NAME_NOT_RESOLVED`. 9/16 구축 초기에 흔한 증상.
- "ProxyPassReverse 가 있으니 Off 여도 된다" — ProxyPassReverse 는 `Location` **헤더만** 고친다. HTML 안의 절대 링크 · 쿠키 도메인은 못 고친다. On 이 근본.
- Internal ALB 에 호스트 기반 규칙을 쓰려면 Host 가 진짜 값이어야 한다 — On 이 전제.

**눈으로 확인**

```bash
# 1) 지시문 존재 — web.sh 원문
grep -n "ProxyPreserveHost" infra/terraform-kdt5/modules/base/user_data/web.sh
# 2) Tomcat 이 바깥 주소로 리다이렉트를 만드는지 — 앱의 폼 흐름 (owners/new 를 GET → 200, 폼 action 이 상대 경로인지)
curl -s https://petclinic.mission-critical.site/petclinic/owners/new | grep -oE 'action="[^"]*"' | head -2
# 3) 서버 안에서 직접 비교 (Bastion 허용 후): Host 를 바꿔 보내도 Tomcat 응답의 링크가 요청 Host 를 따른다
#   ssh … ec2-user@10.0.10.189 'curl -si -H "Host: petclinic.mission-critical.site" http://localhost/petclinic/ | grep -iE "^HTTP|^Location"'
```

기대: 1) `ProxyPreserveHost On` 2) `action="/petclinic/owners/new"` 류 상대 경로(내부 이름 없음) 3) `302 Location: https://petclinic.mission-critical.site/`(XFP 없이는 `/`)
## 2-3. ③ Rewrite 규칙 3쌍 — 조건이 있는 이유
**무슨 일이 일어나나**
1. `RewriteEngine On` 으로 mod_rewrite 를 켜고, **조건(RewriteCond) + 규칙(RewriteRule)** 을 쌍으로 쓴다. 조건은 바로 아래 규칙 하나에만 붙는다. `[R=302,L]` = 302 리다이렉트로 응답하고(L) 더 안 본다.
2. **쌍 1 — 앱 홈은 랜딩으로**: `^/petclinic/$` → `/` 302. WAS 의 welcome.jsp 도 히어로 화면이라 두 번 보이는 걸 막는다. 앱 내부 링크(`/petclinic/vets`)와 헬스체크(Internal ALB → Tomcat 직접)는 영향 없음.
3. **쌍 2 — 슬래시 보정**: `^/petclinic$` → `/petclinic/` 301. Tomcat 컨텍스트 경로 규칙상 슬래시 없는 요청은 Tomcat 이 스스로 301 을 만드는데, 그 Location 이 내부 스킴/이름이 될 수 있어 Apache 가 **먼저** 처리한다.
4. **각 쌍이 2줄인 이유**: 첫 줄은 `RewriteCond %｛HTTP:X-Forwarded-Proto｝ =https` 조건 + `https://%｛HTTP_HOST｝/…` 절대 주소, 둘째 줄은 조건 없는 **폴백**(상대 주소 `/`). ALB 를 거친 요청은 XFP 가 https 라 첫 줄이 잡고, 서버 안에서 `curl localhost` 처럼 평문 직접이면 둘째 줄이 잡는다. 첫 줄이 없으면 Apache 는 `Location: http://…` 를 만들어 **루프**(1단계 ⑤).
5. 규칙은 `L` 이라 첫 매치에서 끝난다 → 조건 있는 줄이 **위**에 있어야 한다(순서 중요).

**우리 값 (실측)**
<table header-row="true" fit-page-width="true">
	<tr>
		<td>요청 (CloudFront 경유)</td>
		<td>응답</td>
		<td>Location</td>
		<td>잡은 줄</td>
	</tr>
	<tr>
		<td>`/petclinic/`</td>
		<td>302</td>
		<td>`https://petclinic.mission-critical.site/`</td>
		<td>쌍 1 첫 줄(XFP=https)</td>
	</tr>
	<tr>
		<td>`/petclinic`</td>
		<td>301</td>
		<td>`https://petclinic.mission-critical.site/petclinic/`</td>
		<td>쌍 2 첫 줄(XFP=https)</td>
	</tr>
	<tr>
		<td>(서버 안 평문) `/petclinic/`</td>
		<td>302</td>
		<td>`/`</td>
		<td>쌍 1 둘째 줄(폴백)</td>
	</tr>
	<tr>
		<td>`/petclinic/vets`</td>
		<td>200</td>
		<td>—</td>
		<td>어느 규칙도 안 맞음 → ProxyPass</td>
	</tr>
</table>
**없으면 · 오해**
- 조건 줄을 지우면: `Location: http://…/` → CloudFront 301 → 다시 Apache → … "리디렉션이 너무 많습니다".
- 폴백 줄을 지우면: 서버 안에서 `curl localhost/petclinic/` 이 302 대신 프록시로 가 welcome.jsp 가 나온다 — 운영엔 영향 없지만 로컬 점검이 헷갈린다.
- `%｛HTTP_HOST｝` 대신 도메인을 하드코딩하면 도메인 변경 때 web.sh 를 고쳐야 한다. Host 를 그대로 쓰는 게 이식성.

**눈으로 확인**

```bash
# 1) 두 리다이렉트의 코드·Location (https 인지)
for p in /petclinic/ /petclinic; do printf "%-12s " $p; curl -sI "https://petclinic.mission-critical.site$p" | grep -iE "^HTTP|^location" | tr -d '\r' | tr '\n' ' '; echo; done
# 2) 규칙 원문 — web.sh 의 ROOT_RULE 분기 + 슬래시 규칙
grep -nE "RewriteCond|RewriteRule|ROOT_RULE=" infra/terraform-kdt5/modules/base/user_data/web.sh
# 3) 리다이렉트도 Apache 로그에 남는다 (302 · 301)
aws logs tail /petclinic/web/access --since 5m --profile mc-deploy --region ap-northeast-2 --format short | grep -E '"(GET|HEAD) /petclinic/? HTTP' | tail -2
```

기대: 1) `/petclinic/ 302 location: https://…/` · `/petclinic 301 location: https://…/petclinic/` 2) 조건 줄 3개(`X-Forwarded-Proto`)와 폴백 줄 3) `"HEAD /petclinic/ HTTP/1.1" 302` · `"HEAD /petclinic HTTP/1.1" 301`
## 2-4. ④ ProxyPass · `!` 제외 · Alias · ProxyPassReverse — 순서가 규칙
**무슨 일이 일어나나**
1. `ProxyPass /petclinic/ http://internal-…:8080/petclinic/` — `/petclinic/` 로 시작하는 요청을 그 주소로 **새 HTTP 연결**을 열어 전달(mod_proxy_http). 응답을 받아 그대로 돌려준다. 이름은 부팅 때 DNS 로 풀린다(Internal ALB 노드 IP 2개 · 라운드 로빈).
2. `ProxyPass /health.html !` — `!` 는 **"이 경로는 프록시하지 마라"**. mod_proxy 는 **위에서부터 첫 매치**를 쓰므로 제외 줄이 전달 줄보다 **위**에 있어야 한다. `/static/` · `/images/` 도 같은 방식으로 제외 → 파일 서빙.
3. `Alias /images/ /var/www/html/static/images/` — URL `/images/…` 를 디스크 `/var/www/html/static/images/…` 로. WAS 의 welcome.jsp 가 옛 경로 `/images/hero/hero.mp4` 를 쓰기 때문(9/16 실제로 hero.mp4 404 를 겪고 추가).
4. `ProxyPassReverse …` — 뒤(Tomcat)가 준 응답의 `Location` · `Content-Location` · `URI` 헤더 값이 내부 주소(`http://internal-…:8080/petclinic/…`)면 바깥 주소(`/petclinic/…`)로 **되돌려 쓴다**. ProxyPreserveHost 와 짝.
5. 프록시 연결도 keep-alive 로 재사용된다(mod_proxy_http 기본). Internal ALB 유휴 60s 와의 관계는 7단계.

**우리 값**
<table header-row="true" fit-page-width="true">
	<tr>
		<td>줄</td>
		<td>뜻</td>
		<td>없으면</td>
	</tr>
	<tr>
		<td>`ProxyPass /health.html !`</td>
		<td>헬스체크는 Apache 가 직접(5단계 '얕게')</td>
		<td>헬스체크가 WAS 까지 감 → WAS 장애 = WEB unhealthy</td>
	</tr>
	<tr>
		<td>`ProxyPass /static/ !` · `/images/ !`</td>
		<td>정적 자산 제외 → 파일</td>
		<td>정적 요청이 WAS 로 가서 404</td>
	</tr>
	<tr>
		<td>`Alias /images/ /var/www/html/static/images/`</td>
		<td>옛 경로를 새 디렉터리로</td>
		<td>hero.mp4 404 (9/16 실제)</td>
	</tr>
	<tr>
		<td>`ProxyPass /petclinic/ http://internal-mc-alb-internal-692352220.ap-northeast-2.elb.amazonaws.com:8080/petclinic/`</td>
		<td>핵심 — 앱을 Internal ALB 로</td>
		<td>앱 없음(전부 404)</td>
	</tr>
	<tr>
		<td>`ProxyPassReverse …`(같은 주소)</td>
		<td>응답 Location 의 내부 주소를 바깥 주소로</td>
		<td>Tomcat 리다이렉트에 내부 주소 노출(ProxyPreserveHost 가 대부분 막지만 이중 안전)</td>
	</tr>
	<tr>
		<td>순서</td>
		<td>제외 3줄 → Alias → 전달 → Reverse</td>
		<td>제외가 전달 아래면 `/static/` 은 `/petclinic/` 과 안 겹쳐 사실 동작은 같지만, 겹치는 제외(예: `/petclinic/static/ !`)는 반드시 위</td>
	</tr>
</table>
**없으면 · 오해**
- "ProxyPass 는 파일이 없을 때만 프록시한다" — 아니다. 경로가 맞으면 무조건 프록시. 그래서 `!` 로 명시적으로 빼야 한다.
- `ProxyPass` 목적지 끝의 `/` 와 경로 끝의 `/` 를 맞춰야 한다(`/petclinic/` ↔ `…/petclinic/`). 하나만 빼면 `/petclinicvets` 처럼 붙는다.
- mod_proxy_http 가 Internal ALB **이름**을 부팅 때 한 번 풀고 캐시하는 문제(IP 변경 시 stale)가 옛 Apache 에 있었다 — 2.4 는 `ProxyPass` 에 `disablereuse` 없이도 DNS TTL 을 따르진 않지만, ALB 노드 IP 는 거의 안 바뀌고 바뀌어도 새 연결 때 다시 푼다. 문제가 되면 `httpd` 재시작.

**눈으로 확인**

```bash
# 1) 제외 → 전달 순서와 목적지 — web.sh 원문
grep -nE "ProxyPass|Alias" infra/terraform-kdt5/modules/base/user_data/web.sh
# 2) 목적지 이름이 실제 Internal ALB 이고, 이름 → 노드 IP 2개(WAS 서브넷)
aws elbv2 describe-load-balancers --names mc-alb-internal --profile mc-deploy --region ap-northeast-2 --query 'LoadBalancers[0].DNSName' --output text
aws ec2 describe-network-interfaces --profile mc-deploy --region ap-northeast-2 --filters "Name=description,Values=ELB app/mc-alb-internal/*" --query 'NetworkInterfaces[].[AvailabilityZone,PrivateIpAddress,SubnetId]' --output table
# 3) 프록시된 요청이 Internal ALB 노드 IP 로 Tomcat 에 닿는다 — WAS 로그 첫 필드
aws logs tail /petclinic/was/access --since 5m --profile mc-deploy --region ap-northeast-2 --format short | grep -v '"GET /petclinic/ ' | awk '{print $2}' | sort | uniq -c
# 4) 제외가 동작한다 — /health.html 은 WAS 로그에 없어야
aws logs tail /petclinic/was/access --since 1h --profile mc-deploy --region ap-northeast-2 --format short | grep -c health.html
```

기대: 1) `!` 3줄이 `ProxyPass /petclinic/` 위 2) `internal-mc-alb-internal-692352220.ap-northeast-2.elb.amazonaws.com` · 2a `10.0.20.x` · 2c `10.0.21.x` 3) `10.0.20.193` · `10.0.21.43` 4) `0`
## 2-5. ⑤ 로그와 모듈 — 의도와 실측이 다른 곳
**무슨 일이 일어나나**
1. **의도**: `SetEnvIf Request_URI "^/health.html$" nolog` 로 헬스체크 요청에 환경 변수 `nolog` 를 붙이고, `CustomLog /var/log/httpd/access_log combined env=!nolog` 로 그 요청은 **안 찍는다**. 10초마다 노드 2개가 찍으면 로그가 헬스체크로 가득 차니까.
2. **실측(9/17)**: `/petclinic/web/access` 에 헬스체크가 1시간 1,442줄 찍히고, 일반 요청은 **같은 줄이 2번**. 원인: AL2023 의 `/etc/httpd/conf/httpd.conf` 에 기본 `CustomLog "logs/access_log" combined` 가 살아 있다 → 같은 파일에 **두 CustomLog** 가 쓴다. 기본 것은 필터가 없어 헬스체크를 찍고, 일반 요청은 둘 다 찍어 중복.
3. **수정안**: web.sh 에서 기본 CustomLog 한 줄을 주석 처리(`sed -i 's∣^⧵s*CustomLog "logs/access_log" combined∣#&∣' /etc/httpd/conf/httpd.conf`) → conf.d 의 필터만 남는다. `user_data` 변경이라 **인스턴스 교체**가 따른다(`-replace` 한 대씩 · README 교훈).
4. **모듈**: 프록시는 `mod_proxy` + `mod_proxy_http`(HTTP 로 전달). 옛 방식 `mod_jk`(AJP 바이너리)는 **ALB 를 중간에 못 둔다**(ALB 는 HTTP 만) → WEB 이 WAS IP 를 직접 알아야 해 교체·증설 때 WEB 설정을 바꿔야 한다. 3-Tier + ALB 면 mod_proxy_http 가 정답. `mod_rewrite` · `mod_alias` · `mod_setenvif` · `mod_log_config` 도 쓰인다(AL2023 기본 로드).
5. 로그 형식은 `combined`(첫 필드 = 연결 상대 IP = ALB 노드). 사용자 IP 는 `X-Forwarded-For` 에 있는데 combined 는 안 찍는다 → 8단계 개선(`%｛X-Forwarded-For｝i`).

**우리 값**
<table header-row="true" fit-page-width="true">
	<tr>
		<td>항목</td>
		<td>값 (실측)</td>
	</tr>
	<tr>
		<td>로그 파일 · 그룹</td>
		<td>`/var/log/httpd/access_log` → CloudWatch `/petclinic/web/access`(30일) · `error_log` → `/petclinic/web/error`</td>
	</tr>
	<tr>
		<td>헬스체크 줄</td>
		<td>1시간 **1,442줄** (`"GET /health.html HTTP/1.1" 200 3 "-" "ELB-HealthChecker/2.0"`) — 의도와 다름</td>
	</tr>
	<tr>
		<td>중복</td>
		<td>일반 요청 같은 줄 ×2 (`GET / … 200 8133` 두 번)</td>
	</tr>
	<tr>
		<td>error_log 최근</td>
		<td>9/16 10:47 `AH00489: Apache/2.4.68 (Amazon Linux) configured -- resuming normal operations`(부팅) 이후 오류 없음</td>
	</tr>
	<tr>
		<td>모듈</td>
		<td>proxy · proxy_http · rewrite · alias · setenvif · log_config · mpm_event (`httpd -M` 은 Bastion 허용 후 확인)</td>
	</tr>
	<tr>
		<td>서버 배너</td>
		<td>`server: Apache/2.4.68 (Amazon Linux)` — 버전 노출(`ServerTokens Prod` 로 줄이는 게 로드맵)</td>
	</tr>
</table>
**없으면 · 오해**
- "로그에 헬스체크가 없으니 필터가 된다" 고 믿고 있었다 — 실측이 다르다. **설정을 넣었다 ≠ 동작한다**. CloudWatch Logs 로 확인하는 습관.
- 헬스체크 줄이 많으면 CloudWatch 수집 비용과 검색 잡음만 늘고, 중복 줄은 요청 수 집계를 2배로 왜곡한다(8단계 지표는 ALB 로그·CloudWatch 지표로 보는 게 정확한 이유).
- mod_jk 가 "더 빠르다" 는 옛 얘기 — keep-alive 를 쓰는 mod_proxy_http 와 차이 미미. 구조(ALB 가능 여부)가 결정 기준.

**눈으로 확인**

```bash
# 1) 의도 — web.sh 의 로그 필터 두 줄
grep -nE "SetEnvIf|CustomLog" infra/terraform-kdt5/modules/base/user_data/web.sh
# 2) 실측 — 헬스체크 줄 수(1h)와 일반 요청 중복
aws logs tail /petclinic/web/access --since 1h --profile mc-deploy --region ap-northeast-2 --format short | grep -c ELB-HealthChecker
aws logs tail /petclinic/web/access --since 1h --profile mc-deploy --region ap-northeast-2 --format short | grep -v ELB-HealthChecker | cut -d' ' -f2- | sort | uniq -c | awk '$1>1' | head -3
# 3) error_log 에 오류가 없는지
aws logs tail /petclinic/web/error --since 24h --profile mc-deploy --region ap-northeast-2 --format short | grep -viE "notice" | tail -3
# 4) 모듈 (Bastion 허용 후): httpd -M 2>/dev/null | grep -E "proxy_http|rewrite|alias|setenvif|mpm"
```

기대: 1) `SetEnvIf Request_URI "^/health.html$" nolog` · `CustomLog … env=!nolog` 2) 약 1,400 · 앞에 `2` 가 붙은 줄들 3) 없음(notice 뿐) 4) `proxy_http_module · rewrite_module · alias_module · setenvif_module · mpm_event_module`
## 2-6. 경로 하나의 여행 — `/petclinic/vets` 가 Apache 를 지나는 순서
<table header-row="true" fit-page-width="true">
	<tr>
		<td>순서</td>
		<td>지시문</td>
		<td>판단</td>
		<td>결과</td>
	</tr>
	<tr>
		<td>1</td>
		<td>(ALB → Apache 80) `GET /petclinic/vets HTTP/1.1` · Host `petclinic.…` · `X-Forwarded-Proto: https`</td>
		<td>—</td>
		<td>Apache 가 받음(연결 상대 `10.0.1.212`)</td>
	</tr>
	<tr>
		<td>2</td>
		<td>③ RewriteRule 쌍 1 `^/petclinic/$`</td>
		<td>`/petclinic/vets` ≠ `/petclinic/` → 불일치</td>
		<td>통과</td>
	</tr>
	<tr>
		<td>3</td>
		<td>③ RewriteRule 쌍 2 `^/petclinic$`</td>
		<td>불일치</td>
		<td>통과</td>
	</tr>
	<tr>
		<td>4</td>
		<td>④ `ProxyPass /health.html !` · `/static/ !` · `/images/ !`</td>
		<td>접두어 불일치</td>
		<td>제외 아님</td>
	</tr>
	<tr>
		<td>5</td>
		<td>④ `ProxyPass /petclinic/ http://internal-…:8080/petclinic/`</td>
		<td>접두어 일치</td>
		<td>② Host 유지한 채 `http://internal-…:8080/petclinic/vets` 로 새 연결(XFF 에 `10.0.1.212` 덧붙임)</td>
	</tr>
	<tr>
		<td>6</td>
		<td>Internal ALB 8080 → mc-tg-was → Tomcat</td>
		<td>기본 작업 forward</td>
		<td>WAS 로그 `10.0.21.43 … "HEAD /petclinic/vets HTTP/1.1" 200`</td>
	</tr>
	<tr>
		<td>7</td>
		<td>④ `ProxyPassReverse`</td>
		<td>응답에 Location 없음</td>
		<td>변경 없음 · 200 본문 그대로</td>
	</tr>
	<tr>
		<td>8</td>
		<td>⑤ `SetEnvIf` / `CustomLog`</td>
		<td>`nolog` 아님</td>
		<td>access_log 기록(현재는 2번) → CloudWatch `/petclinic/web/access`</td>
	</tr>
	<tr>
		<td>9</td>
		<td>응답 → ALB → CloudFront → 브라우저</td>
		<td>—</td>
		<td>`HTTP/2 200` · `server: Apache/2.4.68` · `x-cache: Miss`</td>
	</tr>
</table>
기억할 것 셋: **경로가 역할을 가른다**(파일 vs 프록시 · 제외는 위에) · **Host 는 보존, 스킴은 헤더로**(ProxyPreserveHost + XFP 조건) · **설정을 넣었다 ≠ 동작한다**(로그 필터 실측).
# 3. 용어 — 이 단계에서만 쓰는 것
<table header-row="true" fit-page-width="true">
	<tr>
		<td>용어</td>
		<td>한 줄</td>
		<td>비유</td>
	</tr>
	<tr>
		<td>리버스 프록시</td>
		<td>클라이언트 대신 뒤 서버에 요청하고 답을 돌려주는 앞단 서버</td>
		<td>접수 창구가 진료실에 대신 물어봄</td>
	</tr>
	<tr>
		<td>DocumentRoot</td>
		<td>파일 서빙의 기준 디렉터리 `/var/www/html`</td>
		<td>서류함</td>
	</tr>
	<tr>
		<td>ProxyPass · `!`</td>
		<td>경로 접두어를 뒤 서버 주소로 전달 · `!` 는 전달 제외</td>
		<td>"이 창구 업무는 2층으로" · "이건 여기서 처리"</td>
	</tr>
	<tr>
		<td>ProxyPassReverse</td>
		<td>뒤 서버 응답의 Location 헤더 안 내부 주소를 바깥 주소로</td>
		<td>안내문의 내부 전화번호를 대표번호로 고쳐 씀</td>
	</tr>
	<tr>
		<td>ProxyPreserveHost</td>
		<td>전달할 때 원래 Host 유지</td>
		<td>봉투의 수신인을 그대로</td>
	</tr>
	<tr>
		<td>Alias</td>
		<td>URL 경로 → 디스크 경로 매핑</td>
		<td>옛 방 번호를 새 방으로 안내</td>
	</tr>
	<tr>
		<td>RewriteCond · RewriteRule · [R,L]</td>
		<td>조건 + 규칙 · R=리다이렉트 코드 · L=여기서 끝</td>
		<td>"○○이면 저리로 가세요(끝)"</td>
	</tr>
	<tr>
		<td>SetEnvIf · env=</td>
		<td>요청 특성으로 변수를 붙이고, 로그에 조건으로 씀</td>
		<td>서류에 스티커 붙이고 스티커 없는 것만 기록</td>
	</tr>
	<tr>
		<td>mod_proxy_http vs mod_jk</td>
		<td>HTTP 로 전달(ALB 가능) vs AJP 로 전달(ALB 불가)</td>
		<td>표준 우편 vs 사내 전용 배송</td>
	</tr>
</table>
# 4. 왜 이렇게 만들었나 (멘토가 물을 만한 것)
- **왜 WEB 계층을 따로 두나(ALB→Tomcat 직결도 되는데)?** 정적 서빙·리다이렉트·헬스체크 분리·점검 안내를 WAS 없이 처리하고, WAS 를 사설 깊숙이 둔다. 계층별 독립 확장.
- **왜 mod_jk 가 아니라 mod_proxy_http?** 중간에 Internal ALB 를 두려면 HTTP 여야 한다. WAS 교체·증설 때 WEB 무변경.
- **왜 Apache 가 리다이렉트를 만드나(Tomcat 이 아니라)?** Apache 가 XFP 를 보고 https 절대 주소를 만들 수 있고, Tomcat 이 내부 이름으로 만드는 위험을 앞에서 차단.
- **왜 정적 자산을 Apache 에도 두나(S3 가 있는데)?** 폴백 + CloudFront 없이 붙는 테스트 경로. 같은 브랜치에서 나와 불일치 없음.
- **헬스체크 로그 필터가 왜 안 되나?** httpd.conf 기본 CustomLog 와 중복. 한 줄 수정(sed) + 인스턴스 교체로 해결 — 발견 9/17.
# 5. 다음 단계(7. 분산·타임아웃) 진입 기준
<details>
<summary>Q1. `ProxyPreserveHost On` 을 끄면 사용자가 어떤 증상을 보나?</summary>
	Tomcat 이 만드는 리다이렉트(폼 제출 후)가 `http://internal-mc-alb-internal-…:8080/…` 로 와서 브라우저가 열지 못한다(내부 이름 · 사설망). ProxyPassReverse 는 Location 만 고치므로 HTML 안 링크는 못 막는다.
</details>
<details>
<summary>Q2. RewriteRule 앞의 RewriteCond(X-Forwarded-Proto) 를 지우면?</summary>
	Apache 는 평문으로 받으니 `Location: http://…/` 를 준다 → CloudFront 가 http→https 301 → 다시 Apache → 무한 루프.
</details>
<details>
<summary>Q3. `ProxyPass /health.html !` 을 `ProxyPass /petclinic/` 아래로 옮기면?</summary>
	`/health.html` 은 `/petclinic/` 과 안 겹쳐 동작은 같다. 하지만 겹칠 수 있는 제외(`/petclinic/static/ !` 같은)는 반드시 위 — mod_proxy 는 첫 매치. 습관적으로 제외를 먼저 둔다.
</details>
<details>
<summary>Q4. 로그에 헬스체크가 찍히고 일반 요청이 두 번 찍힌다. 원인과 수정은?</summary>
	httpd.conf 의 기본 `CustomLog "logs/access_log" combined` 와 conf.d 의 `CustomLog … env=!nolog` 가 같은 파일에 쓴다. 기본 줄을 주석 처리(web.sh 에 sed 한 줄) 후 인스턴스 교체.
</details>
# 6. 읽을 자료
- Apache 문서 — *mod_proxy* (`ProxyPass` · `ProxyPassReverse` · `ProxyPreserveHost` · `!` 제외 · 순서)
- Apache 문서 — *mod_rewrite* (`RewriteCond %｛HTTP:…｝` · 플래그 `R` `L`) · *mod_log_config* (`env=`)
- 저장소 `infra/terraform-kdt5/modules/base/user_data/web.sh` (이 파일을 만드는 스크립트 · 콘솔 가이드 ⑤ 5-2)
<callout icon="🗺️" color="gray_bg">
	**로드맵 위치**: 0 VPC 입구 → 1 HTTP 기초 → 2 TLS 종료 지점 → 3 ALB 해부 → 4 오리진 보호(헤더) → 5 헬스체크 → **6 Apache 프록시(이 페이지)** → 7 분산·타임아웃 → 8 WEB 관측 → 9 장애 모드 → 10 ASG·AMI.
</callout>
