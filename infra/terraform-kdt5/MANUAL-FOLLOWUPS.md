# 수동 후속 ⓜ1~7 — 코드가 건드리지 않는 기존 리소스(WEB·WAS·ALB·RDS 재부팅)에서 콘솔로 할 일

`terraform apply` 뒤 `terraform output manual_followups` 와 같은 목록. 도면: `docs/architecture-kdt5-terraform.drawio` 의 노란 배지.
순서가 중요한 것: **ⓜ1 은 apply 도중**(ACM DNS 검증이 NS 위임을 기다림), **ⓜ5 → ⓜ7 순서**(TLS 강제 재부팅 전에 WAS 가 Proxy·TLS 로 붙어 있어야 함), **ⓜ6 은 CloudFront 로 접속 확인 뒤**.

| # | 어디서 | 무엇을 | 왜 |
|---|---|---|---|
| ⓜ1 | 가비아 My가비아 → 도메인 관리 → 네임서버 설정 | `terraform output route53_name_servers` 의 NS 4개로 교체. `dig NS mission-critical.site` 로 전파 확인 | Route 53 존은 코드가 새로 만들므로, 등록기관이 그 존을 가리켜야 ACM 검증 CNAME·A 레코드가 유효. apply 는 검증 완료까지 대기(최대 수십 분) |
| ⓜ2 | EC2 → 로드밸런서 → `test-Public-ALB` → 속성 → 편집 → 모니터링 → 액세스 로그 | 켜기 → S3 URI `s3://mc-logs-723165663216/alb/public`. `alb-internal-test` 도 같은 방식으로 `/alb/internal` | 버킷·전송 정책은 코드가 만들었지만 ALB 속성은 ALB 를 코드가 관리하지 않아 콘솔. 로그 5종 중 "ALB 액세스" 항목 |
| ⓜ3 | EC2 → 시작 템플릿 `web` → 작업 → 템플릿 수정(새 버전) → 고급 세부 정보 → IAM 인스턴스 프로파일 `mc-ec2-role` → 생성 후 ASG `web-test` 의 기본 버전을 새 버전으로 → 인스턴스 새로 고침(최소 정상 50%). `WAS-test-a`: 인스턴스 → 작업 → 보안 → IAM 역할 수정 → `mc-ec2-role` | 프로파일 부착 | SSM 접속·CloudWatch Agent·Secrets 조회(코드의 `mc-ec2-inline`)는 인스턴스 프로파일로만 전달. 현재 kdt5 인스턴스 6대 모두 미부착 |
| ⓜ4 | `web-ami`(AMI 빌더)와 `WAS-test-a` 에 SSM 세션(ⓜ3 뒤) 또는 bastion 으로 접속 | `sudo dnf install -y amazon-cloudwatch-agent` → `sudo /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl -a fetch-config -m ec2 -c ssm:/mc/cwagent/web -s` (WAS 는 `ssm:/mc/cwagent/was`) → WEB 은 AMI `web-appache` v2 생성 → 시작 템플릿 새 버전 → 인스턴스 새로 고침 | 로그가 인스턴스 밖(CloudWatch Logs `/mc/web·/mc/was`)에 있어야 ASG 축소·교체 뒤에도 남음. 설정 JSON 은 코드가 SSM 파라미터로 배포 |
| ⓜ5 | `WAS-test-a` | `terraform output was_jdbc_url` 값으로 재빌드: `./mvnw -q package -P MySQL -DskipTests "-Djdbc.url=<값>" "-Djdbc.username=admin" "-Djdbc.password=<Secrets Manager rds!db-… 의 password, XML 이스케이프>"` → `petclinic.war` 교체·Tomcat 재기동 → `/petclinic/test.jsp` 에서 vets 행 수·`Ssl_cipher` 확인 → 확인 뒤 EC2 → 보안 그룹 `petclinic-db-sg` 인바운드에서 `3306 ← was-instance-sg` 삭제 | 지금 WAS 는 H2 인메모리(DB 미연동). 도면 ④ 는 WAS → RDS Proxy(TLS) 경로. 파라미터 그룹 `require_secure_transport=1` 이 적용(ⓜ7)되면 TLS 없는 연결은 거부되므로 먼저 Proxy·`sslMode=REQUIRED` 로 전환. 직접 접속 규칙 삭제로 Proxy 우회 차단 |
| ⓜ6 | `https://<domain_name>/petclinic/` 이 CloudFront 로 열리는 것 확인 뒤 | EC2 → 로드밸런서 `test-Public-ALB` → 리스너 → HTTP:80 삭제. 보안 그룹 `alb-public-sg` 인바운드 → `80 0.0.0.0/0`·`443 0.0.0.0/0`·`22` 삭제(코드가 넣은 CloudFront 프리픽스 443 만 남김) | 1차 차단은 코드의 443 리스너 기본 403 + X-Origin-Verify 규칙, 2차가 SG. 80 이 남아 있으면 CloudFront 우회 경로 |
| ⓜ7 | RDS → `database-1` → 구성 탭에서 파라미터 그룹 `mc-mysql80 (pending-reboot)` 확인 → 작업 → 재부팅(Multi-AZ 라 "장애 조치와 함께 재부팅" 선택 가능, 60~120초) | 점검 시간에 재부팅 | `require_secure_transport`·`character_set_server` 는 static 파라미터라 재부팅해야 적용. 코드는 `apply_immediately=false` 라 안 하면 유지관리 창(월 13:01 UTC = 22:01 KST) 에 자동 재부팅 |

## 확인 명령
```bash
terraform output route53_name_servers                       # ⓜ1
aws elbv2 describe-load-balancer-attributes --load-balancer-arn <arn> --query 'Attributes[?starts_with(Key,`access_logs`)]'   # ⓜ2
aws ec2 describe-instances --filters Name=tag:Name,Values=ASG-Web,WAS-test-a --query 'Reservations[].Instances[].[Tags[?Key==`Name`]|[0].Value,IamInstanceProfile.Arn]' --output text   # ⓜ3
aws logs describe-log-streams --log-group-name /mc/was/catalina --query 'logStreams[].logStreamName'   # ⓜ4
curl -s https://<domain_name>/petclinic/test.jsp | grep -i -E 'ssl_cipher|vets'   # ⓜ5
aws elbv2 describe-listeners --load-balancer-arn <public-alb-arn> --query 'Listeners[].Port'   # ⓜ6 → [443]
aws rds describe-db-instances --db-instance-identifier database-1 --query 'DBInstances[0].DBParameterGroups[0]'   # ⓜ7 → in-sync
```
