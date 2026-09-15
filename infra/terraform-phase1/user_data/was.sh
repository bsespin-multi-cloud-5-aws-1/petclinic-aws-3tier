#!/bin/bash
# WAS (Tomcat + PetClinic) — Blue: 제공본 main 그대로(Spring 5.3.9), OpenJDK 8, Tomcat ${tomcat_version}. AL2023.
# 요구사항 "Tomcat / OpenJDK": AL2023 표준 저장소의 java-1.8.0-amazon-corretto = OpenJDK 8 코드의 AWS 패키징 (java -version → openjdk 1.8.0)
set -uo pipefail
exec > >(tee -a /var/log/mc-userdata.log) 2>&1
REGION="${region}"
TOMCAT_VER="${tomcat_version}"

dnf install -y java-1.8.0-amazon-corretto-devel git unzip jq

# ---- DB 자격증명: Secrets Manager(RDS 관리형) → 빌드 시점 주입 ----
# pom 의 MySQL 프로필이 datasource-config.xml 까지 Maven 필터링하므로 런타임 -Djdbc.* 는 무시됨 → mvnw -Djdbc.* 로 빌드 시 주입
DB_SECRET=$(aws secretsmanager get-secret-value --region "$REGION" --secret-id "${db_secret_arn}" --query SecretString --output text)
DB_USER=$(echo "$DB_SECRET" | jq -r .username)
DB_PASS=$(echo "$DB_SECRET" | jq -r .password)
# 값이 XML 속성에 들어가므로 & < > " 이스케이프 (RDS 관리형 비밀번호엔 특수문자가 꼭 있음)
DB_PASS_XML=$(printf '%s' "$DB_PASS" | python3 -c 'import sys,html; print(html.escape(sys.stdin.read(), quote=True), end="")')
JDBC_URL="jdbc:mysql://${db_endpoint}:3306/${db_name}?useUnicode=true&amp;characterEncoding=UTF-8&amp;serverTimezone=Asia/Seoul"

# ---- Tomcat (Blue = 9.0.53 은 archive 에만 있음) ----
cd /tmp && curl -fLO "https://dlcdn.apache.org/tomcat/tomcat-9/v$TOMCAT_VER/bin/apache-tomcat-$TOMCAT_VER.tar.gz" \
  || curl -fLO "https://archive.apache.org/dist/tomcat/tomcat-9/v$TOMCAT_VER/bin/apache-tomcat-$TOMCAT_VER.tar.gz"
mkdir -p /opt/tomcat && tar xzf "apache-tomcat-$TOMCAT_VER.tar.gz" -C /opt/tomcat --strip-components=1
id tomcat >/dev/null 2>&1 || useradd -r -m -d /opt/tomcat -s /sbin/nologin tomcat
rm -rf /opt/tomcat/webapps/*   # ROOT·manager·examples 제거 (manager 는 공격 표적, ROOT 는 / 헬스체크 거짓 통과)

# ---- 앱 빌드 (제공본 그대로) ----
cd /opt && git clone -b "${repo_branch}" "${repo_url}" petclinic-src
cd /opt/petclinic-src && ./mvnw -q package -P MySQL -DskipTests \
  "-Djdbc.url=$JDBC_URL" "-Djdbc.username=$DB_USER" "-Djdbc.password=$DB_PASS_XML" \
  && cp target/petclinic.war /opt/tomcat/webapps/ || echo "BUILD FAILED: petclinic.war not deployed"
rm -rf /opt/petclinic-src/target/classes /opt/petclinic-src/target/petclinic   # 평문 자격증명이 든 중간산물 제거

# setenv.sh 는 JVM 옵션만 (자격증명을 넣으면 셸 eval 오류 + ps 노출)
cat > /opt/tomcat/bin/setenv.sh <<'SETENV'
export CATALINA_OPTS="$CATALINA_OPTS -Xms512m -Xmx1g"
SETENV
chown -R tomcat:tomcat /opt/tomcat

cat > /etc/systemd/system/tomcat.service <<UNIT
[Unit]
Description=Apache Tomcat 9
After=network.target
[Service]
Type=forking
User=tomcat
Group=tomcat
Environment=JAVA_HOME=/usr/lib/jvm/java-1.8.0-amazon-corretto.x86_64
Environment=CATALINA_HOME=/opt/tomcat
ExecStart=/opt/tomcat/bin/startup.sh
ExecStop=/opt/tomcat/bin/shutdown.sh
Restart=on-failure
[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload && systemctl enable --now tomcat

# 확인
sleep 25
curl -s -o /dev/null -w "petclinic %%{http_code}\n" "http://localhost:8080${app_context}/"
curl -s "http://localhost:8080${app_context}/vets.json" | head -c 120; echo
