# CloudFront 오리진 대면 IP 목록 (Public ALB 인바운드 제한용)
data "aws_ec2_managed_prefix_list" "cloudfront" {
  name = "com.amazonaws.global.cloudfront.origin-facing"
}

# ---------- SG 체인: alb-public → web → alb-internal → was → rds-proxy → rds ----------
resource "aws_security_group" "alb_public" {
  name        = "mc-sg-alb-public"
  description = "Public ALB: CloudFront origin-facing only (443)"
  vpc_id      = aws_vpc.main.id
  tags        = merge(local.tier_tag.edge, { Name = "sg-alb-public" })
}

resource "aws_vpc_security_group_ingress_rule" "alb_public_443" {
  security_group_id = aws_security_group.alb_public.id
  prefix_list_id    = data.aws_ec2_managed_prefix_list.cloudfront.id
  from_port         = 443
  to_port           = 443
  ip_protocol       = "tcp"
  description       = "HTTPS from CloudFront"
}

resource "aws_vpc_security_group_ingress_rule" "alb_public_80" {
  security_group_id = aws_security_group.alb_public.id
  prefix_list_id    = data.aws_ec2_managed_prefix_list.cloudfront.id
  from_port         = 80
  to_port           = 80
  ip_protocol       = "tcp"
  description       = "HTTP (redirect to HTTPS)"
}

resource "aws_vpc_security_group_egress_rule" "alb_public_all" {
  security_group_id = aws_security_group.alb_public.id
  ip_protocol       = "-1"
  cidr_ipv4         = "0.0.0.0/0"
}

resource "aws_security_group" "web" {
  name        = "mc-sg-web"
  description = "WEB (Apache): 80 from Public ALB"
  vpc_id      = aws_vpc.main.id
  tags        = merge(local.tier_tag.web, { Name = "sg-web" })
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
  name        = "mc-sg-alb-internal"
  description = "Internal ALB: 8080 from WEB"
  vpc_id      = aws_vpc.main.id
  tags        = merge(local.tier_tag.was, { Name = "sg-alb-internal" })
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
  name        = "mc-sg-was"
  description = "WAS (Tomcat): 8080 from Internal ALB"
  vpc_id      = aws_vpc.main.id
  tags        = merge(local.tier_tag.was, { Name = "sg-was" })
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

resource "aws_security_group" "rds_proxy" {
  name        = "mc-sg-rds-proxy"
  description = "RDS Proxy: 3306 from WAS"
  vpc_id      = aws_vpc.main.id
  tags        = merge(local.tier_tag.db, { Name = "sg-rds-proxy" })
}

resource "aws_vpc_security_group_ingress_rule" "rds_proxy_3306" {
  security_group_id            = aws_security_group.rds_proxy.id
  referenced_security_group_id = aws_security_group.was.id
  from_port                    = 3306
  to_port                      = 3306
  ip_protocol                  = "tcp"
}

resource "aws_vpc_security_group_egress_rule" "rds_proxy_all" {
  security_group_id = aws_security_group.rds_proxy.id
  ip_protocol       = "-1"
  cidr_ipv4         = "0.0.0.0/0"
}

resource "aws_security_group" "rds" {
  name        = "mc-sg-rds"
  description = "RDS: 3306 from RDS Proxy (and WAS for Blue phase)"
  vpc_id      = aws_vpc.main.id
  tags        = merge(local.tier_tag.db, { Name = "sg-rds" })
}

resource "aws_vpc_security_group_ingress_rule" "rds_from_proxy" {
  security_group_id            = aws_security_group.rds.id
  referenced_security_group_id = aws_security_group.rds_proxy.id
  from_port                    = 3306
  to_port                      = 3306
  ip_protocol                  = "tcp"
}

resource "aws_vpc_security_group_ingress_rule" "rds_from_was" {
  security_group_id            = aws_security_group.rds.id
  referenced_security_group_id = aws_security_group.was.id
  from_port                    = 3306
  to_port                      = 3306
  ip_protocol                  = "tcp"
  description                  = "Direct access before RDS Proxy (Phase 1-2)"
}
