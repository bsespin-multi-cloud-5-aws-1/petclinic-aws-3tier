# 9/18 계층별 미구현 정리 보고 — 양식 (항목 · 가이드 절 · 상태 · 필요 작업 · 소요h)

> 작성: 각 계층 담당이 **오늘 오전 중** 상태·소요h·비고를 채워 팀장에게 보고 → 취합 → Jira 등록. 항목은 🛠️ 콘솔 구축 가이드 절 번호 기준으로 미리 채워 두었고, "필요 작업"은 **없을 때** 기준이니 부분이면 남은 것만 적는다. 소요h 는 추정치(콘솔 클릭 기준)라 실측으로 고친다.
> 우선: **P0** = 없으면 시연 불가(9/21) · **P1** = 발표에 나오는 서비스(9/22) · **P2** = 로드맵 슬라이드. 비고엔 막힌 것·확인 방법(명령·화면).
> 같은 내용 CSV: `docs/report-9-18-gap-template.csv` (스프레드시트 · Jira CSV 가져오기).

## 작성 규칙
- 상태: **있음** = 가이드 값과 같게 동작 확인됨 · **부분** = 있으나 값·연결이 다름(무엇이 다른지 비고) · **없음** = 리소스 자체 없음
- 확인은 화면이 아니라 **동작**으로: 예) ALB 443 → `curl -sk https://‹alb-dns›/` 403(헤더 없음) · TG healthy · 로그 그룹에 스트림
- 이름·태그는 이 보고에서 다루지 않음(E4 · 9/22 규칙 확정 후)

## CDN · 보안 · 공통 — 팀장
| # | 항목 | 가이드 절 | 상태 | 필요 작업 (없을 때 기준) | 소요h | 우선 | 비고 |
|---|---|---|---|---|---|---|---|
| 1 | Route 53 호스팅 존 + 가비아 NS 위임 | ① | ☐ 있음 ☐ 부분 ☐ 없음 | 존 생성 → NS 4개 가비아 교체 → dig NS 확인 (전파 20~30분) | 0.5 | P0 | |
| 2 | A/AAAA alias → CloudFront | ①-3 | ☐ 있음 ☐ 부분 ☐ 없음 | 배포 생긴 뒤 레코드 2개 (alias 켬) | 0.2 | P0 | |
| 3 | ACM 인증서 us-east-1 (CloudFront 용) | ②-1 | ☐ 있음 ☐ 부분 ☐ 없음 | 요청 → Route 53 레코드 생성 → ISSUED | 0.3 | P0 | |
| 4 | ACM 인증서 서울 (ALB 443 용) | ④-1 | ☐ 있음 ☐ 부분 ☐ 없음 | 요청 → 같은 CNAME → ISSUED | 0.3 | P0 | |
| 5 | CloudFront 배포 (오리진 4 · Behavior 6 · 오류 응답 · OAC) | ②-3 | ☐ 있음 ☐ 부분 ☐ 없음 | OAC 생성 → 배포 생성(오리진 alb-public/s3-maintenance/s3-static/s3-static-images · Behavior 표 · 502/503/504 → /maintenance.html) → Deployed | 1.5 | P0 | |
| 6 | X-Origin-Verify (CloudFront 커스텀 헤더 = ALB 규칙 값) | ②-3 · ④-3 | ☐ 있음 ☐ 부분 ☐ 없음 | 비밀 문자열 하나를 두 곳에 동일 입력 | 0.2 | P0 | |
| 7 | Public ALB 443 리스너 · 기본 403 · 규칙10 · 80 리스너 없음 | ④-3 | ☐ 있음 ☐ 부분 ☐ 없음 | 443 리스너(서울 ACM · TLS13 정책) → 기본 고정 403 → 규칙 X-Origin-Verify → tg-web · 80 삭제 | 0.5 | P0 | |
| 8 | SG mc-sg-alb-public 443 ← CloudFront 프리픽스 목록 | 0-2 | ☐ 있음 ☐ 부분 ☐ 없음 | 소스 pl- CloudFront origin-facing · 0.0.0.0/0 규칙 삭제 | 0.2 | P0 | |
| 9 | S3 점검 페이지 버킷 + maintenance.html + OAC 정책 | 0-5 · 3-1 · 3-3 | ☐ 있음 ☐ 부분 ☐ 없음 | 버킷(KMS·퍼블릭 차단) → 객체 업로드 → 정책(배포 ARN) | 0.5 | P0 | |
| 10 | Bastion (t3.micro · EIP · 키 mc-ssh · SG 22 ← 팀 IP /32) | ⑬ | ☐ 있음 ☐ 부분 ☐ 없음 | 키 페어 → SG → 인스턴스(퍼블릭 A) → EIP 연결 → WEB/WAS SG 22 ← bastion | 0.7 | P0 | |
| 11 | WAF Web ACL (allow-loadgen · 관리형 3 · rate-all · rate-booking) + 배포 연결 | ②-2 | ☐ 있음 ☐ 부분 ☐ 없음 | IP set → Web ACL 규칙 6 → 로깅(aws-waf-logs-mc, us-east-1) → 배포 연결 | 1.0 | P1 | |
| 12 | S3 정적 자산 버킷 mc-static + 업로드 + /static/* /images/* Behavior | 3-2 | ☐ 있음 ☐ 부분 ☐ 없음 | 버킷 → resources·images 업로드(less 제외) → 정책 → Behavior 2개 S3 오리진 | 1.0 | P1 | |
| 13 | CloudFront 표준 로그 → S3 mc-logs/cloudfront/ | ②-3 | ☐ 있음 ☐ 부분 ☐ 없음 | 로그 버킷 ACL BucketOwnerPreferred → 표준 로깅 켬 | 0.3 | P1 | |
| 14 | CloudTrail mc-trail → S3 mc-cloudtrail (검증 · 다중 리전) | ⑪ | ☐ 있음 ☐ 부분 ☐ 없음 | 버킷 정책(AclCheck·Write) → 추적 생성 → 첫 객체 | 0.5 | P1 | |
| 15 | KMS 고객 관리형 키 mc-cmk (S3·SNS·Logs·Backup·app-db 비밀) | 0-4 | ☐ 있음 ☐ 부분 ☐ 없음 | 키 생성 → 키 정책 2문장(CloudFront·로그 서비스) → 각 리소스에 지정 | 0.7 | P2 | |
| 16 | IAM mc-ec2-role + 인라인 정책 · 인스턴스 프로파일 | 0-3 | ☐ 있음 ☐ 부분 ☐ 없음 | 역할 → CloudWatchAgentServerPolicy + 인라인(비밀 2·kms·ssm:GetParameter·s3) → WEB·WAS·Bastion 부착 | 0.5 | P0 | |
| 17 | CloudWatch 알람 3(+WEB HealthyHost) → SNS mc-alerts 이메일 4명 | ⑫ | ☐ 있음 ☐ 부분 ☐ 없음 | 주제 → 구독 4 → 승인 → 알람 4개 생성 → 테스트 1회 | 0.7 | P1 | |
| 18 | Bastion sshd 로그 → /mc/bastion/secure | ⑩ · 10-1 | ☐ 있음 ☐ 부분 ☐ 없음 | 로그 그룹 → 파라미터 /mc/cwagent/bastion → Agent fetch-config | 0.3 | P1 | |

소계: 항목 18 · 전부 없을 때 9.9h (P0 5.4h) — 있는 건 0 으로 고쳐 합산

## WEB — WEB 담당
| # | 항목 | 가이드 절 | 상태 | 필요 작업 (없을 때 기준) | 소요h | 우선 | 비고 |
|---|---|---|---|---|---|---|---|
| 1 | WEB 인스턴스 2대 (AZ a/c · t3.small · 프로파일 · 키 mc-ssh · 퍼블릭 IP 없음) | ⑤-1 | ☐ 있음 ☐ 부분 ☐ 없음 | 부족한 대수 추가 · 프로파일·키 부착(키는 생성 시만 → 없으면 교체) | 0.7 | P0 | |
| 2 | Apache: index.html 랜딩 + /static/ + ProxyPass /petclinic/ → Internal ALB + /health.html | ⑤-2 | ☐ 있음 ☐ 부분 ☐ 없음 | web.sh 그대로 user_data(LT 새 버전) → 인스턴스 새로 고침 / 또는 SSH 로 conf 반영 | 0.8 | P0 | |
| 3 | httpd.conf 기본 CustomLog 중복 제거 (헬스체크 필터 동작) | ⑤-2 | ☐ 있음 ☐ 부분 ☐ 없음 | 기본 CustomLog 주석 → conf.d 의 env=!nolog 하나만 → `?dup=1` 1줄 확인 | 0.2 | P1 | |
| 4 | mc-tg-web 헬스체크 /health.html 10s·5s·2/3 · 대상 2대 healthy | ④-2 | ☐ 있음 ☐ 부분 ☐ 없음 | TG 설정 확인 · 대상 등록 | 0.2 | P0 | |
| 5 | SG mc-sg-web: 80 ← alb-public · 22 ← bastion 만 | 0-2 | ☐ 있음 ☐ 부분 ☐ 없음 | 불필요 규칙(0.0.0.0/0 등) 삭제 | 0.2 | P0 | |
| 6 | CloudWatch Agent → /mc/web/access · /mc/web/error | ⑩ · 10-1 | ☐ 있음 ☐ 부분 ☐ 없음 | 로그 그룹 2 → 파라미터 /mc/cwagent/web → Agent 설치·fetch-config → 스트림 확인 | 0.5 | P1 | |
| 7 | ALB 액세스 로그 (외부·내부) → S3 mc-logs/alb/ | ④-3 · ⑥ | ☐ 있음 ☐ 부분 ☐ 없음 | 로그 버킷 정책(ALB 계정) → ALB 속성 켬 ×2 → 첫 객체 | 0.3 | P1 | |
| 8 | 시작 템플릿 $Latest · ASG 인스턴스 새로 고침 (ASG 로 운영 시) | ⑤-1 | ☐ 있음 ☐ 부분 ☐ 없음 | LT 새 버전 → ASG 기본 버전 → 새로 고침(50% 유지) | 0.5 | P2 | |

소계: 항목 8 · 전부 없을 때 3.4h (P0 1.9h) — 있는 건 0 으로 고쳐 합산

## WAS — WAS 담당
| # | 항목 | 가이드 절 | 상태 | 필요 작업 (없을 때 기준) | 소요h | 우선 | 비고 |
|---|---|---|---|---|---|---|---|
| 1 | WAS 인스턴스 2대 (AZ a/c · t3.medium · 프로파일 · 키 mc-ssh) | ⑦-1 | ☐ 있음 ☐ 부분 ☐ 없음 | 부족한 대수 추가 · 프로파일·키 | 0.7 | P0 | |
| 2 | Tomcat 9.0.121 · Corretto 8 · systemd · setenv(-Xmx1g · gc.log) | ⑦-2 | ☐ 있음 ☐ 부분 ☐ 없음 | was.sh 그대로 / 기존 설치면 setenv·systemd 만 확인 | 0.5 | P0 | |
| 3 | petclinic.war: JDBC = RDS Proxy 엔드포인트 · sslMode=REQUIRED · 사용자 petclinic_app (빌드 시 주입) | ⑦-2 | ☐ 있음 ☐ 부분 ☐ 없음 | app-db 비밀 조회 → `./mvnw -P MySQL -Djdbc.*` 재빌드 → 배포 → /petclinic/ 200 | 1.0 | P0 | |
| 4 | 부팅 대기 로직 (Proxy 로그인 성공까지 대기 · 404 면 재시작 3회) | ⑦-2 | ☐ 있음 ☐ 부분 ☐ 없음 | user_data 에 포함 (was.sh) — 수동 설치면 재시작 절차만 문서화 | 0.3 | P1 | |
| 5 | 풀 검증 testOnBorrow · 유휴 10분 회수 (datasource-config.xml) | ⑦-2 | ☐ 있음 ☐ 부분 ☐ 없음 | test 브랜치 소스에 포함 → 빌드 브랜치 확인 | 0.1 | P1 | |
| 6 | Internal ALB mc-alb-internal :8080 · mc-tg-was 헬스체크 /petclinic/ · SG 체인 | ⑥ · 0-2 | ☐ 있음 ☐ 부분 ☐ 없음 | TG 경로 슬래시 확인 · sg-alb-internal 8080 ← web · sg-was 8080 ← alb-internal · 22 ← bastion | 0.3 | P0 | |
| 7 | CloudWatch Agent → /mc/was/catalina · access · gc | ⑩ · 10-1 | ☐ 있음 ☐ 부분 ☐ 없음 | 로그 그룹 3 → /mc/cwagent/was → Agent → 스트림 | 0.5 | P1 | |
| 8 | /petclinic/test.jsp 로 WEB→WAS→DB 연동 확인 (Ssl_cipher · vets) | ⑦ | ☐ 있음 ☐ 부분 ☐ 없음 | curl 결과 캡처 | 0.1 | P0 | |
| 9 | JMeter 부하 테스트 준비 (계획서 · 발생기 IP → WAF IP set) | 4절 | ☐ 있음 ☐ 부분 ☐ 없음 | 시나리오·스레드·지표 정의 → IP set 등록 | 1.0 | P1 | |

소계: 항목 9 · 전부 없을 때 4.5h (P0 2.6h) — 있는 건 0 으로 고쳐 합산

## DB — DB 담당
| # | 항목 | 가이드 절 | 상태 | 필요 작업 (없을 때 기준) | 소요h | 우선 | 비고 |
|---|---|---|---|---|---|---|---|
| 1 | RDS mc-petclinic MySQL 8.4 · Multi-AZ · 암호화 · 백업 7일 · 퍼블릭 아니요 | ⑧-2 | ☐ 있음 ☐ 부분 ☐ 없음 | Multi-AZ 아니면 수정(재부팅) · 백업 보존 7 | 0.3 | P0 | |
| 2 | 파라미터 그룹 mc-mysql84 (require_secure_transport=1 · slow_query_log=1 · long_query_time=2 · utf8mb4) 적용 | ⑧-1 | ☐ 있음 ☐ 부분 ☐ 없음 | 그룹 생성 → RDS 수정 → 재부팅(정적 파라미터) → in-sync | 0.5 | P0 | |
| 3 | 앱 사용자 비밀 mc/petclinic/app-db (username·password · 교체 없음) | 0-6 | ☐ 있음 ☐ 부분 ☐ 없음 | Secrets Manager 다른 유형 → 값 입력 | 0.2 | P0 | |
| 4 | 앱 사용자 petclinic_app CREATE USER + petclinic.* 권한 | ⑦-2 | ☐ 있음 ☐ 부분 ☐ 없음 | Bastion 에서 admin 으로 CREATE USER IF NOT EXISTS · GRANT | 0.2 | P0 | |
| 5 | RDS Proxy mc-rds-proxy (TLS 필요 · 비밀 2개 · 역할 · SG proxy 3306 ← was/bastion · 대상 AVAILABLE) | ⑨-2 · 0-3 | ☐ 있음 ☐ 부분 ☐ 없음 | 역할 mc-rds-proxy-role → Proxy 생성 → 대상 AVAILABLE(5~10분) | 1.0 | P0 | |
| 6 | SG mc-sg-rds 3306 ← mc-sg-rds-proxy 만 (WAS 직결 규칙 제거) | 0-2 | ☐ 있음 ☐ 부분 ☐ 없음 | 기존 was→rds 3306 규칙 삭제 (Proxy 전환 확인 후) | 0.1 | P0 | |
| 7 | 로그 내보내기 error · slowquery → /aws/rds/instance/‹id›/* (보존 30일) | 10-2 | ☐ 있음 ☐ 부분 ☐ 없음 | 그룹 미리 생성(보존) → RDS 수정 → 내보내기 체크 → 슬로우 쿼리 1건 확인 | 0.4 | P1 | |
| 8 | RDS Proxy 로그 그룹 /aws/rds/proxy/‹name› 보존 30일 | 10-2 | ☐ 있음 ☐ 부분 ☐ 없음 | 자동 생성 그룹 보존 기간 편집 | 0.1 | P1 | |
| 9 | AWS Backup 볼트 mc-backup-vault + 계획 mc-rds-daily (04:00 KST · 7일) | 9-3 | ☐ 있음 ☐ 부분 ☐ 없음 | 역할 mc-backup-role → 볼트 → 계획 → 리소스 할당 | 0.4 | P1 | |
| 10 | 부하 테스트 중 DB 지표·slowquery 캡처 (DatabaseConnections · CPU) | 4절 | ☐ 있음 ☐ 부분 ☐ 없음 | 테스트 시간에 CloudWatch 그래프 캡처 | 0.3 | P1 | |
| 11 | (P2) CloudWatch Logs → Firehose → S3 cwlogs/db/ | 10-2 | ☐ 있음 ☐ 부분 ☐ 없음 | Firehose · 구독 필터 · IAM 2 | 1.0 | P2 | |

소계: 항목 11 · 전부 없을 때 4.5h (P0 2.3h) — 있는 건 0 으로 고쳐 합산

## 취합 (팀장 · 보고 4개 받은 뒤)
| 계층 | 항목 수 | 없음/부분 수 | P0 남은 h | P1 남은 h | 9/21 P0 완료 가능? | 비고 |
|---|---|---|---|---|---|---|
| CDN·보안 | 18 | | | | | |
| WEB | 8 | | | | | |
| WAS | 9 | | | | | |
| DB | 11 | | | | | |
- P0 합계가 담당자 1인당 하루 4h × 3일(9/19·20·21)을 넘으면 → 팀장이 P0 일부를 다른 담당에게 재배분 또는 P1 로 강등
- 취합 결과는 Jira E1 "취합·확정" 태스크에 첨부, 오늘 멘토링 보고서 "이슈 및 애로사항"에 P0 중 막힌 것만 옮김
