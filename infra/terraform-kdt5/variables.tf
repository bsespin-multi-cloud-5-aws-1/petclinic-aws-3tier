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

# ---------- 모드 전환: kdt5(구축본 참조) vs mc-deploy(기반 계층까지 생성) ----------
variable "create_base" {
  description = <<-EOT
    false = kdt5 모드: VPC·ALB·SG·IAM·WEB·WAS 는 콘솔 구축본을 data 로 읽고 RDS(database-1)는 import.
    true  = mc-deploy 모드(빈 계정): modules/base 가 VPC·SG 체인·IAM·ALB·WEB ×2·WAS ×2 를 만들고 RDS 도 새로 생성. var.existing 은 무시.
  EOT
  type        = bool
  default     = false
}

variable "base" {
  description = "create_base=true 일 때 기반 계층 값"
  type = object({
    azs      = optional(list(string), ["ap-northeast-2a", "ap-northeast-2c"])
    vpc_cidr = optional(string, "10.0.0.0/16")
    subnet_cidrs = optional(object({
      public = list(string)
      web    = list(string)
      was    = list(string)
      db     = list(string)
      }), {
      public = ["10.0.0.0/24", "10.0.1.0/24"]
      web    = ["10.0.10.0/24", "10.0.11.0/24"]
      was    = ["10.0.20.0/24", "10.0.21.0/24"]
      db     = ["10.0.30.0/24", "10.0.31.0/24"]
    })
    web_instance_type    = optional(string, "t3.small")
    was_instance_type    = optional(string, "t3.medium")
    app_repo_url         = optional(string, "https://github.com/bsespin-multi-cloud-5-aws-1/petclinic-aws-3tier.git")
    app_repo_branch      = optional(string, "main") # Blue = main. Phase 2 = test
    tomcat_version       = optional(string, "9.0.53")
    public_http_listener = optional(bool, false) # NS 위임 전 ALB DNS 로 직접 확인할 때만 true
    web_index_branch     = optional(string, "")  # Apache 첫 화면 = 이 브랜치의 src/main/webapp/index.html. 비면 app_repo_branch
    # ---- ASG · AMI (Notion 'AMI & Auto Scaling'·'was' 반영, 기본은 고정 EC2 2대) ----
    enable_asg = optional(bool, false) # true: WEB·WAS 를 시작 템플릿 + ASG 로 (고정 EC2 는 0대). 도면의 회색 'Auto Scaling (로드맵)' 을 켜는 스위치
    web_asg    = optional(object({ min = number, max = number, desired = number, cpu_target = number }), { min = 2, max = 4, desired = 2, cpu_target = 60 })
    was_asg    = optional(object({ min = number, max = number, desired = number, cpu_target = number, req_per_target = number }), { min = 2, max = 4, desired = 2, cpu_target = 60, req_per_target = 300 })
    web_ami_id = optional(string, "") # 구운 AMI(Golden). 비면 AL2023 최신 + 부팅 시 전부 설치
    was_ami_id = optional(string, "") # 구운 AMI 면 was.sh 가 Tomcat 다운로드·git clone 을 건너뛰고 WAR 만 다시 빌드
    # DB 스키마 초기화 주체. app = Spring jdbc:initialize-database(현재 · schema IF NOT EXISTS + INSERT IGNORE 라 멱등)
    # userdata = was.sh 가 GET_LOCK 으로 직렬화해 1회 실행하고 Spring 초기화는 끔(-Djdbc.initLocation) — ASG 동시 부팅용(Notion 'was' 2안)
    db_init_mode = optional(string, "app")
    # ---- 운영자 접속 (팀 결정 9/16 저녁: Bastion + SSH 키 · SSM Session Manager 는 안 씀 → enable_ssm=false) ----
    create_bastion        = optional(bool, true)
    bastion_allowed_cidrs = optional(list(string), []) # SSH 22 를 허용할 운영자 공인 IP(/32). 비면 아무도 못 들어감
    bastion_instance_type = optional(string, "t3.micro")
    ssh_key_name          = optional(string, "") # 기존 키 페어 이름. 비면 mc-ssh 키 페어를 만들고 개인키를 .keys/mc-ssh.pem 에 저장(gitignore)
  })
  default = {}
  validation {
    condition     = contains(["app", "userdata"], var.base.db_init_mode)
    error_message = "base.db_init_mode 는 app 또는 userdata"
  }
}

# ---------- 콘솔로 이미 만든 리소스 (WEB · WAS · VPC · ALB · RDS) — create_base=false 일 때만 사용 ----------
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

variable "enable_waf" {
  description = "CloudFront 에 WAF Web ACL 부착(allow-loadgen → 관리형 3 → rate-all → rate-booking · 로그 → CloudWatch Logs aws-waf-logs-mc). 9/16 멘토링에서 '관리 어려움' 의견이 있었으나 팀 결정으로 유지(true). 끄면 Web ACL·IP set·로그 그룹이 삭제되고 CloudFront 는 Shield Standard 만 남음"
  type        = bool
  default     = true
}

variable "enable_ssm" {
  description = "SSM Session Manager(세션 설정 문서 · /mc/ssm/sessions · AmazonSSMManagedInstanceCore). 팀 결정 9/16: Bastion 을 쓰므로 기본 false. Parameter Store(CW Agent 설정)는 이 값과 무관"
  type        = bool
  default     = false
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

# ---------- ④ DB 계층 ----------
# kdt5 모드: database-1 의 콘솔 확인값(import 후 plan 차이 0) + 보강값. mc-deploy 모드: 새 RDS 사양 (tfvars 예시 참고)
variable "db" {
  type = object({
    engine_version        = optional(string, "8.0.44") # kdt5 database-1. 새로 만들 땐 8.4.x (8.0 표준 지원 종료 2026-07-31)
    instance_class        = optional(string, "db.t3.small")
    allocated_storage     = optional(number, 200)
    max_allocated_storage = optional(number, 1000)
    multi_az              = optional(bool, true)
    backup_window         = optional(string, "13:45-14:15")
    maintenance_window    = optional(string, "mon:13:01-mon:13:31")
    ca_cert_identifier    = optional(string) # kdt5 = rds-ca-rsa2048-g1. null 이면 리전 기본값
    # ---- 도면 ④ 보강: PITR · 삭제 방지 · TLS 강제(파라미터 그룹) ----
    backup_retention_days = optional(number, 7)
    deletion_protection   = optional(bool, true)
    skip_final_snapshot   = optional(bool, false)
    apply_immediately     = optional(bool, false) # kdt5: 파라미터 그룹 교체 재부팅을 유지관리 창으로 미룸
  })
  default = {}
}

variable "app_db_username" {
  description = "앱 전용 DB 사용자 이름 (petclinic.* 권한만 · 교체 없는 비밀)"
  type        = string
  default     = "petclinic_app"
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
  description = "CloudWatch Agent 설정(SSM 파라미터)에 넣을 WAS Tomcat 경로. 빈 값이면 kdt5 = /home/ec2-user/tomcat(수동 설치), create_base = /opt/tomcat"
  type        = string
  default     = ""
}
