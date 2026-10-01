locals {
  p         = var.name_prefix
  az_suffix = ["a", "c"]

  common_tags = {
    Project   = var.project
    Team      = var.team
    Owner     = var.owner
    Env       = var.env
    Phase     = "1-blue"
    ManagedBy = "terraform"
  }

  tier = {
    web = { Tier = "web" }
    was = { Tier = "was" }
    db  = { Tier = "db" }
    ops = { Tier = "ops" }
  }

  app_context = "/petclinic"
}

data "aws_caller_identity" "current" {}

# 콘솔 구축본과 동일: Amazon Linux 2023 최신 (OS는 AL2023 유지, 앱 스택만 구버전)
data "aws_ssm_parameter" "al2023" {
  name = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"
}
