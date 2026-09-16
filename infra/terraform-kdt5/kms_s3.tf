# ---------- KMS CMK: S3(점검·CloudTrail) · SNS · CloudWatch Logs · Backup 볼트 (RDS·비밀은 AWS 관리형 키 그대로) ----------
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
      identifiers = ["logs.${var.region}.amazonaws.com", "cloudtrail.amazonaws.com", "delivery.logs.amazonaws.com", "sns.amazonaws.com", "cloudwatch.amazonaws.com"]
    }
  }
}

resource "aws_kms_key" "main" {
  description         = "${local.p} CMK (S3 · SNS · Logs · Backup)"
  enable_key_rotation = true
  policy              = data.aws_iam_policy_document.kms.json
  tags                = merge(local.tier_tag.ops, { Name = "${local.p}-cmk" })
}

resource "aws_kms_alias" "main" {
  name          = "alias/${local.p}-cmk"
  target_key_id = aws_kms_key.main.key_id
}

# ---------- 버킷 3: 점검 페이지(OAC 전용) · 로그(ALB 액세스 · 인스턴스) · CloudTrail ----------
locals {
  buckets = {
    maintenance = "${local.p}-maintenance-${data.aws_caller_identity.current.account_id}"
    logs        = "${local.p}-logs-${data.aws_caller_identity.current.account_id}"
    static      = "${local.p}-static-${data.aws_caller_identity.current.account_id}"
    cloudtrail  = "${local.p}-cloudtrail-${data.aws_caller_identity.current.account_id}"
  }
}

resource "aws_s3_bucket" "maintenance" {
  bucket        = local.buckets.maintenance
  force_destroy = true
  tags          = merge(local.tier_tag.edge, { Name = local.buckets.maintenance })
}

# 정적 자산(랜딩 페이지 css·이미지·hero 영상): CloudFront /static/* · /images/* 의 오리진 (OAC). Apache 를 거치지 않음
resource "aws_s3_bucket" "static" {
  bucket        = local.buckets.static
  force_destroy = true
  tags          = merge(local.tier_tag.edge, { Name = local.buckets.static })
}

resource "aws_s3_bucket" "logs" {
  bucket        = local.buckets.logs
  force_destroy = true
  tags          = merge(local.tier_tag.ops, { Name = local.buckets.logs })
}

resource "aws_s3_bucket" "cloudtrail" {
  bucket        = local.buckets.cloudtrail
  force_destroy = true
  tags          = merge(local.tier_tag.ops, { Name = local.buckets.cloudtrail })
}

locals {
  all_buckets = {
    maintenance = aws_s3_bucket.maintenance
    static      = aws_s3_bucket.static
    logs        = aws_s3_bucket.logs
    cloudtrail  = aws_s3_bucket.cloudtrail
  }
}

# CloudFront 표준 로그는 버킷 ACL(awslogsdelivery FULL_CONTROL)로 쓰므로 로그 버킷만 ACL 허용(BucketOwnerPreferred). 나머지는 기본(ACL 비활성)
resource "aws_s3_bucket_ownership_controls" "logs" {
  bucket = aws_s3_bucket.logs.id
  rule {
    object_ownership = "BucketOwnerPreferred"
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

# 점검 페이지·CloudTrail: SSE-KMS + 버킷 키. 로그 버킷은 ALB 로그 전송 호환을 위해 SSE-S3
resource "aws_s3_bucket_server_side_encryption_configuration" "kms" {
  for_each = { maintenance = aws_s3_bucket.maintenance, static = aws_s3_bucket.static, cloudtrail = aws_s3_bucket.cloudtrail }
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
    id     = "cloudfront-access-90d"
    status = "Enabled"
    filter {
      prefix = "cloudfront/"
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
data "aws_iam_policy_document" "maintenance_bucket" {
  statement {
    sid       = "AllowCloudFrontOAC"
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.maintenance.arn}/*"]
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
    resources = [aws_s3_bucket.maintenance.arn, "${aws_s3_bucket.maintenance.arn}/*"]
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

resource "aws_s3_bucket_policy" "maintenance" {
  bucket = aws_s3_bucket.maintenance.id
  policy = data.aws_iam_policy_document.maintenance_bucket.json
}

data "aws_iam_policy_document" "static_bucket" {
  statement {
    sid       = "AllowCloudFrontOAC"
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.static.arn}/*"]
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
    resources = [aws_s3_bucket.static.arn, "${aws_s3_bucket.static.arn}/*"]
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

resource "aws_s3_bucket_policy" "static" {
  bucket = aws_s3_bucket.static.id
  policy = data.aws_iam_policy_document.static_bucket.json
}

# 정적 자산 동기화: 저장소의 src/main/webapp/resources·images → s3://mc-static/static/… (apply 때 바뀐 파일만 다시 올림). .less 원본은 제외
locals {
  static_root = "${path.root}/../../src/main/webapp"
  static_files = merge(
    { for f in fileset("${local.static_root}/resources", "**") : "static/resources/${f}" => "${local.static_root}/resources/${f}" if !startswith(f, "less/") },
    { for f in fileset("${local.static_root}/images", "**") : "static/images/${f}" => "${local.static_root}/images/${f}" },
  )
  mime = {
    css = "text/css", js = "application/javascript", json = "application/json", html = "text/html", svg = "image/svg+xml",
    png = "image/png", jpg = "image/jpeg", jpeg = "image/jpeg", gif = "image/gif", webp = "image/webp", ico = "image/x-icon",
    mp4 = "video/mp4", webm = "video/webm", woff = "font/woff", woff2 = "font/woff2", ttf = "font/ttf", eot = "application/vnd.ms-fontobject", otf = "font/otf",
  }
}

resource "aws_s3_object" "static" {
  for_each      = local.static_files
  bucket        = aws_s3_bucket.static.id
  key           = each.key
  source        = each.value
  source_hash   = filemd5(each.value)
  content_type  = lookup(local.mime, lower(element(split(".", each.key), length(split(".", each.key)) - 1)), "application/octet-stream")
  cache_control = "public, max-age=86400"
  tags          = local.tier_tag.edge
}

# 로그 버킷: ALB 액세스 로그 전송 계정 허용 → 기존 ALB 두 개의 "액세스 로그" 를 콘솔에서 이 버킷으로 켜면 됨 (README 후속)
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
