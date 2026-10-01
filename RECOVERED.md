# 실행 중이던 WAS 소스 (2026-10-01 복구)

AWS 정리(2026-10-01) 뒤 남아 있던 WAS AMI v6(`was-goldenImage-v6`, ami-0eac111a62f8b8c94) 루트 디스크 스냅샷
`snap-074fad84289cfaccb` 에서 `/opt/petclinic-build/source` 를 꺼낸 것이다.

- 원본: 팀 저장소 `bsespin-multi-cloud-5-aws-1/petclinic-aws-3tier` 클론 + 커밋 안 한 수정(2026-09-26 KST 27일 03:27 빌드)
- 복구한 그대로의 소스(원래 main 위)로 빌드한 WAR = 운영 중이던 WAR (md5 `be905ed1394dc4b2f6ea2efbee7e0399`, 42,711,209 bytes). 복구 원본: https://github.com/grapefruit0205/petclinic-was-source
- **이 저장소 main 에는 `test` 브랜치(2026 스택 업데이트 Spring 5.3.39 · Hibernate 5.6.15 · 화면 개편 등)를 합친 위에 얹었다.** 그래서 main 을 빌드한 WAR 는 운영 WAR 와 같지 않다(2026-10-01 Corretto 8 + Maven 으로 `package` 빌드 통과, 테스트·실행은 안 해 봄). `datasource-config.xml` 은 복구판을 그대로 씀(test 의 연결 점검 설정 포함, 풀 크기만 복구판 값)
- 실행 환경: Amazon Corretto 1.8 · Tomcat 9.0.121 · mysql-connector-j 8.4.0 · Hibernate 5.5 · 프로필 `jpa`

## 원본 저장소 대비 바뀐 것 (두 번째 커밋)

| 파일 | 내용 |
|---|---|
| `config/ReadWriteRoutingDataSource.java` (새 파일) | `@Transactional(readOnly = true)` 면 읽기 복제본, 아니면 주 DB 로 보냄 |
| `spring/datasource-config.xml` | write·read 두 데이터소스 + 라우팅 데이터소스 |
| `spring/data-access.properties` | `jdbc.read.url` 추가 |
| `service/ClinicServiceImpl.java` | 라우팅용 수정 1줄 |
| `pom.xml` | AWS RDS 프로필(주 DB `database` · 복제본 `db-readonly` 주소) 등 |
| `logback.xml` | 로그 설정 |
| `deploy/` (서버 실행 설정, `deploy/README.md`) | `tomcat.service` · `bootstrap.env.example`(값은 자리표시자) · `setenv.sh` 와 함께 — Tomcat 시작 전(ExecStartPre) Secrets Manager 에서 DB 계정을 받아 `/run/petclinic/data-access.properties` 를 만드는 스크립트 (AMI 의 `/opt/petclinic-bootstrap`) |

## 지운 것

- `pom.xml` 의 예제 기본 DB 비밀번호(`petclinic`) → 빈 값
- Tomcat 설정(`tomcat-users.xml` 등)은 비밀번호가 있어 올리지 않음
- 실제 DB 비밀번호는 원래부터 소스·WAR 에 없음(실행 때 Secrets Manager 에서 받음)
- `pom.xml` 의 RDS 주소 → `WRITE_DB_HOST` · `READ_DB_HOST` 자리표시자 (운영에서는 `deploy/fetch_db_secret.py` 가 실행 때 주소를 채움)
