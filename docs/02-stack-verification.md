# 주말 검증 절차 — Phase 1(Blue) / Phase 2(Green) 스택 리허설 (9/12~13)

두 번 검증한다. 같은 방법으로 EC2 2대(또는 1대를 순서대로).

| 트랙 | 역할 | OS | JDK | Tomcat | PetClinic 브랜치 |
|---|---|---|---|---|---|
| **A. Blue (Phase 1 리허설)** | 제공된 구버전을 그대로 올림 = "현재 환경" | **Amazon Linux 2** | Corretto 11 | 9.0.53 | `main` |
| **B. Green (Phase 2 리허설)** | 업그레이드 스택 | **Amazon Linux 2023** | OpenJDK 8 (Corretto 빌드) | 9.0.121 | `chore/stack-update-2026` |

끝나면 아래 **기록표**를 트랙별로 채운다. 둘 다 DB는 주말용 RDS 하나를 같이 쓴다.

## 0. 준비 (콘솔)

- **RDS**: MySQL 8.0, db.t3.micro, 단일 AZ, 기본 VPC, 퍼블릭 액세스 아니요, 초기 DB 이름 `petclinic`, 마스터 `admin`. 보안그룹 `sg-rds-weekend`: 3306 ← `sg-ec2-weekend`
- **EC2 A**: Amazon Linux 2 AMI (x86_64), t3.medium, 20GB, 기본 VPC 퍼블릭 서브넷, IAM 역할 `mc-ec2-role`(SSM), 보안그룹 `sg-ec2-weekend`: 8080 ← 내 IP (22 안 엶 — SSM으로 접속)
- **EC2 B**: Amazon Linux 2023 AMI, 나머지 동일
- 접속: EC2 → 연결 → **Session Manager**
- 검증 끝나면 EC2 종료, RDS 삭제(스냅샷 없이)

> AL2 AMI는 표준 지원이 끝났지만 실행은 됩니다. "지원 종료된 OS 위의 Legacy 앱"이 Phase 1의 출발점입니다.

## A. Blue — Amazon Linux 2 + Corretto 11 + Tomcat 9.0.53 + `main`

```bash
sudo yum update -y
sudo yum install -y java-11-amazon-corretto-headless git unzip
java -version                                   # 11.x
cd /tmp && curl -fLO https://archive.apache.org/dist/tomcat/tomcat-9/v9.0.53/bin/apache-tomcat-9.0.53.tar.gz
sudo mkdir -p /opt/tomcat && sudo tar xzf apache-tomcat-9.0.53.tar.gz -C /opt/tomcat --strip-components=1
sudo useradd -r -m -d /opt/tomcat -s /sbin/nologin tomcat
sudo rm -rf /opt/tomcat/webapps/*               # manager·docs·examples 제거
sudo chown -R tomcat:tomcat /opt/tomcat

cd ~ && git clone https://github.com/bsespin-multi-cloud-5-aws-1/petclinic-aws-3tier.git
cd petclinic-aws-3tier                          # main = 제공본 그대로
./mvnw -q package -P MySQL -DskipTests
unzip -l target/petclinic.war | grep -E 'spring-webmvc|hibernate-core|mysql-connector'   # 5.3.9 / 5.5.6 / 8.0.19
```

배포 + DB 접속정보 런타임 주입 (`<RDS>`·`<암호>`는 본인 값):

```bash
sudo cp target/petclinic.war /opt/tomcat/webapps/
sudo tee /opt/tomcat/bin/setenv.sh >/dev/null <<'EOF'
export CATALINA_OPTS="$CATALINA_OPTS -Xms512m -Xmx1g -Djdbc.url=jdbc:mysql://<RDS>:3306/petclinic?useUnicode=true -Djdbc.username=admin -Djdbc.password=<암호>"
EOF
sudo chown tomcat:tomcat /opt/tomcat/bin/setenv.sh && sudo chmod +x /opt/tomcat/bin/setenv.sh
sudo tee /etc/systemd/system/tomcat.service >/dev/null <<'EOF'
[Unit]
Description=Apache Tomcat 9
After=network.target
[Service]
Type=simple
User=tomcat
Group=tomcat
Environment=JAVA_HOME=/usr/lib/jvm/java-11-amazon-corretto.x86_64
Environment=CATALINA_HOME=/opt/tomcat
ExecStart=/opt/tomcat/bin/catalina.sh run
Restart=on-failure
[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload && sudo systemctl enable --now tomcat
```

확인:

```bash
sudo tail -n 30 /opt/tomcat/logs/catalina.out            # "Server startup in" + 예외 없음
curl -s localhost:8080/petclinic/vets.json | head -c 200  # 수의사 JSON
```

브라우저 `http://<EC2 A 공인IP>:8080/petclinic/` → Find Owners 10명 → 주인 1명 추가.

> AL2의 `yum install mysql`은 MariaDB 5.5 클라이언트라 RDS MySQL 8(`caching_sha2_password`)에 접속이 안 됩니다. DB 확인은 앱(`/vets.json`, 화면)으로 하거나 트랙 B의 `mariadb105`로 하세요. 이게 케이스북 첫 항목 "옛 클라이언트 vs 새 서버".

(선택) WEB 리허설 — 같은 박스에 Apache 올려 프록시만 확인:

```bash
sudo yum install -y httpd
echo '<h1>Mission Critical Pet Clinic</h1><a href="/petclinic/">진료 시스템 입장</a>' | sudo tee /var/www/html/index.html
sudo tee /etc/httpd/conf.d/petclinic.conf >/dev/null <<'EOF'
ProxyPreserveHost On
ProxyPass        /petclinic/ http://127.0.0.1:8080/petclinic/
ProxyPassReverse /petclinic/ http://127.0.0.1:8080/petclinic/
EOF
sudo systemctl enable --now httpd && curl -s localhost/petclinic/vets.json | head -c 100
```

## B. Green — Amazon Linux 2023 + OpenJDK 8 (java-1.8.0-amazon-corretto) + Tomcat 9.0.121 + `test`

트랙 A와 같고 다른 줄만:

```bash
sudo dnf install -y java-1.8.0-amazon-corretto-devel git unzip mariadb105
java -version                                   # 17.x
cd /tmp && curl -fLO https://dlcdn.apache.org/tomcat/tomcat-9/v9.0.121/bin/apache-tomcat-9.0.121.tar.gz
sudo mkdir -p /opt/tomcat && sudo tar xzf apache-tomcat-9.0.121.tar.gz -C /opt/tomcat --strip-components=1
# useradd / rm webapps / chown 동일
cd ~ && git clone -b test https://github.com/bsespin-multi-cloud-5-aws-1/petclinic-aws-3tier.git
cd petclinic-aws-3tier && ./mvnw -q package -P MySQL -DskipTests     # Maven 3.9.16 자동 다운로드
unzip -l target/petclinic.war | grep -E 'spring-webmvc|hibernate-core|mysql-connector'   # 5.3.39 / 5.6.15 / 8.4.0
```

systemd 유닛의 `JAVA_HOME=/usr/lib/jvm/java-1.8.0-amazon-corretto.x86_64`. 나머지 동일.

DB 직접 확인(AL2023 클라이언트는 MySQL 8 인증 지원):

```bash
mysql -h <RDS> -u admin -p -e "show tables from petclinic; select count(*) from petclinic.owners;"
```

> 9.0.121 링크가 404면 https://dlcdn.apache.org/tomcat/tomcat-9/ 에서 현재 번호로. 버전 결정표도 같이 수정.

## C. (선택, 15분) Tomcat 10 실패 재현 — "왜 9인가"

트랙 B 박스에서 Tomcat 10.1 tarball을 `/opt/tomcat10`에 풀고 같은 WAR를 `webapps/`에 넣어 8081로 기동 → 404/ClassNotFound(`javax.servlet`) 확인 → `webapps-javaee/`에 넣으면 자동 변환되어 뜨는지도 확인 → 케이스북에 "Tomcat 9 유지, 10은 로드맵" 근거.

## D. 기록표 (트랙별로 채워 1일차 멘토링에 제출)

| 항목 | 명령 | A. Blue | B. Green |
|---|---|---|---|
| OS | `cat /etc/os-release \| head -2` | | |
| JDK | `java -version` | | |
| Tomcat | `/opt/tomcat/bin/version.sh \| grep 'Server number'` | | |
| Spring / Hibernate / 드라이버 | `unzip -l target/petclinic.war \| grep -E 'spring-webmvc\|hibernate-core\|mysql-connector'` | | |
| 빌드 시간 | `time ./mvnw -q package -P MySQL -DskipTests` | | |
| 기동 시간 | catalina.out `Server startup in` | | |
| 화면 조회·등록 | Find Owners 10명 / 주인 추가 | ☐ | ☐ |
| `/vets.json` | curl 200 | ☐ | ☐ |
| 막힌 것 | 증상 → 원인 → 조치 | | |

## E. 흔한 문제

| 증상 | 원인 | 조치 |
|---|---|---|
| (A) `mysql` 접속 시 `caching_sha2_password cannot be loaded` | AL2 MariaDB 5.5 클라이언트 | 앱으로 확인하거나 AL2023에서 확인. 케이스북 기록 |
| (B) 빌드 중 wro4j/less4j 오류 | LESS 플러그인 + JDK 17 | `wro4j.version` 1.8.0으로 되돌려 재시도 |
| (B) `Unsupported class file major version` | byte-buddy 구버전 | Hibernate 5.6.15 확인(이미 적용). 그래도면 `java.version` 11 |
| `Access denied ... CREATE DATABASE` | schema.sql의 `CREATE DATABASE IF NOT EXISTS` | RDS 초기 DB 이름 `petclinic` + 마스터 계정이면 문제 없음 |
| 8080 접속 안 됨 | 보안그룹 / Tomcat 미기동 | `sudo systemctl status tomcat`, `sudo journalctl -u tomcat -n 50` |
| 한글 깨짐 | 문자셋 | URL에 `&characterEncoding=UTF-8` |
| catalina.sh가 JAVA_HOME을 못 찾음 | 경로 다름 | `readlink -f $(which java)`로 실제 경로 확인 후 유닛 수정 |
