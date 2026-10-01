# ---------- Public ALB (443 리스너 · 규칙은 루트 alb.tf) ----------
resource "aws_lb" "public" {
  name               = "${local.p}-alb-public"
  load_balancer_type = "application"
  internal           = false
  security_groups    = [aws_security_group.alb_public.id]
  subnets            = aws_subnet.public[*].id
  idle_timeout       = 60

  access_logs {
    bucket  = var.access_logs_bucket
    prefix  = "alb/public"
    enabled = true
  }

  tags = merge(var.tier_tag.web, { Name = "${local.p}-alb-public" })
}

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

  tags = merge(var.tier_tag.web, { Name = "${local.p}-tg-web" })
}

# 선택: 80 리스너 (NS 위임 전 ALB DNS 로 직접 확인용). 설계 경로는 CloudFront → 443
resource "aws_lb_listener" "public_http" {
  count             = var.public_http_listener ? 1 : 0
  load_balancer_arn = aws_lb.public.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.web.arn
  }
}

resource "aws_lb_target_group_attachment" "web" {
  count            = local.ec2_count
  target_group_arn = aws_lb_target_group.web.arn
  target_id        = aws_instance.web[count.index].id
  port             = 80
}

# ---------- Internal ALB (8080 · WEB → WAS) ----------
resource "aws_lb" "internal" {
  name               = "${local.p}-alb-internal"
  load_balancer_type = "application"
  internal           = true
  security_groups    = [aws_security_group.alb_internal.id]
  subnets            = aws_subnet.was[*].id
  idle_timeout       = 60

  access_logs {
    bucket  = var.access_logs_bucket
    prefix  = "alb/internal"
    enabled = true
  }

  tags = merge(var.tier_tag.was, { Name = "${local.p}-alb-internal" })
}

resource "aws_lb_target_group" "was" {
  name                 = "${local.p}-tg-was"
  port                 = 8080
  protocol             = "HTTP"
  vpc_id               = aws_vpc.main.id
  deregistration_delay = 30

  health_check {
    path                = "${var.app_context}/"
    interval            = 10
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
    matcher             = "200"
  }

  tags = merge(var.tier_tag.was, { Name = "${local.p}-tg-was" })
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

resource "aws_lb_target_group_attachment" "was" {
  count            = local.ec2_count
  target_group_arn = aws_lb_target_group.was.arn
  target_id        = aws_instance.was[count.index].id
  port             = 8080
}
