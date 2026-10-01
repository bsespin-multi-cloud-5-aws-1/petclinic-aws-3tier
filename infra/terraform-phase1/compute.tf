# Phase 1 = AZ당 1대 고정 (ASG·AMI 이미지화는 Phase 2/3). 공인 IP 없음, 키 페어 없음(SSM), IMDSv2 필수.
resource "aws_instance" "web" {
  count                       = 2
  ami                         = data.aws_ssm_parameter.al2023.value
  instance_type               = var.web_instance_type
  subnet_id                   = aws_subnet.web[count.index].id
  vpc_security_group_ids      = [aws_security_group.web.id]
  iam_instance_profile        = aws_iam_instance_profile.ec2.name
  associate_public_ip_address = false
  key_name                    = var.create_bastion ? var.bastion_key_name : null

  metadata_options {
    http_tokens = "required"
  }
  root_block_device {
    volume_size = 20
    volume_type = "gp3"
    encrypted   = true
  }

  user_data = templatefile("${path.module}/user_data/web.sh", {
    internal_alb_dns = aws_lb.internal.dns_name
    app_context      = local.app_context
  })
  user_data_replace_on_change = true

  tags = merge(local.tier.web, { Name = "${local.p}-web-${local.az_suffix[count.index]}" })
}

resource "aws_instance" "was" {
  count                       = 2
  ami                         = data.aws_ssm_parameter.al2023.value
  instance_type               = var.was_instance_type
  subnet_id                   = aws_subnet.was[count.index].id
  vpc_security_group_ids      = [aws_security_group.was.id]
  iam_instance_profile        = aws_iam_instance_profile.ec2.name
  associate_public_ip_address = false
  key_name                    = var.create_bastion ? var.bastion_key_name : null

  metadata_options {
    http_tokens = "required"
  }
  root_block_device {
    volume_size = 20
    volume_type = "gp3"
    encrypted   = true
  }

  user_data = templatefile("${path.module}/user_data/was.sh", {
    region         = var.region
    db_secret_arn  = aws_db_instance.main.master_user_secret[0].secret_arn
    db_endpoint    = aws_db_instance.main.address
    db_name        = var.db_name
    repo_url       = var.app_repo_url
    repo_branch    = var.app_repo_branch
    tomcat_version = var.tomcat_version
    app_context    = local.app_context
  })
  user_data_replace_on_change = true

  tags = merge(local.tier.was, { Name = "${local.p}-was-${local.az_suffix[count.index]}" })

  depends_on = [aws_iam_role_policy.ec2_inline]
}

# Bastion (선택, 기본 생성 안 함)
resource "aws_instance" "bastion" {
  count                       = var.create_bastion ? 1 : 0
  ami                         = data.aws_ssm_parameter.al2023.value
  instance_type               = "t3.micro"
  subnet_id                   = aws_subnet.public[0].id
  vpc_security_group_ids      = [aws_security_group.bastion[0].id]
  associate_public_ip_address = true
  key_name                    = var.bastion_key_name
  metadata_options {
    http_tokens = "required"
  }
  tags = { Name = "${local.p}-bastion" }
}
