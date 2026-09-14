# ---------- 식별 · 태그 ----------
variable "project" {
  description = "Project 태그 값"
  type        = string
  default     = "petclinic-3tier"
}

variable "team" {
  description = "Team 태그 값"
  type        = string
  default     = "mc-1"
}

variable "owner" {
  description = "Owner 태그 값 (담당자 이름)"
  type        = string
}

variable "env" {
  description = "Env 태그 값"
  type        = string
  default     = "lab"
}

variable "name_prefix" {
  description = "리소스 이름 접두사 (mc-<계층>-<az>)"
  type        = string
  default     = "mc"
}

variable "region" {
  description = "기본 리전"
  type        = string
  default     = "ap-northeast-2"
}

variable "azs" {
  description = "사용할 가용영역 2개 (a, c)"
  type        = list(string)
  default     = ["ap-northeast-2a", "ap-northeast-2c"]
}

# ---------- 네트워크 ----------
variable "vpc_cidr" {
  type    = string
  default = "10.0.0.0/16"
}

variable "subnet_cidrs" {
  description = "계층별 서브넷 CIDR (AZ 순서와 동일)"
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

# ---------- 도메인 · 인증서 ----------
variable "domain_name" {
  description = "서비스 도메인 (예: hospital.example.com)"
  type        = string
}

variable "hosted_zone_name" {
  description = "Route 53 호스팅 존 이름 (예: example.com)"
  type        = string
}

# ---------- 컴퓨팅 ----------
variable "web_ami_id" {
  description = "WEB 골든 AMI. 비우면 AL2023 최신 AMI + user_data 부트스트랩(첫 배포용)"
  type        = string
  default     = ""
}

variable "was_ami_id" {
  description = "WAS 골든 AMI. 비우면 AL2023 최신 AMI + user_data 부트스트랩(OpenJDK 8 · Tomcat 9.0.121 · git clone · mvnw 빌드, 기동 5~8분)"
  type        = string
  default     = ""
}

variable "app_repo_url" {
  description = "부트스트랩 모드에서 빌드할 저장소"
  type        = string
  default     = "https://github.com/bsespin-multi-cloud-5-aws-1/petclinic-aws-3tier.git"
}

variable "app_repo_branch" {
  description = "빌드할 브랜치 (Green 스택: OpenJDK 8 · Spring 5.3.39 · Tomcat 9.0.121)"
  type        = string
  default     = "test"
}

variable "web_instance_type" {
  type    = string
  default = "t3.small"
}

variable "was_instance_type" {
  type    = string
  default = "t3.medium"
}

variable "web_asg" {
  type    = object({ min = number, max = number, desired = number, cpu_target = number })
  default = { min = 2, max = 6, desired = 2, cpu_target = 60 }
}

variable "was_asg" {
  type    = object({ min = number, max = number, desired = number, cpu_target = number, req_per_target = number })
  default = { min = 2, max = 8, desired = 2, cpu_target = 60, req_per_target = 300 }
}

variable "was_scheduled_scale" {
  description = "예약 증설: 이벤트 15분 전 desired 4 (cron, UTC). 비우면 생성 안 함"
  type = object({
    enabled    = bool
    desired    = number
    start_cron = string # 예: "45 0 * * *" (KST 09:45)
    end_cron   = string # 예: "0 3 * * *"  (KST 12:00)
  })
  default = { enabled = true, desired = 4, start_cron = "45 0 * * *", end_cron = "0 3 * * *" }
}

# ---------- DB ----------
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

# ---------- 진입 · 보안 ----------
variable "origin_verify_secret" {
  description = "CloudFront → ALB 오리진 검증 헤더 값 (X-Origin-Verify)"
  type        = string
  sensitive   = true
}

variable "waf_rate_limit_all" {
  description = "IP당 5분 요청 상한 (전체)"
  type        = number
  default     = 2000
}

variable "waf_rate_limit_booking" {
  description = "IP당 5분 요청 상한 (예약 경로)"
  type        = number
  default     = 100
}

variable "loadgen_cidrs" {
  description = "JMeter 부하 발생기 공인 IP (WAF 허용). 실험 후 비움"
  type        = list(string)
  default     = []
}

# ---------- 운영 · 알림 ----------
variable "alert_emails" {
  description = "SNS mc-alerts 이메일 구독자"
  type        = list(string)
  default     = []
}

variable "slack_team_id" {
  description = "AWS Chatbot용 Slack 워크스페이스 ID (비우면 Chatbot 생성 안 함)"
  type        = string
  default     = ""
}

variable "slack_alerts_channel_id" {
  description = "#mc-alerts 채널 ID"
  type        = string
  default     = ""
}

variable "enable_grafana" {
  description = "Amazon Managed Grafana 워크스페이스 생성 (IAM Identity Center 필요)"
  type        = bool
  default     = false
}

variable "log_retention_days" {
  type    = number
  default = 30
}
