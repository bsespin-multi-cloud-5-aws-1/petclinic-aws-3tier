# ---------- KMS CMK: S3 이미지 · 로그 · RDS · Secrets ----------
data "aws_iam_policy_document" "kms" {
  statement {
    sid       = "EnableRoot"
    actions   = ["kms:*"]
    resources = ["*"]
    principals {
      type        = "AWS"
      identifiers = ["arn:${data.aws_partition.current.partition}:iam::${data.aws_caller_identity.current.account_id}:root"]
    }
  }
  statement {
    sid       = "CloudFrontOACDecrypt"
    actions   = ["kms:Decrypt", "kms:Encrypt", "kms:GenerateDataKey*"]
    resources = ["*"]
    principals {
      type        = "Service"
      identifiers = ["cloudfront.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "aws:SourceArn"
      values   = [aws_cloudfront_distribution.main.arn]
    }
  }
  statement {
    sid       = "LogDeliveryServices"
    actions   = ["kms:Encrypt", "kms:Decrypt", "kms:GenerateDataKey*", "kms:DescribeKey"]
    resources = ["*"]
    principals {
      type        = "Service"
      identifiers = ["logs.${var.region}.amazonaws.com", "cloudtrail.amazonaws.com", "delivery.logs.amazonaws.com"]
    }
  }
}

resource "aws_kms_key" "main" {
  description         = "${local.p} CMK (S3 · RDS · Secrets · Logs)"
  enable_key_rotation = true
  policy              = data.aws_iam_policy_document.kms.json
  tags                = merge(local.tier_tag.db, { Name = "${local.p}-cmk" })
}

resource "aws_kms_alias" "main" {
  name          = "alias/${local.p}-cmk"
  target_key_id = aws_kms_key.main.key_id
}

# ---------- 공통 버킷 설정 헬퍼 ----------
locals {
  buckets = {
    maintenance = { name = "${local.p}-maintenance-${data.aws_caller_identity.current.account_id}", tier = "edge" }
    logs        = { name = "${local.p}-logs-${data.aws_caller_identity.current.account_id}", tier = "ops" }
    cloudtrail  = { name = "${local.p}-cloudtrail-${data.aws_caller_identity.current.account_id}", tier = "ops" }
  }
}

# ---------- 점검 페이지 버킷 (CloudFront OAC로만 읽기) ----------
# 공개 이미지 버킷(mc-images · 수의사/후기 사진)은 9/15 제거 — 정적 이미지는 WAR resources/ 로 통합, /petclinic/resources/* CloudFront 캐시가 담당
resource "aws_s3_bucket" "maintenance" {
  bucket        = local.buckets.maintenance.name
  force_destroy = true # destroy 시 객체까지 삭제 (프로젝트 정리용)
  tags          = merge(local.tier_tag.edge, { Name = local.buckets.maintenance.name })
}

resource "aws_s3_bucket" "logs" {
  bucket        = local.buckets.logs.name
  force_destroy = true # destroy 시 객체까지 삭제 (프로젝트 정리용)
  tags          = merge(local.tier_tag.ops, { Name = local.buckets.logs.name })
}

resource "aws_s3_bucket" "cloudtrail" {
  bucket        = local.buckets.cloudtrail.name
  force_destroy = true # destroy 시 객체까지 삭제 (프로젝트 정리용)
  tags          = merge(local.tier_tag.ops, { Name = local.buckets.cloudtrail.name })
}

locals {
  all_buckets = {
    maintenance = aws_s3_bucket.maintenance
    logs        = aws_s3_bucket.logs
    cloudtrail  = aws_s3_bucket.cloudtrail
  }
}

resource "aws_s3_bucket_public_access_block" "all" {
  for_each                = local.all_buckets
  bucket                  = each.value.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "all" {
  for_each = local.all_buckets
  bucket   = each.value.id
  versioning_configuration {
    status = "Enabled"
  }
}

# 점검 페이지·CloudTrail: SSE-KMS + 버킷 키. 로그 버킷은 전송 서비스 호환을 위해 SSE-S3
resource "aws_s3_bucket_server_side_encryption_configuration" "kms" {
  for_each = { maintenance = aws_s3_bucket.maintenance, cloudtrail = aws_s3_bucket.cloudtrail }
  bucket   = each.value.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.main.arn
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "logs" {
  bucket = aws_s3_bucket.logs.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# 로그 Lifecycle: ALB 액세스 로그 90일 · 종료 훅 로그 30일
resource "aws_s3_bucket_lifecycle_configuration" "logs" {
  bucket = aws_s3_bucket.logs.id
  rule {
    id     = "alb-access-90d"
    status = "Enabled"
    filter {
      prefix = "alb/"
    }
    expiration {
      days = 90
    }
  }
  rule {
    id     = "instance-logs-30d"
    status = "Enabled"
    filter {
      prefix = "was/"
    }
    expiration {
      days = 30
    }
  }
  rule {
    id     = "abort-multipart"
    status = "Enabled"
    filter {}
    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "cloudtrail" {
  bucket = aws_s3_bucket.cloudtrail.id
  rule {
    id     = "audit-1y"
    status = "Enabled"
    filter {}
    transition {
      days          = 90
      storage_class = "GLACIER_IR"
    }
    expiration {
      days = 365
    }
  }
}

# ---------- 버킷 정책 ----------
# 점검 페이지: CloudFront OAC(SigV4) + SourceArn 조건. 공개 읽기 없음
data "aws_iam_policy_document" "oac_bucket" {
  for_each = { maintenance = aws_s3_bucket.maintenance }
  statement {
    sid       = "AllowCloudFrontOAC"
    actions   = ["s3:GetObject"]
    resources = ["${each.value.arn}/*"]
    principals {
      type        = "Service"
      identifiers = ["cloudfront.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "AWS:SourceArn"
      values   = [aws_cloudfront_distribution.main.arn]
    }
  }
  statement {
    sid       = "DenyInsecureTransport"
    effect    = "Deny"
    actions   = ["s3:*"]
    resources = [each.value.arn, "${each.value.arn}/*"]
    principals {
      type        = "*"
      identifiers = ["*"]
    }
    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

resource "aws_s3_bucket_policy" "oac" {
  for_each = { maintenance = aws_s3_bucket.maintenance }
  bucket   = each.value.id
  policy   = data.aws_iam_policy_document.oac_bucket[each.key].json
}

# 로그 버킷: ALB 액세스 로그 전송 계정 허용
data "aws_elb_service_account" "main" {}

data "aws_iam_policy_document" "logs_bucket" {
  statement {
    sid       = "ALBAccessLogs"
    actions   = ["s3:PutObject"]
    resources = ["${aws_s3_bucket.logs.arn}/alb/*"]
    principals {
      type        = "AWS"
      identifiers = [data.aws_elb_service_account.main.arn]
    }
  }
  statement {
    sid       = "DenyInsecureTransport"
    effect    = "Deny"
    actions   = ["s3:*"]
    resources = [aws_s3_bucket.logs.arn, "${aws_s3_bucket.logs.arn}/*"]
    principals {
      type        = "*"
      identifiers = ["*"]
    }
    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

resource "aws_s3_bucket_policy" "logs" {
  bucket = aws_s3_bucket.logs.id
  policy = data.aws_iam_policy_document.logs_bucket.json
}

# CloudTrail 버킷
data "aws_iam_policy_document" "cloudtrail_bucket" {
  statement {
    sid       = "AWSCloudTrailAclCheck"
    actions   = ["s3:GetBucketAcl"]
    resources = [aws_s3_bucket.cloudtrail.arn]
    principals {
      type        = "Service"
      identifiers = ["cloudtrail.amazonaws.com"]
    }
  }
  statement {
    sid       = "AWSCloudTrailWrite"
    actions   = ["s3:PutObject"]
    resources = ["${aws_s3_bucket.cloudtrail.arn}/AWSLogs/${data.aws_caller_identity.current.account_id}/*"]
    principals {
      type        = "Service"
      identifiers = ["cloudtrail.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "s3:x-amz-acl"
      values   = ["bucket-owner-full-control"]
    }
  }
}

resource "aws_s3_bucket_policy" "cloudtrail" {
  bucket = aws_s3_bucket.cloudtrail.id
  policy = data.aws_iam_policy_document.cloudtrail_bucket.json
}

# 점검 페이지 객체
resource "aws_s3_object" "maintenance_page" {
  bucket       = aws_s3_bucket.maintenance.id
  key          = "maintenance.html"
  content_type = "text/html; charset=utf-8"
  content      = "<!doctype html><meta charset=\"utf-8\"><title>점검 중</title><h1>Mission Critical Pet Clinic</h1><p>지금은 점검 중입니다. 잠시 후 다시 접속해 주세요.</p>"
  kms_key_id   = aws_kms_key.main.arn
}
