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

create_base 모드의 WAS 는 부팅 시 RDS Proxy 엔드포인트(TLS)로 `mvnw -P MySQL -Djdbc.*` 빌드 → 도면 ④ 경로가 처음부터 적용. CloudWatch Agent 도 SSM 파라미터(`/petclinic/cwagent/web|was`)로 설정. Apache 첫 화면은 `base.web_index_branch` 브랜치의 `src/main/webapp/index.html` + `resources/`·`images/` 를 `/var/www/html/{index.html,static/}` 로 복사해 직접 서빙(자산 링크는 `/static/…`, 앱 링크는 `/petclinic/…` 로 치환 · `/static/*` 은 CloudFront 캐시). Blue(main) WAR 에는 리디자인 자산이 없으므로 랜딩 페이지 자산을 WAS 에 의존시키지 않는다. 그 브랜치에 index.html 이 없으면(main=Blue) `/` → 302 `/petclinic/` 폴백.
랜딩 자산(`/static/*`·`/images/*`)은 9/16 저녁부터 S3 mc-static(OAC) 오리진이 서빙(아래 절). 설계 경로가 CloudFront → 443 이라 Public ALB 80 리스너는 기본 없음 — NS 위임 전 ALB DNS 로 직접 확인하려면 `base.public_http_listener = true`.

## 무엇을 건드리고 무엇을 안 건드리나

| 구분 | 리소스 | 코드에서 |
|---|---|---|
| 그대로 (읽기만) | `test-vpc` · 서브넷 8 · NAT · IGW · `test-Public-ALB` · `alb-internal-test` · `Targetgroup-web` · `tg-internal-alb` · SG 5개 · `mc-ec2-role` · WEB ASG `web-test`(AMI `web-appache`) · `WAS-test-a` · `bas-server` | `existing.tf` data 소스. 이름은 `var.existing` |
| 편입 (import) | RDS `database-1` (MySQL 8.0.44 · db.t3.small · Multi-AZ · 200GB gp3) | `imports.tf` + `rds.tf` — 파라미터 그룹(TLS 강제·utf8mb4) · 백업 7일(PITR) · 삭제 방지만 바뀜 |
| 신규 ① | Route 53 존 · ACM ×2(us-east-1·서울) · WAF(관리형 3 + rate 2 · `enable_waf`) · CloudFront(Behavior 3 · 5xx→점검 페이지) · S3 점검 페이지(OAC) · **기존 Public ALB 에 443 리스너 + X-Origin-Verify 규칙** · alb-public-sg 에 CloudFront 프리픽스 443 규칙 | `edge.tf` `alb.tf` `security.tf` |
| 신규 ④ | RDS Proxy(TLS·Secrets 인증) + SG · petclinic-db-sg 에 Proxy 3306 규칙 · AWS Backup 볼트/계획 | `rds.tf` `security.tf` |
| 신규 ⑤ | KMS CMK · S3 로그/CloudTrail 버킷 · CloudWatch Logs 6 · CW Agent 설정(SSM 파라미터) · 알람 3 → SNS · CloudTrail · SSM 세션 설정 · Grafana(선택) · mc-ec2-role 인라인 정책 | `kms_s3.tf` `observability.tf` `iam.tf` |
| 수동 후속 | 가비아 NS · ALB 액세스 로그 · 인스턴스 프로파일 부착 · CW Agent 설치 · WAS JDBC → Proxy 재빌드 · 80 리스너/0.0.0.0/0 정리 · RDS 재부팅 | output `manual_followups` · [MANUAL-FOLLOWUPS.md](MANUAL-FOLLOWUPS.md) · 도면 `docs/architecture-kdt5-terraform.drawio` |

왜 WEB·WAS 를 코드로 안 만드나: 팀이 콘솔로 AMI(`web-appache`)·ASG(`web-test`)·WAS 를 이미 만들었고 "WEB·WAS 는 그대로" 결정. Terraform 이 이를 다시 만들면 두 벌이 되거나 교체된다. 대신 **경계(ALB 리스너 · SG 규칙 · IAM 인라인 · 알람 차원)** 만 코드가 붙인다.

## 9/16 멘토링 반영
- `enable_waf`(기본 **true** · 9/16 저녁 팀 결정으로 **유지**): CloudFront 에 붙는 Web ACL(allow-loadgen → 관리형 3 → rate-all 2,000/5분 → rate-booking `/visits/new` 100/5분) + 로그 → CloudWatch Logs `aws-waf-logs-mc`(us-east-1). 멘토링의 '관리 어려움' 의견은 기록만. 끄려면 `enable_waf = false`(Web ACL·IP set·로그 그룹 삭제 — CloudFront 에서 먼저 떼야 해서 `update-distribution --web-acl-id ""` 뒤 apply).
- Phase 3 부하 실험 전 `loadgen_cidrs` 에 JMeter IP 를 넣지 않으면 rate-all 이 발생기를 차단한다.
- Bastion 옵션·EFS 설계는 `docs/notion-mentoring-followup.md` 참고.

## ASG · AMI (`base.enable_asg` · `base.web_ami_id` / `was_ami_id` · `base.db_init_mode`) — Notion 'AMI & Auto Scaling' · 'was' 반영
기본은 **고정 EC2 2대**(도면의 회색 'Auto Scaling (로드맵)' 상태). 켜는 순서:

| 단계 | 값 | 무슨 일 |
|---|---|---|
| 0 (현재) | `enable_asg=false` | `aws_instance` 2+2 · 대상 그룹에 직접 등록 |
| 1 AMI 굽기(선택) | 콘솔: 현재 `mc-was-a` 에서 이미지 생성 → `was_ami_id = "ami-…"` (WEB 도 동일) | was.sh 가 Tomcat 다운로드·git clone 을 건너뛰고 WAR 만 다시 빌드(~/.m2 캐시). 부팅 5~8분 → 1~2분. **WAR 에 Proxy 주소·앱 비밀이 박히므로 계정·비밀이 바뀌면 다시 굽기** |
| 2 ASG 켜기 | `enable_asg=true` (+ `web_asg`/`was_asg` min 2 · max 4 · desired 2 · CPU 60% · WAS 는 대상당 요청 300 추가) | 고정 EC2 0대 → 시작 템플릿(`$Latest`) + ASG(`mc-asg-web/was`) 생성. 템플릿을 고치면 `instance_refresh`(Rolling · 50% 유지)가 교체. WAS 종료 훅 300s: `mc-lifecycle-watch` 가 마지막 로그를 `s3://mc-logs/was/<instance-id>/` 로 sync 후 CONTINUE |
| 2' DB 초기화 | `db_init_mode="userdata"` (ASG 권장) | Notion 'was' 의 우려(동시 부팅 시 schema 경합)에 대한 답. 우리 앱은 Spring Boot 가 아니라 XML `jdbc:initialize-database` 이고 MySQL 스크립트가 `CREATE TABLE IF NOT EXISTS`·`INSERT IGNORE` 라 **현재(app 모드)도 멱등** — 9/16 롤링 교체·동시 부팅에서 실측 문제 없음. `userdata` 는 한 단계 더: was.sh 가 앱 사용자로 `GET_LOCK('mc_db_init')` 아래에서 1회 실행하고 Spring 초기화는 `-Djdbc.initLocation`(datasource-config.xml 이 `system-properties-mode="OVERRIDE"`)으로 빈 스크립트로 돌림. Java 0줄 |

**교훈(9/16 저녁 실측)**: `-target=module.base[0].aws_lb_target_group_attachment.web[0]` 처럼 인스턴스 하나만 겨냥해도 Terraform 은 의존성을 **리소스 단위**(`aws_instance.web` 전체)로 넓혀서 4대를 한 번에 교체했다(약 3분 WEB · 6분 WAS 동안 서비스 중단). 고정 EC2 를 롤링하려면 `-target` 이 아니라 **한 대씩 `terraform taint`/`-replace="module.base[0].aws_instance.web[0]"` 로 교체**해야 한다. 또 count 로 바뀐 리소스(예: `aws_ssm_document.session_prefs`)가 plan 에 있으면 `-target` 세트에 그것도 넣어야 한다.

주의: `user_data_replace_on_change = true` 라 was.sh 템플릿이 바뀌면 고정 EC2 는 **교체**된다(템플릿 기본 렌더링은 byte-identical 하게 유지 — `enable_asg`·`baked`·`db_init_mode` 블록은 켤 때만 나옴). 교체는 AZ-a → AZ-c 순으로 `-target` 롤링.

## 운영자 접속 = Bastion (팀 결정 9/16 저녁 · SSM Session Manager 는 안 씀)
| 항목 | 값 |
|---|---|
| 스위치 | `base.create_bastion`(기본 true) · `enable_ssm`(기본 **false**: Session Manager 문서 · `/petclinic/ssm/sessions` · `AmazonSSMManagedInstanceCore` 제거. Parameter Store 로 CW Agent 설정을 받는 건 그대로) |
| 위치 | 퍼블릭 서브넷 A · `t3.micro` · EIP · SG `mc-sg-bastion` 22 ← **`base.bastion_allowed_cidrs`(운영자 공인 IP /32)만**. 팀원은 tfvars 에 `/32` 추가 후 apply |
| 키 | `base.ssh_key_name` 이 비면 ED25519 키 페어 `mc-ssh` 를 만들고 개인키를 `.keys/mc-ssh.pem`(0600 · gitignore)에 저장. 같은 키가 Bastion·WEB·WAS(·시작 템플릿)에 붙음 → `key_name` 변경이라 **고정 EC2 4대는 교체**(AZ-a → AZ-c 롤링) |
| 접속 | `ssh -i .keys/mc-ssh.pem ec2-user@<bastion_public_ip>` · WEB/WAS: `ssh -i .keys/mc-ssh.pem -J ec2-user@<bastion> ec2-user@10.0.2x.x` (SG: web/was 22 ← Bastion SG) · DB: Bastion 에서 `mysql --ssl -h <rds_proxy_endpoint> -u petclinic_app -p` (SG: rds-proxy 3306 ← Bastion SG) — output `bastion` 에 명령이 그대로 나옴 |
| 로그 | `/var/log/secure`(sshd 로그인 성공·실패) → CloudWatch Agent → `/petclinic/bastion/secure` 90일 |

## 정적 자산 S3 (`mc-static-<계정>` · OAC)
`/static/*`(랜딩 페이지 css·이미지) · `/images/*`(hero 영상)은 CloudFront → **S3 mc-static** (OAC · SSE-KMS · 공개 차단). Apache 를 거치지 않는다. 내용은 저장소 `src/main/webapp/resources`·`images` 를 `aws_s3_object`(23개 · `.less` 제외 · `source_hash`)가 apply 때 동기화하므로 **자산을 바꾸면 apply + invalidation** (`/static/*` `/images/*`). `/images/*` 는 같은 버킷의 두 번째 오리진(`origin_path = /static`)이라 키는 `static/images/…` 하나만 둔다. WAR 안의 `/petclinic/resources/*` 는 여전히 ALB(Tomcat) 캐시.

## DB 로그 → CloudWatch Logs · CloudWatch Logs → S3 장기 보관 (9/17 · `logs_archive.tf`)
도면에서 DB 계층만 로그 화살표가 없었고, CloudWatch Logs → S3 도 없었다. 둘 다 실제로 만든다.
| 무엇 | 어떻게 | 확인 |
|---|---|---|
| RDS error · **slowquery** → CloudWatch Logs | `enabled_cloudwatch_logs_exports = ["error","slowquery"]` + 파라미터 그룹 `slow_query_log=1` · `long_query_time=2`(동적 · 재부팅 없음). 그룹 `/aws/rds/instance/mc-petclinic/{error,slowquery}` 는 이름이 고정이라 **우리가 먼저 만들어** 보존 30일 · KMS 를 건다(이미 자동 생성된 error · Proxy 그룹은 `imports.tf` 로 편입 — 없으면 `existing_rds_log_groups` 에서 키를 뺌) | `aws logs tail /aws/rds/instance/mc-petclinic/slowquery` |
| RDS Proxy → CloudWatch Logs | Proxy 가 스스로 `/aws/rds/proxy/mc-rds-proxy` 에 씀 → 편입해 보존·KMS | `describe-log-groups --log-group-name-prefix /aws/rds` |
| **CloudWatch Logs → S3 사본** | 로그 그룹마다 구독 필터(필터 없음) → **Kinesis Data Firehose**(계층당 1개: `mc-cwlogs-web/was/bastion/db`) → `s3://mc-logs/cwlogs/<tier>/yyyy/MM/dd/` gzip · 5분 버퍼 · 1년 보관. 레코드는 Firehose 가 gzip 을 풀어 줄 단위 JSON(logGroup · logStream · logEvents)으로 저장 → Athena 로 바로 조회. WAF 로그는 us-east-1 이라 제외 | `aws s3 ls s3://mc-logs-528821350786/cwlogs/db/ --recursive` (첫 객체는 로그 발생 후 ≤5분) |

왜 Firehose 인가: CloudWatch Logs 는 자체 저장소라 S3 에 "저장"되지 않는다. S3 사본은 (a) 내보내기 작업(수동·느림), (b) 구독 → Firehose(실시간 · 관리형), (c) 구독 → Lambda 중 (b) 가 운영 부담이 가장 적다. 비용은 GB 당 몇 십 원 수준(우리 로그 양 MB 단위).

## 9/18 도면 최종본 대조 (apply 전 · 코드만)
팀 최종 도면(`0917 아키텍쳐 다이어그램 최종본`)은 저장소 `docs/architecture-current-tiered-v2.drawio` 0번 탭과 동일. WAS → CloudWatch Logs 화살표는 Agent(`/petclinic/cwagent/was` → catalina·access·gc)로 이미 구현돼 있어 코드 변경 없음. 도면과 어긋나 있던 두 가지를 코드로 맞춤:
| 도면 | 전엔 | 지금 코드 | apply 하면 |
|---|---|---|---|
| KMS → Secrets Manager 화살표 | app-db 비밀이 AWS 관리형 키(aws/secretsmanager) | `aws_secretsmanager_secret.app_db` 에 `kms_key_id = mc-cmk` + EC2·Proxy 역할 `kms:Decrypt` 에 mc-cmk 추가(ViaService 조건 유지) | 비밀·정책 in-place. **기존 버전은 옛 키로 남고 새 버전부터 mc-cmk** — 지금 값을 바꿀 일이 없으니 실효는 다음 비밀 갱신 때. admin(RDS 관리형) 비밀은 그대로 |
| WEB → CloudWatch Logs (Agent · access·error) | httpd.conf 기본 `CustomLog "logs/access_log" combined` 이 같은 파일에 필터 없이 또 써서 **헬스체크가 그대로 남고(최근 2000줄 전부 ELB-HealthChecker) 일반 요청은 2줄**(9/18 web-c 실측 `?dup=1` → 2줄) | web.sh 가 기본 CustomLog 를 주석 처리 → petclinic.conf 의 `env=!nolog` 하나만 | `user_data_replace_on_change` 라 **WEB 2대 교체** — `-replace="module.base[0].aws_instance.web[0]"` → healthy 확인 → `[1]` 순으로(위 교훈). 교체 전까지는 두 서버에서 같은 sed 를 수동 실행해도 됨 |

## 9/18 Q&A 반영 — VPC 엔드포인트 · EBS 키 (옵션 · 기본 끔 = 지금 구성 그대로)
| 스위치 | 기본 | 켜면 | 왜 옵션인가 |
|---|---|---|---|
| `base.enable_vpc_endpoints` | false | 인터페이스 `secretsmanager` · `logs` · `ssm`(web 서브넷 AZ 2 · SG 443 ← web/was/bastion · 사설 DNS) + **S3 게이트웨이**(무료, private·db 라우팅 테이블) | 서버의 AWS API 호출(비밀 조회·로그 전송·Agent 설정)이 공용망을 안 탄다. 단 NAT 는 못 없앰(dnf·git·Maven·Tomcat) · ≈$48/월 → 규제·감사 요구 시 |
| `base.ebs_kms_key_arn` | `""` = aws/ebs | `"mc-cmk"` 또는 키 ARN → WEB·WAS·Bastion·시작 템플릿 루트 볼륨을 고객 관리형 키로 | **기존 인스턴스는 볼륨 교체(replace)** — 신규 구축·ASG 새로 고침 때만. ASG 와 같이 켜면 키 정책에 Auto Scaling 서비스 연결 역할 문장이 자동 추가 |
| `enable_ebs_default_encryption` | false | 계정(리전) EBS 기본 암호화 켬 (+ mc-cmk 면 기본 키 지정) | 계정 전체 설정이라 팀 결정 후. 실수로 암호화 안 켠 볼륨 방지 |
지금 상태: 루트 볼륨 전부 `encrypted=true`(aws/ebs) · 엔드포인트 없음(AWS API 는 NAT 경유 TLS). 발표 답: "개인정보는 RDS 에만, EBS 는 저장 암호화, DB 전송 TLS 강제. CMK 통일·엔드포인트는 로드맵".

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
