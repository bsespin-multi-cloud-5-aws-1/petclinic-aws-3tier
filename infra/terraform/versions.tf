terraform {
  required_version = ">= 1.6"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.70"
    }
  }

  # 원격 상태는 팀 결정 후 활성화 (S3 + DynamoDB 잠금)
  # backend "s3" {
  #   bucket         = "mc-tfstate"
  #   key            = "petclinic-3tier/terraform.tfstate"
  #   region         = "ap-northeast-2"
  #   dynamodb_table = "mc-tfstate-lock"
  #   encrypt        = true
  # }
}

# `aws login` 세션은 프로바이더가 직접 못 읽으므로 CLI export-credentials 를 credential_process 로 사용
provider "aws" {
  region = var.region

  default_tags {
    tags = local.common_tags
  }
}

# CloudFront · WAF(CLOUDFRONT 범위) · CloudFront용 ACM은 us-east-1 필수
provider "aws" {
  alias  = "us_east_1"
  region = "us-east-1"

  default_tags {
    tags = local.common_tags
  }
}
