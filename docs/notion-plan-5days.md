# 9/16 멘토링 회의록 정리 + 5일 실행 계획 (9/17 목 ~ 9/21 월 11:00 멘토링 전)

> 회의: 2026-09-16 09:59 KST · 멘토 전동진 · 참석 박준석(팀장)·이재운·김세민·신예나. 발표 10/1. **다음 멘토링 9/21(월) 11:00**, 질문은 Space에 남길 것.
> 아래 "확정 필요"는 회의록에 담당자 이름이 없어 팀이 정해야 하는 것.

## 0. 회의 요약 — 결정 · 조언

### 결정(의견 일치)
| # | 결정 | 우리에게 바뀌는 것 |
|---|---|---|
| D1 | **중간 프로젝트는 Terraform 미사용, 콘솔 구축** (파이널에서 IaC) | `infra/terraform*`는 **설계 검증·정답지**로만 사용. 팀 산출물은 kdt5 콘솔 구축 + 콘솔 클릭 가이드(⑦·⑧·⑩) |
| D2 | 아키텍처 **이번 주 내 구성, 설계는 9/18(금)까지 완료** | 도면·계층별 설정값 확정 → 9/18 팀 리뷰 |
| D3 | 로그·모니터링 담당 배정: **앱 세팅 담당이 앱 로그, DB 로그는 DB 담당** | 공통(CloudWatch·CloudTrail)은 함께 공부 후 1명 발표 |

### 멘토 조언(반영 방향)
| 주제 | 멘토 의견 | 반영 |
|---|---|---|
| EBS | **루트/데이터 볼륨 분리**(루트 50~100GB 미만, 데이터 100~150GB), 설정은 루트·데이터는 데이터 볼륨 | WEB·WAS 인스턴스 재구성(볼륨 2개, gp3 옵션 근거) |
| 설치 방식 | dnf 패키지 대신 **Apache·Tomcat 소스 컴파일**, 데이터 볼륨에 설치 | 학습용. 컴파일 절차·의존성(apr·openssl 등) 문서화 |
| 인스턴스 타입 | T = 버스터블(크레딧, 10% 미만 적립, 초과 시 과금). **운영 가정이면 M/R, 비용이면 T — 근거를 발표에** | 타입 선정 근거표 작성 |
| EFS | WAS 증설 시 **동적 데이터 공유용 EFS** 검토 | WAR·설정 공유 설계(⑮ 후기 6절 설계안) |
| 세션 | **ALB 스티키 세션**으로 세션 유지 가능 | 스티키 설정법·쿠키 종류·제약 학습 |
| 인증서 | CloudFront / ALB / 서버 중 **어디에 둘지 장단점·제약 조사**. 무난한 답은 ALB. 암복호화 반복 성능 고려 | 배치 비교표 + 자동 갱신(DNS 검증) |
| 암호화 | EBS·S3는 **KMS 키 암호화**가 일반적. 보안 vs 성능·비용 트레이드오프 | 암호화 표(⑮ 후기 4절) 유지 |
| 큐 vs 캐시 | 펫클리닉 같은 웹서비스에 **큐는 부적합**. 부하는 **Redis 캐시 또는 RDS Read Replica** | SQS 미도입 확정. Redis/Read Replica는 "폭주 대응 옵션"으로 비교표 |
| 트랜잭션 흐름 | 정적(S3+CloudFront)·동적(ALB) 요청이 WEB→WAS→DB를 지나는 **타임라인을 코드 레벨로** 학습. VPC Flow Logs·traceroute·Fiddler | ⑪ 요청 흐름 페이지에 "코드 레벨 타임라인" 절 추가 |
| NAT | 아웃바운드는 패치 때만 필요 → **상시 두지 말고 필요할 때 생성**이 100점 | ⚠ 기존 후기 문서(NAT 2 유지)와 다름 → 아래 "차이" 참조 |
| WAF | 관리 어려움. 학습은 **AWS 관리형 룰셋으로 개념**, 운영은 모니터링으로 커스텀 조정 | rate 규칙은 빼고 관리형만 두거나(학습), 전체 제거 중 택1 |
| 로그 역할 | SA/TA/AA처럼 앱 담당이 앱 로그, DB 담당이 DB 로그 | 담당표 |
| user_data vs Golden AMI | AMI에 못 담는 **동적 값**(EFS 마운트 엔드포인트 등)만 user_data | AMI + 짧은 user_data |
| SSM vs Bastion | SSM은 편하지만 **보안팀 통제(2FA·세분 권한·감사)** 설득이 어려움 | SSM 기본 + Bastion 병행(현재 kdt5 그대로) |
| CloudFront 캐시 | 이미지 배포 빈도에 맞춰 **캐시 옵션(TTL)** 조정 | 정적 TTL 설계값 근거 |
| 배포 | 롤링 / 블루-그린 / 카나리 개념 | 발표 슬라이드 1장 |

### ⚠ 기존 문서(`notion-mentoring-followup.md`, 9/16 12:05)와 회의록의 차이
| 항목 | 후기 문서 | 회의록(권위) | 처리 |
|---|---|---|---|
| NAT | "AZ당 1개가 맞다, 2개 유지" | "필요할 때 생성이 100점" | **회의록 기준**: 평시 NAT 없음(SG 아웃바운드 최소), 패치·설치 시 생성 → 후기 5절 수정 |
| WAF | "WAF 제거, CloudFront 유지" | "학습용 관리형 룰셋 적용" | **관리형 룰셋 1~2개만 유지**(rate 규칙 제거). 완전 제거보다 발표 설명이 쉬움 |
| Redis | "미도입 유지" | "Redis 캐시 또는 Read Replica가 적절" | 미도입은 유지하되 **폭주 대응 옵션 비교표(Redis vs Read Replica vs ASG)** 를 설계에 포함 |
| Terraform | (언급 없음) | **미사용** | 코드는 정답지, 산출물은 콘솔 |

---

## 1. 5일 일정 (마일스톤)
| 날 | 목표 | 완료 기준 |
|---|---|---|
| **9/17(목)** | 조사 완료·설계 초안 | 인스턴스 타입 근거표 · EBS 분리안 · 인증서 배치 비교 · 스티키/EFS 조사 메모 · 담당표 확정 |
| **9/18(금)** | **설계 완료(마감)** | 도면 v2(WAF·NAT 결정 반영) · 계층별 설정값표 · 팀 리뷰 |
| **9/19(토)** | 콘솔 구축 1 | WEB·WAS 재구축(볼륨 2개·소스 컴파일·CW Agent) · AMI v1 |
| **9/20(일)** | 콘솔 구축 2 | ASG(WEB·WAS) · RDS 연동(파라미터 그룹·Proxy 여부 결정) · 스티키/ACM/CloudFront 반영 · 로그 확인 |
| **9/21(월) 11:00 전** | 검증·질문 준비 | 요청 흐름 타임라인 시연 가능 · Space에 질문 등록 · 멘토링 |

---

## 2. 파트별 할 일

### 2-1. 네트워크 · 진입 (Route 53 · CloudFront · ACM · ALB · NAT · SG)
- [ ] **NAT 정책 재설계**: 평시 NAT 제거 가능 여부 점검 — SSM·CloudWatch Agent·Secrets Manager는 **VPC 엔드포인트**로, 패치·설치는 작업 시 NAT 생성 후 삭제. 비용 표 ($43/개·월 vs 엔드포인트 $8/AZ)
- [ ] **인증서 배치 비교표**: CloudFront(us-east-1 ACM) / ALB(서울 ACM) / 서버(수동 인증서) — 갱신(ACM DNS 검증 자동), 성능(암복호화 위치), 제약(CloudFront는 us-east-1 필수, 서버는 갱신 수동)
- [ ] **CloudFront 캐시 옵션 근거**: 정적 TTL(1일) · 무효화 절차 · 이미지 배포 빈도 가정
- [ ] **WAF 최종안**: 관리형 룰셋(Common·KnownBadInputs)만 유지, rate 규칙 제거 — 콘솔 적용
- [ ] **스티키 세션**: ALB 대상 그룹 속성(Load balancer generated cookie / 앱 쿠키, duration) 학습 → Internal ALB에 적용할지 결정(PetClinic 무상태라 "설정법 숙지 + 미적용" 가능)
- [ ] SG 아웃바운드 최소화 표(계층별 인바운드/아웃바운드)

### 2-2. WEB 티어 (Apache)
- [ ] **EBS 분리**: 루트 gp3 50GB(OS·설정 `/etc/httpd`), 데이터 gp3 100GB(`/data`: Apache 설치 프리픽스·문서 루트·로그). gp3 IOPS/처리량 기본값 근거
- [ ] **소스 컴파일 설치**: httpd 2.4.x tar → `./configure --prefix=/data/apache --enable-ssl --enable-proxy` → make → systemd 유닛. 의존성(apr, apr-util, pcre2, openssl-devel) 목록
- [ ] mod_proxy 리버스 프록시 설정 재적용(`/petclinic/` → Internal ALB, `ProxyPreserveHost`), index.html 랜딩
- [ ] CloudWatch Agent 설치(메모리·디스크 지표 + access/error 로그) — **앱 담당이 로그 확인**
- [ ] AMI v1(WEB) 생성 → 시작 템플릿 → ASG(min 2 / max 4, CPU 60%)

### 2-3. WAS 티어 (Tomcat)
- [ ] **EBS 분리**: 루트 50GB, 데이터 100~150GB(`/data`: Tomcat 설치·webapps·logs)
- [ ] **소스 설치**: Tomcat 9.0.121 바이너리 tar(소스 빌드는 Ant 필요 — 멘토 취지가 "패키지 매니저 배제"이므로 tar 배포본 사용을 확인) + Corretto 8, `/data/tomcat`
- [ ] **인스턴스 타입 근거**: t3.medium(RAM 4GB, 동기식 톰캣 스레드) vs m6i.large — 발표용 근거 한 줄 + 버스터블 크레딧 설명
- [ ] **EFS 조사**: 무엇을 공유하나(WAR 릴리스·context.xml) / 마운트(`amazon-efs-utils`, `-o tls`) / 성능 모드 / 비용 / EFS 위 WAR 직접 실행 vs 로컬 복사 — 설계안은 ⑮ 후기 6절
- [ ] DB 연동: JDBC → RDS(Proxy 도입 여부는 DB 파트와 결정), 비밀은 Secrets Manager
- [ ] CloudWatch Agent(catalina·access·gc) · AMI v1(WAS) · ASG(min 2 / max 6)

### 2-4. DB 티어 (RDS)
- [ ] 인스턴스 타입 근거: db.t3.small(스탠바이 포함) — 운영 가정이면 db.m6g.large 비교
- [ ] 파라미터 그룹(TLS 강제·utf8mb4) 콘솔 생성·적용(재부팅 시점)
- [ ] **폭주 대응 옵션 비교표**: Read Replica(읽기 분산, 앱 데이터소스 분리 필요) vs Redis 캐시(코드 필요) vs RDS Proxy(커넥션 풀) — 멘토 조언 반영
- [ ] 앱 전용 DB 사용자(`petclinic_app`, 최소 권한) + admin 비밀 자동 교체 영향 정리
- [ ] **DB 로그 담당 분리**: RDS 에러·slow query 로그 → CloudWatch 내보내기, 백업(자동 7일·AWS Backup) 확인
- [ ] 세션 유지 대안: ALB 스티키(네트워크 파트) vs Redis — DB 관점 의견

### 2-5. 공통 (운영·관측·보안) — 함께 공부, 1명 발표
- [ ] CloudWatch Logs·CloudTrail 목적/이유/사용처(⑮ 후기 Extra 1·2) 발표 원고
- [ ] KMS·S3·EBS 암호화 표(후기 4절) — EBS 데이터 볼륨도 KMS 적용
- [ ] **요청 흐름 타임라인**(코드 레벨): 브라우저 → DNS → CloudFront(캐시 Hit/Miss) → ALB → Apache → Internal ALB → Tomcat(DispatcherServlet → Controller → Repository) → JDBC → RDS → 응답. VPC Flow Logs 켜서 확인, traceroute/curl -w 타임라인 캡처
- [ ] 배포 전략 슬라이드(롤링·블루그린·카나리) + Golden AMI vs user_data 원칙
- [ ] 로그 담당표 · 알람 3개 · SNS 이메일 구독

---

## 3. 서비스별 체크리스트
| 서비스 | 할 일 | 파트 |
|---|---|---|
| EC2 · EBS | 타입 근거표(T vs M/R) · 루트/데이터 볼륨 분리 · gp3 옵션 · 소스 설치 · AMI v1 | WEB·WAS |
| ASG · 시작 템플릿 | LT(AMI v1 + 짧은 user_data) · min/max · CPU 60% · 헬스체크 ELB · 인스턴스 새로 고침 | WEB·WAS |
| EFS | 공유 대상 정의 · 마운트 타깃 2 AZ · SG 2049 · TLS · 성능 모드 · 비용 | WAS |
| ALB(외부·내부) | 443 리스너·ACM · 헬스체크 · **스티키 세션** 설정법 · 액세스 로그 S3 | 네트워크·WAS |
| Route 53 · ACM · CloudFront | 인증서 배치 비교 · DNS 검증 자동 갱신 · 캐시 TTL/무효화 · 점검 페이지 | 네트워크 |
| WAF · Shield | 관리형 룰셋만 · rate 제거 · 로그 | 네트워크 |
| NAT · VPC 엔드포인트 · SG | 필요 시 NAT 생성 절차 · 엔드포인트(SSM·Secrets·Logs) · 아웃바운드 최소화 | 네트워크 |
| RDS · Proxy | 타입 근거 · 파라미터 그룹 · Multi-AZ · 앱 사용자 · Read Replica/Redis 비교 · 로그 내보내기 | DB |
| Secrets Manager · KMS | 비밀 조회 방식 · 자동 교체 영향 · 암호화 표 | DB·공통 |
| CloudWatch(Agent·Logs·알람) · SNS | Agent 설치(메모리 지표) · 로그 그룹 · 알람 3 · 이메일 | 공통(앱 로그는 각 파트) |
| CloudTrail · S3 | 추적·S3 1년·검증 · 로그 버킷 lifecycle | 공통 |
| SSM · Bastion | SSM 기본 + Bastion 병행 · 세션 로그 · 보안팀 관점 장단점 | 네트워크 |
| VPC Flow Logs | 요청 흐름 학습용으로 한시 활성화 | 공통 |

---

## 4. 인원별 (역할은 회의록에 이름이 없어 **추정 — 9/17 첫 회의에서 확정**)
| 인원 | 추정 담당 | 9/17~9/21 할 일 |
|---|---|---|
| **박준석** (팀장) | 네트워크·진입 + 공통 발표 조율 | NAT/엔드포인트 재설계 · 인증서 배치 비교 · WAF 최종안 · CloudFront 캐시 근거 · 스티키 세션 조사 · 도면 v2(9/18) · 요청 흐름 타임라인 · Space 질문 등록 · 역할표 확정 |
| **이재운** | WAS(인스턴스 타입 논의 주도) | 타입 근거표(T3 medium vs M) · EBS 분리+Tomcat 설치 · EFS 조사 · ASG(WAS) · WAS 로그(catalina·gc) |
| **김세민** | WEB(Apache/Tomcat 설치 경험) | EBS 분리 + Apache 소스 컴파일 · mod_proxy · CW Agent · AMI v1(WEB) · ASG(WEB) · WEB 로그 |
| **신예나** | DB | RDS 타입 근거 · 파라미터 그룹 · 앱 사용자·비밀 · Read Replica/Redis 비교 · DB 로그 분리 · 백업 |
| **공통(전원)** | CloudWatch·CloudTrail·암호화·배포 전략 | 각자 파트 원고 1장씩 → 1명이 통합 발표(누가 할지 9/17 결정) |
| **멘토 후속** | — | 9/21(월) 11:00 · 질문은 Space · 설계 결과물(도면 v2·설정값표) 공유 |

---

## 5. 지금 당장 정할 것 (9/17 첫 회의 안건)
1. 위 인원별 담당 확정 + 공통 발표자 1명
2. **mc-deploy Terraform 환경 처리**: 콘솔 구축이 산출물이므로 (a) 정답지로 5일 더 유지(≈ $60) 후 destroy, (b) 지금 destroy — 팀 결정. 유지 시 admin 비밀 교체(9/22) 전 앱 사용자 적용 필요
3. NAT: "필요 시 생성" 방식으로 갈지(엔드포인트 3개 추가 ≈ $24/월) — 비용·구현 난이도 비교 후 결정
4. WAF: 관리형 룰셋만 vs 완전 제거
5. Redis/Read Replica: 설계 비교표에만 두고 미구현 유지할지
