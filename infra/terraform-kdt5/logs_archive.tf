# ---------- ④ DB 계층 로그 → CloudWatch Logs · 모든 CloudWatch Logs → S3 장기 보관 (Firehose 구독) — 9/17 ----------
# 도면의 빈 화살표 두 개를 채운다: (1) RDS(error·slowquery)·RDS Proxy 로그 → CloudWatch Logs, (2) CloudWatch Logs → S3 mc-logs/cwlogs/ (1년).
# CloudWatch Logs 는 자체 저장소라 S3 에 "저장"되는 게 아니고, 구독 필터 → Kinesis Data Firehose 가 사본을 S3 객체로 떨군다(5분 버퍼 · gzip).
# RDS/Proxy 로그 그룹은 이름이 서비스에 고정돼 있어(/aws/rds/…) 미리 만들어 보존 기간·KMS 를 건다 (이미 자동 생성된 두 개는 imports.tf 로 편입).
locals {
  rds_log_groups = {
    error     = "/aws/rds/instance/${local.db_identifier}/error"
    slowquery = "/aws/rds/instance/${local.db_identifier}/slowquery"
    proxy     = "/aws/rds/proxy/${local.p}-rds-proxy"
  }
  # 계층(=Firehose 스트림 · S3 접두사) → 구독할 로그 그룹. WAF 로그는 us-east-1 이라 제외(구독은 같은 리전만)
  cwlogs_archive = {
    web     = ["/mc/web/access", "/mc/web/error"]
    was     = ["/mc/was/catalina", "/mc/was/access", "/mc/was/gc"]
    bastion = var.create_base && var.base.create_bastion ? ["/mc/bastion/secure"] : []
    db      = [for k in sort(keys(local.rds_log_groups)) : local.rds_log_groups[k]]
  }
  cwlogs_subscriptions = {
    for pair in flatten([for tier, groups in local.cwlogs_archive : [for g in groups : { tier = tier, group = g }]]) :
    "${pair.tier}:${pair.group}" => pair
  }
}

resource "aws_cloudwatch_log_group" "rds" {
  for_each          = local.rds_log_groups
  name              = each.value
  retention_in_days = var.log_retention_days
  kms_key_id        = aws_kms_key.main.arn
  tags              = merge(local.tier_tag.db, { Name = each.value })
}

# ---- Firehose (계층당 1개) → S3 mc-logs/cwlogs/<tier>/yyyy/MM/dd/ ----
data "aws_iam_policy_document" "firehose_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["firehose.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "sts:ExternalId"
      values   = [data.aws_caller_identity.current.account_id]
    }
  }
}

resource "aws_iam_role" "firehose" {
  name               = "${local.p}-firehose-cwlogs-role"
  assume_role_policy = data.aws_iam_policy_document.firehose_assume.json
  tags               = local.tier_tag.ops
}

data "aws_iam_policy_document" "firehose_s3" {
  statement {
    actions   = ["s3:AbortMultipartUpload", "s3:GetBucketLocation", "s3:GetObject", "s3:ListBucket", "s3:ListBucketMultipartUploads", "s3:PutObject"]
    resources = [aws_s3_bucket.logs.arn, "${aws_s3_bucket.logs.arn}/cwlogs/*", "${aws_s3_bucket.logs.arn}/cwlogs-errors/*"]
  }
}

resource "aws_iam_role_policy" "firehose_s3" {
  name   = "${local.p}-firehose-s3"
  role   = aws_iam_role.firehose.id
  policy = data.aws_iam_policy_document.firehose_s3.json
}

resource "aws_kinesis_firehose_delivery_stream" "cwlogs" {
  for_each    = { for tier, groups in local.cwlogs_archive : tier => groups if length(groups) > 0 }
  name        = "${local.p}-cwlogs-${each.key}"
  destination = "extended_s3"

  extended_s3_configuration {
    role_arn            = aws_iam_role.firehose.arn
    bucket_arn          = aws_s3_bucket.logs.arn
    prefix              = "cwlogs/${each.key}/!{timestamp:yyyy/MM/dd}/"
    error_output_prefix = "cwlogs-errors/${each.key}/!{firehose:error-output-type}/!{timestamp:yyyy/MM/dd}/"
    buffering_size      = 5   # MB
    buffering_interval  = 300 # 초 — 로그 양이 적어 대개 5분마다 객체 1개
    compression_format  = "GZIP"

    # 구독 필터가 보내는 레코드는 gzip 된 배치(JSON: logGroup · logStream · logEvents[]) → 풀어서 줄 단위 JSON 으로 저장(Athena 로 바로 조회)
    processing_configuration {
      enabled = true
      processors {
        type = "Decompression"
        parameters {
          parameter_name  = "CompressionFormat"
          parameter_value = "GZIP"
        }
      }
      processors {
        type = "AppendDelimiterToRecord" # 기본 구분자 = 개행. Delimiter 파라미터를 적으면 API 가 돌려주지 않아 plan 이 계속 바뀜 → 생략
      }
    }

    cloudwatch_logging_options {
      enabled = false
    }
  }

  tags = merge(local.tier_tag.ops, { Name = "${local.p}-cwlogs-${each.key}" })
}

# ---- CloudWatch Logs → Firehose 구독 필터 (그룹당 1개 · 필터 없음 = 전부) ----
data "aws_iam_policy_document" "logs_to_firehose_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["logs.${var.region}.amazonaws.com"]
    }
    condition {
      test     = "ArnLike"
      variable = "aws:SourceArn"
      values   = ["arn:${data.aws_partition.current.partition}:logs:${var.region}:${data.aws_caller_identity.current.account_id}:*"]
    }
  }
}

resource "aws_iam_role" "logs_to_firehose" {
  name               = "${local.p}-cwlogs-to-firehose-role"
  assume_role_policy = data.aws_iam_policy_document.logs_to_firehose_assume.json
  tags               = local.tier_tag.ops
}

data "aws_iam_policy_document" "logs_to_firehose" {
  statement {
    actions   = ["firehose:PutRecord", "firehose:PutRecordBatch"]
    resources = [for s in aws_kinesis_firehose_delivery_stream.cwlogs : s.arn]
  }
}

resource "aws_iam_role_policy" "logs_to_firehose" {
  name   = "${local.p}-cwlogs-to-firehose"
  role   = aws_iam_role.logs_to_firehose.id
  policy = data.aws_iam_policy_document.logs_to_firehose.json
}

resource "aws_cloudwatch_log_subscription_filter" "cwlogs" {
  for_each        = local.cwlogs_subscriptions
  name            = "${local.p}-s3-archive"
  log_group_name  = each.value.group
  filter_pattern  = ""
  destination_arn = aws_kinesis_firehose_delivery_stream.cwlogs[each.value.tier].arn
  role_arn        = aws_iam_role.logs_to_firehose.arn

  depends_on = [aws_cloudwatch_log_group.app, aws_cloudwatch_log_group.rds, aws_iam_role_policy.logs_to_firehose]
}
