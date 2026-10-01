"""modify1 브랜치 infra/terraform-phase1 (Phase 1 Blue · 코드만, 미적용) 을 리소스 이름 그대로 도면화.
실행: python3 docs/architecture-modify1-terraform.py → docs/architecture-modify1-terraform.drawio
PNG: 아래 render() 가 viewer.diagrams.net + headless Chrome 으로 docs/architecture-modify1-terraform.png 생성."""
import html as _html, json, os, subprocess, sys
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(__file__))
PTS = "points=[[0,0,0],[0.25,0,0],[0.5,0,0],[0.75,0,0],[1,0,0],[0,1,0],[0.25,1,0],[0.5,1,0],[0.75,1,0],[1,1,0],[0,0.25,0],[0,0.5,0],[0,0.75,0],[1,0.25,0],[1,0.5,0],[1,0.75,0]]"
GPTS = "points=[[0,0],[0.25,0],[0.5,0],[0.75,0],[1,0],[1,0.25],[1,0.5],[1,0.75],[1,1],[0.75,1],[0.5,1],[0.25,1],[0,1],[0,0.75],[0,0.5],[0,0.25]]"
FONT = "fontFamily=Helvetica;"
CAT = {"net": ("#EDE7F6", "#8C4FFF"), "compute": ("#FFF2E8", "#ED7100"), "db": ("#F5E6F7", "#C925D1"),
       "sec": ("#FFEBEE", "#DD344C"), "gen": ("#F5F5F5", "#666666"), "opt": ("#FAFAFA", "#9E9E9E")}
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
EDGE_RED = EDGE + "strokeColor=#D32F2F;strokeWidth=2;"
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

    def svc(self, cid, title, sub, res, cat, x, y, w=130, h=118, optional=False):
        tint, stroke = CAT["opt"] if optional else CAT[cat]
        dashed = "dashed=1;dashPattern=6 4;" if optional else ""
        self.v(f"grp-{cid}", title, f"fillColor={tint};strokeColor={stroke};rounded=1;whiteSpace=wrap;html=1;verticalAlign=top;fontStyle=1;fontSize=11;fontColor={stroke};{FONT}container=1;collapsible=0;shadow=0;strokeWidth=1.5;{dashed}", x, y, w, h)
        fill = "#9E9E9E" if optional else CAT[cat][1]
        ist = (f"sketch=0;{PTS};outlineConnect=0;fontColor=#232F3E;fillColor={fill};strokeColor=#ffffff;dashed=0;verticalLabelPosition=bottom;verticalAlign=top;align=center;html=1;fontSize=9;fontStyle=0;aspect=fixed;"
               f"shape=mxgraph.aws4.resourceIcon;resIcon=mxgraph.aws4.{res};{FONT}")
        self.v(cid, sub, ist, w // 2 - 22, 26, 44, 44, parent=f"grp-{cid}")

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

    def note(self, cid, value, x, y, w, h, color="#0B5394", fill="#F3F6FB"):
        self.v(cid, value, f"rounded=1;whiteSpace=wrap;html=1;fillColor={fill};strokeColor={color};strokeWidth=1.5;align=left;verticalAlign=top;fontSize=11;fontColor=#232F3E;spacing=8;{FONT}", x, y, w, h)

    def write(self, path):
        ET.ElementTree(self.mxfile).write(path, encoding="utf-8", xml_declaration=True); print("wrote", path)


d = D("modify1 · infra/terraform-phase1 (Phase 1 Blue)", 2060, 1120)
d.text("title", "modify1 브랜치 — infra/terraform-phase1 Terraform 아키텍처 (Phase 1 Blue · 코드만, 미적용)", 40, 20, 1600, 40, size=26, bold=True)
d.text("subtitle", "사용자 → Public ALB → Apache(index.html 없음 · / → 302 /petclinic/) → Internal ALB → Tomcat 9.0.53 · OpenJDK 8 · PetClinic main(MySQL 프로필) → RDS MySQL 8.4.11 Multi-AZ  |  terraform validate 통과 · apply 안 함",
       40, 60, 1600, 30, size=13, color="#555555")
d.v("cloud", "AWS Cloud · 계정 723165663216 (kdt5) · profile = var.aws_profile", STY["cloud"], 140, 110, 1300, 960)
d.v("region", "ap-northeast-2 · versions.tf (aws ~> 5.70 · default_tags Project/Team/Phase=1-blue)", STY["region"], 165, 145, 1250, 910)
d.v("vpc", "VPC mc-vpc · 10.0.0.0/16 · network.tf (IGW · 서브넷 8 · NAT ×2 · 라우팅 public/private-a/private-c/db)", STY["vpc"], 190, 215, 1200, 820)
d.v("az-a", "Availability Zone A (ap-northeast-2a) · var.azs[0]", STY["az"], 215, 250, 560, 760)
d.v("az-c", "Availability Zone C (ap-northeast-2c) · var.azs[1]", STY["az"], 815, 250, 560, 760)
for az, x, i in (("a", 230, 0), ("c", 830, 1)):
    d.v(f"sub-pub-{az}", f"aws_subnet.public[{i}] · 10.0.{i}.0/24 · rt-public → IGW", STY["pub"], x, 280, 530, 150)
    d.v(f"sub-web-{az}", f"aws_subnet.web[{i}] · 10.0.1{i}.0/24 · rt-private-{az} → NAT-{az}", STY["priv"], x, 445, 530, 160)
    d.v(f"sub-was-{az}", f"aws_subnet.was[{i}] · 10.0.2{i}.0/24 · rt-private-{az} → NAT-{az}", STY["priv"], x, 620, 530, 160)
    d.v(f"sub-db-{az}", f"aws_subnet.db[{i}] · 10.0.3{i}.0/24 · rt-db (local 만 · 인터넷 경로 없음)", STY["priv"], x, 795, 530, 200)
d.v("user", "사용자", f"sketch=0;outlineConnect=0;fontColor=#232F3E;gradientColor=none;fillColor=#232F3D;strokeColor=none;dashed=0;verticalLabelPosition=bottom;verticalAlign=top;align=center;html=1;fontSize=11;fontStyle=0;aspect=fixed;shape=mxgraph.aws4.users;{FONT}", 40, 300, 56, 56)
d.v("igw", "mc-igw", f"sketch=0;{PTS};outlineConnect=0;fontColor=#232F3E;fillColor=#8C4FFF;strokeColor=#ffffff;dashed=0;verticalLabelPosition=bottom;verticalAlign=top;align=center;html=1;fontSize=10;aspect=fixed;shape=mxgraph.aws4.resourceIcon;resIcon=mxgraph.aws4.internet_gateway;{FONT}", 770, 165, 44, 44)

# public
d.svc("nat-a", "NAT Gateway", "mc-nat-a · EIP<br>WEB/WAS 아웃바운드(dnf·git·Maven)", "nat_gateway", "net", 250, 300)
d.svc("bastion", "Bastion (선택)", "create_bastion=false<br>기본 미생성 · SSM 대체", "ec2", "sec", 400, 300, optional=True)
d.svc("nat-c", "NAT Gateway", "mc-nat-c · EIP", "nat_gateway", "net", 850, 300)
d.svc("alb-pub", "Public ALB", "mc-alb-public · internet-facing · :80<br>tg-web · /health.html 10/5/2/3<br>SG mc-sg-alb-public 80 ← 0.0.0.0/0", "application_load_balancer", "net", 620, 300)
# web
d.svc("web-a", "WEB", "aws_instance.web[0] · AL2023 · t3.small<br>Apache 2.4 · <b>index.html 없음</b><br>/ → 302 /petclinic/ · /health.html", "ec2", "compute", 250, 465)
d.svc("web-c", "WEB", "aws_instance.web[1] · 같은 user_data<br>SG mc-sg-web 80 ← sg-alb-public<br>퍼블릭 IP 없음 · IMDSv2", "ec2", "compute", 850, 465)
d.svc("alb-int", "Internal ALB", "mc-alb-internal · :8080<br>tg-was · /petclinic/ 10/5/2/3 · 등록취소 30s<br>SG mc-sg-alb-internal 8080 ← sg-web", "application_load_balancer", "net", 620, 550)
# was
d.svc("was-a", "WAS", "aws_instance.was[0] · AL2023 · t3.medium<br>Corretto(OpenJDK) 8 · Tomcat 9.0.53<br>main · mvnw -P MySQL -Djdbc.* · systemd", "ec2", "compute", 250, 640)
d.svc("was-c", "WAS", "aws_instance.was[1] · 같은 user_data<br>SG mc-sg-was 8080 ← sg-alb-internal<br>인스턴스 프로파일 mc-ec2-profile", "ec2", "compute", 850, 640)
# db
d.svc("rds-a", "RDS MySQL 8.4.11 Primary", "mc-petclinic · db.t3.small · gp3 20→100<br>db_name=petclinic · admin · 관리형 비밀<br>백업 7일 · 암호화 · publicly_accessible=false", "rds", "db", 250, 815, h=130)
d.svc("rds-c", "RDS Standby", "multi_az=true · 동기 복제<br>자동 failover", "rds", "db", 850, 815, h=130)
d.svc("pg", "파라미터 그룹", "mc-mysql84 (family mysql8.4)<br>character_set_server=utf8mb4<br>collation_server=utf8mb4_unicode_ci", "rds", "db", 400, 815, h=130)
d.svc("sg-rds", "SG mc-sg-rds", "3306 ← mc-sg-was 만<br>(아웃바운드 규칙 없음)", "network_access_control_list", "sec", 550, 815, h=130)
# outside vpc (left)
d.svc("ssm", "운영자 접속", "SSM Session Manager<br>22번·키페어 없음<br>NAT 경유 ssm 엔드포인트", "systems_manager", "sec", 30, 560)
d.svc("iam", "IAM (iam.tf)", "mc-ec2-role · SSM Core<br>CW Agent · 인라인: GetSecretValue<br>+ kms:Decrypt(ViaService)", "identity_and_access_management", "sec", 30, 700)
d.svc("secrets", "Secrets Manager", "rds!db-… (RDS 관리형)<br>username/password JSON<br>7일 자동 교체", "secrets_manager", "sec", 30, 840)

# edges
d.edge("e1", "user", "igw", label="HTTP · http://&lt;public_alb_dns&gt;/", pts=[(68, 187)], exit=(0.5, 0), entry=(0, 0.5), lx=-0.2)
d.edge("e2", "igw", "grp-alb-pub", exit=(0.5, 1), entry=(0.5, 0))
d.edge("e3a", "grp-alb-pub", "grp-web-a", EDGE_RED, label="① / → Apache 302 → /petclinic/ (WAS 홈)", pts=[(685, 450), (315, 450)], exit=(0.5, 1), entry=(0.5, 0), lx=0.1)
d.edge("e3c", "grp-alb-pub", "grp-web-c", pts=[(685, 450), (915, 450)], exit=(0.5, 1), entry=(0.5, 0))
d.edge("e4a", "grp-web-a", "grp-alb-int", label="② ProxyPass /petclinic/ · ProxyPreserveHost · SELinux httpd_can_network_connect", pts=[(315, 600), (685, 600)], exit=(0.5, 1), entry=(0.5, 0), lx=0.15)
d.edge("e4c", "grp-web-c", "grp-alb-int", pts=[(915, 600), (685, 600)], exit=(0.5, 1), entry=(0.5, 0))
d.edge("e5a", "grp-alb-int", "grp-was-a", label="③ tg-was :8080 /petclinic/ → welcome.jsp", pts=[(685, 700), (400, 700)], exit=(0.5, 1), entry=(1, 0.5), lx=0.2)
d.edge("e5c", "grp-alb-int", "grp-was-c", pts=[(685, 700), (830, 700)], exit=(0.5, 1), entry=(0, 0.5))
d.edge("e6a", "grp-was-a", "grp-rds-a", EDGE_RED, label="④ JDBC 3306", exit=(0.5, 1), entry=(0.5, 0), lx=0.6, ly=0)
d.edge("e6c", "grp-was-c", "grp-rds-a", pts=[(915, 795), (320, 795)], exit=(0.5, 1), entry=(0.55, 0))
d.edge("e7", "grp-rds-a", "grp-rds-c", EDGE_BI, label="동기 복제 (Multi-AZ)", pts=[(380, 960), (915, 960)], exit=(0.5, 1), entry=(0.5, 1), ly=10)
d.edge("e8", "grp-ssm", "grp-was-a", EDGE_BI, label="세션", pts=[(200, 619), (200, 660)], exit=(1, 0.5), entry=(0, 0.2))
d.edge("e9", "grp-secrets", "grp-was-a", EDGE_BI, label="부팅 시 조회 → 빌드 주입", pts=[(200, 899), (200, 740)], exit=(1, 0.5), entry=(0, 0.85), lx=0.4)
d.edge("e10", "grp-iam", "grp-was-a", "edgeStyle=orthogonalEdgeStyle;html=1;endArrow=open;strokeColor=#DD344C;dashed=1;" + FONT, label="프로파일 부착", pts=[(185, 759), (185, 720)], exit=(1, 0.5), entry=(0, 0.6), lx=0.2)

# notes (right)
d.note("n1", "<b>파일 → 리소스 (infra/terraform-phase1)</b><br>"
       "• <code>network.tf</code> VPC · IGW · 서브넷 8 · EIP/NAT ×2 · 라우팅 4<br>"
       "• <code>security.tf</code> SG 체인 (22번 규칙 없음)<br>"
       "• <code>iam.tf</code> mc-ec2-role · 인스턴스 프로파일<br>"
       "• <code>alb.tf</code> Public/Internal ALB · TG · 리스너 · 대상 등록<br>"
       "• <code>compute.tf</code> web ×2 · was ×2 (templatefile user_data) · bastion(선택)<br>"
       "• <code>rds.tf</code> 서브넷 그룹 · 파라미터 그룹 · RDS Multi-AZ<br>"
       "• <code>user_data/web.sh · was.sh</code> Apache 설정 / Tomcat·앱 빌드·DB 검증",
       1460, 300, 560, 190)
d.note("n2", "<b>SG 체인 (소스 = 앞 단계 SG)</b><br>mc-sg-alb-public 80 ← var.public_alb_ingress_cidrs (0.0.0.0/0)<br>mc-sg-web 80 ← sg-alb-public<br>mc-sg-alb-internal 8080 ← sg-web<br>mc-sg-was 8080 ← sg-alb-internal<br>mc-sg-rds 3306 ← sg-was<br>Bastion 켜면 sg-bastion 22 ← var.bastion_ssh_cidrs, web/was 22 ← sg-bastion",
       1460, 505, 560, 150)
d.note("n3", "<b>이번 커밋(933e79b)에서 바뀐 것 — 붉은 화살표</b><br>"
       "① <b>WEB</b>: Apache 자체 index.html 생성 삭제 + <code>rm -f</code>. <code>RewriteRule ^/$ /petclinic/ [R=302]</code> 로 첫 화면을 WAS(Spring welcome.jsp)가 담당. <code>ProxyPass /health.html !</code> 만 Apache 직접 응답(헬스체크)<br>"
       "④ <b>WAS→RDS</b>: Secrets Manager 계정 조회 → <code>mvnw -P MySQL -Djdbc.url/username/password</code> 빌드 주입(datasource-config.xml 이 Maven 필터링되므로 런타임 주입 불가) → RDS 3306 도달 대기 → mysql 로그인·DB 확인 → Tomcat 기동 → 앱이 schema.sql·data.sql 실행 → vets/owners/pets 건수 검증 · 자격증명 unset",
       1460, 670, 560, 210, color="#D32F2F", fill="#FFF8E1")
d.note("n4", "<b>변수 기본값 (variables.tf)</b><br>web t3.small · was t3.medium · tomcat 9.0.53 · app_repo_branch=main · db 8.4.11 db.t3.small multi_az=true · create_bastion=false<br>"
       "<b>Phase 2</b>: app_repo_branch=test · tomcat_version=9.0.121 → WAS 재생성(user_data_replace_on_change)<br>"
       "<b>outputs</b>: public_alb_dns · internal_alb_dns · rds_endpoint · rds_master_secret_arn · ssm_session_hint · db_check_hint",
       1460, 895, 560, 130)
d.text("legend", "■ 실선 = 요청 흐름 · <span style='color:#D32F2F'>■ 붉은 실선 = 이번 커밋 변경 구간</span> · ■ 점선 양방향 = 복제·운영 접속·비밀 조회 · ■ 회색 점선 박스 = 변수로 끄고 켜는 선택 리소스",
       140, 1080, 1300, 24, size=11, color="#555555")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "architecture-modify1-terraform.drawio")
d.write(OUT)


def render(drawio, png, w=2740, h=1220):
    xml = open(drawio, encoding="utf-8").read()
    cfg = json.dumps({"xml": xml, "nav": False, "resize": True, "toolbar": "", "highlight": "#0000ff", "lightbox": False})
    html = f"<html><body style='margin:0;background:#fff'><div class='mxgraph' style='max-width:100%;border:0' data-mxgraph='{_html.escape(cfg, quote=True)}'></div><script src='https://viewer.diagrams.net/js/viewer-static.min.js'></script></body></html>"
    tmp = os.path.join(os.environ.get("SCRATCH", "/tmp"), "modify1-render.html")
    open(tmp, "w", encoding="utf-8").write(html)
    subprocess.run(["google-chrome", "--headless=new", "--disable-gpu", "--no-sandbox", "--hide-scrollbars", "--virtual-time-budget=30000",
                    "--force-device-scale-factor=2", f"--window-size={w},{h}", f"--screenshot={png}", "file://" + tmp], check=True, capture_output=True)
    print("wrote", png)


if __name__ == "__main__" and "--png" in sys.argv:
    render(OUT, OUT.replace(".drawio", ".png"))
