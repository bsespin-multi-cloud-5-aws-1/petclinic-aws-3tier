locals {
  p = var.name_prefix # "mc"

  az_suffix = ["a", "c"]

  common_tags = {
    Project   = var.project
    Team      = var.team
    Owner     = var.owner
    Env       = var.env
    ManagedBy = "terraform"
  }

  tier_tag = {
    edge = { Tier = "edge" }
    web  = { Tier = "web" }
    was  = { Tier = "was" }
    db   = { Tier = "db" }
    ops  = { Tier = "ops" }
  }

  app_context  = "/petclinic"
  booking_path = "/petclinic/owners/*/pets/*/visits/new"
}
