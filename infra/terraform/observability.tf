# ---------- CloudWatch Logs (필수 5: 앱 로그 · ALB 액세스(S3) · WAF · CloudTrail · SSM 세션) ----------
locals {
  log_groups = {
    "/mc/web/access"   = 30
    "/mc/web/error"    = 30
    "/mc/was/catalina" = 30
    "/mc/was/access"   = 30
    "/mc/was/gc"       = 30
    "/mc/was/auth"     = 90
    "/mc/was/events"   = 30
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

# ---------- SNS mc-alerts (시스템 알람) ----------
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

# ---------- AWS Chatbot → Slack #mc-alerts (변수 비우면 생성 안 함) ----------
data "aws_iam_policy_document" "chatbot_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["chatbot.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "chatbot" {
  count              = var.slack_team_id != "" ? 1 : 0
  name               = "${local.p}-chatbot-role"
  assume_role_policy = data.aws_iam_policy_document.chatbot_assume.json
  tags               = local.tier_tag.ops
}

resource "aws_iam_role_policy_attachment" "chatbot_readonly" {
  count      = var.slack_team_id != "" ? 1 : 0
  role       = aws_iam_role.chatbot[0].name
  policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/CloudWatchReadOnlyAccess"
}

resource "aws_chatbot_slack_channel_configuration" "alerts" {
  count              = var.slack_team_id != "" ? 1 : 0
  configuration_name = "${local.p}-alerts"
  iam_role_arn       = aws_iam_role.chatbot[0].arn
  slack_channel_id   = var.slack_alerts_channel_id
  slack_team_id      = var.slack_team_id
  sns_topic_arns     = [aws_sns_topic.alerts.arn]
  logging_level      = "ERROR"
  tags               = merge(local.tier_tag.ops, { Name = "${local.p}-alerts" })
}

# ---------- 예약 알림: /mc/was/events 구독 필터 → Lambda → Slack #mc-reservations ----------
resource "aws_secretsmanager_secret" "slack_webhook" {
  name       = "${local.p}/slack-webhook-reservations"
  kms_key_id = aws_kms_key.main.arn
  tags       = merge(local.tier_tag.ops, { Name = "${local.p}/slack-webhook-reservations" })
  # 값(Incoming Webhook URL)은 콘솔/CLI로 수동 입력 — 저장소에 남기지 않음
}

data "archive_file" "notify" {
  type        = "zip"
  source_file = "${path.module}/lambda/notify.py"
  output_path = "${path.module}/lambda/notify.zip"
}

data "aws_iam_policy_document" "lambda_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "notify" {
  name               = "${local.p}-notify-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
  tags               = local.tier_tag.ops
}

resource "aws_iam_role_policy_attachment" "notify_basic" {
  role       = aws_iam_role.notify.name
  policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

data "aws_iam_policy_document" "notify_inline" {
  statement {
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [aws_secretsmanager_secret.slack_webhook.arn]
  }
  statement {
    actions   = ["kms:Decrypt"]
    resources = [aws_kms_key.main.arn]
  }
  statement {
    actions   = ["sqs:SendMessage"]
    resources = [aws_sqs_queue.notify_dlq.arn]
  }
}

resource "aws_iam_role_policy" "notify_inline" {
  name   = "${local.p}-notify-inline"
  role   = aws_iam_role.notify.id
  policy = data.aws_iam_policy_document.notify_inline.json
}

resource "aws_sqs_queue" "notify_dlq" {
  name                    = "${local.p}-notify-dlq"
  sqs_managed_sse_enabled = true
  tags                    = merge(local.tier_tag.ops, { Name = "${local.p}-notify-dlq" })
}

resource "aws_lambda_function" "notify" {
  function_name    = "${local.p}-notify-reservation"
  role             = aws_iam_role.notify.arn
  runtime          = "python3.12"
  handler          = "notify.handler"
  filename         = data.archive_file.notify.output_path
  source_code_hash = data.archive_file.notify.output_base64sha256
  timeout          = 10
  memory_size      = 128


  environment {
    variables = {
      SLACK_WEBHOOK_SECRET_ID = aws_secretsmanager_secret.slack_webhook.name
      APP_BASE_URL            = "https://${var.domain_name}${local.app_context}"
    }
  }

  dead_letter_config {
    target_arn = aws_sqs_queue.notify_dlq.arn
  }

  tags = merge(local.tier_tag.ops, { Name = "${local.p}-notify-reservation" })
}

resource "aws_lambda_permission" "logs_invoke" {
  statement_id   = "AllowCloudWatchLogs"
  action         = "lambda:InvokeFunction"
  function_name  = aws_lambda_function.notify.function_name
  principal      = "logs.${var.region}.amazonaws.com"
  source_arn     = "${aws_cloudwatch_log_group.app["/mc/was/events"].arn}:*"
  source_account = data.aws_caller_identity.current.account_id
}

resource "aws_cloudwatch_log_subscription_filter" "reservation" {
  name            = "${local.p}-reservation-created"
  log_group_name  = aws_cloudwatch_log_group.app["/mc/was/events"].name
  filter_pattern  = "RESERVATION_CREATED"
  destination_arn = aws_lambda_function.notify.arn
  depends_on      = [aws_lambda_permission.logs_invoke]
}

# 같은 로그의 지표 필터: 예약 건수 → 대시보드 · 폭주 알람
resource "aws_cloudwatch_log_metric_filter" "reservation_count" {
  name           = "${local.p}-reservation-count"
  log_group_name = aws_cloudwatch_log_group.app["/mc/was/events"].name
  pattern        = "RESERVATION_CREATED"

  metric_transformation {
    name      = "ReservationCount"
    namespace = "MC/Petclinic"
    value     = "1"
    unit      = "Count"
  }
}

resource "aws_cloudwatch_metric_alarm" "reservation_surge" {
  alarm_name          = "${local.p}-reservation-surge"
  namespace           = "MC/Petclinic"
  metric_name         = "ReservationCount"
  statistic           = "Sum"
  period              = 60
  evaluation_periods  = 1
  threshold           = 100
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  tags                = local.tier_tag.ops
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
