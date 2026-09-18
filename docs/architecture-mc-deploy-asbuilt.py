"""mc-deploy 계정 As-Built (2026-09-17): infra/terraform-kdt5 create_base=true 로 apply 한 실제 리소스 ID·IP·엔드포인트 기준.
실행: python3 docs/architecture-mc-deploy-asbuilt.py [--png] → docs/architecture-mc-deploy-asbuilt.drawio / .png"""
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





d = D("mc-deploy As-Built (2026-09-17)", 2820, 1470)
d.text("title", "현재 아키텍처 As-Built — mc-deploy(528821350786) · infra/terraform-kdt5 create_base=true · 2026-09-17 (WAF 유지 · Bastion · 정적 S3 · DB 로그 → CloudWatch Logs → Firehose → S3)", 40, 20, 2400, 40, size=26, bold=True)
d.text("subtitle", "사용자 → Route 53 → CloudFront(WAF Web ACL · 정적은 S3 OAC) → Public ALB :443(X-Origin-Verify) → Apache ×2 → Internal ALB :8080 → Tomcat 9.0.121 · OpenJDK 8 · PetClinic test(Green) ×2 → RDS Proxy(TLS) → RDS MySQL 8.4.11 Multi-AZ  |  검증: / 302 → /petclinic/ 200 · vets 6 / owners 10 / pets 13 · CloudFront css Hit · ALB 직접 접근 차단",
       40, 60, 2500, 30, size=13, color="#555555")
d.v("cloud", "AWS Cloud · 528821350786 (mc-deploy) · Terraform state: infra/terraform-kdt5/terraform.tfstate", STY["cloud"], 40, 110, 2740, 1300)

# ---- ① Edge ----
d.v("edge", "① 진입 계층 (edge.tf · alb.tf · security.tf)", "fillColor=none;strokeColor=#8C4FFF;dashed=1;verticalAlign=top;align=left;spacingLeft=8;fontStyle=1;fontSize=12;fontColor=#8C4FFF;whiteSpace=wrap;html=1;" + FONT, 70, 150, 480, 1000)
d.v("user", "사용자<br>https://petclinic.mission-critical.site/", f"sketch=0;outlineConnect=0;fontColor=#232F3E;fillColor=#232F3D;strokeColor=none;dashed=0;verticalLabelPosition=bottom;verticalAlign=top;align=center;html=1;fontSize=11;aspect=fixed;shape=mxgraph.aws4.users;{FONT}", 100, 190, 56, 56)
d.svc("r53", "Route 53", "mission-critical.site · Z0299891BL9WGKOA2LW9<br>A/AAAA alias → CloudFront<br>NS 4개 가비아 위임 완료", "route_53", "net", 250, 180, w=150)
d.svc("acm", "ACM ×2 (ISSUED)", "cloudfront: us-east-1<br>alb: 서울(443 리스너)<br>DNS 검증 21분", "certificate_manager", "sec", 410, 180, w=130)
d.svc("waf", "WAF mc-web-acl (유지 · enable_waf=true)", "CloudFront 에 부착(us-east-1) · 기본 Allow<br>allow-loadgen → 관리형 3 → rate-all 2,000/5분<br>rate-booking /visits/new 100/5분<br>로그 → aws-waf-logs-mc(us-east-1)", "waf", "sec", 95, 340, w=205, h=160)
d.svc("cf", "CloudFront E2PWXW3LUYTDEE", "d2p7som2iuyba.cloudfront.net · PriceClass_200 · 오리진 4<br>/static/* /images/* → S3 mc-static(OAC)<br>/petclinic/resources/* → ALB 캐시 · * 동적 ALB<br>5xx → 503 점검 · 로그 → S3 cloudfront/", "cloudfront", "net", 310, 340, w=220, h=160)
d.svc("s3-maint", "S3 점검 · 정적 (OAC 전용)", "mc-maintenance-… · maintenance.html<br><b>mc-static-…</b> · static/resources · static/images<br>apply 가 저장소 자산 동기화 · SSE-KMS", "simple_storage_service", "stor", 100, 512, w=200, h=110)
d.svc("kms", "KMS alias/mc-cmk", "S3(점검·정적·CloudTrail) · SNS · Logs · Backup · <b>app-db 비밀</b><br>RDS 스토리지·admin 비밀은 AWS 관리형 키", "key_management_service", "sec", 320, 512, w=210, h=110)
d.note("edge-how", "<b>정적 · 동적 분리 (9/17)</b><br>• 정적 <code>/static/*</code> <code>/images/*</code>(랜딩 css·이미지·hero.mp4): CloudFront → <b>S3 mc-static(OAC)</b> · CachingOptimized 1일 → Hit 면 엣지, Miss 면 S3 — <b>Apache 를 안 거침</b><br>• <code>/petclinic/resources/*</code>(WAR 안): 오리진 그룹(ALB) 캐시 · AllViewer 로 Host 전달<br>• 동적 <code>*</code>: CachingDisabled + AllViewer → 매번 ALB → Apache → Internal ALB → Tomcat<br>• WAF 는 팀 결정으로 유지 — Web ACL 은 캐시 조회보다 먼저 평가, 차단은 캐시·오리진 미도달. Phase 3 전 loadgen IP set 에 JMeter IP", 100, 640, 430, 170)
d.note("edge-sec", "<b>오리진 보호</b> Public ALB SG 인바운드 = CloudFront origin-facing 프리픽스 443 만 · 리스너 기본 403 · 규칙10: X-Origin-Verify 헤더 일치 → mc-tg-web. 80 리스너 없음. ALB DNS 직접 curl → 타임아웃(차단) 확인", 100, 830, 430, 110)
d.note("edge-out", "<b>outputs</b> app_url · cloudfront_domain d2p7som2iuyba.cloudfront.net · public_alb_dns mc-alb-public-485062926.ap-northeast-2.elb.amazonaws.com · rds_proxy_endpoint · was_jdbc_url · rds_master_secret_arn(rds!db-ffb62b33…) · sns_alerts_topic_arn", 100, 960, 430, 120)

# ---- VPC ----
d.v("region", "ap-northeast-2", STY["region"], 580, 150, 1560, 1000)
d.v("vpc", "VPC mc-vpc · 10.0.0.0/16 (modules/base/network.tf) — 서브넷 8 · mc-igw · mc-nat-a/c · rt public / private-a / private-c / db(local 만)", STY["vpc"], 600, 200, 1520, 930)
d.v("az-a", "ap-northeast-2a", STY["az"], 620, 235, 740, 880)
d.v("az-c", "ap-northeast-2c", STY["az"], 1370, 235, 740, 880)
for az, x, i in (("a", 635, 0), ("c", 1385, 1)):
    d.v(f"sub-pub-{az}", f"mc-public-{az} · 10.0.{i}.0/24 · rt-public → IGW", STY["pub"], x, 265, 710, 170)
    d.v(f"sub-web-{az}", f"mc-web-{az} · 10.0.1{i}.0/24 · rt-private-{az} → NAT-{az}", STY["priv"], x, 450, 710, 165)
    d.v(f"sub-was-{az}", f"mc-was-{az} · 10.0.2{i}.0/24 · rt-private-{az} → NAT-{az}", STY["priv"], x, 630, 710, 165)
    d.v(f"sub-db-{az}", f"mc-db-{az} · 10.0.3{i}.0/24 · rt-db (인터넷 경로 없음)", STY["priv"], x, 810, 710, 290)
d.v("igw", "mc-igw", f"sketch=0;{PTS};outlineConnect=0;fontColor=#232F3E;fillColor=#8C4FFF;strokeColor=#ffffff;dashed=0;verticalLabelPosition=bottom;verticalAlign=top;align=center;html=1;fontSize=10;aspect=fixed;shape=mxgraph.aws4.resourceIcon;resIcon=mxgraph.aws4.internet_gateway;{FONT}", 1343, 165, 44, 44)

d.svc("nat-a", "NAT Gateway", "mc-nat-a · EIP<br>dnf · git · Maven 아웃바운드", "nat_gateway", "net", 655, 285, w=170)
d.svc("bastion", "Bastion mc-bastion (SSM 대신)", "t3.micro · EIP 52.78.145.87 · 키 mc-ssh<br>SG 22 ← 운영자 공인 IP /32 만<br>같은 키로 WEB·WAS 22 · Proxy 3306 · sshd 로그 → CW", "ec2", "ops", 840, 285, w=320, h=125)
d.svc("alb-pub", "Public ALB mc-alb-public", "internet-facing · :443 HTTPS(ACM) · 기본 403<br>규칙 X-Origin-Verify → mc-tg-web :80 /health.html 10s·2/3<br>SG mc-sg-alb-public 443 ← CloudFront 프리픽스 · 액세스 로그 → S3 mc-logs/alb/public", "application_load_balancer", "net", 1180, 285, w=360, h=125)
d.svc("nat-c", "NAT Gateway", "mc-nat-c · EIP", "nat_gateway", "net", 1935, 285, w=170)
d.v("web-tier", "WEB ×2 (EC2 고정 · ASG 는 base.enable_asg 옵션 — 로드맵)", "fillColor=none;strokeColor=#ED7100;dashed=1;dashPattern=8 4;strokeWidth=2;verticalAlign=top;align=left;spacingLeft=8;fontStyle=1;fontSize=11;fontColor=#ED7100;whiteSpace=wrap;html=1;" + FONT, 650, 470, 1440, 135)
d.svc("web-a", "mc-web-a (Apache 2.4)", "i-01a195cff8acb28d8 · t3.small · AL2023 · 키 mc-ssh<br>index.html + /static/ = test WAR 소스 복사(Apache 직접) · / 200<br>ProxyPass /petclinic/ → Internal ALB · Alias /images · /health.html<br><b>로그는 서버에 안 둠</b> → CW Agent → CloudWatch Logs", "ec2", "compute", 670, 490, w=330, h=110)
d.svc("web-c", "mc-web-c (Apache 2.4)", "i-01d1734d081d8bc57 · t3.small · 같은 user_data<br>SG mc-sg-web 80 ← sg-alb-public · 22 ← sg-bastion", "ec2", "compute", 1760, 490, w=310, h=110)
d.v("was-tier", "WAS ×2 (EC2 고정)", "fillColor=none;strokeColor=#ED7100;dashed=1;dashPattern=8 4;strokeWidth=2;verticalAlign=top;align=left;spacingLeft=8;fontStyle=1;fontSize=11;fontColor=#ED7100;whiteSpace=wrap;html=1;" + FONT, 650, 650, 1440, 145)
d.svc("was-a", "mc-was-a (Tomcat 9.0.121 · OpenJDK 8 · Green)", "i-0ff9a07cd26d34ba0 · t3.medium<br>PetClinic <b>test</b>(Spring 5.3.39) · mvnw -P MySQL -Djdbc.url=Proxy(TLS) · 사용자 <b>petclinic_app</b> · 풀 testOnBorrow · systemd<br>CW Agent → CloudWatch Logs(catalina·access·gc) · SG mc-sg-was 8080 ← sg-alb-internal", "ec2", "compute", 670, 670, w=340, h=120)
d.svc("alb-int", "Internal ALB mc-alb-internal", "internal · :8080 → mc-tg-was :8080 /petclinic/ 10s·2/3<br>SG mc-sg-alb-internal 8080 ← sg-web · 액세스 로그 → S3 mc-logs/alb/internal", "application_load_balancer", "net", 1180, 670, w=360, h=120)
d.svc("was-c", "mc-was-c (Tomcat 9.0.121 · OpenJDK 8 · Green)", "i-0d308599780158a68 · t3.medium · 키 mc-ssh<br>was.sh: Proxy 로그인 대기 · 404 면 재시작 · 22 ← sg-bastion", "ec2", "compute", 1760, 670, w=310, h=120)
d.svc("proxy", "RDS Proxy mc-rds-proxy", "mc-rds-proxy.proxy-c7ku4mw88shn.ap-northeast-2.rds.amazonaws.com<br>require_tls · SECRETS 인증 2개(admin·petclinic_app) · 대상 AVAILABLE<br>SG 3306 ← sg-was · ← sg-bastion · 로그 → /aws/rds/proxy/mc-rds-proxy", "rds_proxy", "db", 670, 835, w=340, h=125)
d.svc("pg", "파라미터 그룹 mc-mysql84", "family mysql8.4<br>require_secure_transport=1<br>utf8mb4 · utf8mb4_unicode_ci", "rds", "db", 1030, 835, w=190, h=125)
d.svc("rds", "RDS mc-petclinic (Standby 2a)", "MySQL 8.4.11 · db.t3.small · Multi-AZ · 20→100GB gp3 · 암호화<br>db petclinic · admin 관리형 비밀(7일 교체) · 백업 7일 · 이 AZ(2a) = Standby<br>로그 내보내기 <b>error · slowquery</b>(2s) → /aws/rds/instance/mc-petclinic/*", "rds", "db", 670, 975, w=340, h=120)
d.svc("sg-db", "SG mc-sg-rds", "3306 ← mc-sg-rds-proxy 만<br>(WAS 직접 접속 규칙 없음)", "network_access_control_list", "sec", 1030, 975, w=190, h=120)
d.svc("rds-c", "RDS Primary (ap-northeast-2c)", "mc-petclinic.c7ku4mw88shn.ap-northeast-2.rds.amazonaws.com<br>동기 복제 · 자동 failover", "rds", "db", 1760, 975, w=310, h=120)
d.svc("proxy-c", "RDS Proxy ENI", "db 서브넷 2c", "rds_proxy", "db", 1760, 835, w=150, h=125)
d.note("db-how", "<b>DB 연동 (현재)</b> WAS 부팅 → Secrets Manager 에서 admin 비밀 조회 → <code>mvnw -P MySQL -Djdbc.url/username/password</code> 로 WAR 빌드(Maven 필터링이라 빌드 시 주입) → Tomcat 기동 시 Spring <code>initialize-database</code> 가 schema.sql·data.sql 을 RDS 에 실행 → vets 6 · owners 10 · pets 13 확인. H2 인메모리 아님", 1240, 835, 500, 125, color="#7B1FA2", fill="#F3E5F5")

# ---- ⑤ Ops ----
d.v("ops", "⑤ 운영 · 관측 (observability.tf · kms_s3.tf · iam.tf · rds.tf)", "fillColor=none;strokeColor=#E7157B;dashed=1;verticalAlign=top;align=left;spacingLeft=8;fontStyle=1;fontSize=12;fontColor=#E7157B;whiteSpace=wrap;html=1;" + FONT, 2170, 150, 590, 1000)
d.svc("cwlogs", "CloudWatch Logs (계정에 1개 · VPC 밖)", "/mc/web/* · /mc/was/* 30일 · /mc/bastion/secure 90일<br><b>/aws/rds/instance/mc-petclinic/{error,slowquery} · /aws/rds/proxy/mc-rds-proxy</b> 30일<br>스트림 = 인스턴스 ID · 자체 저장소 · KMS · WAF 는 us-east-1", "cloudwatch", "ops", 2200, 190, w=280, h=125)
d.svc("firehose", "Kinesis Data Firehose ×4 → S3 사본", "mc-cwlogs-web · was · bastion · db<br>구독 필터(그룹당 1) → 5분/5MB · gzip 해제 → 줄 JSON<br>→ s3://mc-logs/cwlogs/‹tier›/yyyy/MM/dd/ · 1년", "kinesis_data_firehose", "ops", 2495, 190, w=245, h=125)
d.svc("alarms", "CloudWatch 알람 ×3", "mc-was-unhealthy-host(≥1, 2분)<br>mc-alb-p95-latency(&gt;2s, 3분)<br>mc-rds-connections-high(&gt;60, 3분)", "cloudwatch", "ops", 2200, 325, w=280, h=115)
d.svc("sns", "SNS mc-alerts", "KMS · email 구독 <b>0건</b>(alert_emails 비어 있음)<br>Slack 은 Grafana Alerting 예정", "simple_notification_service", "ops", 2495, 465, w=245, h=115)
d.svc("trail", "CloudTrail mc-trail (계정 수준 · VPC·리전 밖)", "누가 어떤 AWS API 를 호출했나 — 콘솔·CLI·Terraform 전부<br>다중 리전 · 로그 파일 검증 → S3 객체(1년)", "cloudtrail", "ops", 2200, 460, w=280, h=115)
d.svc("s3-logs", "S3 mc-logs (객체 · .gz)", "alb/public · alb/internal · cloudfront/ 90일<br><b>cwlogs/‹tier›/ 1년</b>(CloudWatch Logs 사본) · cwlogs-errors/ 30일<br>SSE-S3 · CloudTrail 은 별도 버킷", "simple_storage_service", "stor", 2495, 335, w=245, h=115)
d.svc("backup", "AWS Backup", "mc-backup-vault(KMS) · mc-rds-daily<br>daily-7d 04:00 KST → mc-petclinic", "backup", "ops", 2200, 595, w=280, h=115)
d.svc("cwparam", "Parameter Store (Agent 설정)", "/mc/cwagent/web · was · bastion<br>Agent 는 user_data 설치 · Session Manager 아님(enable_ssm=false)", "systems_manager", "ops", 2495, 595, w=245, h=115)
d.svc("iam", "IAM mc-ec2-role + mc-ec2-inline", "CW Agent · GetSecretValue(admin + app-db) · SSM Core 없음<br>kms:Decrypt(ViaService) · ssm:GetParameter(/mc/cwagent/*)<br>s3:PutObject/ListBucket mc-logs · CompleteLifecycleAction", "identity_and_access_management", "sec", 2200, 730, w=280, h=125)
d.svc("secrets", "Secrets Manager", "admin rds!db-…(7일 교체 · aws/secretsmanager)<br>+ <b>app-db</b> petclinic_app(교체 없음 · <b>KMS mc-cmk</b>)<br>WAS 빌드·Proxy 인증은 app-db", "secrets_manager", "sec", 2495, 730, w=245, h=125)
d.svc("grafana", "Managed Grafana (미생성)", "enable_grafana=false<br>IAM Identity Center 필요 → 켜면 mc-ops", "managed_service_for_grafana", "ops", 2200, 875, w=280, h=110, optional=True)
d.note("ops-todo", "<b>로그 원칙</b> 서버(EBS)에 남기지 않고 만들자마자 밖으로 — 앱·Bastion·RDS·Proxy = CloudWatch Logs, ALB·CloudFront·CloudTrail = S3 객체, CloudWatch Logs 는 Firehose 로 S3 사본 1년<br><b>안 켠 것</b> alert_emails · enable_grafana · enable_asg", 2495, 875, 245, 110)

# ---- edges ----
d.edge("e0", "user", "grp-r53", label="DNS", exit=(1, 0.5), entry=(0, 0.5))
d.edge("e1", "user", "grp-cf", label="HTTPS", pts=[(128, 322), (425, 322)], exit=(0.5, 1), entry=(0.5, 0), lx=0.3)
d.edge("e1w", "grp-waf", "grp-cf", "edgeStyle=orthogonalEdgeStyle;html=1;endArrow=open;strokeColor=#DD344C;dashed=1;" + FONT, label="Web ACL 부착 · 먼저 평가", exit=(1, 0.3), entry=(0, 0.3), ly=-8)
d.edge("e1m", "grp-cf", "grp-s3-maint", "edgeStyle=orthogonalEdgeStyle;html=1;endArrow=block;endFill=1;strokeColor=#1B8B3B;" + FONT, label="정적 Miss (OAC) · 5xx → 점검 페이지", pts=[(400, 495), (200, 495)], exit=(0.35, 1), entry=(0.5, 0), lx=0.2)
d.edge("e2", "grp-cf", "igw", label="① HTTPS 443 + X-Origin-Verify (캐시 미스·동적만)", pts=[(425, 138), (1365, 138)], exit=(0.5, 0), entry=(0.5, 0), lx=0.25)
d.edge("e3", "igw", "grp-alb-pub", exit=(0.5, 1), entry=(0.5, 0))
d.edge("e4a", "grp-alb-pub", "grp-web-a", label="② mc-tg-web :80 라운드로빈", pts=[(1360, 445), (835, 445)], exit=(0.5, 1), entry=(0.5, 0), lx=0.1)
d.edge("e4c", "grp-alb-pub", "grp-web-c", pts=[(1360, 445), (1915, 445)], exit=(0.5, 1), entry=(0.5, 0))
d.edge("e5a", "grp-web-a", "grp-alb-int", label="③ ProxyPass /petclinic/ → :8080 · ProxyPreserveHost", pts=[(835, 625), (1360, 625)], exit=(0.5, 1), entry=(0.5, 0), lx=0.15)
d.edge("e5c", "grp-web-c", "grp-alb-int", pts=[(1915, 625), (1360, 625)], exit=(0.5, 1), entry=(0.5, 0))
d.edge("e6a", "grp-alb-int", "grp-was-a", label="④ mc-tg-was /petclinic/", exit=(0, 0.5), entry=(1, 0.5))
d.edge("e6c", "grp-alb-int", "grp-was-c", exit=(1, 0.5), entry=(0, 0.5))
d.edge("e7", "grp-was-a", "grp-proxy", EDGE_RED, label="⑤ JDBC 3306 sslMode=REQUIRED", exit=(0.5, 1), entry=(0.5, 0), lx=0.6)
d.edge("e7c", "grp-was-c", "grp-proxy-c", EDGE_RED, exit=(0.5, 1), entry=(0.5, 0))
d.edge("e8", "grp-proxy", "grp-rds", EDGE_RED, label="⑥ 풀링 커넥션 → Primary(2c)", exit=(0.5, 1), entry=(0.5, 0), lx=0.6)
d.edge("e9", "grp-rds", "grp-rds-c", EDGE_BI, label="동기 복제 (Multi-AZ)", pts=[(1010, 1130), (1915, 1130)], exit=(0.5, 1), entry=(0.5, 1), ly=10)
d.edge("e10", "grp-secrets", "grp-proxy-c", EDGE_BI, label="비밀 조회", pts=[(2150, 792), (2150, 897)], exit=(0, 0.5), entry=(1, 0.5), lx=0.3)
d.edge("l1", "grp-cf", "grp-s3-logs", "edgeStyle=orthogonalEdgeStyle;html=1;endArrow=open;strokeColor=#1B8B3B;dashed=1;" + FONT, label="CloudFront 액세스 로그 (S3 객체)", pts=[(425, 1345), (2755, 1345), (2755, 392)], exit=(0.5, 1), entry=(1, 0.5), lx=0.3, ly=10)
d.edge("l2", "grp-alb-pub", "grp-s3-logs", "edgeStyle=orthogonalEdgeStyle;html=1;endArrow=open;strokeColor=#1B8B3B;dashed=1;" + FONT, label="ALB 액세스 로그", pts=[(1560, 300), (2150, 300), (2150, 392)], exit=(1, 0.2), entry=(0, 0.5), lx=0.2)
d.edge("l3", "grp-was-a", "grp-cwlogs", "edgeStyle=orthogonalEdgeStyle;html=1;endArrow=open;strokeColor=#E7157B;dashed=1;" + FONT, label="Agent → 로그 이벤트 (WEB·WAS·Bastion)", pts=[(840, 660), (2135, 660), (2135, 252)], exit=(0.5, 0), entry=(0, 0.5), lx=0.3)
d.edge("l4", "grp-rds-c", "grp-cwlogs", "edgeStyle=orthogonalEdgeStyle;html=1;endArrow=open;strokeColor=#E7157B;dashed=1;" + FONT, label="RDS 내보내기 error·slowquery · Proxy 로그 → /aws/rds/*", pts=[(2175, 1035), (2175, 302)], exit=(1, 0.5), entry=(0, 0.9), lx=-0.55, ly=12)
d.edge("l5", "grp-cwlogs", "grp-firehose", "edgeStyle=orthogonalEdgeStyle;html=1;endArrow=block;endFill=1;strokeColor=#1B8B3B;dashed=1;" + FONT, label="구독 필터", exit=(1, 0.5), entry=(0, 0.5), ly=-8)
d.edge("l6", "grp-firehose", "grp-s3-logs", "edgeStyle=orthogonalEdgeStyle;html=1;endArrow=block;endFill=1;strokeColor=#1B8B3B;dashed=1;" + FONT, exit=(0.5, 1), entry=(0.5, 0))
d.edge("l7", "grp-bastion", "grp-cwlogs", "edgeStyle=orthogonalEdgeStyle;html=1;endArrow=open;strokeColor=#E7157B;dashed=1;" + FONT, label="sshd 로그", pts=[(1000, 260), (2135, 260)], exit=(0.5, 0), entry=(0, 0.5), lx=0.4, ly=-8)
d.edge("e13", "user", "grp-bastion", "edgeStyle=orthogonalEdgeStyle;html=1;endArrow=block;endFill=1;strokeColor=#545B64;" + FONT, label="운영자 SSH 22 (키 mc-ssh · /32 만)", pts=[(128, 250), (1000, 250)], exit=(0.5, 0), entry=(0.5, 0), lx=0.3, ly=-8)
d.edge("e11", "grp-alarms", "grp-sns", "edgeStyle=orthogonalEdgeStyle;html=1;endArrow=open;strokeColor=#E7157B;dashed=1;" + FONT, label="alarm_actions", exit=(1, 0.5), entry=(0, 0.5), ly=-8)
d.edge("e12", "grp-backup", "grp-rds-c", "edgeStyle=orthogonalEdgeStyle;html=1;endArrow=open;strokeColor=#E7157B;dashed=1;" + FONT, label="daily-7d", pts=[(2150, 652), (2150, 1035)], exit=(0, 0.5), entry=(1, 0.5), lx=0.3)
d.text("legend", "■ 실선 = 요청 흐름 ①~⑥ · <span style='color:#D32F2F'>■ 붉은 실선 = DB 경로(RDS Proxy · TLS)</span> · ■ 분홍 점선 = 로그 → CloudWatch Logs(계정에 1개) · ■ 초록 점선 = 로그 → S3 객체 · ■ 점선 = 알림·백업·비밀 · ■ 주황 점선 = 계층(EC2 고정 2대) · ■ 회색 점선 박스 = 미생성(Grafana)  |  분홍 = Agent 또는 RDS·Proxy 내보내기 → CloudWatch Logs · 초록 = S3 객체(ALB·CloudFront 직접 · CloudWatch Logs 는 Firehose 사본)  |  운영자 접속 = Bastion + 키 mc-ssh(SSM Session Manager 안 씀)  |  WAS = test 브랜치 Green · Tomcat 9.0.121 · Corretto 8",
       70, 1420, 2600, 24, size=11, color="#555555")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "architecture-mc-deploy-asbuilt.drawio")
d.write(OUT)


def render(drawio, png, w=2820, h=1470):
    xml = open(drawio, encoding="utf-8").read()
    cfg = json.dumps({"xml": xml, "nav": False, "resize": True, "toolbar": "", "highlight": "#0000ff", "lightbox": False})
    html = f"<html><body style='margin:0;background:#fff'><div class='mxgraph' style='max-width:100%;border:0' data-mxgraph='{_html.escape(cfg, quote=True)}'></div><script src='https://viewer.diagrams.net/js/viewer-static.min.js'></script></body></html>"
    tmp = os.path.join(os.environ.get("SCRATCH", "/tmp"), "mcdeploy-render.html")
    open(tmp, "w", encoding="utf-8").write(html)
    subprocess.run(["google-chrome", "--headless=new", "--disable-gpu", "--no-sandbox", "--hide-scrollbars", "--virtual-time-budget=30000",
                    "--force-device-scale-factor=2", f"--window-size={w},{h}", f"--screenshot={png}", "file://" + tmp], check=True, capture_output=True)
    print("wrote", png)


if __name__ == "__main__" and "--png" in sys.argv:
    render(OUT, OUT.replace(".drawio", ".png"))
