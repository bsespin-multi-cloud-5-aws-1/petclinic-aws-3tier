# ---------- Public ALB (사용자 → WEB) ----------
resource "aws_lb" "public" {
  name               = "${local.p}-alb-public"
  load_balancer_type = "application"
  internal           = false
  subnets            = aws_subnet.public[*].id
  security_groups    = [aws_security_group.alb_public.id]
  tags               = { Name = "${local.p}-alb-public" }
}

# WEB 헬스체크는 얕게(/health.html): WAS 장애가 WEB까지 unhealthy로 번지지 않게
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
  tags = merge(local.tier.web, { Name = "${local.p}-tg-web" })
}

resource "aws_lb_listener" "public_http" {
  load_balancer_arn = aws_lb.public.arn
  port              = 80
  protocol          = "HTTP"
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.web.arn
  }
}

resource "aws_lb_target_group_attachment" "web" {
  count            = 2
  target_group_arn = aws_lb_target_group.web.arn
  target_id        = aws_instance.web[count.index].id
  port             = 80
}

# ---------- Internal ALB (WEB → WAS) — OT "Internal LB 필수" ----------
resource "aws_lb" "internal" {
  name               = "${local.p}-alb-internal"
  load_balancer_type = "application"
  internal           = true
  subnets            = aws_subnet.was[*].id
  security_groups    = [aws_security_group.alb_internal.id]
  tags               = { Name = "${local.p}-alb-internal" }
}

# WAS 헬스체크는 깊게(/petclinic/ — 슬래시 필수, /petclinic 은 302). 앱 컨텍스트 로드까지 확인
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
  tags = merge(local.tier.was, { Name = "${local.p}-tg-was" })
}

resource "aws_lb_listener" "internal_http" {
  load_balancer_arn = aws_lb.internal.arn
  port              = 8080
  protocol          = "HTTP"
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.was.arn
  }
}

resource "aws_lb_target_group_attachment" "was" {
  count            = 2
  target_group_arn = aws_lb_target_group.was.arn
  target_id        = aws_instance.was[count.index].id
  port             = 8080
}
