# ---------- 계정(리전) 수준 설정 (옵션 · 9/18) ----------
# EBS 기본 암호화: 켜면 이 리전에서 새로 만드는 모든 볼륨·스냅샷이 자동 암호화 (기존 볼륨은 영향 없음). 콘솔: EC2 → 설정 → EBS 암호화
resource "aws_ebs_encryption_by_default" "main" {
  count   = var.enable_ebs_default_encryption ? 1 : 0
  enabled = true
}

resource "aws_ebs_default_kms_key" "main" {
  count   = var.enable_ebs_default_encryption && var.base.ebs_kms_key_arn == "mc-cmk" ? 1 : 0
  key_arn = aws_kms_key.main.arn
}
