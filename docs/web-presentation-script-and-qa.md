# WEB 계층 — 발표 대본 · 슬라이드 · Q&A 분리본 (9/18)

> 출처: 팀장이 정리한 초안을 "내가 말할 것"과 "물어보면 답할 것"으로 나눔. 사실 관계는 9/18 WEB-C·Bastion 실측으로 확인한 것만 남기고, 과장된 표현 4곳은 ✏️ 로 고침(아래 5절).

---

## A. 발표 — 내가 말할 것 (2분 30초, 슬라이드 3장)

### 슬라이드 1 · SSL 오프로딩 & 암호화 경계
- 외부 구간 HTTPS 2단계: 뷰어 ↔ CloudFront(us-east-1 ACM) · CloudFront ↔ ALB(서울 ACM, HTTPS only)
- ALB → WEB(Apache) **HTTP 80** — `mod_ssl` 미설치, EC2 암복호화 부하 0 · 인증서는 ACM DNS 검증 자동 갱신
- DB 구간만 TLS 강제: WAS → RDS Proxy(`require_tls`) → RDS(`require_secure_transport=1`), JDBC `sslMode=REQUIRED`

### 슬라이드 2 · mod_proxy 리버스 프록시 & 트래픽 분기
- WAS 격리는 **SG 체인**: `mc-sg-was` 8080 ← `mc-sg-alb-internal` 만 · 프라이빗 서브넷 (Bastion → WAS 8080 직접 = timeout 실측)
- 정적은 엣지에서 끝: `/static/*` `/images/*` → CloudFront → S3(OAC), Apache 미경유 (`server: AmazonS3`)
- Apache = 단일 진입점: `/`(랜딩) · `/health.html` 직접, **`/petclinic/` 만** Internal ALB:8080 으로 `ProxyPass` + `ProxyPreserveHost On` (`mod_proxy_http`)

### 슬라이드 3 · Shallow Health Check & 장애 격리 실증
- 검사 깊이 분리: WEB `/health.html`(정적 · `ProxyPass !` · 10s·5s·2/3) · WAS `/petclinic/`(Spring 컨텍스트) · DB는 헬스체크 대신 CloudWatch 알람
- 9/16 실측: `was-a` Access denied → unhealthy, WEB 2대 healthy 유지, `was-c` 로 우회 → 무중단
- 헬스체크 로그 제외 `SetEnvIf … nolog` (✏️ 현재 기본 CustomLog 중복으로 실제론 미동작 → 수정 반영 예정, 트러블슈팅 슬라이드)

### 대본 (~해요체 · 150초)
"WEB 계층, ○○○입니다.
첫째, 암호화 경계예요. 외부 구간은 CloudFront와 ALB에서 각각 ACM 인증서로 두 번 HTTPS를 종단해요. 그래서 아파치에는 mod_ssl을 아예 안 올리고 80 포트만 열어 EC2의 암복호화 부하를 없앴어요. 사설망 안은 평문이지만, 개인정보가 오가는 DB 구간만큼은 RDS Proxy의 require_tls와 JDBC sslMode=REQUIRED로 암호화를 강제했어요.
둘째, 리버스 프록시예요. WAS를 지키는 건 아파치가 아니라 보안 그룹 체인이에요 — Bastion에서 WAS 8080으로 직접 curl 하면 타임아웃이고, Internal ALB를 통해서만 열려요. 정적 파일은 아파치에 오지도 않고 CloudFront와 S3에서 엣지에서 끝나요. 아파치는 랜딩 페이지와 헬스체크만 직접 주고, /petclinic/ 동적 요청만 mod_proxy로 Internal ALB에 넘기는 단일 진입점이에요.
셋째, 헬스체크 깊이 분리예요. WEB은 정적 /health.html, WAS는 앱 컨텍스트 /petclinic/, DB는 CloudWatch 알람으로 나눴어요. 9월 16일 was-a 장애 때 WEB 두 대는 healthy를 유지하고 was-c로 트래픽이 넘어가 서비스가 끊기지 않았어요. 헬스체크 로그 제외 필터도 두었는데, 기본 로그 설정과 겹쳐 실제로는 안 걸러지는 걸 발견해 고치는 중이에요 — 트러블슈팅 장에서 말씀드릴게요."

### (멘토가 로그를 물으면 붙이는) 로그·모니터링 30초
"웹서버 로그는 서버에 두지 않아요. Parameter Store `/petclinic/cwagent/web` 에 access·error 로그 경로와 메모리 지표 설정을 두고, 부팅 때 fetch-config 로 받아 CloudWatch Agent가 `/petclinic/web/access`·`/petclinic/web/error` 로 실시간 전송해요. 서버가 교체돼도 로그가 남고, 기본 EC2 지표엔 없는 메모리 사용률까지 봐요."

---

## B. Q&A — 물어보면 답할 것 (답변 틀: 이름 → 결론 한 줄 → 근거 → 확인 방법)

### ① 암호화
| 질문 | 3초 답 | 근거 | 확인 |
|---|---|---|---|
| 왜 CloudFront–ALB 사이도 HTTPS? | 그 구간도 AWS 밖 공용 인터넷을 지나기 때문 | 엣지(전 세계) ↔ 서울 리전 · 도청·위변조 방지 · ALB 오리진 `https-only` + 서울 ACM | CloudFront 오리진 설정 |
| 왜 내부(ALB→WEB→WAS)는 평문? | VPC·SG로 격리돼 있고 t3 CPU를 암복호화에 쓰지 않으려고 | SG 체인 · 프라이빗 서브넷 · Apache 80만 리스닝, mod_ssl 없음 | `ss -ltnp`(80만) · TG 프로토콜 HTTP |
| ⭐ 내부는 평문인데 DB만 TLS — 모순 아닌가? | DB 데이터는 개인정보·비밀번호 그 자체라 전송 암호화 기준이 다르다 | 웹서버 1대가 뚫려도 내부 패킷으로 DB 원문을 못 봄(측면 이동 차단) · 전송 중 데이터 암호화 권고 | Proxy `require_tls` · 파라미터 `require_secure_transport=1` · `test.jsp` Ssl_cipher |
| 내부 도청 위험은? | 위와 동일 + 종단 DB 구간은 암호화 | — | — |
| 인증서 갱신은 누가? | ACM DNS 검증 자동 갱신, 2장(us-east-1·서울) | Route 53 검증 CNAME 유지 | ACM 상태 ISSUED · Renewal eligible |

### ② 리버스 프록시
| 질문 | 3초 답 | 근거 | 확인 |
|---|---|---|---|
| ⭐ mod_jk 대신 mod_proxy? | 중간에 Internal ALB가 있어 AJP(mod_jk)는 통과 못 함 | ALB는 HTTP/HTTPS만 · AJP 8009 바이너리 불가 · mod_proxy_http는 기본 모듈, 컴파일 불필요 | `petclinic.conf` ProxyPass http://…:8080 |
| 톰캣만 두면 되지 왜 아파치? | 동적 `/petclinic/` 단일 진입점 + 랜딩·정적 분리 + 점검 우회 | `/` 랜딩 index.html · `/petclinic/` 만 프록시 · WAS 중단 시 CloudFront 5xx → `/maintenance.html` 503 (✏️ 점검 페이지는 아파치가 아니라 CloudFront 오류 응답이 함) | conf · CloudFront 오류 응답 |
| 왜 "아파치가 방패"가 아니라 "SG가 막는다"? | 아파치는 L7 소프트웨어, 패킷을 막는 건 SG·서브넷 | Bastion→WAS 8080 timeout 실측 · `mc-sg-was` 8080 ← `mc-sg-alb-internal` 만 | `curl http://10.0.20.x:8080/` timeout |
| 왜 정적을 CloudFront+S3로 뺐나? | EC2 디스크 I/O·대역폭 0, 엣지 캐시로 빠르게 | 9/16 개선 · `/static/*` `/images/*` S3 오리진(OAC) · WAR 안 `/petclinic/resources/*` 는 ALB 경유 캐시 | `curl -I …/static/…css` → `server: AmazonS3`, 두 번째 `x-cache: Hit` |
| ProxyPreserveHost 왜? | 뒤 WAS가 원래 Host(도메인)를 알아야 리다이렉트·링크가 맞음 | 없으면 Tomcat이 내부 ALB DNS로 응답 생성 | conf |
| 정적 파일 바꾸면? | S3 업로드 + CloudFront 무효화(기본 TTL 1일) | — | `create-invalidation /static/*` |

### ③ 헬스체크
| 질문 | 3초 답 | 근거 | 확인 |
|---|---|---|---|
| Shallow면 WAS·DB 죽어도 WEB이 트래픽 받지 않나? | WAS 장애는 Internal ALB가 떼어내고 살아있는 WAS로 보냄 | 9/16 was-a unhealthy → was-c 우회 · WEB까지 Deep이면 전체 마비 | TG 상태 화면 · 알람 |
| 왜 WEB은 `/health.html`? | 아파치 생존만 보면 됨 · `ProxyPass !` 라 WAS·DB 안 감 · 10초마다 DB 커넥션 낭비 없음 | 정적 `ok` 파일 | TG 설정 10s·5s·2/3 |
| WAS 헬스체크 `/petclinic/` 는 DB를 찌르나? | 아니요, 홈 컨트롤러라 DB 쿼리 없음 — 단 Spring 컨텍스트가 떠 있어야 200 | 부팅 때 DB 못 붙으면 404 → unhealthy (9/16 사례) | catalina.out |
| DB 상태는 어떻게? | 헬스체크 대신 CloudWatch 알람(RDS 연결 수·CPU) + RDS 로그 | `mc-rds-connections-high` | 알람 목록 |
| 헬스체크 로그 노이즈? | `SetEnvIf` 제외 필터 — ✏️ 기본 CustomLog 중복으로 미동작 발견, 기본 것 주석 처리로 수정 | 9/18 실측 요청당 2줄 | `?dup=1` 1줄 |

### ④ 로그·모니터링 (멘토 단골)
| 질문 | 3초 답 | 근거 | 확인 |
|---|---|---|---|
| 웹서버 로그·모니터링 구성? | 로컬에 안 두고 CloudWatch Logs로, 설정은 Parameter Store | `/petclinic/cwagent/web` → fetch-config → `/petclinic/web/access`·`/petclinic/web/error` · 메모리·디스크 지표 | 로그 그룹 스트림 = 인스턴스 ID |
| 왜 로컬에 안 두나? | 디스크 풀 방지 · 서버 교체 시 유실 방지 · 침해 흔적 보존 | ASG/교체 시 인스턴스 사라짐 (9/16 롤링 5회 유실 0) | 옛 인스턴스 스트림 조회 |
| 왜 설정을 Parameter Store에? | 서버마다 수정·AMI 재빌드 없이 한 곳만 고침 | 부팅 시 fetch-config | 파라미터 값 |
| 왜 Agent로 메모리? | 기본 EC2 지표는 하이퍼바이저 밖에서 재서 RAM을 못 봄, OOM 감지 | `mem_used_percent` 네임스페이스 MC/WEB | CloudWatch 지표 |
| 로그 장기 보관은? | S3 사본: 구독 필터 → Firehose → `mc-logs/cwlogs/web/` 1년 (9/17) | — | S3 객체 |

---

## C. 사실 관계 — 초안에서 고친 4곳 ✏️
| 초안 | 실제 | 대본 반영 |
|---|---|---|
| "아파치가 있으면 503 점검 페이지로 우회" | 점검 페이지는 **CloudFront 오류 응답**(502/503/504 → S3 `/maintenance.html`)이 함. 아파치 단독으론 502 그대로 | "점검 페이지는 CloudFront가 S3에서 준다" |
| "순수 동적 API(/petclinic/)" | PetClinic은 JSP 페이지(API 아님) | "동적 요청 `/petclinic/`" |
| "SetEnvIf 로그 제외 튜닝 적용" | 설정은 있으나 httpd.conf 기본 CustomLog 중복으로 **현재 미동작**(요청당 2줄) | "적용했으나 미동작 발견 → 수정 중"으로 정직하게 · 트러블슈팅 재료 |
| "WAS 헬스체크는 DB 쿼리 배제" | 검사 자체는 DB 안 찌르지만 **부팅 시 DB 연결 실패면 컨텍스트가 안 떠 404** | "앱 컨텍스트 검사"로 표현, 9/16 사례로 설명 |

## D. 시연·캡처 체크리스트 (WEB)
- [ ] `sudo ss -ltnp | grep httpd` → `*:80` 만 · `rpm -q mod_ssl` → not installed
- [ ] `/etc/httpd/conf.d/petclinic.conf` 화면
- [ ] Bastion: `curl -m 5 http://10.0.20.x:8080/petclinic/` → timeout · WEB: Internal ALB 경유 200
- [ ] `curl -I https://…/static/resources/css/petclinic.css` → `server: AmazonS3` · 두 번째 `x-cache: Hit`
- [ ] 대상 그룹 `mc-tg-web` 상태 검사 설정 화면 · healthy 2/2
- [ ] CloudWatch `/petclinic/web/access` 스트림(인스턴스 ID) · 알람 목록
- [ ] ⚠ 도메인: 가비아 NS가 새 존으로 바뀌어 **현재 `petclinic.mission-critical.site` 미해석** — 새 존에 A/AAAA alias 넣기 전엔 CloudFront 도메인으로 시연
