# ---------- 콘솔 구축본 참조 (create_base=false · 읽기 전용). WEB ASG(web-test) · WAS-test-a · ALB · VPC 는 그대로 ----------
data "aws_caller_identity" "current" {}
data "aws_partition" "current" {}

data "aws_vpc" "main" {
  count = var.create_base ? 0 : 1
  filter {
    name   = "tag:Name"
    values = [var.existing.vpc_name]
  }
}

data "aws_subnet" "db" {
  for_each = var.create_base ? toset([]) : toset(var.existing.subnet_names.db)
  vpc_id   = data.aws_vpc.main[0].id
  filter {
    name   = "tag:Name"
    values = [each.value]
  }
}

# Public ALB(test-Public-ALB) · Internal ALB(alb-internal-test) 와 대상 그룹 — 443 리스너·알람이 참조
data "aws_lb" "public" {
  count = var.create_base ? 0 : 1
  name  = var.existing.public_alb_name
}

data "aws_lb" "internal" {
  count = var.create_base ? 0 : 1
  name  = var.existing.internal_alb_name
}

data "aws_lb_target_group" "web" {
  count = var.create_base ? 0 : 1
  name  = var.existing.tg_web_name
}

data "aws_lb_target_group" "was" {
  count = var.create_base ? 0 : 1
  name  = var.existing.tg_was_name
}

# SG: 기존 체인(alb-public-sg → web-instance-sg → alb-internal-sg → was-instance-sg → petclinic-db-sg)에 규칙만 추가
data "aws_security_group" "alb_public" {
  count  = var.create_base ? 0 : 1
  vpc_id = data.aws_vpc.main[0].id
  filter {
    name   = "group-name"
    values = [var.existing.sg_alb_public]
  }
}

data "aws_security_group" "was" {
  count  = var.create_base ? 0 : 1
  vpc_id = data.aws_vpc.main[0].id
  filter {
    name   = "group-name"
    values = [var.existing.sg_was]
  }
}

data "aws_security_group" "db" {
  count  = var.create_base ? 0 : 1
  vpc_id = data.aws_vpc.main[0].id
  filter {
    name   = "group-name"
    values = [var.existing.sg_db]
  }
}

# EC2 역할(mc-ec2-role · SSM Core + CW Agent 부착 완료). 인라인 정책만 추가
data "aws_iam_role" "ec2" {
  count = var.create_base ? 0 : 1
  name  = var.existing.ec2_role_name
}

# RDS 관리형 비밀은 AWS 관리형 키(aws/secretsmanager)로 암호화됨 → 복호화 허용 대상
data "aws_kms_alias" "secretsmanager" {
  name = "alias/aws/secretsmanager"
}

# CloudFront 오리진 대면 IP 목록 (Public ALB 443 인바운드 제한)
data "aws_ec2_managed_prefix_list" "cloudfront" {
  name = "com.amazonaws.global.cloudfront.origin-facing"
}
