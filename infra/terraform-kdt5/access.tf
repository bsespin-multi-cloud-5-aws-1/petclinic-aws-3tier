# ---------- 운영자 접속 (팀 결정 9/16 저녁): Bastion + SSH 키. SSM Session Manager 는 enable_ssm=false 로 끔 ----------
# Bastion 자체(EIP · SG · 인스턴스 · 키 페어)는 modules/base/bastion.tf. 여기는 모듈 밖 리소스와의 연결과 개인키 파일
locals {
  bastion_on = var.create_base && var.base.create_bastion
}

# DB 관리(스키마 확인 · DBeaver 포트 포워딩)는 Bastion → RDS Proxy 3306 (RDS 직접은 여전히 Proxy SG 만)
resource "aws_vpc_security_group_ingress_rule" "rds_proxy_3306_bastion" {
  count                        = local.bastion_on ? 1 : 0
  security_group_id            = aws_security_group.rds_proxy.id
  referenced_security_group_id = module.base[0].sg_bastion_id
  from_port                    = 3306
  to_port                      = 3306
  ip_protocol                  = "tcp"
  description                  = "MySQL from Bastion (admin via Proxy, TLS)"
}

# 생성된 개인키 → .keys/mc-ssh.pem (0600 · gitignore). 기존 키(ssh_key_name)를 쓰면 만들지 않음
resource "local_sensitive_file" "ssh_key" {
  count                = local.bastion_on && var.base.ssh_key_name == "" ? 1 : 0
  content              = module.base[0].ssh_private_key_pem
  filename             = "${path.root}/.keys/${local.p}-ssh.pem"
  file_permission      = "0600"
  directory_permission = "0700"
}
