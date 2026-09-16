<callout icon="🧭" color="blue_bg">
	**기준**: mc-deploy(528821350786) · 서울(ap-northeast-2) · 이름 접두사 `mc-` · 2026-09-16 저녁 As-Built(WAF 유지 · Bastion · 정적 S3). 아래는 Terraform(`infra/terraform-kdt5`)이 실제로 apply 한 값을 **콘솔에서 손으로 그대로 만드는 순서**로 풀어쓴 것. 번호 ①~⑬ 은 도면 범례의 "계층별 흐름" 번호와 같다(요청이 흐르는 순서). 콘솔로 만들 때는 의존성 때문에 **0 → 8 → 9 → 6 → 7 → 4 → 5 → 1 → 2 → 3 → 10 → 11 → 12 → 13** 순서가 편하다(각 절 첫 줄 "선행").
	비밀값(X-Origin-Verify 헤더 값, DB 비밀번호, SSH 개인키)은 이 페이지에 적지 않는다 — 각자 만든 값을 두 곳에 똑같이 넣는 것이 원칙.
</callout>
<image src="file-upload://3dd50089-e090-8149-a331-00b24fe47404"></image>
<table_of_contents/>
# 구축 순서 한눈에 (의존성)
<table header-row="true" fit-page-width="true">
	<tr>
		<td>순서</td>
		<td>절</td>
		<td>만드는 것</td>
		<td>먼저 있어야 하는 것</td>
	</tr>
	<tr>
		<td>1</td>
		<td>0 기반</td>
		<td>VPC·서브넷 8·IGW·NAT 2·라우팅 4 · SG 7 · IAM 역할 3 · KMS · S3 버킷 4 · Secrets(app-db) · SSM 파라미터 3 · 로그 그룹 7</td>
		<td>계정만</td>
	</tr>
	<tr>
		<td>2</td>
		<td>⑧ RDS</td>
		<td>파라미터 그룹 mc-mysql84 · RDS mc-petclinic(Multi-AZ · 관리형 admin 비밀)</td>
		<td>DB 서브넷 그룹 · mc-sg-rds</td>
	</tr>
	<tr>
		<td>3</td>
		<td>⑨ Proxy·Backup</td>
		<td>RDS Proxy mc-rds-proxy(TLS · 비밀 2) · Backup 볼트·계획</td>
		<td>RDS · 비밀 2 · mc-rds-proxy-role</td>
	</tr>
	<tr>
		<td>4</td>
		<td>⑥ Internal ALB</td>
		<td>mc-alb-internal :8080 · mc-tg-was</td>
		<td>WAS 서브넷 · mc-sg-alb-internal</td>
	</tr>
	<tr>
		<td>5</td>
		<td>⑦ WAS ×2</td>
		<td>mc-was-a/c(Tomcat 9.0.121 · WAR 빌드 시 Proxy 주소 주입)</td>
		<td>Proxy 엔드포인트 · 비밀 2 · mc-ec2-profile · SSM 파라미터</td>
	</tr>
	<tr>
		<td>6</td>
		<td>① Route 53 존</td>
		<td>mission-critical.site 존 → 가비아 NS 교체</td>
		<td>없음 (ACM 검증이 이 존을 씀)</td>
	</tr>
	<tr>
		<td>7</td>
		<td>④ ACM 서울 + Public ALB</td>
		<td>인증서(DNS 검증) · mc-alb-public :443(기본 403 · X-Origin-Verify 규칙) · mc-tg-web</td>
		<td>존 · 퍼블릭 서브넷 · mc-sg-alb-public</td>
	</tr>
	<tr>
		<td>8</td>
		<td>⑤ WEB ×2</td>
		<td>mc-web-a/c(Apache · index.html · ProxyPass → Internal ALB)</td>
		<td>Internal ALB DNS · mc-ec2-profile</td>
	</tr>
	<tr>
		<td>9</td>
		<td>② ACM us-east-1 + WAF + CloudFront</td>
		<td>인증서 · Web ACL mc-web-acl · 배포(오리진 4 · Behavior 6) · Route 53 A/AAAA alias</td>
		<td>Public ALB DNS · S3 버킷(점검·정적) · OAC</td>
	</tr>
	<tr>
		<td>10</td>
		<td>③ Behavior</td>
		<td>정적 S3 내용 업로드 · 점검 페이지 · 버킷 정책(OAC) · KMS 키 정책(CloudFront)</td>
		<td>배포 ARN</td>
	</tr>
	<tr>
		<td>11</td>
		<td>⑩⑪⑫</td>
		<td>CloudWatch Agent 설정 반영 · ALB/CloudFront 로그 확인 · CloudTrail · 알람 3 → SNS</td>
		<td>로그 버킷 · KMS</td>
	</tr>
	<tr>
		<td>12</td>
		<td>⑬ Bastion</td>
		<td>키 페어 mc-ssh · mc-sg-bastion · mc-bastion(EIP) · SG 22/3306 규칙</td>
		<td>퍼블릭 서브넷 · mc-ec2-profile</td>
	</tr>
</table>
# 0. 기반 계층 (VPC · SG · IAM · KMS · S3 · 비밀 · 파라미터 · 로그 그룹)
> 코드: `modules/base/network.tf` `security.tf` `iam.tf` · 루트 `kms_s3.tf` `iam.tf` `rds.tf` `observability.tf`
## 0-1. VPC · 서브넷 · 라우팅 (VPC 콘솔)
**VPC → VPC 생성 → "VPC만"**: 이름 `mc-vpc`, IPv4 CIDR `10.0.0.0/16`, 테넌시 기본. 생성 후 **작업 → VPC 설정 편집 → DNS 호스트 이름 활성화** 체크(둘 다 켬).
<table header-row="true" fit-page-width="true">
	<tr>
		<td>서브넷 이름</td>
		<td>AZ</td>
		<td>CIDR</td>
		<td>용도</td>
		<td>라우팅 테이블</td>
	</tr>
	<tr>
		<td>mc-public-a</td>
		<td>ap-northeast-2a</td>
		<td>10.0.0.0/24</td>
		<td>NAT-a · Public ALB · Bastion</td>
		<td>mc-rt-public</td>
	</tr>
	<tr>
		<td>mc-public-c</td>
		<td>ap-northeast-2c</td>
		<td>10.0.1.0/24</td>
		<td>NAT-c · Public ALB</td>
		<td>mc-rt-public</td>
	</tr>
	<tr>
		<td>mc-web-a</td>
		<td>2a</td>
		<td>10.0.10.0/24</td>
		<td>WEB-A</td>
		<td>mc-rt-private-a</td>
	</tr>
	<tr>
		<td>mc-web-c</td>
		<td>2c</td>
		<td>10.0.11.0/24</td>
		<td>WEB-C</td>
		<td>mc-rt-private-c</td>
	</tr>
	<tr>
		<td>mc-was-a</td>
		<td>2a</td>
		<td>10.0.20.0/24</td>
		<td>WAS-A · Internal ALB</td>
		<td>mc-rt-private-a</td>
	</tr>
	<tr>
		<td>mc-was-c</td>
		<td>2c</td>
		<td>10.0.21.0/24</td>
		<td>WAS-C · Internal ALB</td>
		<td>mc-rt-private-c</td>
	</tr>
	<tr>
		<td>mc-db-a</td>
		<td>2a</td>
		<td>10.0.30.0/24</td>
		<td>RDS · Proxy ENI</td>
		<td>mc-rt-db</td>
	</tr>
	<tr>
		<td>mc-db-c</td>
		<td>2c</td>
		<td>10.0.31.0/24</td>
		<td>RDS · Proxy ENI</td>
		<td>mc-rt-db</td>
	</tr>
</table>
퍼블릭 서브넷도 **"퍼블릭 IPv4 주소 자동 할당"은 끈다**(Bastion 만 인스턴스 생성 시 개별로 켬).
1. **인터넷 게이트웨이** `mc-igw` 생성 → mc-vpc 에 연결.
2. **탄력적 IP** 2개 할당(이름 `mc-nat-eip-a` / `-c`) → **NAT 게이트웨이** `mc-nat-a`(서브넷 mc-public-a, 퍼블릭, EIP a) · `mc-nat-c`(mc-public-c, EIP c). AZ 당 1개인 이유: 한 AZ 가 죽어도 다른 AZ 의 WEB/WAS 가 dnf·git·Secrets 호출을 계속하기 위해(멘토링 확인).
3. **라우팅 테이블** 4개:
<table header-row="true" fit-page-width="true">
	<tr>
		<td>이름</td>
		<td>라우트</td>
		<td>연결 서브넷</td>
	</tr>
	<tr>
		<td>mc-rt-public</td>
		<td>10.0.0.0/16 local · 0.0.0.0/0 → mc-igw</td>
		<td>mc-public-a · mc-public-c</td>
	</tr>
	<tr>
		<td>mc-rt-private-a</td>
		<td>0.0.0.0/0 → mc-nat-a</td>
		<td>mc-web-a · mc-was-a</td>
	</tr>
	<tr>
		<td>mc-rt-private-c</td>
		<td>0.0.0.0/0 → mc-nat-c</td>
		<td>mc-web-c · mc-was-c</td>
	</tr>
	<tr>
		<td>mc-rt-db</td>
		<td>local 만 (인터넷 경로 없음)</td>
		<td>mc-db-a · mc-db-c</td>
	</tr>
</table>
4. **RDS → 서브넷 그룹** `mc-db-subnets`: mc-vpc · AZ 2a/2c · 서브넷 mc-db-a, mc-db-c.
## 0-2. 보안 그룹 7개 (EC2 → 보안 그룹, 모두 mc-vpc · 아웃바운드는 기본 "모두 허용")
앞 단계의 SG 만 인바운드로 허용하는 **체인**. 소스는 CIDR 이 아니라 **보안 그룹 ID** 로 넣는다.
<table header-row="true" fit-page-width="true">
	<tr>
		<td>이름</td>
		<td>인바운드 규칙</td>
		<td>설명</td>
	</tr>
	<tr>
		<td>mc-sg-alb-public</td>
		<td>HTTPS 443 ← 접두사 목록 `com.amazonaws.global.cloudfront.origin-facing`</td>
		<td>CloudFront 오리진 대면 IP 만. 80 없음</td>
	</tr>
	<tr>
		<td>mc-sg-web</td>
		<td>HTTP 80 ← mc-sg-alb-public · SSH 22 ← mc-sg-bastion</td>
		<td>Apache</td>
	</tr>
	<tr>
		<td>mc-sg-alb-internal</td>
		<td>TCP 8080 ← mc-sg-web</td>
		<td>Internal ALB</td>
	</tr>
	<tr>
		<td>mc-sg-was</td>
		<td>TCP 8080 ← mc-sg-alb-internal · SSH 22 ← mc-sg-bastion</td>
		<td>Tomcat</td>
	</tr>
	<tr>
		<td>mc-sg-rds-proxy</td>
		<td>MySQL 3306 ← mc-sg-was · 3306 ← mc-sg-bastion</td>
		<td>Proxy ENI</td>
	</tr>
	<tr>
		<td>mc-sg-rds</td>
		<td>MySQL 3306 ← mc-sg-rds-proxy **만**</td>
		<td>WAS 직접 접속 경로 없음</td>
	</tr>
	<tr>
		<td>mc-sg-bastion</td>
		<td>SSH 22 ← 운영자 공인 IP `/32` (여러 명이면 규칙 여러 개)</td>
		<td>⑬</td>
	</tr>
</table>
접두사 목록은 "소스" 입력란에 `pl-` 를 치면 CloudFront origin-facing 목록이 뜬다(서울 리전 ID 는 계정마다 같음). mc-sg-bastion 을 먼저 만들어야 web/was 규칙에 넣을 수 있다.
## 0-3. IAM 역할 3개 (IAM → 역할)
<table header-row="true" fit-page-width="true">
	<tr>
		<td>역할</td>
		<td>신뢰 주체</td>
		<td>정책</td>
		<td>인스턴스 프로파일</td>
	</tr>
	<tr>
		<td>mc-ec2-role</td>
		<td>EC2</td>
		<td>관리형 `CloudWatchAgentServerPolicy` + 인라인 `mc-ec2-inline`(아래). **AmazonSSMManagedInstanceCore 는 붙이지 않음**(팀 결정: Session Manager 안 씀)</td>
		<td>mc-ec2-profile (콘솔에서 EC2 역할을 만들면 자동 생성)</td>
	</tr>
	<tr>
		<td>mc-rds-proxy-role</td>
		<td>RDS</td>
		<td>인라인: `secretsmanager:GetSecretValue`(비밀 2개 ARN) + `kms:Decrypt`(aws/secretsmanager 키, 조건 kms:ViaService = secretsmanager.ap-northeast-2.amazonaws.com)</td>
		<td>—</td>
	</tr>
	<tr>
		<td>mc-backup-role</td>
		<td>AWS Backup</td>
		<td>관리형 `AWSBackupServiceRolePolicyForBackup`</td>
		<td>—</td>
	</tr>
</table>
`mc-ec2-inline` (JSON · 비밀 ARN 은 ⑧⑨ 에서 만든 뒤 채움):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {"Sid": "ReadRdsSecrets", "Effect": "Allow", "Action": "secretsmanager:GetSecretValue",
     "Resource": ["arn:aws:secretsmanager:ap-northeast-2:528821350786:secret:rds!db-…", "arn:aws:secretsmanager:ap-northeast-2:528821350786:secret:mc/petclinic/app-db-…"]},
    {"Sid": "DecryptSecret", "Effect": "Allow", "Action": "kms:Decrypt", "Resource": "arn:aws:kms:ap-northeast-2:528821350786:key/<aws/secretsmanager 키 ID>",
     "Condition": {"StringEquals": {"kms:ViaService": "secretsmanager.ap-northeast-2.amazonaws.com"}}},
    {"Sid": "ReadCwAgentConfig", "Effect": "Allow", "Action": "ssm:GetParameter", "Resource": "arn:aws:ssm:ap-northeast-2:528821350786:parameter/mc/cwagent/*"},
    {"Sid": "SyncLogsToS3", "Effect": "Allow", "Action": "s3:PutObject", "Resource": ["arn:aws:s3:::mc-logs-528821350786/was/*", "arn:aws:s3:::mc-logs-528821350786/web/*"]},
    {"Sid": "ListLogsBucket", "Effect": "Allow", "Action": "s3:ListBucket", "Resource": "arn:aws:s3:::mc-logs-528821350786"},
    {"Sid": "CompleteAsgLifecycleHook", "Effect": "Allow", "Action": "autoscaling:CompleteLifecycleAction",
     "Resource": "arn:aws:autoscaling:ap-northeast-2:528821350786:autoScalingGroup:*:autoScalingGroupName/mc-asg-*"}
  ]
}
```

## 0-4. KMS 키 (KMS → 고객 관리형 키 생성)
대칭 · 암호화/복호화 · 별칭 `mc-cmk` · **키 교체 활성화**. 키 정책에 기본(계정 root 전체) 외에 두 문장을 추가(② 배포를 만든 뒤 ARN 을 채움):

```json
{"Sid": "CloudFrontOACDecrypt", "Effect": "Allow", "Principal": {"Service": "cloudfront.amazonaws.com"},
 "Action": ["kms:Decrypt", "kms:Encrypt", "kms:GenerateDataKey*"], "Resource": "*",
 "Condition": {"StringEquals": {"aws:SourceArn": "arn:aws:cloudfront::528821350786:distribution/<배포 ID>"}}},
{"Sid": "LogDeliveryServices", "Effect": "Allow",
 "Principal": {"Service": ["logs.ap-northeast-2.amazonaws.com", "cloudtrail.amazonaws.com", "delivery.logs.amazonaws.com", "sns.amazonaws.com", "cloudwatch.amazonaws.com"]},
 "Action": ["kms:Encrypt", "kms:Decrypt", "kms:GenerateDataKey*", "kms:DescribeKey"], "Resource": "*"}
```

쓰는 곳: S3(점검·정적·CloudTrail) · SNS · CloudWatch Logs 그룹 · Backup 볼트. **RDS 와 비밀은 AWS 관리형 키(aws/rds · aws/secretsmanager) 그대로**.
## 0-5. S3 버킷 4개 (S3 → 버킷 만들기, 서울)
공통: ACL 비활성(로그 버킷만 예외) · **퍼블릭 액세스 모두 차단** · 버전 관리 활성화.
<table header-row="true" fit-page-width="true">
	<tr>
		<td>버킷</td>
		<td>암호화</td>
		<td>정책 · 수명 주기</td>
		<td>내용</td>
	</tr>
	<tr>
		<td>mc-maintenance-528821350786</td>
		<td>SSE-KMS mc-cmk · 버킷 키</td>
		<td>CloudFront OAC 만 GetObject(③) · TLS 아닌 요청 거부</td>
		<td>`maintenance.html`(점검 페이지)</td>
	</tr>
	<tr>
		<td>mc-static-528821350786</td>
		<td>SSE-KMS mc-cmk · 버킷 키</td>
		<td>동일(OAC · TLS)</td>
		<td>`static/resources/…` `static/images/…` (③)</td>
	</tr>
	<tr>
		<td>mc-logs-528821350786</td>
		<td>SSE-S3(AES256) — ALB 로그 전송 호환</td>
		<td>객체 소유권 **BucketOwnerPreferred(ACL 활성)** — CloudFront 표준 로그가 ACL 로 씀 · 정책: ALB 로그 계정 PutObject `alb/*` · TLS 거부 · 수명 주기 `alb/` 90일 · `cloudfront/` 90일 · `was/` 30일 · 미완료 멀티파트 7일</td>
		<td>ALB · CloudFront 액세스 로그(객체)</td>
	</tr>
	<tr>
		<td>mc-cloudtrail-528821350786</td>
		<td>SSE-KMS mc-cmk</td>
		<td>CloudTrail 서비스 GetBucketAcl(버킷) · PutObject `AWSLogs/528821350786/*`(bucket-owner-full-control) · 수명 주기 90일 → Glacier Instant Retrieval · 365일 만료</td>
		<td>감사 로그(⑪)</td>
	</tr>
</table>
로그 버킷 정책의 ALB 로그 계정(서울) 은 `arn:aws:iam::600734575887:root` 이다.

```json
{"Sid": "ALBAccessLogs", "Effect": "Allow", "Principal": {"AWS": "arn:aws:iam::600734575887:root"},
 "Action": "s3:PutObject", "Resource": "arn:aws:s3:::mc-logs-528821350786/alb/*"},
{"Sid": "DenyInsecureTransport", "Effect": "Deny", "Principal": "*", "Action": "s3:*",
 "Resource": ["arn:aws:s3:::mc-logs-528821350786", "arn:aws:s3:::mc-logs-528821350786/*"], "Condition": {"Bool": {"aws:SecureTransport": "false"}}}
```

## 0-6. 비밀 · 파라미터 · 로그 그룹
- **Secrets Manager** `mc/petclinic/app-db` (다른 유형): 키/값 `username` = `petclinic_app`, `password` = 32자 랜덤(특수문자는 `!#%^*()-_=+` 만 — XML·셸·JDBC URL 에서 탈 나지 않는 문자). **자동 교체 없음**. admin 비밀(`rds!db-…`)은 ⑧ 에서 RDS 가 만든다.
- **Systems Manager → Parameter Store** 표준 String 3개: `/mc/cwagent/web` · `/mc/cwagent/was` · `/mc/cwagent/bastion` — 값은 ⑩ 의 JSON. (Parameter Store 는 Session Manager 와 무관 — 설정 배포용)
- **CloudWatch → 로그 그룹** (서울 · KMS mc-cmk): `/mc/web/access` `/mc/web/error` `/mc/was/catalina` `/mc/was/access` `/mc/was/gc` 보존 30일 · `/mc/bastion/secure` 90일. **버지니아(us-east-1)** 에 `aws-waf-logs-mc` 30일(② WAF 로그, 이름이 `aws-waf-logs-` 로 시작해야 함).

# ① 사용자 → Route 53
> 선행: 없음(존만) · 레코드는 ② 뒤 · 코드 `edge.tf`
1. **Route 53 → 호스팅 존 생성**: `mission-critical.site` · 퍼블릭. 생성되면 NS 레코드 4개가 보인다 — 실제 값:

```text
ns-1392.awsdns-46.org
ns-1654.awsdns-14.co.uk
ns-33.awsdns-04.com
ns-784.awsdns-34.net
```

2. **가비아 → 도메인 관리 → 네임서버 설정**: 위 4개로 교체(1~4차). 반영 20~30분. 확인: `dig NS mission-critical.site +short`.
3. **레코드 2개**(② 배포가 생긴 뒤): `petclinic.mission-critical.site` **A** · **AAAA** — 레코드 유형 A/AAAA, **별칭(alias) 켬** → "CloudFront 배포에 대한 별칭" → `d2p7som2iuyba.cloudfront.net`. ALB 로 직접 가는 레코드는 만들지 않는다(ALB DNS 비공개).
4. ACM 검증용 CNAME 은 ②/④ 에서 "Route 53 에서 레코드 생성" 버튼으로 자동 추가(두 인증서가 같은 CNAME 을 씀 · 자동 갱신 위해 지우지 말 것).
왜: 도메인 → CloudFront 만 공개. Failover 레코드는 단일 리전이라 불필요(오리진 그룹이 대신).

# ② CloudFront (WAF · ACM 부착)
> 선행: ④ Public ALB(DNS) · ③ 의 S3 버킷 2개 · 코드 `edge.tf`
## 2-1. ACM 인증서 (버지니아 us-east-1 — CloudFront 는 여기 인증서만 씀)
리전을 **us-east-1** 로 바꾸고 **ACM → 요청 → 퍼블릭**: 도메인 `petclinic.mission-critical.site` · DNS 검증 · RSA 2048. "Route 53 에서 레코드 생성" 클릭 → 5~20분 뒤 **발급됨**. (서울 인증서는 ④)
## 2-2. WAF Web ACL (WAF & Shield → Web ACLs · 리전 "Global (CloudFront)")
- IP set `mc-loadgen` (CloudFront 범위 · IPv4 · 비워둠 — Phase 3 부하 실험 때 JMeter IP 추가)
- Web ACL `mc-web-acl` · 기본 동작 **Allow** · 규칙(우선순위 순):
<table header-row="true" fit-page-width="true">
	<tr>
		<td>우선</td>
		<td>이름</td>
		<td>유형</td>
		<td>동작</td>
		<td>설정</td>
	</tr>
	<tr>
		<td>0</td>
		<td>allow-loadgen</td>
		<td>IP set 참조 mc-loadgen</td>
		<td>Allow</td>
		<td>부하 발생기 통과</td>
	</tr>
	<tr>
		<td>1</td>
		<td>AWSManagedRulesAmazonIpReputationList</td>
		<td>AWS 관리형</td>
		<td>규칙 그룹 기본</td>
		<td>악성 IP 평판</td>
	</tr>
	<tr>
		<td>2</td>
		<td>AWSManagedRulesCommonRuleSet</td>
		<td>AWS 관리형</td>
		<td>규칙 그룹 기본</td>
		<td>OWASP 계열 공통</td>
	</tr>
	<tr>
		<td>3</td>
		<td>AWSManagedRulesKnownBadInputsRuleSet</td>
		<td>AWS 관리형</td>
		<td>규칙 그룹 기본</td>
		<td>알려진 악성 입력</td>
	</tr>
	<tr>
		<td>4</td>
		<td>rate-all</td>
		<td>Rate-based · IP 기준 · 평가 창 5분</td>
		<td>**Block**</td>
		<td>한도 **2,000** / 5분 / IP</td>
	</tr>
	<tr>
		<td>5</td>
		<td>rate-booking</td>
		<td>Rate-based · IP · 5분 · 범위 축소: URI path **ends with** `/visits/new` (텍스트 변환 lowercase)</td>
		<td>**Block**</td>
		<td>한도 **100** / 5분 / IP — 예약 폭주 대비</td>
	</tr>
</table>
- 각 규칙 CloudWatch 지표 켬 · 샘플 요청 켬. **로깅**: 로깅 활성화 → 대상 CloudWatch Logs 그룹 `aws-waf-logs-mc`(us-east-1).
- 연결(Associated resources)은 2-3 배포를 만든 뒤 여기서 추가하거나, 배포 생성 화면의 "웹 애플리케이션 방화벽" 에서 선택.
## 2-3. CloudFront 배포 (CloudFront → 배포 생성)
**Origin Access Control** 먼저: 보안 → Origin access → 생성 `mc-oac-s3` · 유형 S3 · 서명 "항상 서명(SigV4)".
<table header-row="true" fit-page-width="true">
	<tr>
		<td>항목</td>
		<td>값</td>
	</tr>
	<tr>
		<td>대체 도메인(CNAME)</td>
		<td>`petclinic.mission-critical.site`</td>
	</tr>
	<tr>
		<td>인증서</td>
		<td>2-1 의 us-east-1 인증서 · 보안 정책 **TLSv1.2_2021** · SNI</td>
	</tr>
	<tr>
		<td>HTTP 버전 · IPv6 · 가격</td>
		<td>HTTP/2 + HTTP/3 · IPv6 켬 · **PriceClass_200**(북미·유럽·아시아)</td>
	</tr>
	<tr>
		<td>WAF</td>
		<td>`mc-web-acl` 연결</td>
	</tr>
	<tr>
		<td>표준 로깅</td>
		<td>켬 → 버킷 `mc-logs-528821350786` · 접두사 `cloudfront/` · 쿠키 포함 끔 (버킷 ACL 활성 필요 — 0-5)</td>
	</tr>
	<tr>
		<td>설명</td>
		<td>mc petclinic (Behavior 분기: 정적 S3(OAC) 캐시 / 점검 페이지 S3 / 동적 ALB)</td>
	</tr>
</table>
**오리진 4개**:
<table header-row="true" fit-page-width="true">
	<tr>
		<td>오리진 이름(ID)</td>
		<td>도메인</td>
		<td>설정</td>
	</tr>
	<tr>
		<td>alb-public</td>
		<td>`mc-alb-public-485062926.ap-northeast-2.elb.amazonaws.com`</td>
		<td>프로토콜 **HTTPS only** · TLSv1.2 · 응답 제한 30s · keep-alive 5s · **커스텀 헤더 `X-Origin-Verify` = ‹비밀 문자열›**(④ 리스너 규칙과 동일)</td>
	</tr>
	<tr>
		<td>s3-maintenance</td>
		<td>`mc-maintenance-528821350786.s3.ap-northeast-2.amazonaws.com`</td>
		<td>Origin access control `mc-oac-s3` (버킷 정책은 ③ 에서 복사)</td>
	</tr>
	<tr>
		<td>s3-static</td>
		<td>`mc-static-528821350786.s3.ap-northeast-2.amazonaws.com`</td>
		<td>OAC `mc-oac-s3`</td>
	</tr>
	<tr>
		<td>s3-static-images</td>
		<td>같은 mc-static 버킷</td>
		<td>OAC · **오리진 경로 `/static`** (그래서 `/images/x` 요청이 키 `static/images/x` 를 읽음)</td>
	</tr>
</table>
**오리진 그룹** `alb-with-maintenance-failover`: 기본 alb-public → 보조 s3-maintenance · 장애 조치 기준 **500 · 502 · 503 · 504**.
**동작(Behavior)** — 위에서부터 순서대로(정확도 순):
<table header-row="true" fit-page-width="true">
	<tr>
		<td>경로 패턴</td>
		<td>오리진</td>
		<td>뷰어 프로토콜</td>
		<td>메서드</td>
		<td>캐시 정책</td>
		<td>오리진 요청 정책</td>
		<td>응답 헤더 정책</td>
		<td>압축</td>
	</tr>
	<tr>
		<td>`/petclinic/resources/*`</td>
		<td>오리진 그룹</td>
		<td>HTTPS 로 리디렉션</td>
		<td>GET HEAD OPTIONS</td>
		<td>CachingOptimized</td>
		<td>AllViewer</td>
		<td>SecurityHeadersPolicy</td>
		<td>켬</td>
	</tr>
	<tr>
		<td>`/static/*`</td>
		<td>s3-static</td>
		<td>HTTPS 로 리디렉션</td>
		<td>GET HEAD OPTIONS</td>
		<td>CachingOptimized</td>
		<td>**없음** (S3 오리진에 AllViewer 를 붙이면 Host 가 넘어가 서명 불일치 403)</td>
		<td>SecurityHeadersPolicy</td>
		<td>켬</td>
	</tr>
	<tr>
		<td>`/images/*`</td>
		<td>s3-static-images</td>
		<td>HTTPS 로 리디렉션</td>
		<td>GET HEAD OPTIONS</td>
		<td>CachingOptimized</td>
		<td>없음</td>
		<td>SecurityHeadersPolicy</td>
		<td>켬</td>
	</tr>
	<tr>
		<td>`/petclinic/images/*`</td>
		<td>오리진 그룹</td>
		<td>HTTPS 로 리디렉션</td>
		<td>GET HEAD OPTIONS</td>
		<td>CachingOptimized</td>
		<td>AllViewer</td>
		<td>SecurityHeadersPolicy</td>
		<td>켬</td>
	</tr>
	<tr>
		<td>`/maintenance.html`</td>
		<td>s3-maintenance</td>
		<td>HTTPS 로 리디렉션</td>
		<td>GET HEAD</td>
		<td>CachingOptimized</td>
		<td>없음</td>
		<td>없음</td>
		<td>—</td>
	</tr>
	<tr>
		<td>기본 `*`</td>
		<td>alb-public (그룹 아님 — POST 는 오리진 그룹 불가)</td>
		<td>HTTPS 로 리디렉션</td>
		<td>**모두**(GET~DELETE) · 캐시는 GET HEAD</td>
		<td>**CachingDisabled**</td>
		<td>AllViewer</td>
		<td>SecurityHeadersPolicy</td>
		<td>—</td>
	</tr>
</table>
**사용자 지정 오류 응답** 3개: 502 · 503 · 504 → 응답 페이지 `/maintenance.html` · 응답 코드 **503** · 오류 캐싱 최소 TTL **10초**.
배포 후 "Deployed" 까지 5~10분. 확인: `curl -sI https://d2p7som2iuyba.cloudfront.net/` 는 403(호스트 헤더 불일치 — 정상) → ① 의 A/AAAA 를 만든 뒤 `curl -sI https://petclinic.mission-critical.site/` 첫 줄이 `HTTP/2 200`.
왜 WAF 를 두나: CloudFront 에 붙은 Web ACL 은 캐시 조회보다 먼저 평가돼 차단 요청이 캐시·오리진에 닿지 않는다. 멘토링 때 "관리 어려움" 의견이 있었지만 팀 결정으로 유지.

# ③ Behavior 분기 → 정적 S3 / ALB / 점검 S3
> 선행: ② 배포 ARN(버킷 정책 · KMS 정책 조건에 필요) · 코드 `kms_s3.tf` `edge.tf`
## 3-1. 버킷 정책 (mc-maintenance · mc-static 공통 — 버킷 이름만 바꿔 붙임)

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {"Sid": "AllowCloudFrontOAC", "Effect": "Allow", "Principal": {"Service": "cloudfront.amazonaws.com"},
     "Action": "s3:GetObject", "Resource": "arn:aws:s3:::mc-static-528821350786/*",
     "Condition": {"StringEquals": {"AWS:SourceArn": "arn:aws:cloudfront::528821350786:distribution/E2PWXW3LUYTDEE"}}},
    {"Sid": "DenyInsecureTransport", "Effect": "Deny", "Principal": "*", "Action": "s3:*",
     "Resource": ["arn:aws:s3:::mc-static-528821350786", "arn:aws:s3:::mc-static-528821350786/*"],
     "Condition": {"Bool": {"aws:SecureTransport": "false"}}}
  ]
}
```

KMS 키 정책의 `CloudFrontOACDecrypt`(0-4) 에도 같은 배포 ARN 을 넣어야 SSE-KMS 객체를 CloudFront 가 읽는다.
## 3-2. 정적 자산 업로드 (mc-static)
저장소 `test` 브랜치의 `src/main/webapp/resources/**`(`less/` 제외) → 키 `static/resources/…`, `src/main/webapp/images/**` → 키 `static/images/…`. 콘솔 업로드 시 폴더째 끌어넣으면 되고, CLI 라면:

```bash
cd src/main/webapp
aws s3 sync resources s3://mc-static-528821350786/static/resources --exclude "less/*" --cache-control "public, max-age=86400"
aws s3 sync images    s3://mc-static-528821350786/static/images   --cache-control "public, max-age=86400"
# Content-Type 은 확장자로 자동. 바꾼 뒤엔 무효화:
aws cloudfront create-invalidation --distribution-id E2PWXW3LUYTDEE --paths "/static/*" "/images/*"
```

왜 두 오리진인가: 랜딩 index.html 은 `/static/resources/...` 를, WAS 의 welcome.jsp 는 옛 경로 `/images/hero/hero.mp4` 를 쓴다. 파일은 한 벌(`static/images/…`)만 두고 `/images/*` 오리진에 **오리진 경로 `/static`** 을 줘서 같은 키를 읽게 했다.
## 3-3. 점검 페이지 (mc-maintenance)
`maintenance.html` 한 파일(정적 HTML · "점검 중" 안내) 을 버킷 루트에 업로드. ② 의 오류 응답이 ALB·WEB·WAS 가 전부 5xx 일 때 이 페이지를 503 으로 보여준다. 확인: `curl -sI https://petclinic.mission-critical.site/maintenance.html` 첫 줄 `HTTP/2 200`.
## 3-4. 흐름 정리
<table header-row="true" fit-page-width="true">
	<tr>
		<td>요청</td>
		<td>어디서 끝나나</td>
	</tr>
	<tr>
		<td>`/static/…` · `/images/…` (랜딩 css·이미지·hero.mp4)</td>
		<td>엣지 캐시 Hit → 끝. Miss → S3 mc-static (Apache 안 거침)</td>
	</tr>
	<tr>
		<td>`/petclinic/resources/…` (WAR 안 css·js)</td>
		<td>엣지 캐시 Hit → 끝. Miss → ALB → Apache → Internal ALB → Tomcat</td>
	</tr>
	<tr>
		<td>그 외 `*` (동적 · POST 포함)</td>
		<td>매번 ALB(캐시 없음 · 쿠키·쿼리 그대로)</td>
	</tr>
	<tr>
		<td>오리진 5xx</td>
		<td>`/maintenance.html`(S3) 503</td>
	</tr>
</table>
# ④ Public ALB → WEB ×2
> 선행: ① 존(ACM 검증) · 0 의 서브넷·SG · 코드 `modules/base/alb.tf` · 루트 `alb.tf`
## 4-1. ACM 인증서 (서울)
ACM(서울) → 요청 → `petclinic.mission-critical.site` · DNS 검증 → "Route 53 에서 레코드 생성"(us-east-1 인증서와 같은 CNAME 이라 이미 있으면 그대로) → 발급.
## 4-2. 대상 그룹 (EC2 → 대상 그룹)
<table header-row="true" fit-page-width="true">
	<tr>
		<td>항목</td>
		<td>값</td>
	</tr>
	<tr>
		<td>이름 · 유형</td>
		<td>`mc-tg-web` · 인스턴스 · HTTP **80** · mc-vpc · HTTP1</td>
	</tr>
	<tr>
		<td>상태 검사</td>
		<td>HTTP · 경로 **`/health.html`** · 간격 10s · 제한 시간 5s · 정상 임계값 2 · 비정상 3 · 성공 코드 200</td>
	</tr>
	<tr>
		<td>등록 취소 지연</td>
		<td>30초</td>
	</tr>
	<tr>
		<td>대상</td>
		<td>⑤ 에서 만든 mc-web-a, mc-web-c :80</td>
	</tr>
</table>
얕게(`/health.html` 정적 파일) 검사하는 이유: WAS 장애가 WEB 까지 연쇄 unhealthy 로 번지지 않게. WAS 장애는 Internal ALB · 알람이 잡는다.
## 4-3. 로드 밸런서 (EC2 → 로드 밸런서 → ALB)
<table header-row="true" fit-page-width="true">
	<tr>
		<td>항목</td>
		<td>값</td>
	</tr>
	<tr>
		<td>이름 · 체계</td>
		<td>`mc-alb-public` · **인터넷 경계** · IPv4</td>
	</tr>
	<tr>
		<td>네트워크</td>
		<td>mc-vpc · 서브넷 mc-public-a, mc-public-c · SG **mc-sg-alb-public** 만</td>
	</tr>
	<tr>
		<td>리스너</td>
		<td>**HTTPS 443** 만(80 없음) · 인증서 4-1 · 보안 정책 `ELBSecurityPolicy-TLS13-1-2-2021-06`</td>
	</tr>
	<tr>
		<td>443 기본 작업</td>
		<td>**고정 응답 403** · text/plain · 본문 `Forbidden`</td>
	</tr>
	<tr>
		<td>443 규칙 우선순위 10</td>
		<td>조건 **HTTP 헤더** `X-Origin-Verify` = ‹비밀 문자열›(② 오리진 커스텀 헤더와 같은 값) → 작업 **전달 mc-tg-web**</td>
	</tr>
	<tr>
		<td>속성</td>
		<td>유휴 제한 시간 60s · **액세스 로그 켬** → `s3://mc-logs-528821350786/alb/public`</td>
	</tr>
</table>
두 겹 방어: SG(CloudFront IP 만) + 헤더(값을 아는 CloudFront 만). 확인: `curl -sk -m 8 https://mc-alb-public-485062926.ap-northeast-2.elb.amazonaws.com/` → 타임아웃(SG) 또는 403(헤더 없음)이면 정상.

# ⑤ WEB → Internal ALB (Apache 2.4 · mod_proxy_http)
> 선행: ⑥ Internal ALB DNS(스크립트에 넣음) · 0-3 프로파일 · ⑬ 키 페어 · 코드 `modules/base/compute.tf` `user_data/web.sh`
## 5-1. 인스턴스 2대 (EC2 → 인스턴스 시작)
<table header-row="true" fit-page-width="true">
	<tr>
		<td>항목</td>
		<td>mc-web-a</td>
		<td>mc-web-c</td>
	</tr>
	<tr>
		<td>AMI</td>
		<td>Amazon Linux 2023 (x86_64, 최신)</td>
		<td>동일</td>
	</tr>
	<tr>
		<td>유형</td>
		<td>t3.small</td>
		<td>t3.small</td>
	</tr>
	<tr>
		<td>키 페어</td>
		<td>`mc-ssh`(⑬)</td>
		<td>동일</td>
	</tr>
	<tr>
		<td>네트워크</td>
		<td>mc-vpc · 서브넷 **mc-web-a** · 퍼블릭 IP **비활성** · SG **mc-sg-web**</td>
		<td>서브넷 **mc-web-c**</td>
	</tr>
	<tr>
		<td>스토리지</td>
		<td>gp3 20GiB · 암호화</td>
		<td>동일</td>
	</tr>
	<tr>
		<td>고급 → IAM 프로파일</td>
		<td>`mc-ec2-profile`</td>
		<td>동일</td>
	</tr>
	<tr>
		<td>고급 → 메타데이터</td>
		<td>IMDSv2 **필수** · 홉 제한 1</td>
		<td>동일</td>
	</tr>
	<tr>
		<td>고급 → 사용자 데이터</td>
		<td>아래 스크립트 (두 대 동일)</td>
		<td>동일</td>
	</tr>
</table>
## 5-2. 사용자 데이터 `web.sh` (실제 값 반영)

```bash
#!/bin/bash
# WEB (Apache 2.4) — 첫 화면 = WAR 의 index.html (src/main/webapp/index.html) 을 Apache 가 직접 서빙.
# index.html 이 쓰는 자산(resources/·images/)은 같은 브랜치에서 /var/www/html/static/ 으로 복사해 Apache 가 직접 서빙(/static/* 은 CloudFront 캐시).
# 앱 링크(preview-info.html?route=/X)는 /petclinic/X 로. WAS 의 welcome.jsp 가 쓰는 /images/hero/hero.mp4 (옛 S3 경로) 는 Alias 로 같은 /static/images 를 서빙. WAR 에 index.html 이 없는 브랜치(main=Blue)면 / → 302 /petclinic/ 폴백.
# 왜 자산도 복사하나: Blue(main) WAR 에는 리디자인 css·영상이 없어 /petclinic/resources/… 로 보내면 404. 랜딩 페이지는 앱 브랜치와 독립이어야 함.
# /petclinic/ 만 Internal ALB 로 프록시. AL2023.
set -uo pipefail
exec > >(tee -a /var/log/mc-userdata.log) 2>&1

dnf install -y httpd git amazon-cloudwatch-agent

# ---- WAR 의 index.html 가져오기 (index_branch 가 비면 앱 브랜치와 동일) ----
INDEX_BRANCH="test"
[ -z "$INDEX_BRANCH" ] && INDEX_BRANCH="test"
rm -rf /tmp/petclinic-src
git clone -q --depth 1 -b "$INDEX_BRANCH" "https://github.com/bsespin-multi-cloud-5-aws-1/petclinic-aws-3tier.git" /tmp/petclinic-src || echo "WARN: clone failed ($INDEX_BRANCH)"
ROOT_RULE=""
if [ -f /tmp/petclinic-src/src/main/webapp/index.html ]; then
  rm -rf /var/www/html/static && mkdir -p /var/www/html/static
  cp -r /tmp/petclinic-src/src/main/webapp/resources /var/www/html/static/resources
  [ -d /tmp/petclinic-src/src/main/webapp/images ] && cp -r /tmp/petclinic-src/src/main/webapp/images /var/www/html/static/images
  # 자산 상대 경로 → /static/… (Apache 직접) · preview-info.html?route=/X (디자인 패키지 스텁) → 실제 앱 경로 /petclinic/X
  sed -E \
    -e 's#(href|src|poster)="resources/#\1="/static/resources/#g' \
    -e 's#(href|src|poster)="images/#\1="/static/images/#g' \
    -e 's#href="preview-info\.html\?route=/#href="/petclinic/#g' \
    /tmp/petclinic-src/src/main/webapp/index.html > /var/www/html/index.html
  echo "index.html installed from $INDEX_BRANCH ($(wc -c < /var/www/html/index.html) bytes) · static $(du -sh /var/www/html/static | cut -f1)"
  # 히어로(첫 화면)는 한 번만: 앱 홈 /petclinic/ (welcome.jsp 도 히어로) 는 랜딩 / 로 보냄. 앱 내부 링크·헬스체크(Internal ALB→Tomcat 직접)는 영향 없음
  ROOT_RULE='RewriteCond %{HTTP:X-Forwarded-Proto} =https
RewriteRule ^'"/petclinic"'/$ https://%{HTTP_HOST}/ [R=302,L]
RewriteRule ^'"/petclinic"'/$ / [R=302,L]'
else
  rm -f /var/www/html/index.html
  ROOT_RULE='RewriteCond %{HTTP:X-Forwarded-Proto} =https
RewriteRule ^/$ https://%{HTTP_HOST}'"/petclinic"'/ [R=302,L]
RewriteRule ^/$ '"/petclinic"'/ [R=302,L]'
  echo "no index.html in $INDEX_BRANCH → / redirects to /petclinic/"
fi
rm -rf /tmp/petclinic-src

cat > /etc/httpd/conf.d/petclinic.conf <<CONF
ProxyPreserveHost On
RewriteEngine On
$ROOT_RULE
RewriteCond %{HTTP:X-Forwarded-Proto} =https
RewriteRule ^/petclinic$ https://%{HTTP_HOST}/petclinic/ [R=301,L]
RewriteRule ^/petclinic$ /petclinic/ [R=301,L]
ProxyPass        /health.html !
ProxyPass        /static/ !
ProxyPass        /images/ !
Alias            /images/ /var/www/html/static/images/
ProxyPass        /petclinic/ http://internal-mc-alb-internal-692352220.ap-northeast-2.elb.amazonaws.com:8080/petclinic/
ProxyPassReverse /petclinic/ http://internal-mc-alb-internal-692352220.ap-northeast-2.elb.amazonaws.com:8080/petclinic/
SetEnvIf Request_URI "^/health.html$" nolog
CustomLog /var/log/httpd/access_log combined env=!nolog
CONF

echo ok > /var/www/html/health.html

setsebool -P httpd_can_network_connect 1 || true
apachectl configtest && systemctl enable --now httpd && systemctl restart httpd

for i in $(seq 1 12); do
  /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl -a fetch-config -m ec2 -c "ssm:/mc/cwagent/web" -s && { echo "cwagent configured"; break; }
  echo "cwagent config retry $i/12"; sleep 10
done

curl -s -o /dev/null -w "root %{http_code} -> %{redirect_url}\n" http://localhost/
curl -s -o /dev/null -w "health %{http_code}\n" http://localhost/health.html
```

무엇을 하나: Apache 설치 → test 브랜치 WAR 소스의 `index.html` 과 `resources/`·`images/` 를 `/var/www/html`(정적 서빙, 링크는 `/static/…`·`/petclinic/…` 로 치환) → `petclinic.conf`(ProxyPass `/petclinic/` → Internal ALB :8080 · ProxyPreserveHost · `/petclinic/` 은 랜딩 `/` 로 302 · `/health.html` 은 프록시 제외) → CloudWatch Agent 설정을 Parameter Store `/mc/cwagent/web` 에서 받아 시작.
mod_jk 가 아니라 mod_proxy_http 인 이유: AJP 는 ALB 를 통과할 수 없고 HTTP 리버스 프록시는 Internal ALB 뒤의 WAS 를 증설·교체해도 WEB 설정이 안 바뀐다.
확인(Bastion 경유 SSH): `curl -sI http://localhost/` 와 `curl -sI http://localhost/health.html` 첫 줄 `HTTP/1.1 200 OK`, `/var/log/mc-userdata.log` 에 `index.html installed from test`.

# ⑥ Internal ALB → WAS ×2
> 선행: 0 의 WAS 서브넷 · mc-sg-alb-internal · 코드 `modules/base/alb.tf`
<table header-row="true" fit-page-width="true">
	<tr>
		<td>항목</td>
		<td>값</td>
	</tr>
	<tr>
		<td>대상 그룹</td>
		<td>`mc-tg-was` · 인스턴스 · HTTP **8080** · 상태 검사 경로 **`/petclinic/`**(슬래시 필수 — 없으면 301 로 실패) · 10s · 5s · 2/3 · 200 · 등록 취소 30s · 대상 mc-was-a, mc-was-c :8080</td>
	</tr>
	<tr>
		<td>로드 밸런서</td>
		<td>`mc-alb-internal` · **내부** · 서브넷 mc-was-a, mc-was-c · SG mc-sg-alb-internal · 리스너 **HTTP 8080** → mc-tg-was 전달 · 유휴 60s · 액세스 로그 → `s3://mc-logs-528821350786/alb/internal`</td>
	</tr>
</table>
DNS 는 `internal-mc-alb-internal-692352220.ap-northeast-2.elb.amazonaws.com` 처럼 나온다 — 이 값을 ⑤ web.sh 의 `ProxyPass` 에 넣는다. WEB 은 WAS IP 를 모르므로 WAS 를 갈아끼워도 WEB 은 무변경.

# ⑦ WAS → RDS Proxy (Tomcat 9.0.121 · Corretto 8 · PetClinic test)
> 선행: ⑨ Proxy 엔드포인트 · 비밀 2개 · 0-3 프로파일 · ⑬ 키 · 코드 `user_data/was.sh`
## 7-1. 인스턴스 2대
mc-web 과 같되: 이름 `mc-was-a`/`mc-was-c` · **t3.medium**(Maven 빌드 + Tomcat 1GB 힙) · 서브넷 mc-was-a / mc-was-c · SG **mc-sg-was** · 사용자 데이터는 아래.
## 7-2. 사용자 데이터 `was.sh` (실제 값 반영 · 비밀 ARN 은 ⑧⑨ 값)

```bash
#!/bin/bash
# WAS (Tomcat 9.0.121 + PetClinic test) — OpenJDK 8(Corretto) · AL2023 · JDBC 는 RDS Proxy(TLS 필수) 경유
set -uo pipefail
exec > >(tee -a /var/log/mc-userdata.log) 2>&1
REGION="ap-northeast-2"
TOMCAT_VER="9.0.121"

dnf install -y java-1.8.0-amazon-corretto-devel git unzip jq mariadb105 amazon-cloudwatch-agent

# ---- DB 자격증명: RDS 관리형 비밀 → 빌드 시점 주입 (루트 인라인 정책이 붙기 전일 수 있어 재시도) ----
DB_SECRET=""
for i in $(seq 1 18); do
  DB_SECRET=$(aws secretsmanager get-secret-value --region "$REGION" --secret-id "arn:aws:secretsmanager:ap-northeast-2:528821350786:secret:rds!db-ffb62b33-b4c4-4241-b6ba-fec77071ae08-cx63qJ" --query SecretString --output text 2>/dev/null) && [ -n "$DB_SECRET" ] && break
  echo "secret retry $i/18"; sleep 10
done
ADMIN_USER=$(echo "$DB_SECRET" | jq -r .username)
ADMIN_PASS=$(echo "$DB_SECRET" | jq -r .password)
# 앱 전용 사용자 비밀(교체 없음) — admin 은 7일마다 교체돼 WAR 에 박아두면 Proxy 인증이 깨짐
APP_SECRET=$(aws secretsmanager get-secret-value --region "$REGION" --secret-id "arn:aws:secretsmanager:ap-northeast-2:528821350786:secret:mc/petclinic/app-db-IpGESL" --query SecretString --output text)
DB_USER=$(echo "$APP_SECRET" | jq -r .username)
DB_PASS=$(echo "$APP_SECRET" | jq -r .password)
DB_PASS_XML=$(printf '%s' "$DB_PASS" | python3 -c 'import sys,html; print(html.escape(sys.stdin.read(), quote=True), end="")')
# Proxy 는 require_tls → sslMode=REQUIRED. 파라미터 그룹 require_secure_transport 와 짝
JDBC_URL="jdbc:mysql://mc-rds-proxy.proxy-c7ku4mw88shn.ap-northeast-2.rds.amazonaws.com:3306/petclinic?useUnicode=true&amp;characterEncoding=UTF-8&amp;serverTimezone=Asia/Seoul&amp;sslMode=REQUIRED"

# ---- Proxy 3306 도달 대기 ----
for i in $(seq 1 30); do
  timeout 3 bash -c "echo > /dev/tcp/mc-rds-proxy.proxy-c7ku4mw88shn.ap-northeast-2.rds.amazonaws.com/3306" 2>/dev/null && { echo "DB endpoint reachable (mc-rds-proxy.proxy-c7ku4mw88shn.ap-northeast-2.rds.amazonaws.com:3306)"; break; }
  echo "waiting mc-rds-proxy.proxy-c7ku4mw88shn.ap-northeast-2.rds.amazonaws.com:3306 ($i/30)"; sleep 10
done
# TCP 가 열려도 RDS Proxy 대상(target) 이 AVAILABLE 되기까지 몇 분 걸림 → 실제 로그인 성공까지 대기 (안 하면 앱이 Communications link failure 로 기동 실패)
for i in $(seq 1 30); do
  mysql --ssl -h "mc-rds-proxy.proxy-c7ku4mw88shn.ap-northeast-2.rds.amazonaws.com" -u "$ADMIN_USER" -p"$ADMIN_PASS" -e "SELECT VERSION() AS mysql_version; SHOW DATABASES LIKE 'petclinic';" && { echo "DB login OK ($i)"; break; }
  echo "DB login retry $i/30"; sleep 10
done
# 앱 사용자 생성/동기화 (멱등) — petclinic.* 만. 비밀번호는 비밀 값으로 매번 맞춤
DB_PASS_SQL=$(printf '%s' "$DB_PASS" | sed "s/'/''/g")
mysql --ssl -h "mc-rds-proxy.proxy-c7ku4mw88shn.ap-northeast-2.rds.amazonaws.com" -u "$ADMIN_USER" -p"$ADMIN_PASS" -e "CREATE USER IF NOT EXISTS '$DB_USER'@'%' IDENTIFIED BY '$DB_PASS_SQL'; ALTER USER '$DB_USER'@'%' IDENTIFIED BY '$DB_PASS_SQL'; GRANT ALL PRIVILEGES ON \`petclinic\`.* TO '$DB_USER'@'%'; FLUSH PRIVILEGES;" \
  && echo "app user $DB_USER ready" || echo "APP USER FAILED"
# 앱 사용자로 Proxy 경유 로그인이 될 때까지 대기 — Proxy 의 SECRETS 인증 목록에 앱 비밀이 반영되기 전에 Tomcat 이 뜨면
# "Access denied for user petclinic_app" 로 컨텍스트 초기화 실패(404) 후 재시도하지 않음 (9/16 was-a 재현)
for i in $(seq 1 30); do
  mysql --ssl -h "mc-rds-proxy.proxy-c7ku4mw88shn.ap-northeast-2.rds.amazonaws.com" -u "$DB_USER" -p"$DB_PASS" -e "SELECT CURRENT_USER() AS app_login;" && { echo "app login via proxy OK ($i)"; break; }
  echo "app login retry $i/30"; sleep 10
done
unset ADMIN_PASS DB_SECRET DB_PASS_SQL

# ---- Tomcat ----
cd /tmp && curl -fLO "https://dlcdn.apache.org/tomcat/tomcat-9/v$TOMCAT_VER/bin/apache-tomcat-$TOMCAT_VER.tar.gz" \
  || curl -fLO "https://archive.apache.org/dist/tomcat/tomcat-9/v$TOMCAT_VER/bin/apache-tomcat-$TOMCAT_VER.tar.gz"
mkdir -p /opt/tomcat && tar xzf "apache-tomcat-$TOMCAT_VER.tar.gz" -C /opt/tomcat --strip-components=1
id tomcat >/dev/null 2>&1 || useradd -r -m -d /opt/tomcat -s /sbin/nologin tomcat
rm -rf /opt/tomcat/webapps/*

# ---- 앱 빌드 (MySQL 프로필 · 빌드 시 주입) ----
cd /opt && git clone -b "test" "https://github.com/bsespin-multi-cloud-5-aws-1/petclinic-aws-3tier.git" petclinic-src
cd /opt/petclinic-src && ./mvnw -q package -P MySQL -DskipTests \
  "-Djdbc.url=$JDBC_URL" "-Djdbc.username=$DB_USER" "-Djdbc.password=$DB_PASS_XML" \
  && cp target/petclinic.war /opt/tomcat/webapps/ || echo "BUILD FAILED: petclinic.war not deployed"
rm -rf /opt/petclinic-src/target/classes /opt/petclinic-src/target/petclinic

cat > /opt/tomcat/bin/setenv.sh <<'SETENV'
export CATALINA_OPTS="$CATALINA_OPTS -Xms512m -Xmx1g -Xloggc:/opt/tomcat/logs/gc.log -XX:+PrintGCDetails -XX:+PrintGCDateStamps"
SETENV
chown -R tomcat:tomcat /opt/tomcat

cat > /etc/systemd/system/tomcat.service <<UNIT
[Unit]
Description=Apache Tomcat 9
After=network.target
[Service]
Type=forking
User=tomcat
Group=tomcat
Environment=JAVA_HOME=/usr/lib/jvm/java-1.8.0-amazon-corretto.x86_64
Environment=CATALINA_HOME=/opt/tomcat
ExecStart=/opt/tomcat/bin/startup.sh
ExecStop=/opt/tomcat/bin/shutdown.sh
Restart=on-failure
[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload && systemctl enable --now tomcat

# CloudWatch Agent (catalina · access · gc → /mc/was/*)
for i in $(seq 1 12); do
  /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl -a fetch-config -m ec2 -c "ssm:/mc/cwagent/was" -s && { echo "cwagent configured"; break; }
  echo "cwagent config retry $i/12"; sleep 10
done

# 앱 기동 확인 — DB 연결 실패로 404 면 Tomcat 재시작(최대 3회). Spring 컨텍스트는 실패 후 스스로 재시도하지 않음
for i in 1 2 3; do
  sleep 30
  code=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:8080/petclinic/")
  [ "$code" = "200" ] && break
  echo "petclinic $code → tomcat restart ($i/3)"; systemctl restart tomcat
done
curl -s -o /dev/null -w "petclinic %{http_code}\n" "http://localhost:8080/petclinic/"
curl -s "http://localhost:8080/petclinic/vets.json" | head -c 120; echo
mysql --ssl -h "mc-rds-proxy.proxy-c7ku4mw88shn.ap-northeast-2.rds.amazonaws.com" -u "$DB_USER" -p"$DB_PASS" "petclinic" \
  -e "SELECT 'vets' t, COUNT(*) n FROM vets UNION ALL SELECT 'owners', COUNT(*) FROM owners UNION ALL SELECT 'pets', COUNT(*) FROM pets;" \
  || echo "DB CHECK FAILED: 앱이 스키마를 만들지 못함 → /opt/tomcat/logs/catalina.out"
unset DB_PASS DB_PASS_XML APP_SECRET
```

순서대로 하는 일:
1. admin 비밀(rds!db-…) 조회 → Proxy 3306 TCP 대기 → **admin 로그인 성공까지 대기**(Proxy 대상이 AVAILABLE 되기 전에 앱이 뜨면 Communications link failure).
2. 앱 사용자 `petclinic_app` 생성/동기화(`CREATE USER IF NOT EXISTS` · `petclinic.*` 권한만) → **앱 사용자로 Proxy 경유 로그인 성공까지 대기**(Proxy 인증 목록 반영 전이면 Access denied → 컨텍스트 초기화 실패 404).
3. Tomcat 9.0.121 설치(systemd · tomcat 사용자) → 저장소 test 브랜치 clone → `./mvnw -P MySQL -Djdbc.url=…sslMode=REQUIRED -Djdbc.username -Djdbc.password` 로 WAR 빌드(비밀은 WAR 안에만 · Java 수정 0줄) → 배포.
4. CloudWatch Agent 설정(`/mc/cwagent/was`) → 앱 200 확인(404 면 재시작 최대 3회) → `vets/owners/pets` 건수 출력.
DB 스키마는 앱이 첫 기동 때 `schema.sql`(CREATE TABLE IF NOT EXISTS) · `data.sql`(INSERT IGNORE) 로 만든다 — 멱등이라 2대가 동시에 떠도 안전(9/16 실측). 풀 설정(`datasource-config.xml`: testOnBorrow `SELECT 1` · 유휴 10분 회수)은 저장소에 이미 반영.
확인: `curl -sI http://localhost:8080/petclinic/` 첫 줄 `HTTP/1.1 200`, `curl -s http://localhost:8080/petclinic/vets.json`, `/var/log/mc-userdata.log` 의 `app login via proxy OK` · `vets 6`.

# ⑧ RDS MySQL 8.4 Multi-AZ
> 선행: 0-1 서브넷 그룹 · mc-sg-rds · 코드 `rds.tf`
## 8-1. 파라미터 그룹 (RDS → 파라미터 그룹 → 생성)
이름 `mc-mysql84` · 패밀리 **mysql8.4** · 편집: `require_secure_transport` = **1**(TLS 아닌 접속 거부) · `character_set_server` = `utf8mb4` · `collation_server` = `utf8mb4_unicode_ci`.
## 8-2. 데이터베이스 생성 (표준 생성)
<table header-row="true" fit-page-width="true">
	<tr>
		<td>항목</td>
		<td>값</td>
	</tr>
	<tr>
		<td>엔진 · 버전</td>
		<td>MySQL **8.4.11** (8.0 은 2026-07-31 표준 지원 종료)</td>
	</tr>
	<tr>
		<td>템플릿 · 배포</td>
		<td>프로덕션 · **다중 AZ DB 인스턴스**(Standby 1)</td>
	</tr>
	<tr>
		<td>식별자 · DB 이름</td>
		<td>`mc-petclinic` · 초기 데이터베이스 `petclinic`</td>
	</tr>
	<tr>
		<td>마스터</td>
		<td>사용자 `admin` · **AWS Secrets Manager 에서 관리** (KMS aws/secretsmanager) → 비밀 `rds!db-…` 자동 생성 · 7일마다 자동 교체</td>
	</tr>
	<tr>
		<td>인스턴스 · 스토리지</td>
		<td>db.t3.small · gp3 **20GiB** · 자동 조정 최대 **100GiB** · 암호화(aws/rds)</td>
	</tr>
	<tr>
		<td>연결</td>
		<td>mc-vpc · 서브넷 그룹 `mc-db-subnets` · 퍼블릭 액세스 **아니요** · SG `mc-sg-rds` · 포트 3306 · CA rds-ca-rsa2048-g1</td>
	</tr>
	<tr>
		<td>추가 구성</td>
		<td>파라미터 그룹 `mc-mysql84` · 옵션 그룹 default:mysql-8-4 · 백업 보존 **7일** · 백업 창 **19:00–19:30 UTC**(04:00 KST) · 스냅샷에 태그 복사 · 로그 내보내기 **error** · 유지 관리 창 **일 20:00–20:30 UTC** · 마이너 자동 업그레이드 끔 · Performance Insights 끔(t3.small 미지원) · 삭제 방지 **끔**(실습; 운영이면 켬)</td>
	</tr>
	<tr>
		<td>태그</td>
		<td>Tier=db · Data=pii · Name=mc-petclinic</td>
	</tr>
</table>
생성 10~15분. **RDS Proxy 를 만들려면 이 인스턴스가 사용 가능 상태**여야 한다. 확인: 연결 탭 엔드포인트 `mc-petclinic.c7ku4mw88shn.ap-northeast-2.rds.amazonaws.com`, 구성 탭 "다중 AZ: 예", 보조 AZ.
왜 Multi-AZ: 동기 복제(RPO 0), 장애 시 60~120초 안에 자동 전환, 엔드포인트 동일. 9/16 실측 Primary 2c / Standby 2a.

# ⑨ Secrets ×2 · RDS Proxy · KMS · Backup
> 선행: ⑧ · 0-3 mc-rds-proxy-role · 0-6 app-db 비밀 · 코드 `rds.tf`
## 9-1. 비밀 2개가 왜 필요한가
<table header-row="true" fit-page-width="true">
	<tr>
		<td>비밀</td>
		<td>누가 만드나</td>
		<td>교체</td>
		<td>누가 쓰나</td>
	</tr>
	<tr>
		<td>`rds!db-…` (admin)</td>
		<td>RDS 가 자동</td>
		<td>**7일** 자동</td>
		<td>was.sh 부팅 시 앱 사용자 생성 · 운영 작업 · Proxy 인증 1</td>
	</tr>
	<tr>
		<td>`mc/petclinic/app-db` (petclinic_app)</td>
		<td>0-6 에서 수동</td>
		<td>없음</td>
		<td>WAS JDBC(WAR 에 빌드 시 주입) · Proxy 인증 2 · Bastion DB 접속</td>
	</tr>
</table>
admin 비밀만 쓰면 7일 뒤 교체 순간 WAR 안의 비밀번호와 Proxy 인증이 어긋나 앱이 끊긴다 → 교체 없는 앱 전용 사용자를 두고 최소 권한(`petclinic.*`)도 맞춘다.
## 9-2. RDS Proxy (RDS → 프록시 → 생성)
<table header-row="true" fit-page-width="true">
	<tr>
		<td>항목</td>
		<td>값</td>
	</tr>
	<tr>
		<td>이름 · 엔진</td>
		<td>`mc-rds-proxy` · MySQL</td>
	</tr>
	<tr>
		<td>**TLS 필요**</td>
		<td>켬 (파라미터 그룹 require_secure_transport 와 짝 · 앱 JDBC `sslMode=REQUIRED`)</td>
	</tr>
	<tr>
		<td>유휴 클라이언트 연결 제한</td>
		<td>**1,800초**(30분)</td>
	</tr>
	<tr>
		<td>대상 그룹</td>
		<td>DB 인스턴스 `mc-petclinic` · 연결 풀 최대 **90%** · 최대 유휴 50% · 대기 제한 120초</td>
	</tr>
	<tr>
		<td>인증</td>
		<td>Secrets Manager 비밀 **2개**: rds!db-… + mc/petclinic/app-db · IAM 인증 **비활성** · 역할 `mc-rds-proxy-role`</td>
	</tr>
	<tr>
		<td>연결</td>
		<td>서브넷 mc-db-a, mc-db-c · SG `mc-sg-rds-proxy`</td>
	</tr>
</table>
생성 5~10분. 대상 상태가 **AVAILABLE** 이 된 뒤에야 로그인이 된다(was.sh 가 그걸 기다림). 엔드포인트 예: `mc-rds-proxy.proxy-c7ku4mw88shn.ap-northeast-2.rds.amazonaws.com` → ⑦ was.sh 의 `jdbc_host`.
왜 Proxy: 커넥션 다중화(WAS 대수 × 풀 크기 가 DB 상한을 넘지 않게) · failover 중 앱 연결 유지 · 비밀은 Proxy 가 직접 읽음.
## 9-3. AWS Backup (AWS Backup → 볼트 · 백업 계획)
- 볼트 `mc-backup-vault` · 암호화 키 **mc-cmk**.
- 계획 `mc-rds-daily` → 규칙 `daily-7d`: 볼트 mc-backup-vault · 빈도 매일 · 시작 시간 **19:00 UTC**(04:00 KST) · 보존 **7일**. 리소스 할당: 역할 `mc-backup-role` · 리소스 유형 RDS · `mc-petclinic`.
RDS 자체 자동 백업(7일 · PITR 5분)과 별개로 **다른 볼트에 복구 지점**을 두는 것(실수 삭제·계정 사고 대비).

# ⑩ 계층별 로그 = 서버에 두지 않음
> 선행: 0-6 로그 그룹·파라미터 · 0-5 로그 버킷 · 코드 `observability.tf`
CloudWatch Logs 는 계정에 하나인 리전 서비스이고 **로그 그룹**만 계층별로 나눈다. 서버(EBS) 에 남기지 않고 만들자마자 밖으로 보내는 게 원칙 — 교체·축소해도 유실 없음.
<table header-row="true" fit-page-width="true">
	<tr>
		<td>로그</td>
		<td>만드는 곳</td>
		<td>어떻게 나가나</td>
		<td>저장소 · 보존</td>
		<td>켜는 곳</td>
	</tr>
	<tr>
		<td>Apache access·error</td>
		<td>WEB EC2</td>
		<td>CloudWatch Agent(user_data 설치)</td>
		<td>CW Logs `/mc/web/*` 30일</td>
		<td>Parameter Store `/mc/cwagent/web`</td>
	</tr>
	<tr>
		<td>Tomcat catalina·access·gc</td>
		<td>WAS EC2</td>
		<td>CloudWatch Agent</td>
		<td>CW Logs `/mc/was/*` 30일</td>
		<td>`/mc/cwagent/was`</td>
	</tr>
	<tr>
		<td>sshd 로그인</td>
		<td>Bastion</td>
		<td>CloudWatch Agent</td>
		<td>CW Logs `/mc/bastion/secure` 90일</td>
		<td>`/mc/cwagent/bastion`</td>
	</tr>
	<tr>
		<td>WAF 매치·차단</td>
		<td>Web ACL(us-east-1)</td>
		<td>WAF 로깅</td>
		<td>CW Logs `aws-waf-logs-mc` 30일</td>
		<td>② 로깅 활성화</td>
	</tr>
	<tr>
		<td>ALB 액세스</td>
		<td>Public·Internal ALB</td>
		<td>서비스가 5분마다 S3 로</td>
		<td>S3 `mc-logs/alb/public` · `alb/internal` 90일 (객체 .gz)</td>
		<td>④⑥ ALB 속성</td>
	</tr>
	<tr>
		<td>CloudFront 액세스</td>
		<td>CloudFront</td>
		<td>서비스가 S3 로(1시간 이내)</td>
		<td>S3 `mc-logs/cloudfront/` 90일</td>
		<td>② 표준 로깅</td>
	</tr>
	<tr>
		<td>RDS error · Proxy</td>
		<td>RDS</td>
		<td>자동</td>
		<td>CW Logs `/aws/rds/instance/mc-petclinic/error` · `/aws/rds/proxy/mc-rds-proxy`</td>
		<td>⑧ 로그 내보내기</td>
	</tr>
</table>
## 10-1. Parameter Store 값 (Systems Manager → Parameter Store → 파라미터 생성 · 표준 · String)
`/mc/cwagent/web`:

```json
{
  "agent": {"metrics_collection_interval": 60, "run_as_user": "root"},
  "logs": {"logs_collected": {"files": {"collect_list": [
    {"file_path": "/var/log/httpd/access_log", "log_group_name": "/mc/web/access", "log_stream_name": "{instance_id}", "timezone": "LOCAL"},
    {"file_path": "/var/log/httpd/error_log", "log_group_name": "/mc/web/error", "log_stream_name": "{instance_id}", "timezone": "LOCAL"}
  ]}}},
  "metrics": {"namespace": "MC/WEB", "append_dimensions": {"InstanceId": "${aws:InstanceId}", "AutoScalingGroupName": "${aws:AutoScalingGroupName}"},
    "metrics_collected": {"mem": {"measurement": ["mem_used_percent"]}, "disk": {"measurement": ["used_percent"], "resources": ["/"]}}}
}
```

`/mc/cwagent/was`:

```json
{
  "agent": {"metrics_collection_interval": 60, "run_as_user": "root"},
  "logs": {"logs_collected": {"files": {"collect_list": [
    {"file_path": "/opt/tomcat/logs/catalina.out", "log_group_name": "/mc/was/catalina", "log_stream_name": "{instance_id}", "timezone": "LOCAL"},
    {"file_path": "/opt/tomcat/logs/localhost_access_log.*.txt", "log_group_name": "/mc/was/access", "log_stream_name": "{instance_id}", "timezone": "LOCAL"},
    {"file_path": "/opt/tomcat/logs/gc.log", "log_group_name": "/mc/was/gc", "log_stream_name": "{instance_id}", "timezone": "LOCAL"}
  ]}}},
  "metrics": {"namespace": "MC/WAS", "append_dimensions": {"InstanceId": "${aws:InstanceId}", "AutoScalingGroupName": "${aws:AutoScalingGroupName}"},
    "metrics_collected": {"mem": {"measurement": ["mem_used_percent"]}, "disk": {"measurement": ["used_percent"], "resources": ["/"]}}}
}
```

`/mc/cwagent/bastion`:

```json
{
  "agent": {"metrics_collection_interval": 60, "run_as_user": "root"},
  "logs": {"logs_collected": {"files": {"collect_list": [
    {"file_path": "/var/log/secure", "log_group_name": "/mc/bastion/secure", "log_stream_name": "{instance_id}", "timezone": "LOCAL"}
  ]}}},
  "metrics": {"namespace": "MC/BASTION", "append_dimensions": {"InstanceId": "${aws:InstanceId}", "AutoScalingGroupName": "${aws:AutoScalingGroupName}"},
    "metrics_collected": {"mem": {"measurement": ["mem_used_percent"]}, "disk": {"measurement": ["used_percent"], "resources": ["/"]}}}
}
```

인스턴스는 부팅 스크립트 마지막에 `amazon-cloudwatch-agent-ctl -a fetch-config -m ec2 -c ssm:/mc/cwagent/‹tier› -s` 로 받아간다(권한은 0-3 인라인의 `ssm:GetParameter` + 관리형 CloudWatchAgentServerPolicy). 설정을 바꾸면 파라미터만 고치고 각 서버에서 같은 명령을 다시 실행.
확인: CloudWatch → 로그 그룹 `/mc/was/catalina` 에 스트림 = 인스턴스 ID 가 생기고, `aws logs tail /mc/was/catalina --since 10m`.

# ⑪ 감사 로그 — CloudTrail (계정 수준 · VPC 밖)
> 선행: 0-5 mc-cloudtrail 버킷(정책) · 0-4 KMS · 코드 `observability.tf` `kms_s3.tf`
CloudTrail → 추적 생성: 이름 `mc-trail` · 스토리지 **기존 버킷** `mc-cloudtrail-528821350786` · **SSE-KMS mc-cmk** · **로그 파일 검증 켬** · CloudWatch Logs 연결 안 함(로드맵) · 이벤트: **관리 이벤트(읽기+쓰기)** · 데이터 이벤트 없음 · **다중 리전 추적** · 글로벌 서비스 이벤트 포함.
버킷 정책(0-5) 에 `AWSCloudTrailAclCheck`(GetBucketAcl · 버킷) 와 `AWSCloudTrailWrite`(PutObject · `AWSLogs/528821350786/*` · `s3:x-amz-acl = bucket-owner-full-control`) 가 있어야 생성이 통과한다. KMS 키 정책엔 `cloudtrail.amazonaws.com` 가 GenerateDataKey/Decrypt 가능해야 함(0-4).
무엇을 기록하나: 누가(콘솔·CLI·Terraform) 어떤 AWS API 를 호출했나 — SG·RDS·IAM 변경 추적. 서버·에이전트와 무관하게 AWS API 서버에서 기록. 확인: `aws cloudtrail lookup-events --max-results 5`, 버킷에 `AWSLogs/…/CloudTrail/…json.gz`.

# ⑫ 관측 · 알림 — CloudWatch 알람 3 → SNS (Grafana · Slack 은 로드맵)
> 선행: ④⑥⑧ 의 ALB·대상 그룹·RDS · 0-4 KMS · 코드 `observability.tf`
1. **SNS → 주제** `mc-alerts` · 표준 · 암호화 **mc-cmk**. 구독: 이메일(팀원 주소) — 현재 0건 → 구독 후 확인 메일 승인 필요.
2. **CloudWatch → 알람 생성** 3개 (알람·정상 상태 전환 시 모두 `mc-alerts` 로 통보):
<table header-row="true" fit-page-width="true">
	<tr>
		<td>알람</td>
		<td>지표(네임스페이스)</td>
		<td>차원</td>
		<td>통계 · 기간</td>
		<td>조건</td>
	</tr>
	<tr>
		<td>mc-was-unhealthy-host</td>
		<td>UnHealthyHostCount (AWS/ApplicationELB)</td>
		<td>LoadBalancer = mc-alb-internal(app/… 접미사) · TargetGroup = mc-tg-was</td>
		<td>최대 · 60초 · 2/2</td>
		<td>≥ 1</td>
	</tr>
	<tr>
		<td>mc-alb-p95-latency</td>
		<td>TargetResponseTime (AWS/ApplicationELB)</td>
		<td>LoadBalancer = mc-alb-public</td>
		<td>**p95** · 60초 · 3/3</td>
		<td>› 2초</td>
	</tr>
	<tr>
		<td>mc-rds-connections-high</td>
		<td>DatabaseConnections (AWS/RDS)</td>
		<td>DBInstanceIdentifier = mc-petclinic</td>
		<td>평균 · 60초 · 3/3</td>
		<td>› 60 (t3.small max_connections ≈ 85 의 70%)</td>
	</tr>
</table>
차원의 LoadBalancer 값은 ALB ARN 의 `app/mc-alb-internal/…` 부분(콘솔 지표 탐색기에서 고르면 자동).
로드맵(회색): Amazon Managed Grafana(IAM Identity Center 필요) 대시보드 · Slack 은 Grafana Alerting 한 경로 · ASG 대상 추적.

# ⑬ 운영자 접속 = Bastion (SSM Session Manager 안 씀)
> 선행: 0-1 mc-public-a · 0-3 mc-ec2-profile · 코드 `modules/base/bastion.tf` `access.tf` `user_data/bastion.sh`
팀 결정(9/16 저녁): 보안팀 설득이 쉬운 전통 방식 — 퍼블릭 서브넷의 Bastion 1대에만 SSH 를 열고, 나머지는 Bastion 에서만 들어간다. SSM 은 **인스턴스 프로파일에 AmazonSSMManagedInstanceCore 를 붙이지 않고**, Session Manager 기본 설정 문서(`SSM-SessionManagerRunShell`)·`/mc/ssm/sessions` 로그 그룹도 만들지 않는다.
## 13-1. 키 페어 · SG
- **EC2 → 키 페어 생성** `mc-ssh` · 유형 **ED25519** · `.pem` 다운로드(개인키는 팀 채널로 안전하게 전달 · 저장소에 넣지 않음). 이 **한 키를 Bastion·WEB·WAS 모두에** 부착한다(⑤⑦ 생성 시 선택).
- `mc-sg-bastion`(0-2): 22 ← 운영자 공인 IP `/32`. `mc-sg-web`·`mc-sg-was` 에 22 ← mc-sg-bastion, `mc-sg-rds-proxy` 에 3306 ← mc-sg-bastion.
## 13-2. 인스턴스
<table header-row="true" fit-page-width="true">
	<tr>
		<td>항목</td>
		<td>값</td>
	</tr>
	<tr>
		<td>이름 · AMI · 유형</td>
		<td>`mc-bastion` · Amazon Linux 2023 · **t3.micro**</td>
	</tr>
	<tr>
		<td>네트워크</td>
		<td>mc-vpc · 서브넷 **mc-public-a** · 퍼블릭 IP **자동 할당 켬** · SG mc-sg-bastion · 키 mc-ssh</td>
	</tr>
	<tr>
		<td>스토리지 · 메타데이터</td>
		<td>gp3 8GiB 암호화 · IMDSv2 필수</td>
	</tr>
	<tr>
		<td>IAM 프로파일</td>
		<td>`mc-ec2-profile` (CW Agent 설정 조회 · 관리자가 비밀 조회)</td>
	</tr>
	<tr>
		<td>탄력적 IP</td>
		<td>할당 → 인스턴스에 연결(재부팅해도 주소 고정) — 현재 `52.78.145.87`</td>
	</tr>
	<tr>
		<td>사용자 데이터</td>
		<td>아래</td>
	</tr>
</table>
```bash
#!/bin/bash
# Bastion (AL2023) — 운영자 SSH 진입점 (SSM Session Manager 대신). WEB·WAS 는 같은 키로 -J 점프, DB 는 mariadb 클라이언트로 RDS Proxy(TLS) 경유
# sshd 로그(/var/log/secure)는 CloudWatch Agent 로 /mc/bastion/secure 에 남긴다 — 누가 언제 들어왔나 (서버에만 두지 않음)
set -uo pipefail
exec > >(tee -a /var/log/mc-userdata.log) 2>&1

dnf install -y mariadb105 jq amazon-cloudwatch-agent

for i in $(seq 1 12); do
  /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl -a fetch-config -m ec2 -c "ssm:/mc/cwagent/bastion" -s && { echo "cwagent configured"; break; }
  echo "cwagent config retry $i/12"; sleep 10
done

cat > /etc/motd <<'MOTD'
mc-bastion — WEB/WAS: ssh ec2-user@<사설 IP> (같은 키)  ·  DB: mysql --ssl -h <rds-proxy-endpoint> -u petclinic_app -p
MOTD
```

## 13-3. 쓰는 법

```bash
# Bastion
ssh -i mc-ssh.pem ec2-user@52.78.145.87
# WEB / WAS 로 점프 (같은 키 · 사설 IP 는 EC2 콘솔)
ssh -i mc-ssh.pem -J ec2-user@52.78.145.87 ec2-user@10.0.20.53
# DB (Bastion 안에서 · 비밀번호는 Secrets Manager 콘솔 "비밀 값 검색")
mysql --ssl -h mc-rds-proxy.proxy-c7ku4mw88shn.ap-northeast-2.rds.amazonaws.com -u petclinic_app -p petclinic
# DBeaver 등 로컬 툴: SSH 터널
ssh -i mc-ssh.pem -N -L 3306:mc-rds-proxy.proxy-c7ku4mw88shn.ap-northeast-2.rds.amazonaws.com:3306 ec2-user@52.78.145.87
```

로그: `/var/log/secure`(누가 언제 로그인했나·실패 시도) → `/mc/bastion/secure` 90일. 팀원이 늘면 SG 에 `/32` 규칙 추가, 나가면 삭제.

# 최종 검증 체크리스트

```bash
curl -s -o /dev/null -w "%{http_code}\n" https://petclinic.mission-critical.site/                      # 200 랜딩(Apache)
curl -s -o /dev/null -w "%{http_code} %{redirect_url}\n" https://petclinic.mission-critical.site/petclinic/   # 302 → /
curl -s -o /dev/null -w "%{http_code}\n" https://petclinic.mission-critical.site/petclinic/vets           # 200 (WAS → DB)
curl -sI https://petclinic.mission-critical.site/static/resources/css/petclinic.css | grep -iE "x-cache|server"   # server: AmazonS3
curl -sI https://petclinic.mission-critical.site/petclinic/resources/css/petclinic.css | grep -i x-cache          # Hit from cloudfront
curl -sk -m 8 -o /dev/null -w "%{http_code}\n" https://mc-alb-public-485062926.ap-northeast-2.elb.amazonaws.com/  # 타임아웃/403 = 차단
aws cloudfront get-distribution-config --id E2PWXW3LUYTDEE --query 'DistributionConfig.[WebACLId,Logging.Enabled]'   # WAF ARN · true
aws elbv2 describe-target-health --target-group-arn <mc-tg-was ARN> --query 'TargetHealthDescriptions[].TargetHealth.State'  # healthy healthy
aws logs describe-log-groups --log-group-name-prefix /mc --query 'logGroups[].logGroupName'                 # web·was·bastion 그룹
aws s3 ls s3://mc-logs-528821350786/cloudfront/ | tail -2                                                  # CloudFront 로그 객체
```

<callout icon="⚠️" color="yellow_bg">
	**주의**
	- 정적 파일(css·이미지)을 바꾸면 S3 업로드 + CloudFront 무효화(`/static/*` `/images/*` · WAR 쪽은 `/petclinic/resources/*`). 안 하면 하루(기본 TTL) 동안 옛것이 보인다.
	- Phase 3 부하 실험 전에 WAF IP set `mc-loadgen` 에 JMeter IP 를 넣지 않으면 rate-all(2,000/5분)이 발생기를 차단한다.
	- X-Origin-Verify 값 · DB 비밀번호 · mc-ssh.pem 은 노션·저장소에 적지 않는다.
	- 인스턴스에 **키 페어를 나중에 붙이는 건 불가**(교체 필요) — WEB·WAS 를 만들 때 처음부터 mc-ssh 를 고른다.
	- 이 페이지의 값은 코드(`infra/terraform-kdt5`) 가 원본. 콘솔로 만든 것과 코드가 어긋나면 `terraform plan` 이 차이를 보여준다.
</callout>
