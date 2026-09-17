> **이 단계의 목표**: HTTP 전체가 아니라 "CloudFront 를 떠나 Apache 에 닿기까지" 구간에서 **실제로 쓰이는 다섯 가지**만 손에 익힌다. 하루 분량. 뒤의 2~9단계(TLS · ALB 규칙 · 헤더 검증 · 헬스체크 · Apache 프록시 · 타임아웃 · 로그 · 장애)가 전부 여기에 기댄다.
# 1. 딱 필요한 다섯 가지
| 개념 | 한 줄 뜻 | 우리 설계에서 쓰이는 곳 (다음 단계) |
|---|---|---|
| 요청줄 + **Host 헤더** | `GET /petclinic/ HTTP/1.1` + `Host: petclinic.mission-critical.site` — "어느 사이트의 어느 경로" | ALB 규칙 · Apache `ProxyPreserveHost` · CloudFront `AllViewer` 가 전부 "Host 를 누가 어떻게 넘기나" 문제 (3 · 6단계) |
| 상태 코드 **200 · 301 · 302 · 403 · 502 · 503 · 504** | 서버가 결과를 세 자리 숫자로 말함 | 403 = 리스너 기본 작업, 302 = Apache 랜딩 리다이렉트, 5xx = 장애 모드 · 점검 페이지 (3 · 9단계) |
| **X-Forwarded-For · X-Forwarded-Proto** | 프록시가 "원래 클라이언트 IP" 와 "원래 https 였나" 를 뒤로 전달하는 헤더 | Apache 로그의 진짜 IP · 리다이렉트를 https 로 만드는 조건 (4 · 6 · 8단계) |
| **keep-alive · 유휴 타임아웃** | 한 TCP 연결을 여러 요청에 재사용, 놀면 끊음 | ALB 유휴 60s 와 Apache 타임아웃이 안 맞으면 502 (7단계) |
| **리다이렉트가 도는 원리** | 3xx + `Location` 헤더 → 브라우저가 그 주소로 다시 요청 | TLS 종료기 뒤에서 루프가 나는 이유 (6단계) |
# 2. 하나씩
## 2-1. 요청줄과 Host
브라우저가 보내는 첫 줄은 **메서드 · 경로 · 버전**, 둘째 줄이 **Host**. 같은 IP 에 사이트가 여럿 있을 수 있어서 "어느 사이트냐" 는 Host 로만 구분한다.

```text
GET /petclinic/vets HTTP/1.1
Host: petclinic.mission-critical.site
```

우리 구간에서 이 Host 는 세 번 손을 탄다:
- CloudFront → ALB: 오리진 요청 정책 **AllViewer** 라서 뷰어의 Host 가 그대로 간다 (안 넘기면 ALB 인증서 이름과 안 맞아 실패)
- ALB → Apache: ALB 는 Host 를 바꾸지 않는다
- Apache → Internal ALB: `ProxyPreserveHost On` 이라 Tomcat 도 원래 Host 를 본다 (리다이렉트·링크 생성에 쓰임)
## 2-2. 상태 코드 — 우리 구간에서 실제로 보는 것만
| 코드 | 뜻 | 우리 아키텍처에서 언제 나오나 |
|---|---|---|
| 200 | 성공 | `/` 랜딩(Apache 직접) · `/petclinic/vets`(Tomcat) |
| 301 | 영구 이동 | `/petclinic` (슬래시 없음) → `/petclinic/` — Apache RewriteRule |
| 302 | 임시 이동 | `/petclinic/` → `/` (히어로는 한 번만) — Apache RewriteRule |
| 403 | 거부 | ALB 443 리스너 **기본 작업** — `X-Origin-Verify` 헤더가 없거나 틀린 요청 (CloudFront 우회 차단) |
| 502 | 게이트웨이 오류 — 뒤 서버가 응답은 했는데 이상 | Apache 가 죽어가는 중 · 타임아웃 불일치로 연결이 먼저 끊김 |
| 503 | 서비스 불가 — **보낼 정상 대상이 하나도 없음** | WEB 2대 모두 unhealthy · CloudFront 는 502/503/504 를 받으면 `/maintenance.html` 을 **503** 으로 돌려줌 |
| 504 | 게이트웨이 타임아웃 — 뒤 서버가 제때 응답 안 함 | ALB 유휴 60s · CloudFront 오리진 응답 30s 안에 답이 없을 때 |
기억법: **4xx 는 "네 잘못"(클라이언트), 5xx 는 "내 잘못"(서버 쪽)**. 502/503/504 는 전부 "중간의 프록시(ALB·CloudFront)가 뒤를 대신해 사과하는 것".
## 2-3. X-Forwarded-For · X-Forwarded-Proto
프록시(CloudFront · ALB)를 지나면 뒤 서버가 보는 연결의 상대는 **프록시 IP** 이고, 프로토콜은 **http**(ALB → Apache 는 평문 80)다. 원래 정보는 헤더로만 전달된다.
| 헤더 | 누가 붙이나 | 값 예 | Apache 가 어디에 쓰나 |
|---|---|---|---|
| `X-Forwarded-For` | CloudFront 가 뷰어 IP 를 넣고, ALB 가 뒤에 CloudFront IP 를 덧붙임 | `183.98.42.129, 13.224.x.x` | 로그의 진짜 클라이언트 IP (맨 앞 값) · WAF rate 제한도 이 IP 기준 |
| `X-Forwarded-Proto` | ALB (뷰어가 https 였으면 `https`) | `https` | `RewriteCond %<HTTP:X-Forwarded-Proto> =https` — 리다이렉트 Location 을 https 로 만들 때 |
| `X-Forwarded-Port` | ALB | `443` | (우리는 안 씀) |
왜 중요한가: 헤더를 안 보면 Apache 는 "나는 80 포트 http 서버" 라고만 알아서 (1) 로그에 CloudFront IP 만 남고 (2) 리다이렉트를 `http://…` 로 보내 브라우저가 다시 https 로 올라오며 **루프** 또는 혼합 콘텐츠가 난다.
## 2-4. keep-alive 와 유휴 타임아웃
HTTP/1.1 은 기본으로 연결을 재사용한다(keep-alive). 양쪽이 "얼마나 놀면 끊을지" 를 각자 정하는데, **뒤쪽(Apache)이 앞쪽(ALB)보다 먼저 끊으면** ALB 가 이미 닫힌 연결에 요청을 보내 502 가 난다.
- 우리 값: ALB 유휴 제한 **60초** → Apache 의 `KeepAliveTimeout`/`Timeout` 은 그보다 **길어야** 안전 (7단계에서 실제 값 확인)
- CloudFront → ALB 도 keep-alive 5초 · 응답 제한 30초 (② 오리진 설정)
## 2-5. 리다이렉트가 도는 원리
서버가 `302` + `Location: https://petclinic.mission-critical.site/` 를 주면 브라우저가 **그 주소로 새 요청**을 보낸다. 서버는 그저 주소를 알려줄 뿐, 브라우저가 움직인다.
루프가 나는 전형: Apache 가 http 인 줄 알고 `Location: http://…/petclinic/` 로 보냄 → CloudFront 가 http 를 https 로 리다이렉트 → Apache 가 또 http 로 … . 그래서 6단계의 RewriteRule 이 `X-Forwarded-Proto` 를 먼저 본다.
# 3. 오늘 실습 — 우리 사이트로 확인

```bash
# 1) 요청줄 · Host · 상태 코드 · 응답 헤더를 한 번에
curl -sv https://petclinic.mission-critical.site/ -o /dev/null 2>&1 | grep -E "^> (GET|Host)|^< HTTP|^< (via|x-cache|server|location)"

# 2) 302 리다이렉트 — Location 이 https 로 오는지 (Apache 가 X-Forwarded-Proto 를 봤다는 증거)
curl -sI https://petclinic.mission-critical.site/petclinic/ | grep -iE "^HTTP|location"

# 3) 403 — 헤더 없이 ALB 를 직접 (SG 에 막히면 타임아웃 — 그것도 정답)
curl -sk -m 8 -o /dev/null -w "%{http_code}\n" https://mc-alb-public-485062926.ap-northeast-2.elb.amazonaws.com/

# 4) Apache 로그의 맨 앞 IP 가 CloudFront 인지 (Bastion 경유)
ssh -i infra/terraform-kdt5/.keys/mc-ssh.pem -J ec2-user@52.78.145.87 ec2-user@10.0.10.189 'sudo tail -3 /var/log/httpd/access_log'
```

| 실습 | 기대 결과 | 배우는 것 |
|---|---|---|
| 1 | `HTTP/2 200` · `via: 1.1 ….cloudfront.net` · `server: Apache` · `x-cache: Miss` 또는 `Hit` | CloudFront 를 거쳐 Apache 가 응답했다는 흔적 |
| 2 | `HTTP/2 302` · `location: https://petclinic.mission-critical.site/` | Location 이 https — X-Forwarded-Proto 가 동작 |
| 3 | `000`(타임아웃) 또는 `403` | SG(1차) · 헤더(2차) 두 겹 방어 — 4단계 예고 |
| 4 | 첫 IP 가 `13.x` 등 AWS 대역(CloudFront), 내 IP 아님 | "왜 X-Forwarded-For 가 필요한가" 체감 — 8단계에서 로그 형식에 XFF 넣기 |
# 4. 다음 단계(2. TLS 종료 지점) 진입 기준
아래 셋을 **자기 말로** 설명할 수 있으면 넘어간다.
**Q1. 브라우저가 보낸 Host 가 Apache 까지 그대로 가려면 CloudFront · ALB · Apache 에서 각각 무엇이 필요한가?**
CloudFront 오리진 요청 정책 AllViewer(Host 전달) · ALB 는 기본 유지 · Apache `ProxyPreserveHost On` (Tomcat 까지 전달). 셋 중 하나가 빠지면 인증서 불일치(ALB) 또는 Tomcat 이 만든 링크·리다이렉트가 내부 주소가 된다.
**Q2. Apache 는 자기 앞에서 TLS 가 끝났다는 걸 어떻게 아나?**
모른다 — 연결 자체는 평문 80 이다. ALB 가 붙인 `X-Forwarded-Proto: https` 헤더를 읽어서만 안다. 그래서 RewriteCond 로 그 헤더를 검사한다.
**Q3. 502 · 503 · 504 중 "정상 대상이 하나도 없을 때" 나는 코드는?**
503. 502 는 대상이 응답은 했는데 이상(또는 연결이 먼저 끊김), 504 는 대상이 제시간에 응답하지 않음.
# 5. 읽을 자료 (각 5분)
- MDN — HTTP 개요 (An overview of HTTP)
- MDN — HTTP 응답 상태 코드 (HTTP response status codes) 에서 200 · 301 · 302 · 403 · 502 · 503 · 504 항목만
- MDN — X-Forwarded-For
- MDN — X-Forwarded-Proto
> **로드맵 위치**: 1 HTTP 기초 → 2 TLS 종료 지점 → 3 ALB 해부 → 4 오리진 보호(헤더) → 5 헬스체크 → 6 Apache 프록시 → 7 분산·타임아웃 → 8 WEB 관측 → 9 장애 모드 → 10 ASG·AMI. 상위 페이지에 전체 표.
