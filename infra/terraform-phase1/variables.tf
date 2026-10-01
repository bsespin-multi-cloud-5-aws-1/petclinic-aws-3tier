variable "aws_profile" {
  description = "AWS CLI 프로파일 (예: kdt5-tf = credential_process로 kdt5 세션 export)"
  type        = string
  default     = null
}

variable "region" {
  type    = string
  default = "ap-northeast-2"
}

variable "project" {
  type    = string
  default = "petclinic-3tier"
}

variable "team" {
  type    = string
  default = "mc-1"
}

variable "owner" {
  type    = string
  default = "Junseok Pak"
}

variable "env" {
  type    = string
  default = "lab"
}

variable "name_prefix" {
  description = "리소스 이름 접두사. kdt5 콘솔 구축본은 test-* / mc-* 혼용이었음"
  type        = string
  default     = "mc"
}

variable "azs" {
  type    = list(string)
  default = ["ap-northeast-2a", "ap-northeast-2c"]
}

variable "vpc_cidr" {
  type    = string
  default = "10.0.0.0/16"
}

# kdt5 콘솔 구축본과 동일한 CIDR 배치 (public 0/1 · web 10/11 · was 20/21 · db 30/31)
variable "subnet_cidrs" {
  type = object({
    public = list(string)
    web    = list(string)
    was    = list(string)
    db     = list(string)
  })
  default = {
    public = ["10.0.0.0/24", "10.0.1.0/24"]
    web    = ["10.0.10.0/24", "10.0.11.0/24"]
    was    = ["10.0.20.0/24", "10.0.21.0/24"]
    db     = ["10.0.30.0/24", "10.0.31.0/24"]
  }
}

variable "public_alb_ingress_cidrs" {
  description = "Public ALB 80 허용 소스. Blue(Spring4Shell 잔존) 동안은 팀 IP만 권장, 패치 후 0.0.0.0/0"
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

variable "web_instance_type" {
  type    = string
  default = "t3.small"
}

variable "was_instance_type" {
  description = "Maven 빌드 + Tomcat 1GB 힙 → t3.micro(1GB)는 OOM. medium 이상"
  type        = string
  default     = "t3.medium"
}

variable "app_repo_url" {
  type    = string
  default = "https://github.com/bsespin-multi-cloud-5-aws-1/petclinic-aws-3tier.git"
}

variable "app_repo_branch" {
  description = "Blue = main(제공본 그대로, Spring 5.3.9). Green 스테이징 시 test"
  type        = string
  default     = "main"
}

variable "tomcat_version" {
  description = "Blue = 9.0.53(제공본 pom tomcat.version). Green = 9.0.121"
  type        = string
  default     = "9.0.53"
}

variable "db_engine_version" {
  description = "RDS MySQL 8.0은 2026-07-31 표준 지원 종료(Extended Support 과금) → 8.4"
  type        = string
  default     = "8.4.11"
}

variable "db_instance_class" {
  type    = string
  default = "db.t3.small"
}

variable "db_name" {
  type    = string
  default = "petclinic"
}

variable "db_username" {
  type    = string
  default = "admin"
}

variable "db_multi_az" {
  type    = bool
  default = true
}

variable "create_bastion" {
  description = "설계는 SSM Session Manager(공인 IP·22번 불필요). kdt5 초기 구축처럼 Bastion이 필요할 때만 true"
  type        = bool
  default     = false
}

variable "bastion_key_name" {
  type    = string
  default = null
}

variable "bastion_ssh_cidrs" {
  type    = list(string)
  default = []
}
