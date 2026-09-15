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
variable "db_name" { type = string }
variable "jdbc_host" {
  description = "WAS 가 접속할 MySQL 호스트 — 루트가 RDS Proxy 엔드포인트를 넘김 (TLS 필수)"
  type        = string
}

variable "cwagent_param_prefix" {
  description = "CloudWatch Agent 설정 SSM 파라미터 접두사 (루트 observability.tf 가 /mc/cwagent/web|was 생성)"
  type        = string
}
