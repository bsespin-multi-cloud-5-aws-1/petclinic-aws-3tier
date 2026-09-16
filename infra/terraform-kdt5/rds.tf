# ---------- ④ DB 계층: 기존 database-1 (import) · 파라미터 그룹 · RDS Proxy · AWS Backup ----------
# 기본 파라미터 그룹(default.mysql8.0)은 수정 불가 → 사본. require_secure_transport 는 도면 ④ "JDBC sslMode=REQUIRED + 서버 TLS 강제"
resource "aws_db_parameter_group" "main" {
  name   = "${local.p}-${replace(local.db_family, ".", "")}" # mc-mysql80 / mc-mysql84
  family = local.db_family

  parameter {
    name  = "require_secure_transport"
    value = "1"
  }
  parameter {
    name  = "character_set_server"
    value = "utf8mb4"
  }
  parameter {
    name  = "collation_server"
    value = "utf8mb4_unicode_ci"
  }

  tags = merge(local.tier_tag.db, { Name = "${local.p}-${replace(local.db_family, ".", "")}" })
}

# kdt5 모드: 콘솔로 만든 database-1 을 imports.tf 로 편입 (var.db 기본값 = 2026-09-15 콘솔 확인값 — 바꾸면 plan 에 차이).
# create_base 모드: 같은 리소스가 mc-petclinic 으로 새로 생성 (tfvars 로 8.4 · 20GB 등 지정)
resource "aws_db_instance" "main" {
  identifier     = local.db_identifier
  engine         = "mysql"
  engine_version = var.db.engine_version
  instance_class = var.db.instance_class

  db_name                     = "petclinic"
  username                    = "admin"
  manage_master_user_password = true # rds!db-… (Secrets Manager 관리형 · 7일 교체)

  allocated_storage     = var.db.allocated_storage
  max_allocated_storage = var.db.max_allocated_storage
  storage_type          = "gp3"
  storage_encrypted     = true # aws/rds 기본 키

  multi_az               = var.db.multi_az
  db_subnet_group_name   = local.db_subnet_group_name
  vpc_security_group_ids = [local.sg_db_id]
  publicly_accessible    = false
  port                   = 3306
  network_type           = "IPV4"
  ca_cert_identifier     = var.db.ca_cert_identifier
  option_group_name      = "default:mysql-${replace(local.db_major_minor, ".", "-")}"

  backup_window                   = var.db.backup_window
  maintenance_window              = var.db.maintenance_window
  auto_minor_version_upgrade      = false
  enabled_cloudwatch_logs_exports = ["error"]
  performance_insights_enabled    = false # db.t3.small(MySQL) 미지원
  monitoring_interval             = 0

  # ---- 도면 ④ 보강: kdt5 import 후 첫 plan 에 이 항목만 바뀌어야 정상 ----
  parameter_group_name      = aws_db_parameter_group.main.name # TLS 강제 · utf8mb4 (기존 DB 는 재부팅 필요)
  backup_retention_period   = var.db.backup_retention_days     # kdt5: 0 → 7 (PITR 5분 활성)
  deletion_protection       = var.db.deletion_protection
  copy_tags_to_snapshot     = true
  apply_immediately         = var.db.apply_immediately
  skip_final_snapshot       = var.db.skip_final_snapshot
  final_snapshot_identifier = var.db.skip_final_snapshot ? null : "${local.db_identifier}-final"

  tags = merge(local.tier_tag.db, { Name = local.db_identifier, Data = "pii" })
}

# ---------- 앱 전용 DB 사용자 비밀 (교체 없음) ----------
# 왜: RDS 관리형 admin 비밀(rds!db-…)은 7일마다 자동 교체되는데 WAS 는 빌드 시점 비밀번호를 WAR 에 갖고 있어
# 교체 뒤 Proxy 인증(SECRETS)이 실패한다. 앱은 교체되지 않는 별도 사용자(petclinic_app · petclinic.* 권한만)로 접속 → 최소 권한도 충족.
# 사용자 생성은 WAS 부팅 시 admin 비밀로 CREATE USER IF NOT EXISTS (멱등) — was.sh
resource "random_password" "app_db" {
  length           = 32
  special          = true
  override_special = "!#%^*()-_=+" # XML·셸·JDBC URL 에서 문제 없는 문자만
}

resource "aws_secretsmanager_secret" "app_db" {
  name                    = "${local.p}/petclinic/app-db"
  description             = "PetClinic 앱 전용 DB 사용자 (Proxy SECRETS 인증 · 교체 없음)"
  recovery_window_in_days = 0 # 프로젝트 정리용. 운영이면 7~30
  tags                    = merge(local.tier_tag.db, { Name = "${local.p}-app-db-secret" })
}

resource "aws_secretsmanager_secret_version" "app_db" {
  secret_id = aws_secretsmanager_secret.app_db.id
  secret_string = jsonencode({
    username = var.app_db_username
    password = random_password.app_db.result
  })
}

# ---------- RDS Proxy (커넥션 다중화 · failover 중 연결 유지 · Require TLS · 비밀 직접 조회 → 앱 무영향) ----------
resource "aws_db_proxy" "main" {
  name                   = "${local.p}-rds-proxy"
  engine_family          = "MYSQL"
  role_arn               = aws_iam_role.rds_proxy.arn
  vpc_subnet_ids         = local.db_subnet_ids
  vpc_security_group_ids = [aws_security_group.rds_proxy.id]
  require_tls            = true
  idle_client_timeout    = 1800
  debug_logging          = false

  # admin(관리형·7일 교체) — 부팅 시 사용자 생성·운영 작업용
  auth {
    auth_scheme = "SECRETS"
    iam_auth    = "DISABLED"
    secret_arn  = aws_db_instance.main.master_user_secret[0].secret_arn
  }
  # 앱 사용자(교체 없음) — WAS JDBC 가 쓰는 계정
  auth {
    auth_scheme = "SECRETS"
    iam_auth    = "DISABLED"
    secret_arn  = aws_secretsmanager_secret.app_db.arn
  }

  tags = merge(local.tier_tag.db, { Name = "${local.p}-rds-proxy" })
}

resource "aws_db_proxy_default_target_group" "main" {
  db_proxy_name = aws_db_proxy.main.name

  connection_pool_config {
    max_connections_percent      = 90
    max_idle_connections_percent = 50
    connection_borrow_timeout    = 120
  }
}

resource "aws_db_proxy_target" "main" {
  db_proxy_name          = aws_db_proxy.main.name
  target_group_name      = aws_db_proxy_default_target_group.main.name
  db_instance_identifier = aws_db_instance.main.identifier
}

# ---------- AWS Backup 일일 계획 (RDS 자동 백업 7일 = PITR, Backup = 별도 볼트에 복구 지점 · 실수 삭제 대비) ----------
resource "aws_backup_vault" "main" {
  name          = "${local.p}-backup-vault"
  force_destroy = true # 프로젝트 정리용
  kms_key_arn   = aws_kms_key.main.arn
  tags          = merge(local.tier_tag.db, { Name = "${local.p}-backup-vault" })
}

resource "aws_backup_plan" "rds" {
  name = "${local.p}-rds-daily"

  rule {
    rule_name         = "daily-7d"
    target_vault_name = aws_backup_vault.main.name
    schedule          = "cron(0 19 * * ? *)" # 04:00 KST
    lifecycle {
      delete_after = 7
    }
  }

  tags = merge(local.tier_tag.db, { Name = "${local.p}-rds-daily" })
}

data "aws_iam_policy_document" "backup_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["backup.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "backup" {
  name               = "${local.p}-backup-role"
  assume_role_policy = data.aws_iam_policy_document.backup_assume.json
  tags               = local.tier_tag.db
}

resource "aws_iam_role_policy_attachment" "backup" {
  role       = aws_iam_role.backup.name
  policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/service-role/AWSBackupServiceRolePolicyForBackup"
}

resource "aws_backup_selection" "rds" {
  name         = "${local.p}-rds"
  plan_id      = aws_backup_plan.rds.id
  iam_role_arn = aws_iam_role.backup.arn
  resources    = [aws_db_instance.main.arn]
}
