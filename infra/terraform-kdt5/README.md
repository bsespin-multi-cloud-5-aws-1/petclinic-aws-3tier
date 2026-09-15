# infra/terraform-kdt5 — 콘솔 구축본(WEB·WAS) 은 그대로, 나머지 도면 계층을 코드로 (+ 빈 계정용 create_base 모드)

`docs/architecture-tiered-tabs.drawio` 의 ①~⑤ 계층 중 **② WEB · ③ WAS 는 kdt5 계정에 콘솔로 만든 것을 그대로 두고**,
그 주변(① 진입 계층 · ④ DB 보강 · ⑤ 운영 계층)만 Terraform 으로 만든다. **코드만 작성 — apply 하지 않음** (validate · plan 만 통과).

## 두 가지 모드 (`create_base`)

| | `create_base = false` (기본 · kdt5) | `create_base = true` (mc-deploy 같은 빈 계정) |
|---|---|---|
| VPC·서브넷·NAT·IGW · SG 체인 · IAM 역할 · Public/Internal ALB · WEB·WAS | 콘솔 구축본을 `data` 로 읽기만 (`var.existing` 이름) | `modules/base` 가 생성 (VPC 10.0.0.0/16 · SG 6 · `mc-ec2-role` · ALB 2 · WEB ×2 · WAS ×2 · DB 서브넷 그룹) |
| RDS | `database-1` **import** → 파라미터 그룹·백업·삭제 방지만 변경 | `mc-petclinic` 신규 (tfvars 로 8.4 · 20GB 등) |
| ① 진입 · ④ Proxy/Backup · ⑤ 운영 | 동일 코드 | 동일 코드 |
| 수동 후속 | ⓜ1~7 (`MANUAL-FOLLOWUPS.md`) | ⓜ1(가비아 NS) 만 — 나머지는 user_data 가 처리 |
| plan 결과 (2026-09-15 확인) | `1 to import, 67 to add, 1 to change` (database-1 in-place: parameter_group · backup 7 · deletion_protection · copy_tags · tags) | `127 to add` (module.base 59 + 68) |
| tfvars 예시 | `terraform.tfvars.example` | `terraform.tfvars.mc-deploy.example` |

create_base 모드의 WAS 는 부팅 시 RDS Proxy 엔드포인트(TLS)로 `mvnw -P MySQL -Djdbc.*` 빌드 → 도면 ④ 경로가 처음부터 적용. CloudWatch Agent 도 SSM 파라미터(`/mc/cwagent/web|was`)로 설정. Apache 첫 화면은 `base.web_index_branch` 브랜치의 `src/main/webapp/index.html` 을 복사해 직접 서빙(자산·앱 링크는 `/petclinic/…` 절대 경로로 치환, `/petclinic/images/*` 도 CloudFront 캐시). 그 브랜치에 index.html 이 없으면(main=Blue) `/` → 302 `/petclinic/` 폴백.
설계 경로가 CloudFront → 443 이라 Public ALB 80 리스너는 기본 없음 — NS 위임 전 ALB DNS 로 직접 확인하려면 `base.public_http_listener = true`.

## 무엇을 건드리고 무엇을 안 건드리나

| 구분 | 리소스 | 코드에서 |
|---|---|---|
| 그대로 (읽기만) | `test-vpc` · 서브넷 8 · NAT · IGW · `test-Public-ALB` · `alb-internal-test` · `Targetgroup-web` · `tg-internal-alb` · SG 5개 · `mc-ec2-role` · WEB ASG `web-test`(AMI `web-appache`) · `WAS-test-a` · `bas-server` | `existing.tf` data 소스. 이름은 `var.existing` |
| 편입 (import) | RDS `database-1` (MySQL 8.0.44 · db.t3.small · Multi-AZ · 200GB gp3) | `imports.tf` + `rds.tf` — 파라미터 그룹(TLS 강제·utf8mb4) · 백업 7일(PITR) · 삭제 방지만 바뀜 |
| 신규 ① | Route 53 존 · ACM ×2(us-east-1·서울) · WAF(관리형 3 + rate 2) · CloudFront(Behavior 3 · 5xx→점검 페이지) · S3 점검 페이지(OAC) · **기존 Public ALB 에 443 리스너 + X-Origin-Verify 규칙** · alb-public-sg 에 CloudFront 프리픽스 443 규칙 | `edge.tf` `alb.tf` `security.tf` |
| 신규 ④ | RDS Proxy(TLS·Secrets 인증) + SG · petclinic-db-sg 에 Proxy 3306 규칙 · AWS Backup 볼트/계획 | `rds.tf` `security.tf` |
| 신규 ⑤ | KMS CMK · S3 로그/CloudTrail 버킷 · CloudWatch Logs 6 · CW Agent 설정(SSM 파라미터) · 알람 3 → SNS · CloudTrail · SSM 세션 설정 · Grafana(선택) · mc-ec2-role 인라인 정책 | `kms_s3.tf` `observability.tf` `iam.tf` |
| 수동 후속 | 가비아 NS · ALB 액세스 로그 · 인스턴스 프로파일 부착 · CW Agent 설치 · WAS JDBC → Proxy 재빌드 · 80 리스너/0.0.0.0/0 정리 · RDS 재부팅 | output `manual_followups` · [MANUAL-FOLLOWUPS.md](MANUAL-FOLLOWUPS.md) · 도면 `docs/architecture-kdt5-terraform.drawio` |

왜 WEB·WAS 를 코드로 안 만드나: 팀이 콘솔로 AMI(`web-appache`)·ASG(`web-test`)·WAS 를 이미 만들었고 "WEB·WAS 는 그대로" 결정. Terraform 이 이를 다시 만들면 두 벌이 되거나 교체된다. 대신 **경계(ALB 리스너 · SG 규칙 · IAM 인라인 · 알람 차원)** 만 코드가 붙인다.

## 검증 (적용 없이)
```bash
cd infra/terraform-kdt5
terraform init -backend=false
terraform validate
```
`terraform plan` 은 계정 조회가 필요하다. `aws login` 세션은 프로바이더가 못 읽으므로 `~/.aws/config` 에 credential_process 프로필을 두고 `aws_profile` 로 지정:
```
[profile kdt5-tf]
region = ap-northeast-2
credential_process = aws configure export-credentials --profile kdt5 --format process

[profile mc-deploy-tf]
region = ap-northeast-2
credential_process = aws configure export-credentials --profile mc-deploy --format process
```
```bash
# kdt5
cp terraform.tfvars.example terraform.tfvars              # aws_profile=kdt5-tf · domain · origin_verify_secret
# mc-deploy
cp terraform.tfvars.mc-deploy.example terraform.tfvars    # aws_profile=mc-deploy-tf · create_base=true
terraform init && terraform plan                          # 읽기 전용
```
kdt5 모드 plan 에서 `aws_db_instance.main` 은 **update in-place** 로 parameter_group_name · backup_retention_period · deletion_protection · copy_tags_to_snapshot · tags 만 바뀌어야 한다. `must be replaced` 가 보이면 `var.db` 를 콘솔 값에 맞추고 절대 apply 하지 않는다.

## mc-deploy 에 apply 할 때 (팀 결정 후)
1. `terraform.tfvars` 에 `create_base = true`, `aws_profile = "mc-deploy-tf"`.
2. `terraform apply` → Route 53 존이 먼저 생기고 ACM 검증에서 대기 → **그때 가비아 네임서버를 output `route53_name_servers` 로 교체**(ⓜ1). 검증 완료 후 CloudFront·ALB 443 이 이어서 생성. 전체 25~30분(RDS Multi-AZ · Proxy · CloudFront · WAS 빌드).
3. 확인: `https://<domain_name>/petclinic/` → WAS 홈. WAS `/var/log/mc-userdata.log` 에 `vets` 건수(Proxy·TLS 경유 DB 확인).
4. 정리: `terraform destroy` (버킷 force_destroy · RDS skip_final_snapshot=true · deletion_protection=false 로 예시 tfvars 설정됨).

## MySQL 8.0 → 8.4
`database-1` 은 8.0.44 (8.0 표준 지원 종료 2026-07-31). 8.4 는 메이저 업그레이드 → `db.engine_version = "8.4.x"` + `allow_major_version_upgrade = true` + 파라미터 그룹 family 자동 변경(`local.db_family`) · 사전 스냅샷. Phase 2 항목.

## 다른 코드와의 관계
- `infra/terraform/` — 전부 새로 만드는 최종 설계(ASG·CloudFront·Proxy 포함). 새 계정에 처음부터 올릴 때.
- `infra/terraform-phase1/` — kdt5 구축본을 EC2 ×2 로 재현 + RDS. 콘솔 없이 Phase 1 Blue 를 재현할 때.
- `infra/terraform-kdt5/` (이 폴더) — kdt5 구축본을 살리고 도면의 나머지 계층을 얹을 때.
