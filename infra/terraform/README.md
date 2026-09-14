# infra/terraform — PetClinic 3-Tier on AWS (1팀 Mission Critical)

`docs/architecture-tiered-detail.drawio` 최종 구조를 코드로 옮긴 것. **plan/apply 전 단계** — 현재는 `fmt`·`validate`만 통과한 상태.

## 구성 (파일 = 계층)

| 파일 | 계층 | 내용 |
|---|---|---|
| `edge.tf` | ① 진입 | Route 53 별칭, ACM(us-east-1 · 서울), WAF(관리형 3 + rate 2 + 부하기 허용), CloudFront(Behavior 4 · OAC · 오리진 그룹 failover) |
| `alb.tf` | ② WEB · ③ WAS | Public ALB 443(X-Origin-Verify 규칙 · 80→443), tg-web `/health.html`, Internal ALB 8080, tg-was `/petclinic/` + sticky |
| `compute.tf` `user_data/` | ② ③ | 시작 템플릿(IMDSv2), ASG WEB(CPU 60%) · WAS(대상당 요청 수 + CPU + 예약 증설 + 종료 훅) |
| `rds.tf` | ④ DB | RDS MySQL 8.0 Multi-AZ(관리형 비밀 · `require_secure_transport`), RDS Proxy(Require TLS), AWS Backup 일일 |
| `cognito.tf` | ① / ③ | 사용자 풀 · 그룹 vets/admins · 앱 클라이언트 · OIDC 설정 Secrets |
| `kms_s3.tf` | 공통 | CMK, 버킷 4개(images · maintenance · logs · cloudtrail), OAC 버킷 정책, Lifecycle |
| `observability.tf` `lambda/` | ⑤ 운영 | 로그 그룹, 알람 3 + 예약 폭주, SNS → Chatbot, 예약 알림 Lambda(구독 필터), CloudTrail, SSM 세션 설정, Managed Grafana(선택) |
| `network.tf` `security.tf` `iam.tf` | 기반 | VPC · 서브넷 8 · NAT 2 · 라우팅, SG 체인, EC2/RDS Proxy 역할 |

## 이름 · 태그 규칙

- 이름: `mc-<계층>-<az>` (예 `mc-web-a`, `mc-asg-was`, `sg-was`, `mc-tg-web`)
- 공통 태그(`provider default_tags`): `Project=petclinic-3tier`, `Team=mc-1`, `Owner=<이름>`, `Env=lab`, `ManagedBy=terraform`
- 계층 태그: `Tier=edge|web|was|db|ops`, RDS에 `Data=pii`

## 검증만 (AWS에 아무것도 만들지 않음)

```bash
cd infra/terraform
terraform fmt -check -recursive
terraform init -backend=false
terraform validate
```

## 실제 배포 전 준비 (plan 이전)

1. `terraform.tfvars.example` → `terraform.tfvars` (AMI ID 2개, 도메인, Owner, origin_verify_secret)
2. Route 53 호스팅 존이 이미 있어야 함(`hosted_zone_name`)
3. 골든 AMI: WEB(httpd · CloudWatch Agent 설정), WAS(Corretto 17 · Tomcat 9.0.121 · petclinic.war · aws cli · jq · CloudWatch Agent)
4. Secrets `mc/slack-webhook-reservations` 값은 apply 후 콘솔에서 수동 입력
5. AWS Chatbot: 콘솔에서 Slack 워크스페이스 연결 후 `slack_team_id` · 채널 ID 입력
6. 원격 상태(S3 + DynamoDB) 활성화 후 `terraform plan`

## 앱 쪽 전제 (코드 변경)

- Spring Security OAuth2 Client(Cognito issuer) — `-Doauth.cognito.*` 시스템 속성 사용
- 예약 등록 시 `RESERVATION_CREATED id= vet= time= owner_id= pet=` 로그 1줄 → `/opt/tomcat/logs/events.log` → CloudWatch Agent → `/mc/was/events`
- Tomcat `RemoteIpValve`(x-forwarded-proto) — HTTPS 콜백 URL 생성
