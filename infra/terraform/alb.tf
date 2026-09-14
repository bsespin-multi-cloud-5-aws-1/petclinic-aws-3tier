# ---------- Public ALB (443 · ACM 서울 · CloudFront 오리진) ----------
resource "aws_lb" "public" {
  name               = "${local.p}-alb-public"
  load_balancer_type = "application"
  internal           = false
  security_groups    = [aws_security_group.alb_public.id]
  subnets            = aws_subnet.public[*].id
  idle_timeout       = 60

  access_logs {
    bucket  = aws_s3_bucket.logs.bucket
    prefix  = "alb/public"
    enabled = true
  }

  tags       = merge(local.tier_tag.web, { Name = "${local.p}-alb-public" })
  depends_on = [aws_s3_bucket_policy.logs]
}

# tg-web: 얕은 헬스체크 (/health.html = Apache 생존만)
resource "aws_lb_target_group" "web" {
  name                 = "${local.p}-tg-web"
  port                 = 80
  protocol             = "HTTP"
  vpc_id               = aws_vpc.main.id
  deregistration_delay = 30

  health_check {
    path                = "/health.html"
    interval            = 10
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
    matcher             = "200"
  }

  tags = merge(local.tier_tag.web, { Name = "${local.p}-tg-web" })
}

# 443만 (HTTP→HTTPS 리다이렉트는 CloudFront viewer policy가 처리). 기본 403, X-Origin-Verify 헤더가 맞을 때만 전달
resource "aws_lb_listener" "public_https" {
  load_balancer_arn = aws_lb.public.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = aws_acm_certificate_validation.alb.certificate_arn

  default_action {
    type = "fixed-response"
    fixed_response {
      content_type = "text/plain"
      message_body = "Forbidden"
      status_code  = "403"
    }
  }
}

# 리스너 규칙: X-Origin-Verify 헤더가 맞을 때만 전달 (CloudFront 우회 차단). 로그인/인증 없음 — Cognito 제외(9/14 결정)
resource "aws_lb_listener_rule" "origin_verify" {
  listener_arn = aws_lb_listener.public_https.arn
  priority     = 10

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.web.arn
  }

  condition {
    http_header {
      http_header_name = "X-Origin-Verify"
      values           = [var.origin_verify_secret]
    }
  }
}

# ---------- Internal ALB (8080 · WEB → WAS · sticky) ----------
resource "aws_lb" "internal" {
  name               = "${local.p}-alb-internal"
  load_balancer_type = "application"
  internal           = true
  security_groups    = [aws_security_group.alb_internal.id]
  subnets            = aws_subnet.was[*].id

  access_logs {
    bucket  = aws_s3_bucket.logs.bucket
    prefix  = "alb/internal"
    enabled = true
  }

  tags       = merge(local.tier_tag.was, { Name = "${local.p}-alb-internal" })
  depends_on = [aws_s3_bucket_policy.logs]
}

# tg-was: 깊은 헬스체크 (/petclinic/ · 슬래시 필수 · permitAll). 로그인 세션용 stickiness
resource "aws_lb_target_group" "was" {
  name                 = "${local.p}-tg-was"
  port                 = 8080
  protocol             = "HTTP"
  vpc_id               = aws_vpc.main.id
  deregistration_delay = 30

  health_check {
    path                = "${local.app_context}/"
    interval            = 10
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
    matcher             = "200"
  }

  stickiness {
    type            = "lb_cookie"
    cookie_duration = 86400
    enabled         = true
  }

  tags = merge(local.tier_tag.was, { Name = "${local.p}-tg-was" })
}

resource "aws_lb_listener" "internal_8080" {
  load_balancer_arn = aws_lb.internal.arn
  port              = 8080
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.was.arn
  }
}
