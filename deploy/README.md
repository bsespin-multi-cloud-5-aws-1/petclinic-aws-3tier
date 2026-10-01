# WAS 서버 실행 설정 (WAS AMI v6 에서 복구)

코드(WAR)만으로는 읽기/쓰기 분리가 돌지 않는다. 운영 WAS 는 아래 파일로 DB 주소·계정을 **실행할 때** 넣었다.

| 이 폴더 | 서버 위치 | 하는 일 |
|---|---|---|
| `systemd/tomcat.service` | `/etc/systemd/system/tomcat.service` | `bootstrap.env` 를 읽고, 시작 전(ExecStartPre)에 `fetch_db_secret.py` 실행 → Tomcat 실행 |
| `bootstrap.env.example` | `/etc/petclinic/bootstrap.env` | 리전 · 시크릿 ID · 주 DB/복제본 주소 · 포트 · DB 이름 (값은 자리표시자) |
| `fetch_db_secret.py` | `/opt/petclinic-bootstrap/fetch_db_secret.py` | Secrets Manager 에서 계정을 받아 `/run/petclinic/data-access.properties`(0600, 메모리) 생성 |
| `tomcat/setenv.sh` | `/opt/tomcat/bin/setenv.sh` (`/opt/tomcat` → `/opt/apache-tomcat-9.0.121`) | 힙 512m–1g · `-Dpetclinic.config.location=file:/run/petclinic/data-access.properties` |

## 흐름

1. systemd 가 `/etc/petclinic/bootstrap.env` 를 환경 변수로 읽음
2. `fetch_db_secret.py` → `/run/petclinic/data-access.properties` (`jdbc.url` · `jdbc.read.url` · 계정)
3. `setenv.sh` 의 `petclinic.config.location` → `datasource-config.xml` 의 `property-placeholder` 가 WAR 안 기본 파일 대신 2번 파일을 읽음
4. `ReadWriteRoutingDataSource` 가 `readOnly` 트랜잭션은 `jdbc.read.url`(복제본), 나머지는 `jdbc.url`(주 DB)로

## 서버 쪽 전제

- 사용자/그룹 `tomcat`, Amazon Corretto 8 (`/usr/lib/jvm/java-1.8.0-amazon-corretto.x86_64`), Tomcat 9.0.121
- `/data` 마운트(`RequiresMountsFor=/data`, 힙 덤프 `/data/dump`), 앱 로그 `/opt/tomcat/logs/petclinic`
- 인스턴스 역할에 해당 시크릿 `secretsmanager:GetSecretValue` 권한
- Tomcat `conf/` 는 커넥터 기본값(8080, 스레드 기본 200)이라 따로 넣지 않음. `tomcat-users.xml` 은 비밀번호가 있어 뺌
