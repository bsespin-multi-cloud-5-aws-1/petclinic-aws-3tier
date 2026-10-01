# ---------- AMI: 골든 AMI가 없으면 AL2023 최신 (SSM 공개 파라미터) ----------
data "aws_ssm_parameter" "al2023" {
  name = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"
}

locals {
  web_ami = var.web_ami_id != "" ? var.web_ami_id : data.aws_ssm_parameter.al2023.value
  was_ami = var.was_ami_id != "" ? var.was_ami_id : data.aws_ssm_parameter.al2023.value
}

# ---------- 시작 템플릿 ----------
resource "aws_launch_template" "web" {
  name          = "${local.p}-lt-web"
  image_id      = local.web_ami
  instance_type = var.web_instance_type

  iam_instance_profile {
    name = aws_iam_instance_profile.ec2.name
  }

  vpc_security_group_ids = [aws_security_group.web.id]

  metadata_options {
    http_tokens                 = "required" # IMDSv2
    http_put_response_hop_limit = 1
  }

  user_data = base64encode(templatefile("${path.module}/user_data/web.sh", {
    internal_alb_dns = aws_lb.internal.dns_name
    app_context      = local.app_context
    log_group_prefix = "/petclinic/web"
  }))

  tag_specifications {
    resource_type = "instance"
    tags          = merge(local.common_tags, local.tier_tag.web, { Name = "${local.p}-web" })
  }
  tag_specifications {
    resource_type = "volume"
    tags          = merge(local.common_tags, local.tier_tag.web, { Name = "${local.p}-web" })
  }

  tags = merge(local.tier_tag.web, { Name = "${local.p}-lt-web" })
}

resource "aws_launch_template" "was" {
  name          = "${local.p}-lt-was"
  image_id      = local.was_ami
  instance_type = var.was_instance_type

  iam_instance_profile {
    name = aws_iam_instance_profile.ec2.name
  }

  vpc_security_group_ids = [aws_security_group.was.id]

  metadata_options {
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
  }

  user_data = base64encode(templatefile("${path.module}/user_data/was.sh", {
    rds_proxy_endpoint = aws_db_proxy.main.endpoint
    db_name            = var.db_name
    repo_url           = var.app_repo_url
    repo_branch        = var.app_repo_branch
    db_secret_arn      = aws_db_instance.main.master_user_secret[0].secret_arn
    region             = var.region
    logs_bucket        = aws_s3_bucket.logs.bucket
    log_group_prefix   = "/petclinic/was"
  }))

  tag_specifications {
    resource_type = "instance"
    tags          = merge(local.common_tags, local.tier_tag.was, { Name = "${local.p}-was" })
  }
  tag_specifications {
    resource_type = "volume"
    tags          = merge(local.common_tags, local.tier_tag.was, { Name = "${local.p}-was" })
  }

  tags = merge(local.tier_tag.was, { Name = "${local.p}-lt-was" })
}

# ---------- ASG — WEB (min 2 · max 6 · CPU 60%) ----------
resource "aws_autoscaling_group" "web" {
  name                      = "${local.p}-asg-web"
  min_size                  = var.web_asg.min
  max_size                  = var.web_asg.max
  desired_capacity          = var.web_asg.desired
  vpc_zone_identifier       = aws_subnet.web[*].id
  target_group_arns         = [aws_lb_target_group.web.arn]
  health_check_type         = "ELB"
  health_check_grace_period = 300
  default_instance_warmup   = 180

  launch_template {
    id      = aws_launch_template.web.id
    version = "$Latest"
  }

  instance_refresh {
    strategy = "Rolling"
    preferences {
      min_healthy_percentage = 50
    }
  }

  dynamic "tag" {
    for_each = merge(local.common_tags, local.tier_tag.web, { Name = "${local.p}-web" })
    content {
      key                 = tag.key
      value               = tag.value
      propagate_at_launch = true
    }
  }
}

resource "aws_autoscaling_policy" "web_cpu" {
  name                   = "${local.p}-web-cpu-target"
  autoscaling_group_name = aws_autoscaling_group.web.name
  policy_type            = "TargetTrackingScaling"

  target_tracking_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ASGAverageCPUUtilization"
    }
    target_value = var.web_asg.cpu_target
  }
}

# ---------- ASG — WAS (min 2 · max 8 · 대상당 요청 수 + CPU · 예약 증설 · 종료 훅) ----------
resource "aws_autoscaling_group" "was" {
  name                      = "${local.p}-asg-was"
  min_size                  = var.was_asg.min
  max_size                  = var.was_asg.max
  desired_capacity          = var.was_asg.desired
  vpc_zone_identifier       = aws_subnet.was[*].id
  target_group_arns         = [aws_lb_target_group.was.arn]
  health_check_type         = "ELB"
  health_check_grace_period = 300
  default_instance_warmup   = 300

  launch_template {
    id      = aws_launch_template.was.id
    version = "$Latest"
  }

  instance_refresh {
    strategy = "Rolling"
    preferences {
      min_healthy_percentage = 50
    }
  }

  # 종료 직전 마지막 로그를 S3로 sync할 시간 (user_data의 훅 처리와 짝)
  initial_lifecycle_hook {
    name                 = "${local.p}-was-terminating"
    lifecycle_transition = "autoscaling:EC2_INSTANCE_TERMINATING"
    heartbeat_timeout    = 300
    default_result       = "CONTINUE"
  }

  dynamic "tag" {
    for_each = merge(local.common_tags, local.tier_tag.was, { Name = "${local.p}-was" })
    content {
      key                 = tag.key
      value               = tag.value
      propagate_at_launch = true
    }
  }
}

resource "aws_autoscaling_policy" "was_req" {
  name                   = "${local.p}-was-req-per-target"
  autoscaling_group_name = aws_autoscaling_group.was.name
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
  name                   = "${local.p}-was-cpu-target"
  autoscaling_group_name = aws_autoscaling_group.was.name
  policy_type            = "TargetTrackingScaling"

  target_tracking_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ASGAverageCPUUtilization"
    }
    target_value = var.was_asg.cpu_target
  }
}

# 예약 증설: 이벤트(영상 공개) 전에 desired 올리고, 지나면 되돌림
resource "aws_autoscaling_schedule" "was_scale_out" {
  count                  = var.was_scheduled_scale.enabled ? 1 : 0
  scheduled_action_name  = "${local.p}-was-pre-event"
  autoscaling_group_name = aws_autoscaling_group.was.name
  min_size               = var.was_asg.min
  max_size               = var.was_asg.max
  desired_capacity       = var.was_scheduled_scale.desired
  recurrence             = var.was_scheduled_scale.start_cron
  time_zone              = "Etc/UTC"
}

resource "aws_autoscaling_schedule" "was_scale_in" {
  count                  = var.was_scheduled_scale.enabled ? 1 : 0
  scheduled_action_name  = "${local.p}-was-post-event"
  autoscaling_group_name = aws_autoscaling_group.was.name
  min_size               = var.was_asg.min
  max_size               = var.was_asg.max
  desired_capacity       = var.was_asg.desired
  recurrence             = var.was_scheduled_scale.end_cron
  time_zone              = "Etc/UTC"
}
