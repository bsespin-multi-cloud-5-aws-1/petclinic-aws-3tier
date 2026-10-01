terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.70"
    }
  }
}

# aws login 세션은 프로바이더가 직접 못 읽음 → 프로파일에 credential_process 를 두거나 AWS_PROFILE 로 export-credentials 사용
provider "aws" {
  region  = var.region
  profile = var.aws_profile
  default_tags {
    tags = local.common_tags
  }
}
