terraform {
  required_version = ">= 1.6" # import 블록(기존 RDS 를 코드로 편입) 사용

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.70"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
  # 원격 상태(S3 + DynamoDB 잠금)는 팀 결정 후 활성화
}

# `aws login` 세션은 프로바이더가 직접 못 읽음 → ~/.aws/config 에 credential_process 프로필(kdt5-tf) 을 두고 그 이름을 aws_profile 로 지정 (README)
provider "aws" {
  region  = var.region
  profile = var.aws_profile

  default_tags {
    tags = local.common_tags
  }
}

# CloudFront · WAF(CLOUDFRONT 범위) · CloudFront 용 ACM 은 us-east-1 필수
provider "aws" {
  alias   = "us_east_1"
  region  = "us-east-1"
  profile = var.aws_profile

  default_tags {
    tags = local.common_tags
  }
}
