# ---------- ② Public ALB 에 443 리스너 (kdt5: 기존 test-Public-ALB 에 추가 · create_base: 모듈 ALB 에) ----------
# 기존 80 리스너(HTTP → Targetgroup-web)는 손대지 않음. CloudFront 전환 뒤 콘솔에서 삭제 (README 후속)
resource "aws_lb_listener" "public_https" {
  load_balancer_arn = local.public_alb_arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = aws_acm_certificate_validation.alb.certificate_arn

  # 기본 403: 검증 헤더 없이 ALB DNS 로 직접 오는 요청 차단
  default_action {
    type = "fixed-response"
    fixed_response {
      content_type = "text/plain"
      message_body = "Forbidden"
      status_code  = "403"
    }
  }

  tags = merge(local.tier_tag.web, { Name = "${local.p}-public-443" })
}

# X-Origin-Verify 헤더가 CloudFront 가 붙인 값과 같을 때만 기존 Targetgroup-web(WEB ASG) 으로 전달
resource "aws_lb_listener_rule" "origin_verify" {
  listener_arn = aws_lb_listener.public_https.arn
  priority     = 10

  action {
    type             = "forward"
    target_group_arn = local.tg_web_arn
  }

  condition {
    http_header {
      http_header_name = "X-Origin-Verify"
      values           = [var.origin_verify_secret]
    }
  }

  tags = local.tier_tag.web
}
