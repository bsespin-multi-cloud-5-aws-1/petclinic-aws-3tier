output "vpc_id" { value = aws_vpc.main.id }
output "public_subnet_ids" { value = aws_subnet.public[*].id }
output "db_subnet_ids" { value = aws_subnet.db[*].id }
output "db_subnet_group_name" { value = aws_db_subnet_group.main.name }

output "public_alb_arn" { value = aws_lb.public.arn }
output "public_alb_dns" { value = aws_lb.public.dns_name }
output "public_alb_arn_suffix" { value = aws_lb.public.arn_suffix }
output "internal_alb_arn_suffix" { value = aws_lb.internal.arn_suffix }
output "tg_web_arn" { value = aws_lb_target_group.web.arn }
output "tg_was_arn_suffix" { value = aws_lb_target_group.was.arn_suffix }

output "sg_alb_public_id" { value = aws_security_group.alb_public.id }
output "sg_was_id" { value = aws_security_group.was.id }
output "sg_db_id" { value = aws_security_group.rds.id }

output "ec2_role_id" { value = aws_iam_role.ec2.id }
output "web_instance_ids" { value = aws_instance.web[*].id } # enable_asg 면 []
output "was_instance_ids" { value = aws_instance.was[*].id }
output "sg_bastion_id" { value = try(aws_security_group.bastion[0].id, null) }
output "bastion_public_ip" { value = try(aws_eip.bastion[0].public_ip, null) }
output "bastion_private_ip" { value = try(aws_instance.bastion[0].private_ip, null) }
output "ssh_key_name" { value = local.ssh_key_name }
output "ssh_private_key_pem" {
  value     = try(tls_private_key.ssh[0].private_key_openssh, null)
  sensitive = true
}
output "web_asg_name" { value = try(aws_autoscaling_group.web[0].name, null) }
output "was_asg_name" { value = try(aws_autoscaling_group.was[0].name, null) }
