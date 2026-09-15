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

  # "8.0.44" → "mysql8.0" (파라미터 그룹 family 는 엔진 메이저.마이너와 일치해야 함)
  db_family = "mysql${join(".", slice(split(".", var.db.engine_version), 0, 2))}"

  public_subnet_ids = [for n in var.existing.subnet_names.public : data.aws_subnet.public[n].id]
  db_subnet_ids     = [for n in var.existing.subnet_names.db : data.aws_subnet.db[n].id]
}
