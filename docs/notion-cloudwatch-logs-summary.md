# CloudWatch Logs 총정리 — 오늘(9/16) 나온 질문과 답을 한 장에

> 질문 순서대로: ① 왜 계층마다 있나 → ② S3인가 → ③ CloudTrail은 VPC 밖인가 → ④ CloudFront는 어떻게 남기나(알아서 되나) → ⑤ 파일·객체·블록 → ⑥ ASG면 로그를 어디에 두나. 실측·조치 포함.

## 1. 한 장 그림
```
[EBS 파일] WEB: /var/log/httpd/*     ─┐
[EBS 파일] WAS: /opt/tomcat/logs/*   ─┤─ CloudWatch Agent(각 서버에 설치) ──▶ CloudWatch Logs  (계정에 1개 · VPC 밖 · 자체 저장소)
            SSM 세션                  ─┘                                       로그 그룹 /petclinic/web/* /petclinic/was/* /petclinic/ssm/sessions

 ALB ×2 ─┐
 CloudFront ─┼── 서비스가 5분마다 직접 ──▶ S3 mc-logs (객체 .gz)   alb/ · cloudfront/
 CloudTrail ─┘  (계정 수준, VPC·리전 밖)  ▶ S3 mc-cloudtrail (객체 .json.gz)
```

## 2. 질문 → 답
| # | 질문 | 답 (한 줄) | 근거·실측 |
|---|---|---|---|
| ① | CloudWatch Logs가 왜 계층마다 있나 | **없다.** 계정에 하나 있는 리전 서비스. 도면의 계층 옆 아이콘은 "여기서 로그가 나간다"는 출발점 표시였고, 로그 **그룹**만 계층별로 나눈 것(검색·보관·권한을 따로 관리하려고) | 로그 그룹 6개 `/petclinic/web/*`·`/petclinic/was/*`·`/petclinic/ssm/sessions`, 스트림 = 인스턴스 ID |
| ② | S3에 저장되나 | **아니다.** CloudWatch Logs는 자체 저장소(파일·객체·블록 어느 것도 아닌 로그 이벤트 DB). S3로 가는 건 ALB·CloudFront·CloudTrail. (9/17) 단, 장기 보관용 **사본**은 구독 필터 → Firehose 로 S3 `mc-logs/cwlogs/‹tier›/` 에 1년 — 원본은 여전히 CloudWatch Logs | `describe-log-groups`: storedBytes 3.5 MB, KMS 암호화, 보관 30/90일 |
| ③ | CloudTrail은 VPC 밖인가 | **맞다.** 계정 수준 서비스. 서버·에이전트·네트워크 무관, AWS API 서버가 호출을 받을 때 기록해 S3에 떨굼 | `mc-trail` 다중 리전·로그 파일 검증, 마지막 전달 13:18 |
| ④ | CloudFront 같은 관리형 리소스는 어떻게 남기나, 알아서 되나 | **알아서 안 된다.** 우리 서버(EC2)는 Agent를 설치해야 하고, 관리형 리소스(CloudFront·ALB·RDS·SSM)는 안에 설치할 곳이 없어 리소스 설정에서 "로깅 켜기 + 목적지"를 켜야 한다. 목적지는 서비스마다 정해져 있음(CloudFront·ALB = S3만, RDS = CW Logs만) | CloudFront 로그가 빠져 있어 오늘 켬(아래 4절) |
| ⑤ | 파일인지 객체인지 블록인지 | 서버 안 원본 = **블록**(EBS) 위 파일 · S3 로그 = **객체**(5분마다 새 .gz, append 불가) · **파일**(EFS)은 로그엔 안 씀 · CloudWatch Logs = 셋 다 아님 | |
| ⑥ | ASG면 로그를 어디에 두나 | **서버에 두지 않는다.** 만들자마자 밖으로(Agent 실시간 전송), 스트림 이름에 인스턴스 ID, 설정은 SSM 파라미터에서, 축소 때 종료 훅 300초로 마지막 줄 S3 sync | 오늘 롤링 교체 5번 동안 유실 0, 옛 인스턴스 3개 스트림 조회 가능 |

## 3. 우리 로그 5종 최종 (WAF 제거 후)
| 로그 | 만드는 곳 | 어떻게 나가나 | 저장소 · 형태 | 보관 | 켜는 방법 |
|---|---|---|---|---|---|
| 앱(Apache·Tomcat) | WEB·WAS EC2 | **CloudWatch Agent**(우리가 설치) | CloudWatch Logs · 이벤트 | 30일 | user_data 설치 + SSM 파라미터 설정 + IAM |
| SSM 세션 | Session Manager | 서비스 → CW Logs | CloudWatch Logs | 90일 | 세션 설정 문서 `SSM-SessionManagerRunShell` |
| ALB 액세스 | Public·Internal ALB | 서비스 → S3 5분 | S3 `mc-logs/alb/` · 객체 | 90일 | ALB `access_logs` + 버킷 정책 |
| **CloudFront 액세스** | CloudFront | 서비스 → S3 (1시간 이내) | S3 `mc-logs/cloudfront/` · 객체 | 90일 | `logging_config` + 버킷 ACL(BucketOwnerPreferred) — **9/16 켬** |
| CloudTrail | AWS 계정 | 서비스 → S3 5분 | S3 `mc-cloudtrail-…` · 객체 | 1년(90일 후 Glacier IR) | 추적 `mc-trail` |
+ 부가: RDS 에러 로그 `/aws/rds/instance/mc-petclinic/error`, RDS Proxy 로그 `/aws/rds/proxy/mc-rds-proxy` (자동 생성, CW Logs)

## 4. 오늘 조치
1. **CloudFront 액세스 로그 켬** (`a7e0c99`) — WAF를 뺀 뒤 엣지에서의 유일한 요청 기록. `mc-logs` 버킷에 `BucketOwnerPreferred`(CloudFront 표준 로그는 ACL로 씀), `cloudfront/` 90일 만료, output `log_locations`. 확인: `Logging.Enabled=true`, 버킷 ACL에 `awslogsdelivery` FULL_CONTROL 자동 부여. 첫 객체는 요청 후 수 분~1시간.
2. **도면 수정** — 계층 옆 CloudWatch 아이콘 제거 → 운영 계층에 CloudWatch Logs 1개(VPC 밖) + 각 계층에서 Agent 점선(분홍), ALB·CloudFront → S3 객체(초록), CloudTrail "계정 수준 · VPC·리전 밖" 표기, 로그 원칙 노트.
3. **was-a 장애 발견·복구** — 알람 `mc-was-unhealthy-host`가 ALARM → `/petclinic/was/catalina`에서 `Access denied for user 'petclinic_app'` 확인(Proxy 인증 목록 반영 전 부팅) → Tomcat 재시작으로 healthy → `was.sh` 보강(`2f746d8`: Proxy 경유 앱 로그인 대기 + 404면 재시작). **서버에 들어가지 않고 CloudWatch Logs로 원인을 찾은 실제 사례.**

## 5. 아직 안 한 것 (로드맵)
- `alert_emails` 비어 있음 → SNS 이메일 구독 0건 (tfvars 한 줄)
- CloudTrail → CloudWatch Logs 연결 + 지표 필터(SG·RDS·IAM 변경 즉시 알람)
- ASG 도입 시 종료 훅(300초 S3 sync)을 `modules/base`에 추가 (`infra/terraform`엔 이미 있음)
- kdt5 콘솔 구축본: 인스턴스 프로파일 미부착이라 Agent 설치해도 전송 불가 → ⓜ3·ⓜ4

## 6. 확인 명령
```bash
aws logs describe-log-groups --log-group-name-prefix /mc --query 'logGroups[].[logGroupName,retentionInDays,storedBytes]' --output table --profile mc-deploy
aws logs tail /petclinic/was/catalina --since 1h --profile mc-deploy | grep -iE "SEVERE|Access denied"
aws s3 ls s3://mc-logs-528821350786/cloudfront/ --profile mc-deploy      # CloudFront 로그 객체
aws s3 ls s3://mc-logs-528821350786/alb/public/ --recursive --profile mc-deploy | tail -3
aws cloudtrail lookup-events --max-results 5 --profile mc-deploy --query 'Events[].[EventTime,EventName,Username]' --output table
```
