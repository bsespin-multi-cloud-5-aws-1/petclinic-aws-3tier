#!/bin/bash
# WEB (Apache) 부팅 스크립트. 골든 AMI가 아니면 패키지 설치부터 수행 (AL2023)
set -uo pipefail
exec > >(tee -a /var/log/mc-userdata.log) 2>&1

if ! rpm -q httpd >/dev/null 2>&1; then
  dnf install -y httpd amazon-cloudwatch-agent
fi

cat > /etc/httpd/conf.d/petclinic.conf <<CONF
ProxyPreserveHost On
RedirectMatch 301 ^${app_context}$ ${app_context}/
ProxyPass        ${app_context}/ http://${internal_alb_dns}:8080${app_context}/
ProxyPassReverse ${app_context}/ http://${internal_alb_dns}:8080${app_context}/
SetEnvIf Request_URI "^/health.html$" nolog
CustomLog /var/log/httpd/access_log combined env=!nolog
CONF

echo ok > /var/www/html/health.html
echo '<h1>Mission Critical Pet Clinic</h1><a href="${app_context}/">진료 시스템 입장</a>' > /var/www/html/index.html
setsebool -P httpd_can_network_connect 1 || true
systemctl enable --now httpd

# CloudWatch Agent: access/error → ${log_group_prefix}/access, /error
cat > /opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json <<'CW'
{"metrics":{"append_dimensions":{"AutoScalingGroupName":"$${aws:AutoScalingGroupName}","InstanceId":"$${aws:InstanceId}"},
 "metrics_collected":{"mem":{"measurement":["mem_used_percent"]},"disk":{"measurement":["used_percent"],"resources":["/"]}}},
 "logs":{"logs_collected":{"files":{"collect_list":[
  {"file_path":"/var/log/httpd/access_log","log_group_name":"${log_group_prefix}/access","log_stream_name":"{instance_id}"},
  {"file_path":"/var/log/httpd/error_log","log_group_name":"${log_group_prefix}/error","log_stream_name":"{instance_id}"}]}}}}
CW
/opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl -a fetch-config -m ec2 -s -c file:/opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json || true
