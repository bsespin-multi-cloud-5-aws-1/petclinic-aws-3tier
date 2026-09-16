terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.70"
    }
    tls = {
      source  = "hashicorp/tls"
      version = "~> 4.0"
    }
  }
}
# 프로바이더 설정은 루트에서 상속 (count 로 호출되는 모듈은 provider 블록을 가질 수 없음)
