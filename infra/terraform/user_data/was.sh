#!/bin/bash
# WAS (Tomcat) 부팅 스크립트. 골든 AMI가 아니면 Corretto 17 · Tomcat 9.0.121 · WAR 빌드까지 수행 (AL2023, 5~8분)
set -uo pipefail
exec > >(tee -a /var/log/mc-userdata.log) 2>&1
REGION="${region}"
TOMCAT_VER="9.0.121"

# DB 자격증명은 Secrets Manager(RDS 관리형)에서 조회 → 빌드 시점에 Maven 리소스 필터링으로 주입
# (pom의 MySQL 프로필이 datasource-config.xml까지 필터링하므로 런타임 -Djdbc.* 오버라이드는 동작하지 않음)
dnf install -y jq >/dev/null 2>&1 || true
DB_SECRET=$(aws secretsmanager get-secret-value --region "$REGION" --secret-id "${db_secret_arn}" --query SecretString --output text)
DB_USER=$(echo "$DB_SECRET" | jq -r .username)
DB_PASS=$(echo "$DB_SECRET" | jq -r .password)
# 비밀번호도 XML 속성으로 들어가므로 & < > " 를 XML 이스케이프 (python3는 AL2023 기본 포함)
DB_PASS_XML=$(printf '%s' "$DB_PASS" | python3 -c 'import sys,html; print(html.escape(sys.stdin.read(), quote=True), end="")')
# 필터링 대상이 XML 속성이므로 &는 &amp; 로 (data-access.properties의 jdbc.url은 미사용)
JDBC_URL="jdbc:mysql://${rds_proxy_endpoint}:3306/${db_name}?useUnicode=true&amp;characterEncoding=UTF-8&amp;serverTimezone=Asia/Seoul&amp;sslMode=REQUIRED"

if [ ! -x /opt/tomcat/bin/catalina.sh ]; then
  dnf install -y java-17-amazon-corretto-headless git unzip jq amazon-cloudwatch-agent
  cd /tmp && curl -fLO "https://dlcdn.apache.org/tomcat/tomcat-9/v$TOMCAT_VER/bin/apache-tomcat-$TOMCAT_VER.tar.gz" \
    || curl -fLO "https://archive.apache.org/dist/tomcat/tomcat-9/v$TOMCAT_VER/bin/apache-tomcat-$TOMCAT_VER.tar.gz"
  mkdir -p /opt/tomcat && tar xzf "apache-tomcat-$TOMCAT_VER.tar.gz" -C /opt/tomcat --strip-components=1
  id tomcat >/dev/null 2>&1 || useradd -r -m -d /opt/tomcat -s /sbin/nologin tomcat
  rm -rf /opt/tomcat/webapps/*
  cd /opt && git clone -b "${repo_branch}" "${repo_url}" petclinic-src
  cd /opt/petclinic-src && ./mvnw -q package -P MySQL -DskipTests \
    "-Djdbc.url=$JDBC_URL" "-Djdbc.username=$DB_USER" "-Djdbc.password=$DB_PASS_XML" \
    && cp target/petclinic.war /opt/tomcat/webapps/ || echo "BUILD FAILED: petclinic.war not deployed"
  rm -rf /opt/petclinic-src/target/classes /opt/petclinic-src/target/petclinic   # 평문 자격증명이 든 필터링 결과 제거
  chown -R tomcat:tomcat /opt/tomcat
  cat > /etc/systemd/system/tomcat.service <<UNIT
[Unit]
Description=Apache Tomcat 9
After=network.target
[Service]
Type=simple
User=tomcat
Group=tomcat
Environment=JAVA_HOME=/usr/lib/jvm/java-17-amazon-corretto.x86_64
Environment=CATALINA_HOME=/opt/tomcat
ExecStart=/opt/tomcat/bin/catalina.sh run
ExecStop=/usr/local/bin/mc-sync-logs.sh
Restart=on-failure
[Install]
WantedBy=multi-user.target
UNIT
  systemctl daemon-reload
fi


# JVM 옵션만 (DB 자격증명은 WAR 안에 주입됨 → 명령줄·ps에 노출 없음)
cat > /opt/tomcat/bin/setenv.sh <<'SETENV'
export CATALINA_OPTS="$CATALINA_OPTS -Xms512m -Xmx1g"
SETENV
chown tomcat:tomcat /opt/tomcat/bin/setenv.sh && chmod 750 /opt/tomcat/bin/setenv.sh

cat > /usr/local/bin/mc-sync-logs.sh <<SYNC
#!/bin/bash
TOKEN=\$(curl -s -X PUT http://169.254.169.254/latest/api/token -H 'X-aws-ec2-metadata-token-ttl-seconds: 60')
IID=\$(curl -s -H "X-aws-ec2-metadata-token: \$TOKEN" http://169.254.169.254/latest/meta-data/instance-id)
aws s3 sync /opt/tomcat/logs "s3://${logs_bucket}/was/\$IID/" --region "$REGION" || true
SYNC
chmod +x /usr/local/bin/mc-sync-logs.sh

cat > /opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json <<'CW'
{"metrics":{"append_dimensions":{"AutoScalingGroupName":"$${aws:AutoScalingGroupName}","InstanceId":"$${aws:InstanceId}"},
 "metrics_collected":{"mem":{"measurement":["mem_used_percent"]},"disk":{"measurement":["used_percent"],"resources":["/"]}}},
 "logs":{"logs_collected":{"files":{"collect_list":[
  {"file_path":"/opt/tomcat/logs/catalina.out","log_group_name":"${log_group_prefix}/catalina","log_stream_name":"{instance_id}"},
  {"file_path":"/opt/tomcat/logs/localhost_access_log.*.txt","log_group_name":"${log_group_prefix}/access","log_stream_name":"{instance_id}"},
  {"file_path":"/opt/tomcat/logs/events.log","log_group_name":"${log_group_prefix}/events","log_stream_name":"{instance_id}"}]}}}}
CW
/opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl -a fetch-config -m ec2 -s -c file:/opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json || true

systemctl enable --now tomcat
