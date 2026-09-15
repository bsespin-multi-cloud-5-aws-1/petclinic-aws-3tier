# ---------- WEB ×2 (Apache) · WAS ×2 (Tomcat) — AL2023 · IMDSv2 · 퍼블릭 IP 없음 · SSM ----------
resource "aws_instance" "web" {
  count                       = 2
  ami                         = data.aws_ssm_parameter.al2023.value
  instance_type               = var.web_instance_type
  subnet_id                   = aws_subnet.web[count.index].id
  vpc_security_group_ids      = [aws_security_group.web.id]
  iam_instance_profile        = aws_iam_instance_profile.ec2.name
  associate_public_ip_address = false

  metadata_options {
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
  }

  root_block_device {
    volume_type = "gp3"
    volume_size = 20
    encrypted   = true
  }

  user_data = templatefile("${path.module}/user_data/web.sh", {
    internal_alb_dns = aws_lb.internal.dns_name
    app_context      = var.app_context
    region           = var.region
    cwagent_param    = "${var.cwagent_param_prefix}/web"
  })
  user_data_replace_on_change = true

  tags = merge(var.tier_tag.web, { Name = "${local.p}-web-${substr(var.azs[count.index], -1, 1)}" })
}

resource "aws_instance" "was" {
  count                       = 2
  ami                         = data.aws_ssm_parameter.al2023.value
  instance_type               = var.was_instance_type
  subnet_id                   = aws_subnet.was[count.index].id
  vpc_security_group_ids      = [aws_security_group.was.id]
  iam_instance_profile        = aws_iam_instance_profile.ec2.name
  associate_public_ip_address = false

  metadata_options {
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
  }

  root_block_device {
    volume_type = "gp3"
    volume_size = 20
    encrypted   = true
  }

  # jdbc_host = RDS Proxy 엔드포인트(루트) → Proxy 가 생긴 뒤에 WAS 가 만들어짐
  user_data = templatefile("${path.module}/user_data/was.sh", {
    region         = var.region
    db_secret_arn  = var.db_secret_arn
    jdbc_host      = var.jdbc_host
    db_name        = var.db_name
    repo_url       = var.app_repo_url
    repo_branch    = var.app_repo_branch
    tomcat_version = var.tomcat_version
    app_context    = var.app_context
    cwagent_param  = "${var.cwagent_param_prefix}/was"
  })
  user_data_replace_on_change = true

  tags = merge(var.tier_tag.was, { Name = "${local.p}-was-${substr(var.azs[count.index], -1, 1)}" })
}
