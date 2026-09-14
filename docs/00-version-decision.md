# 버전 결정표 — Legacy PetClinic → 2026 채택 스택

- 팀: 1팀 Mission Critical
- 작성일: 2026-09-11 (주말 검증 전 초안, 9/13 검증 결과 반영 후 확정)
- 원칙: **앱 코드는 건드리지 않는다.** 바꾸는 것은 빌드 설정(pom.xml)과 실행 환경뿐.
- 상한선: PetClinic이 Spring 5.3 / `javax.servlet` 기반이라 **Tomcat 10+ · Spring 6(Jakarta)는 코드 수정 없이는 불가** → 이번 범위 밖, 로드맵.

## 0. Phase 구분 — Blue(현재 환경) → Green(업그레이드)

| | Phase 1 · Blue (1~4일차, 제공본 그대로) | Phase 2 · Green (5~6일차, 업그레이드) |
|---|---|---|
| OS | Amazon Linux 2 (지원 종료) | Amazon Linux 2023 |
| JDK | Corretto 11 | **OpenJDK 8** (java-1.8.0-amazon-corretto) |
| Tomcat | 9.0.53 | 9.0.121 |
| PetClinic | `main` (Spring 5.3.9, Spring4Shell 취약) | `chore/stack-update-2026` (5.3.39) |
| 배포 | WAR 복사, AMI v1 | AMI v2 → Green 대상 그룹 → Internal ALB 가중치 전환(Canary→Blue/Green) → 롤백 리허설 |
| DB 접속 | `-Djdbc.*` 주입 (처음부터) | + Secrets Manager |
| 노출 통제 | 취약 상태이므로 Public ALB SG를 팀 IP로 제한 | 패치 후 전체 공개 |

## 1. 결정표

| 구성요소 | 제공본 (2021, 강사 배포) | 채택 (2026) | 이유 | 제약·주의 |
|---|---|---|---|---|
| OS | Ubuntu 18.04 (README) → Phase 1 기준환경은 **Amazon Linux 2** (2025-06 표준 지원 종료, 슬라이드의 yum 계열) | **Amazon Linux 2023** | 지원 종료 OS 이관 = 현업의 2025~26년 대표 작업. SSM·CloudWatch 에이전트 기본 탑재 | 차이: yum→dnf, amazon-linux-extras 없음, MySQL 클라이언트 MariaDB 5.5→10.5(옛 클라이언트는 RDS MySQL 8 인증 불가), IMDSv2 기본, OpenSSL 3, SELinux permissive 기본. Tomcat은 두 OS 모두 tarball |
| JDK | 컴파일 1.8 / CI 11 → Phase 1은 **Corretto 11** | **OpenJDK 8 = `java-1.8.0-amazon-corretto-devel`** (AL2023 표준 저장소, "Amazon Corretto's packaging of the OpenJDK 8 code") — 9/14 팀 결정: 요구사항 "Tomcat / OpenJDK" 준수, 메이저 유지·패치만 최신화 | Spring 5.3.39가 17 지원, AL2023에 `java-17-amazon-corretto-headless` | 안 뜨면 `java.version`을 11로 내리고 사유 기록(후퇴 경로) |
| Tomcat | 9.0.53 | **9.0.121** (2026-09 기준 9.0.x 최신) | 9.0.x는 계속 패치 중, CVE 누적분 해소 | 10.x는 `jakarta.*`라 배포 불가(404/ClassNotFound) — 실험으로 확인해 케이스북에 기록 |
| Apache | 2.4 (AL2 httpd 2.4.5x) | **2.4.x** (AL2023 httpd) | — | — |
| MySQL | 단일 VM(5.7 추정), 공인 IP | **RDS MySQL 8.0 최신 마이너**, private subnet | 5.7은 2023-10 지원 종료 | 저장 암호화는 생성 시에만 설정 가능 |
| Spring Framework | 5.3.9 | **5.3.39** (5.3 계열 마지막 OSS) | **CVE-2022-22965 Spring4Shell** — 제공본 조건(JDK9+·Tomcat·WAR·webmvc) 전부 해당. 5.3.18+에서 수정 | 5.3 OSS 지원은 2024-08 종료 → 중기 로드맵: Spring 6 + Tomcat 10 전환 |
| Hibernate | 5.5.6.Final | **5.6.15.Final** (5.x 마지막) | JDK 17에서 프록시 생성(byte-buddy) 호환 | 여전히 `javax.persistence` → Spring 5.3과 호환 |
| MySQL Connector/J | 8.0.19 (`mysql:mysql-connector-java`) | **8.4.0 LTS** (`com.mysql:mysql-connector-j`) | CVE 해소, 8.0.31부터 좌표 변경 | 드라이버 클래스명은 동일(`com.mysql.cj.jdbc.Driver`) |
| wro4j (LESS 빌드 플러그인) | 1.8.0 | **1.8.0 유지** (1.9+는 Java 9 필요) + `wro4j-extensions`에서 jshint 제외(minimatch 범위 충돌) | Java 8 유지 | 빌드 실패 시 첫 용의자 |
| JaCoCo | 0.8.6 | 0.8.12 | 0.8.6은 Java 16까지만 | 테스트 실행 시에만 관여 |
| JAXB runtime | 2.3.4 | 2.3.9 | 패치 | — |
| Maven (래퍼) | 3.5.4 | 3.9.16 | 최신 플러그인 호환 (Java 8에서도 동작 확인) | `.mvn/wrapper/maven-wrapper.properties` 한 줄, 래퍼 jar은 그대로 |
| 배포 방식 | `tomcat7:deploy` (manager 앱, `tomcat/tomcat` 평문 계정) | WAR 파일 복사(→ 이후 S3 → WAS pull), **manager 앱 삭제** | 관리 콘솔 노출·평문 계정 제거 | — |
| DB 접속정보 | pom.xml에 하드코딩 | 부팅 시 Secrets Manager 조회 → **빌드 시점 `mvnw -Djdbc.*` 주입**(Maven 리소스 필터링) | 런타임 `-Djdbc.*` 오버라이드는 **동작하지 않음** — MySQL 프로필 필터링이 `datasource-config.xml`까지 치환해 `${jdbc.url}` 자리표시자가 사라짐(9/14 배포에서 확인). 값은 XML 속성이라 `&`→`&amp;`, 비밀번호는 XML 이스케이프 | 비밀은 저장소·명령줄에 없음, WAR 안에만 |
| 로그 | `jpa.showSql=true` | `false` (운영) | 로그 폭증 방지 | — |

## 2. 적용 방법 — pom.xml 10줄 + Maven 래퍼 1줄 (브랜치 `chore/stack-update-2026`)

```
java.version              1.8      → 17
Maven wrapper             3.5.4    → 3.9.16 (.mvn/wrapper/maven-wrapper.properties)
spring-framework.version  5.3.9    → 5.3.39
wro4j.version             1.8.0    → 1.10.1
tomcat.version            9.0.53   → 9.0.121
jaxb-runtime.version      2.3.4    → 2.3.9
hibernate.version         5.5.6.Final → 5.6.15.Final
mysql-driver.version      8.0.19   → 8.4.0
jacoco-maven-plugin       0.8.6    → 0.8.12
MySQL 프로파일 의존성      mysql:mysql-connector-java → com.mysql:mysql-connector-j
```

## 3. 실패 시 후퇴 경로 (검증 중 막히면 순서대로)

1. 빌드가 wro4j/less4j에서 실패 → `wro4j.version`을 1.8.0으로 되돌리고 JDK 17 유지해 재시도
2. 기동 시 Hibernate/byte-buddy `Unsupported class file major version` → Hibernate 5.6.15 확인(이미 적용). 그래도 실패면 `java.version` 11 + `openjdk-11-jdk-headless`
3. 테스트(`./mvnw test`)만 실패 → 앱 기동엔 영향 없음. Mockito 3.11 → 4.11.0 상향 후 재시도, 안 되면 `-DskipTests`로 진행하고 케이스북에 기록
4. MySQL 접속 `Public Key Retrieval is not allowed` → JDBC URL에 `&allowPublicKeyRetrieval=true` (로컬 MySQL만; RDS는 TLS라 불필요)

## 4. 로드맵 (발표 마지막 슬라이드)

- 단기(이번 프로젝트): 위 표대로 패치·업그레이드 완료, 3-Tier 이관
- 중기: Spring 6.x + Tomcat 10.1 + Jakarta 네임스페이스 전환 (코드 수정 필요, 별도 프로젝트)
