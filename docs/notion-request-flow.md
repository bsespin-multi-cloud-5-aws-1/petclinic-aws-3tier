# 사용자 요청 → WEB → WAS → DB — 한 요청이 지나가는 길 (mc-deploy As-Built · 2026-09-16)

> Notion 페이지용 원고. 도면: `docs/architecture-mc-deploy-asbuilt.png`. 코드: `infra/terraform-kdt5` (create_base=true).
> 확인값: `https://petclinic.mission-critical.site/` → 302 → `/petclinic/` 200 · vets 6 / owners 10 / pets 13 · CloudFront css Hit · ALB 직접 접근 차단.

## 0. 한눈에
```
브라우저 ─DNS─▶ Route 53 ─▶ CloudFront [WAF] ─HTTPS+X-Origin-Verify─▶ Public ALB :443 ─▶ Apache ×2 ─ProxyPass─▶ Internal ALB :8080 ─▶ Tomcat 9.0.121 ×2 ─JDBC TLS─▶ RDS Proxy ─▶ RDS MySQL 8.4 (Multi-AZ)
                                  │                                                                                     ▲
                                  └─ /petclinic/resources/* 는 캐시 Hit 면 여기서 끝 (오리진 미도달)                        └─ 부팅 시 Secrets Manager 에서 비밀 조회 → WAR 빌드
```

## 1. 사용자 → Route 53 → CloudFront
| 단계 | 무엇이 일어나나 | 왜 이렇게 |
|---|---|---|
| DNS | `petclinic.mission-critical.site` A/AAAA alias → `d2p7som2iuyba.cloudfront.net` (존 Z0299891BL9WGKOA2LW9, 가비아 NS 위임) | 도메인 → CloudFront 만 공개. ALB DNS 는 노출 안 함 |
| TLS | CloudFront 뷰어 인증서 ACM(us-east-1) · TLSv1.2_2021 · redirect-to-https | http 로 와도 https 로 |
| WAF | **제거(9/16 멘토링)** — `enable_waf=false`. Shield Standard 는 CloudFront 기본 포함 | 규칙 튜닝·오탐 운영 부담. 폭주 방어는 캐시 + Proxy 풀링 + ASG |
| Behavior | `/static/*` · `/images/*` · `/petclinic/resources/*` · `/petclinic/images/*` → CachingOptimized(기본 1일)+compress · `/maintenance.html` → S3(OAC) · 그 외 `*` → CachingDisabled+AllViewer | 정적은 엣지에서, 동적은 매번 오리진. 쿠키·쿼리는 AllViewer 로 그대로 전달 |
| 장애 | ALB 5xx(502/503/504) → 503 + `/maintenance.html` (S3, 오리진 그룹 failover) | WEB·WAS 전부 죽어도 사용자는 점검 페이지 |

## 2. CloudFront → Public ALB → Apache (WEB)
| 단계 | 무엇이 | 왜 |
|---|---|---|
| 오리진 | `mc-alb-public-485062926.ap-northeast-2.elb.amazonaws.com` · HTTPS only(서울 ACM) · 커스텀 헤더 `X-Origin-Verify: <secret>` | 오리진 → ALB 구간도 TLS |
| SG | `mc-sg-alb-public` 인바운드 = CloudFront origin-facing 프리픽스 리스트 443 만 | 1차 우회 차단(네트워크) |
| 리스너 | 443 기본 액션 403 · 규칙10: `X-Origin-Verify` 일치 시만 `mc-tg-web` forward | 2차 우회 차단(헤더). 80 리스너 없음 |
| 대상 그룹 | `mc-tg-web` :80 · 헬스체크 `/health.html` 10s·5s·2/3 · 등록취소 30s · 두 AZ 라운드로빈 | 얕은 헬스체크(Apache 생존만) → WAS 장애로 WEB 까지 연쇄 unhealthy 방지 |
| Apache | `/` = WAR 소스(test 브랜치)의 `index.html` + `resources/`·`images/` 를 부팅 시 `/var/www/html/{index.html,static/}` 로 복사해 직접 서빙(자산 링크 `/static/…`, 앱 링크 `/petclinic/…`) · `ProxyPass /petclinic/ → Internal ALB:8080` · `ProxyPreserveHost On` · `/health.html` | 첫 화면(정적)은 WEB 이, 앱은 WAS 가. index.html 이 없는 브랜치(main)면 `/` → 302 `/petclinic/` 폴백 |
| 로그 | access/error → CloudWatch Agent → `/mc/web/access`·`/mc/web/error` · ALB 액세스 로그 → S3 `mc-logs/alb/public` | 인스턴스 밖에 남아야 교체 뒤에도 조회 |

## 3. Apache → Internal ALB → Tomcat (WAS)
| 단계 | 무엇이 | 왜 |
|---|---|---|
| Internal ALB | `mc-alb-internal` internal · :8080 → `mc-tg-was` `/petclinic/` 10s·2/3 | WEB 이 WAS IP 를 몰라도 됨. WAS 증설·교체 시 WEB 무변경 |
| SG 체인 | `mc-sg-alb-internal` 8080 ← `mc-sg-web` · `mc-sg-was` 8080 ← `mc-sg-alb-internal` | 앞 단계 SG 만 허용. 22번 없음(SSM) |
| Tomcat | 9.0.121 · Corretto(OpenJDK) 8 · `/opt/tomcat` · systemd · `petclinic.war` (test 브랜치 = Spring 5.3.39 + welcome.jsp mc-hero) | Green. Blue(main·9.0.53)로 복귀는 tfvars 2줄 |
| 정적 파일 | WAR 안 `resources/` 를 Tomcat 이 서빙 → Apache 프록시 → CloudFront 캐시 | 캐시 미스 때만 WAS 도달 |
| 로그 | catalina.out · localhost_access_log · gc.log → `/mc/was/*` | |

## 4. Tomcat → RDS Proxy → RDS (DB)
| 단계 | 무엇이 | 왜 |
|---|---|---|
| 비밀 | 부팅 시 admin 비밀(`rds!db-…`)로 앱 사용자 `petclinic_app` 생성(멱등) → 앱 비밀 `mc/petclinic/app-db`(교체 없음)로 빌드 | admin 은 7일 자동 교체라 WAR 에 박으면 깨짐 → 앱 전용 계정·최소 권한 |
| 빌드 주입 | `./mvnw -P MySQL -Djdbc.url=jdbc:mysql://<proxy>:3306/petclinic?...&sslMode=REQUIRED -Djdbc.username -Djdbc.password` | `datasource-config.xml` 이 Maven 필터링되므로 빌드 시점에만 주입 가능(소스 0줄 수정) |
| Proxy | `mc-rds-proxy.proxy-c7ku4mw88shn…` · require_tls · SECRETS 인증(admin + petclinic_app) · max 90% · idle 30분(앱 풀은 testOnBorrow 로 검증) | 커넥션 다중화, failover 중 연결 유지, 비밀 교체 시 앱 무영향 |
| RDS | `mc-petclinic` MySQL 8.4.11 · db.t3.small · Multi-AZ(Primary 2c · Standby 2a) · 파라미터 그룹 `mc-mysql84` require_secure_transport=1 · 백업 7일 | TLS 없는 연결 거부. RPO 0 |
| 스키마 | 앱 기동 시 Spring `jdbc:initialize-database` 가 `db/mysql/schema.sql`·`data.sql` 실행 → vets 6 · owners 10 · pets 13 | DB 안에 데이터가 있음 = H2 인메모리가 아님 |
| SG | `mc-sg-rds-proxy` 3306 ← `mc-sg-was` · `mc-sg-rds` 3306 ← `mc-sg-rds-proxy` 만 | WAS → RDS 직접 경로 없음 |

## 5. 운영 계층이 붙는 곳
- CloudWatch Logs 6 그룹 · 알람 3(WAS unhealthy · ALB p95 · RDS 연결) → SNS `mc-alerts` (이메일 구독은 `alert_emails` 로 추가) · Slack 은 Grafana Alerting 한 경로
- CloudTrail `mc-trail` → S3 `mc-cloudtrail-…` 1년 · SSM Session Manager 세션 로그 `/mc/ssm/sessions` · AWS Backup `mc-rds-daily` 04:00 KST

## 6. 정적 파일을 바꿨을 때
CloudFront 가 `/petclinic/resources/*`·`/static/*`·`/images/*` 를 1일 캐시하므로 WAS/WEB 교체 뒤 CSS·이미지가 옛것으로 보이면 무효화: `aws cloudfront create-invalidation --distribution-id E2PWXW3LUYTDEE --paths "/petclinic/resources/*" "/static/*" "/images/*"`

## 7. 직접 확인하는 명령
```bash
curl -s -o /dev/null -w "%{http_code}\n" https://petclinic.mission-critical.site/                                  # 200 index.html
curl -s -o /dev/null -w "%{http_code} x-cache=%header{x-cache}\n" https://petclinic.mission-critical.site/petclinic/resources/css/petclinic.css   # Hit
curl -s https://petclinic.mission-critical.site/petclinic/vets.json | head -c 120                                  # DB 데이터
curl -sk -m 8 -o /dev/null -w "%{http_code}\n" https://mc-alb-public-485062926.ap-northeast-2.elb.amazonaws.com/  # 타임아웃 = 차단
aws ssm start-session --target i-082a98edcc9a8faf6 --profile mc-deploy       # WAS 접속 → grep vets /var/log/mc-userdata.log
```
