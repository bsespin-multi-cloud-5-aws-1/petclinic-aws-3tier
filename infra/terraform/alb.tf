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

# 리스너 규칙 (우선순위 순): 부하기 IP 우회 → 공개 경로 → 앱(Cognito 인증) → 기타
# 부하 테스트 중에만: JMeter 공인 IP는 인증 없이 통과 (loadgen_cidrs 비우면 생성 안 함)
resource "aws_lb_listener_rule" "loadgen_bypass" {
  count        = length(var.loadgen_cidrs) > 0 ? 1 : 0
  listener_arn = aws_lb_listener.public_https.arn
  priority     = 1

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.web.arn
  }

  condition {
    source_ip {
      values = var.loadgen_cidrs
    }
  }
  condition {
    http_header {
      http_header_name = "X-Origin-Verify"
      values           = [var.origin_verify_secret]
    }
  }
}

# 공개 경로: 헬스체크·랜딩 (인증 없음)
resource "aws_lb_listener_rule" "public_paths" {
  listener_arn = aws_lb_listener.public_https.arn
  priority     = 5

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.web.arn
  }

  condition {
    path_pattern {
      values = ["/health.html", "/", "/index.html"]
    }
  }
  condition {
    http_header {
      http_header_name = "X-Origin-Verify"
      values           = [var.origin_verify_secret]
    }
  }
}

# 앱 경로: ALB가 Cognito Hosted UI로 인증 후 전달 (앱 수정 없음). 콜백 /oauth2/idpresponse 는 ALB가 처리
resource "aws_lb_listener_rule" "app_authenticated" {
  listener_arn = aws_lb_listener.public_https.arn
  priority     = 10

  action {
    type = "authenticate-cognito"
    authenticate_cognito {
      user_pool_arn              = aws_cognito_user_pool.main.arn
      user_pool_client_id        = aws_cognito_user_pool_client.petclinic.id
      user_pool_domain           = aws_cognito_user_pool_domain.main.domain
      scope                      = "openid email profile"
      session_cookie_name        = "AWSELBAuthSessionCookie"
      session_timeout            = 28800 # 8h
      on_unauthenticated_request = "authenticate"
    }
  }

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.web.arn
  }

  condition {
    path_pattern {
      values = ["${local.app_context}/*"]
    }
  }
  condition {
    http_header {
      http_header_name = "X-Origin-Verify"
      values           = [var.origin_verify_secret]
    }
  }
}

# 나머지 (정적 등): 검증 헤더만 확인
resource "aws_lb_listener_rule" "origin_verify" {
  listener_arn = aws_lb_listener.public_https.arn
  priority     = 20

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
