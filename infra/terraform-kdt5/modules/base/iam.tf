# ---------- EC2 역할: SSM · CloudWatch Agent (비밀 조회 등 인라인은 루트 iam.tf 가 추가) ----------
data "aws_iam_policy_document" "ec2_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "ec2" {
  name               = "${local.p}-ec2-role"
  assume_role_policy = data.aws_iam_policy_document.ec2_assume.json
  tags               = var.tier_tag.ops
}

resource "aws_iam_role_policy_attachment" "ec2_ssm" {
  count      = var.enable_ssm ? 1 : 0 # 팀 결정 9/16: Bastion 사용 → 기본 없음 (SSM 에이전트가 등록 못 함 = Session Manager 불가)
  role       = aws_iam_role.ec2.name
  policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_role_policy_attachment" "ec2_cwagent" {
  role       = aws_iam_role.ec2.name
  policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/CloudWatchAgentServerPolicy"
}

resource "aws_iam_instance_profile" "ec2" {
  name = "${local.p}-ec2-profile"
  role = aws_iam_role.ec2.name
}
