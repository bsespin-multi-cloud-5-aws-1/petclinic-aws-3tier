# PetClinic on AWS 3-tier — AWS 1팀

Spring PetClinic 을 AWS 3-tier 로 올린 팀 프로젝트 레포입니다. 앱 소스(WAS)와 서버 실행 설정, Terraform, 설계 문서를 함께 둡니다.

```
CloudFront → 공개 ALB → web(Apache) → 내부 ALB → WAS(Tomcat 9, 이 레포의 앱) → RDS MySQL 주 DB / 읽기 복제본
```

앱 원본은 [spring-framework-petclinic](https://github.com/spring-petclinic/spring-framework-petclinic) 을 과제용으로 고친
`SteveKimbespin/petclinic_btc` 이고, 여기에 **읽기 복제본 라우팅**과 **AWS RDS 연결 설정**을 더했습니다.

## 폴더

| 폴더 | 내용 |
|---|---|
| `src/`, `pom.xml` | WAS 에서 실제로 돌던 앱 소스 (복구 경위·원본과 다른 점: [RECOVERED.md](RECOVERED.md)) |
| `deploy/` | WAS 서버 실행 설정 — Tomcat 시작 전 DB 주소·계정을 넣는 방법 ([deploy/README.md](deploy/README.md)) |
| `infra/` | 단계별 Terraform (각 폴더 README 참고). 콘솔 최종 상태를 맞춘 코드는 [petclinic-iac](https://github.com/grapefruit0205/petclinic-iac) |
| `docs/` | 설계 도면 · 노션 정리본 · 학습 자료 · 정적 사이트 |

## 앱에서 바뀐 점 한 줄 요약

`@Transactional(readOnly = true)` 인 요청은 읽기 복제본(`jdbc.read.url`)으로, 나머지는 주 DB(`jdbc.url`)로 보냅니다
(`config/ReadWriteRoutingDataSource.java`, `spring/datasource-config.xml`).

## 필요한 것

- JDK 8 (운영은 Amazon Corretto 8)
- Tomcat 9 (운영은 9.0.121)
- Maven 은 동봉된 `./mvnw` 사용

## WAR 빌드

```bash
./mvnw clean package -P MySQL -DskipTests
```

`target/petclinic.war` 가 나옵니다. Tomcat 의 `webapps/` 에 넣으면 `http://<서버>:8080/petclinic` 으로 열립니다.

> 원래 README 의 `./mvnw tomcat7:deploy` 는 쓸 수 없습니다. 지금 `pom.xml` 에는 `tomcat7-maven-plugin` 이 없습니다.

## DB 연결

`pom.xml` 의 `MySQL` 프로필 주소는 자리표시자(`WRITE_DB_HOST` · `READ_DB_HOST`)이고 비밀번호는 비어 있습니다.
운영에서는 빌드 때 값을 넣지 않고, **실행할 때** 바깥 파일로 덮어씁니다.

1. Tomcat 시작 전 `deploy/fetch_db_secret.py` 가 Secrets Manager 에서 계정을 받아 `/run/petclinic/data-access.properties` 생성
2. `setenv.sh` 의 `-Dpetclinic.config.location=file:/run/petclinic/data-access.properties` 로 WAR 안 기본 설정 대신 그 파일을 읽음

직접 MySQL 에 붙여 볼 때도 같은 방식으로 파일을 만들어 `petclinic.config.location` 으로 넘기면 됩니다.

```properties
jdbc.driverClassName=com.mysql.cj.jdbc.Driver
jdbc.url=jdbc:mysql://<주 DB 주소>:3306/petclinic?useUnicode=true
jdbc.read.url=jdbc:mysql://<복제본 주소>:3306/petclinic?useUnicode=true
jdbc.username=<계정>
jdbc.password=<비밀번호>
jdbc.initLocation=classpath:db/mysql/schema.sql
jdbc.dataLocation=classpath:db/mysql/data.sql
jpa.database=MYSQL
jpa.showSql=false
```

- 복제본이 없으면 `jdbc.read.url` 에 주 DB 주소를 그대로 넣으면 됩니다.
- 앱이 시작할 때마다 `schema.sql` · `data.sql` 이 주 DB 에 실행됩니다.

## 로컬에서 H2 로 실행

기본 프로필이 H2(메모리 DB)라 따로 설정할 것이 없습니다. 읽기·쓰기 모두 같은 메모리 DB 를 씁니다.

```bash
./mvnw jetty:run-war
```

## 라이선스

Apache License 2.0 — [LICENSE.txt](LICENSE.txt)
