# infra/terraform — PetClinic 3-Tier on AWS (1팀 Mission Critical)

`docs/architecture-tiered-detail.drawio` 최종 구조를 코드로 옮긴 것. **9/14 apply 완료** — 계정 528821350786(IAM 사용자 `mc-deploy`), 리전 ap-northeast-2, state 리소스 175개.

## 배포 결과 (9/14)

| 항목 | 값 |
|---|---|
| 서비스 URL | https://petclinic.mission-critical.site/petclinic/ (`/petclinic/*`는 Cognito 로그인 필요) |
| 공개 확인 | `/health.html` · `/` → 200 (인증 없음) |
| CloudFront | `d1zuqmc7aabioo.cloudfront.net` (WAF Web ACL · ACM us-east-1 부착) |
| Route 53 존 | `mission-critical.site` — 가비아 네임서버를 아래 NS 4개로 변경 완료 |
| Public ALB | `mc-alb-public-1647467264.ap-northeast-2.elb.amazonaws.com` (443만, ACM 서울, authenticate-cognito) |
| Internal ALB | `internal-mc-alb-internal-526016631.ap-northeast-2.elb.amazonaws.com` (8080, sticky) |
| RDS Proxy | `mc-rds-proxy.proxy-c7ku4mw88shn.ap-northeast-2.rds.amazonaws.com` |
| Cognito | 풀 `ap-northeast-2_WiGQeZwfg`, Hosted UI `mc-hospital-528821350786.auth.ap-northeast-2.amazoncognito.com` |
| 버킷 | `mc-images-…` · `mc-maintenance-…` · `mc-logs-…` · `mc-cloudtrail-…` (접미사 = 계정 ID) |
| SNS | `mc-alerts` (이메일·Chatbot 구독은 tfvars에서 추가) |
| Lambda | `mc-notify-reservation` (Slack webhook 값은 Secrets `mc/slack-webhook-reservations`에 수동 입력) |

NS: `ns-1495.awsdns-58.org` · `ns-1538.awsdns-00.co.uk` · `ns-177.awsdns-22.com` · `ns-929.awsdns-52.net`

### apply 중 겪은 제약과 수정 (케이스북)

| 증상 | 원인 | 조치 |
|---|---|---|
| CloudFront 생성 400 `AllowedMethods cannot include POST … origin group` | 오리진 그룹은 GET·HEAD Behavior에만 허용 | 기본 Behavior는 ALB 직접, 점검 페이지는 `custom_error_response`(502·503·504 → /maintenance.html) |
| SG 규칙 `RulesPerSecurityGroupLimitExceeded` | CloudFront 관리형 접두사 목록은 항목 수만큼 규칙으로 계산 | Public ALB 80 인바운드·리스너 제거(443만) |
| RDS `Performance Insights not supported` | db.t3.small(MySQL)은 PI 미지원 | `performance_insights_enabled = false` |
| Lambda `ReservedConcurrentExecutions … below minimum` | 새 계정 동시 실행 한도 | 예약 동시성 제거 |
| ACM 검증 22분 대기 | 가비아 NS 전파 | 정상(전파 후 자동 통과) |
| WAS `Remote branch chore/stack-update-2026 not found` | 스택 업데이트가 `test` 브랜치에 있음 | `app_repo_branch = "test"` |
| WAS `GetSecretValue AccessDenied` (rds!db-…) | EC2 역할에 RDS 관리형 비밀 권한 누락 | `iam.tf` ec2_inline에 secret ARN 추가 |
| WAS `aws: unbound variable` | CloudWatch 설정 heredoc의 `${aws:…}`가 `set -u`에 걸림 | `<<'CW'` 인용 + `$${` 이스케이프 |
| WAS `wro4j … Could not resolve version conflict (minimatch)` | jshint 웹자 의존성 범위 충돌 | pom에서 `wro4j-extensions`의 jshint 제외(프로세서 미사용). Corretto 17로 빌드 검증 |
| Tomcat `catalina.sh: eval … exec` 실패 | `setenv.sh`의 CATALINA_OPTS에 작은따옴표 | 따옴표 제거, 배열 인용 방식으로 |
| JDBC URL의 `&`가 XML 속성에서 깨짐 | `datasource-config.xml` 속성 필터링 | URL·비밀번호를 XML 이스케이프(`&amp;`) |

### 인증 방식 (최종)
Spring Security OAuth2 Client는 앱 작업 부담으로 로드맵. **Public ALB 리스너 규칙**이 `/petclinic/*`를 Cognito Hosted UI로 보내고 콜백 `/oauth2/idpresponse`를 ALB가 처리(세션 8h). 앱 수정 없음. 사용자 생성:
```bash
aws cognito-idp admin-create-user --user-pool-id ap-northeast-2_WiGQeZwfg --username vet1@example.com \
  --user-attributes Name=email,Value=vet1@example.com Name=email_verified,Value=true --profile mc-deploy
aws cognito-idp admin-add-user-to-group --user-pool-id ap-northeast-2_WiGQeZwfg --username vet1@example.com --group-name vets --profile mc-deploy
```

### 자격증명 메모
Terraform AWS 프로바이더는 `aws login` 세션을 직접 읽지 못한다 → `~/.aws/config`에 `credential_process = aws configure export-credentials --profile mc-deploy --format process`인 프로필 `mc-deploy-tf`를 두고 `AWS_PROFILE=mc-deploy-tf`로 실행.

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
3. 골든 AMI: WEB(httpd · CloudWatch Agent 설정), WAS(OpenJDK 8 = java-1.8.0-amazon-corretto · Tomcat 9.0.121 · petclinic.war · aws cli · jq · CloudWatch Agent)
4. Secrets `mc/slack-webhook-reservations` 값은 apply 후 콘솔에서 수동 입력
5. AWS Chatbot: 콘솔에서 Slack 워크스페이스 연결 후 `slack_team_id` · 채널 ID 입력
6. 원격 상태(S3 + DynamoDB) 활성화 후 `terraform plan`

## 앱 쪽 전제 (코드 변경)

- 예약 등록 시 `RESERVATION_CREATED id= vet= time= owner_id= pet=` 로그 1줄 → `/opt/tomcat/logs/events.log` → CloudWatch Agent → `/mc/was/events`
- 로그인은 ALB가 처리하므로 앱 변경 없음. ALB가 `x-amzn-oidc-data` 헤더로 사용자 정보를 전달
