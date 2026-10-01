# CloudWatch Logs · CloudTrail 쉽게 이해하기 — 무엇을, 왜, 어디서 (mc-deploy 기준 · 2026-09-16)

> 한 줄 요약: **CloudWatch Logs = "서버가 일하면서 남기는 일기"를 밖에 모아 두는 곳. CloudTrail = "누가 AWS 콘솔·CLI에서 무엇을 만졌나"의 출입 기록.** 둘 다 "로그"지만 보는 이유가 다르다.

## 0. 비유로 먼저
| | CloudWatch Logs | CloudTrail |
|---|---|---|
| 비유 | 가게 안 CCTV·매출 장부(영업 중 일어난 일) | 건물 출입 기록·열쇠 사용 내역(누가 문을 열었나) |
| 답하는 질문 | "왜 페이지가 느렸지?", "어떤 SQL이 실패했지?", "Tomcat이 왜 죽었지?" | "누가 보안 그룹을 열었지?", "RDS를 누가 재부팅했지?", "이 비밀번호를 누가 읽어갔지?" |
| 기록 주체 | 서버 안 프로그램(Apache·Tomcat·CloudWatch Agent) | AWS 자체(모든 API 호출을 AWS가 자동 기록) |
| 우리가 켜야 하나 | 예 — Agent 설치·설정, 로그 그룹 생성 | 기본 90일은 자동. 1년 보관·검증은 **추적(Trail)** 을 만들어야 |
| 저장 위치 | CloudWatch Logs(로그 그룹) | S3 버킷(+ 콘솔 이벤트 기록 90일) |

---

## 1. CloudWatch Logs

### 1-1. 목적 — 서버 "안"의 로그를 "밖"으로
서버 안 `/var/log/httpd/access_log`, `/opt/tomcat/logs/catalina.out` 은 **그 서버가 사라지면 같이 사라진다**. 우리는 9/16 하루에만 WEB·WAS를 롤링 교체 4번 했고, ASG를 붙이면 서버가 자동으로 늘고 준다. 그래서 로그는 서버 밖(CloudWatch Logs)에 실시간으로 복사해 둔다.

### 1-2. 이유 — 네 가지
1. **사라지지 않는다**: 인스턴스 교체·축소 뒤에도 로그가 남는다(보관 30일·90일을 우리가 정함).
2. **한 화면에서 본다**: WAS가 2대(앞으로 8대)면 서버마다 들어가 `tail` 할 수 없다. Logs Insights에서 여러 서버 로그를 시간순으로 합쳐 검색한다.
3. **알람의 재료**: 로그에서 "Exception" 같은 단어를 세어 지표로 만들고(지표 필터) SNS/Grafana 알람에 연결할 수 있다.
4. **보안·규정**: 접속 기록(SSM 세션)을 KMS로 암호화해 보관 → "누가 서버에 들어가 무엇을 쳤나"를 증명.

### 1-3. 어디서 쓰나 — 우리 로그 그룹 6개 (실측)
| 로그 그룹 | 무엇이 들어오나 | 보내는 주체 | 보관 | 암호화 | 지금 크기 |
|---|---|---|---|---|---|
| `/petclinic/web/access` | Apache 접속 로그(누가 어떤 URL을, 응답 코드) | CloudWatch Agent(WEB 2대) | 30일 | KMS `mc-cmk` | 1.8 MB |
| `/petclinic/web/error` | Apache 오류(프록시 실패 502 등) | CloudWatch Agent | 30일 | KMS | 3 KB |
| `/petclinic/was/catalina` | Tomcat 기동 로그·Spring 예외(DB 접속 실패 등) | CloudWatch Agent(WAS 2대) | 30일 | KMS | 19 KB |
| `/petclinic/was/access` | Tomcat 접속 로그(Internal ALB→WAS 요청) | CloudWatch Agent | 30일 | KMS | 1.6 MB |
| `/petclinic/was/gc` | JVM GC 로그(메모리 압박·멈춤 시간) | CloudWatch Agent | 30일 | KMS | 12 KB |
| `/petclinic/ssm/sessions` | SSM으로 서버에 들어가 친 명령·출력 | Session Manager | 90일 | KMS | (아직 0) |
| `/aws/rds/instance/mc-petclinic/error` | MySQL 에러 로그 | RDS 내보내기 | 무기한 | — | 3 KB |
| `/aws/rds/proxy/mc-rds-proxy` | RDS Proxy 인증·연결 로그 | RDS Proxy | 무기한 | — | 5 KB |
- 로그 **스트림** = 로그 그룹 안에서 서버 1대당 1줄(이름 = 인스턴스 ID). 오늘 `/petclinic/was/catalina` 에는 교체 전후 인스턴스 3개 스트림이 있어 "옛 서버 로그"도 그대로 조회된다.
- **어떻게 들어오나**: WEB·WAS 부팅 스크립트가 `amazon-cloudwatch-agent` 를 설치하고, 설정(어떤 파일을 어느 그룹으로)은 SSM 파라미터 `/petclinic/cwagent/web`·`/petclinic/cwagent/was` 에서 받는다(Terraform이 배포). 서버 → NAT → CloudWatch API(HTTPS).
- **권한**: 인스턴스 역할 `mc-ec2-role` 에 `CloudWatchAgentServerPolicy`(로그 쓰기) + `ssm:GetParameter(/petclinic/cwagent/*)`.

### 1-4. 안 쓰는 곳 (왜)
- **ALB 액세스 로그** → S3 `mc-logs-…/alb/` 로만 간다. ALB는 CloudWatch Logs 전송을 지원하지 않고, 양이 많아 S3가 싸다(Athena로 조회).
- **CloudTrail** → S3. 필요하면 CloudWatch Logs로도 복사해 "SG 변경 즉시 알람" 같은 지표 필터를 걸 수 있다(로드맵).
- **WAF 로그** → 9/16 WAF 제거로 없어짐.

### 1-5. 알람 3개 (CloudWatch 지표 → SNS)
로그 그룹과 별개로 **지표(metric)** 기반 알람. 상태는 실측(9/16 13:20).
| 알람 | 조건 | 지금 | 뜻 |
|---|---|---|---|
| `mc-was-unhealthy-host` | Internal ALB의 unhealthy WAS ≥ 1, 2분 | **ALARM → 조치 후 OK** | WAS 한 대가 헬스체크 실패. 오늘 was-a가 Proxy 인증 반영 전 부팅해 404 → Tomcat 재시작으로 복구, 부팅 스크립트 보강(`2f746d8`) |
| `mc-alb-p95-latency` | Public ALB 응답 p95 > 2초, 3분 | INSUFFICIENT_DATA | 트래픽이 거의 없어 p95 계산 불가(정상) |
| `mc-rds-connections-high` | RDS 연결 > 60, 3분 | OK | 연결 수 정상 |
알람 → SNS `mc-alerts` → 이메일(구독은 `alert_emails` 변수에 넣으면 생성). Slack은 Grafana Alerting 경로.

### 1-6. 실제로 보는 법
- 콘솔: CloudWatch → 로그 그룹 → `/petclinic/was/catalina` → 스트림 클릭. 또는 **Logs Insights** 에서 그룹 여러 개 선택 후:
```sql
fields @timestamp, @logStream, @message
| filter @message like /Exception|SEVERE|Access denied/
| sort @timestamp desc | limit 50
```
- CLI: `aws logs tail /petclinic/was/catalina --since 30m --follow --profile mc-deploy`
- 오늘 실제 사례: `/petclinic/was/catalina` 에서 `Access denied for user 'petclinic_app'@'10.0.20.216'` 를 찾아 was-a 장애 원인(Proxy 인증 목록 반영 전 기동)을 확정했다 — 서버에 안 들어가고.

---

## 2. CloudTrail

### 2-1. 목적 — "누가 AWS를 만졌나"
콘솔 클릭, CLI, Terraform, 그리고 서비스끼리의 호출(예: Auto Scaling이 EC2를 조회)까지 **모든 API 호출**을 AWS가 자동으로 기록한다. 앱이 남기는 로그가 아니라 **계정 조작 기록**이다.

### 2-2. 이유 — 세 가지
1. **사고 조사**: "누가 보안 그룹 3306을 0.0.0.0/0으로 열었나", "RDS를 누가 재부팅했나", "이 DB 비밀번호를 누가 읽었나(`GetSecretValue`)".
2. **규정**: 개인정보를 다루는 시스템은 접근·변경 기록을 보관해야 한다(개인정보 안전성 확보조치 기준 — 접속기록 1년).
3. **변경 추적**: Terraform apply도 IAM 사용자 `mc-deploy` 이름으로 전부 남는다 → "코드로 바꾼 것"과 "콘솔에서 손으로 바꾼 것"을 구분할 수 있다.

### 2-3. 기본 90일 vs 추적(Trail)
- 아무것도 안 해도 **이벤트 기록** 90일은 콘솔에서 무료로 보인다. 하지만 90일 뒤 사라지고, 파일로 내보내 보관·검색(Athena)이 안 된다.
- **추적(Trail)** 을 만들면 5분마다 S3에 파일로 저장 → 우리가 정한 기간 보관, 변조 검증, 다른 리전 사건도 포함.

### 2-4. 어디서 쓰나 — 우리 구성 (실측)
| 항목 | 값 | 왜 |
|---|---|---|
| 추적 이름 | `mc-trail` (로깅 중, 마지막 전달 13:18) | |
| 범위 | 다중 리전 + 글로벌 서비스(IAM·CloudFront·Route 53) | 서울 밖(버지니아 ACM·CloudFront) 사건도 잡음 |
| 저장 | S3 `mc-cloudtrail-528821350786` `/AWSLogs/528821350786/CloudTrail/ap-northeast-2/2026/09/16/…json.gz` | 5분 간격 압축 파일 |
| 보관 | 90일 후 Glacier IR → 365일 만료 | 1년 규정 + 비용 |
| 보호 | KMS `mc-cmk` 암호화 · 버저닝 · 버킷 정책(CloudTrail만 쓰기·HTTPS만) · **로그 파일 검증** 켜짐 | 검증 = 다이제스트 파일로 "삭제·변조됐는지" 확인 가능 |
| 기록되는 것 | 관리 이벤트 전부 — 예(오늘 13:19): `DescribeInstanceStatus`(AutoScaling), `Decrypt`/`GenerateDataKey`(KMS, 로그 암호화), `DescribeTags`(EC2) | |
| 기록 안 하는 것 | S3 객체 읽기/쓰기(데이터 이벤트 — 진료 파일 저장을 뺐으므로 불필요, 켜면 유료), RDS 안의 SQL, 앱 로그 | |
| 권한 | CloudTrail 서비스가 버킷에 `PutObject`(`bucket-owner-full-control` 조건) | |

### 2-5. 실제로 보는 법
- 콘솔: CloudTrail → 이벤트 기록 → 이벤트 이름 `AuthorizeSecurityGroupIngress` 로 필터 → 누가·언제·어떤 SG·어떤 포트.
- CLI: `aws cloudtrail lookup-events --lookup-attributes AttributeKey=EventName,AttributeValue=ModifyDBInstance --profile mc-deploy`
- 오래된 것(90일 이전)은 S3의 json.gz를 Athena 테이블로 조회.
- 예시 — 오늘 우리가 한 일이 어떻게 남나: `UpdateDistribution`(CloudFront WAF 해제, 사용자 mc-deploy), `DeleteWebACL`(3번 실패 400 → 4번째 성공), `RunInstances`/`TerminateInstances`(WAS 교체), `GetSecretValue`(WAS 부팅 시 역할 `mc-ec2-role`).

---

## 3. 둘의 관계 · 자주 헷갈리는 것
- **CloudWatch Logs에 CloudTrail을 넣을 수 있다** — 추적 설정에서 "CloudWatch Logs로 전송"을 켜면 API 기록도 로그 그룹에 들어와 지표 필터·알람(예: SG 변경 즉시 Slack)이 가능. 지금은 S3만(로드맵).
- **CloudWatch 지표(metric) ≠ 로그** — CPU·응답시간·연결 수 같은 숫자는 로그 없이 서비스가 직접 보낸다. 알람 3개는 이 지표 기반.
- **로그 5종(OT 요구) 중 어디에 속하나**: 앱 로그(CW Logs) · ALB 액세스(S3) · WAF(제거) · SSM 세션(CW Logs) · CloudTrail(S3) → CloudWatch Logs 2종 + S3 2종.
- **비용**: CloudWatch Logs 수집 $0.76/GB + 보관 $0.03/GB·월(지금 총 3.5 MB ≈ $0), CloudTrail 첫 추적 무료(S3 저장 ≈ $0.02/월).

## 4. 발표용 한 줄
"서버가 남기는 로그는 CloudWatch Logs로 서버 밖에 모아 교체·증설에도 잃지 않고, AWS 계정 조작은 CloudTrail로 S3에 1년 보관·변조 검증한다. 오늘 was-a 장애도 서버에 들어가지 않고 `/petclinic/was/catalina`에서 원인을 찾았다."
