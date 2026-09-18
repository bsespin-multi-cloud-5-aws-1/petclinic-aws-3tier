# 멘토링 후기 → 결정 · 반영 계획 (2026-09-16)

> 멘토님 의견 6가지 + 추가 질문 2가지를 **"멘토 의견 → 우리 결정 → 코드/구성에서 바뀌는 것 → 영향(비용·운영) → 할 일"** 로 정리. 질문지는 ⑬, 개념은 ⑭, 현재 구성은 ⑪.

## 1. WAF는 관리가 어려워 뺀다
- **멘토**: 규칙 튜닝·오탐 대응에 손이 많이 가서 소규모 팀이 운영하기 어렵다.
- **결정**: **CloudFront는 유지, WAF만 제거.** CloudFront가 남는 이유(정적 캐시·오리진 은닉·5xx 점검 페이지·엣지 TLS)는 WAF와 무관하게 유효. Shield Standard(L3/4 DDoS)는 CloudFront에 기본 포함이라 그대로.
- **바뀌는 것**: `aws_wafv2_web_acl`·IP set·WAF 로그 그룹 제거, CloudFront `web_acl_id` 해제. 코드는 `enable_waf` 변수로 켜고 끌 수 있게 해 두어 "빼는 근거·다시 켜는 방법"을 발표에서 설명.
- **영향**: 비용 −$11/월. "예약 폭주" 1차 방어(rate-booking)가 사라지므로 폭주 대응은 **CloudFront 캐시 + RDS Proxy 풀링 + ASG 증설 + (선택) Apache `mod_ratelimit`/ALB 규칙**으로 설명. 로그 5종 → 4종.
- **할 일**: tfvars `enable_waf=false` → apply(CloudFront 업데이트 ~5분). 도면·⑪·⑫에서 WAF 제거.

## 2. ASG · SQS · Redis는 트레이드오프로 결정 — ASG는 잘 관리하면 좋다
- **멘토**: 무조건 넣지 말고 이득이 명확한 것만. ASG는 관리(AMI·헬스체크·증설 기준)를 잘 하면 가치가 크다.
- **결정**: **ASG 도입(WEB·WAS)**, **SQS·Redis 미도입 유지**(로그인·비동기 작업 없음, 코드 변경 필요 — ⑬ 3-3 근거 그대로).
- **바뀌는 것**: mc-deploy(`terraform-kdt5` create_base)의 고정 EC2 ×2 → 시작 템플릿 + ASG(WEB min2/max4 CPU 60%, WAS min2/max6 CPU 60% + 요청 수) · 인스턴스 새로 고침(Rolling 50%). Golden AMI와 묶어야 워밍업 8분 문제가 풀림 → **AMI v1 굽기가 선행**.
- **영향**: 평시 비용 동일(2대), 폭주 시 상한 ↑. 운영: LT 버전·AMI 갱신 절차 문서화.
- **할 일**: ① 현재 인스턴스에서 AMI v1(WEB·WAS) 생성 ② `modules/base`에 ASG 옵션 추가(`enable_asg`) ③ 부하 테스트로 증설 기준 산정.

## 3. SSM — 보안팀 설득이 어려워 실무에선 Bastion을 쓴다
- **멘토**: 원칙은 SSM이 맞지만 현장에선 보안팀 정책(접속 통제 장비·망 분리)이 Bastion을 요구하는 경우가 많다.
- **결정**: **코드 기본은 SSM 유지 + Bastion을 옵션으로 제공.** 발표는 "SSM으로 22번 포트·키를 없앴고, 조직 정책이 요구하면 Bastion을 켤 수 있다(한 줄 변수)"로.
- **바뀌는 것**: `terraform-kdt5`에 `create_bastion`(phase1과 동일 패턴: 퍼블릭 서브넷 t3.micro, SG 22 ← 팀 IP, WEB/WAS SG 22 ← bastion) 옵션 추가. kdt5 콘솔 구축본은 이미 Bastion 사용 중이라 그대로.
- **영향**: Bastion 켜면 +$8/월, 키 관리·패치 부담. SSM 세션 로그(`/petclinic/ssm/sessions`)는 Bastion 경로엔 안 남으므로 Bastion을 쓰면 **CloudTrail + Bastion의 sshd 로그**로 보완.
- **할 일**: 옵션 코드 추가(적용은 팀 결정).

## 4. KMS · S3 보안(SSE-S3 등)
- **멘토**: 저장 암호화를 어떻게 하고 있는지 명확히.
- **현재**: 이미 적용됨 —
  | 대상 | 암호화 | 키 |
  |---|---|---|
  | S3 점검 페이지 · CloudTrail 버킷 | SSE-KMS + 버킷 키 | `alias/mc-cmk`(고객 관리형, 자동 교체) |
  | S3 로그 버킷(ALB 액세스 로그) | SSE-S3(AES-256) | AWS 관리 — ALB 로그 전송이 SSE-KMS를 지원하지 않아 SSE-S3 |
  | RDS 스토리지 · 스냅샷 | 저장 암호화 | `aws/rds` |
  | Secrets Manager | 암호화 | `aws/secretsmanager` |
  | CloudWatch Logs 6그룹 · SNS · Backup 볼트 | KMS | `alias/mc-cmk` |
  | EBS 루트 볼륨(WEB·WAS) | 암호화 | 계정 기본 키 |
  | 전송 중 | CloudFront TLS1.2+ · ALB 443 · Proxy TLS · 버킷 정책 `aws:SecureTransport` Deny | |
- **결정**: 유지. 발표 슬라이드에 위 표 한 장. 로드맵: EBS를 CMK로 통일, S3 Object Lock(감사 로그 변조 방지).

## 5. NAT Gateway 2개가 맞다 — 업데이트가 잦지 않은 웹서비스라서
- **멘토**: 아웃바운드가 적어도 AZ 장애 때 다른 AZ가 살아야 하므로 AZ당 1개가 맞다.
- **결정**: **2개 유지**(현재 그대로). 비용 절감은 NAT가 아니라 다른 곳(WAF 제거, WEB 계층 축소 검토)에서.
- **할 일**: 없음. 로드맵에 "Secrets Manager·SSM VPC 엔드포인트로 NAT 전송량 축소" 한 줄.

## 6. WAS에서 EFS — Root와 Data를 나누고 init script · AMI를 어떻게 할지
- **멘토**: OS/런타임(Root)과 앱 데이터(Data)를 분리하고, 여러 WAS가 공유해야 하는 것은 EFS로.
- **우리 상황**: PetClinic은 파일 업로드가 없어 **공유가 필요한 데이터가 거의 없음**. 공유하면 좋은 것은 ① 빌드된 `petclinic.war`(지금은 대당 8분씩 각자 빌드) ② Tomcat 설정(`context.xml` — JNDI로 가면 DB 정보) ③ 세션(스티키 없음이라 불필요). 로그는 CloudWatch로 보내므로 EFS 불필요.
- **설계안**:
  | 계층 | 어디에 | 내용 | 만드는 방법 |
  |---|---|---|---|
  | Root(EBS gp3 20GB) | AMI | AL2023 + Corretto 8 + Tomcat 9.0.121 + CW Agent + `amazon-efs-utils` | Golden AMI v1 (설치만, WAR·비밀 없음) |
  | Data(EFS, 두 AZ 마운트 타깃) | `/mnt/petclinic` | `releases/petclinic-<ver>.war`, `conf/context.xml`(Proxy 엔드포인트), `current` 심링크 | 빌드 서버(또는 WAS 1대)가 한 번 빌드해 올림. 롤백 = 심링크만 바꿈 |
  | init script(user_data) | 부팅 시 | `mount -t efs -o tls fs-xxx:/ /mnt/petclinic` → `ln -s /mnt/petclinic/current /opt/tomcat/webapps/petclinic.war` → `context.xml` 복사 → Secrets 조회는 JNDI면 불필요(비밀은 EFS 대신 Secrets Manager에서 Tomcat이 읽도록) → `systemctl start tomcat` — **8분 → 1분** | |
- **주의**: EFS에 **비밀번호를 두지 말 것**(context.xml에 비밀번호가 들어가면 EFS가 비밀 저장소가 됨) → JNDI 리소스의 password는 부팅 시 Secrets Manager에서 받아 로컬 파일로 씀. EFS는 SG 2049 ← `mc-sg-was`만, 저장 암호화(KMS) + 전송 TLS(`-o tls`). 성능 모드 General Purpose·처리량 Elastic이면 WAR 읽기엔 충분. Tomcat이 EFS 위 WAR를 직접 펼치면 느릴 수 있어 **로컬 EBS로 복사 후 배포**가 안전(`cp` 한 줄).
- **비용**: EFS 1GB ≈ $0.3/월 + 마운트 타깃 무료. **운영**: 릴리스 디렉터리 관리·심링크 전환 절차.
- **결정**: **Phase 2 후반 로드맵**. 지금 우선순위는 ASG + AMI v1이고, EFS는 "WAR 공유·즉시 롤백"이 필요해질 때(부하 테스트 반복 시점) 도입. 코드 골격은 `enable_efs` 옵션으로 준비.

---

## Extra 1. CloudWatch Logs — 목적 · 이유 · 어디서 쓰나
- **목적**: 서버 **안**에 있는 로그를 서버 **밖**에 모아 두고 검색·알람·보관하는 것.
- **이유**: ASG로 서버가 늘고 줄면 서버 안 로그는 사라진다. 여러 대의 로그를 한 화면(Logs Insights)에서 시간순으로 봐야 장애 원인을 찾는다. 알람(지표 필터)·대시보드(Grafana)·보관 기간(30/90일)·암호화(KMS)를 한곳에서 관리.
- **어디서 쓰나(우리 구성)**:
  | 소스 | 로그 그룹 | 보내는 주체 |
  |---|---|---|
  | WEB Apache access/error | `/petclinic/web/access` `/petclinic/web/error` | CloudWatch Agent(EC2 안) |
  | WAS Tomcat catalina/access/gc | `/petclinic/was/catalina` `/petclinic/was/access` `/petclinic/was/gc` | CloudWatch Agent |
  | SSM 세션 기록 | `/petclinic/ssm/sessions` | Session Manager |
  | (제거 예정) WAF | `aws-waf-logs-mc` | WAF |
  | RDS 에러 로그 | `/aws/rds/instance/mc-petclinic/error` | RDS 내보내기 |
  | CloudWatch 알람 3개(WAS unhealthy · ALB p95 · RDS 연결) | → SNS `mc-alerts` | 지표 기반(로그 그룹과 별개) |
- **안 쓰는 곳**: ALB 액세스 로그(S3 전용) · CloudTrail(S3, 필요 시 CW Logs 연결 가능).

## Extra 2. CloudTrail — 목적 · 이유 · 어디서 쓰나
- **목적**: "**누가, 언제, 어떤 AWS API를 호출했나**"의 감사 기록. 앱 로그가 아니라 **AWS 계정 조작 기록**(콘솔 클릭·CLI·Terraform·서비스 간 호출 전부).
- **이유**: 사고 조사("누가 SG를 열었나", "RDS를 누가 재부팅했나"), 규정(개인정보 취급 시스템의 접근 기록 보관), 변경 추적(Terraform apply도 남음). 기본 90일 이벤트 기록은 무료지만 콘솔에서만 보이고 계정을 넘어 보관이 안 되므로 **추적(Trail)** 을 만들어 S3에 1년 보관.
- **어디서 쓰나(우리 구성)**: 추적 `mc-trail` — 다중 리전·글로벌 서비스(IAM·CloudFront) 포함·**로그 파일 검증**(변조 감지) → S3 `mc-cloudtrail-<acct>`(KMS·버저닝·CloudTrail만 쓰기·90일 후 Glacier IR·1년 만료). 기록되는 것: EC2/RDS/ALB/IAM/Secrets Manager 등 **모든 관리 이벤트**(예: `GetSecretValue` 호출자, `ModifyDBInstance`, `AuthorizeSecurityGroupIngress`). 기록 안 하는 것: S3 객체 읽기/쓰기 같은 데이터 이벤트(진료 파일 저장을 뺐으므로 불필요), RDS 안의 SQL.
- **CloudWatch Logs와의 차이**: CloudWatch Logs = 서버·서비스가 **동작하며 남기는 로그**, CloudTrail = AWS **조작 감사**. 둘 다 "로그 5종"에 들어가지만 보는 목적이 다르다.
