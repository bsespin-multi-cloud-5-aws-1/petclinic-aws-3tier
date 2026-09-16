# ---------- WEB ×2 (Apache) · WAS ×2 (Tomcat) — AL2023 · IMDSv2 · 퍼블릭 IP 없음 · SSM ----------
# enable_asg=false(기본): 고정 EC2 2대(aws_instance). enable_asg=true: 같은 user_data 를 시작 템플릿에 담아 ASG 가 띄움(고정 EC2 0대)
# AMI: web_ami_id/was_ami_id 가 비면 AL2023 최신(부팅 시 전부 설치). 구운 AMI(Golden)면 was.sh 가 Tomcat·소스 다운로드를 건너뜀
# (Notion 'AMI & Auto Scaling': 시작 템플릿 $Latest + 인스턴스 새로 고침 · 'was': DB 초기화는 db_init_mode 로)
locals {
  web_user_data = templatefile("${path.module}/user_data/web.sh", {
    internal_alb_dns = aws_lb.internal.dns_name
    app_context      = var.app_context
    region           = var.region
    cwagent_param    = "${var.cwagent_param_prefix}/web"
    repo_url         = var.app_repo_url
    repo_branch      = var.app_repo_branch
    index_branch     = var.web_index_branch
  })
  # jdbc_host = RDS Proxy 엔드포인트(루트) → Proxy 가 생긴 뒤에 WAS 가 만들어짐
  was_user_data = templatefile("${path.module}/user_data/was.sh", {
    region         = var.region
    db_secret_arn  = var.db_secret_arn
    app_secret_arn = var.app_db_secret_arn
    jdbc_host      = var.jdbc_host
    db_name        = var.db_name
    repo_url       = var.app_repo_url
    repo_branch    = var.app_repo_branch
    tomcat_version = var.tomcat_version
    app_context    = var.app_context
    cwagent_param  = "${var.cwagent_param_prefix}/was"
    baked          = var.was_ami_id != ""
    db_init_mode   = var.db_init_mode
    enable_asg     = var.enable_asg
    logs_bucket    = var.access_logs_bucket
    asg_name       = local.was_asg_name
    asg_hook_name  = local.was_hook_name
  })
}

# ---------- 고정 EC2 (enable_asg=false) ----------
resource "aws_instance" "web" {
  count                       = local.ec2_count
  ami                         = local.web_ami
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

  user_data                   = local.web_user_data
  user_data_replace_on_change = true

  tags = merge(var.tier_tag.web, { Name = "${local.p}-web-${substr(var.azs[count.index], -1, 1)}" })
}

resource "aws_instance" "was" {
  count                       = local.ec2_count
  ami                         = local.was_ami
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

  user_data                   = local.was_user_data
  user_data_replace_on_change = true

  tags = merge(var.tier_tag.was, { AppSecretVersion = var.app_db_secret_ready }, { Name = "${local.p}-was-${substr(var.azs[count.index], -1, 1)}" })
}

# ---------- ASG (enable_asg=true): 시작 템플릿 $Latest → 템플릿을 고치면 인스턴스 새로 고침(Rolling · 50% 유지)이 교체 ----------
resource "aws_launch_template" "web" {
  count                  = local.asg_count
  name                   = "${local.p}-lt-web"
  image_id               = local.web_ami
  instance_type          = var.web_instance_type
  update_default_version = true
  vpc_security_group_ids = [aws_security_group.web.id]
  user_data              = base64encode(local.web_user_data)

  iam_instance_profile {
    name = aws_iam_instance_profile.ec2.name
  }
  metadata_options {
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
  }
  block_device_mappings {
    device_name = "/dev/xvda"
    ebs {
      volume_type = "gp3"
      volume_size = 20
      encrypted   = true
    }
  }
  tag_specifications {
    resource_type = "instance"
    tags          = merge(var.tier_tag.web, { Name = "${local.p}-web" })
  }
  tag_specifications {
    resource_type = "volume"
    tags          = merge(var.tier_tag.web, { Name = "${local.p}-web" })
  }

  tags = merge(var.tier_tag.web, { Name = "${local.p}-lt-web" })
}

resource "aws_launch_template" "was" {
  count                  = local.asg_count
  name                   = "${local.p}-lt-was"
  image_id               = local.was_ami
  instance_type          = var.was_instance_type
  update_default_version = true
  vpc_security_group_ids = [aws_security_group.was.id]
  user_data              = base64encode(local.was_user_data)

  iam_instance_profile {
    name = aws_iam_instance_profile.ec2.name
  }
  metadata_options {
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
  }
  block_device_mappings {
    device_name = "/dev/xvda"
    ebs {
      volume_type = "gp3"
      volume_size = 20
      encrypted   = true
    }
  }
  tag_specifications {
    resource_type = "instance"
    tags          = merge(var.tier_tag.was, { Name = "${local.p}-was", AppSecretVersion = var.app_db_secret_ready })
  }
  tag_specifications {
    resource_type = "volume"
    tags          = merge(var.tier_tag.was, { Name = "${local.p}-was" })
  }

  tags = merge(var.tier_tag.was, { Name = "${local.p}-lt-was" })
}

resource "aws_autoscaling_group" "web" {
  count                     = local.asg_count
  name                      = "${local.p}-asg-web"
  min_size                  = var.web_asg.min
  max_size                  = var.web_asg.max
  desired_capacity          = var.web_asg.desired
  vpc_zone_identifier       = aws_subnet.web[*].id
  target_group_arns         = [aws_lb_target_group.web.arn]
  health_check_type         = "ELB"
  health_check_grace_period = 300 # Apache 설치 + index.html 복사 ≈ 1~2분
  default_instance_warmup   = 180

  launch_template {
    id      = aws_launch_template.web[0].id
    version = "$Latest"
  }

  instance_refresh {
    strategy = "Rolling"
    preferences {
      min_healthy_percentage = 50
    }
  }

  dynamic "tag" {
    for_each = merge(var.tier_tag.web, { Name = "${local.p}-web" })
    content {
      key                 = tag.key
      value               = tag.value
      propagate_at_launch = true
    }
  }

  lifecycle {
    ignore_changes = [desired_capacity] # 대상 추적이 바꾼 수를 apply 가 되돌리지 않게
  }
}

resource "aws_autoscaling_group" "was" {
  count                     = local.asg_count
  name                      = local.was_asg_name
  min_size                  = var.was_asg.min
  max_size                  = var.was_asg.max
  desired_capacity          = var.was_asg.desired
  vpc_zone_identifier       = aws_subnet.was[*].id
  target_group_arns         = [aws_lb_target_group.was.arn]
  health_check_type         = "ELB"
  health_check_grace_period = var.was_ami_id != "" ? 300 : 900 # 스톡 AMI 는 Tomcat 다운로드 + Maven 빌드 + Proxy 로그인 대기 ≈ 5~8분
  default_instance_warmup   = 300

  launch_template {
    id      = aws_launch_template.was[0].id
    version = "$Latest"
  }

  instance_refresh {
    strategy = "Rolling"
    preferences {
      min_healthy_percentage = 50
    }
  }

  # 종료 직전 마지막 로그를 S3 로 sync 할 시간 — was.sh 의 mc-lifecycle-watch 가 sync 후 CONTINUE 로 마감
  initial_lifecycle_hook {
    name                 = local.was_hook_name
    lifecycle_transition = "autoscaling:EC2_INSTANCE_TERMINATING"
    heartbeat_timeout    = 300
    default_result       = "CONTINUE"
  }

  dynamic "tag" {
    for_each = merge(var.tier_tag.was, { Name = "${local.p}-was" })
    content {
      key                 = tag.key
      value               = tag.value
      propagate_at_launch = true
    }
  }

  lifecycle {
    ignore_changes = [desired_capacity]
  }
}

resource "aws_autoscaling_policy" "web_cpu" {
  count                  = local.asg_count
  name                   = "${local.p}-web-cpu-target"
  autoscaling_group_name = aws_autoscaling_group.web[0].name
  policy_type            = "TargetTrackingScaling"

  target_tracking_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ASGAverageCPUUtilization"
    }
    target_value = var.web_asg.cpu_target
  }
}

resource "aws_autoscaling_policy" "was_req" {
  count                  = local.asg_count
  name                   = "${local.p}-was-req-per-target"
  autoscaling_group_name = aws_autoscaling_group.was[0].name
  policy_type            = "TargetTrackingScaling"

  target_tracking_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ALBRequestCountPerTarget"
      resource_label         = "${aws_lb.internal.arn_suffix}/${aws_lb_target_group.was.arn_suffix}"
    }
    target_value = var.was_asg.req_per_target
  }
}

resource "aws_autoscaling_policy" "was_cpu" {
  count                  = local.asg_count
  name                   = "${local.p}-was-cpu-target"
  autoscaling_group_name = aws_autoscaling_group.was[0].name
  policy_type            = "TargetTrackingScaling"

  target_tracking_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ASGAverageCPUUtilization"
    }
    target_value = var.was_asg.cpu_target
  }
}
