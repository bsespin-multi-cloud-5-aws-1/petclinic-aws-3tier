resource "aws_db_subnet_group" "main" {
  name       = "${local.p}-db"
  subnet_ids = aws_subnet.db[*].id
  tags       = merge(local.tier.db, { Name = "${local.p}-db" })
}

# 기본 파라미터 그룹은 수정 불가 → 사본. Phase 2에서 require_secure_transport=1(TLS 강제), max_connections 상향
resource "aws_db_parameter_group" "main" {
  name   = "${local.p}-mysql84"
  family = "mysql8.4"
  parameter {
    name  = "character_set_server"
    value = "utf8mb4"
  }
  parameter {
    name  = "collation_server"
    value = "utf8mb4_unicode_ci"
  }
  tags = merge(local.tier.db, { Name = "${local.p}-mysql84" })
}

resource "aws_db_instance" "main" {
  identifier     = "${local.p}-petclinic"
  engine         = "mysql"
  engine_version = var.db_engine_version
  instance_class = var.db_instance_class

  db_name                     = var.db_name # 초기 DB — schema.sql 의 CREATE DATABASE 권한 문제 회피
  username                    = var.db_username
  manage_master_user_password = true # Secrets Manager 관리형(rds!db-…), 7일 자동 교체
  parameter_group_name        = aws_db_parameter_group.main.name

  allocated_storage     = 20
  max_allocated_storage = 100
  storage_type          = "gp3"
  storage_encrypted     = true

  multi_az               = var.db_multi_az
  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds.id]
  publicly_accessible    = false
  availability_zone      = var.db_multi_az ? null : var.azs[0]

  backup_retention_period      = 7
  backup_window                = "19:00-19:30" # 04:00 KST
  maintenance_window           = "sun:20:00-sun:20:30"
  monitoring_interval          = 0     # 향상된 모니터링은 역할 추가 필요 → Phase 2 운영 체계에서
  performance_insights_enabled = false # db.t3.small(MySQL) 미지원

  deletion_protection = false # 프로젝트 기간. 운영이면 true
  skip_final_snapshot = true
  apply_immediately   = true

  tags = merge(local.tier.db, { Name = "${local.p}-petclinic" })
}
