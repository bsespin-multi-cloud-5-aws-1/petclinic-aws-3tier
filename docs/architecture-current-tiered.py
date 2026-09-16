"""현재 아키텍처(mc-deploy As-Built · 2026-09-16) 를 '계층별 상세 아키텍처' 양식(번호 배지 + 오른쪽 범례 패널)으로 그린다.
실행: python3 docs/architecture-current-tiered.py [--png] → docs/architecture-current-tiered.drawio / .png
근거: infra/terraform-kdt5 (create_base=true) apply 결과 · aws cli 실측 (인스턴스 ID · RDS AZ · CloudFront 로깅)"""
import html as _html, json, os, subprocess, sys
import xml.etree.ElementTree as ET

PTS = "points=[[0,0,0],[0.25,0,0],[0.5,0,0],[0.75,0,0],[1,0,0],[0,1,0],[0.25,1,0],[0.5,1,0],[0.75,1,0],[1,1,0],[0,0.25,0],[0,0.5,0],[0,0.75,0],[1,0.25,0],[1,0.5,0],[1,0.75,0]]"
GPTS = "points=[[0,0],[0.25,0],[0.5,0],[0.75,0],[1,0],[1,0.25],[1,0.5],[1,0.75],[1,1],[0.75,1],[0.5,1],[0.25,1],[0,1],[0,0.75],[0,0.5],[0,0.25]]"
FONT = "fontFamily=Helvetica;"
CAT = {  # tint, stroke, icon fill
    "net": ("#EDE7F6", "#8C4FFF", "#8C4FFF"), "compute": ("#FFF2E8", "#ED7100", "#ED7100"), "db": ("#F5E6F7", "#C925D1", "#C925D1"),
    "storage": ("#E8F5E9", "#3F8624", "#3F8624"), "integ": ("#FCE4EC", "#E7157B", "#E7157B"), "sec": ("#FFEBEE", "#DD344C", "#DD344C"),
    "gen": ("#F5F5F5", "#666666", "#232F3D"), "opt": ("#FAFAFA", "#9E9E9E", "#9E9E9E"),
}
GROUP_BASE = f"{GPTS};outlineConnect=0;gradientColor=none;html=1;whiteSpace=wrap;fontSize=12;fontStyle=0;shape=mxgraph.aws4.group;"
STY = {
    "cloud": GROUP_BASE + "grIcon=mxgraph.aws4.group_aws_cloud;strokeColor=#232F3E;fillColor=light-dark(#232F3E0D,#232F3E0D);fillStyle=auto;verticalAlign=top;align=left;spacingLeft=30;fontColor=#232F3E;dashed=0;container=0;pointerEvents=0;collapsible=0;recursiveResize=0;fontSize=14;fontStyle=1;" + FONT,
    "region": GROUP_BASE + "grIcon=mxgraph.aws4.group_region;strokeColor=#00A4A6;fillColor=light-dark(#0C7B7D0D,#0C7B7D0D);fillStyle=auto;verticalAlign=top;align=left;spacingLeft=30;fontColor=#00A4A6;dashed=1;container=0;pointerEvents=0;collapsible=0;recursiveResize=0;fontSize=14;fontStyle=1;" + FONT,
    "vpc": GROUP_BASE + "grIcon=mxgraph.aws4.group_vpc2;strokeColor=#8C4FFF;fillColor=light-dark(#8C4FFF0D,#8C4FFF0D);fillStyle=auto;verticalAlign=top;align=left;spacingLeft=30;fontColor=#8C4FFF;dashed=0;container=0;pointerEvents=0;collapsible=0;recursiveResize=0;fontSize=14;fontStyle=1;" + FONT,
    "az": "fillColor=none;strokeColor=#147EBA;dashed=1;verticalAlign=top;fontStyle=1;fontSize=12;fontColor=#147EBA;whiteSpace=wrap;html=1;container=0;pointerEvents=0;collapsible=0;recursiveResize=0;" + FONT,
    "pub": GROUP_BASE + "grIcon=mxgraph.aws4.group_public_subnet;strokeColor=#248814;fillColor=light-dark(#2488140D,#2488140D);fillStyle=auto;verticalAlign=top;align=left;spacingLeft=30;fontColor=#248814;dashed=0;container=0;pointerEvents=0;collapsible=0;recursiveResize=0;" + FONT,
    "priv": GROUP_BASE + "grIcon=mxgraph.aws4.group_private_subnet;strokeColor=#147EBA;fillColor=light-dark(#147EBA0D,#147EBA0D);fillStyle=auto;verticalAlign=top;align=left;spacingLeft=30;fontColor=#147EBA;dashed=0;container=0;pointerEvents=0;collapsible=0;recursiveResize=0;" + FONT,
    "tier": "fillColor=none;strokeColor=#ED7100;dashed=1;dashPattern=8 4;strokeWidth=2;verticalAlign=top;align=left;spacingLeft=10;fontStyle=1;fontSize=12;fontColor=#ED7100;whiteSpace=wrap;html=1;container=0;pointerEvents=0;collapsible=0;recursiveResize=0;" + FONT,
}
EDGE = "edgeStyle=orthogonalEdgeStyle;html=1;endArrow=block;elbow=vertical;startArrow=none;endFill=1;strokeColor=#545B64;rounded=0;strokeWidth=1.5;" + FONT
EDGE_D = "edgeStyle=orthogonalEdgeStyle;html=1;endArrow=open;elbow=vertical;startArrow=none;strokeColor=#545B64;rounded=0;dashed=1;" + FONT
EDGE_LOGCW = EDGE_D + "strokeColor=#E7157B;"      # 분홍 점선: Agent → CloudWatch Logs
EDGE_LOGS3 = EDGE_D + "strokeColor=#1B8B3B;"      # 초록 점선: 서비스 → S3 객체
EDGE_DB = EDGE + "strokeColor=#C925D1;strokeWidth=2;"
EDGE_BI = "edgeStyle=orthogonalEdgeStyle;html=1;endArrow=block;elbow=vertical;startArrow=block;startFill=1;endFill=1;strokeColor=#545B64;rounded=0;" + FONT
EDGE_GHOST = EDGE_D + "strokeColor=#9E9E9E;"

mxfile = ET.Element("mxfile", host="Electron", version="29.6.1")
diagram = ET.SubElement(mxfile, "diagram", name="현재 아키텍처 (As-Built 9/16)", id="cur-1")
model = ET.SubElement(diagram, "mxGraphModel", dx="2400", dy="1600", grid="0", gridSize="10", guides="1", tooltips="1", connect="1", arrows="1", fold="1",
                      page="0", pageScale="1", pageWidth="2900", pageHeight="2200", math="0", shadow="0")
root = ET.SubElement(model, "root")
ET.SubElement(root, "mxCell", id="0"); ET.SubElement(root, "mxCell", id="1", parent="0")

def vertex(cid, value, style, x, y, w, h, parent="1"):
    c = ET.SubElement(root, "mxCell", id=cid, value=value, style=style, vertex="1", parent=parent)
    ET.SubElement(c, "mxGeometry", x=str(x), y=str(y), width=str(w), height=str(h)).set("as", "geometry")
    return c

def text(cid, value, x, y, w, h, color="#232F3E", size=14, bold=True, align="left", parent="1"):
    return vertex(cid, value, f"text;html=1;whiteSpace=wrap;strokeColor=none;fillColor=none;align={align};verticalAlign=middle;fontSize={size};fontStyle={1 if bold else 0};fontColor={color};{FONT}", x, y, w, h, parent)

def icon_style(res, fill, kind="svc", size=10):
    if kind == "svc":
        return (f"sketch=0;{PTS};outlineConnect=0;fontColor=#232F3E;fillColor={fill};strokeColor=#ffffff;dashed=0;verticalLabelPosition=bottom;verticalAlign=top;align=center;html=1;"
                f"fontSize={size};fontStyle=0;aspect=fixed;shape=mxgraph.aws4.resourceIcon;resIcon=mxgraph.aws4.{res};{FONT}shadow=1;")
    return (f"sketch=0;outlineConnect=0;fontColor=#232F3E;gradientColor=none;fillColor={fill};strokeColor=none;dashed=0;verticalLabelPosition=bottom;verticalAlign=top;align=center;html=1;"
            f"fontSize={size};fontStyle=0;aspect=fixed;pointerEvents=1;shape=mxgraph.aws4.{res};{FONT}")

def service(cid, cat_label, name, sub, res, cat, x, y, kind="svc", optional=False):
    """120×120 카테고리 박스 + 아이콘 + 아이콘 아래 한두 줄 실측값. optional=True 는 회색 점선(미도입·제거)."""
    tint, stroke, fill = CAT["opt"] if optional else CAT[cat]
    dashed = "dashed=1;dashPattern=6 4;" if optional else ""
    vertex(f"grp-{cid}", cat_label, f"fillColor={tint};strokeColor={stroke};rounded=1;whiteSpace=wrap;html=1;verticalAlign=top;fontStyle=1;fontSize=11;fontColor={stroke};{FONT}container=1;collapsible=0;shadow=1;strokeWidth=1.5;{dashed}", x, y, 120, 120)
    val = f"<b>{name}</b>" + (f"<br><i>{sub}</i>" if sub else "")
    vertex(cid, val, icon_style(res, fill, kind, 9), 36, 26, 48, 48, parent=f"grp-{cid}")

def attach(host, cid, label, res, cat, corner="tr", optional=False):
    """호스트 박스 모서리에 붙는 부착 기능(ACM 인증서 등). 트래픽 경로 아님."""
    tint, stroke, fill = CAT["opt"] if optional else CAT[cat]
    x = 104 if corner.endswith("r") else -16
    vertex(cid, label, f"sketch=0;{PTS};outlineConnect=0;fontColor={stroke};fillColor={fill};strokeColor=#ffffff;dashed=0;verticalLabelPosition=bottom;verticalAlign=top;align=center;html=1;fontSize=9;fontStyle=1;aspect=fixed;shape=mxgraph.aws4.resourceIcon;resIcon=mxgraph.aws4.{res};{FONT}shadow=1;", x, 34, 32, 32, parent=f"grp-{host}")

def edge(cid, src, dst, style, pts=None, label=None, lx=0.0, ly=0, exit=None, entry=None):
    st = style
    if exit: st += f"exitX={exit[0]};exitY={exit[1]};exitDx=0;exitDy=0;"
    if entry: st += f"entryX={entry[0]};entryY={entry[1]};entryDx=0;entryDy=0;"
    c = ET.SubElement(root, "mxCell", id=cid, style=st, edge="1", parent="1", source=src, target=dst)
    g = ET.SubElement(c, "mxGeometry", relative="1"); g.set("as", "geometry")
    if pts:
        arr = ET.SubElement(g, "Array"); arr.set("as", "points")
        for px, py in pts: ET.SubElement(arr, "mxPoint", x=str(px), y=str(py))
    if label:
        l = ET.SubElement(root, "mxCell", id=f"{cid}-label", value=label, style=f"edgeLabel;html=1;align=center;verticalAlign=middle;resizable=0;points=[];labelBackgroundColor=#FFFFFF;fontSize=11;{FONT}", connectable="0", vertex="1", parent=cid)
        lg = ET.SubElement(l, "mxGeometry", relative="1", x=str(lx), y=str(ly)); lg.set("as", "geometry"); ET.SubElement(lg, "mxPoint").set("as", "offset")

def badge(n, x, y):
    vertex(f"step-{n}", str(n), f"rounded=1;whiteSpace=wrap;html=1;fillColor=#007CBD;strokeColor=default;fontColor=#FFFFFF;fontStyle=1;fontSize=16;{FONT}shadow=1;glass=0;strokeWidth=2;align=center;verticalAlign=middle;labelBackgroundColor=none;", x, y, 28, 28)

def actor(cid, label, x, y, res="users", kind="svc"):
    vertex(cid, label, f"fillColor=#f5f5f5;strokeColor=light-dark(#666666,#D4D4D4);rounded=1;whiteSpace=wrap;html=1;verticalAlign=top;fontStyle=1;fontSize=12;fontColor=#333333;{FONT}container=1;collapsible=0;shadow=1;strokeWidth=1;", x, y, 107, 98)
    vertex(f"{cid}-icon", "", icon_style(res, "#232F3D", kind), 30, 30, 48, 48, parent=cid)

# ---------- title ----------
tg = ET.SubElement(root, "mxCell", id="title-group", value="", style=f"group;{FONT}", connectable="0", vertex="1", parent="1")
ET.SubElement(tg, "mxGeometry", x="50", y="30", width="2000", height="83").set("as", "geometry")
t1 = ET.SubElement(root, "mxCell", id="title-text", value="PetClinic 3-Tier on AWS — 현재 아키텍처 As-Built (1팀 Mission Critical · mc-deploy 528821350786 · 2026-09-16)",
                   style=f"text;html=1;resizable=1;points=[];autosize=1;align=left;verticalAlign=top;spacingTop=-4;fontSize=30;fontStyle=1;{FONT}", vertex="1", parent="title-group")
ET.SubElement(t1, "mxGeometry", width="1900", height="42").set("as", "geometry")
t2 = ET.SubElement(root, "mxCell", id="subtitle-text", value="① 네트워크 진입 → ② WEB → ③ WAS → ④ DB + 계층별 로그·비밀·백업  |  infra/terraform-kdt5 create_base=true (127 리소스)  |  Route 53 → CloudFront(WAF 유지·로그 켬 · 정적은 S3 OAC) → Public ALB :443 → Apache ×2 → Internal ALB :8080 → Tomcat 9.0.121 ×2 (test·Green) → RDS Proxy(TLS) → RDS MySQL 8.4.11 Multi-AZ",
                   style=f"text;html=1;resizable=0;points=[];whiteSpace=wrap;align=left;verticalAlign=top;spacingTop=-4;fontSize=14;{FONT}", vertex="1", parent="title-group")
ET.SubElement(t2, "mxGeometry", x="5", y="40", width="1990", height="30").set("as", "geometry")
t3 = ET.SubElement(root, "mxCell", id="title-separator", value="", style=f"line;strokeWidth=2;html=1;fontSize=14;strokeColor=#FF9900;{FONT}", vertex="1", parent="title-group")
ET.SubElement(t3, "mxGeometry", x="5", y="70", width="1990", height="10").set("as", "geometry")

# ---------- groups ----------
vertex("aws-cloud", "AWS Cloud · 528821350786 (mc-deploy) · Terraform state infra/terraform-kdt5/terraform.tfstate", STY["cloud"], 230, 140, 1820, 2000)
vertex("band-entry", "①  네트워크 진입 계층 · 글로벌 엣지 (Route 53 → CloudFront [WAF Web ACL · ACM us-east-1 부착] → Behavior 분기: 정적 → S3 mc-static(OAC) / 동적 → Public ALB / 점검 페이지 S3(OAC) · 액세스 로그 → S3 · WAF 로그 → CloudWatch Logs)",
       f"rounded=0;fillColor=none;dashed=1;strokeColor=#8C4FFF;verticalAlign=top;align=left;spacingLeft=10;fontColor=#8C4FFF;fontStyle=1;fontSize=14;whiteSpace=wrap;html=1;container=0;pointerEvents=0;{FONT}", 250, 165, 1780, 300)
vertex("region", "ap-northeast-2 (서울)", STY["region"], 260, 500, 1760, 1580)
vertex("vpc", "VPC mc-vpc · 10.0.0.0/16 (서브넷 8 · IGW · NAT ×2 · rt public / private-a / private-c / db)", STY["vpc"], 290, 580, 1210, 1040)
vertex("az-a", "가용영역 A (ap-northeast-2a)", STY["az"], 320, 640, 500, 950)
vertex("az-c", "가용영역 C (ap-northeast-2c)", STY["az"], 980, 640, 500, 950)
vertex("sub-pub-a", "퍼블릭 mc-public-a · 10.0.0.0/24 → IGW", STY["pub"], 350, 670, 450, 170)
vertex("sub-pub-c", "퍼블릭 mc-public-c · 10.0.1.0/24 → IGW", STY["pub"], 1010, 670, 450, 170)
vertex("tier-web", "WEB 계층 — EC2 고정 2대 (mc-web-a/c · t3.small · AL2023) · ASG 는 로드맵(멘토링 9/16)", STY["tier"], 335, 875, 1140, 215)
vertex("sub-web-a", "프라이빗 mc-web-a · 10.0.10.0/24 → NAT-a", STY["priv"], 350, 905, 450, 170)
vertex("sub-web-c", "프라이빗 mc-web-c · 10.0.11.0/24 → NAT-c", STY["priv"], 1010, 905, 450, 170)
vertex("tier-was", "WAS 계층 — EC2 고정 2대 (mc-was-a/c · t3.medium) · Tomcat 9.0.121 · Corretto 8 · PetClinic test(Green)", STY["tier"], 335, 1120, 1140, 215)
vertex("sub-was-a", "프라이빗 mc-was-a · 10.0.20.0/24 → NAT-a", STY["priv"], 350, 1150, 450, 170)
vertex("sub-was-c", "프라이빗 mc-was-c · 10.0.21.0/24 → NAT-c", STY["priv"], 1010, 1150, 450, 170)
vertex("sub-db-a", "프라이빗 mc-db-a · 10.0.30.0/24 (rt-db · 인터넷 경로 없음)", STY["priv"], 350, 1380, 450, 180)
vertex("sub-db-c", "프라이빗 mc-db-c · 10.0.31.0/24 (rt-db · 인터넷 경로 없음)", STY["priv"], 1010, 1380, 450, 180)

# tier labels (left column)
text("lbl-web", "②  WEB 계층", 40, 950, 180, 24, "#ED7100", 16)
text("lbl-web2", "Apache 2.4 · mod_proxy_http<br>index.html + /static/ 직접<br>Public ALB · /health.html", 40, 976, 170, 56, "#232F3E", 10, False)
text("lbl-was", "③  WAS 계층", 40, 1195, 180, 24, "#ED7100", 16)
text("lbl-was2", "Tomcat 9.0.121 · Corretto 8<br>test 브랜치(Spring 5.3.39) Green<br>Internal ALB · 헬스체크 /petclinic/", 40, 1221, 180, 56, "#232F3E", 10, False)
text("lbl-db", "④  DB 계층", 40, 1425, 180, 24, "#C925D1", 16)
text("lbl-db2", "RDS MySQL 8.4.11 Multi-AZ<br>RDS Proxy(TLS) · 앱 전용 사용자<br>Secrets ×2 · Backup", 40, 1451, 180, 56, "#232F3E", 10, False)
text("lbl-store", "감사", 40, 1725, 180, 24, "#E7157B", 16)
text("lbl-store2", "CloudTrail 계정 수준(VPC 밖)<br>S3 객체 1년 · 로그 파일 검증", 40, 1751, 180, 44, "#232F3E", 10, False)
text("lbl-ops", "운영 · 관측 공통", 40, 1925, 180, 24, "#E7157B", 16)
text("lbl-ops2", "CloudWatch 알람 3 → SNS<br>Grafana·Slack 은 미도입", 40, 1951, 180, 44, "#232F3E", 10, False)
text("lbl-store-band", "감사 로그 (계정 수준)", 300, 1630, 520, 22, "#E7157B", 14)
text("lbl-ops-band", "운영 · 관측 공통 (전 계층)", 300, 1845, 400, 22, "#E7157B", 14)
text("lbl-opscol", "계층별 로그 · 비밀 · 백업 (오른쪽 열, 계층 행에 맞춤) — 로그는 서버에 두지 않음", 1550, 515, 470, 24, "#E7157B", 14)
text("lbl-row-web", "WEB·WAS·Bastion 로그 (계정에 1개)", 1550, 910, 300, 20, "#ED7100", 12)
text("lbl-row-was", "WAS 설정 · 권한 · 증설(로드맵)", 1550, 1155, 300, 20, "#ED7100", 12)
text("lbl-row-db", "DB 계층 비밀 · 암호화 · 백업", 1550, 1385, 260, 20, "#C925D1", 12)

# ---------- external actors ----------
actor("users", "사용자 (의료진·환자)", 60, 290)
actor("ops", "운영자 (관리자)", 60, 690, res="user")
vertex("slack", "Slack (미연결 · 로드맵)", f"fillColor=#FAFAFA;strokeColor=#9E9E9E;dashed=1;dashPattern=6 4;rounded=1;whiteSpace=wrap;html=1;verticalAlign=top;fontStyle=1;fontSize=12;fontColor=#9E9E9E;{FONT}container=1;collapsible=0;shadow=0;strokeWidth=1;", 2080, 1900, 107, 98)
vertex("slack-icon", "", icon_style("chat", "#9E9E9E", "sub"), 30, 30, 48, 48, parent="slack")

# ---------- ① entry tier ----------
service("r53", "DNS", "Amazon Route 53", "mission-critical.site<br>A/AAAA alias → CloudFront", "route_53", "net", 300, 260)
service("waf", "웹 방화벽 (유지)", "AWS WAF", "관리형 3 + rate-all 2,000/5분<br>rate-booking 100/5분 · 로그 → CW Logs", "waf", "sec", 520, 260)
service("cf", "CDN · 엣지", "Amazon CloudFront", "E2PWXW3LUYTDEE<br>PriceClass_200 · TLS1.2_2021", "cloudfront", "net", 740, 260)
attach("cf", "acm-cf", "ACM", "certificate_manager", "sec", "tr")
service("s3static", "정적 자산 (OAC)", "Amazon S3", "mc-static · /static/* · /images/*<br>apply 가 저장소 자산 동기화", "s3", "storage", 960, 260)
service("s3maint", "점검 페이지 (OAC)", "Amazon S3", "mc-maintenance-…<br>5xx → 503 maintenance.html", "s3", "storage", 1180, 260)
service("s3cflog", "CloudFront 액세스 로그", "Amazon S3", "mc-logs/cloudfront/ · 객체 .gz<br>9/16 켬 · 90일", "s3", "storage", 1420, 260)
service("acm", "인증서", "AWS Certificate Manager", "us-east-1: CloudFront<br>서울: ALB 443 · 자동 갱신", "certificate_manager", "sec", 1660, 260)
service("kms", "암호화 키", "AWS KMS", "alias/mc-cmk<br>S3 · SNS · Logs · Backup", "key_management_service", "sec", 1880, 260)

# ---------- VPC · middle lane ----------
service("igw", "인터넷 연결", "Internet Gateway", "mc-igw", "internet_gateway", "net", 840, 510, kind="sub")
service("alb", "부하 분산 (외부)", "Public ALB", "mc-alb-public · :443 만<br>기본 403 · X-Origin-Verify", "application_load_balancer", "net", 840, 690, kind="sub")
attach("alb", "acm-alb", "ACM", "certificate_manager", "sec", "tr")
service("ialb", "부하 분산 (내부)", "Internal ALB", "mc-alb-internal · :8080<br>tg-was /petclinic/ 10s·2/3", "application_load_balancer", "net", 840, 1170, kind="sub")
service("proxy", "커넥션 관리", "RDS Proxy", "mc-rds-proxy · require_tls<br>SECRETS 인증 2개", "rds_proxy", "db", 840, 1410, kind="sub")
service("nat-a", "아웃바운드", "NAT Gateway", "mc-nat-a · EIP<br>dnf · git · Maven · SSM", "nat_gateway", "net", 380, 700, kind="sub")
service("nat-c", "아웃바운드", "NAT Gateway", "mc-nat-c · EIP<br>AZ 손실 대비 (2개 유지)", "nat_gateway", "net", 1030, 700, kind="sub")
service("web-a", "WEB", "mc-web-a · Apache 2.4", "i-01a195cff8acb28d8<br>/ · /static/ 직접 · /petclinic/ 프록시", "ec2", "compute", 380, 935)
service("web-c", "WEB", "mc-web-c · Apache 2.4", "i-01d1734d081d8bc57<br>같은 user_data (web.sh)", "ec2", "compute", 1030, 935)
service("was-a", "WAS", "mc-was-a · Tomcat 9.0.121", "i-0ff9a07cd26d34ba0<br>mvnw -P MySQL · petclinic_app", "ec2", "compute", 380, 1180)
service("was-c", "WAS", "mc-was-c · Tomcat 9.0.121", "i-0d308599780158a68<br>풀 testOnBorrow · systemd", "ec2", "compute", 1030, 1180)
service("rds-s", "관계형 DB (대기 · Standby)", "RDS mc-petclinic", "Secondary AZ = 2a<br>동기 복제 · 자동 failover", "rds", "db", 380, 1410)
service("rds-p", "관계형 DB (주 · Primary)", "RDS MySQL 8.4.11", "Primary AZ = 2c · db.t3.small<br>Multi-AZ · 암호화 · TLS 필수", "rds", "db", 1030, 1410)

# ---------- ops column (per tier) ----------
service("cwl", "로그 저장소 (계정에 1개)", "CloudWatch Logs", "/mc/web/* · /mc/was/* 30일<br>/mc/bastion/secure 90일 · WAF · KMS", "cloudwatch_logs", "integ", 1550, 935, kind="sub")
service("s3-logs", "액세스 로그 (객체)", "Amazon S3", "mc-logs · alb/public · alb/internal<br>cloudfront/ · 90일 · 5분 .gz", "s3", "storage", 1710, 935)
service("bastion", "운영자 접속 (Bastion)", "Bastion Host", "퍼블릭 A · EIP · SSH 22 ← 운영자 IP<br>같은 키로 WEB·WAS · Proxy 3306", "ec2", "integ", 620, 700)
service("cwparam", "Agent 설정 (Parameter Store)", "SSM Parameter Store", "/mc/cwagent/web · was · bastion<br>Session Manager 아님 · 설정만", "systems_manager", "integ", 1550, 1180, kind="sub")
service("iam", "인스턴스 권한", "IAM mc-ec2-role", "SSM Core · CW Agent · Secrets 2개<br>kms:Decrypt · s3:PutObject mc-logs", "identity_and_access_management", "sec", 1710, 1180)
service("asg", "증설 (로드맵)", "Auto Scaling", "enable_asg 미도입<br>도입 시 종료 훅 300s 로그 sync", "autoscaling", "compute", 1870, 1180, optional=True)
service("secrets", "비밀 관리", "Secrets Manager", "admin rds!db-…(7일 교체)<br>app-db petclinic_app(교체 없음)", "secrets_manager", "sec", 1550, 1410)
service("pg", "파라미터 그룹", "mc-mysql84", "require_secure_transport=1<br>utf8mb4 · unicode_ci", "rds", "db", 1710, 1410)
service("backup", "백업", "AWS Backup", "mc-rds-daily 04:00 KST · 7일<br>mc-backup-vault(KMS) · PITR", "backup", "storage", 1870, 1410)

# ---------- audit band ----------
service("cloudtrail", "감사 추적", "AWS CloudTrail", "mc-trail · 다중 리전<br>관리 이벤트 · 로그 파일 검증", "cloudtrail", "integ", 350, 1680)
service("s3-trail", "감사 로그 (객체)", "Amazon S3", "mc-cloudtrail-… · 1년<br>90일 후 Glacier IR", "s3", "storage", 570, 1680)

# ---------- common ops band ----------
service("cw", "지표 · 알람 ×3", "Amazon CloudWatch", "was-unhealthy-host · alb-p95&gt;2s<br>rds-connections&gt;60", "cloudwatch", "integ", 790, 1880)
service("sns", "알림 주제", "Amazon SNS", "mc-alerts · KMS<br>email 구독 0건(alert_emails)", "sns", "integ", 1010, 1880)
service("grafana", "대시보드 (미생성)", "Managed Grafana", "enable_grafana=false<br>Identity Center 필요", "managed_service_for_grafana", "integ", 1230, 1880, optional=True)

# ---------- edges: request flow ----------
edge("e1", "users", "r53", EDGE, label="DNS 조회", lx=-0.1, ly=-12, exit=(1, 0.5), entry=(0, 0.5))
edge("e2", "r53", "waf", EDGE, label="alias · HTTPS", lx=0, ly=-12, exit=(1, 0.5), entry=(0, 0.5))
edge("e2w", "waf", "cf", EDGE, label="먼저 검사 → 통과만 (부착 · 홉 아님)", lx=0, ly=-16, exit=(1, 0.5), entry=(0, 0.5))
edge("e2l", "waf", "cwl", EDGE_LOGCW, pts=[(580, 212), (1590, 212)], label="WAF 로그 aws-waf-logs-mc → CloudWatch Logs", lx=-0.25, ly=-10, exit=(0.5, 0), entry=(0.35, 0))
edge("e6s", "cf", "s3static", EDGE, label="정적 Miss (OAC)", lx=0, ly=-12, exit=(1, 0.5), entry=(0, 0.5))
edge("e6", "cf", "s3maint", EDGE_LOGS3, pts=[(830, 440), (1240, 440)], label="오리진 5xx·타임아웃 → 점검 페이지 (OAC SigV4)", lx=-0.1, ly=12, exit=(0.75, 1), entry=(0.5, 1))
edge("e6l", "cf", "s3cflog", EDGE_LOGS3, pts=[(800, 228), (1480, 228)], label="액세스 로그 (1시간 이내 · S3 객체)", lx=0.2, ly=-10, exit=(0.5, 0), entry=(0.5, 0))
edge("e7", "cf", "igw", EDGE, pts=[(770, 464), (900, 464)], label="동적 + /petclinic/resources/* Miss → ALB · HTTPS 443 + X-Origin-Verify", lx=-0.25, ly=-12, exit=(0.25, 1), entry=(0.5, 0))
edge("e8", "igw", "alb", EDGE, exit=(0.5, 1), entry=(0.5, 0))
edge("e10", "alb", "web-a", EDGE, pts=[(870, 858), (440, 858)], label="mc-tg-web :80 · /health.html 10s · 2/3 · 라운드로빈", lx=0.1, ly=-12, exit=(0.25, 1), entry=(0.5, 0))
edge("e11", "alb", "web-c", EDGE, pts=[(930, 858), (1090, 858)], exit=(0.75, 1), entry=(0.5, 0))
edge("e12", "web-a", "ialb", EDGE, pts=[(440, 1108), (870, 1108)], label="ProxyPass /petclinic/ → :8080 · ProxyPreserveHost On", lx=0.1, ly=-12, exit=(0.5, 1), entry=(0.25, 0))
edge("e13", "web-c", "ialb", EDGE, pts=[(1090, 1108), (930, 1108)], exit=(0.5, 1), entry=(0.75, 0))
edge("e14", "ialb", "was-a", EDGE, label="mc-tg-was · /petclinic/", lx=0.3, ly=-12, exit=(0, 0.5), entry=(1, 0.5))
edge("e15", "ialb", "was-c", EDGE, exit=(1, 0.5), entry=(0, 0.5))
edge("e16", "was-a", "proxy", EDGE_DB, pts=[(440, 1355), (870, 1355)], label="JDBC 3306 · sslMode=REQUIRED · 사용자 petclinic_app", lx=0.1, ly=-12, exit=(0.5, 1), entry=(0.25, 0))
edge("e17", "was-c", "proxy", EDGE_DB, pts=[(1090, 1355), (930, 1355)], exit=(0.5, 1), entry=(0.75, 0))
edge("e18", "proxy", "rds-p", EDGE_DB, label="풀링 커넥션 → Primary(2c)", lx=0, ly=-12, exit=(1, 0.5), entry=(0, 0.5))
edge("e19", "rds-p", "rds-s", EDGE_BI, pts=[(1090, 1545), (440, 1545)], label="동기 복제 · 자동 failover 60~120s (RPO 0)", lx=0, ly=-11, exit=(0.5, 1), entry=(0.5, 1))
# ---------- edges: secrets / backup / logs ----------
edge("e20", "secrets", "proxy", EDGE_D, pts=[(1610, 1595), (900, 1595)], label="Proxy 인증 = admin + app-db 비밀 (교체돼도 앱 무영향)", lx=-0.3, ly=13, exit=(0.5, 1), entry=(0.5, 1))
edge("e20b", "secrets", "was-c", EDGE_D, pts=[(1530, 1470), (1530, 1300), (1150, 1300)], label="부팅 시 app-db 조회 → WAR 빌드 주입", lx=0.35, ly=-11, exit=(0, 0.5), entry=(0.5, 1))
edge("e21", "rds-p", "backup", EDGE_D, pts=[(1090, 1575), (1930, 1575)], label="daily-7d", lx=0.3, ly=11, exit=(0.5, 1), entry=(0.5, 1))
edge("e21p", "pg", "rds-p", EDGE_D, pts=[(1770, 1395), (1090, 1395)], label="파라미터 그룹 적용", lx=0.3, ly=-10, exit=(0.5, 0), entry=(0.5, 0))
edge("e26", "cloudtrail", "s3-trail", EDGE_LOGS3, label="5분마다 객체 · 1년", lx=0, ly=-12, exit=(1, 0.5), entry=(0, 0.5))
edge("e28", "cw", "sns", EDGE, label="alarm_actions (구독 0건 → 이메일 추가 필요)", lx=0, ly=-12, exit=(1, 0.5), entry=(0, 0.5))
edge("e27", "cw", "grafana", EDGE_GHOST, pts=[(850, 2035), (1290, 2035)], label="지표·로그 → Grafana (로드맵)", lx=0, ly=12, exit=(0.5, 1), entry=(0.5, 1))
edge("e31", "grafana", "slack", EDGE_GHOST, pts=[(1350, 1940), (2060, 1940)], label="Grafana Alerting → Slack (로드맵)", lx=0.2, ly=-11, exit=(1, 0.5), entry=(0, 0.5))
edge("e33", "web-c", "cwl", EDGE_LOGCW, label="CloudWatch Agent · access·error", lx=0, ly=-12, exit=(1, 0.5), entry=(0, 0.5))
edge("e34", "was-c", "cwl", EDGE_LOGCW, pts=[(1520, 1240), (1520, 1030)], label="Agent · catalina·access·gc", lx=-0.3, ly=-12, exit=(1, 0.5), entry=(0, 0.75))
edge("e35", "alb", "s3-logs", EDGE_LOGS3, pts=[(830, 702), (830, 572), (1770, 572)], label="ALB 액세스 로그 (외부·내부) → S3 객체 5분", lx=0.15, ly=-11, exit=(0, 0.1), entry=(0.5, 0))
edge("e36", "cwparam", "was-c", EDGE_D, pts=[(1610, 1150), (1150, 1150)], label="fetch-config", lx=0.3, ly=-10, exit=(0.5, 0), entry=(0.75, 0))
edge("e37", "ops", "bastion", EDGE, label="SSH 22 (키 mc-ssh)", lx=-0.2, ly=-10, exit=(1, 0.5), entry=(0, 0.5))
edge("e38", "bastion", "cwl", EDGE_LOGCW, pts=[(680, 865), (1562, 865)], label="sshd 로그 → /mc/bastion/secure", lx=0.2, ly=-10, exit=(0.5, 1), entry=(0.1, 0))
edge("e39", "bastion", "web-a", EDGE_D, pts=[(560, 760), (560, 995)], label="같은 키로 WEB·WAS 22", lx=0.4, ly=12, exit=(0, 0.5), entry=(1, 0.5))

# ---------- badges ----------
for n, (x, y) in {1: (215, 300), 2: (455, 285), 3: (1300, 405), 4: (885, 825), 5: (455, 1070), 6: (805, 1205), 7: (455, 1312),
                  8: (1165, 1500), 9: (1625, 1540), 10: (1030, 960), 11: (455, 1648), 12: (1030, 1850), 13: (215, 700), 14: (1548, 228)}.items():
    badge(n, x, y)

# ---------- legend ----------
LX, LY, LW, LH = 2230, 30, 650, 2130
vertex("legend-bg", "", "verticalLabelPosition=bottom;verticalAlign=top;html=1;shape=mxgraph.basic.rect;fillColor2=none;strokeWidth=1;size=20;indent=5;fillColor=light-dark(#EDF3FF,#305363);strokeColor=#6c8ebf;", LX, LY, LW, LH)
lc = ET.SubElement(root, "mxCell", id="legend-container", value="", style="group", connectable="0", vertex="1", parent="1")
ET.SubElement(lc, "mxGeometry", x=str(LX + 20), y=str(LY + 30), width="602", height=str(LH - 40)).set("as", "geometry")
lt = ET.SubElement(root, "mxCell", id="legend-title", value="계층별 흐름 · 설정 · 로그  (mc-deploy 실측 · 2026-09-16)", style=f"text;html=1;align=left;verticalAlign=top;fontSize=16;fontStyle=1;{FONT}", vertex="1", parent="legend-container")
ET.SubElement(lt, "mxGeometry", width="580", height="24").set("as", "geometry")
steps = [
 ("① 사용자 → Route 53", "petclinic.mission-critical.site A/AAAA alias → d2p7som2iuyba.cloudfront.net (존 Z0299891BL9WGKOA2LW9, 가비아 NS 위임). ALB DNS 는 공개하지 않음"),
 ("① CloudFront (WAF · ACM 부착)", "WAF 는 별도 홉이 아니라 CloudFront 에 붙은 Web ACL(us-east-1): 캐시 조회보다 먼저 평가, 차단은 캐시·오리진 미도달. allow-loadgen(JMeter IP set) → 관리형 3 → rate-all IP당 5분 2,000 → rate-booking /visits/new 100. 로그 → CloudWatch Logs aws-waf-logs-mc. 멘토링 '관리 어려움' 의견은 있었으나 팀 결정으로 유지(enable_waf=true). ACM us-east-1 · TLSv1.2_2021 · HTTP→HTTPS"),
 ("① Behavior 분기 → 정적 S3 / ALB / 점검 S3", "오리진 3개. /static/* · /images/*(랜딩 css·이미지·hero 영상) = S3 mc-static(OAC) — apply 가 src/main/webapp/resources·images 를 동기화, CachingOptimized 1일 → Hit 면 엣지, Miss 면 S3(Apache 안 거침). /petclinic/resources/* · /petclinic/images/*(WAR 안) = ALB 캐시. * = CachingDisabled + AllViewer → 매번 ALB. /maintenance.html = 점검 S3 OAC, 오리진 5xx → 503(오리진 그룹 failover). 정적 교체 후 invalidation"),
 ("② Public ALB → WEB ×2", "SG = CloudFront origin-facing 프리픽스 443 만(1차) · 리스너 기본 403 · 규칙10 X-Origin-Verify 일치 시만 mc-tg-web(2차). 80 리스너 없음. 헬스체크 /health.html 10s·5s·2/3(얕게 → WAS 장애 연쇄 방지). 액세스 로그 → S3 mc-logs/alb/public"),
 ("② WEB → Internal ALB", "Apache 2.4 mod_proxy_http(mod_jk 아님 — AJP 는 ALB 통과 불가). / = test 브랜치 WAR 의 index.html + resources·images 를 부팅 시 /var/www/html/static 으로 복사해 직접 서빙 · /petclinic/ → 302 / (hero 1회) · ProxyPass /petclinic/ → :8080 · ProxyPreserveHost On"),
 ("③ Internal ALB → WAS ×2", "mc-alb-internal :8080 → mc-tg-was /petclinic/ 10s·2/3. SG 체인: sg-alb-internal 8080 ← sg-web · sg-was 8080 ← sg-alb-internal. WEB 은 WAS IP 를 모름 → WAS 교체·증설 시 WEB 무변경"),
 ("③→④ WAS → RDS Proxy", "부팅 시 Secrets Manager 에서 app-db(petclinic_app) 조회 → mvnw -P MySQL -Djdbc.* 로 WAR 빌드 주입(Java 0줄) · Tomcat 9.0.121 systemd. JDBC sslMode=REQUIRED → Proxy require_tls. tomcat-jdbc 풀 testOnBorrow(SELECT 1)·유휴 10분 회수(Proxy idle 30분 대비). was.sh: Proxy 로그인 성공까지 대기 · 404 면 재시작"),
 ("④ RDS Multi-AZ", "mc-petclinic MySQL 8.4.11 · db.t3.small · Primary 2c / Standby 2a 동기 복제(RPO 0) · failover 60~120s 엔드포인트 동일 · 파라미터 그룹 mc-mysql84 require_secure_transport=1 · SG 3306 ← sg-rds-proxy 만(WAS 직결 없음). Spring initialize-database → vets 6 · owners 10 · pets 13"),
 ("④ Secrets ×2 · 파라미터 그룹 · Backup", "admin 비밀(rds!db-…)은 RDS 관리형 7일 교체 → 앱이 쓰면 교체 때 끊김 → 앱 전용 petclinic_app 비밀(교체 없음) 추가, Proxy 인증 2개 등록. Backup mc-rds-daily 04:00 KST 7일 + PITR. KMS alias/mc-cmk 는 S3·SNS·Logs·Backup, RDS·비밀은 AWS 관리형 키"),
 ("계층별 로그 = 서버에 두지 않음", "CloudWatch Logs 는 계정에 1개(VPC 밖 · 자체 저장소) — 로그 그룹만 /mc/web/* · /mc/was/* 30일 · /mc/bastion/secure 90일(sshd) · aws-waf-logs-mc(us-east-1) 로 나눔, 스트림 = 인스턴스 ID. Agent 는 user_data 로 설치하고 설정은 SSM 파라미터 /mc/cwagent/*. ALB·CloudFront 는 서비스가 직접 S3 객체(5분 .gz)로. 롤링 교체 5회 유실 0"),
 ("감사 로그 (계정 수준)", "CloudTrail mc-trail(다중 리전 · 관리 이벤트 · 로그 파일 검증) → S3 mc-cloudtrail 1년(90일 후 Glacier IR). 서버·VPC 와 무관하게 AWS API 호출을 기록. 오늘 장애(was-a Access denied)는 서버 접속 없이 /mc/was/catalina 로 원인 확인"),
 ("관측 · 알림 (공통)", "CloudWatch 알람 3(was-unhealthy-host ≥1 2분 · alb-p95 &gt;2s 3분 · rds-connections &gt;60 3분) → SNS mc-alerts. 이메일 구독 0건(alert_emails tfvars 한 줄). Grafana(enable_grafana=false)·Slack 은 미도입 로드맵"),
 ("② ③ 운영자 접속 = Bastion (SSM 안 씀)", "팀 결정 9/16: 퍼블릭 서브넷 A 의 Bastion(t3.micro · EIP) 에 SSH 22 — 허용은 운영자 공인 IP /32 만(base.bastion_allowed_cidrs). 키 mc-ssh 하나를 Bastion·WEB·WAS 에 부착 → ssh -J 점프, DB 는 Bastion 에서 mysql --ssl → RDS Proxy 3306. Session Manager 문서·/mc/ssm 로그·SSM Core 정책 제거(enable_ssm=false). sshd 로그 → /mc/bastion/secure. NAT ×2 는 아웃바운드 전용"),
 ("① CloudFront 액세스 로그 (9/16 켬)", "WAF 로그(차단·규칙 매치)와 별개로 모든 엣지 요청의 기록 → logging_config → S3 mc-logs/cloudfront/ 90일. CloudFront 표준 로그는 버킷 ACL 로 쓰므로 BucketOwnerPreferred + awslogsdelivery FULL_CONTROL 자동 부여. 첫 객체 16:55 확인. 로그 5종 = 앱·SSM(CW Logs) · ALB·CloudFront·CloudTrail(S3)"),
]
y = 36
for i, (title, desc) in enumerate(steps, 1):
    g = ET.SubElement(root, "mxCell", id=f"step-{i}-legend", value="", style=f"group;{FONT}", connectable="0", vertex="1", parent="legend-container")
    ET.SubElement(g, "mxGeometry", x="0", y=str(y), width="600", height="100").set("as", "geometry")
    b = ET.SubElement(root, "mxCell", id=f"step-{i}-badge-legend", value=str(i), style=f"rounded=1;whiteSpace=wrap;html=1;fillColor=#007CBD;strokeColor=default;fontColor=#FFFFFF;fontStyle=1;fontSize=22;labelBackgroundColor=none;{FONT}shadow=1;glass=0;strokeWidth=2;", vertex="1", parent=f"step-{i}-legend")
    ET.SubElement(b, "mxGeometry", y="2", width="40", height="38").set("as", "geometry")
    val = (f'<div><b>{title}</b></div><div><span style="color: light-dark(rgb(0,0,0), rgb(255,255,255));"><b><font style="font-size: 15px;">-</font> </b>{desc}</span></div>')
    d = ET.SubElement(root, "mxCell", id=f"step-{i}-desc-legend", value=val, style=f"text;html=1;align=left;verticalAlign=top;spacingTop=-4;fontSize=12;labelBackgroundColor=none;whiteSpace=wrap;{FONT}", vertex="1", parent=f"step-{i}-legend")
    ET.SubElement(d, "mxGeometry", x="52", width="548", height="100").set("as", "geometry")
    y += 108
note = ET.SubElement(root, "mxCell", id="legend-note", value='<i><span style="color: light-dark(rgb(0,0,0), rgb(255,255,255));">회색 점선 박스 = 미도입(ASG · Grafana · Slack). WAF 는 CloudFront 에 부착된 Web ACL 이며 별도 홉 아님(팀 결정 9/16 유지). 모서리 작은 ACM 아이콘은 부착된 인증서. NAT·IGW 는 흐름 번호 없음. Blue(main · Tomcat 9.0.53) 복귀는 tfvars 2줄(app_repo_branch · tomcat_version).</span></i>', style=f"text;html=1;align=left;verticalAlign=top;fontSize=12;whiteSpace=wrap;{FONT}", vertex="1", parent="legend-container")
ET.SubElement(note, "mxGeometry", x="0", y=str(y + 4), width="600", height="44").set("as", "geometry")
y += 56
lsg = ET.SubElement(root, "mxCell", id="legend-line-styles-group", value="", style=f"group;{FONT}", vertex="1", parent="legend-container")
ET.SubElement(lsg, "mxGeometry", x="0", y=str(y), width="456", height="150").set("as", "geometry")
ls_bg = ET.SubElement(root, "mxCell", id="legend-line-styles-bg", value="선 종류", style=f"rounded=1;whiteSpace=wrap;html=1;fillColor=light-dark(#F5F5F5,#29393B);strokeColor=#666666;verticalAlign=top;fontStyle=1;fontSize=12;{FONT}", vertex="1", parent="legend-line-styles-group")
ET.SubElement(ls_bg, "mxGeometry", width="456", height="150").set("as", "geometry")
for j, (sty, txt) in enumerate([(EDGE, "실선 : 요청 흐름 (사용자 → WAS)"), (EDGE_DB, "보라 실선 : DB 경로 (JDBC TLS → RDS Proxy → RDS)"), (EDGE_LOGCW, "분홍 점선 : Agent → CloudWatch Logs (로그 이벤트)"),
                                (EDGE_LOGS3, "초록 점선 : 서비스 → S3 객체 (ALB · CloudFront · CloudTrail)"), (EDGE_D, "점선 : 비밀 · 설정 · 백업 · 알림"), (EDGE_BI, "양방향 : Multi-AZ 동기 복제"), (EDGE_GHOST, "회색 점선 : 로드맵 (미도입)")]):
    yy = 30 + j * 17
    e = ET.SubElement(root, "mxCell", id=f"ls-{j}", style=sty, edge="1", parent="legend-line-styles-group")
    eg = ET.SubElement(e, "mxGeometry", relative="1"); eg.set("as", "geometry")
    ET.SubElement(eg, "mxPoint", x="16", y=str(yy)).set("as", "sourcePoint"); ET.SubElement(eg, "mxPoint", x="90", y=str(yy)).set("as", "targetPoint")
    t = ET.SubElement(root, "mxCell", id=f"ls-t-{j}", value=f'<span style="color: light-dark(rgb(0,0,0), rgb(255,255,255));">{txt}</span>', style=f"text;html=1;align=left;verticalAlign=middle;fontSize=11;{FONT}", vertex="1", parent="legend-line-styles-group")
    ET.SubElement(t, "mxGeometry", x="100", y=str(yy - 9), width="350", height="18").set("as", "geometry")

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "architecture-current-tiered.drawio")
tree = ET.ElementTree(mxfile); ET.indent(tree, space="  "); tree.write(OUT, encoding="utf-8", xml_declaration=False); print("wrote", OUT)

def render(drawio, png, w=2900, h=2200):
    xml = open(drawio, encoding="utf-8").read()
    cfg = json.dumps({"xml": xml, "nav": False, "resize": True, "toolbar": "", "highlight": "#0000ff", "lightbox": False})
    html = f"<html><body style='margin:0;background:#fff'><div class='mxgraph' style='max-width:100%;border:0' data-mxgraph='{_html.escape(cfg, quote=True)}'></div><script src='https://viewer.diagrams.net/js/viewer-static.min.js'></script></body></html>"
    tmp = os.path.join(os.environ.get("SCRATCH", "/tmp"), "current-tiered-render.html")
    open(tmp, "w", encoding="utf-8").write(html)
    subprocess.run(["google-chrome", "--headless=new", "--disable-gpu", "--no-sandbox", "--hide-scrollbars", "--virtual-time-budget=30000", "--force-device-scale-factor=2",
                    f"--window-size={w},{h}", f"--screenshot={png}", "file://" + tmp], check=True, capture_output=True)
    print("wrote", png)
if __name__ == "__main__" and "--png" in sys.argv:
    render(OUT, OUT.replace(".drawio", ".png"))
