# ---------- Bastion (팀 결정 9/16 저녁: SSM Session Manager 대신 SSH 키 + Bastion) ----------
# 퍼블릭 서브넷 A · EIP · SG 22 ← bastion_allowed_cidrs(운영자 공인 IP) 만. WEB·WAS 22 ← Bastion SG, RDS Proxy 3306 ← Bastion SG(루트 access.tf)
# 키 페어: ssh_key_name 이 비면 tls 로 ED25519 키를 만들고(개인키는 루트 .keys/mc-ssh.pem 에 저장) Bastion·WEB·WAS 에 같은 키를 부착
resource "tls_private_key" "ssh" {
  count     = var.create_bastion && var.ssh_key_name == "" ? 1 : 0
  algorithm = "ED25519"
}

resource "aws_key_pair" "ssh" {
  count      = var.create_bastion && var.ssh_key_name == "" ? 1 : 0
  key_name   = "${local.p}-ssh"
  public_key = tls_private_key.ssh[0].public_key_openssh
  tags       = merge(var.tier_tag.ops, { Name = "${local.p}-ssh" })
}

locals {
  ssh_key_name = var.create_bastion ? (var.ssh_key_name != "" ? var.ssh_key_name : aws_key_pair.ssh[0].key_name) : null
}

resource "aws_security_group" "bastion" {
  count       = var.create_bastion ? 1 : 0
  name        = "${local.p}-sg-bastion"
  description = "Bastion: 22 from operator CIDRs only"
  vpc_id      = aws_vpc.main.id
  tags        = merge(var.tier_tag.ops, { Name = "${local.p}-sg-bastion" })
}

resource "aws_vpc_security_group_ingress_rule" "bastion_22" {
  for_each          = var.create_bastion ? toset(var.bastion_allowed_cidrs) : toset([])
  security_group_id = aws_security_group.bastion[0].id
  cidr_ipv4         = each.value
  from_port         = 22
  to_port           = 22
  ip_protocol       = "tcp"
  description       = "SSH from operator"
}

resource "aws_vpc_security_group_egress_rule" "bastion_all" {
  count             = var.create_bastion ? 1 : 0
  security_group_id = aws_security_group.bastion[0].id
  ip_protocol       = "-1"
  cidr_ipv4         = "0.0.0.0/0"
}

# WEB · WAS 22 ← Bastion 만 (인터넷에서 직접 22 는 여전히 없음)
resource "aws_vpc_security_group_ingress_rule" "web_22_bastion" {
  count                        = var.create_bastion ? 1 : 0
  security_group_id            = aws_security_group.web.id
  referenced_security_group_id = aws_security_group.bastion[0].id
  from_port                    = 22
  to_port                      = 22
  ip_protocol                  = "tcp"
  description                  = "SSH from Bastion"
}

resource "aws_vpc_security_group_ingress_rule" "was_22_bastion" {
  count                        = var.create_bastion ? 1 : 0
  security_group_id            = aws_security_group.was.id
  referenced_security_group_id = aws_security_group.bastion[0].id
  from_port                    = 22
  to_port                      = 22
  ip_protocol                  = "tcp"
  description                  = "SSH from Bastion"
}

resource "aws_eip" "bastion" {
  count  = var.create_bastion ? 1 : 0
  domain = "vpc"
  tags   = merge(var.tier_tag.ops, { Name = "${local.p}-bastion" })
}

resource "aws_instance" "bastion" {
  count                       = var.create_bastion ? 1 : 0
  ami                         = data.aws_ssm_parameter.al2023.value
  instance_type               = var.bastion_instance_type
  subnet_id                   = aws_subnet.public[0].id
  vpc_security_group_ids      = [aws_security_group.bastion[0].id]
  iam_instance_profile        = aws_iam_instance_profile.ec2.name # CW Agent 설정 조회 · (관리자) 비밀 조회
  key_name                    = local.ssh_key_name
  associate_public_ip_address = true

  metadata_options {
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
  }

  root_block_device {
    volume_type = "gp3"
    volume_size = 8
    encrypted   = true
    kms_key_id  = var.ebs_kms_key_arn != "" ? var.ebs_kms_key_arn : null
  }

  user_data = templatefile("${path.module}/user_data/bastion.sh", {
    cwagent_param = "${var.cwagent_param_prefix}/bastion"
  })
  user_data_replace_on_change = true

  tags = merge(var.tier_tag.ops, { Name = "${local.p}-bastion" })
}

resource "aws_eip_association" "bastion" {
  count         = var.create_bastion ? 1 : 0
  instance_id   = aws_instance.bastion[0].id
  allocation_id = aws_eip.bastion[0].id
}
