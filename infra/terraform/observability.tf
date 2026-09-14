# ---------- CloudWatch Logs (필수 5: 앱 로그 · ALB 액세스(S3) · WAF · CloudTrail · SSM 세션) ----------
locals {
  log_groups = {
    "/mc/web/access"   = 30
    "/mc/web/error"    = 30
    "/mc/was/catalina" = 30
    "/mc/was/access"   = 30
    "/mc/was/gc"       = 30
    "/mc/ssm/sessions" = 90
  }
}

resource "aws_cloudwatch_log_group" "app" {
  for_each          = local.log_groups
  name              = each.key
  retention_in_days = each.value
  kms_key_id        = aws_kms_key.main.arn
  tags              = local.tier_tag.ops
}

# ---------- SNS mc-alerts (시스템 알람 · 이메일). Slack 알림은 Amazon Managed Grafana Alerting → Slack 한 경로로 통일(9/14 결정) ----------
resource "aws_sns_topic" "alerts" {
  name              = "${local.p}-alerts"
  kms_master_key_id = aws_kms_key.main.arn
  tags              = merge(local.tier_tag.ops, { Name = "${local.p}-alerts" })
}

resource "aws_sns_topic_subscription" "email" {
  for_each  = toset(var.alert_emails)
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = each.value
}

# ---------- CloudWatch 알람 3개 ----------
resource "aws_cloudwatch_metric_alarm" "was_unhealthy" {
  alarm_name          = "${local.p}-was-unhealthy-host"
  namespace           = "AWS/ApplicationELB"
  metric_name         = "UnHealthyHostCount"
  statistic           = "Maximum"
  period              = 60
  evaluation_periods  = 2
  threshold           = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  ok_actions          = [aws_sns_topic.alerts.arn]
  dimensions = {
    LoadBalancer = aws_lb.internal.arn_suffix
    TargetGroup  = aws_lb_target_group.was.arn_suffix
  }
  tags = local.tier_tag.ops
}

resource "aws_cloudwatch_metric_alarm" "alb_p95" {
  alarm_name          = "${local.p}-alb-p95-latency"
  namespace           = "AWS/ApplicationELB"
  metric_name         = "TargetResponseTime"
  extended_statistic  = "p95"
  period              = 60
  evaluation_periods  = 3
  threshold           = 2
  comparison_operator = "GreaterThanThreshold"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  ok_actions          = [aws_sns_topic.alerts.arn]
  dimensions = {
    LoadBalancer = aws_lb.public.arn_suffix
  }
  tags = local.tier_tag.ops
}

resource "aws_cloudwatch_metric_alarm" "rds_connections" {
  alarm_name          = "${local.p}-rds-connections-high"
  namespace           = "AWS/RDS"
  metric_name         = "DatabaseConnections"
  statistic           = "Average"
  period              = 60
  evaluation_periods  = 3
  threshold           = 60 # db.t3.small max_connections(~85)의 약 70%
  comparison_operator = "GreaterThanThreshold"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  ok_actions          = [aws_sns_topic.alerts.arn]
  dimensions = {
    DBInstanceIdentifier = aws_db_instance.main.identifier
  }
  tags = local.tier_tag.ops
}

# ---------- CloudTrail (관리 이벤트 · 다중 리전 · 로그 파일 검증) ----------
resource "aws_cloudtrail" "main" {
  name                          = "${local.p}-trail"
  s3_bucket_name                = aws_s3_bucket.cloudtrail.id
  is_multi_region_trail         = true
  include_global_service_events = true
  enable_log_file_validation    = true
  kms_key_id                    = aws_kms_key.main.arn
  tags                          = merge(local.tier_tag.ops, { Name = "${local.p}-trail" })
  depends_on                    = [aws_s3_bucket_policy.cloudtrail]
}

# ---------- SSM Session Manager 환경 설정 (세션 로그 → CloudWatch Logs · KMS) ----------
resource "aws_ssm_document" "session_prefs" {
  name            = "SSM-SessionManagerRunShell"
  document_type   = "Session"
  document_format = "JSON"

  content = jsonencode({
    schemaVersion = "1.0"
    description   = "Session Manager preferences: CloudWatch Logs + KMS"
    sessionType   = "Standard_Stream"
    inputs = {
      kmsKeyId                    = aws_kms_key.main.key_id
      cloudWatchLogGroupName      = "/mc/ssm/sessions"
      cloudWatchEncryptionEnabled = true
      cloudWatchStreamingEnabled  = true
      idleSessionTimeout          = "20"
      runAsEnabled                = false
    }
  })

  tags = local.tier_tag.ops
}

# ---------- Amazon Managed Grafana (선택 · IAM Identity Center 필요) ----------
data "aws_iam_policy_document" "grafana_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["grafana.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "grafana" {
  count              = var.enable_grafana ? 1 : 0
  name               = "${local.p}-grafana-role"
  assume_role_policy = data.aws_iam_policy_document.grafana_assume.json
  tags               = local.tier_tag.ops
}

resource "aws_iam_role_policy_attachment" "grafana_cw" {
  count      = var.enable_grafana ? 1 : 0
  role       = aws_iam_role.grafana[0].name
  policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/service-role/AmazonGrafanaCloudWatchAccess"
}

resource "aws_grafana_workspace" "main" {
  count                    = var.enable_grafana ? 1 : 0
  name                     = "${local.p}-ops"
  account_access_type      = "CURRENT_ACCOUNT"
  authentication_providers = ["AWS_SSO"]
  permission_type          = "SERVICE_MANAGED"
  role_arn                 = aws_iam_role.grafana[0].arn
  data_sources             = ["CLOUDWATCH"]
  tags                     = merge(local.tier_tag.ops, { Name = "${local.p}-ops" })
}
