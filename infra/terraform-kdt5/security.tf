# ---------- SG 체인에 규칙 추가 (kdt5: 기존 SG 에 · create_base: 모듈이 만든 SG 에) ----------
# alb-public-sg: CloudFront 오리진 대면 IP 목록에서 443. 기존 80/443 0.0.0.0/0 규칙은 CloudFront 전환 뒤 콘솔에서 제거 (README 후속)
resource "aws_vpc_security_group_ingress_rule" "alb_public_443_cloudfront" {
  security_group_id = local.sg_alb_public_id
  prefix_list_id    = data.aws_ec2_managed_prefix_list.cloudfront.id
  from_port         = 443
  to_port           = 443
  ip_protocol       = "tcp"
  description       = "HTTPS from CloudFront origin-facing prefix list"
  tags              = merge(local.tier_tag.edge, { Name = "alb-public-443-cloudfront" })
}

# ---------- ④ RDS Proxy SG (신규): 3306 ← 기존 was-instance-sg ----------
resource "aws_security_group" "rds_proxy" {
  name        = "${local.p}-sg-rds-proxy"
  description = "RDS Proxy: 3306 from WAS"
  vpc_id      = local.vpc_id
  tags        = merge(local.tier_tag.db, { Name = "${local.p}-sg-rds-proxy" })
}

resource "aws_vpc_security_group_ingress_rule" "rds_proxy_3306" {
  security_group_id            = aws_security_group.rds_proxy.id
  referenced_security_group_id = local.sg_was_id
  from_port                    = 3306
  to_port                      = 3306
  ip_protocol                  = "tcp"
  description                  = "MySQL from WAS (was-instance-sg)"
}

resource "aws_vpc_security_group_egress_rule" "rds_proxy_all" {
  security_group_id = aws_security_group.rds_proxy.id
  ip_protocol       = "-1"
  cidr_ipv4         = "0.0.0.0/0"
}

# 기존 petclinic-db-sg 에 Proxy → RDS 3306 추가 (기존 3306 ← was-instance-sg 는 Blue 직접 접속용으로 유지)
resource "aws_vpc_security_group_ingress_rule" "rds_from_proxy" {
  security_group_id            = local.sg_db_id
  referenced_security_group_id = aws_security_group.rds_proxy.id
  from_port                    = 3306
  to_port                      = 3306
  ip_protocol                  = "tcp"
  description                  = "MySQL from RDS Proxy"
  tags                         = merge(local.tier_tag.db, { Name = "rds-3306-from-proxy" })
}
