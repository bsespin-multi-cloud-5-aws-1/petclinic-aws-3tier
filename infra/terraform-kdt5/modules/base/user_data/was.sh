#!/bin/bash
# WAS (Tomcat ${tomcat_version} + PetClinic ${repo_branch}) — OpenJDK 8(Corretto) · AL2023 · JDBC 는 RDS Proxy(TLS 필수) 경유
set -uo pipefail
exec > >(tee -a /var/log/mc-userdata.log) 2>&1
REGION="${region}"
TOMCAT_VER="${tomcat_version}"

dnf install -y java-1.8.0-amazon-corretto-devel git unzip jq mariadb105 amazon-cloudwatch-agent

# ---- DB 자격증명: RDS 관리형 비밀 → 빌드 시점 주입 (루트 인라인 정책이 붙기 전일 수 있어 재시도) ----
DB_SECRET=""
for i in $(seq 1 18); do
  DB_SECRET=$(aws secretsmanager get-secret-value --region "$REGION" --secret-id "${db_secret_arn}" --query SecretString --output text 2>/dev/null) && [ -n "$DB_SECRET" ] && break
  echo "secret retry $i/18"; sleep 10
done
ADMIN_USER=$(echo "$DB_SECRET" | jq -r .username)
ADMIN_PASS=$(echo "$DB_SECRET" | jq -r .password)
# 앱 전용 사용자 비밀(교체 없음) — admin 은 7일마다 교체돼 WAR 에 박아두면 Proxy 인증이 깨짐
APP_SECRET=$(aws secretsmanager get-secret-value --region "$REGION" --secret-id "${app_secret_arn}" --query SecretString --output text)
DB_USER=$(echo "$APP_SECRET" | jq -r .username)
DB_PASS=$(echo "$APP_SECRET" | jq -r .password)
DB_PASS_XML=$(printf '%s' "$DB_PASS" | python3 -c 'import sys,html; print(html.escape(sys.stdin.read(), quote=True), end="")')
# Proxy 는 require_tls → sslMode=REQUIRED. 파라미터 그룹 require_secure_transport 와 짝
JDBC_URL="jdbc:mysql://${jdbc_host}:3306/${db_name}?useUnicode=true&amp;characterEncoding=UTF-8&amp;serverTimezone=Asia/Seoul&amp;sslMode=REQUIRED"

# ---- Proxy 3306 도달 대기 ----
for i in $(seq 1 30); do
  timeout 3 bash -c "echo > /dev/tcp/${jdbc_host}/3306" 2>/dev/null && { echo "DB endpoint reachable (${jdbc_host}:3306)"; break; }
  echo "waiting ${jdbc_host}:3306 ($i/30)"; sleep 10
done
# TCP 가 열려도 RDS Proxy 대상(target) 이 AVAILABLE 되기까지 몇 분 걸림 → 실제 로그인 성공까지 대기 (안 하면 앱이 Communications link failure 로 기동 실패)
for i in $(seq 1 30); do
  mysql --ssl -h "${jdbc_host}" -u "$ADMIN_USER" -p"$ADMIN_PASS" -e "SELECT VERSION() AS mysql_version; SHOW DATABASES LIKE '${db_name}';" && { echo "DB login OK ($i)"; break; }
  echo "DB login retry $i/30"; sleep 10
done
# 앱 사용자 생성/동기화 (멱등) — petclinic.* 만. 비밀번호는 비밀 값으로 매번 맞춤
DB_PASS_SQL=$(printf '%s' "$DB_PASS" | sed "s/'/''/g")
mysql --ssl -h "${jdbc_host}" -u "$ADMIN_USER" -p"$ADMIN_PASS" -e "CREATE USER IF NOT EXISTS '$DB_USER'@'%' IDENTIFIED BY '$DB_PASS_SQL'; ALTER USER '$DB_USER'@'%' IDENTIFIED BY '$DB_PASS_SQL'; GRANT ALL PRIVILEGES ON \`${db_name}\`.* TO '$DB_USER'@'%'; FLUSH PRIVILEGES;" \
  && echo "app user $DB_USER ready" || echo "APP USER FAILED"
# 앱 사용자로 Proxy 경유 로그인이 될 때까지 대기 — Proxy 의 SECRETS 인증 목록에 앱 비밀이 반영되기 전에 Tomcat 이 뜨면
# "Access denied for user petclinic_app" 로 컨텍스트 초기화 실패(404) 후 재시도하지 않음 (9/16 was-a 재현)
for i in $(seq 1 30); do
  mysql --ssl -h "${jdbc_host}" -u "$DB_USER" -p"$DB_PASS" -e "SELECT CURRENT_USER() AS app_login;" && { echo "app login via proxy OK ($i)"; break; }
  echo "app login retry $i/30"; sleep 10
done
unset ADMIN_PASS DB_SECRET DB_PASS_SQL

# ---- Tomcat ----
cd /tmp && curl -fLO "https://dlcdn.apache.org/tomcat/tomcat-9/v$TOMCAT_VER/bin/apache-tomcat-$TOMCAT_VER.tar.gz" \
  || curl -fLO "https://archive.apache.org/dist/tomcat/tomcat-9/v$TOMCAT_VER/bin/apache-tomcat-$TOMCAT_VER.tar.gz"
mkdir -p /opt/tomcat && tar xzf "apache-tomcat-$TOMCAT_VER.tar.gz" -C /opt/tomcat --strip-components=1
id tomcat >/dev/null 2>&1 || useradd -r -m -d /opt/tomcat -s /sbin/nologin tomcat
rm -rf /opt/tomcat/webapps/*

# ---- 앱 빌드 (MySQL 프로필 · 빌드 시 주입) ----
cd /opt && git clone -b "${repo_branch}" "${repo_url}" petclinic-src
cd /opt/petclinic-src && ./mvnw -q package -P MySQL -DskipTests \
  "-Djdbc.url=$JDBC_URL" "-Djdbc.username=$DB_USER" "-Djdbc.password=$DB_PASS_XML" \
  && cp target/petclinic.war /opt/tomcat/webapps/ || echo "BUILD FAILED: petclinic.war not deployed"
rm -rf /opt/petclinic-src/target/classes /opt/petclinic-src/target/petclinic

cat > /opt/tomcat/bin/setenv.sh <<'SETENV'
export CATALINA_OPTS="$CATALINA_OPTS -Xms512m -Xmx1g -Xloggc:/opt/tomcat/logs/gc.log -XX:+PrintGCDetails -XX:+PrintGCDateStamps"
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

# CloudWatch Agent (catalina · access · gc → /mc/was/*)
for i in $(seq 1 12); do
  /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl -a fetch-config -m ec2 -c "ssm:${cwagent_param}" -s && { echo "cwagent configured"; break; }
  echo "cwagent config retry $i/12"; sleep 10
done

# 앱 기동 확인 — DB 연결 실패로 404 면 Tomcat 재시작(최대 3회). Spring 컨텍스트는 실패 후 스스로 재시도하지 않음
for i in 1 2 3; do
  sleep 30
  code=$(curl -s -o /dev/null -w "%%{http_code}" "http://localhost:8080${app_context}/")
  [ "$code" = "200" ] && break
  echo "petclinic $code → tomcat restart ($i/3)"; systemctl restart tomcat
done
curl -s -o /dev/null -w "petclinic %%{http_code}\n" "http://localhost:8080${app_context}/"
curl -s "http://localhost:8080${app_context}/vets.json" | head -c 120; echo
mysql --ssl -h "${jdbc_host}" -u "$DB_USER" -p"$DB_PASS" "${db_name}" \
  -e "SELECT 'vets' t, COUNT(*) n FROM vets UNION ALL SELECT 'owners', COUNT(*) FROM owners UNION ALL SELECT 'pets', COUNT(*) FROM pets;" \
  || echo "DB CHECK FAILED: 앱이 스키마를 만들지 못함 → /opt/tomcat/logs/catalina.out"
unset DB_PASS DB_PASS_XML APP_SECRET
