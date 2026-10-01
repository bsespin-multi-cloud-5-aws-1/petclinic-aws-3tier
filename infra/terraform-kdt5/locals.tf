locals {
  p = var.name_prefix

  common_tags = {
    Project   = var.project
    Team      = var.team
    Owner     = var.owner
    Env       = var.env
    ManagedBy = "terraform-kdt5"
  }

  tier_tag = {
    edge = { Tier = "edge" }
    web  = { Tier = "web" }
    was  = { Tier = "was" }
    db   = { Tier = "db" }
    ops  = { Tier = "ops" }
  }

  app_context = "/petclinic"

  # "8.0.44" → "8.0" → family mysql8.0 · 옵션 그룹 default:mysql-8-0
  db_major_minor = join(".", slice(split(".", var.db.engine_version), 0, 2))
  db_family      = "mysql${local.db_major_minor}"
  db_identifier  = var.create_base ? "${local.p}-petclinic" : var.existing.db_identifier

  was_tomcat_home = var.was_tomcat_home != "" ? var.was_tomcat_home : (var.create_base ? "/opt/tomcat" : "/home/ec2-user/tomcat")

  # ---- 기반 계층 참조: create_base 면 모듈 출력, 아니면 콘솔 구축본 data (선택된 쪽만 평가됨) ----
  vpc_id               = var.create_base ? module.base[0].vpc_id : data.aws_vpc.main[0].id
  db_subnet_ids        = var.create_base ? module.base[0].db_subnet_ids : [for n in var.existing.subnet_names.db : data.aws_subnet.db[n].id]
  db_subnet_group_name = var.create_base ? module.base[0].db_subnet_group_name : var.existing.db_subnet_group_name

  public_alb_arn          = var.create_base ? module.base[0].public_alb_arn : data.aws_lb.public[0].arn
  public_alb_dns          = var.create_base ? module.base[0].public_alb_dns : data.aws_lb.public[0].dns_name
  public_alb_arn_suffix   = var.create_base ? module.base[0].public_alb_arn_suffix : data.aws_lb.public[0].arn_suffix
  internal_alb_arn_suffix = var.create_base ? module.base[0].internal_alb_arn_suffix : data.aws_lb.internal[0].arn_suffix
  tg_web_arn              = var.create_base ? module.base[0].tg_web_arn : data.aws_lb_target_group.web[0].arn
  tg_was_arn_suffix       = var.create_base ? module.base[0].tg_was_arn_suffix : data.aws_lb_target_group.was[0].arn_suffix

  sg_alb_public_id = var.create_base ? module.base[0].sg_alb_public_id : data.aws_security_group.alb_public[0].id
  sg_was_id        = var.create_base ? module.base[0].sg_was_id : data.aws_security_group.was[0].id
  sg_db_id         = var.create_base ? module.base[0].sg_db_id : data.aws_security_group.db[0].id
  ec2_role_id      = var.create_base ? module.base[0].ec2_role_id : data.aws_iam_role.ec2[0].id
}
