# 아키텍처 Q&A 정리 (멘토·OT 질문 대응 · mc-deploy As-Built 2026-09-16 기준)

> Notion 페이지용 원고. 현재 구성: 사용자 → Route 53 → CloudFront[WAF] → Public ALB :443 → Apache ×2 → Internal ALB :8080 → Tomcat 9.0.121 ×2(test 브랜치 Green) → RDS Proxy(TLS) → RDS MySQL 8.4 Multi-AZ. 코드: `infra/terraform-kdt5`.

## 1. CloudFront 캐시 키 · WAF rate-based rule
**캐시 키** = CloudFront 가 "같은 객체"로 보는 기준. 캐시 정책(Cache Policy)이 정하고, 오리진 요청 정책(Origin Request Policy)은 "오리진에 무엇을 넘기나"만 정한다 — 둘은 별개.
| Behavior | 캐시 정책 | 캐시 키 | TTL | 오리진 요청 정책 |
|---|---|---|---|---|
| `/static/*` · `/images/*` · `/petclinic/resources/*` · `/petclinic/images/*` | CachingOptimized | **경로만** (쿼리·쿠키·헤더 제외, Accept-Encoding 만 gzip/br 정규화) | 기본 1일(오리진 Cache-Control 있으면 그 값, 최소 1s·최대 1년) | AllViewer(Host·쿠키·쿼리 전달 — 키엔 안 들어감) |
| `/maintenance.html` | CachingOptimized | 경로 | 1일 | — |
| `*` (동적 · API) | CachingDisabled | 캐시 없음 | — | AllViewer |
- 왜 경로만: `JSESSIONID` 쿠키나 쿼리가 키에 들어가면 사용자마다 다른 객체 → Hit 율 0. 반대로 **쿼리 무시라 `?v=2` 캐시 버스팅이 안 먹음** → 정적 파일을 바꾸면 무효화(`create-invalidation --paths "/petclinic/resources/*" "/static/*" "/images/*"`) 또는 경로 버전(`/v2/…`). 어제 Green 전환 뒤 CSS 가 옛것으로 보인 게 정확히 이 케이스.
- 압축: `compress=true` → 엣지에서 gzip/br. 보안 헤더: SecurityHeadersPolicy(HSTS·nosniff·frame-options).
**WAF rate-based rule** (CLOUDFRONT 범위, 캐시보다 먼저 평가):
- `rate-all`: 소스 IP 당 **5분 창 2,000 요청** 초과 시 Block(403) → 초과 상태가 풀릴 때까지. `rate-booking`: URI 가 `/visits/new` 로 끝나는 요청만(LOWERCASE 변환) IP 당 5분 100 → Phase 3 "예약 폭주" 1차 방어. 관리형 3종(IpReputation·Common·KnownBadInputs)은 "모양"을, rate 는 "양"을 본다.
- 평가는 약 30초 주기 슬라이딩 창이라 limit 은 "정확한 상한"이 아니라 "이 이상이면 곧 차단". 회사 NAT 뒤 다수 사용자가 한 IP 면 오탐 가능 → 필요 시 rate-all 상향, booking 은 유지. 부하 테스트 발생기는 `loadgen_cidrs` 로 allow.
- 로그 → `aws-waf-logs-mc`(CloudWatch Logs, us-east-1) · 지표 `rateAll`·`rateBooking` BlockedRequests 로 차단 건수 확인.

## 2. WEB 의 index.html 유지 · mod_proxy(리버스 프록시)
- **index.html 유지**: Apache `/var/www/html/index.html` + `/static/`(css·js·이미지·hero.mp4 9.6MB) 를 부팅 시 `test` 브랜치 WAR 소스에서 복사해 직접 서빙. 랜딩(정적)은 WEB, 앱은 WAS — 역할 분리. 히어로는 한 번만: 앱 홈 `/petclinic/`(welcome.jsp 도 히어로)은 Apache 가 `/` 로 302.
- **mod_proxy_http** (mod_jk 아님): `ProxyPass /petclinic/ → http://<Internal ALB>:8080/petclinic/` + `ProxyPreserveHost On`. 예외: `/health.html`·`/static/`·`/images/` 는 `ProxyPass !` 로 Apache 가 직접. **mod_jk(AJP)는 배제** — 사이에 Internal ALB 가 있어 AJP 가 통과 못 하고, WAS IP 를 워커에 고정해야 해서 ASG 증설과 충돌. HTTP 리버스 프록시는 목적지가 DNS 하나라 WAS 가 몇 대든 WEB 무변경.
- 리버스 프록시가 하는 일: 헤더 유지(Host·X-Forwarded-For/Proto), 앱 서버 은닉(WAS 는 프라이빗·SG 로 Internal ALB 만 허용), 정적/동적 분리 지점.

## 3. DB 세션 유지(Redis) · SQS 가 필요한가
- **Redis: 지금은 불필요.** 로그인이 없어 공유할 세션이 없고(PetClinic stateless, Internal ALB 스티키 없음), 읽기 부하는 RDS + Proxy 풀링으로 충분. 붙이려면 Spring Session/Cache 코드가 들어가 "소스 0줄" 원칙 위반. 필요 시점: 로그인 도입(세션 공유), 폭주 시 핫 읽기 캐시(수의사 목록), 예약 중복 방지 카운터 → ElastiCache(별도 서비스, RDS 안이 아님) 로드맵.
- **SQS: 지금은 불필요.** 비동기 작업(메일·SMS·파일 처리)이 없음. 예약 폭주 시 쓰기(`/visits/new`)를 큐로 완충하는 설계는 가능하지만 producer/consumer 코드 필요 → 로드맵. 현재 폭주 흡수는 WAF rate → CloudFront 캐시 → (ASG) → RDS Proxy 커넥션 다중화 → RDS Multi-AZ 순.

## 4. CloudWatch Agent 를 init script(user_data)에 쓰나
- **예 (현재)**: WEB·WAS user_data 가 `dnf install amazon-cloudwatch-agent` → `amazon-cloudwatch-agent-ctl -a fetch-config -c ssm:/mc/cwagent/web|was -s`. 설정 JSON 은 코드(Terraform `aws_ssm_parameter`)가 SSM 파라미터로 배포 → AMI 재생성 없이 로그 경로 변경 가능.
- Golden AMI 로 가면 **설치는 AMI 굽는 단계**, 부팅 시엔 fetch-config 만. IAM: `CloudWatchAgentServerPolicy` + 인라인 `ssm:GetParameter(/mc/cwagent/*)`.
- 수집 항목: WEB access/error → `/mc/web/*`, WAS catalina/access/gc → `/mc/was/*`, 메모리·디스크 지표(`MC/WEB`, `MC/WAS` 네임스페이스).

## 5. CloudTrail · CloudWatch Logs 수집
| 로그 | 어디로 | 보관 |
|---|---|---|
| WEB·WAS 앱 로그 | CW Agent → CloudWatch Logs `/mc/web/*` `/mc/was/*` (KMS) | 30일 |
| ALB 액세스 로그(외부·내부) | S3 `mc-logs-<acct>/alb/public|internal` | 90일 만료 |
| WAF | CloudWatch Logs `aws-waf-logs-mc`(us-east-1) | 30일 |
| SSM 세션 | CloudWatch Logs `/mc/ssm/sessions` (KMS) | 90일 |
| CloudTrail(관리 이벤트·다중 리전·로그 파일 검증) | S3 `mc-cloudtrail-<acct>` (KMS·버저닝·CloudTrail 만 쓰기) | 90일 후 Glacier IR → 1년 만료 |
- 왜 인스턴스 밖에: ASG 축소·교체 뒤에도 남아야 하고, 한 곳(CloudWatch/S3)에서 Athena·Logs Insights 로 조회.
- 강화 로드맵: CloudTrail → CloudWatch Logs 연결 + 지표 필터(SG·RDS·IAM 변경 알람), S3 Object Lock(변조 방지), VPC Flow Logs.

## 6. ASG Target Tracking · 로그 수집
- **현재 mc-deploy(terraform-kdt5)는 WEB·WAS EC2 고정 2대** — ASG 는 `infra/terraform`(최종 설계) 과 kdt5 콘솔 `web-test`(CPU 60%, min 2·max 4)에 있음. Phase 3 전에 mc-deploy 도 ASG 로 전환 권장.
- 설계값(`infra/terraform`): WEB ASG min 2·max 6 CPU 60% 목표 추적 · WAS ASG min 2·max 8 CPU 60% + `ALBRequestCountPerTarget` 300 + 예약 증설(이벤트 15분 전 desired 4) · 워밍업 300s · 헬스체크 ELB · 두 AZ 균등 · Rolling 50%.
- 목표 추적이 CloudWatch 알람 2개(high/low)를 자동 생성해 증설·축소. 스케일 인 시 **종료 수명 주기 훅(300s)** 으로 마지막 로그를 S3 `mc-logs/was/<id>/` 에 sync 후 종료 → 로그 유실 없음. 평소 로그는 CW Agent 가 실시간 전송.

## 7. Secrets Manager — 비밀 키 취급 · 전송 중 암호화
- 비밀 = RDS 관리형 `rds!db-…`(admin). 저장: KMS(aws/secretsmanager) 암호화. 전송: Secrets Manager API 는 TLS 1.2 만(HTTPS), WAS → NAT → 엔드포인트. 접근: 인스턴스 역할 인라인 정책이 **그 비밀 ARN 하나**에만 `GetSecretValue`, KMS 는 `kms:ViaService=secretsmanager` 조건. Proxy 도 자기 역할로 조회(앱 무관).
- 평문이 남는 곳 차단: user_data·AMI·git 에 없음, WAS 는 부팅 시 조회 → `mvnw -Djdbc.*` 빌드 → 중간 산물 삭제 → 변수 unset. DB 구간은 Proxy `require_tls` + 파라미터 `require_secure_transport=1` + JDBC `sslMode=REQUIRED`.
- **발견 → 조치(9/16 적용)**: RDS 관리형 admin 비밀은 **7일마다 자동 교체**(다음 9/23 09:00)되는데 WAS 는 빌드 시점 비밀번호를 WAR 에 갖고 있어 교체 뒤 Proxy 인증(SECRETS)이 실패하는 구조였음. → **앱 전용 DB 사용자 `petclinic_app`**(Secrets Manager `mc/petclinic/app-db`, 교체 없음, `petclinic.*` 권한만)을 WAS 부팅 시 admin 으로 생성(멱등)하고 WAR·Proxy 인증(2개)이 그 계정을 사용. admin 은 부팅 시 사용자 생성에만 쓰이므로 교체돼도 무영향. 최소 권한(앱이 admin 미사용)도 충족. 확인: test.jsp `jdbc.username=petclinic_app`, Proxy Auth 2개.

### 7-b. 운영 중 발견 — 커넥션 풀과 RDS Proxy idle timeout
- 증상: 30분 이상 유휴였던 WAS(was-c)가 `JDBC begin transaction failed` 로 exception.jsp 반환(HTTP 200 HTML), 재시작하면 정상.
- 원인: Proxy `idle_client_timeout=1800s` 가 유휴 클라이언트 연결을 끊는데 앱의 tomcat-jdbc 풀에 **검증 설정이 없어** 죽은 연결을 계속 빌려줌.
- 조치: `datasource-config.xml` 에 `testOnBorrow=true · validationQuery=SELECT 1 · validationInterval=30s · testWhileIdle · 유휴 10분 회수 · maxActive 20`(XML 설정만, Java 무수정). 교훈: Proxy/LB 뒤의 풀은 반드시 검증·회수 설정이 있어야 한다.

## 8. 기능 구현이 필요한가 — 스토리지·Lifecycle(진료 기록 · 개인정보)
- 앱 기능 추가 없음(안 C). 개인정보(이름·전화·예약)는 **RDS 행** 으로만 존재 → 보호는 Multi-AZ·자동 백업 7일(PITR)·AWS Backup 일일 볼트·삭제 방지·저장 암호화·TLS 강제로 충족. 진료 **파일** S3 저장은 9/14 시나리오에서 제외(Object Lock·Macie 불필요).
- Lifecycle 은 로그·감사에만: ALB 90일, 인스턴스 로그 30일, CloudTrail 1년(90일 후 Glacier IR). 개인정보 보존기간·파기는 정책 문서로 정의하고, 파기 작업이 필요하면 예약 SQL(EventBridge + Lambda/ SSM Automation) 로 로드맵.
- 만약 진료 파일이 요구되면: S3(KMS·버킷 키) + Object Lock(Compliance) + 수명 주기(IA 90일 → Glacier 1년 → 파기) + 데이터 이벤트 CloudTrail — 코드 골격은 이전 `infra/terraform` 이력에 있음.

## 9. 권한 — 모두 거부 + 명시적 허용, 태그 기반 정책
- IAM 은 기본 암묵적 거부. 코드의 역할들은 **필요한 ARN 만 허용**: EC2 역할 = SSM Core·CW Agent + 인라인(비밀 ARN 1개·KMS ViaService·`/mc/cwagent/*`·S3 `mc-logs/was|web/*`), Proxy 역할 = 비밀 1개, Backup 역할 = 서비스 정책. 명시적 거부: 버킷 정책 `aws:SecureTransport=false` Deny, 점검 버킷은 CloudFront OAC(`SourceArn`) 만.
- **태그 기반(ABAC)**: Terraform `default_tags` 로 모든 리소스에 `Project=petclinic-3tier · Team=mc-1 · Env=lab · Tier=edge|web|was|db|ops · ManagedBy`. 사람용 정책 예시 —
```json
{"Effect":"Allow","Action":["ec2:StartInstances","ec2:StopInstances","ec2:RebootInstances"],"Resource":"*",
 "Condition":{"StringEquals":{"aws:ResourceTag/Project":"petclinic-3tier"}}},
{"Effect":"Allow","Action":"ssm:StartSession","Resource":"arn:aws:ec2:*:*:instance/*",
 "Condition":{"StringEquals":{"ssm:resourceTag/Tier":["web","was"]}}},
{"Effect":"Deny","Action":["ec2:RunInstances","rds:CreateDBInstance"],"Resource":"*",
 "Condition":{"Null":{"aws:RequestTag/Project":"true"}}}
```
  → 태그 없는 리소스 생성 거부, 우리 프로젝트 태그가 붙은 것만 조작, SSM 접속은 Tier 로 제한. 조직이면 SCP 로 같은 규칙을 계정 전체에.

## 10. 네이밍 규칙
`<prefix>-<계층/서비스>-<구분>[-<az>]`, prefix = `mc`(name_prefix 변수).
| 종류 | 규칙 | 예 |
|---|---|---|
| 네트워크 | `mc-vpc`, `mc-<tier>-<az>` | `mc-web-a`, `mc-db-c`, `mc-nat-a`, `mc-rt-private-c` |
| 보안 그룹 | `mc-sg-<대상>` | `mc-sg-alb-public`, `mc-sg-was`, `mc-sg-rds-proxy` |
| LB·TG | `mc-alb-<public|internal>`, `mc-tg-<tier>` | `mc-alb-public`, `mc-tg-was` |
| 인스턴스 | `mc-<tier>-<az>` (ASG 는 `mc-asg-<tier>`, LT `mc-lt-<tier>`) | `mc-was-c` |
| DB | `mc-petclinic`(인스턴스) · `mc-mysql84`(파라미터 그룹) · `mc-rds-proxy` | |
| 버킷(전역 유일) | `mc-<용도>-<계정ID>` | `mc-logs-528821350786` |
| 로그 그룹 · SSM 파라미터 | `/mc/<tier>/<stream>` · `/mc/<용도>/<이름>` | `/mc/was/catalina`, `/mc/cwagent/was` |
| IAM · KMS · SNS · CloudTrail | `mc-<대상>-role`, `alias/mc-cmk`, `mc-alerts`, `mc-trail` | |
| 태그 | Project · Team · Owner · Env · Tier · ManagedBy · (Name) | |
kdt5 콘솔 구축본(`test-vpc`, `Targetgroup-web`, `alb-internal-test`, `web-appache`)은 규칙 밖 → 정리 대상.

## 11. CDN(CloudFront)을 정말 써야 하나
- 솔직한 답: 한국 사용자 위주·소규모 트래픽이면 **캐시 성능 이득은 작다.** 그래도 두는 이유는 성능보다 **경계**: ① WAF(CLOUDFRONT)·Shield Standard 가 엣지에서 차단 → ALB·WAS·RDS 미도달, ② 오리진 은닉(프리픽스 리스트 + X-Origin-Verify, 80 리스너 없음), ③ 5xx → S3 점검 페이지 failover(전 계층 장애 때도 안내), ④ 엣지 TLS/HTTP3, ⑤ Phase 3 폭주 때 정적(`/static/*`·`/petclinic/resources/*`) 을 엣지가 흡수.
- 없앤다면: WAF 를 REGIONAL 로 ALB 에 부착, 점검 페이지는 ALB 고정 응답, ACM 은 서울 1개, `/static` 은 Apache 가 직접 — 구성은 단순해지지만 DDoS 흡수·오리진 은닉·전 계층 장애 안내가 약해진다.
- 비용: 프리 티어 1TB/월·1천만 요청 안이라 실질 0에 가까움. 결론: **유지** (요구사항의 "고가용·보안" 축에 기여, 비용 무시 수준).

## 이전 라운드 요약 (한 줄씩)
- Apache index.html → 유지, WAR 소스에서 복사(§2) · mod_jk 아님 mod_proxy · Golden AMI = 부팅 검증 → 흔적·WAR 제거 → `create-image` → `*_ami_id` 변수(JNDI 프로필로 WAR 환경 독립화 가능) · init script 는 WEB/WAS 각각 필요(설치·환경값 다름) · DB 는 RDS Proxy 경유(빌드 시 주입, H2 아님) · 읽기 테스트 GET /vets·/owners, 쓰기 POST /owners/new·/visits/new(loadgen_cidrs 먼저) · Grafana 는 Identity Center 필요, Slack 은 Grafana Alerting 한 경로, 이메일은 `alert_emails` · ACM 은 DNS 검증 CNAME 유지 시 자동 갱신 · 파라미터 그룹은 기본이 수정 불가 + TLS 강제·utf8mb4 · Redis 불필요(§3).
