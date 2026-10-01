# SG 체인: 소스는 IP가 아니라 앞 단계 SG. 22번은 어디에도 없음 (SSM). 이름은 sg- 로 시작 불가 → mc-sg-*
resource "aws_security_group" "alb_public" {
  name        = "${local.p}-sg-alb-public"
  description = "Public ALB: 80 from allowed CIDRs"
  vpc_id      = aws_vpc.main.id
  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = var.public_alb_ingress_cidrs
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  tags = { Name = "${local.p}-sg-alb-public" }
}

resource "aws_security_group" "web" {
  name        = "${local.p}-sg-web"
  description = "WEB(Apache): 80 from Public ALB only"
  vpc_id      = aws_vpc.main.id
  ingress {
    from_port       = 80
    to_port         = 80
    protocol        = "tcp"
    security_groups = [aws_security_group.alb_public.id]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  tags = merge(local.tier.web, { Name = "${local.p}-sg-web" })
}

resource "aws_security_group" "alb_internal" {
  name        = "${local.p}-sg-alb-internal"
  description = "Internal ALB: 8080 from WEB only"
  vpc_id      = aws_vpc.main.id
  ingress {
    from_port       = 8080
    to_port         = 8080
    protocol        = "tcp"
    security_groups = [aws_security_group.web.id]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  tags = { Name = "${local.p}-sg-alb-internal" }
}

resource "aws_security_group" "was" {
  name        = "${local.p}-sg-was"
  description = "WAS(Tomcat): 8080 from Internal ALB only"
  vpc_id      = aws_vpc.main.id
  ingress {
    from_port       = 8080
    to_port         = 8080
    protocol        = "tcp"
    security_groups = [aws_security_group.alb_internal.id]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  tags = merge(local.tier.was, { Name = "${local.p}-sg-was" })
}

resource "aws_security_group" "rds" {
  name        = "${local.p}-sg-rds"
  description = "RDS: 3306 from WAS only"
  vpc_id      = aws_vpc.main.id
  ingress {
    from_port       = 3306
    to_port         = 3306
    protocol        = "tcp"
    security_groups = [aws_security_group.was.id]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  tags = merge(local.tier.db, { Name = "${local.p}-sg-rds" })
}

# Bastion (선택) — 설계는 SSM. create_bastion=true 일 때만 22번이 생김
resource "aws_security_group" "bastion" {
  count       = var.create_bastion ? 1 : 0
  name        = "${local.p}-sg-bastion"
  description = "Bastion: 22 from team CIDRs"
  vpc_id      = aws_vpc.main.id
  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = var.bastion_ssh_cidrs
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  tags = { Name = "${local.p}-sg-bastion" }
}

resource "aws_security_group_rule" "web_ssh_from_bastion" {
  count                    = var.create_bastion ? 1 : 0
  type                     = "ingress"
  security_group_id        = aws_security_group.web.id
  from_port                = 22
  to_port                  = 22
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.bastion[0].id
}

resource "aws_security_group_rule" "was_ssh_from_bastion" {
  count                    = var.create_bastion ? 1 : 0
  type                     = "ingress"
  security_group_id        = aws_security_group.was.id
  from_port                = 22
  to_port                  = 22
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.bastion[0].id
}
