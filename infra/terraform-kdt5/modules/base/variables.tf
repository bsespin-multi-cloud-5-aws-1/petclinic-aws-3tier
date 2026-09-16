# 기반 계층 (VPC · SG 체인 · IAM 역할 · Public/Internal ALB · WEB ×2 · WAS ×2 · DB 서브넷 그룹)
# = infra/terraform-phase1 의 리소스를 모듈로 옮긴 것. RDS 인스턴스는 루트가 만든다(import 모드와 코드 공유).
variable "name_prefix" { type = string }
variable "region" { type = string }
variable "azs" { type = list(string) }
variable "vpc_cidr" { type = string }
variable "subnet_cidrs" {
  type = object({ public = list(string), web = list(string), was = list(string), db = list(string) })
}
variable "tier_tag" { type = map(map(string)) }
variable "app_context" { type = string }

variable "web_instance_type" { type = string }
variable "was_instance_type" { type = string }
variable "app_repo_url" { type = string }
variable "app_repo_branch" { type = string }
variable "tomcat_version" { type = string }

variable "web_index_branch" {
  description = "Apache 첫 화면으로 쓸 WAR index.html 을 가져올 브랜치. 비면 app_repo_branch (main 에는 index.html 이 없어 302 폴백)"
  type        = string
  default     = ""
}

variable "public_http_listener" {
  description = "Public ALB 에 80 리스너(HTTP → tg-web)도 만들지. 설계는 CloudFront → 443 만이라 기본 false. NS 위임 전 ALB DNS 로 직접 확인할 때만 true"
  type        = bool
  default     = false
}

variable "access_logs_bucket" {
  description = "ALB 액세스 로그 버킷 이름 (루트 kms_s3.tf 의 로그 버킷 · 정책 적용 후 전달)"
  type        = string
}

variable "db_secret_arn" {
  description = "RDS 관리형 비밀 ARN (WAS 부팅 시 조회)"
  type        = string
}
variable "app_db_secret_arn" {
  description = "앱 전용 DB 사용자 비밀 ARN ({username,password}) — WAS 가 이 계정으로 빌드·접속"
  type        = string
}
variable "app_db_secret_ready" {
  description = "비밀 버전 ID — 값은 안 쓰고 의존성(버전 생성 후 WAS 부팅)만 만든다"
  type        = string
}
variable "db_name" { type = string }
variable "jdbc_host" {
  description = "WAS 가 접속할 MySQL 호스트 — 루트가 RDS Proxy 엔드포인트를 넘김 (TLS 필수)"
  type        = string
}

# ---- ASG · AMI (루트 var.base 에서 전달) ----
variable "enable_asg" {
  description = "true: WEB·WAS 를 시작 템플릿 + ASG 로 (고정 aws_instance 는 0대). false: 고정 EC2 2대"
  type        = bool
  default     = false
}
variable "web_asg" {
  type    = object({ min = number, max = number, desired = number, cpu_target = number })
  default = { min = 2, max = 4, desired = 2, cpu_target = 60 }
}
variable "was_asg" {
  type    = object({ min = number, max = number, desired = number, cpu_target = number, req_per_target = number })
  default = { min = 2, max = 4, desired = 2, cpu_target = 60, req_per_target = 300 }
}
variable "web_ami_id" {
  description = "구운 AMI. 비면 AL2023 최신"
  type        = string
  default     = ""
}
variable "was_ami_id" {
  description = "구운 AMI. 비면 AL2023 최신. 값이 있으면 was.sh 가 Tomcat·소스 다운로드를 건너뜀"
  type        = string
  default     = ""
}
variable "db_init_mode" {
  description = "app = Spring 이 부팅 시 schema/data 실행(멱등) · userdata = was.sh 가 GET_LOCK 직렬화로 1회 실행 후 Spring 초기화 끔"
  type        = string
  default     = "app"
}

variable "cwagent_param_prefix" {
  description = "CloudWatch Agent 설정 SSM 파라미터 접두사 (루트 observability.tf 가 /mc/cwagent/web|was 생성)"
  type        = string
}
