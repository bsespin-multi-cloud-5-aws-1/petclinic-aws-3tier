# ---------- ① 진입 계층: Route 53 → CloudFront [WAF · ACM] → (기존) Public ALB / S3 점검 페이지(OAC) ----------
# 호스팅 존은 이 코드가 생성. apply 후 output route53_name_servers 4개를 가비아 네임서버로 교체
resource "aws_route53_zone" "main" {
  name    = var.hosted_zone_name
  comment = "${local.p} petclinic (registrar: Gabia)"
  tags    = merge(local.tier_tag.edge, { Name = var.hosted_zone_name })
}

resource "aws_acm_certificate" "cloudfront" {
  provider          = aws.us_east_1
  domain_name       = var.domain_name
  validation_method = "DNS"
  tags              = merge(local.tier_tag.edge, { Name = "${local.p}-acm-cloudfront" })

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_acm_certificate" "alb" {
  domain_name       = var.domain_name
  validation_method = "DNS"
  tags              = merge(local.tier_tag.edge, { Name = "${local.p}-acm-alb" })

  lifecycle {
    create_before_destroy = true
  }
}

# 두 인증서의 검증 CNAME 은 동일 → 한 번만 생성 (자동 갱신을 위해 삭제 금지)
resource "aws_route53_record" "acm_validation" {
  for_each = {
    for dvo in aws_acm_certificate.cloudfront.domain_validation_options : dvo.domain_name => {
      name   = dvo.resource_record_name
      record = dvo.resource_record_value
      type   = dvo.resource_record_type
    }
  }

  zone_id         = aws_route53_zone.main.zone_id
  name            = each.value.name
  type            = each.value.type
  ttl             = 60
  records         = [each.value.record]
  allow_overwrite = true
}

resource "aws_acm_certificate_validation" "cloudfront" {
  provider                = aws.us_east_1
  certificate_arn         = aws_acm_certificate.cloudfront.arn
  validation_record_fqdns = [for r in aws_route53_record.acm_validation : r.fqdn]
}

resource "aws_acm_certificate_validation" "alb" {
  certificate_arn         = aws_acm_certificate.alb.arn
  validation_record_fqdns = [for r in aws_route53_record.acm_validation : r.fqdn]
}

# ---------- WAF (CLOUDFRONT 범위 · us-east-1) — 별도 홉이 아니라 CloudFront 에 부착된 Web ACL ----------
resource "aws_cloudwatch_log_group" "waf" {
  count             = var.enable_waf ? 1 : 0
  provider          = aws.us_east_1
  name              = "aws-waf-logs-${local.p}"
  retention_in_days = var.log_retention_days
  tags              = local.tier_tag.edge
}

resource "aws_wafv2_ip_set" "loadgen" {
  count              = var.enable_waf ? 1 : 0
  provider           = aws.us_east_1
  name               = "${local.p}-loadgen"
  scope              = "CLOUDFRONT"
  ip_address_version = "IPV4"
  addresses          = var.loadgen_cidrs
  tags               = local.tier_tag.edge
}

resource "aws_wafv2_web_acl" "main" {
  count    = var.enable_waf ? 1 : 0
  provider = aws.us_east_1
  name     = "${local.p}-web-acl"
  scope    = "CLOUDFRONT"

  default_action {
    allow {}
  }

  # 0. JMeter 부하 발생기 허용 (Phase 3 실험 후 loadgen_cidrs 비움)
  rule {
    name     = "allow-loadgen"
    priority = 0
    action {
      allow {}
    }
    statement {
      ip_set_reference_statement {
        arn = aws_wafv2_ip_set.loadgen[0].arn
      }
    }
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "allowLoadgen"
      sampled_requests_enabled   = true
    }
  }

  # 1~3. 관리형 규칙
  dynamic "rule" {
    for_each = {
      1 = "AWSManagedRulesAmazonIpReputationList"
      2 = "AWSManagedRulesCommonRuleSet"
      3 = "AWSManagedRulesKnownBadInputsRuleSet"
    }
    content {
      name     = rule.value
      priority = rule.key
      override_action {
        none {}
      }
      statement {
        managed_rule_group_statement {
          name        = rule.value
          vendor_name = "AWS"
        }
      }
      visibility_config {
        cloudwatch_metrics_enabled = true
        metric_name                = rule.value
        sampled_requests_enabled   = true
      }
    }
  }

  # 4. rate-based 전체: IP당 5분 2,000
  rule {
    name     = "rate-all"
    priority = 4
    action {
      block {}
    }
    statement {
      rate_based_statement {
        limit                 = var.waf_rate_limit_all
        aggregate_key_type    = "IP"
        evaluation_window_sec = 300
      }
    }
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "rateAll"
      sampled_requests_enabled   = true
    }
  }

  # 5. rate-based 예약 경로(/visits/new): IP당 5분 100 — Phase 3 예약 폭주 대응
  rule {
    name     = "rate-booking"
    priority = 5
    action {
      block {}
    }
    statement {
      rate_based_statement {
        limit                 = var.waf_rate_limit_booking
        aggregate_key_type    = "IP"
        evaluation_window_sec = 300
        scope_down_statement {
          byte_match_statement {
            positional_constraint = "ENDS_WITH"
            search_string         = "/visits/new"
            field_to_match {
              uri_path {}
            }
            text_transformation {
              priority = 0
              type     = "LOWERCASE"
            }
          }
        }
      }
    }
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "rateBooking"
      sampled_requests_enabled   = true
    }
  }

  visibility_config {
    cloudwatch_metrics_enabled = true
    metric_name                = "${local.p}-web-acl"
    sampled_requests_enabled   = true
  }

  tags = merge(local.tier_tag.edge, { Name = "${local.p}-web-acl" })
}

resource "aws_wafv2_web_acl_logging_configuration" "main" {
  count                   = var.enable_waf ? 1 : 0
  provider                = aws.us_east_1
  resource_arn            = aws_wafv2_web_acl.main[0].arn
  log_destination_configs = [aws_cloudwatch_log_group.waf[0].arn]
}

# ---------- CloudFront ----------
data "aws_cloudfront_cache_policy" "optimized" {
  name = "Managed-CachingOptimized"
}

data "aws_cloudfront_cache_policy" "disabled" {
  name = "Managed-CachingDisabled"
}

data "aws_cloudfront_origin_request_policy" "all_viewer" {
  name = "Managed-AllViewer"
}

data "aws_cloudfront_response_headers_policy" "security" {
  name = "Managed-SecurityHeadersPolicy"
}

resource "aws_cloudfront_origin_access_control" "s3" {
  name                              = "${local.p}-oac-s3"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

locals {
  cf_origin_alb           = "alb-public"
  cf_origin_maintenance   = "s3-maintenance"
  cf_origin_static        = "s3-static"        # /static/*  → 키 static/…
  cf_origin_static_images = "s3-static-images" # /images/*  → origin_path /static → 키 static/images/…
  cf_origin_group         = "alb-with-maintenance-failover"
}

resource "aws_cloudfront_distribution" "main" {
  enabled         = true
  is_ipv6_enabled = true
  comment         = "${local.p} petclinic (Behavior 분기: 정적 S3(OAC) 캐시 / 점검 페이지 S3 / 동적 ALB)"
  aliases         = [var.domain_name]
  price_class     = "PriceClass_200"
  web_acl_id      = var.enable_waf ? aws_wafv2_web_acl.main[0].arn : null
  http_version    = "http2and3"

  # 액세스 로그 → S3 mc-logs/cloudfront/ (WAF 제거 후 엣지에서의 유일한 요청 기록). 표준 로그는 S3 만 지원, 버킷 ACL 필요(kms_s3.tf ownership_controls)
  logging_config {
    bucket          = aws_s3_bucket.logs.bucket_domain_name
    prefix          = "cloudfront/"
    include_cookies = false
  }

  # 오리진 1: 기존 Public ALB(test-Public-ALB) — HTTPS only + 검증 헤더 (443 리스너는 alb.tf 가 추가)
  origin {
    domain_name = local.public_alb_dns
    origin_id   = local.cf_origin_alb

    custom_origin_config {
      http_port                = 80
      https_port               = 443
      origin_protocol_policy   = "https-only"
      origin_ssl_protocols     = ["TLSv1.2"]
      origin_read_timeout      = 30
      origin_keepalive_timeout = 5
    }

    custom_header {
      name  = "X-Origin-Verify"
      value = var.origin_verify_secret
    }
  }

  # 오리진 2: 점검 페이지 S3 (OAC) — 오리진 그룹 secondary
  origin {
    domain_name              = aws_s3_bucket.maintenance.bucket_regional_domain_name
    origin_id                = local.cf_origin_maintenance
    origin_access_control_id = aws_cloudfront_origin_access_control.s3.id
  }

  # 오리진 3·4: 정적 자산 S3 (OAC · 같은 버킷). 정적 트래픽은 Apache 를 거치지 않는다 (Hit 면 엣지, Miss 면 S3)
  origin {
    domain_name              = aws_s3_bucket.static.bucket_regional_domain_name
    origin_id                = local.cf_origin_static
    origin_access_control_id = aws_cloudfront_origin_access_control.s3.id
  }

  origin {
    domain_name              = aws_s3_bucket.static.bucket_regional_domain_name
    origin_id                = local.cf_origin_static_images
    origin_path              = "/static"
    origin_access_control_id = aws_cloudfront_origin_access_control.s3.id
  }

  origin_group {
    origin_id = local.cf_origin_group
    failover_criteria {
      status_codes = [500, 502, 503, 504]
    }
    member {
      origin_id = local.cf_origin_alb
    }
    member {
      origin_id = local.cf_origin_maintenance
    }
  }

  # Behavior 1: 정적 리소스 → ALB(오리진 그룹) · 캐시. AllViewer 로 Host 를 넘겨야 ALB 인증서와 일치(없으면 S3 failover → 403)
  ordered_cache_behavior {
    path_pattern               = "${local.app_context}/resources/*"
    target_origin_id           = local.cf_origin_group
    viewer_protocol_policy     = "redirect-to-https"
    allowed_methods            = ["GET", "HEAD", "OPTIONS"]
    cached_methods             = ["GET", "HEAD"]
    compress                   = true
    cache_policy_id            = data.aws_cloudfront_cache_policy.optimized.id
    origin_request_policy_id   = data.aws_cloudfront_origin_request_policy.all_viewer.id
    response_headers_policy_id = data.aws_cloudfront_response_headers_policy.security.id
  }

  # Behavior 1-c: 랜딩 페이지 자산 /static/* (resources/·images/) → S3 정적 버킷 (OAC). S3 오리진엔 AllViewer 를 붙이면 Host 가 넘어가 서명 불일치 → 캐시 정책만
  ordered_cache_behavior {
    path_pattern               = "/static/*"
    target_origin_id           = local.cf_origin_static
    viewer_protocol_policy     = "redirect-to-https"
    allowed_methods            = ["GET", "HEAD", "OPTIONS"]
    cached_methods             = ["GET", "HEAD"]
    compress                   = true
    cache_policy_id            = data.aws_cloudfront_cache_policy.optimized.id
    response_headers_policy_id = data.aws_cloudfront_response_headers_policy.security.id
  }

  # Behavior 1-d: /images/* — WAS welcome.jsp 의 배경 영상 경로 → 같은 S3 버킷 (origin_path /static → 키 static/images/…)
  ordered_cache_behavior {
    path_pattern               = "/images/*"
    target_origin_id           = local.cf_origin_static_images
    viewer_protocol_policy     = "redirect-to-https"
    allowed_methods            = ["GET", "HEAD", "OPTIONS"]
    cached_methods             = ["GET", "HEAD"]
    compress                   = true
    cache_policy_id            = data.aws_cloudfront_cache_policy.optimized.id
    response_headers_policy_id = data.aws_cloudfront_response_headers_policy.security.id
  }

  # Behavior 1-b: WAR 의 images/* (test 브랜치 WAR 를 올렸을 때 hero.mp4 · 포스터) 도 캐시
  ordered_cache_behavior {
    path_pattern               = "${local.app_context}/images/*"
    target_origin_id           = local.cf_origin_group
    viewer_protocol_policy     = "redirect-to-https"
    allowed_methods            = ["GET", "HEAD", "OPTIONS"]
    cached_methods             = ["GET", "HEAD"]
    compress                   = true
    cache_policy_id            = data.aws_cloudfront_cache_policy.optimized.id
    origin_request_policy_id   = data.aws_cloudfront_origin_request_policy.all_viewer.id
    response_headers_policy_id = data.aws_cloudfront_response_headers_policy.security.id
  }

  # Behavior 2: 점검 페이지 객체 → S3 (custom_error_response 가 참조)
  ordered_cache_behavior {
    path_pattern           = "/maintenance.html"
    target_origin_id       = local.cf_origin_maintenance
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    cache_policy_id        = data.aws_cloudfront_cache_policy.optimized.id
  }

  # Behavior 3 (기본): 동적 → ALB 직접 · 캐시 없음 (POST 허용 → 오리진 그룹 불가, 점검 페이지는 custom_error_response 로)
  default_cache_behavior {
    target_origin_id           = local.cf_origin_alb
    viewer_protocol_policy     = "redirect-to-https"
    allowed_methods            = ["GET", "HEAD", "OPTIONS", "PUT", "POST", "PATCH", "DELETE"]
    cached_methods             = ["GET", "HEAD"]
    cache_policy_id            = data.aws_cloudfront_cache_policy.disabled.id
    origin_request_policy_id   = data.aws_cloudfront_origin_request_policy.all_viewer.id
    response_headers_policy_id = data.aws_cloudfront_response_headers_policy.security.id
  }

  # ALB·WEB·WAS 전부 실패(5xx) 시 점검 페이지
  dynamic "custom_error_response" {
    for_each = [502, 503, 504]
    content {
      error_code            = custom_error_response.value
      response_code         = 503
      response_page_path    = "/maintenance.html"
      error_caching_min_ttl = 10
    }
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    acm_certificate_arn      = aws_acm_certificate_validation.cloudfront.certificate_arn
    ssl_support_method       = "sni-only"
    minimum_protocol_version = "TLSv1.2_2021"
  }

  tags = merge(local.tier_tag.edge, { Name = "${local.p}-cloudfront" })
}

resource "aws_route53_record" "app" {
  for_each = toset(["A", "AAAA"])
  zone_id  = aws_route53_zone.main.zone_id
  name     = var.domain_name
  type     = each.value

  alias {
    name                   = aws_cloudfront_distribution.main.domain_name
    zone_id                = aws_cloudfront_distribution.main.hosted_zone_id
    evaluate_target_health = false
  }
}
