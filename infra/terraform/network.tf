# ---------- VPC ----------
resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags                 = { Name = "${local.p}-vpc" }
}

resource "aws_internet_gateway" "igw" {
  vpc_id = aws_vpc.main.id
  tags   = { Name = "${local.p}-igw" }
}

# ---------- 서브넷 (AZ당 public · web · was · db) ----------
resource "aws_subnet" "public" {
  count                   = 2
  vpc_id                  = aws_vpc.main.id
  cidr_block              = var.subnet_cidrs.public[count.index]
  availability_zone       = var.azs[count.index]
  map_public_ip_on_launch = false
  tags                    = merge(local.tier_tag.edge, { Name = "${local.p}-public-${local.az_suffix[count.index]}" })
}

resource "aws_subnet" "web" {
  count             = 2
  vpc_id            = aws_vpc.main.id
  cidr_block        = var.subnet_cidrs.web[count.index]
  availability_zone = var.azs[count.index]
  tags              = merge(local.tier_tag.web, { Name = "${local.p}-web-${local.az_suffix[count.index]}" })
}

resource "aws_subnet" "was" {
  count             = 2
  vpc_id            = aws_vpc.main.id
  cidr_block        = var.subnet_cidrs.was[count.index]
  availability_zone = var.azs[count.index]
  tags              = merge(local.tier_tag.was, { Name = "${local.p}-was-${local.az_suffix[count.index]}" })
}

resource "aws_subnet" "db" {
  count             = 2
  vpc_id            = aws_vpc.main.id
  cidr_block        = var.subnet_cidrs.db[count.index]
  availability_zone = var.azs[count.index]
  tags              = merge(local.tier_tag.db, { Name = "${local.p}-db-${local.az_suffix[count.index]}" })
}

# ---------- NAT (AZ당 1개 · 아웃바운드 전용: dnf · Agent · SSM · OIDC 토큰 교환) ----------
resource "aws_eip" "nat" {
  count  = 2
  domain = "vpc"
  tags   = { Name = "${local.p}-nat-eip-${local.az_suffix[count.index]}" }
}

resource "aws_nat_gateway" "nat" {
  count         = 2
  allocation_id = aws_eip.nat[count.index].id
  subnet_id     = aws_subnet.public[count.index].id
  tags          = { Name = "${local.p}-nat-${local.az_suffix[count.index]}" }
  depends_on    = [aws_internet_gateway.igw]
}

# ---------- 라우팅 ----------
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id
  tags   = { Name = "${local.p}-rt-public" }
}

resource "aws_route" "public_default" {
  route_table_id         = aws_route_table.public.id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.igw.id
}

resource "aws_route_table_association" "public" {
  count          = 2
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table" "private" {
  count  = 2
  vpc_id = aws_vpc.main.id
  tags   = { Name = "${local.p}-rt-private-${local.az_suffix[count.index]}" }
}

resource "aws_route" "private_default" {
  count                  = 2
  route_table_id         = aws_route_table.private[count.index].id
  destination_cidr_block = "0.0.0.0/0"
  nat_gateway_id         = aws_nat_gateway.nat[count.index].id
}

resource "aws_route_table_association" "web" {
  count          = 2
  subnet_id      = aws_subnet.web[count.index].id
  route_table_id = aws_route_table.private[count.index].id
}

resource "aws_route_table_association" "was" {
  count          = 2
  subnet_id      = aws_subnet.was[count.index].id
  route_table_id = aws_route_table.private[count.index].id
}

# DB 서브넷: 기본 경로 없음 (인터넷 경로 없음)
resource "aws_route_table" "db" {
  vpc_id = aws_vpc.main.id
  tags   = { Name = "${local.p}-rt-db" }
}

resource "aws_route_table_association" "db" {
  count          = 2
  subnet_id      = aws_subnet.db[count.index].id
  route_table_id = aws_route_table.db.id
}
