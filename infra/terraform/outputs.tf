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

output "buckets" {
  value = { for k, b in local.all_buckets : k => b.bucket }
}

output "sns_alerts_topic_arn" {
  value = aws_sns_topic.alerts.arn
}

output "route53_name_servers" {
  description = "가비아 네임서버에 등록할 NS 4개"
  value       = aws_route53_zone.main.name_servers
}
