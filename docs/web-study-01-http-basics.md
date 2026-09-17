> **이 단계의 목표**: HTTP 전체가 아니라 "CloudFront 를 떠나 Apache 에 닿기까지" 구간에서 **실제로 쓰이는 다섯 가지**만 손에 익힌다. 하루 분량. 뒤의 2~9단계(TLS · ALB 규칙 · 헤더 검증 · 헬스체크 · Apache 프록시 · 타임아웃 · 로그 · 장애)가 전부 여기에 기댄다. 아래 값은 전부 2026-09-17 우리 사이트에서 실측한 것.
# 0. 그림 한 장

```text
브라우저 ──GET / HTTP/2 · Host: petclinic.mission-critical.site──▶ CloudFront ──GET / HTTP/1.1 · Host 그대로 · +X-Origin-Verify──▶ ALB ──HTTP/1.1 평문 · +X-Forwarded-For/Proto/Port──▶ Apache
   ◀── HTTP/2 200 · server: Apache · via: …cloudfront.net · x-cache: Miss ──────────────────────────────────────────────────────────────── 200 ◀──
   ① 요청줄+Host          ② 상태 코드           ③ X-Forwarded-*            ④ keep-alive·유휴           ⑤ 리다이렉트(3xx+Location)
```

핵심 하나: 프록시(CloudFront · ALB)를 지날 때마다 **연결은 새로 만들어지고, 원래 정보는 헤더로만 전달된다**. 그래서 이 구간의 문제는 대부분 "누가 어떤 헤더를 붙였나·안 붙였나" 로 귀결된다.
# 1. 딱 필요한 다섯 가지 — 한 표
| # | 개념 | 한 줄 뜻 | 우리 값 (실측) |
|---|---|---|---|
| ① | 요청줄 + **Host** | `GET / HTTP/2` + `Host: petclinic.mission-critical.site` — "어느 사이트의 어느 경로". Host 는 세 번 손을 탐(AllViewer · ALB 유지 · ProxyPreserveHost) | 브라우저→CloudFront 는 HTTP/2, CloudFront→ALB→Apache 는 **HTTP/1.1**(ALB·Apache 로그에 `HTTP/1.1`) |
| ② | 상태 코드 **200 · 301 · 302 · 403 · 404 · 502 · 503 · 504** | 서버가 결과를 세 자리 숫자로 말함. 4xx 는 "네 잘못", 5xx 는 "내(서버 쪽) 잘못" | `/` 200 · `/petclinic` 301 · `/petclinic/` 302 · `/nope` 404 · `http://` 301(CloudFront) · 403 = ALB 기본 작업 · 5xx 지난 24h **0건** |
| ③ | **X-Forwarded-For · X-Forwarded-Proto** | 프록시가 "원래 클라이언트 IP" 와 "원래 https 였나" 를 뒤로 전달하는 헤더 | Apache 로그 첫 IP = ALB 노드 `10.0.0.212`/`10.0.1.212`(사용자 IP 아님) · `X-Forwarded-Proto: https` 를 RewriteCond 가 봄 |
| ④ | **keep-alive · 유휴 타임아웃** | 한 TCP 연결을 여러 요청에 재사용, 놀면 끊음. 구간마다 값이 따로 | CloudFront→ALB keep-alive 5s · ALB 유휴 **60s** · Apache 기본 5s(서버 미확인) |
| ⑤ | **리다이렉트가 도는 원리** | 3xx + `Location` 헤더 → **브라우저가** 그 주소로 다시 요청. 서버는 주소만 알려 줌 | `/petclinic/` → `302 location: https://petclinic.mission-critical.site/` (https 인 게 ③의 증거) |
# 2. 자세히 — 항목마다 "무슨 일 · 우리 값 · 없으면 · 눈으로 확인"
## 2-1. ① 요청줄과 Host — "어느 사이트의 어느 경로"
**무슨 일이 일어나나**
1. 브라우저가 보내는 첫 줄은 **메서드 · 경로 · 버전**, 그다음 줄들이 헤더. 같은 IP 에 사이트가 여럿 있을 수 있어서(CloudFront 엣지 하나가 수천 배포를 받음) "어느 사이트냐" 는 **Host 헤더**로만 구분한다. HTTP/2 에선 `:authority` 라는 이름이지만 뜻은 같다.
2. CloudFront 는 Host 로 **우리 배포**(`d2p7som2iuyba.cloudfront.net` 의 대체 도메인 `petclinic.mission-critical.site`)를 고르고, 경로로 **동작(behavior)** 을 고른다 — `/static/*` 는 S3, `/maintenance.html` 은 S3, 나머지 `*` 는 ALB.
3. CloudFront → ALB 로 갈 때 오리진 요청 정책이 **AllViewer** 라서 뷰어의 Host 가 **그대로** 간다. ALB 는 이 Host 로 인증서(SNI)를 고르고(2단계), Host 를 바꾸지 않는다.
4. ALB → Apache 도 Host 그대로. Apache 는 `/petclinic/*` 를 Internal ALB 로 넘길 때 `ProxyPreserveHost On` 이라 Tomcat 까지 원래 Host 가 간다(6단계) — Tomcat 이 만드는 리다이렉트·절대 링크가 바깥 주소가 되는 이유.
5. 버전은 구간마다 다르다: 브라우저↔CloudFront **HTTP/2**(또는 3), CloudFront→ALB·ALB→Apache·Apache→Tomcat 은 전부 **HTTP/1.1**. 오리진 쪽은 항상 1.1 이라 서버 쪽 로그엔 `HTTP/1.1` 만 찍힌다.

**우리 값**
| 구간 | 요청줄 (실측) | Host |
|---|---|---|
| 브라우저 → CloudFront | `GET / HTTP/2` | `petclinic.mission-critical.site` (Route 53 alias → CloudFront) |
| CloudFront → ALB | `GET https://petclinic.mission-critical.site:443/ HTTP/1.1` (ALB 로그 표기) | 그대로 — 오리진 요청 정책 AllViewer(`216adef6-…`) |
| ALB → Apache | `GET / HTTP/1.1` (Apache access_log) | 그대로 |
| Apache → Internal ALB → Tomcat | `HEAD /petclinic/vets HTTP/1.1` (WAS access log) | 그대로 — `ProxyPreserveHost On` |
**없으면 · 오해**
- AllViewer 대신 Host 를 안 넘기면: CloudFront 가 오리진 도메인(ALB DNS 이름)을 Host 로 보내고, ALB 인증서 이름(`petclinic.…`)과 안 맞아 CloudFront 가 **502** 를 낸다.
- `ProxyPreserveHost` 가 없으면: Tomcat 은 Host 를 `internal-mc-alb-internal-…:8080` 으로 보고, 폼 제출 뒤 리다이렉트가 그 내부 주소로 나가 브라우저가 못 연다.
- "HTTP/2 로 켰는데 왜 서버 로그는 1.1?" — 오리진 쪽은 원래 1.1. ALB 의 `routing.http2.enabled` 는 뷰어(CloudFront) 쪽 얘기이고 CloudFront 는 오리진에 1.1 로만 말한다.

**눈으로 확인**

```bash
# 1) 요청줄 · Host · 버전 — 브라우저 쪽은 HTTP/2
curl -sv https://petclinic.mission-critical.site/ -o /dev/null 2>&1 | grep -E "^> (GET|Host)|^< HTTP"
# 2) 서버 쪽은 HTTP/1.1 — Apache access_log (CloudWatch Logs · 서버 접속 불필요)
aws logs tail /mc/web/access --since 1h --profile mc-deploy --region ap-northeast-2 --format short | grep -v health.html | tail -3
# 3) CloudFront 가 Host 를 넘기는 정책 = AllViewer
aws cloudfront get-origin-request-policy --id 216adef6-5c7f-47e4-b989-5492eafa07d3 --profile mc-deploy --query 'OriginRequestPolicy.OriginRequestPolicyConfig.[Name,HeadersConfig.HeaderBehavior]' --output text
```

기대: 1) `› GET / HTTP/2` · `› Host: petclinic.mission-critical.site` · `‹ HTTP/2 200` 2) `10.0.0.212 - - […] "GET / HTTP/1.1" 200 8133` 3) `Managed-AllViewer allViewer`
## 2-2. ② 상태 코드 — 우리 구간에서 실제로 보는 것만
**무슨 일이 일어나나**
1. 응답 첫 줄이 상태 코드. **누가 냈는지**가 코드만큼 중요하다 — 같은 403 이라도 ALB 규칙(도장 없음)과 WAF(차단)와 S3(키 없음)가 다르다. `server` 헤더와 `x-cache` 헤더가 누가 냈는지 알려 준다.
2. 2xx·3xx·4xx 는 대개 **끝 서버(Apache·Tomcat·S3)** 가 낸다. 5xx 중 **502·503·504 는 중간 프록시(ALB·CloudFront)가 뒤를 대신해 사과하는 것** — 502 "뒤가 이상하게 답함/연결 끊김", 503 "보낼 정상 대상이 없음", 504 "제때 안 답함".
3. CloudFront 는 오리진이 **502·503·504** 를 주면 `/maintenance.html` 을 **503** 으로 바꿔 보여 준다(9단계). 403·404·500 은 그대로 사용자에게.
4. 4xx 도 CloudFront 를 지나면 `x-cache: Error from cloudfront` 로 표시된다 — 오류 응답을 캐시 대상으로 다루기 때문. 오류가 아니라 "오류 응답을 전달했다" 는 뜻.

**우리 값 — 오늘 실측**
| 요청 | 코드 | 누가 | 왜 |
|---|---|---|---|
| `https://…/` | **200** | Apache (`server: Apache/2.4.68`) | 랜딩 `index.html` 직접 서빙 · 8,133 바이트 |
| `https://…/petclinic` | **301** | Apache RewriteRule | 슬래시 없는 컨텍스트 → `/petclinic/` (영구) |
| `https://…/petclinic/` | **302** | Apache RewriteRule | 앱 홈은 랜딩으로 (히어로 화면은 한 번만). `location: https://petclinic.mission-critical.site/` |
| `https://…/petclinic/vets` | **200** | Tomcat (Apache 경유 · `server: Apache`) | 앱 페이지. `content-type: text/html;charset=UTF-8`(Tomcat 표기 — 공백 없음) |
| `https://…/nope` | **404** | Apache | 파일 없음 · `x-cache: Error from cloudfront` |
| `http://…/` | **301** | **CloudFront** (`Server: CloudFront`) | 뷰어 정책 redirect-to-https · 오리진엔 안 감 |
| `https://…/static/resources/css/petclinic.css` | **200** | S3 (`server: AmazonS3`) | `/static/*` 동작 → OAC 로 S3 · `cache-control: max-age=86400` |
| (도장 없이 ALB 도달) | **403** | ALB 기본 작업 | 밖에선 SG 가 먼저 막아 재현 불가(0단계) · 로그엔 `matched_rule_priority 0` |
| 502 · 503 · 504 | — | ALB · CloudFront | 지난 24h `HTTPCode_ELB_5XX` · `Target_5XX` **0** (9단계에서 일부러 내 본다) |
**없으면 · 오해**
- "404 가 났으니 서버가 죽었다" — 아니다. 404 는 서버가 **멀쩡히** "그런 경로 없음" 이라 답한 것. 죽었으면 502·503.
- "302 와 301 은 아무거나" — 301 은 브라우저가 **캐시**해서 다음부턴 서버에 묻지도 않고 이동한다. 잠깐 쓰는 리다이렉트를 301 로 두면 되돌리기 어렵다. 우리는 `/petclinic`→`/petclinic/` 만 301.
- `/static/css/petclinic.css` 처럼 S3 에 없는 키를 치면 S3 가 **403**(404 아님)을 준다 — OAC 로 ListBucket 권한이 없어 "없음" 을 숨기기 때문. 정적 자산 경로는 `/static/resources/…`.

**눈으로 확인**

```bash
# 1) 경로별 코드와 낸 주체(server 헤더)를 한 번에
for p in / /petclinic /petclinic/ /petclinic/vets /nope /static/resources/css/petclinic.css /maintenance.html; do printf "%-40s " "$p"; curl -sI "https://petclinic.mission-critical.site$p" | grep -iE "^HTTP|^server|^location" | tr -d '\r' | tr '\n' ' '; echo; done
# 2) http 는 CloudFront 가 301 — 오리진엔 안 감
curl -sI http://petclinic.mission-critical.site/ | grep -iE "^HTTP|^Server|^Location"
# 3) 지난 24시간 5xx (ALB 가 낸 것 · 대상이 낸 것)
for m in HTTPCode_ELB_5XX_Count HTTPCode_Target_5XX_Count; do printf "%s " $m; aws cloudwatch get-metric-statistics --namespace AWS/ApplicationELB --metric-name $m --dimensions Name=LoadBalancer,Value=app/mc-alb-public/0780e6e7d84abe76 --start-time $(date -u -d '-24 hour' +%FT%TZ) --end-time $(date -u +%FT%TZ) --period 86400 --statistics Sum --profile mc-deploy --region ap-northeast-2 --query 'Datapoints[0].Sum' --output text; done
```

기대: 1) `200 Apache` · `301 → /petclinic/` · `302 → https://…/` · `200` · `404` · `200 AmazonS3` · `200 AmazonS3` 2) `301 · Server: CloudFront · Location: https://…` 3) 둘 다 `None`(=0)
## 2-3. ③ X-Forwarded-For · X-Forwarded-Proto — 원래 정보는 헤더로만
**무슨 일이 일어나나**
1. 프록시를 지나면 뒤 서버가 보는 **연결의 상대**는 프록시다. Apache 가 보는 상대 IP 는 ALB 노드의 사설 IP(`10.0.0.212` / `10.0.1.212`), 프로토콜은 **http**(ALB→Apache 는 평문 80). 사용자 IP 와 "원래 https 였다" 는 사실은 사라진다.
2. 그래서 프록시가 **헤더에 적어서** 넘긴다. `X-Forwarded-For`(XFF)는 지나온 클라이언트 IP 를 **쉼표로 이어 붙이는** 목록 — CloudFront 가 뷰어 IP 를 넣고, ALB 가 그 뒤에 CloudFront 의 오리진 쪽 IP 를 덧붙인다(`xff_header_processing.mode = append`). **맨 앞이 사용자**.
3. `X-Forwarded-Proto: https` · `X-Forwarded-Port: 443` 은 ALB 가 리스너 정보로 붙인다. Apache 의 RewriteCond 가 이 값을 보고 리다이렉트 Location 을 https 로 만든다(⑤ · 6단계).
4. Apache 도 `/petclinic/*` 를 프록시할 때 mod_proxy 가 XFF 에 자기 클라이언트(ALB 노드 IP)를 덧붙이고 `X-Forwarded-Host` · `X-Forwarded-Server` 를 추가한다. Internal ALB 가 또 덧붙인다. Tomcat 에 닿을 땐 XFF 가 4개 IP.
5. XFF 는 **믿을 수 있는 구간에서만** 믿는다 — 맨 앞 값은 뷰어가 조작할 수 있다. CloudFront 가 붙이는 값부터가 진짜. WAF rate 제한은 CloudFront 가 본 뷰어 IP 기준이라 안전.

**우리 값**
| 헤더 | 누가 붙이나 | 값 (오늘 내 curl 기준 · 형태) | 어디에 쓰이나 |
|---|---|---|---|
| `X-Forwarded-For` | CloudFront 가 뷰어 IP → ALB 가 CloudFront IP 덧붙임(append) | `221.148.195.245, 15.158.254.101` | 진짜 사용자 IP(맨 앞). Apache `combined` 형식은 **이걸 안 찍는다** → 8단계 개선 |
| `X-Forwarded-Proto` | ALB (뷰어 리스너가 HTTPS 면 `https`) | `https` | `RewriteCond %｛HTTP:X-Forwarded-Proto｝ =https` — Location 을 https 로 |
| `X-Forwarded-Port` | ALB | `443` | 안 씀 |
| `X-Amzn-Trace-Id` | ALB | `Root=1-6aab51f9-…` | ALB 로그 trace_id 와 대조(8단계) |
| Apache 로그의 첫 IP | (헤더 아님) 연결 상대 | `10.0.1.212` · `10.0.0.212` | ALB 노드. WAS 로그의 첫 IP `10.0.21.43` · `10.0.20.193` 은 Internal ALB 노드 |
**없으면 · 오해**
- XFF 를 안 보면: 로그·차단·통계가 전부 "CloudFront IP" 기준이 된다. 특정 사용자를 찾거나 막을 수 없다.
- XFP 를 안 보면: Apache 가 `Location: http://…` 를 만들고 CloudFront 가 http→https 로 다시 보내 **루프**(⑤).
- "XFF 맨 뒤가 사용자" — 반대. 맨 뒤는 **마지막 프록시**, 맨 앞이 사용자(단, 앞은 위조 가능하니 CloudFront 뒤에서만 신뢰).

**눈으로 확인**

```bash
# 1) Apache 로그 첫 IP 가 ALB 노드(10.0.0.212 / 10.0.1.212)인지 — CloudWatch Logs
aws logs tail /mc/web/access --since 1h --profile mc-deploy --region ap-northeast-2 --format short | grep -v health.html | tail -3 | awk '{print $2}'
# 2) WAS 로그 첫 IP 는 Internal ALB 노드(10.0.20.x / 10.0.21.x)
aws logs tail /mc/was/access --since 1h --profile mc-deploy --region ap-northeast-2 --format short | tail -2 | awk '{print $2}'
# 3) ALB 가 XFF 를 '덧붙이기' 모드로 처리하는지
aws elbv2 describe-load-balancer-attributes --load-balancer-arn $(aws elbv2 describe-load-balancers --names mc-alb-public --profile mc-deploy --query 'LoadBalancers[0].LoadBalancerArn' --output text) --profile mc-deploy --query 'Attributes[?Key==`routing.http.xff_header_processing.mode`].Value' --output text
# 4) X-Forwarded-Proto 가 실제로 동작한다는 간접 증거 — Location 이 https
curl -sI https://petclinic.mission-critical.site/petclinic/ | grep -i "^location"
```

기대: 1) `10.0.1.212` `10.0.0.212` … 2) `10.0.21.43` `10.0.20.193` 3) `append` 4) `location: https://petclinic.mission-critical.site/`
## 2-4. ④ keep-alive 와 유휴 타임아웃 — 연결은 구간마다 따로
**무슨 일이 일어나나**
1. HTTP/1.1 은 기본으로 **연결을 재사용**한다(keep-alive). 요청 하나마다 TCP·TLS 를 새로 맺으면 느리니, 한 연결로 여러 요청을 보낸다. HTTP/2 는 한 연결에 여러 요청을 **동시에**(멀티플렉싱).
2. 우리 구간엔 **연결이 세 개**다: 브라우저↔CloudFront(HTTP/2) · CloudFront↔ALB(1.1) · ALB↔Apache(1.1). 각각 "얼마나 놀면 끊을지" 를 **따로** 정한다. 서로 모른다.
3. 위험한 경우: **뒤쪽이 앞쪽보다 먼저 끊으면** 앞쪽이 이미 닫힌 연결에 요청을 써서 실패한다. ALB↔Apache 에서 Apache 가 먼저 끊으면 ALB 가 **502**. AWS 권고: 대상(Apache)의 keep-alive 타임아웃 › ALB 유휴 타임아웃.
4. 유휴(idle) 타임아웃은 "데이터가 안 오가는 시간" 의 상한. 응답 대기 타임아웃(CloudFront 30s)은 "첫 바이트를 기다리는 시간" 의 상한 — 다른 것(7단계).

**우리 값**
| 연결 | 버전 | keep-alive · 유휴 | 출처 |
|---|---|---|---|
| 브라우저 ↔ CloudFront | HTTP/2 (`http2and3`) | CloudFront 관리 | 배포 설정 |
| CloudFront ↔ ALB | HTTP/1.1 | keep-alive **5s** · 응답 대기 30s · 연결 시도 3회/10s | 오리진 `alb-public` (실측) |
| ALB ↔ Apache | HTTP/1.1 | ALB 유휴 **60s** · Apache `KeepAliveTimeout` **5s(httpd 기본값 · web.sh 가 안 바꿈 · 서버 미확인)** | ALB 속성 · web.sh |
**없으면 · 오해**
- Apache 5s ‹ ALB 60s 는 권고와 어긋난다. 실측 5XX 0 이라 지금 문제는 없지만(ALB 가 닫힌 연결을 만나면 재시도), 안전하게는 `KeepAliveTimeout 75`(7단계 개선 항목).
- "keep-alive 를 끄면 안전하다" — 502 는 줄지만 연결을 매번 새로 맺어 지연이 늘고 서버 소켓이 낭비된다. 값을 맞추는 게 정답.
- "브라우저가 닫아도 서버 연결이 닫힌다" — 아니다. 세 연결은 독립. 브라우저가 떠나도 ALB↔Apache 연결은 유휴 60s 까지 산다.

**눈으로 확인**

```bash
# 1) 브라우저 쪽 연결 재사용 — 같은 연결로 두 번 (curl 이 'Re-using existing connection' 을 찍음)
curl -sv https://petclinic.mission-critical.site/ https://petclinic.mission-critical.site/health.html -o /dev/null -o /dev/null 2>&1 | grep -iE "Re-using|Connected to|HTTP/2 200"
# 2) CloudFront → ALB keep-alive 5 · 응답 30
aws cloudfront get-distribution-config --id E2PWXW3LUYTDEE --profile mc-deploy --query 'DistributionConfig.Origins.Items[?Id==`alb-public`].CustomOriginConfig.[OriginKeepaliveTimeout,OriginReadTimeout]' --output text
# 3) ALB 유휴 60
aws elbv2 describe-load-balancer-attributes --load-balancer-arn $(aws elbv2 describe-load-balancers --names mc-alb-public --profile mc-deploy --query 'LoadBalancers[0].LoadBalancerArn' --output text) --profile mc-deploy --query 'Attributes[?Key==`idle_timeout.timeout_seconds`].Value' --output text
# 4) Apache 값 — 코드 근거(web.sh 가 KeepAlive 를 안 건드림) · 서버 확인은 Bastion 허용 후
grep -nE "KeepAlive|Timeout" infra/terraform-kdt5/modules/base/user_data/web.sh || echo "web.sh 에 KeepAlive/Timeout 설정 없음 → httpd 기본값(KeepAliveTimeout 5 · Timeout 60)"
```

기대: 1) `Connected to …` 한 번, 두 번째 요청에 `Re-using existing connection` 2) `5 30` 3) `60` 4) "설정 없음 → 기본값"
## 2-5. ⑤ 리다이렉트가 도는 원리 — 서버는 주소만, 움직이는 건 브라우저
**무슨 일이 일어나나**
1. 서버가 `302` + `Location: https://petclinic.mission-critical.site/` 를 주면 브라우저가 **그 주소로 새 요청**을 보낸다. 서버는 그저 주소를 알려 줄 뿐. 그래서 Location 의 주소가 틀리면(내부 이름 · http) 사용자가 그리로 가서 실패한다.
2. 우리 구간엔 리다이렉트를 내는 곳이 **두 곳**: CloudFront(http → https, 301) 와 Apache(`/petclinic` → `/petclinic/` 301, `/petclinic/` → `/` 302). Tomcat 도 폼 제출 뒤 302 를 낸다(앱 내부).
3. **루프의 전형**: Apache 가 평문으로 받았으니 `Location: http://…/` 로 만듦 → CloudFront 가 http 를 https 로 301 → 다시 Apache → 또 http … 브라우저가 "리디렉션이 너무 많음" 을 띄운다. 그래서 Apache 규칙이 `X-Forwarded-Proto` 를 **먼저** 본다(2-3).
4. 301 은 브라우저가 캐시하므로 되돌리기 어렵고, 302 는 매번 서버에 묻는다. 그래서 "슬래시 붙이기" 처럼 영원한 것만 301.

**우리 값 (실측)**
| 요청 | 응답 | Location | 낸 곳 · 규칙 |
|---|---|---|---|
| `http://petclinic.…/` | 301 | `https://petclinic.mission-critical.site/` | CloudFront 뷰어 정책 `redirect-to-https` |
| `https://…/petclinic` | 301 | `https://petclinic.mission-critical.site/petclinic/` | Apache `RewriteRule ^/petclinic$ https://%｛HTTP_HOST｝/petclinic/ [R=301,L]` (XFP=https 조건) |
| `https://…/petclinic/` | 302 | `https://petclinic.mission-critical.site/` | Apache `RewriteRule ^/petclinic/$ https://%｛HTTP_HOST｝/ [R=302,L]` (XFP=https 조건) |
| (평문으로 Apache 직접 · 서버 안에서) | 302 | `/` (상대 경로) | XFP 조건이 안 맞을 때의 폴백 규칙 — 6단계 |
**없으면 · 오해**
- Location 이 `http://` 로 오는 순간 루프다. 실측 Location 이 전부 `https://` 인 것이 ③④⑤ 가 맞물려 돌아간다는 증거.
- "리다이렉트는 서버가 이동시킨다" — 아니다. 브라우저(또는 curl -L)가 새 요청을 만든다. 그래서 Location 은 **사용자 브라우저가 열 수 있는 주소**여야 한다(내부 ALB 이름 불가).
- 301 을 잘못 걸어 두면 브라우저 캐시 때문에 서버를 고쳐도 사용자는 옛 주소로 계속 간다 — 시크릿 창으로 확인.

**눈으로 확인**

```bash
# 1) 세 리다이렉트의 Location 이 전부 https 인지
curl -sI http://petclinic.mission-critical.site/ | grep -i "^Location"
curl -sI https://petclinic.mission-critical.site/petclinic | grep -i "^location"
curl -sI https://petclinic.mission-critical.site/petclinic/ | grep -i "^location"
# 2) 브라우저가 따라가는 과정 — -L 로 최종 200 까지 (홉 수 확인)
curl -sL -o /dev/null -w "final=%{url_effective} code=%{http_code} redirects=%{num_redirects}\n" http://petclinic.mission-critical.site/petclinic
# 3) 규칙의 원문 — web.sh 에서 (서버 접속 없이)
grep -nE "RewriteCond|RewriteRule" infra/terraform-kdt5/modules/base/user_data/web.sh
```

기대: 1) 세 줄 모두 `https://petclinic.mission-critical.site/…` 2) `final=https://petclinic.mission-critical.site/ code=200 redirects=3`(http→https 301 · `/petclinic`→`/petclinic/` 301 · `/petclinic/`→`/` 302) 3) XFP 조건이 붙은 규칙과 폴백 규칙 쌍
## 2-6. 한 요청의 여행 — 헤더가 어떻게 바뀌나 (오늘 `curl https://petclinic.mission-critical.site/`)
| 구간 | 요청줄 · Host | 이 구간에서 붙는 헤더 | 응답에서 보이는 흔적 |
|---|---|---|---|
| 브라우저 → CloudFront (ICN80 엣지) | `GET / HTTP/2` · `Host: petclinic.mission-critical.site` | — | `HTTP/2 200` · `via: 1.1 ….cloudfront.net` · `x-cache: Miss from cloudfront` · `x-amz-cf-pop: ICN80-P4` |
| CloudFront → ALB | `GET …/ HTTP/1.1` · Host 그대로(AllViewer) | `X-Origin-Verify: (비밀)` · `Via` · `X-Forwarded-For: 221.148.195.245` | ALB 로그: client `15.158.254.101:19438` · `200 200` · `matched_rule_priority 10` |
| ALB → Apache (web-c) | `GET / HTTP/1.1` · Host 그대로 | `X-Forwarded-For: 221.148.195.245, 15.158.254.101` · `X-Forwarded-Proto: https` · `X-Forwarded-Port: 443` · `X-Amzn-Trace-Id` | Apache access_log: `10.0.1.212 - - […] "GET / HTTP/1.1" 200 8133` · 응답 `server: Apache/2.4.68` |
| (앱 경로일 때) Apache → Internal ALB → Tomcat | `HEAD /petclinic/vets HTTP/1.1` · Host 그대로(ProxyPreserveHost) | XFF 에 `10.0.1.212` · `10.0.10.189` 덧붙음 · `X-Forwarded-Host` | WAS access log: `10.0.21.43 - - […] "HEAD /petclinic/vets HTTP/1.1" 200` |
기억할 것 셋: **연결은 구간마다 새것**(그래서 keep-alive·타임아웃도 각각) · **원래 정보(IP·https)는 헤더로만** · **리다이렉트 주소는 브라우저가 열 수 있어야**.
# 3. 용어 — 이 단계에서만 쓰는 것
| 용어 | 한 줄 | 비유 |
|---|---|---|
| 요청줄 | `메서드 경로 버전` — 응답의 첫 줄은 `버전 코드 사유` | 편지 봉투의 첫 줄 |
| Host | 어느 사이트에 온 요청인지. 한 IP 에 여러 사이트가 있어 필수 | 봉투의 "수신: ○○병원" |
| 헤더 | `이름: 값` 줄들. 요청 헤더(브라우저·프록시가 붙임)와 응답 헤더(서버가 붙임) | 봉투에 붙는 스티커 |
| 프록시(리버스) | 클라이언트 대신 뒤 서버에 요청하고 답을 돌려주는 중간자. CloudFront · ALB · Apache 전부 | 접수 창구 |
| X-Forwarded-* | 프록시가 원래 정보를 뒤에 알려 주는 관례 헤더(For · Proto · Port · Host) | 창구 직원의 메모 "원래 오신 분은 ○○, 정문으로 오셨음" |
| keep-alive | 연결을 닫지 않고 다음 요청에 재사용 | 전화를 끊지 않고 다음 질문 |
| 유휴 타임아웃 | 아무 말 없이 얼마나 지나면 끊을지 | 통화 중 침묵이 N초면 끊김 |
| Location | 3xx 응답에서 "여기로 가라" 는 주소 | "그 창구는 2층입니다" 안내 |
| x-cache · via | CloudFront 가 붙이는 응답 헤더 — 캐시 적중 여부 · 어느 엣지를 지났나 | 택배 송장의 경유 스탬프 |
# 4. 왜 이렇게 만들었나 (멘토가 물을 만한 것)
- **왜 Host 를 끝까지 보존하나?** 리다이렉트·절대 링크·인증서 검증이 전부 Host 를 쓴다. 중간에서 바꾸면 사용자가 내부 이름을 받는다.
- **왜 Apache 가 리다이렉트를 만들 때 헤더를 먼저 보나?** ALB 가 TLS 를 풀어 Apache 는 평문만 보기 때문(2단계). 헤더가 유일한 단서.
- **왜 http→https 를 CloudFront 에서 하나?** 오리진까지 가기 전에 끝내는 게 가장 싸고, ALB 는 80 을 아예 안 들어 평문이 VPC 에 안 온다(0단계).
- **왜 502·503·504 를 구분해 두나?** 원인이 다르다 — 502 연결/응답 이상(타임아웃 불일치 · 프로세스 재시작), 503 정상 대상 0(헬스체크), 504 느림(DB·GC). 9단계 진단표의 뼈대.
- **왜 XFF 를 Apache 로그에 아직 안 찍나?** 기본 `combined` 형식 그대로라서. `%｛X-Forwarded-For｝i` 를 넣는 것이 8단계 로드맵 — 넣으면 사용자 IP 로 검색·차단이 가능.
# 5. 다음 단계(2. TLS 종료 지점) 진입 기준
**Q1. 브라우저가 보낸 Host 가 Tomcat 까지 그대로 가려면 CloudFront · ALB · Apache 에서 각각 무엇이 필요한가?**
CloudFront 오리진 요청 정책 AllViewer(Host 전달) · ALB 는 기본 유지 · Apache `ProxyPreserveHost On`. 하나가 빠지면 CloudFront 502(인증서 이름 불일치) 또는 Tomcat 이 만든 링크·리다이렉트가 내부 주소가 된다.

**Q2. Apache 는 자기 앞에서 TLS 가 끝났다는 걸 어떻게 아나?**
모른다 — 연결 자체는 평문 80 이다. ALB 가 붙인 `X-Forwarded-Proto: https` 를 읽어서만 안다. 그래서 RewriteCond 로 그 헤더를 검사하고, 실측 Location 이 전부 https 인 게 그 증거.

**Q3. 502 · 503 · 504 중 "정상 대상이 하나도 없을 때" 나는 코드는? 나머지 둘은?**
503. 502 는 대상이 응답은 했는데 이상하거나 연결이 먼저 끊김(keep-alive 불일치), 504 는 대상이 제시간(ALB 60s · CloudFront 30s)에 응답하지 않음.

**Q4. Apache access_log 의 첫 IP 가 10.0.1.212 인 이유와, 진짜 사용자 IP 는 어디 있나?**
연결 상대가 ALB 노드라서. 사용자 IP 는 `X-Forwarded-For` 맨 앞 값(`221.148.195.245, 15.158.254.101` 의 첫 번째)에 있고, 로그에 남기려면 LogFormat 에 넣어야 한다.

# 6. 읽을 자료 (각 5분)
- MDN — *An overview of HTTP* · *HTTP response status codes* 에서 200 · 301 · 302 · 403 · 404 · 502 · 503 · 504 항목만
- MDN — *X-Forwarded-For* · *X-Forwarded-Proto*
- AWS 문서 — *HTTP headers and Application Load Balancers* (XFF · XFP · X-Amzn-Trace-Id)
- 콘솔 구축 가이드 **2-3 오리진 요청 정책 · 5-2 petclinic.conf** 절
> **로드맵 위치**: 0 VPC 입구 → **1 HTTP 기초(이 페이지)** → 2 TLS 종료 지점 → 3 ALB 해부 → 4 오리진 보호(헤더) → 5 헬스체크 → 6 Apache 프록시 → 7 분산·타임아웃 → 8 WEB 관측 → 9 장애 모드 → 10 ASG·AMI.
