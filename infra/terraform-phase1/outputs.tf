output "public_alb_dns" {
  value       = aws_lb.public.dns_name
  description = "사용자 진입: http://<이 값>/ (Apache 가 302 로 /petclinic/ = WAS 홈으로 보냄)"
}

output "internal_alb_dns" {
  value = aws_lb.internal.dns_name
}

output "web_instance_ids" {
  value = aws_instance.web[*].id
}

output "was_instance_ids" {
  value = aws_instance.was[*].id
}

output "rds_endpoint" {
  value = aws_db_instance.main.address
}

output "rds_master_secret_arn" {
  value = aws_db_instance.main.master_user_secret[0].secret_arn
}

output "db_check_hint" {
  value       = "SSM 으로 WAS 접속 후: grep -A4 'vets' /var/log/mc-userdata.log  (앱이 RDS 에 만든 테이블 건수)"
  description = "WAS→RDS 연결·스키마 적용 확인 방법"
}

output "ssm_session_hint" {
  value = "aws ssm start-session --target ${aws_instance.was[0].id} --region ${var.region}"
}
