# ---------- VPC · 서브넷 8 (public / web / was / db × AZ 2) · IGW · NAT ×2 · 라우팅 ----------
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

resource "aws_subnet" "public" {
  count                   = 2
  vpc_id                  = aws_vpc.main.id
  cidr_block              = var.subnet_cidrs.public[count.index]
  availability_zone       = var.azs[count.index]
  map_public_ip_on_launch = false
  tags                    = merge(var.tier_tag.edge, { Name = "${local.p}-public-${substr(var.azs[count.index], -1, 1)}" })
}

resource "aws_subnet" "web" {
  count             = 2
  vpc_id            = aws_vpc.main.id
  cidr_block        = var.subnet_cidrs.web[count.index]
  availability_zone = var.azs[count.index]
  tags              = merge(var.tier_tag.web, { Name = "${local.p}-web-${substr(var.azs[count.index], -1, 1)}" })
}

resource "aws_subnet" "was" {
  count             = 2
  vpc_id            = aws_vpc.main.id
  cidr_block        = var.subnet_cidrs.was[count.index]
  availability_zone = var.azs[count.index]
  tags              = merge(var.tier_tag.was, { Name = "${local.p}-was-${substr(var.azs[count.index], -1, 1)}" })
}

resource "aws_subnet" "db" {
  count             = 2
  vpc_id            = aws_vpc.main.id
  cidr_block        = var.subnet_cidrs.db[count.index]
  availability_zone = var.azs[count.index]
  tags              = merge(var.tier_tag.db, { Name = "${local.p}-db-${substr(var.azs[count.index], -1, 1)}" })
}

resource "aws_eip" "nat" {
  count  = 2
  domain = "vpc"
  tags   = { Name = "${local.p}-nat-eip-${substr(var.azs[count.index], -1, 1)}" }
}

# AZ 당 NAT 1 — 한 AZ 장애 시 다른 AZ 의 WEB/WAS 아웃바운드(dnf · SSM · Secrets) 유지
resource "aws_nat_gateway" "nat" {
  count         = 2
  allocation_id = aws_eip.nat[count.index].id
  subnet_id     = aws_subnet.public[count.index].id
  tags          = { Name = "${local.p}-nat-${substr(var.azs[count.index], -1, 1)}" }
  depends_on    = [aws_internet_gateway.igw]
}

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
  tags   = { Name = "${local.p}-rt-private-${substr(var.azs[count.index], -1, 1)}" }
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

# DB 서브넷: local 경로만 (인터넷 경로 없음 — 도면 ④)
resource "aws_route_table" "db" {
  vpc_id = aws_vpc.main.id
  tags   = { Name = "${local.p}-rt-db" }
}

resource "aws_route_table_association" "db" {
  count          = 2
  subnet_id      = aws_subnet.db[count.index].id
  route_table_id = aws_route_table.db.id
}

resource "aws_db_subnet_group" "main" {
  name       = "${local.p}-db-subnets"
  subnet_ids = aws_subnet.db[*].id
  tags       = merge(var.tier_tag.db, { Name = "${local.p}-db-subnets" })
}
