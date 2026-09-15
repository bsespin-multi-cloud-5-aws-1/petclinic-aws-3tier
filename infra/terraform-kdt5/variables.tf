# ---------- 계정 · 공통 ----------
variable "aws_profile" {
  description = "Terraform 이 쓸 AWS CLI 프로필 (credential_process 로 aws login 세션을 넘겨주는 프로필)"
  type        = string
  default     = "kdt5-tf"
}

variable "region" {
  type    = string
  default = "ap-northeast-2"
}

variable "name_prefix" {
  description = "새로 만드는 리소스 이름 접두사 (콘솔 구축본 이름은 existing 변수)"
  type        = string
  default     = "mc"
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
  default = ""
}

variable "env" {
  type    = string
  default = "lab"
}

# ---------- 콘솔로 이미 만든 리소스 (WEB · WAS · VPC · ALB · RDS) — 이름만 받아 data 로 참조, 수정 안 함 ----------
variable "existing" {
  description = "kdt5 계정에 콘솔로 구축된 리소스 이름. 이 코드는 이들을 만들거나 바꾸지 않고 참조만 한다 (RDS 만 import 로 편입)"
  type = object({
    vpc_name = string
    subnet_names = object({
      public = list(string)
      web    = list(string)
      was    = list(string)
      db     = list(string)
    })
    public_alb_name      = string
    internal_alb_name    = string
    tg_web_name          = string
    tg_was_name          = string
    sg_alb_public        = string
    sg_web               = string
    sg_was               = string
    sg_db                = string
    ec2_role_name        = string
    db_identifier        = string
    db_subnet_group_name = string
  })
  default = {
    vpc_name = "test-vpc"
    subnet_names = {
      public = ["test-subnet-public1-ap-northeast-2a", "test-subnet-public2-ap-northeast-2c"]
      web    = ["test-subnet-private1-ap-northeast-2a", "test-subnet-private2-ap-northeast-2c"]
      was    = ["test-subnet-private3-ap-northeast-2a", "test-subnet-private4-ap-northeast-2c"]
      db     = ["test-subnet-private5-ap-northeast-2a", "test-subnet-private6-ap-northeast-2c"]
    }
    public_alb_name      = "test-Public-ALB"
    internal_alb_name    = "alb-internal-test"
    tg_web_name          = "Targetgroup-web"
    tg_was_name          = "tg-internal-alb"
    sg_alb_public        = "alb-public-sg"
    sg_web               = "web-instance-sg"
    sg_was               = "was-instance-sg"
    sg_db                = "petclinic-db-sg"
    ec2_role_name        = "mc-ec2-role"
    db_identifier        = "database-1"
    db_subnet_group_name = "petclinic-db-subnet-group"
  }
}

# ---------- 도메인 · 인증서 (① 진입 계층) ----------
variable "domain_name" {
  description = "서비스 도메인 (예: petclinic.mission-critical.site)"
  type        = string
}

variable "hosted_zone_name" {
  description = "Route 53 호스팅 존 이름 (예: mission-critical.site). apply 후 NS 4개를 가비아에 등록"
  type        = string
}

variable "origin_verify_secret" {
  description = "CloudFront → ALB 검증 헤더 값 (X-Origin-Verify). 32자 이상 임의 문자열"
  type        = string
  sensitive   = true
}

variable "waf_rate_limit_all" {
  description = "WAF rate-based: IP당 5분 요청 상한(전체)"
  type        = number
  default     = 2000
}

variable "waf_rate_limit_booking" {
  description = "WAF rate-based: IP당 5분 요청 상한(예약 경로 /visits/new)"
  type        = number
  default     = 100
}

variable "loadgen_cidrs" {
  description = "JMeter 부하 발생기 IP (WAF allow). 실험 후 비움"
  type        = list(string)
  default     = []
}

# ---------- ④ DB 계층: 콘솔로 만든 database-1 의 현재 값 + 도면대로 보강할 값 ----------
variable "db" {
  description = "database-1 현재 설정(콘솔 확인값 · import 후 plan 차이 0 이 되도록) 과 보강값"
  type = object({
    engine_version        = string
    instance_class        = string
    allocated_storage     = number
    max_allocated_storage = number
    backup_window         = string
    maintenance_window    = string
    # ---- 보강 (도면 ④: PITR · 삭제 방지 · TLS 강제) ----
    backup_retention_days = number
    deletion_protection   = bool
  })
  default = {
    engine_version        = "8.0.44" # 8.0 표준 지원 종료(2026-07-31). 8.4 는 메이저 업그레이드(README)
    instance_class        = "db.t3.small"
    allocated_storage     = 200
    max_allocated_storage = 1000
    backup_window         = "13:45-14:15"
    maintenance_window    = "mon:13:01-mon:13:31"
    backup_retention_days = 7
    deletion_protection   = true
  }
}

# ---------- ⑤ 운영 계층 ----------
variable "alert_emails" {
  description = "SNS mc-alerts 이메일 구독 (기본 알람 경로). Slack 은 Grafana Alerting"
  type        = list(string)
  default     = []
}

variable "enable_grafana" {
  description = "Amazon Managed Grafana 생성 (IAM Identity Center 필요)"
  type        = bool
  default     = false
}

variable "log_retention_days" {
  type    = number
  default = 30
}

variable "was_tomcat_home" {
  description = "CloudWatch Agent 설정(SSM 파라미터)에 넣을 WAS Tomcat 경로. kdt5 WAS-test-a 는 ec2-user 홈에 수동 설치"
  type        = string
  default     = "/home/ec2-user/tomcat"
}
