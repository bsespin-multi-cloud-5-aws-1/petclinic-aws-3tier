output "app_url" {
  value       = "https://${var.domain_name}${local.app_context}/"
  description = "사용자 진입 (Route 53 → CloudFront → 기존 Public ALB 443)"
}

output "cloudfront_domain" {
  value = aws_cloudfront_distribution.main.domain_name
}

output "route53_name_servers" {
  value       = aws_route53_zone.main.name_servers
  description = "가비아 네임서버에 등록할 NS 4개"
}

output "rds_proxy_endpoint" {
  value = aws_db_proxy.main.endpoint
}

output "was_jdbc_url" {
  value       = "jdbc:mysql://${aws_db_proxy.main.endpoint}:3306/petclinic?useUnicode=true&characterEncoding=UTF-8&serverTimezone=Asia/Seoul&sslMode=REQUIRED"
  description = "WAS 재빌드 시 -Djdbc.url 값 (Proxy 경유 · TLS 필수). WAS 자체는 이 코드가 건드리지 않음"
}

output "rds_master_secret_arn" {
  value = aws_db_instance.main.master_user_secret[0].secret_arn
}

output "sns_alerts_topic_arn" {
  value = aws_sns_topic.alerts.arn
}

output "buckets" {
  value = local.buckets
}

output "public_alb_dns" {
  value = local.public_alb_dns
}

output "mode" {
  value = var.create_base ? "create_base (기반 계층 모듈 생성 · 예: mc-deploy)" : "kdt5 (구축본 참조 · database-1 import)"
}

output "manual_followups" {
  description = "kdt5 모드: 코드가 건드리지 않는 기존 리소스(WEB·WAS·ALB)에서 콘솔로 해야 할 후속. create_base 모드는 ⓜ1 만 해당(나머지는 코드가 처리)"
  value = var.create_base ? ["1. 가비아 네임서버 → route53_name_servers 4개로 교체 (apply 중 ACM 검증이 이걸 기다림)"] : [
    "1. 가비아 네임서버 → route53_name_servers 4개로 교체 (ACM DNS 검증·A 레코드가 그 뒤에 유효)",
    "2. 기존 ALB 두 개: 속성 → 액세스 로그 켜기 → s3://${local.buckets.logs}/alb/public, /alb/internal",
    "3. WEB ASG 시작 템플릿(web) · WAS-test-a: IAM 인스턴스 프로파일 mc-ec2-role 부착 → SSM 접속·CW Agent 동작",
    "4. WEB·WAS 에 CloudWatch Agent 설치 후 `amazon-cloudwatch-agent-ctl -a fetch-config -m ec2 -c ssm:/mc/cwagent/web|was -s`",
    "5. WAS: was_jdbc_url 로 WAR 재빌드(mvnw -P MySQL -Djdbc.url=...) → RDS Proxy 경유. Proxy 전환 확인 후 petclinic-db-sg 의 3306 ← was-instance-sg 제거",
    "6. CloudFront 로 전환 확인 후: Public ALB 80 리스너 삭제, alb-public-sg 의 80/443 0.0.0.0/0 규칙 삭제 (CloudFront 프리픽스 443 만 남김)",
    "7. database-1 파라미터 그룹 교체는 유지관리 창에 재부팅됨(apply_immediately=false). 점검 시간에 바로 적용하려면 콘솔 재부팅",
  ]
}
