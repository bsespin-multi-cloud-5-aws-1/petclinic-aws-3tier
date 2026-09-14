# 설계 초안 — PetClinic 3-Tier on AWS (1일차 팀 확정용)

- 팀: 1팀 Mission Critical · 작성 2026-09-11 · 상태: **초안 v2** (9/12 결정 반영: Bastion 없음·SSM, Route 53 도메인, RDS Multi-AZ 기본, OS 2단계 AL2→AL2023, Phase 1은 제공본 그대로)
- 다이어그램: `docs/architecture.drawio` (1페이지 기준선, 2페이지 계층별 과부하 대응)

## 1. 서비스 시나리오와 규모 가정

| 항목 | 가정 |
|---|---|
| 서비스 | 동물병원 진료 예약·기록 시스템 (PetClinic) |
| 평소 | 일 100명, 동시 접속 ≤ 20 |
| 이벤트 | 토요일 10:00 "반값 건강검진" 오픈 → 동시 접속 2,000, 5분 피크, 진료 등록(INSERT) 비율 20% |
| 목표(SLO) | 피크 중 p95 응답 < 1초, 에러율 < 1%, **AZ 1개 손실 시에도 동일 목표 유지** |
| 측정 도구 | JMeter (`src/test/jmeter/petclinic_test_plan.jmx` 기반) + CloudWatch |

측정 지표 5개(모든 실험에서 동일하게 기록): ① 에러 건수 ② 영향 시간(초) ③ p95 응답시간 ④ 살아있는 WAS 수 ⑤ 복구까지 분

## 2. 아키텍처 (요청 흐름)

```
사용자 → Route 53 → [CloudFront + WAF]* → Public ALB → Apache(WEB) → Internal ALB → Tomcat+PetClinic(WAS) → [RDS Proxy]* → RDS MySQL (Multi-AZ)
                                                                                          * = Phase 3(7~8일차)에 추가
```

Phase 1(Blue) = 제공본 그대로(AL2·Corretto 11·Tomcat 9.0.53·Spring 5.3.9) → Phase 2(Green) = AL2023·Corretto 17·Tomcat 9.0.121·Spring 5.3.39 를 Blue/Green으로 전환 → Phase 3 = 트래픽 과부하 대응

- 리전 `ap-northeast-2`, AZ `2a`·`2c`
- WEB/WAS는 private subnet, 퍼블릭 IP 없음. 관리 접속은 **SSM Session Manager**(22번 포트 안 엶). **Bastion 없음(확정)** — 슬라이드 예시에는 있으나 SSM으로 대체, 근거는 발표에 한 줄
- 도메인은 Route 53에서 구매 → Public ALB 별칭. ACM 인증서로 HTTPS(Phase 1 말 또는 Phase 2)
- DB subnet은 인터넷 경로 없음

## 3. 네트워크

| 이름 | CIDR | AZ | 라우팅 |
|---|---|---|---|
| mc-vpc | 10.0.0.0/16 | — | — |
| mc-public-a / c | 10.0.0.0/24 / 10.0.1.0/24 | 2a / 2c | 0.0.0.0/0 → IGW |
| mc-web-a / c | 10.0.10.0/24 / 10.0.11.0/24 | 2a / 2c | 0.0.0.0/0 → NAT-a / NAT-c |
| mc-was-a / c | 10.0.20.0/24 / 10.0.21.0/24 | 2a / 2c | 0.0.0.0/0 → NAT-a / NAT-c |
| mc-db-a / c | 10.0.30.0/24 / 10.0.31.0/24 | 2a / 2c | 로컬만 (기본 경로 없음) |

## 4. 보안그룹 매트릭스 (인바운드만, 아웃바운드는 기본)

| 보안그룹 | 포트 | 소스 | 붙는 곳 |
|---|---|---|---|
| sg-alb-public | 80 (443) | **Phase 1: 팀원 IP만**(Spring4Shell 취약 상태 노출 통제) → Phase 2 패치 후 0.0.0.0/0 → Phase 3 CloudFront 접두사 목록 | Public ALB |
| sg-web | 80 | sg-alb-public | WEB EC2 |
| sg-alb-internal | 8080 | sg-web | Internal ALB |
| sg-was | 8080 | sg-alb-internal | WAS EC2 |
| sg-rds-proxy (8일차) | 3306 | sg-was | RDS Proxy |
| sg-rds | 3306 | sg-was (+ sg-rds-proxy) | RDS |
| sg-loadgen | — (아웃바운드만) | — | JMeter EC2 |

## 5. 컴퓨팅·DB 사양

| 계층 | 사양 | 기본 대수 → 보강 후 |
|---|---|---|
| WEB | Phase 1 AL2 → Phase 2 AL2023, t3.small, Apache 2.4 | AZ당 1 → ASG min 2 / max 6 |
| WAS | Phase 1 AL2·Corretto 11·Tomcat 9.0.53 → Phase 2 AL2023·Corretto 17·Tomcat 9.0.121, t3.medium | AZ당 1 → ASG min 2 / max 8, 이벤트 전 예약 4 |
| DB | RDS MySQL 8.0, db.t3.small, 20GB gp3, 암호화, **Multi-AZ 생성 시부터**(슬라이드 기본 구성) | + RDS Proxy(Phase 3) |
| 부하 발생기 | t3.medium, public-a, JMeter | 1 |

## 6. 네이밍·태깅

- 리소스 이름: `mc-<계층>-<az>[-n]` (예 `mc-was-a-1`), 보안그룹 `sg-<역할>`, AMI `mc-<계층>-ami-v<n>`
- 태그(전 리소스): `Project=petclinic-3tier`, `Team=mc-1`, `Owner=<이름>`, `Tier=web|was|db|edge`, `Env=lab`
- 비용: 예산 알람 70% / 90% (Budgets), 실험 인스턴스는 당일 삭제

## 7. Phase별 계획 (5일차 이후)

| 일차 | Phase | 내용 | 검증 |
|---|---|---|---|
| 5 | 2 마이그레이션 | 진단표·변경 티켓 → 스테이징 WAS(Green 스택) → AMI v2 → Green 대상 그룹 → Internal ALB 가중치 10→50→100% | 점검표 + JMeter 전/후, 롤백 리허설 |
| 6 | 2 운영 | Secrets Manager, CloudWatch 알람, 백업·PITR 복원, OS 롤링 패치, SSM 운영 절차, Blue 폐기 | 복원 데이터 확인, 패치 무중단 |
| 7 | 3 과부하(진입·WEB·WAS) | 기준선 측정 → CloudFront·WAF·헬스체크 5s → Apache 튜닝·WEB ASG → Tomcat 튜닝·WAS ASG·예약 증설 | 계층별 전/후 표, WAS 강제 종료 |
| 8 + 연휴 | 3 과부하(연결·DB) + 종합 | 풀 validationQuery·RDS Proxy·파라미터 → 종합 실험(폭주+AZ 장애+failover) → 영상·초안 → 9/27 프리징 | 종합 전/후 표 |

## 8. 결정 사항

확정(9/12): Bastion 없음·SSM만 / Route 53 도메인 구매 / RDS Multi-AZ 생성 시부터 / OS AL2(Phase 1)→AL2023(Phase 2) / Phase 1은 제공본 그대로

1일차에 팀이 결정할 것:
- [ ] WEB↔WAS 연동: mod_proxy_http(초안) vs mod_jk — 멘토 의견
- [ ] 도메인 이름
- [ ] 역할: 팀장=네트워크·측정, WEB, WAS, DB 담당 확정
- [ ] Phase 2 전환 방식: 가중치 Canary(초안) vs 한 번에 Blue/Green
