# 최종 스프린트 — 콘솔 구축 마무리 → 테스트 → 네이밍·태그 → PPT·시연 영상 → 리허설 (9/18 → 10/1)

> 팀장 방침(9/18): 한 계정 · 콘솔 · "돌아가면 됨" · 초점은 발표·Q&A. 발표는 **전체 흐름을 각자 파트로 나눠** 발표(전체 이해는 간략히). 지라에 일정·할 일을 만들고 각자 체크리스트로 관리.
> 남은 멘토링: **9/18(오늘) · 9/22(화)** + 10/1 발표. OT 마감: 초안 9/30 09:00 · 리허설 9/30 11:30 · 최종 10/1 09:00 · 발표 10/1 11:30.
> Jira 가져오기: `docs/jira-final-sprint.csv` (에픽 6 · 태스크 36 · 서브태스크 81 = 체크리스트). Jira → 프로젝트 설정 → **외부 시스템 가져오기 → CSV** → 담당자는 `팀장(박준석)/WEB 담당/WAS 담당/DB 담당/시연 담당/전원` 을 실제 계정에 매핑, 날짜 형식 `yyyy-MM-dd`. `Parent Id` 로 에픽→태스크→서브태스크가 이어진다.

## 0. 흐름 한 줄
**9/18 계층별 미구현 정리·보고 → 취합** → **9/19~21 콘솔 구현 마무리(로그 수집 · 시나리오 통과)** → **9/21~22 JMeter 읽기·쓰기 부하 테스트** → **9/22 멘토링** → **9/22~23 네이밍·태그 정리 + 트러블슈팅 보고** → **9/24~28 PPT·시연 영상**(추석은 원격) → **9/28~29 리허설·모의 Q&A → [초안] 업로드** → 9/30 공식 리허설·[최종] → 10/1 발표

| 마감 | 완료 기준 |
|---|---|
| **9/18(금)** | 4개 계층 미구현 보고 → 취합 · Jira 등록 · 멘토링 |
| **9/21(월)** | 로그 수집 전부 켜짐 · 시나리오 A·B 1회 통과·캡처 |
| **9/22(화)** | 부하 테스트 결과 캡처 · 멘토링 · 네이밍 규칙 확정 → **인프라 변경 종료** |
| **9/23(수)** | 이름·태그 적용 완료 · 트러블슈팅 4개 보고 취합 · 슬라이드 골격 |
| **9/28(월)** | PPT 20장 · 시연 영상 삽입 · 리허설 1 · 모의 Q&A 1 |
| **9/29(화)** | 리허설 2·3 · 모의 Q&A 2·3 · **[초안] 업로드** (기한 9/30 09:00 을 앞당김) |
| 9/30 → 10/1 | 공식 리허설 → [최종] 저녁 업로드 → 발표 |

## 1. 9/18 보고 양식 (계층별 미구현 정리 — 각자 오전 중 작성)
| 항목 | 가이드 절 | 상태(있음/부분/없음) | 필요한 작업 | 소요(h) | 마감 | 비고 |
|---|---|---|---|---|---|---|
| 예) RDS Proxy | ⑨-2 | 없음 | 생성 · 비밀 2개 인증 · SG 3306 | 1.5 | 9/18 | 앱 사용자 먼저 |
- 참조: 🛠️ 콘솔 구축 가이드(①~⑬ · 값 그대로) · `MANUAL-FOLLOWUPS.md` ⓜ1~7 · 이 문서 3절(로그 수집 정의)
- 취합 기준: **P0** = 없으면 시연 불가 → 9/21 · **P1** = 발표에 나옴 → 9/22 · **P2** = 로드맵 슬라이드

## 2. Jira 항목 (CSV 와 동일 · 서브태스크는 CSV 참조)
| ID | 유형 | 항목 | 담당 | 마감 |
|---|---|---|---|---|
| 1 | **에픽** | E1 계층별 현황·미구현 정리 → 취합 (9/18) | 팀장(박준석) | 09/18 |
| 2 | 태스크 | CDN·보안 계층 미구현 정리 보고 | 팀장(박준석) | 09/18 |
| 11 | 태스크 | WEB 계층 미구현 정리 보고 | WEB 담당 | 09/18 |
| 17 | 태스크 | WAS 계층 미구현 정리 보고 | WAS 담당 | 09/18 |
| 24 | 태스크 | DB 계층 미구현 정리 보고 | DB 담당 | 09/18 |
| 31 | 태스크 | 취합·확정 → Jira 등록 · 오늘 멘토링 보고서 | 팀장(박준석) | 09/18 |
| 35 | **에픽** | E2 콘솔 구현 마무리 — 로그 수집(CloudWatch Logs · S3) + 시연 시나리오 통과 (9/19~9/21) | 팀장(박준석) | 09/21 |
| 36 | 태스크 | WEB 로그 수집: /petclinic/web/access · /petclinic/web/error | WEB 담당 | 09/20 |
| 40 | 태스크 | WAS 로그 수집: /petclinic/was/catalina · access · gc | WAS 담당 | 09/20 |
| 43 | 태스크 | DB 로그 수집: RDS error · slowquery · Proxy 로그 | DB 담당 | 09/20 |
| 46 | 태스크 | 공통 로그: Bastion sshd → /petclinic/bastion/secure · CloudTrail → S3 · CloudFront 로그 → S3 | 팀장(박준석) | 09/20 |
| 51 | 태스크 | (P2) CloudWatch Logs → Firehose → S3 사본 (10-2) | 팀장(박준석) | 09/22 |
| 53 | 태스크 | 알람 3 + SNS 이메일 4명 구독·승인 · WEB HealthyHost 알람 추가 | 팀장(박준석) | 09/21 |
| 56 | 태스크 | 시연 시나리오 A(정상 흐름) · B(장애·복구) 1회 통과 + 캡처 | 시연 담당 | 09/21 |
| 60 | **에픽** | E3 JMeter 읽기·쓰기 부하 테스트 (9/21~9/22) | WAS 담당 | 09/22 |
| 61 | 태스크 | 부하 테스트 계획서 1장 | WAS 담당 | 09/21 |
| 65 | 태스크 | 부하 테스트 실행 + 지표 캡처 | WAS 담당 | 09/22 |
| 69 | 태스크 | 결과 정리 1장: 병목·한계·개선안(ASG·Read Replica·캐시) | WAS 담당 | 09/22 |
| 70 | **에픽** | E4 네이밍·태그 정리 + 계층별 트러블슈팅 정리 보고 (9/22~9/23) | 팀장(박준석) | 09/23 |
| 71 | 태스크 | 네이밍·태그 규칙 확정 + 재생성 필요 목록 공지 | 팀장(박준석) | 09/22 |
| 74 | 태스크 | 이름·태그 적용 — 팀장 | 팀장(박준석) | 09/23 |
| 76 | 태스크 | 이름·태그 적용 — WEB 담당 | WEB 담당 | 09/23 |
| 78 | 태스크 | 이름·태그 적용 — WAS 담당 | WAS 담당 | 09/23 |
| 80 | 태스크 | 이름·태그 적용 — DB 담당 | DB 담당 | 09/23 |
| 82 | 태스크 | 트러블슈팅 정리 보고 — CDN·보안·공통 | 팀장(박준석) | 09/23 |
| 85 | 태스크 | 트러블슈팅 정리 보고 — WEB | WEB 담당 | 09/23 |
| 88 | 태스크 | 트러블슈팅 정리 보고 — WAS | WAS 담당 | 09/23 |
| 91 | 태스크 | 트러블슈팅 정리 보고 — DB | DB 담당 | 09/23 |
| 94 | 태스크 | 트러블슈팅 취합 보고 + 슬라이드 18 초안 | 팀장(박준석) | 09/23 |
| 95 | **에픽** | E5 발표 자료(구글슬라이드 지정 양식) + 시연 영상 (9/23~9/28) | 팀장(박준석) | 09/28 |
| 96 | 태스크 | 지정 양식 확보 · 20장 골격(제목+담당) · 개요·아키텍처·흐름 슬라이드 1~8 | 팀장(박준석) | 09/24 |
| 98 | 태스크 | 파트 슬라이드 9~10 — WEB | WEB 담당 | 09/28 |
| 102 | 태스크 | 파트 슬라이드 11~12 — WAS | WAS 담당 | 09/28 |
| 106 | 태스크 | 파트 슬라이드 13~14 — DB | DB 담당 | 09/28 |
| 110 | 태스크 | 슬라이드 15~20: 로그 흐름 · 보안 · 트러블슈팅 · 부하 테스트 결과 · 비용·트레이드오프 · 로드맵 | 팀장(박준석) | 09/28 |
| 111 | 태스크 | 시연 영상: 콘티 → 촬영(A 1분 + B 1.5분) → 편집 → 슬라이드 삽입 → 재생 확인 · 플랜B 파일 | 시연 담당 | 09/28 |
| 115 | **에픽** | E6 리허설 · 모의 Q&A · 제출 (9/28~10/1) | 팀장(박준석) | 10/01 |
| 116 | 태스크 | 자체 리허설 1 + 모의 Q&A 1 (타이머 15분 · 이름 먼저 · 화면 전환) | 팀장(박준석) | 09/28 |
| 117 | 태스크 | 개인 Q&A 15문 답 작성(자기 파트) → 팀 뱅크 60문 | 전원 | 09/28 |
| 118 | 태스크 | 리허설 2·3 + 모의 Q&A 2·3 (온라인 → 현장 순서 흉내) · [초안] 업로드 | 팀장(박준석) | 09/29 |
| 120 | 태스크 | 공식 리허설 9/30 11:30~12:10 → 수정 → [최종] 저녁 업로드 | 팀장(박준석) | 09/30 |
| 123 | 태스크 | 발표 당일: 09:00 제출 확인 · 10:30 사이트·zoom·공용 노트북 점검 · 11:25 대기 · 11:30 발표 | 팀장(박준석) | 10/01 |

## 3. "무엇을 수집하나" — 로그 수집 정의 (E2 의 기준)
| 계층 | 소스 | 어디로 | 그룹·경로 | 보존 | 켜는 곳 |
|---|---|---|---|---|---|
| WEB | Apache access_log · error_log | CloudWatch Logs (Agent) | /petclinic/web/access · /petclinic/web/error | 30일 | Parameter Store /petclinic/cwagent/web → fetch-config |
| WAS | catalina.out · localhost_access_log · gc.log | CloudWatch Logs (Agent) | /petclinic/was/catalina · access · gc | 30일 | /petclinic/cwagent/was |
| DB | RDS error · slowquery(2s) · RDS Proxy | CloudWatch Logs (서비스 내보내기) | /aws/rds/instance/‹id›/error · /slowquery · /aws/rds/proxy/‹name› | 30일 | RDS 수정 → 로그 내보내기 · 파라미터 slow_query_log=1 |
| CDN·보안 | CloudFront 표준 로그 | S3 객체 | mc-logs/cloudfront/ | 90일 | 배포 → 표준 로깅(버킷 ACL 활성 필요) |
| CDN·보안 | WAF 규칙 매치·차단 | CloudWatch Logs (us-east-1) | aws-waf-logs-mc | 30일 | Web ACL → 로깅 |
| WEB·WAS | ALB 액세스 로그(외부·내부) | S3 객체 | mc-logs/alb/public · alb/internal | 90일 | ALB 속성 |
| 공통 | CloudTrail 관리 이벤트 | S3 객체 | mc-cloudtrail-‹acct›/AWSLogs/ | 1년 | 추적 mc-trail |
| 공통 | Bastion sshd | CloudWatch Logs (Agent) | /petclinic/bastion/secure | 90일 | /petclinic/cwagent/bastion |
| (P2) | CloudWatch Logs 전부 | S3 사본 (Firehose) | mc-logs/cwlogs/‹tier›/ | 1년 | 구독 필터 → Firehose ×4 |
확인 명령: `aws logs describe-log-groups --log-group-name-prefix /mc` · `aws logs tail /petclinic/was/catalina --since 10m` · `aws s3 ls s3://mc-logs-‹acct›/alb/public/ --recursive | tail -3`

## 4. JMeter 읽기·쓰기 부하 테스트 (E3)
- 읽기: `GET /petclinic/vets` · `GET /petclinic/owners?lastName=` (검색 → DB 조회) · 쓰기: `POST /petclinic/owners/new` (firstName·lastName·address·city·telephone 폼)
- 설정: 스레드 50 · 램프 60s · 10분 · 읽기 70% / 쓰기 30% · HTTP Cookie Manager · 응답 assertion 200
- **발생기 공인 IP 를 WAF IP set `mc-loadgen` 에 먼저 등록**(rate-all 2,000/5분·rate-booking 100/5분이 차단) · 끝나면 제거
- 관측: ALB TargetResponseTime p95 · HTTPCode 5xx · WAS CPU·mem(MC/WAS) · RDS DatabaseConnections(알람 60)·CPU · Proxy 연결 · slowquery 건수 · (ASG면) 인스턴스 수 → 그래프 5장 캡처
- 결과 1장: 요청 수·오류율·p95 · 병목(예: WAS CPU 먼저 vs DB 연결 먼저) · 개선안(ASG · Read Replica · 캐시) — 슬라이드 19

## 5. 네이밍·태그 규칙 + "바꿔야 할 것만" (E4)
- 이름: `mc-<계층>-<역할>[-<az>]` — 예 `mc-web-a` `mc-was-c` `mc-alb-public` `mc-tg-was` `mc-sg-rds-proxy` `mc-rds-proxy` `mc-bastion` `mc-trail` `mc-alerts`
- 태그(전 리소스 공통): `Project=mission-critical` `Team=AWS1` `Tier=edge|web|was|db|ops` `Owner=<이름>` `Env=prod` `ManagedBy=console`
| 리소스 | 이름 변경 | 권장 |
|---|---|---|
| EC2 · EBS · CloudWatch 알람 · Backup 계획 | Name 태그/이름 즉시 변경 가능 | 바꾼다 |
| SG · TG · ALB · IAM 역할 · S3 버킷 · Secrets · 로그 그룹 · Route 53 존 · WAF ACL · Proxy · 파라미터 그룹 | **이름 불변** → 재생성해야 바뀜 | **Name 태그만**. 재생성은 팀장 승인(ALB 재생성 = CloudFront 오리진·Apache ProxyPass DNS 변경 → WEB 새로 고침) |
| RDS 식별자 | 변경 가능하나 **엔드포인트 변경 + Proxy 대상 재등록** | 안 바꿈 · Name 태그 |
| CloudFront | 이름 없음 · 설명(comment)만 | 설명에 `mc-cloudfront` |

## 6. 트러블슈팅 사전 목록 (각 담당이 확인·보강해 9/23 보고 · 실제 겪은 건 스크린샷 첨부)
### CDN·보안·공통 (팀장)
| 발생 지점 | 증상 | 원인 | 해결 | 확인 |
|---|---|---|---|---|
| ACM | 검증 pending 계속 | 가비아 NS 미전파 / CNAME 없음 | `dig NS` 확인 · Route 53 에서 레코드 생성 · 20~30분 | ACM 상태 ISSUED |
| CloudFront 기본 도메인 | 403 | alias 만 허용(Host 불일치) | 도메인으로 접속 | `curl -sI https://petclinic…` 200 |
| CloudFront → ALB | 502/503 → 점검 페이지 | ALB SG 프리픽스 누락 / X-Origin-Verify 값 불일치(기본 403) | SG 443 ← 프리픽스 · 헤더 값 두 곳 동일 | ALB 액세스 로그 403 여부 |
| CloudFront → S3 정적 | 403 | AllViewer 로 Host 전달 → 서명 불일치 / 버킷 정책 SourceArn | 캐시 정책만 · 정책에 배포 ARN | `server: AmazonS3` 200 |
| 정적 파일 교체 | 옛 css 보임 | 캐시 1일 | 무효화 `/static/*` `/images/*` | x-cache Miss → Hit |
| WAF | JMeter·스캐너 차단 | rate-all 2,000/5분 | 발생기 IP → allow IP set | aws-waf-logs-mc action=BLOCK |
| CloudTrail 생성 | 정책 오류 | 버킷 정책 AclCheck·Write 누락 | 0-5 정책 | 첫 객체 |
| CloudFront 로그 | 객체 안 생김 | 버킷 ACL 비활성 | BucketOwnerPreferred | cloudfront/ 객체 |
| Bastion | SSH 타임아웃 | 공인 IP 바뀜 / 키 권한 | SG /32 갱신 · chmod 600 | ssh 접속 |
| SNS | 알람 메일 없음 | 구독 미승인 | 확인 메일 승인 | 구독 Confirmed |
### WEB
| 발생 지점 | 증상 | 원인 | 해결 | 확인 |
|---|---|---|---|---|
| TG 헬스체크 | unhealthy → 503 | /health.html 없음 / ProxyPass 가 먼저 잡음 | `echo ok > health.html` · `ProxyPass /health.html !` 를 위에 | TG healthy |
| Apache 프록시 | 503 | SELinux `httpd_can_network_connect` | setsebool -P 1 | 502/503 사라짐 |
| 랜딩 자산 | css·영상 404 | 상대 경로 / S3 Behavior 없음 | `/static/` Alias·CloudFront `/static/*` | 200 |
| 로그 | CloudWatch 스트림 없음 | 프로파일 미부착 / 파라미터 권한 | mc-ec2-profile · ssm:GetParameter | `describe-log-streams` |
| 로그 | 요청당 2줄 · 헬스체크 줄 남음 | httpd.conf 기본 CustomLog 중복 | 기본 CustomLog 주석 → conf.d 하나만 | `?dup=1` 1줄 |
| ASG | 새 LT 버전 미반영 | $Latest 이지만 기존 인스턴스 유지 | 인스턴스 새로 고침 | 새 인스턴스 ID |
### WAS
| 발생 지점 | 증상 | 원인 | 해결 | 확인 |
|---|---|---|---|---|
| 부팅 | `Access denied for user petclinic_app` → 404 | Proxy 인증 목록 반영 전 기동 | Proxy 경유 로그인 성공까지 대기 · 404면 재시작 | catalina.out |
| 부팅 | `Communications link failure` | Proxy 대상 AVAILABLE 전 | 대기 루프 | Proxy 대상 상태 |
| 30분 유휴 후 | `JDBC begin transaction failed` | Proxy idle_client_timeout 이 풀 연결 끊음 | testOnBorrow SELECT 1 · 유휴 10분 회수 | 재현 안 됨 |
| TG 헬스체크 | unhealthy | `/petclinic`(슬래시 없음) → 301 | `/petclinic/` | healthy |
| 빌드 | mysql-connector 없음 / 메모리 부족 | 8.0.44 아티팩트 없음 · t3.micro | pom 8.4.0 · t3.medium | BUILD SUCCESS |
| JDBC | 접속 거부 | sslMode=REQUIRED 누락(Proxy require_tls) | URL 에 sslMode=REQUIRED | test.jsp Ssl_cipher |
| 2대 동시 부팅 | schema 경합 우려 | — | schema IF NOT EXISTS · INSERT IGNORE 라 멱등(실측 OK) | vets 6 |
### DB
| 발생 지점 | 증상 | 원인 | 해결 | 확인 |
|---|---|---|---|---|
| 파라미터 그룹 | pending-reboot | 정적 파라미터 | 재부팅(장애 조치 포함) 유지 창 | in-sync |
| Proxy 대상 | Unavailable | 비밀 형식 / 역할 kms·secrets 권한 / SG 3306 | 역할 정책 · SG rds ← proxy | AVAILABLE |
| admin 비밀 | 7일 뒤 앱 인증 실패 | RDS 관리형 교체 | 앱 전용 사용자(교체 없음) | Proxy 인증 2개 |
| Multi-AZ failover | 60~120s 오류 | 전환 시간 | Proxy 가 연결 유지 · 앱 풀 재연결 | failover 후 200 |
| 로그 | slowquery 그룹 비어 있음 | 내보내기 미체크 / long_query_time | 내보내기 error·slowquery · 2s | 그룹 스트림 |
| 연결 수 | 알람 >60 | t3.small max_connections≈85 | Proxy max 90% · 풀 maxActive 20 | DatabaseConnections |
| Backup | 작업 실패 | 역할 정책 | AWSBackupServiceRolePolicyForBackup | 복구 지점 |

## 7. 발표 — 흐름을 파트로 나눔 (15분)
| 분 | 파트 | 발표자 |
|---|---|---|
| 0–3 | 개요 · 전체 흐름 한 장(간략) | 팀장 |
| 3–5.5 | CDN·보안 (Route 53 → CloudFront/WAF → ALB 보호 → Bastion) | 팀장 |
| 5.5–8 | WEB (ALB → Apache → Internal ALB · 로그) | WEB |
| 8–10.5 | WAS (Internal ALB → Tomcat → Proxy · 부팅 대기 · 로그 · 부하 테스트 결과) | WAS |
| 10.5–12.5 | DB (Proxy → RDS Multi-AZ · 비밀 · 백업 · 로그) | DB |
| 12.5–14.5 | 시연 영상 (A 정상 · B 장애·복구) | 시연 담당 |
| 14.5–15 | 트러블슈팅·로드맵·마무리 | 팀장 |
답변 틀: **이름 → 결론 → 왜(트레이드오프·대안) → 확인 방법**. 모르면 "지금 구성에선 ~까지 확인했고 ~는 로드맵".
