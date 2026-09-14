output "cloudfront_domain" {
  value = aws_cloudfront_distribution.main.domain_name
}

output "app_url" {
  value = "https://${var.domain_name}${local.app_context}/"
}

output "public_alb_dns" {
  value = aws_lb.public.dns_name
}

output "internal_alb_dns" {
  value = aws_lb.internal.dns_name
}

output "rds_proxy_endpoint" {
  value = aws_db_proxy.main.endpoint
}

output "rds_master_secret_arn" {
  value = aws_db_instance.main.master_user_secret[0].secret_arn
}

output "cognito_user_pool_id" {
  value = aws_cognito_user_pool.main.id
}

output "cognito_hosted_ui" {
  value = "https://${aws_cognito_user_pool_domain.main.domain}.auth.${var.region}.amazoncognito.com"
}

output "buckets" {
  value = { for k, b in local.all_buckets : k => b.bucket }
}

output "sns_alerts_topic_arn" {
  value = aws_sns_topic.alerts.arn
}

output "notify_lambda" {
  value = aws_lambda_function.notify.function_name
}

output "route53_name_servers" {
  description = "가비아 네임서버에 등록할 NS 4개"
  value       = aws_route53_zone.main.name_servers
}
