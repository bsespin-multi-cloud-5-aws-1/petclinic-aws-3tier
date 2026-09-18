#!/bin/bash
# Bastion (AL2023) — 운영자 SSH 진입점 (SSM Session Manager 대신). WEB·WAS 는 같은 키로 -J 점프, DB 는 mariadb 클라이언트로 RDS Proxy(TLS) 경유
# sshd 로그(/var/log/secure)는 CloudWatch Agent 로 /petclinic/bastion/secure 에 남긴다 — 누가 언제 들어왔나 (서버에만 두지 않음)
set -uo pipefail
exec > >(tee -a /var/log/mc-userdata.log) 2>&1

dnf install -y mariadb105 jq amazon-cloudwatch-agent

for i in $(seq 1 12); do
  /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl -a fetch-config -m ec2 -c "ssm:${cwagent_param}" -s && { echo "cwagent configured"; break; }
  echo "cwagent config retry $i/12"; sleep 10
done

cat > /etc/motd <<'MOTD'
mc-bastion — WEB/WAS: ssh ec2-user@<사설 IP> (같은 키)  ·  DB: mysql --ssl -h <rds-proxy-endpoint> -u petclinic_app -p
MOTD
