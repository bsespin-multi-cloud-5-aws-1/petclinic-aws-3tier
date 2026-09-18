# ---------- create_base=true (mc-deploy 같은 빈 계정): 기반 계층을 모듈로 생성 ----------
# kdt5 에서는 count=0 → 아무것도 만들지 않고 existing.tf 의 data 를 쓴다
module "base" {
  count  = var.create_base ? 1 : 0
  source = "./modules/base"

  name_prefix  = local.p
  region       = var.region
  azs          = var.base.azs
  vpc_cidr     = var.base.vpc_cidr
  subnet_cidrs = var.base.subnet_cidrs
  tier_tag     = local.tier_tag
  app_context  = local.app_context

  web_instance_type     = var.base.web_instance_type
  was_instance_type     = var.base.was_instance_type
  app_repo_url          = var.base.app_repo_url
  app_repo_branch       = var.base.app_repo_branch
  tomcat_version        = var.base.tomcat_version
  public_http_listener  = var.base.public_http_listener
  web_index_branch      = var.base.web_index_branch
  enable_asg            = var.base.enable_asg
  web_asg               = var.base.web_asg
  was_asg               = var.base.was_asg
  web_ami_id            = var.base.web_ami_id
  was_ami_id            = var.base.was_ami_id
  db_init_mode          = var.base.db_init_mode
  create_bastion        = var.base.create_bastion
  bastion_allowed_cidrs = var.base.bastion_allowed_cidrs
  bastion_instance_type = var.base.bastion_instance_type
  ssh_key_name          = var.base.ssh_key_name
  enable_ssm            = var.enable_ssm
  enable_vpc_endpoints  = var.base.enable_vpc_endpoints
  vpc_endpoint_services = var.base.vpc_endpoint_services
  ebs_kms_key_arn       = var.base.ebs_kms_key_arn == "mc-cmk" ? aws_kms_key.main.arn : var.base.ebs_kms_key_arn

  access_logs_bucket   = aws_s3_bucket_policy.logs.bucket # 정책 적용 후 ALB 생성
  db_secret_arn        = aws_db_instance.main.master_user_secret[0].secret_arn
  app_db_secret_arn    = aws_secretsmanager_secret.app_db.arn # 버전이 먼저 만들어지도록
  app_db_secret_ready  = aws_secretsmanager_secret_version.app_db.version_id
  db_name              = "petclinic"
  jdbc_host            = aws_db_proxy.main.endpoint # WAS 는 Proxy 가 생긴 뒤 부팅 → TLS 로 접속
  cwagent_param_prefix = "/mc/cwagent"
}
