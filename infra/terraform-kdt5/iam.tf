# ---------- EC2 역할 인라인 정책 (kdt5: 기존 mc-ec2-role 에 · create_base: 모듈 역할에). SSM Core · CW Agent 는 부착돼 있음 ----------
# 주의: kdt5 인스턴스(WEB ASG · WAS-test-a)에는 인스턴스 프로파일이 아직 안 붙어 있음 → 콘솔 후속 (ⓜ3)
data "aws_iam_policy_document" "ec2_inline" {
  statement {
    sid       = "ReadRdsSecrets" # admin(사용자 생성) + 앱 사용자(빌드 시 -Djdbc.* 주입)
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [aws_db_instance.main.master_user_secret[0].secret_arn, aws_secretsmanager_secret.app_db.arn]
  }
  statement {
    sid       = "DecryptSecret"
    actions   = ["kms:Decrypt"]
    resources = [data.aws_kms_alias.secretsmanager.target_key_arn]
    condition {
      test     = "StringEquals"
      variable = "kms:ViaService"
      values   = ["secretsmanager.${var.region}.amazonaws.com"]
    }
  }
  statement {
    sid       = "ReadCwAgentConfig"
    actions   = ["ssm:GetParameter"]
    resources = [for p in aws_ssm_parameter.cwagent : p.arn]
  }
  statement {
    sid       = "SyncLogsToS3" # ASG 종료 훅 · 수동 로그 보관
    actions   = ["s3:PutObject"]
    resources = ["${aws_s3_bucket.logs.arn}/was/*", "${aws_s3_bucket.logs.arn}/web/*"]
  }
}

resource "aws_iam_role_policy" "ec2_inline" {
  name   = "${local.p}-ec2-inline"
  role   = local.ec2_role_id
  policy = data.aws_iam_policy_document.ec2_inline.json
}

# ---------- RDS Proxy 역할: Secrets Manager 조회 ----------
data "aws_iam_policy_document" "rds_proxy_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["rds.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "rds_proxy" {
  name               = "${local.p}-rds-proxy-role"
  assume_role_policy = data.aws_iam_policy_document.rds_proxy_assume.json
  tags               = local.tier_tag.db
}

data "aws_iam_policy_document" "rds_proxy_inline" {
  statement {
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [aws_db_instance.main.master_user_secret[0].secret_arn, aws_secretsmanager_secret.app_db.arn]
  }
  statement {
    actions   = ["kms:Decrypt"]
    resources = [data.aws_kms_alias.secretsmanager.target_key_arn]
    condition {
      test     = "StringEquals"
      variable = "kms:ViaService"
      values   = ["secretsmanager.${var.region}.amazonaws.com"]
    }
  }
}

resource "aws_iam_role_policy" "rds_proxy_inline" {
  name   = "${local.p}-rds-proxy-inline"
  role   = aws_iam_role.rds_proxy.id
  policy = data.aws_iam_policy_document.rds_proxy_inline.json
}
