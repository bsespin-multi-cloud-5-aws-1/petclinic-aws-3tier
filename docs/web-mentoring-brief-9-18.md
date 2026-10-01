# WEB 계층 — 멘토링 브리핑 (9/18 · 3회차)

> 용도: 멘토링 때 화면 공유하고 **3분 안에 읽는 것**. 발표 대본이 아니라 "무엇을 어떻게 만들었고, 무엇이 확인됐고, 무엇을 물어볼지". 실측 전부 9/18 오전 (WEB-C · Bastion · 코드).

## 1. 한 줄
CloudFront → ALB(HTTPS 종단) → **Apache 80(평문·mod_proxy_http)** → Internal ALB 8080 → Tomcat. WAS 격리는 SG 체인, 정적은 엣지(S3), 헬스체크는 계층별 깊이 분리 — 9/16 장애 때 격리 실증.

## 2. 구성 3가지 (했음 · 근거)
| # | 구성 | 우리 값 | 근거(실측) |
|---|---|---|---|
| 1 | **SSL 오프로딩 · 암호화 경계** | 외부 HTTPS 2단계(뷰어↔CloudFront us-east-1 ACM · CloudFront↔ALB 서울 ACM, https-only) → ALB→Apache **HTTP 80** → 사설망 평문 → **DB 구간만 TLS 강제**(Proxy `require_tls` · JDBC `sslMode=REQUIRED` · 파라미터 `require_secure_transport=1`) | Apache `ss -ltnp` → `*:80` 만, `mod_ssl` 미설치 · 리라이트가 `X-Forwarded-Proto` 헤더로 https 판단 · ACM DNS 검증 자동 갱신 |
| 2 | **mod_proxy 리버스 프록시 · 트래픽 분기** | `ProxyPass /petclinic/ → internal-ALB:8080` + `ProxyPreserveHost On` · `/` 랜딩·`/health.html` 직접 · **정적 `/static/*` `/images/*` 는 CloudFront→S3(OAC)** 로 Apache 미경유 · WAS 차단은 **SG 체인**(`mc-sg-was` 8080 ← `mc-sg-alb-internal`만) | Bastion→WAS 8080 직접 `curl` = timeout · WEB→Internal ALB 200 · 정적 응답 `server: AmazonS3` |
| 3 | **Shallow Health Check · 장애 격리** | WEB `mc-tg-web` `/health.html` 10s·5s·2/3 (`ProxyPass !` 라 WAS·DB 안 감) · WAS `mc-tg-was` `/petclinic/`(컨텍스트) · DB는 CloudWatch 알람 | 9/16 `was-a` Access denied → unhealthy, WEB 2대 healthy 유지, `was-c` 우회 · 무중단 |

## 3. 로그·모니터링 (WEB 담당 = WEB 로그)
- Parameter Store `/petclinic/cwagent/web` → 부팅 시 `fetch-config` → CloudWatch Agent → `/petclinic/web/access` `/petclinic/web/error`(30일) + 메모리·디스크 지표(MC/WEB)
- ALB 액세스 로그 → S3 `mc-logs/alb/public|internal` 90일 · (9/17) CloudWatch Logs 사본 → Firehose → S3 `cwlogs/web/` 1년
- 왜: 서버 교체·디스크 풀·침해 흔적 — 9/16 롤링 5회 유실 0

## 4. 발견한 이슈 (트러블슈팅 재료 · 정직하게)
| 이슈 | 상태 |
|---|---|
| 헬스체크 로그 제외 `SetEnvIf … nolog` 가 **안 걸러짐** — httpd.conf 기본 `CustomLog` 가 같은 파일에 또 씀 → 요청당 2줄, 헬스체크 줄 남음 | 원인 확인(9/18 `?dup=1` → 2줄) · 수정안 = 기본 CustomLog 주석(코드 반영, 적용 대기) |
| **도메인 미해석** — 가비아 NS 가 새 Route 53 존으로 바뀌었는데 그 존에 A/AAAA 없음 | 오늘 새 존에 alias 추가 예정 · 전까지 CloudFront 도메인으로 확인 |
| ALB SG 에 이전 테스트용 0.0.0.0/0 규칙 잔존 여부 | 콘솔 계정 현황 점검 중 (E1 보고) |

## 5. 멘토님께 여쭤볼 것 (3개)
1. **내부 평문 vs DB TLS** — "VPC 안은 평문, DB 구간만 TLS 강제"를 현업 기준으로 어떻게 보시는지. 내부까지 TLS(ALB→EC2 HTTPS) 를 요구하는 경우는 어떤 때인지 (규제·제로트러스트).
2. **WAS 헬스체크 깊이** — `/petclinic/`(컨텍스트) vs 전용 `/health` 엔드포인트(DB ping 포함). 코드 수정 없이 가는 현재 방식이 적절한지, 운영에선 어디까지 보는지.
3. **정적 분리 기준** — 랜딩 자산은 S3, WAR 안 `/petclinic/resources/*` 는 여전히 Tomcat 경유 캐시. 이걸 빌드 때 S3 로 빼는 게 맞는지, 아니면 CloudFront 캐시로 충분한지.

## 6. 다음 멘토링(9/22)까지
- [ ] CustomLog 중복 수정 적용 → `?dup=1` 1줄 확인
- [ ] 콘솔 계정: 새 존 alias · ALB 443/403 규칙 · SG 정리 (E1 → E2)
- [ ] WEB 로그 그룹 스트림 확인 · ALB 액세스 로그 첫 객체
- [ ] 시연 캡처: `ss -ltnp` · conf · Bastion timeout · `server: AmazonS3` · TG healthy · 로그 스트림
