# ---------- SG 체인: alb-public → web → alb-internal → was → rds. 22번 없음(SSM) ----------
# alb-public 인바운드는 루트 security.tf 가 넣음 (CloudFront 프리픽스 443). 80 은 public_http_listener=true 일 때만
resource "aws_security_group" "alb_public" {
  name        = "${local.p}-sg-alb-public"
  description = "Public ALB: 443 from CloudFront prefix list (root adds), optional 80"
  vpc_id      = aws_vpc.main.id
  tags        = merge(var.tier_tag.edge, { Name = "${local.p}-sg-alb-public" })
}

resource "aws_vpc_security_group_ingress_rule" "alb_public_80" {
  count             = var.public_http_listener ? 1 : 0
  security_group_id = aws_security_group.alb_public.id
  cidr_ipv4         = "0.0.0.0/0"
  from_port         = 80
  to_port           = 80
  ip_protocol       = "tcp"
  description       = "HTTP for direct ALB test (remove after CloudFront cutover)"
}

resource "aws_vpc_security_group_egress_rule" "alb_public_all" {
  security_group_id = aws_security_group.alb_public.id
  ip_protocol       = "-1"
  cidr_ipv4         = "0.0.0.0/0"
}

resource "aws_security_group" "web" {
  name        = "${local.p}-sg-web"
  description = "WEB (Apache): 80 from Public ALB"
  vpc_id      = aws_vpc.main.id
  tags        = merge(var.tier_tag.web, { Name = "${local.p}-sg-web" })
}

resource "aws_vpc_security_group_ingress_rule" "web_80" {
  security_group_id            = aws_security_group.web.id
  referenced_security_group_id = aws_security_group.alb_public.id
  from_port                    = 80
  to_port                      = 80
  ip_protocol                  = "tcp"
}

resource "aws_vpc_security_group_egress_rule" "web_all" {
  security_group_id = aws_security_group.web.id
  ip_protocol       = "-1"
  cidr_ipv4         = "0.0.0.0/0"
}

resource "aws_security_group" "alb_internal" {
  name        = "${local.p}-sg-alb-internal"
  description = "Internal ALB: 8080 from WEB"
  vpc_id      = aws_vpc.main.id
  tags        = merge(var.tier_tag.was, { Name = "${local.p}-sg-alb-internal" })
}

resource "aws_vpc_security_group_ingress_rule" "alb_internal_8080" {
  security_group_id            = aws_security_group.alb_internal.id
  referenced_security_group_id = aws_security_group.web.id
  from_port                    = 8080
  to_port                      = 8080
  ip_protocol                  = "tcp"
}

resource "aws_vpc_security_group_egress_rule" "alb_internal_all" {
  security_group_id = aws_security_group.alb_internal.id
  ip_protocol       = "-1"
  cidr_ipv4         = "0.0.0.0/0"
}

resource "aws_security_group" "was" {
  name        = "${local.p}-sg-was"
  description = "WAS (Tomcat): 8080 from Internal ALB"
  vpc_id      = aws_vpc.main.id
  tags        = merge(var.tier_tag.was, { Name = "${local.p}-sg-was" })
}

resource "aws_vpc_security_group_ingress_rule" "was_8080" {
  security_group_id            = aws_security_group.was.id
  referenced_security_group_id = aws_security_group.alb_internal.id
  from_port                    = 8080
  to_port                      = 8080
  ip_protocol                  = "tcp"
}

resource "aws_vpc_security_group_egress_rule" "was_all" {
  security_group_id = aws_security_group.was.id
  ip_protocol       = "-1"
  cidr_ipv4         = "0.0.0.0/0"
}

# RDS SG: 인바운드는 루트가 붙임 (Proxy 3306). WAS 직접 3306 은 넣지 않음 — 설계는 Proxy 경유만
resource "aws_security_group" "rds" {
  name        = "${local.p}-sg-rds"
  description = "RDS: 3306 from RDS Proxy (root adds rule)"
  vpc_id      = aws_vpc.main.id
  tags        = merge(var.tier_tag.db, { Name = "${local.p}-sg-rds" })
}
