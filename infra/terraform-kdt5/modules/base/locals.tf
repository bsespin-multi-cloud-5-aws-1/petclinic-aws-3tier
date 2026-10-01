locals {
  p = var.name_prefix
}

data "aws_ssm_parameter" "al2023" {
  name = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"
}

data "aws_partition" "current" {}

locals {
  web_ami       = var.web_ami_id != "" ? var.web_ami_id : data.aws_ssm_parameter.al2023.value
  was_ami       = var.was_ami_id != "" ? var.was_ami_id : data.aws_ssm_parameter.al2023.value
  ec2_count     = var.enable_asg ? 0 : 2
  asg_count     = var.enable_asg ? 1 : 0
  was_asg_name  = "${local.p}-asg-was"
  was_hook_name = "${local.p}-was-terminating"
}
