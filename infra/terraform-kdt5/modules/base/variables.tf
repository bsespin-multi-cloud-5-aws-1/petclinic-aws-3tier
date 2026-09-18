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

# ---- 운영자 접속: Bastion + SSH 키 (SSM Session Manager 대신) ----
variable "create_bastion" {
  type    = bool
  default = true
}
variable "bastion_allowed_cidrs" {
  description = "Bastion 22 를 허용할 CIDR (운영자 공인 IP /32)"
  type        = list(string)
  default     = []
}
variable "bastion_instance_type" {
  type    = string
  default = "t3.micro"
}
variable "ssh_key_name" {
  description = "기존 키 페어 이름. 비면 tls_private_key 로 mc-ssh 를 만든다 (Bastion · WEB · WAS 공통)"
  type        = string
  default     = ""
}
variable "enable_ssm" {
  description = "false: AmazonSSMManagedInstanceCore 를 떼어 Session Manager 접속 불가 (Bastion 만)"
  type        = bool
  default     = false
}

# ---- VPC 엔드포인트 · EBS 키 (9/18 Q&A · 기본은 지금 구성 그대로) ----
variable "enable_vpc_endpoints" {
  description = "secretsmanager · logs · ssm 인터페이스 + S3 게이트웨이 엔드포인트. 공용망 미경유 요구가 있을 때만 (≈$48/월)"
  type        = bool
  default     = false
}
variable "vpc_endpoint_services" {
  description = "인터페이스 엔드포인트 서비스 목록 (monitoring · ec2messages 등 추가 가능)"
  type        = list(string)
  default     = ["secretsmanager", "logs", "ssm"]
}
variable "ebs_kms_key_arn" {
  description = "EBS 루트 볼륨 고객 관리형 키 ARN. 비면 계정 기본 키(aws/ebs). 기존 인스턴스에 바꾸면 볼륨 교체(replace) — 신규 구축·ASG 새로 고침 때만"
  type        = string
  default     = ""
}

variable "cwagent_param_prefix" {
  description = "CloudWatch Agent 설정 SSM 파라미터 접두사 (루트 observability.tf 가 /mc/cwagent/web|was 생성)"
  type        = string
}
