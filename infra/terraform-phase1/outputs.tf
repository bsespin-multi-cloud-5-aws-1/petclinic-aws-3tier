output "public_alb_dns" {
  value       = aws_lb.public.dns_name
  description = "사용자 진입: http://<이 값>/petclinic/"
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

output "ssm_session_hint" {
  value = "aws ssm start-session --target ${aws_instance.was[0].id} --region ${var.region}"
}
