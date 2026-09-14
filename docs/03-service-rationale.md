# Phase 3 서비스 채택 근거 — 계층별 정리

- 팀: 1팀 Mission Critical · 작성 2026-09-13
- 목적: "왜 이 서비스를 썼는가"를 진입 → WEB → WAS → DB → 운영 순으로 한 표씩 정리. 발표 슬라이드와 Q&A 대비용
- 다이어그램: `docs/architecture-phase3-focus.png` (배지 번호 1~7과 대응)

## 0. 한 줄 요약

> 엣지에서 자르고(CloudFront·WAF) → WEB·WAS는 자동 증설로 흡수(ASG·예약 증설) → DB는 보호(RDS Proxy·Multi-AZ) → 전 구간을 측정하고 알린다(CloudWatch·SNS)

시나리오: 구독자 300만 유튜버 영상 노출로 평시 초당 50~100 요청이 초당 500~1,000으로 폭증(최대 10배), 읽기:쓰기 8:2 → 6:4.

---

## 1. 진입 계층 (Edge) — 배지 1·2

| 서비스 | 무엇을 막나 (문제) | 왜 이 서비스인가 (근거) | 설정 요점 | 확인 지표 |
|---|---|---|---|---|
| **Route 53 + ACM** | 도메인 없이는 CloudFront·HTTPS 구성 불가 | Route 53 별칭 레코드는 CloudFront·ALB에 무료로 연결되고 헬스체크 기반 장애 조치 가능. ACM 인증서는 무료·자동 갱신 | 도메인 → CloudFront 별칭, ACM 인증서 HTTPS 종단, HTTP→HTTPS 리다이렉트 | 도메인 응답, 인증서 만료 알람 |
| **CloudFront** | 시설·수의사 프로필·후기 이미지 등 **정적 자원 요청이 ALB·WEB 대역폭을 압박** | 정적 자원은 엣지에서 캐시 히트로 응답 → 오리진(ALB·WEB)에 도달하는 요청 수 자체를 줄임. 캐시 미스(동적)만 오리진으로 전달. 원본 서버 증설보다 싸고 즉시 효과 | `/petclinic/resources/*` 캐시 정책(TTL 장기), 동적 경로는 캐시 비활성. 오리진 = Public ALB. ALB 보안그룹은 CloudFront 관리형 접두사 목록만 허용 | CloudFront CacheHitRate, ALB RequestCount 감소폭 |
| **AWS WAF** | 특정 IP·경로(예약 접수)로 **비정상 폭주·봇 트래픽**이 서버 자원을 소진 | ALB 앞이 아닌 CloudFront에 붙이면 엣지에서 차단되어 오리진 부하 0. rate-based rule로 IP당 요청 상한, 경로별 규칙으로 예약 API만 더 엄격하게 제한 가능. 관리형 규칙(Common·KnownBadInputs)으로 Spring4Shell 같은 알려진 공격 패턴 차단 | Web ACL → CloudFront 연결. rate-based rule(5분 창), 예약 경로 별도 규칙, 관리형 규칙 그룹 | WAF BlockedRequests, AllowedRequests 비율 |

---

## 2. WEB 계층 (Apache) — 배지 3

| 서비스 | 무엇을 막나 (문제) | 왜 이 서비스인가 (근거) | 설정 요점 | 확인 지표 |
|---|---|---|---|---|
| **Public ALB** | 단일 WEB 서버 장애·용량 한계 | L7 로드밸런서로 두 AZ의 WEB 인스턴스에 분산. 헬스체크로 비정상 인스턴스 자동 제외. ASG와 연동해 증설된 인스턴스를 자동 등록 | internet-facing, 80/443, 대상 그룹 헬스체크 5s 간격·2회 성공 기준(장애 인스턴스 10초 내 제외) | RequestCount, TargetResponseTime, HealthyHostCount, HTTP 5XX |
| **Apache 튜닝** | 동시 연결 급증 시 워커 부족으로 **연결 대기·타임아웃** | 인스턴스를 늘리기 전에 한 대가 처리할 수 있는 동시성을 먼저 올리는 것이 비용 효율적. MPM event는 keepalive 연결을 워커 없이 유지해 동시 접속 처리량 증가 | MPM event, `MaxRequestWorkers`·`ServerLimit` 상향, `KeepAliveTimeout` 단축, 정적 파일은 Apache가 직접 서빙(Tomcat 미경유) | CPU, 연결 수, 응답 시간 |
| **ASG — WEB** | 튜닝만으로 못 버티는 수준의 폭주 | 지표 기반 자동 증설로 사람이 개입하지 않아도 용량 확보. 두 AZ에 분산 배치해 한 AZ 손실 시에도 서비스 유지 | min 2 / max 6, CPU 60% Target Tracking, 두 AZ 균등 배치, 골든 AMI(AL2023·Apache 튜닝 완료)로 기동 시간 단축 | GroupInServiceInstances, CPU, 스케일 아웃 소요 시간 |

---

## 3. WAS 계층 (Tomcat + PetClinic) — 배지 4

| 서비스 | 무엇을 막나 (문제) | 왜 이 서비스인가 (근거) | 설정 요점 | 확인 지표 |
|---|---|---|---|---|
| **Internal ALB** | WEB → WAS 연결이 특정 WAS에 고정되면 부하 불균형 | WEB이 WAS IP를 직접 알 필요 없이 ALB DNS만 바라보면 되므로 WAS가 증설·교체되어도 WEB 설정 불변. Blue/Green 전환(Phase 2)에도 같은 ALB의 가중치 라우팅 사용 | internal, 8080, WEB 보안그룹만 허용. Apache `ProxyPass /petclinic/ → Internal ALB` | TargetResponseTime, HealthyHostCount, 5XX |
| **Tomcat 튜닝** | 요청당 스레드 모델이라 **스레드 고갈 시 요청 거부(503)** | 예약 접수 같은 동적 요청은 CloudFront가 못 막으므로 WAS 한 대의 처리량이 곧 서비스 상한. 스레드·대기열 상한을 올리고 DB 커넥션 풀과 비율을 맞춰야 병목이 DB로 넘어가지 않음 | `maxThreads` 상향, `acceptCount`로 대기열 확보, `connectionTimeout` 단축, JVM 힙 고정(-Xms=-Xmx), 커넥션 풀 크기 = maxThreads와 DB 상한 사이 | 스레드 사용률, 요청 처리 시간, 5XX |
| **ASG — WAS + 예약 증설** | 폭주 시점을 알고 있는데(영상 공개 시각) Target Tracking만으로는 **증설이 늦음**(지표 반영 + 기동에 수 분) | Scheduled Scaling으로 이벤트 전에 미리 늘려 두고, 예측 못 한 초과분은 Target Tracking이 흡수. AZ당 2대 기준으로 잡아 한 AZ가 통째로 죽어도 남은 AZ가 피크 100%를 처리 | min 2 / max 8, 이벤트 전 예약 4(09:45 Scheduled Scaling), CPU Target Tracking 병행, 두 AZ 균등 배치 | GroupInServiceInstances 시계열, 예약 증설 시각 대비 실제 부하 도달 시각 |
| **SSM Session Manager** (Bastion 대체) | 운영자 접속 경로가 22번 포트·SSH 키에 의존하면 공격면·키 관리 부담 증가 | Bastion EC2 1대와 22번 인바운드를 모두 제거. IAM 권한으로 접속 통제, 세션 로그 자동 기록, ASG로 늘어난 인스턴스에도 키 배포 없이 접속. AL2023에 에이전트 기본 탑재 | 인스턴스 프로파일에 `AmazonSSMManagedInstanceCore`, 세션 로그 → CloudWatch Logs. SSM 에이전트의 아웃바운드 443은 NAT 경유 | 세션 로그, 22번 포트 인바운드 규칙 0건 |

> NAT 게이트웨이는 SSM과 무관하게 필요하다. SSM은 사람이 들어가는 길(Bastion)을 대체하고, NAT는 인스턴스가 나가는 길(패키지 설치·CloudWatch·SSM 에이전트 통신)이다. AZ당 1개는 한 AZ 손실 시에도 아웃바운드를 유지하기 위한 구성.

---

## 4. DB 계층 (RDS MySQL) — 배지 5·6

| 서비스 | 무엇을 막나 (문제) | 왜 이 서비스인가 (근거) | 설정 요점 | 확인 지표 |
|---|---|---|---|---|
| **RDS Proxy** | WAS가 8대로 늘면 **풀 크기 × 서버 수가 DB `max_connections`를 초과**해 연결 거부. failover 중 WAS의 기존 연결이 끊겨 에러 폭증 | 커넥션 다중화로 WAS 수와 무관하게 DB 연결 수를 상한 이내로 유지. failover 시 프록시가 새 Primary로 자동 재연결해 앱 쪽 에러 시간을 수십 초 → 수 초로 단축. Secrets Manager와 IAM 인증 연동으로 앱에 비밀번호 미보관 | WAS → RDS Proxy 엔드포인트(3306), 풀 `validationQuery`로 끊긴 연결 조기 감지, `max_connections_percent` 설정 | DatabaseConnections(DB 측), ClientConnections(프록시 측), failover 중 에러 초 |
| **RDS Multi-AZ** | Primary 장애·AZ 장애·패치 시 **서비스 전체 중단** | 동기 복제 standby가 다른 AZ에 대기, 장애 시 자동 failover(DNS 전환 1~2분). 백업·패치도 standby에서 먼저 수행해 무중단. 생성 시부터 켜야 나중에 전환 시 다운타임 없음 | Multi-AZ 생성 시부터, db.t3.small, 20GB gp3 암호화, 파라미터 그룹으로 `max_connections`·버퍼 풀 조정, Performance Insights | ReplicaLag, failover 소요 시간, CPU·DatabaseConnections |
| **읽기 부하 대응 (로드맵)** | 읽기:쓰기 6:4에서 SELECT 집중 | Read Replica는 앱이 읽기·쓰기 데이터소스를 분리해야 효과가 있어 PetClinic 코드 수정 필요 → Phase 3 범위 밖, 로드맵으로 명시. 현 단계는 파라미터 튜닝(버퍼 풀)과 CloudFront 캐시로 읽기 요청 자체를 줄이는 방식 | 로드맵: Read Replica + `AbstractRoutingDataSource` | — |

---

## 5. 운영·관측 계층 (전 구간 공통) — 배지 7

| 서비스 | 무엇을 막나 (문제) | 왜 이 서비스인가 (근거) | 설정 요점 | 확인 지표 |
|---|---|---|---|---|
| **CloudWatch** | 어느 계층이 병목인지 모르면 **증설·튜닝의 근거가 없음**. 전/후 비교 불가 | ALB·EC2·RDS·WAF 지표를 한 대시보드에 계층별로 나열해 병목 위치를 즉시 식별. 알람이 ASG Target Tracking의 트리거이기도 함 | 대시보드: RequestCount → TargetResponseTime(p95) → HealthyHost → 5XX → CPU → DatabaseConnections. 알람: 5XX 비율, HealthyHost < 2, DB 연결 80%, CPU 지속 80% | JMeter 기준선 → 조치 → 재측정 표 |
| **SNS** | 알람이 콘솔에만 뜨면 **아무도 못 봄** | CloudWatch 알람 → SNS 토픽 → 팀 채널(이메일·Slack 웹훅)로 즉시 통보. 서버리스·무료 수준 비용 | 토픽 1개, 알람별 구독. 심각도별 토픽 분리는 선택 | 알람 → 수신 지연 |
| **Secrets Manager** | DB 비밀번호가 `pom.xml`·환경변수·AMI에 남으면 **유출 위험**. 비밀번호 교체 시 전 WAS 재배포 | 비밀을 중앙 저장·암호화하고 IAM으로 접근 통제. RDS Proxy가 직접 참조하므로 WAS는 비밀번호를 몰라도 됨. 자동 로테이션 가능 | DB 자격증명 저장 → RDS Proxy 연동. WAS 인스턴스 프로파일에 읽기 권한(직접 읽을 때만) | 비밀 접근 로그(CloudTrail) |
| **Systems Manager** (Run Command·Patch) | 8대 이상 인스턴스에 일일이 접속해 패치·설정 변경 | Session Manager와 같은 에이전트로 다수 인스턴스에 명령 일괄 실행, 롤링 OS 패치 무중단 | Run Command로 설정 배포, Patch Manager 유지관리 창 | 패치 준수율 |

---

## 6. 계층별 병목 → 수단 → 지표 (발표용 한 장)

| 계층 | 병목 | 1차 수단 (싸고 빠름) | 2차 수단 (증설) | 보호 수단 | 확인 지표 |
|---|---|---|---|---|---|
| 진입 | 정적 자원·비정상 트래픽이 오리진 도달 | CloudFront 캐시 | — | WAF rate-based | CacheHitRate, WAF Blocked, ALB RequestCount |
| WEB | Apache 워커 부족 | MPM event 튜닝 | ASG min 2 · CPU 60% | 두 AZ 분산 | CPU, TargetResponseTime |
| WAS | Tomcat 스레드 고갈 | maxThreads·acceptCount | ASG AZ당 2 · 예약 증설 | 헬스체크 5s/2 | HealthyHost, 5XX, 스레드 |
| 연결 | 풀 × 서버 수 > DB 상한 | validationQuery | — | RDS Proxy | DatabaseConnections, failover 에러 초 |
| DB | Primary 장애·연결 상한 | 파라미터 그룹 | (로드맵) Read Replica | Multi-AZ | ReplicaLag, failover 시간 |
| 관측 | 병목 위치 불명 | CloudWatch 대시보드 | — | 알람 → SNS | 전/후 표 |

## 7. 자주 나올 질문

- **SSM을 쓰면 NAT가 필요 없나?** 아니다. SSM은 Bastion(인바운드 접속)을 대체하고, NAT는 아웃바운드(패키지·CloudWatch·SSM 에이전트)용이다. NAT 대신 SSM·CloudWatch·S3 VPC 엔드포인트로 대체할 수 있으나 인터넷 아웃바운드(dnf·git)가 막히므로 골든 AMI 전제가 필요하다.
- **NAT가 있는데 왜 SSM인가?** NAT는 인바운드를 받지 못한다. 접속 수단은 Bastion 또는 SSM 중 하나가 필요하고, SSM은 EC2 1대·22번 포트·SSH 키를 모두 없애며 세션 로그가 남는다.
- **WAF를 ALB가 아닌 CloudFront에 붙인 이유는?** 엣지에서 차단하면 차단된 요청이 오리진에 도달하지 않아 부하가 0이다. ALB에 붙이면 ALB까지는 도달한다.
- **Read Replica는 왜 안 썼나?** 앱이 읽기·쓰기 데이터소스를 분리해야 효과가 있다. PetClinic 코드 수정이 필요해 로드맵으로 남겼다.
- **RDS Proxy 없이 Multi-AZ만으로 안 되나?** failover 자체는 되지만 WAS의 기존 커넥션이 모두 끊겨 재연결까지 에러가 난다. 또 WAS가 8대로 늘면 풀 합계가 DB 상한을 넘는다. Proxy가 두 문제를 모두 해결한다.
