# ---------- RDS MySQL 8.0 · Multi-AZ (개인정보 저장소: owners · pets · visits) ----------
resource "aws_db_subnet_group" "main" {
  name       = "${local.p}-db-subnets"
  subnet_ids = aws_subnet.db[*].id
  tags       = merge(local.tier_tag.db, { Name = "${local.p}-db-subnets" })
}

resource "aws_db_parameter_group" "main" {
  name   = "${local.p}-mysql80"
  family = "mysql8.0"
  tags   = merge(local.tier_tag.db, { Name = "${local.p}-mysql80" })

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
}

resource "aws_db_instance" "main" {
  identifier     = "${local.p}-petclinic"
  engine         = "mysql"
  engine_version = "8.0"
  instance_class = var.db_instance_class

  allocated_storage     = 20
  max_allocated_storage = 100
  storage_type          = "gp3"
  storage_encrypted     = true
  kms_key_id            = aws_kms_key.main.arn

  db_name  = var.db_name
  username = var.db_username
  # 마스터 비밀번호는 Secrets Manager 관리형(7일 자동 로테이션). RDS Proxy가 직접 조회 → 앱 무영향
  manage_master_user_password   = true
  master_user_secret_kms_key_id = aws_kms_key.main.arn

  multi_az               = true
  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds.id]
  parameter_group_name   = aws_db_parameter_group.main.name
  publicly_accessible    = false
  port                   = 3306

  backup_retention_period = 7
  backup_window           = "19:00-19:30" # 04:00 KST
  maintenance_window      = "sun:20:00-sun:20:30"
  copy_tags_to_snapshot   = true
  deletion_protection     = false # 프로젝트 기간 중 destroy 가능하도록 끔 (운영 전환 시 true)
  skip_final_snapshot     = true

  performance_insights_enabled = false # db.t3.small(MySQL)은 PI 미지원. 병목 분석은 CloudWatch 지표로
  monitoring_interval          = 0
  auto_minor_version_upgrade   = true

  tags = merge(local.tier_tag.db, { Name = "${local.p}-petclinic", Data = "pii" })
}

# ---------- RDS Proxy (커넥션 다중화 · failover 단축 · Require TLS · Secrets 직접 조회) ----------
resource "aws_db_proxy" "main" {
  name                   = "${local.p}-rds-proxy"
  engine_family          = "MYSQL"
  role_arn               = aws_iam_role.rds_proxy.arn
  vpc_subnet_ids         = aws_subnet.db[*].id
  vpc_security_group_ids = [aws_security_group.rds_proxy.id]
  require_tls            = true
  idle_client_timeout    = 1800
  debug_logging          = false

  auth {
    auth_scheme = "SECRETS"
    iam_auth    = "DISABLED"
    secret_arn  = aws_db_instance.main.master_user_secret[0].secret_arn
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

# ---------- 백업: AWS Backup 일일 계획 (자동 백업 7일과 별도로 도쿄 복사는 로드맵) ----------
resource "aws_backup_vault" "main" {
  name        = "${local.p}-backup-vault"
  kms_key_arn = aws_kms_key.main.arn
  tags        = merge(local.tier_tag.db, { Name = "${local.p}-backup-vault" })
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
