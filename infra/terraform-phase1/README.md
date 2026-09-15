# infra/terraform-phase1 — Phase 1 Blue (kdt5 콘솔 구축본을 코드로)

kdt5 계정(723165663216)에 콘솔로 만든 3-Tier(WEB·WAS)를 **그대로 코드화**하고, 아직 없던 RDS까지 포함한 Phase 1 완성형.
`infra/terraform/`(최종 설계: ASG·CloudFront·WAF·Proxy 포함)과 별개로 **기본 3-Tier만** 담는다. 적용은 하지 않음(코드 검증만).

| 계층 | 리소스 | 콘솔 구축본 대응 |
|---|---|---|
| 네트워크 | VPC 10.0.0.0/16 · 서브넷 8 · IGW · NAT AZ당 1 · 라우팅 4(DB는 local만) | `test-vpc` 동일 CIDR. DB 라우팅만 수정 |
| 보안 | SG 체인 alb-public → web → alb-internal → was → rds, 22번 없음 | `was-instance-sg` 8080 0.0.0.0/0 등 정리 |
| IAM | `mc-ec2-role`(SSM · CW Agent · 비밀 읽기) | 역할만 있고 미부착이던 것을 부착 |
| WEB | AL2023 t3.small ×2, Apache 2.4 · ProxyPass → Internal ALB · health.html | `WEB-test-a` + AZ-C |
| Internal ALB | 8080 → tg-was(/petclinic/) | `alb-internal-test`(리스너 80) → 8080 통일 |
| WAS | AL2023 t3.medium ×2, OpenJDK 8 · Tomcat 9.0.53 · `main` MySQL 프로필 빌드 시 주입 · systemd | `WAS-test-a`(t3.micro · 9.0.121 · H2 · 수동 기동) |
| Public ALB | 80 → tg-web(/health.html) | `test-Public-ALB` |
| RDS | MySQL 8.4 · db.t3.small · Multi-AZ · 관리형 비밀 · 파라미터 그룹 | 미구축 |

## 검증(적용 없이)
```bash
cd infra/terraform-phase1
terraform init -backend=false
terraform validate
terraform plan -var-file=terraform.tfvars   # 읽기 전용, 리소스 생성 안 함
```

## 적용할 때(팀 결정 후)
`aws login` 세션은 프로바이더가 못 읽으므로 `~/.aws/config`에:
```
[profile kdt5-tf]
region = ap-northeast-2
credential_process = aws configure export-credentials --profile kdt5 --format process
```
`terraform apply` → 약 20분(RDS Multi-AZ 15분 + WAS 빌드 8분). 완료 후 `http://<public_alb_dns>/petclinic/`.

## Phase 2 로 갈 때 바꾸는 값
`app_repo_branch = "test"`, `tomcat_version = "9.0.121"` → WAS 재생성(user_data_replace_on_change). ASG·AMI·Blue/Green·Proxy·TLS는 `infra/terraform/` 사용.
