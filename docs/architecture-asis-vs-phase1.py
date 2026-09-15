"""kdt5 계정(723165663216)에 실제 구축된 As-Is 도면과 Phase 1 목표 도면을 같은 레이아웃으로 생성.
실행: python3 docs/architecture-asis-vs-phase1.py  → docs/architecture-asis-kdt5.drawio, docs/architecture-phase1-target.drawio
As-Is 값은 2026-09-15 aws cli 조회 결과(VPC test-vpc, test-Public-ALB, WEB-test-a, WAS-test-a, bas-server)."""
import xml.etree.ElementTree as ET

PTS = "points=[[0,0,0],[0.25,0,0],[0.5,0,0],[0.75,0,0],[1,0,0],[0,1,0],[0.25,1,0],[0.5,1,0],[0.75,1,0],[1,1,0],[0,0.25,0],[0,0.5,0],[0,0.75,0],[1,0.25,0],[1,0.5,0],[1,0.75,0]]"
GPTS = "points=[[0,0],[0.25,0],[0.5,0],[0.75,0],[1,0],[1,0.25],[1,0.5],[1,0.75],[1,1],[0.75,1],[0.5,1],[0.25,1],[0,1],[0,0.75],[0,0.5],[0,0.25]]"
FONT = "fontFamily=Helvetica;"
CAT = {"net": ("#EDE7F6", "#8C4FFF"), "compute": ("#FFF2E8", "#ED7100"), "db": ("#F5E6F7", "#C925D1"),
       "sec": ("#FFEBEE", "#DD344C"), "gen": ("#F5F5F5", "#666666"), "miss": ("#FFFFFF", "#D32F2F")}
GROUP = f"{GPTS};outlineConnect=0;gradientColor=none;html=1;whiteSpace=wrap;fontSize=12;fontStyle=0;shape=mxgraph.aws4.group;"
STY = {
    "cloud": GROUP + "grIcon=mxgraph.aws4.group_aws_cloud;strokeColor=#232F3E;fillColor=none;verticalAlign=top;align=left;spacingLeft=30;fontColor=#232F3E;dashed=0;container=0;collapsible=0;fontSize=14;fontStyle=1;" + FONT,
    "region": GROUP + "grIcon=mxgraph.aws4.group_region;strokeColor=#00A4A6;fillColor=none;verticalAlign=top;align=left;spacingLeft=30;fontColor=#00A4A6;dashed=1;container=0;collapsible=0;fontSize=14;fontStyle=1;" + FONT,
    "vpc": GROUP + "grIcon=mxgraph.aws4.group_vpc2;strokeColor=#8C4FFF;fillColor=light-dark(#8C4FFF0D,#8C4FFF0D);fillStyle=auto;verticalAlign=top;align=left;spacingLeft=30;fontColor=#8C4FFF;dashed=0;container=0;collapsible=0;fontSize=14;fontStyle=1;" + FONT,
    "az": "fillColor=none;strokeColor=#147EBA;dashed=1;verticalAlign=top;fontStyle=1;fontSize=12;fontColor=#147EBA;whiteSpace=wrap;html=1;container=0;collapsible=0;" + FONT,
    "pub": GROUP + "grIcon=mxgraph.aws4.group_public_subnet;strokeColor=#248814;fillColor=light-dark(#2488140D,#2488140D);fillStyle=auto;verticalAlign=top;align=left;spacingLeft=30;fontColor=#248814;dashed=0;container=0;collapsible=0;" + FONT,
    "priv": GROUP + "grIcon=mxgraph.aws4.group_private_subnet;strokeColor=#147EBA;fillColor=light-dark(#147EBA0D,#147EBA0D);fillStyle=auto;verticalAlign=top;align=left;spacingLeft=30;fontColor=#147EBA;dashed=0;container=0;collapsible=0;" + FONT,
}
EDGE = "edgeStyle=orthogonalEdgeStyle;html=1;endArrow=block;elbow=vertical;startArrow=none;endFill=1;strokeColor=#545B64;rounded=0;strokeWidth=1.5;" + FONT
EDGE_BROKEN = EDGE + "dashed=1;strokeColor=#D32F2F;"
EDGE_BI = "edgeStyle=orthogonalEdgeStyle;html=1;endArrow=block;elbow=vertical;startArrow=block;startFill=1;endFill=1;strokeColor=#545B64;rounded=0;dashed=1;" + FONT


class D:
    def __init__(self, name, page_w, page_h):
        self.mxfile = ET.Element("mxfile", host="Electron", version="29.6.1")
        dg = ET.SubElement(self.mxfile, "diagram", name=name, id="d1")
        model = ET.SubElement(dg, "mxGraphModel", dx="1800", dy="1000", grid="0", gridSize="10", guides="1", tooltips="1", connect="1", arrows="1", fold="1",
                              page="0", pageScale="1", pageWidth=str(page_w), pageHeight=str(page_h), math="0", shadow="0")
        self.root = ET.SubElement(model, "root")
        ET.SubElement(self.root, "mxCell", id="0"); ET.SubElement(self.root, "mxCell", id="1", parent="0")

    def v(self, cid, value, style, x, y, w, h, parent="1"):
        c = ET.SubElement(self.root, "mxCell", id=cid, value=value, style=style, vertex="1", parent=parent)
        ET.SubElement(c, "mxGeometry", x=str(x), y=str(y), width=str(w), height=str(h)).set("as", "geometry")

    def text(self, cid, value, x, y, w, h, color="#232F3E", size=13, bold=False, align="left"):
        self.v(cid, value, f"text;html=1;whiteSpace=wrap;strokeColor=none;fillColor=none;align={align};verticalAlign=top;fontSize={size};fontStyle={1 if bold else 0};fontColor={color};{FONT}", x, y, w, h)

    def svc(self, cid, title, sub, res, cat, x, y, missing=False):
        tint, stroke = CAT["miss"] if missing else CAT[cat]
        dashed = "dashed=1;dashPattern=6 4;" if missing else ""
        self.v(f"grp-{cid}", title, f"fillColor={tint};strokeColor={stroke};rounded=1;whiteSpace=wrap;html=1;verticalAlign=top;fontStyle=1;fontSize=11;fontColor={stroke};{FONT}container=1;collapsible=0;shadow=0;strokeWidth=1.5;{dashed}", x, y, 130, 118)
        fill = "#D32F2F" if missing else CAT[cat][1]
        ist = (f"sketch=0;{PTS};outlineConnect=0;fontColor=#232F3E;fillColor={fill};strokeColor=#ffffff;dashed=0;verticalLabelPosition=bottom;verticalAlign=top;align=center;html=1;fontSize=9;fontStyle=0;aspect=fixed;"
               f"shape=mxgraph.aws4.resourceIcon;resIcon=mxgraph.aws4.{res};{FONT}")
        self.v(cid, sub, ist, 43, 26, 44, 44, parent=f"grp-{cid}")

    def edge(self, cid, s, t, style=EDGE, label=None, pts=None, exit=None, entry=None, lx=0, ly=-10):
        st = style
        if exit: st += f"exitX={exit[0]};exitY={exit[1]};exitDx=0;exitDy=0;"
        if entry: st += f"entryX={entry[0]};entryY={entry[1]};entryDx=0;entryDy=0;"
        c = ET.SubElement(self.root, "mxCell", id=cid, style=st, edge="1", parent="1", source=s, target=t)
        g = ET.SubElement(c, "mxGeometry", relative="1"); g.set("as", "geometry")
        if pts:
            arr = ET.SubElement(g, "Array"); arr.set("as", "points")
            for px, py in pts: ET.SubElement(arr, "mxPoint", x=str(px), y=str(py))
        if label:
            l = ET.SubElement(self.root, "mxCell", id=f"{cid}-l", value=label, style=f"edgeLabel;html=1;align=center;verticalAlign=middle;resizable=0;points=[];labelBackgroundColor=#FFFFFF;fontSize=10;{FONT}", connectable="0", vertex="1", parent=cid)
            lg = ET.SubElement(l, "mxGeometry", relative="1", x=str(lx), y=str(ly)); lg.set("as", "geometry"); ET.SubElement(lg, "mxPoint").set("as", "offset")

    def note(self, cid, value, x, y, w, h, color="#D32F2F"):
        self.v(cid, value, f"rounded=1;whiteSpace=wrap;html=1;fillColor=#FFF8E1;strokeColor={color};strokeWidth=1.5;align=left;verticalAlign=top;fontSize=11;fontColor=#232F3E;spacing=8;{FONT}", x, y, w, h)

    def write(self, path):
        ET.ElementTree(self.mxfile).write(path, encoding="utf-8", xml_declaration=True); print("wrote", path)


def frame(d, title, subtitle, vpc_label, az_extra=""):
    d.text("title", title, 40, 20, 1500, 40, size=26, bold=True)
    d.text("subtitle", subtitle, 40, 60, 1500, 30, size=13, color="#555555")
    d.v("cloud", "AWS Cloud · 계정 723165663216 (kdt5)", STY["cloud"], 140, 110, 1300, 900)
    d.v("region", "ap-northeast-2 (Seoul)", STY["region"], 165, 145, 1250, 850)
    d.v("vpc", vpc_label, STY["vpc"], 190, 215, 1200, 760)
    d.v("az-a", "Availability Zone A (ap-northeast-2a)", STY["az"], 215, 250, 560, 700)
    d.v("az-c", "Availability Zone C (ap-northeast-2c)", STY["az"], 815, 250, 560, 700)
    # subnets: (x, y, w, h)
    for az, x in (("a", 230), ("c", 830)):
        cidr_pub = "10.0.0.0/24" if az == "a" else "10.0.1.0/24"
        cidr_web = "10.0.10.0/24" if az == "a" else "10.0.11.0/24"
        cidr_was = "10.0.20.0/24" if az == "a" else "10.0.21.0/24"
        cidr_db = "10.0.30.0/24" if az == "a" else "10.0.31.0/24"
        d.v(f"sub-pub-{az}", f"Public subnet {az.upper()} · {cidr_pub}", STY["pub"], x, 280, 530, 150)
        d.v(f"sub-web-{az}", f"Private subnet WEB-{az.upper()} · {cidr_web}", STY["priv"], x, 445, 530, 160)
        d.v(f"sub-was-{az}", f"Private subnet WAS-{az.upper()} · {cidr_was}", STY["priv"], x, 620, 530, 160)
        d.v(f"sub-db-{az}", f"Private subnet DB-{az.upper()} · {cidr_db}{az_extra}", STY["priv"], x, 795, 530, 140)
    # user + igw
    d.v("user", "사용자", f"sketch=0;outlineConnect=0;fontColor=#232F3E;gradientColor=none;fillColor=#232F3D;strokeColor=none;dashed=0;verticalLabelPosition=bottom;verticalAlign=top;align=center;html=1;fontSize=11;fontStyle=0;aspect=fixed;shape=mxgraph.aws4.users;{FONT}", 40, 300, 56, 56)
    d.v("igw", "Internet Gateway", f"sketch=0;{PTS};outlineConnect=0;fontColor=#232F3E;fillColor=#8C4FFF;strokeColor=#ffffff;dashed=0;verticalLabelPosition=bottom;verticalAlign=top;align=center;html=1;fontSize=10;aspect=fixed;shape=mxgraph.aws4.resourceIcon;resIcon=mxgraph.aws4.internet_gateway;{FONT}", 770, 165, 44, 44)


def legend(d, x, y, w, title, rows, color="#0B5394"):
    h = 60 + 26 * len(rows)
    d.v("legend", "", f"rounded=1;whiteSpace=wrap;html=1;fillColor=#F3F6FB;strokeColor={color};strokeWidth=1.5;{FONT}", x, y, w, h)
    d.text("legend-t", title, x + 14, y + 10, w - 28, 26, size=14, bold=True, color=color)
    body = "".join(f"<div style='margin:3px 0'>{r}</div>" for r in rows)
    d.text("legend-b", body, x + 14, y + 42, w - 28, h - 50, size=11)


# ===================== 1. As-Is (kdt5) =====================
a = D("As-Is · kdt5 계정 현재 구축 상태", 2000, 1100)
frame(a, "현재 구축 상태 (As-Is) — kdt5 계정 · 2026-09-15 조회",
      "VPC test-vpc · 서브넷 8 · NAT AZ당 1 · Public ALB 1 · WEB 1 · WAS 1 · Bastion 1  |  붉은 점선 = Phase 1에 필요하지만 없거나 연결이 끊긴 것",
      "VPC test-vpc · 10.0.0.0/16")
# public A: bastion + NAT ; public C: NAT
a.svc("nat-a", "NAT Gateway", "test-nat-public1", "nat_gateway", "net", 250, 300)
a.svc("bastion", "Bastion (설계 밖)", "bas-server<br>t3.micro · 13.124.251.253<br>22/80/443 ← 0.0.0.0/0", "ec2", "sec", 400, 300)
a.svc("nat-c", "NAT Gateway", "test-nat-public2", "nat_gateway", "net", 850, 300)
# Public ALB spanning (draw in the middle between AZ)
a.svc("alb-pub", "Public ALB", "test-Public-ALB<br>internet-facing · :80<br>SG 80/443 ← 0.0.0.0/0", "application_load_balancer", "net", 620, 300)
# WEB
a.svc("web-a", "WEB", "WEB-test-a<br>AL2023 · t3.micro · 10.0.10.51<br>Apache 2.4.68 · index.html", "ec2", "compute", 250, 465)
a.svc("web-c", "WEB-C 없음", "AZ-C 미구축", "ec2", "compute", 850, 465, missing=True)
# Internal ALB missing (between WEB and WAS)
a.svc("alb-int", "Internal ALB 없음", "tg-internal-alb만 존재<br>(어느 ALB에도 미연결 · unused)", "application_load_balancer", "net", 620, 550, missing=True)
# WAS
a.svc("was-a", "WAS", "WAS-test-a<br>AL2023 · t3.micro · 10.0.20.235<br>SG 8080/443 ← 0.0.0.0/0", "ec2", "compute", 250, 640)
a.svc("was-c", "WAS-C 없음", "AZ-C 미구축", "ec2", "compute", 850, 640, missing=True)
# DB missing
a.svc("rds-a", "RDS 없음", "미구현", "rds", "db", 250, 810, missing=True)
a.svc("rds-c", "RDS Standby 없음", "미구현", "rds", "db", 850, 810, missing=True)
# edges
a.edge("e1", "user", "igw", label="HTTP (도메인 없음 · ALB DNS 직접)", pts=[(68, 187)], exit=(0.5, 0), entry=(0, 0.5), lx=-0.2)
a.edge("e2", "igw", "grp-alb-pub", exit=(0.5, 1), entry=(0.5, 0))
a.edge("e3", "grp-alb-pub", "grp-web-a", label="tg: Targetgroup-web · :80 · 헬스체크 / · healthy", pts=[(685, 450), (315, 450)], exit=(0.5, 1), entry=(0.5, 0), lx=0.1)
a.edge("e4", "grp-web-a", "grp-alb-int", EDGE_BROKEN, label="/petclinic/ → Apache 404 (ProxyPass 없음)", pts=[(315, 600), (685, 600)], exit=(0.5, 1), entry=(0.5, 0), lx=0.1)
a.edge("e5", "grp-alb-int", "grp-was-a", EDGE_BROKEN, label="tg-internal-alb :8080 (미연결)", pts=[(685, 700), (400, 700)], exit=(0.5, 1), entry=(1, 0.5), lx=0.2)
a.edge("e6", "grp-was-a", "grp-rds-a", EDGE_BROKEN, label="DB 없음", exit=(0.5, 1), entry=(0.5, 0))
a.edge("e7", "grp-bastion", "grp-web-a", EDGE_BI, label="SSH 22 (test-key)", pts=[(465, 435), (400, 435)], exit=(0.5, 1), entry=(1, 0.3), lx=0.6, ly=12)
# notes
a.note("n1", "<b>WEB → WAS 연동 현황</b><br>사용자 → Public ALB → Apache까지는 200(index.html). <b>/petclinic/ 는 Apache가 404</b> — ProxyPass · ProxyPreserveHost 없음, 내부 ALB 없음. WAS Tomcat 상태는 확인 불가(SSM 미등록 · 키 없음).",
       1460, 300, 470, 120)
a.note("n2", "<b>보안 설정 차이</b><br>• was-instance-sg 8080·443 ← 0.0.0.0/0, web-instance-sg 80 ← 0.0.0.0/0 (앞 단계 SG만 허용해야 함)<br>• EC2 3대 모두 IAM 프로파일 없음 → SSM·CloudWatch·Secrets 불가 (mc-ec2-role은 만들어져 있음)<br>• Bastion + 22번 + test-key: 설계는 SSM으로 대체<br>• DB 서브넷 라우팅이 NAT로 나감 (설계: local만)",
       1460, 440, 470, 170)
a.note("n3", "<b>없는 것</b><br>Internal ALB · WEB-C · WAS-C · RDS(Multi-AZ) · AMI v1 · Route 53 호스팅 존 · health.html · test.jsp<br><b>다른 것</b><br>WAS/WEB이 AL2023 · t3.micro (Blue 컨셉은 AL2 · 구버전, 빌드엔 t3.medium 필요) · 헬스체크 경로 / (설계: WEB /health.html · WAS /petclinic/) · EIP 4개(2개 용도 불명)",
       1460, 630, 470, 200, color="#0B5394")
legend(a, 1460, 850, 470, "범례", ["■ 실선 = 현재 동작하는 경로", "<span style='color:#D32F2F'>■ 붉은 점선 = 끊겨 있거나 없는 구성</span>", "■ 점선 양방향 = 운영자 접속(SSH)"])
a.write("/home/grapefruit/middleproject/docs/architecture-asis-kdt5.drawio")

# ===================== 2. Phase 1 target =====================
t = D("Phase 1 목표 · Blue", 2000, 1100)
frame(t, "Phase 1 목표 아키텍처 (Blue) — 구버전 PetClinic 그대로 3-Tier",
      "Route 53 → Public ALB → Apache(ProxyPass) → Internal ALB → Tomcat 9.0.53 · OpenJDK 8 · Spring 5.3.9 (main) → RDS MySQL Multi-AZ  |  22번 없음 · SSM 접속 · AMI v1 = Phase 2 롤백 지점",
      "VPC mc-vpc · 10.0.0.0/16")
t.svc("nat-a", "NAT Gateway", "mc-nat-a<br>아웃바운드 전용", "nat_gateway", "net", 250, 300)
t.svc("nat-c", "NAT Gateway", "mc-nat-c", "nat_gateway", "net", 850, 300)
t.svc("alb-pub", "Public ALB", "mc-alb-public · :80<br>tg-web · 헬스체크 /health.html<br>SG: 팀 IP 또는 0.0.0.0/0+WAF", "application_load_balancer", "net", 620, 300)
t.svc("web-a", "WEB", "mc-web-a · AL2 · t3.small<br>Apache 2.4 · index.html<br>ProxyPass /petclinic/ → 내부 ALB", "ec2", "compute", 250, 465)
t.svc("web-c", "WEB", "mc-web-c (AMI v1 복제)<br>SG 80 ← sg-alb-public", "ec2", "compute", 850, 465)
t.svc("alb-int", "Internal ALB", "mc-alb-internal · :8080<br>tg-was · 헬스체크 /petclinic/<br>등록 취소 30s", "application_load_balancer", "net", 620, 550)
t.svc("was-a", "WAS", "mc-was-a · AL2 · t3.medium<br>OpenJDK 8 · Tomcat 9.0.53<br>PetClinic main · test.jsp", "ec2", "compute", 250, 640)
t.svc("was-c", "WAS", "mc-was-c (AMI v1 복제)<br>SG 8080 ← sg-alb-internal", "ec2", "compute", 850, 640)
t.svc("rds-a", "RDS MySQL 8 Primary", "mc-petclinic · db.t3.small<br>Multi-AZ · 암호화<br>관리형 비밀(Secrets Manager)", "rds", "db", 250, 810)
t.svc("rds-c", "RDS Standby", "동기 복제 · 자동 failover", "rds", "db", 850, 810)
# route53 + ssm + secrets outside VPC
t.svc("r53", "DNS", "Route 53<br>petclinic.mission-critical.site<br>A 별칭 → Public ALB", "route_53", "net", 30, 400)
t.svc("ssm", "운영자 접속", "SSM Session Manager<br>22번 · 키페어 없음<br>mc-ec2-role", "systems_manager", "sec", 30, 560)
t.svc("secrets", "DB 자격증명", "Secrets Manager<br>rds!db-… · 빌드 시 주입", "secrets_manager", "sec", 30, 720)
t.edge("e0", "user", "grp-r53", label="도메인 조회", exit=(0.5, 1), entry=(0.5, 0))
t.edge("e1", "user", "igw", label="HTTP", pts=[(68, 187)], exit=(0.5, 0), entry=(0, 0.5), lx=-0.2)
t.edge("e2", "igw", "grp-alb-pub", exit=(0.5, 1), entry=(0.5, 0))
t.edge("e3a", "grp-alb-pub", "grp-web-a", label="tg-web · 두 AZ 분산", pts=[(685, 450), (315, 450)], exit=(0.5, 1), entry=(0.5, 0), lx=0.1)
t.edge("e3c", "grp-alb-pub", "grp-web-c", pts=[(685, 450), (915, 450)], exit=(0.5, 1), entry=(0.5, 0))
t.edge("e4a", "grp-web-a", "grp-alb-int", label="ProxyPass /petclinic/ · ProxyPreserveHost On", pts=[(315, 600), (685, 600)], exit=(0.5, 1), entry=(0.5, 0), lx=0.1)
t.edge("e4c", "grp-web-c", "grp-alb-int", pts=[(915, 600), (685, 600)], exit=(0.5, 1), entry=(0.5, 0))
t.edge("e5a", "grp-alb-int", "grp-was-a", label="tg-was :8080", pts=[(685, 700), (400, 700)], exit=(0.5, 1), entry=(1, 0.5), lx=0.2)
t.edge("e5c", "grp-alb-int", "grp-was-c", pts=[(685, 700), (830, 700)], exit=(0.5, 1), entry=(0, 0.5))
t.edge("e6a", "grp-was-a", "grp-rds-a", label="JDBC 3306 (빌드 시 -Djdbc.* 주입)", exit=(0.5, 1), entry=(0.5, 0), lx=0.2, ly=-16)
t.edge("e6c", "grp-was-c", "grp-rds-a", pts=[(915, 782), (420, 782)], exit=(0.5, 1), entry=(1, 0.5))
t.edge("e7", "grp-rds-a", "grp-rds-c", EDGE_BI, label="동기 복제 (Multi-AZ)", exit=(1, 0.5), entry=(0, 0.5))
t.edge("e8", "grp-ssm", "grp-was-a", EDGE_BI, label="세션", exit=(1, 0.5), entry=(0, 0.5))
t.edge("e9", "grp-secrets", "grp-was-a", EDGE_BI, label="부팅 시 조회", pts=[(200, 779), (200, 720)], exit=(1, 0.5), entry=(0, 0.7))
t.note("n1", "<b>Phase 1 원칙</b><br>• 앱 코드 무수정 — 제공본 <code>main</code> 그대로 (Spring 5.3.9 · Spring4Shell 존재 = Phase 2 근거)<br>• DB 접속정보는 빌드 시점 <code>mvnw -Djdbc.*</code> 주입 (런타임 주입은 이 앱에서 무시됨)<br>• WEB/WAS 퍼블릭 IP 없음 · 22번 없음 · Bastion 없음 (SSM)<br>• Public ALB SG는 팀 IP만 또는 0.0.0.0/0 + 리전 WAF<br>• 완성본 AMI v1 = Phase 2 롤백 지점",
       1460, 300, 470, 190, color="#0B5394")
t.note("n2", "<b>SG 체인 (소스 = 앞 단계 SG)</b><br>sg-alb-public 80 ← 팀 IP / 0.0.0.0/0<br>sg-web 80 ← sg-alb-public<br>sg-alb-internal 8080 ← sg-web<br>sg-was 8080 ← sg-alb-internal<br>sg-rds 3306 ← sg-was<br>22번 · 0.0.0.0/0 규칙 없음",
       1460, 510, 470, 160, color="#0B5394")
t.note("n3", "<b>완료 기준</b><br>• 도메인으로 점검표 5장(조회/등록/수정/vets.json/oups)<br>• test.jsp: OpenJDK 1.8 · Tomcat 9.0.53 · DB OK · vets 6행, 새로고침마다 WAS-A/C 교대<br>• 4대 healthy · AMI mc-web-v1 · mc-was-v1<br>• trivy: CVE-2022-22965 캡처 (Before)",
       1460, 690, 470, 150, color="#0B5394")
legend(t, 1460, 860, 470, "범례", ["■ 실선 = 요청 흐름 (사용자 → DB)", "■ 점선 양방향 = 복제 · 운영 접속 · 비밀 조회", "As-Is 대비 추가: Internal ALB · WEB-C · WAS-C · RDS · Route 53 · SSM · Secrets · AMI v1"])
t.write("/home/grapefruit/middleproject/docs/architecture-phase1-target.drawio")
