# ---------- VPC 엔드포인트 (옵션 · enable_vpc_endpoints, 기본 false) — 9/18 Q&A ----------
# 서버가 NAT 로 나가는 AWS API 호출 3종(비밀 조회 · 로그 전송 · Agent 설정)을 공용망을 안 타고 VPC 안에서 끝내는 선택지.
# 넣어도 NAT 는 못 없앤다(dnf · git · Maven · Tomcat 다운로드는 AWS 서비스가 아님) → NAT 제거는 골든 AMI 와 함께 로드맵.
# 비용: 인터페이스 3종 × AZ 2 ≈ $48/월 (NAT 처리 요금은 로그 MB 단위라 미미) → 규제(공용망 미경유)·감사 요구가 있을 때 켠다.
# S3 게이트웨이 엔드포인트는 무료 → 같이 켜면 ASG 종료 훅 로그 sync · 정적 자산 업로드가 NAT 를 안 탄다.
data "aws_region" "current" {}

resource "aws_security_group" "vpce" {
  count       = var.enable_vpc_endpoints ? 1 : 0
  name        = "${local.p}-sg-vpce"
  description = "Interface endpoints: 443 from WEB/WAS/Bastion"
  vpc_id      = aws_vpc.main.id
  tags        = merge(var.tier_tag.ops, { Name = "${local.p}-sg-vpce" })
}

resource "aws_vpc_security_group_ingress_rule" "vpce_443" {
  for_each = var.enable_vpc_endpoints ? merge(
    { web = aws_security_group.web.id, was = aws_security_group.was.id },
    var.create_bastion ? { bastion = aws_security_group.bastion[0].id } : {},
  ) : {}
  security_group_id            = aws_security_group.vpce[0].id
  referenced_security_group_id = each.value
  from_port                    = 443
  to_port                      = 443
  ip_protocol                  = "tcp"
  description                  = "HTTPS from ${each.key}"
}

# 인터페이스 3종: secretsmanager(WAS 부팅 비밀) · logs(CW Agent 로그) · ssm(Parameter Store 설정). monitoring(지표)은 필요 시 목록에 추가
resource "aws_vpc_endpoint" "interface" {
  for_each            = var.enable_vpc_endpoints ? toset(var.vpc_endpoint_services) : toset([])
  vpc_id              = aws_vpc.main.id
  service_name        = "com.amazonaws.${data.aws_region.current.name}.${each.key}"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = aws_subnet.web[*].id # 인터페이스는 AZ 당 서브넷 1개만 → web 서브넷(AZ a/c). WAS·Bastion 도 같은 VPC 사설 DNS 로 도달
  security_group_ids  = [aws_security_group.vpce[0].id]
  private_dns_enabled = true # 코드 변경 없이 기존 엔드포인트 DNS(secretsmanager.ap-northeast-2.amazonaws.com)가 사설 IP 로 풀림
  tags                = merge(var.tier_tag.ops, { Name = "${local.p}-vpce-${each.key}" })
}

# S3 게이트웨이(무료): 프라이빗 라우팅 테이블 2 + DB 라우팅 테이블에 prefix list 경로 추가
resource "aws_vpc_endpoint" "s3" {
  count             = var.enable_vpc_endpoints ? 1 : 0
  vpc_id            = aws_vpc.main.id
  service_name      = "com.amazonaws.${data.aws_region.current.name}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = concat(aws_route_table.private[*].id, [aws_route_table.db.id])
  tags              = merge(var.tier_tag.ops, { Name = "${local.p}-vpce-s3" })
}
