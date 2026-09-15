"""kdt5 계정 infra/terraform-kdt5: 콘솔 구축본(그대로 · 회색) + 코드 신규(색) + database-1 import(보라 점선) + 수동 후속 ⓜ1~7(노란 배지).
실행: python3 docs/architecture-kdt5-terraform.py [--png] → docs/architecture-kdt5-terraform.drawio / .png"""
import html as _html, json, os, subprocess, sys
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(__file__))
PTS = "points=[[0,0,0],[0.25,0,0],[0.5,0,0],[0.75,0,0],[1,0,0],[0,1,0],[0.25,1,0],[0.5,1,0],[0.75,1,0],[1,1,0],[0,0.25,0],[0,0.5,0],[0,0.75,0],[1,0.25,0],[1,0.5,0],[1,0.75,0]]"
GPTS = "points=[[0,0],[0.25,0],[0.5,0],[0.75,0],[1,0],[1,0.25],[1,0.5],[1,0.75],[1,1],[0.75,1],[0.5,1],[0.25,1],[0,1],[0,0.75],[0,0.5],[0,0.25]]"
FONT = "fontFamily=Helvetica;"
CAT = {"net": ("#EDE7F6", "#8C4FFF"), "compute": ("#FFF2E8", "#ED7100"), "db": ("#F5E6F7", "#C925D1"), "sec": ("#FFEBEE", "#DD344C"),
       "stor": ("#E8F5E9", "#1B8B3B"), "ops": ("#FFEBEE", "#E7157B"), "gen": ("#F5F5F5", "#666666"), "opt": ("#FAFAFA", "#9E9E9E"), "exist": ("#F4F4F4", "#7B7B7B"), "imp": ("#F3E5F5", "#7B1FA2")}
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




# 배지(수동 후속)
def badge(cid, n, x, y, w=150):
    d.v(cid, f"ⓜ{n}", f"ellipse;whiteSpace=wrap;html=1;fillColor=#FFD54F;strokeColor=#F57F17;strokeWidth=2;fontStyle=1;fontSize=12;fontColor=#4E342E;{FONT}", x, y, 30, 30)

d = D("kdt5 · infra/terraform-kdt5 (구축본 그대로 + 코드 추가 + 수동 후속)", 2820, 1460)
d.text("title", "kdt5 계정 — infra/terraform-kdt5: 콘솔 구축본(WEB·WAS·VPC·ALB)은 그대로 두고, 도면 ①④⑤ 계층을 코드로 얹기 + 수동 후속 ⓜ1~7", 40, 20, 2200, 40, size=26, bold=True)
d.text("subtitle", "회색 = 콘솔 구축본(코드는 data 로 읽기만) · 색 박스 = Terraform 신규 · 보라 점선 = database-1 import 편입 · 노란 배지 ⓜ = 코드가 못 건드리는 기존 리소스에서 콘솔로 해야 할 후속 (오른쪽 아래 목록)  |  코드만 · apply 안 함",
       40, 60, 2300, 30, size=13, color="#555555")
d.v("cloud", "AWS Cloud · 723165663216 (kdt5) · profile kdt5-tf(credential_process)", STY["cloud"], 40, 110, 2740, 1290)

# ---- ① Edge (new) ----
d.v("edge", "① 진입 계층 — 전부 코드 신규 (edge.tf · alb.tf · security.tf)", "fillColor=none;strokeColor=#8C4FFF;dashed=1;verticalAlign=top;align=left;spacingLeft=8;fontStyle=1;fontSize=12;fontColor=#8C4FFF;whiteSpace=wrap;html=1;" + FONT, 70, 150, 480, 1000)
d.v("user", "사용자<br>https://&lt;domain_name&gt;/petclinic/", f"sketch=0;outlineConnect=0;fontColor=#232F3E;fillColor=#232F3D;strokeColor=none;dashed=0;verticalLabelPosition=bottom;verticalAlign=top;align=center;html=1;fontSize=11;aspect=fixed;shape=mxgraph.aws4.users;{FONT}", 100, 190, 56, 56)
d.svc("r53", "Route 53 (신규 존)", "zone = hosted_zone_name<br>A/AAAA alias → CloudFront<br>ACM 검증 CNAME", "route_53", "net", 250, 180, w=150)
badge("b1", 1, 385, 170)
d.svc("acm", "ACM ×2", "cloudfront: us-east-1<br>alb: 서울(443 리스너)<br>DNS 검증", "certificate_manager", "sec", 410, 180, w=130)
d.svc("waf", "WAF v2 (CLOUDFRONT)", "mc-web-acl · 관리형 3종<br>rate-all 2000 · rate-booking 100<br>loadgen 허용 · 로그 → aws-waf-logs-mc", "waf", "sec", 100, 340, w=200, h=130)
d.svc("cf", "CloudFront", "origin: test-Public-ALB DNS (HTTPS · X-Origin-Verify)<br>origin: S3 점검(OAC) · 오리진 그룹 failover<br>Behavior: resources 캐시 / maintenance / 기본", "cloudfront", "net", 320, 340, w=210, h=130)
d.svc("s3-maint", "S3 점검 페이지", "mc-maintenance-723165663216<br>maintenance.html · OAC 전용", "simple_storage_service", "stor", 100, 500, w=200, h=110)
d.svc("kms", "KMS CMK", "alias/mc-cmk · S3·SNS·Logs·Backup<br>(RDS·비밀은 AWS 관리형 키 그대로)", "key_management_service", "sec", 320, 500, w=210, h=110)
d.note("edge-why", "<b>왜 코드가 여기만 만드나</b><br>진입 계층은 kdt5 에 아무것도 없었음(Route 53·ACM·CloudFront·WAF·S3 0개). 기존 Public ALB 는 그대로 두고 <b>443 리스너 + X-Origin-Verify 규칙</b>과 <b>SG 규칙</b>만 코드가 붙임 → CloudFront 만 통과, ALB DNS 직접 접근은 403", 100, 640, 430, 120)
d.note("edge-var", "<b>입력 변수</b> domain_name · hosted_zone_name · origin_verify_secret(민감) · loadgen_cidrs · alert_emails · enable_grafana<br><b>existing</b>(기본값 = 9/15 kdt5 확인값): test-vpc · 서브넷 8 이름 · test-Public-ALB · alb-internal-test · Targetgroup-web · tg-internal-alb · SG 4 · mc-ec2-role · database-1 · petclinic-db-subnet-group", 100, 780, 430, 150)
d.note("edge-out", "<b>outputs</b> app_url · cloudfront_domain · route53_name_servers(ⓜ1) · rds_proxy_endpoint · was_jdbc_url(ⓜ5) · rds_master_secret_arn · sns_alerts_topic_arn · buckets · <b>manual_followups</b>(ⓜ1~7)", 100, 950, 430, 110)

# ---- VPC (existing) ----
d.v("region", "ap-northeast-2", STY["region"], 580, 150, 1560, 1000)
d.v("vpc", "VPC test-vpc · 10.0.0.0/16 (콘솔 구축본 · data.aws_vpc) — 서브넷 8 · NAT ×2 · IGW 그대로", STY["vpc"], 600, 200, 1520, 930)
d.v("az-a", "ap-northeast-2a", STY["az"], 620, 235, 740, 880)
d.v("az-c", "ap-northeast-2c", STY["az"], 1370, 235, 740, 880)
for az, x, i in (("a", 635, 0), ("c", 1385, 1)):
    n = {"a": ("public1", "private1", "private3", "private5"), "c": ("public2", "private2", "private4", "private6")}[az]
    d.v(f"sub-pub-{az}", f"test-subnet-{n[0]}-ap-northeast-2{az} · 10.0.{i}.0/24", STY["pub"], x, 265, 710, 170)
    d.v(f"sub-web-{az}", f"test-subnet-{n[1]}-ap-northeast-2{az} · 10.0.1{i}.0/24 (WEB)", STY["priv"], x, 450, 710, 165)
    d.v(f"sub-was-{az}", f"test-subnet-{n[2]}-ap-northeast-2{az} · 10.0.2{i}.0/24 (WAS)", STY["priv"], x, 630, 710, 165)
    d.v(f"sub-db-{az}", f"test-subnet-{n[3]}-ap-northeast-2{az} · 10.0.3{i}.0/24 (DB)", STY["priv"], x, 810, 710, 290)
d.v("igw", "igw-05f4…", f"sketch=0;{PTS};outlineConnect=0;fontColor=#232F3E;fillColor=#7B7B7B;strokeColor=#ffffff;dashed=0;verticalLabelPosition=bottom;verticalAlign=top;align=center;html=1;fontSize=10;aspect=fixed;shape=mxgraph.aws4.resourceIcon;resIcon=mxgraph.aws4.internet_gateway;{FONT}", 1343, 165, 44, 44)

# public (existing)
d.svc("nat-a", "NAT Gateway", "nat-054321… (그대로)", "nat_gateway", "exist", 655, 285, w=140)
d.svc("bastion", "bas-server", "t3.micro · 13.124.251.253<br>임시 접속용 (SSM 전환 후 정리)", "ec2", "exist", 810, 285, w=170)
d.svc("web-ami", "web-ami (AMI 빌더)", "t2.medium · AMI web-appache<br>ⓜ4 CW Agent 넣고 AMI v2", "ec2", "exist", 995, 285, w=170)
badge("b4a", 4, 1140, 275)
d.svc("alb-pub", "Public ALB test-Public-ALB", "그대로 + <b>코드: 443 리스너(ACM) · 규칙 X-Origin-Verify → Targetgroup-web · 기본 403</b><br>기존 80 리스너 · SG 80/443 0.0.0.0/0 은 ⓜ6 에서 삭제 · 액세스 로그 ⓜ2", "application_load_balancer", "exist", 1180, 285, w=360, h=125)
badge("b2a", 2, 1515, 275); badge("b6", 6, 1515, 305)
d.svc("nat-c", "NAT Gateway", "nat-04c67d… (그대로)", "nat_gateway", "exist", 1945, 285, w=140)
# web (existing)
d.v("asg-web", "ASG web-test · min 2 / desired 2 / max 4 · CPU 60% · LT web(AMI web-appache · t2.small) — 콘솔 구축본 그대로", "fillColor=none;strokeColor=#7B7B7B;dashed=1;dashPattern=8 4;strokeWidth=2;verticalAlign=top;align=left;spacingLeft=8;fontStyle=1;fontSize=11;fontColor=#555555;whiteSpace=wrap;html=1;" + FONT, 650, 470, 1440, 135)
d.svc("web-a", "ASG-Web (Apache)", "10.0.10.237 · t2.small<br>ⓜ3 프로파일 · ⓜ4 CW Agent", "ec2", "exist", 670, 490, w=200, h=110)
badge("b3a", 3, 845, 480)
d.svc("web-test-a", "WEB-test-a (Apache)", "10.0.10.51 · t3.micro · 수동 구축<br>ProxyPass /petclinic/ → alb-internal-test", "ec2", "exist", 890, 490, w=230, h=110)
d.svc("web-c", "ASG-Web (Apache)", "10.0.11.135 · t2.small<br>Targetgroup-web healthy ×3", "ec2", "exist", 1770, 490, w=200, h=110)
# was (existing)
d.svc("was-a", "WAS-test-a (Tomcat 9.0.121 · OpenJDK 8)", "10.0.20.235 · t3.micro · ~/tomcat 수동 기동 · H2 인메모리<br>ⓜ3 프로파일 · ⓜ4 CW Agent · <b>ⓜ5 JDBC → RDS Proxy 재빌드</b>", "ec2", "exist", 670, 650, w=330, h=120)
badge("b3b", 3, 975, 640); badge("b5", 5, 975, 675)
d.svc("alb-int", "Internal ALB alb-internal-test", "그대로 · 리스너 80 → tg-internal-alb :8080 /petclinic/<br>알람 mc-was-unhealthy-host 가 arn_suffix 참조 · 액세스 로그 ⓜ2", "application_load_balancer", "exist", 1180, 650, w=360, h=120)
badge("b2b", 2, 1515, 640)
d.note("was-note", "AZ C 에 WAS 없음 (콘솔 구축본 기준). 코드는 WAS 를 만들지 않음 — ASG·AMI 는 팀이 콘솔로", 1770, 660, 300, 60, color="#7B7B7B", fill="#F4F4F4")
# db
d.svc("rds", "RDS database-1 (import 편입)", "MySQL 8.0.44 · db.t3.small · Multi-AZ · 200GB gp3<br>코드 보강: mc-mysql80(TLS 강제·utf8mb4) · 백업 7일 · 삭제 방지<br>ⓜ7 재부팅으로 파라미터 적용", "rds", "imp", 670, 835, w=330, h=125)
badge("b7", 7, 975, 825)
d.svc("pg", "파라미터 그룹 (신규)", "mc-mysql80 · family mysql8.0<br>require_secure_transport=1", "rds", "db", 1020, 835, w=180, h=125)
d.svc("proxy", "RDS Proxy (신규)", "mc-rds-proxy · require_tls · SECRETS 인증<br>DB 서브넷 ×2 · SG mc-sg-rds-proxy 3306 ← was-instance-sg", "rds_proxy", "db", 1220, 835, w=320, h=125)
d.svc("sg-db", "petclinic-db-sg (그대로)", "3306 ← was-instance-sg (기존)<br>+ <b>코드: 3306 ← mc-sg-rds-proxy</b><br>ⓜ5 뒤 기존 규칙 삭제", "network_access_control_list", "exist", 670, 975, w=330, h=115)
d.svc("rds-c", "RDS Standby", "Multi-AZ 동기 복제 (그대로)", "rds", "imp", 1770, 835, w=200, h=125)
d.svc("proxy-c", "RDS Proxy ENI", "vpc_subnet_ids = DB 서브넷 ×2", "rds_proxy", "db", 1990, 835, w=110, h=125)
d.note("db-why", "<b>왜 import</b> — 파라미터 그룹·백업·삭제 방지는 인스턴스 속성이라 data 로는 못 바꿈. imports.tf 로 편입하면 첫 plan 에 그 3가지만 update in-place 로 떠야 정상(replace 면 var.db 를 콘솔 값에 맞추고 apply 금지). 8.0→8.4 는 메이저 업그레이드 → Phase 2", 1220, 975, 750, 110, color="#7B1FA2", fill="#F3E5F5")

# ---- ⑤ Ops (new, right) ----
d.v("ops", "⑤ 운영 계층 — 전부 코드 신규 (observability.tf · kms_s3.tf · iam.tf)", "fillColor=none;strokeColor=#E7157B;dashed=1;verticalAlign=top;align=left;spacingLeft=8;fontStyle=1;fontSize=12;fontColor=#E7157B;whiteSpace=wrap;html=1;" + FONT, 2170, 150, 590, 1000)
d.svc("cwlogs", "CloudWatch Logs ×6", "/mc/web/access·error · /mc/was/catalina·access·gc<br>/mc/ssm/sessions (90일) · KMS", "cloudwatch", "ops", 2200, 190, w=270, h=115)
d.svc("cwparam", "CW Agent 설정 (SSM 파라미터)", "/mc/cwagent/web · /mc/cwagent/was<br>ⓜ4 fetch-config 로 기존 인스턴스에 적용", "systems_manager", "ops", 2485, 190, w=255, h=115)
badge("b4b", 4, 2715, 180)
d.svc("alarms", "CloudWatch 알람 ×3", "mc-was-unhealthy-host(alb-internal-test)<br>mc-alb-p95-latency(test-Public-ALB)<br>mc-rds-connections-high(database-1)", "cloudwatch", "ops", 2200, 325, w=270, h=115)
d.svc("sns", "SNS mc-alerts", "KMS · email = var.alert_emails<br>(Slack 은 Grafana Alerting)", "simple_notification_service", "ops", 2485, 325, w=255, h=115)
d.svc("trail", "CloudTrail mc-trail", "다중 리전 · 로그 검증 → S3<br>mc-cloudtrail-723165663216 (1년)", "cloudtrail", "ops", 2200, 460, w=270, h=115)
d.svc("s3-logs", "S3 mc-logs-723165663216", "alb/public · alb/internal (ⓜ2 콘솔에서 켜기)<br>was/* · web/* (인스턴스 로그)", "simple_storage_service", "stor", 2485, 460, w=255, h=115)
badge("b2c", 2, 2715, 450)
d.svc("backup", "AWS Backup", "mc-backup-vault(KMS) · mc-rds-daily<br>daily-7d → database-1", "backup", "ops", 2200, 595, w=270, h=115)
d.svc("ssm", "SSM Session Manager", "SSM-SessionManagerRunShell → /mc/ssm/sessions<br>ⓜ3 프로파일 부착돼야 접속 가능", "systems_manager", "sec", 2485, 595, w=255, h=115)
d.svc("iam", "IAM mc-ec2-role (그대로) + 인라인", "SSM Core·CW Agent 이미 부착<br><b>코드: mc-ec2-inline</b> 비밀 조회·kms·ssm 파라미터·s3 put<br>인스턴스 미부착 → ⓜ3", "identity_and_access_management", "exist", 2200, 730, w=270, h=125)
badge("b3c", 3, 2445, 720)
d.svc("secrets", "Secrets Manager (그대로)", "rds!db-0e2be729… (RDS 관리형)<br>Proxy 역할 mc-rds-proxy-role 이 조회", "secrets_manager", "exist", 2485, 730, w=255, h=125)
d.svc("grafana", "Managed Grafana (선택)", "enable_grafana=false<br>mc-ops · CLOUDWATCH", "managed_service_for_grafana", "ops", 2200, 875, w=270, h=110, optional=True)
d.note("ops-why", "<b>왜</b> 로그 5종(WAF·WEB·WAS·ALB·SSM) 중 코드가 끝까지 만드는 건 그룹·버킷·정책·설정까지. 인스턴스 안(Agent 설치)·ALB 속성(액세스 로그)은 기존 리소스라 콘솔(ⓜ2·ⓜ4)", 2485, 875, 255, 110)

# ---- 수동 후속 목록 ----
d.note("manual", "<b>수동 후속 ⓜ1~7 (output manual_followups · infra/terraform-kdt5/MANUAL-FOLLOWUPS.md)</b><br>"
       "ⓜ1 가비아 네임서버 → route53_name_servers 4개 (apply 중 ACM 검증이 이걸 기다림)<br>"
       "ⓜ2 test-Public-ALB · alb-internal-test 속성 → 액세스 로그 → s3://mc-logs-723165663216/alb/public · /alb/internal<br>"
       "ⓜ3 시작 템플릿 web 새 버전 + WAS-test-a: IAM 인스턴스 프로파일 mc-ec2-role 부착 → ASG 인스턴스 새로 고침<br>"
       "ⓜ4 WEB(AMI 빌더)·WAS: amazon-cloudwatch-agent 설치 → fetch-config -c ssm:/mc/cwagent/web|was → AMI web-appache v2<br>"
       "ⓜ5 WAS: was_jdbc_url 로 WAR 재빌드(mvnw -P MySQL -Djdbc.*) → test.jsp 에서 Ssl_cipher 확인 → petclinic-db-sg 의 3306 ← was-instance-sg 삭제<br>"
       "ⓜ6 CloudFront 로 접속 확인 후: Public ALB 80 리스너 삭제 · alb-public-sg 80/443 0.0.0.0/0 · 22 규칙 삭제 (CloudFront 프리픽스 443 만)<br>"
       "ⓜ7 database-1 재부팅(점검 시간) → mc-mysql80 적용 (apply_immediately=false 라 안 하면 월 13:01 UTC 유지관리 창)",
       580, 1170, 2180, 200, color="#F57F17", fill="#FFFDE7")

# ---- edges ----
d.edge("e0", "user", "grp-r53", label="DNS", exit=(1, 0.5), entry=(0, 0.5))
d.edge("e1", "user", "grp-cf", label="HTTPS", pts=[(128, 322), (425, 322)], exit=(0.5, 1), entry=(0.5, 0), lx=0.3)
d.edge("e1w", "grp-waf", "grp-cf", "edgeStyle=orthogonalEdgeStyle;html=1;endArrow=open;strokeColor=#DD344C;dashed=1;" + FONT, label="web_acl_id", exit=(1, 0.3), entry=(0, 0.3), ly=-8)
d.edge("e1m", "grp-cf", "grp-s3-maint", "edgeStyle=orthogonalEdgeStyle;html=1;endArrow=block;endFill=1;strokeColor=#1B8B3B;dashed=1;" + FONT, label="OAC · 5xx failover", pts=[(400, 485), (200, 485)], exit=(0.35, 1), entry=(0.5, 0), lx=0.2)
d.edge("e2", "grp-cf", "igw", label="① HTTPS 443 + X-Origin-Verify → 코드가 추가한 443 리스너", pts=[(425, 138), (1365, 138)], exit=(0.5, 0), entry=(0.5, 0), lx=0.25)
d.edge("e3", "igw", "grp-alb-pub", exit=(0.5, 1), entry=(0.5, 0))
d.edge("e4a", "grp-alb-pub", "grp-web-a", label="② Targetgroup-web :80 /health.html (그대로)", pts=[(1360, 445), (770, 445)], exit=(0.5, 1), entry=(0.5, 0), lx=0.1)
d.edge("e4b", "grp-alb-pub", "grp-web-test-a", pts=[(1360, 445), (1005, 445)], exit=(0.5, 1), entry=(0.5, 0))
d.edge("e4c", "grp-alb-pub", "grp-web-c", pts=[(1360, 445), (1870, 445)], exit=(0.5, 1), entry=(0.5, 0))
d.edge("e5a", "grp-web-a", "grp-alb-int", label="③ ProxyPass /petclinic/ → :80 (그대로)", pts=[(770, 625), (1360, 625)], exit=(0.5, 1), entry=(0.5, 0), lx=0.15)
d.edge("e5c", "grp-web-c", "grp-alb-int", pts=[(1870, 625), (1360, 625)], exit=(0.5, 1), entry=(0.5, 0))
d.edge("e6", "grp-alb-int", "grp-was-a", label="④ tg-internal-alb :8080 /petclinic/", exit=(0, 0.5), entry=(1, 0.5))
d.edge("e7", "grp-was-a", "grp-proxy", EDGE_RED, label="⑤ ⓜ5 뒤: JDBC 3306 TLS → Proxy", pts=[(835, 800), (1380, 800)], exit=(0.5, 1), entry=(0.5, 0), lx=0.1)
d.edge("e8", "grp-proxy", "grp-rds", EDGE_RED, label="⑥ 풀링 커넥션 → Primary", pts=[(1300, 822), (900, 822)], exit=(0.25, 0), entry=(0.7, 0), lx=0.2, ly=8)
d.edge("e9", "grp-rds", "grp-rds-c", EDGE_BI, label="동기 복제 (그대로)", pts=[(1000, 900), (1770, 900)], exit=(1, 0.5), entry=(0, 0.5), lx=0.6)
d.edge("e10", "grp-secrets", "grp-proxy", EDGE_BI, label="비밀 조회 (Proxy 역할)", pts=[(2150, 792), (2150, 1130), (1540, 1130)], exit=(0, 0.5), entry=(1, 0.8), lx=0.1)
d.edge("e11", "grp-alarms", "grp-sns", "edgeStyle=orthogonalEdgeStyle;html=1;endArrow=open;strokeColor=#E7157B;dashed=1;" + FONT, label="alarm_actions", exit=(1, 0.5), entry=(0, 0.5), ly=-8)
d.edge("e12", "grp-backup", "grp-rds-c", "edgeStyle=orthogonalEdgeStyle;html=1;endArrow=open;strokeColor=#E7157B;dashed=1;" + FONT, label="daily-7d", pts=[(2150, 652), (2150, 897)], exit=(0, 0.5), entry=(1, 0.5), lx=0.3)
d.text("legend", "■ 회색 박스 = 콘솔 구축본(그대로 · data) · ■ 색 박스 = Terraform 신규 · ■ 보라 점선 = import 편입 · ■ 실선 = 요청 흐름 · <span style='color:#D32F2F'>■ 붉은 실선 = ⓜ5 뒤에 생기는 DB 경로</span> · ■ 점선 = 로그·알림·백업·비밀 · ● 노란 배지 = 수동 후속 번호",
       70, 1400, 2600, 24, size=11, color="#555555")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "architecture-kdt5-terraform.drawio")
d.write(OUT)


def render(drawio, png, w=2820, h=1460):
    xml = open(drawio, encoding="utf-8").read()
    cfg = json.dumps({"xml": xml, "nav": False, "resize": True, "toolbar": "", "highlight": "#0000ff", "lightbox": False})
    html = f"<html><body style='margin:0;background:#fff'><div class='mxgraph' style='max-width:100%;border:0' data-mxgraph='{_html.escape(cfg, quote=True)}'></div><script src='https://viewer.diagrams.net/js/viewer-static.min.js'></script></body></html>"
    tmp = os.path.join(os.environ.get("SCRATCH", "/tmp"), "kdt5-render.html")
    open(tmp, "w", encoding="utf-8").write(html)
    subprocess.run(["google-chrome", "--headless=new", "--disable-gpu", "--no-sandbox", "--hide-scrollbars", "--virtual-time-budget=30000",
                    "--force-device-scale-factor=2", f"--window-size={w},{h}", f"--screenshot={png}", "file://" + tmp], check=True, capture_output=True)
    print("wrote", png)


if __name__ == "__main__" and "--png" in sys.argv:
    render(OUT, OUT.replace(".drawio", ".png"))
