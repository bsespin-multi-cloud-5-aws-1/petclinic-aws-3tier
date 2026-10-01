"""test 브랜치 infra/terraform (최종 설계: CloudFront·WAF·ASG·RDS Proxy·운영 계층) 을 리소스 이름 그대로 도면화.
실행: python3 docs/architecture-test-terraform.py [--png] → docs/architecture-test-terraform.drawio / .png"""
import html as _html, json, os, subprocess, sys
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(__file__))
PTS = "points=[[0,0,0],[0.25,0,0],[0.5,0,0],[0.75,0,0],[1,0,0],[0,1,0],[0.25,1,0],[0.5,1,0],[0.75,1,0],[1,1,0],[0,0.25,0],[0,0.5,0],[0,0.75,0],[1,0.25,0],[1,0.5,0],[1,0.75,0]]"
GPTS = "points=[[0,0],[0.25,0],[0.5,0],[0.75,0],[1,0],[1,0.25],[1,0.5],[1,0.75],[1,1],[0.75,1],[0.5,1],[0.25,1],[0,1],[0,0.75],[0,0.5],[0,0.25]]"
FONT = "fontFamily=Helvetica;"
CAT = {"net": ("#EDE7F6", "#8C4FFF"), "compute": ("#FFF2E8", "#ED7100"), "db": ("#F5E6F7", "#C925D1"), "sec": ("#FFEBEE", "#DD344C"),
       "stor": ("#E8F5E9", "#1B8B3B"), "ops": ("#FFEBEE", "#E7157B"), "gen": ("#F5F5F5", "#666666"), "opt": ("#FAFAFA", "#9E9E9E")}
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



d = D("test · infra/terraform (최종 설계)", 2760, 1400)
d.text("title", "test 브랜치 — infra/terraform Terraform 아키텍처 (최종 설계 · Phase 1~3 공용 · 코드 기준)", 40, 20, 1800, 40, size=26, bold=True)
d.text("subtitle", "사용자 → Route 53 → CloudFront(+WAF) → Public ALB :443(X-Origin-Verify) → Apache(ASG) → Internal ALB :8080 → Tomcat 9.0.121·OpenJDK 8 (ASG) → RDS Proxy(TLS) → RDS MySQL Multi-AZ  |  운영: CloudWatch·SNS·CloudTrail·Backup·KMS·SSM",
       40, 60, 2000, 30, size=13, color="#555555")
d.v("cloud", "AWS Cloud · data.aws_caller_identity (계정 ID는 버킷 이름에 사용) · provider profile = var.aws_profile", STY["cloud"], 40, 110, 2680, 1240)
# ---- Edge (global) ----
d.v("edge", "글로벌 진입 계층 (edge.tf) — Route 53 · ACM(us-east-1 + 서울) · CloudFront · WAF", "fillColor=none;strokeColor=#8C4FFF;dashed=1;verticalAlign=top;align=left;spacingLeft=8;fontStyle=1;fontSize=12;fontColor=#8C4FFF;whiteSpace=wrap;html=1;" + FONT, 70, 150, 470, 1170)
d.v("user", "사용자<br>https://&lt;domain_name&gt;/petclinic/", f"sketch=0;outlineConnect=0;fontColor=#232F3E;fillColor=#232F3D;strokeColor=none;dashed=0;verticalLabelPosition=bottom;verticalAlign=top;align=center;html=1;fontSize=11;aspect=fixed;shape=mxgraph.aws4.users;{FONT}", 100, 190, 56, 56)
d.svc("r53", "Route 53", "zone = hosted_zone_name<br>A alias → CloudFront<br>ACM 검증 레코드", "route_53", "net", 240, 180, w=150)
d.svc("acm", "ACM 인증서 ×2", "cloudfront: us-east-1<br>alb: 서울 (오리진)<br>DNS 검증", "certificate_manager", "sec", 400, 180, w=130)
d.svc("waf", "WAF v2 (CLOUDFRONT)", "mc-web-acl · 관리형 3종(IpReputation·<br>Common·KnownBadInputs) · rate-all 2000<br>rate-booking 100(visits/new) · loadgen 허용<br>로그 → aws-waf-logs-mc", "waf", "sec", 100, 340, w=200, h=140)
d.svc("cf", "CloudFront", "aws_cloudfront_distribution.main · PriceClass_200<br>TLSv1.2_2021 · aliases=[domain_name]<br>origin alb-public(HTTPS, X-Origin-Verify 헤더)<br>origin s3-maintenance(OAC) · 오리진 그룹 failover 5xx", "cloudfront", "net", 320, 340, w=200, h=140)
d.note("cf-beh", "<b>Behavior</b><br>• <code>/petclinic/resources/*</code> → 오리진 그룹(ALB→S3 failover) · CachingOptimized · AllViewer(Host 전달)<br>• <code>/maintenance.html</code> → s3-maintenance<br>• <code>*</code>(기본) → alb-public · CachingDisabled · AllViewer<br>• 502/503/504 → 503 + /maintenance.html (10s)", 100, 495, 420, 120)
d.svc("s3-maint", "S3 점검 페이지", "mc-maintenance-&lt;account&gt;<br>maintenance.html · OAC 전용<br>KMS · 버저닝 · 퍼블릭 차단", "simple_storage_service", "stor", 100, 630, w=200, h=118)
d.svc("kms", "KMS CMK", "mc-kms (alias)<br>S3 · RDS · Secrets · Logs 암호화<br>CloudFront OAC Decrypt 허용", "key_management_service", "sec", 320, 630, w=200, h=118)
d.note("edge-why", "<b>왜 이렇게</b><br>• Public ALB SG 는 CloudFront origin-facing 프리픽스 리스트 443 만 허용 + 리스너 기본 403, <code>X-Origin-Verify</code> 헤더 일치 시에만 forward → CloudFront 우회 차단<br>• WAF 는 CLOUDFRONT 스코프(us-east-1) — 예약 폭주(Phase 3)용 booking 경로 rate 100<br>• 점검 페이지는 S3 OAC 로만 읽기 → ALB 5xx 시 CloudFront 가 자동 failover", 100, 770, 420, 150)
d.note("edge-var", "<b>variables.tf 기본값</b><br>web t3.small ASG 2~6 (CPU 60%) · was t3.medium ASG 2~8 (CPU 60% + 요청 300/대상) · 예약 증설 desired 4 (KST 09:45~12:00)<br>db.t3.small · app_repo_branch=<b>test</b> · waf_rate_limit_all 2000 · booking 100 · alert_emails=[] · enable_grafana=false · log_retention 30일<br>필수 입력: domain_name · hosted_zone_name · origin_verify_secret", 100, 940, 420, 170)
d.note("edge-out", "<b>outputs.tf</b> cloudfront_domain · app_url · public_alb_dns · internal_alb_dns · rds_proxy_endpoint · rds_master_secret_arn · buckets · sns_alerts_topic_arn · route53_name_servers(가비아 NS 위임)", 100, 1130, 420, 90)

# ---- VPC ----
d.v("region", "ap-northeast-2 (var.region) · versions.tf aws ~> 5.x · default_tags", STY["region"], 570, 150, 1560, 1170)
d.v("vpc", "VPC mc-vpc · 10.0.0.0/16 · network.tf (IGW · 서브넷 8 · NAT ×2 · rt public / private-a / private-c / db)", STY["vpc"], 590, 215, 1520, 1085)
d.v("az-a", "Availability Zone A (ap-northeast-2a)", STY["az"], 610, 250, 740, 1030)
d.v("az-c", "Availability Zone C (ap-northeast-2c)", STY["az"], 1360, 250, 740, 1030)
for az, x, i in (("a", 625, 0), ("c", 1375, 1)):
    d.v(f"sub-pub-{az}", f"aws_subnet.public[{i}] · 10.0.{i}.0/24 · rt-public → IGW", STY["pub"], x, 280, 710, 165)
    d.v(f"sub-web-{az}", f"aws_subnet.web[{i}] · 10.0.1{i}.0/24 · rt-private-{az} → NAT-{az}", STY["priv"], x, 460, 710, 175)
    d.v(f"sub-was-{az}", f"aws_subnet.was[{i}] · 10.0.2{i}.0/24 · rt-private-{az} → NAT-{az}", STY["priv"], x, 650, 710, 185)
    d.v(f"sub-db-{az}", f"aws_subnet.db[{i}] · 10.0.3{i}.0/24 · rt-db (local 만)", STY["priv"], x, 850, 710, 410)
d.v("igw", "mc-igw", f"sketch=0;{PTS};outlineConnect=0;fontColor=#232F3E;fillColor=#8C4FFF;strokeColor=#ffffff;dashed=0;verticalLabelPosition=bottom;verticalAlign=top;align=center;html=1;fontSize=10;aspect=fixed;shape=mxgraph.aws4.resourceIcon;resIcon=mxgraph.aws4.internet_gateway;{FONT}", 1333, 180, 44, 44)
# public
d.svc("nat-a", "NAT Gateway", "mc-nat-a · EIP<br>WEB/WAS 아웃바운드", "nat_gateway", "net", 645, 300)
d.svc("alb-pub", "Public ALB", "mc-alb-public · :443 HTTPS(ACM alb)<br>기본 403 · 규칙10: X-Origin-Verify 일치 → tg-web<br>tg-web :80 /health.html · 액세스 로그 s3 logs/alb/public<br>SG mc-sg-alb-public 443 ← CloudFront 프리픽스", "application_load_balancer", "net", 1180, 300, w=350)
d.svc("nat-c", "NAT Gateway", "mc-nat-c · EIP", "nat_gateway", "net", 1935, 300)
# web
d.v("asg-web", "ASG mc-asg-web · min 2 / desired 2 / max 6 · health ELB · CPU 60% 목표추적 · LT mc-lt-web (AL2023 or var.web_ami_id · IMDSv2 · gp3 암호화)", "fillColor=none;strokeColor=#ED7100;dashed=1;dashPattern=8 4;strokeWidth=2;verticalAlign=top;align=left;spacingLeft=8;fontStyle=1;fontSize=11;fontColor=#ED7100;whiteSpace=wrap;html=1;" + FONT, 640, 480, 1440, 145)
d.svc("web-a", "WEB (Apache 2.4)", "user_data/web.sh · ProxyPass /petclinic/ → Internal ALB<br>index.html · /petclinic → 301 https · health.html<br>SG mc-sg-web 80 ← sg-alb-public", "ec2", "compute", 660, 500, w=300)
d.svc("web-c", "WEB (Apache 2.4)", "같은 LT · AZ C<br>CW Agent → /petclinic/web/access · error", "ec2", "compute", 1760, 500, w=300)
# was
d.v("asg-was", "ASG mc-asg-was · min 2 / desired 2 / max 8 · health ELB · CPU 60% + ALBRequestCountPerTarget 300 · 예약 증설 desired 4 (KST 09:45~12:00) · 종료 훅 300s(로그 S3 sync) · Rolling 50%", "fillColor=none;strokeColor=#ED7100;dashed=1;dashPattern=8 4;strokeWidth=2;verticalAlign=top;align=left;spacingLeft=8;fontStyle=1;fontSize=11;fontColor=#ED7100;whiteSpace=wrap;html=1;" + FONT, 640, 670, 1440, 155)
d.svc("was-a", "WAS (Tomcat 9.0.121 · OpenJDK 8)", "user_data/was.sh · git test 브랜치 → mvnw -P MySQL 빌드<br>JDBC → RDS Proxy :3306 sslMode=REQUIRED<br>SG mc-sg-was 8080 ← sg-alb-internal · systemd", "ec2", "compute", 660, 695, w=330)
d.svc("alb-int", "Internal ALB", "mc-alb-internal · :8080 · was 서브넷<br>tg-was :8080 /petclinic/ · lb_cookie 스티키<br>SG mc-sg-alb-internal 8080 ← sg-web", "application_load_balancer", "net", 1180, 695, w=350)
d.svc("was-c", "WAS (Tomcat 9.0.121 · OpenJDK 8)", "같은 LT · AZ C<br>CW Agent → /petclinic/was/catalina · access · gc", "ec2", "compute", 1760, 695, w=300)
# db
d.svc("proxy", "RDS Proxy", "mc-rds-proxy · JDBC 3306 TLS 진입점<br>MYSQL · require_tls · SECRETS 인증<br>idle 1800s · max_conn 90% · SG 3306 ← sg-was", "rds_proxy", "db", 660, 880, w=250, h=125)
d.svc("rds-a", "RDS MySQL Primary", "mc-petclinic · engine_version <b>8.0</b> · db.t3.small<br>gp3 20→100 · KMS 암호화 · 관리형 비밀(rds!db-…)<br>백업 7일 · deletion_protection=false", "rds", "db", 660, 1025, w=250, h=125)
d.svc("pg", "파라미터 그룹", "mc-mysql80 (family mysql8.0)<br>require_secure_transport=1<br>utf8mb4 · utf8mb4_unicode_ci", "rds", "db", 930, 1025, w=200, h=125)
d.svc("sg-rds", "SG mc-sg-rds", "3306 ← sg-rds-proxy<br>3306 ← sg-was (Phase 1-2 직접 접속)", "network_access_control_list", "sec", 1150, 1025, w=180, h=125)
d.svc("rds-c", "RDS Standby", "multi_az=true · 동기 복제 · 자동 failover", "rds", "db", 1760, 1025, w=250, h=125)
d.svc("proxy-c", "RDS Proxy ENI", "db 서브넷 ×2 에 배치 (vpc_subnet_ids)", "rds_proxy", "db", 1760, 880, w=250, h=125)
d.note("db-why", "<b>왜 RDS Proxy</b> — Phase 3 폭주 시 WAS 증설로 커넥션이 튀어도 Proxy 가 풀링·재사용(max 90%) · TLS 강제 · 비밀 교체 시 앱 재빌드 불필요(Secrets 인증)<br><b>⚠ engine_version 8.0</b>: MySQL 8.0 표준 지원 종료(2026-07-31) — phase1 코드는 8.4.11. 여기도 8.4 + family mysql8.4 로 올려야 함", 930, 880, 400, 125, color="#D32F2F", fill="#FFF8E1")

# ---- Ops (right) ----
d.v("ops", "운영 계층 (observability.tf · kms_s3.tf · iam.tf · rds.tf backup)", "fillColor=none;strokeColor=#E7157B;dashed=1;verticalAlign=top;align=left;spacingLeft=8;fontStyle=1;fontSize=12;fontColor=#E7157B;whiteSpace=wrap;html=1;" + FONT, 2160, 150, 530, 1170)
d.svc("cwlogs", "CloudWatch Logs", "/petclinic/web/access·error · /petclinic/was/catalina·access·gc (30일)<br>/petclinic/ssm/sessions (90일) · aws-waf-logs-mc<br>CW Agent(EC2 역할 CloudWatchAgentServerPolicy)", "cloudwatch", "ops", 2190, 190, w=240, h=125)
d.svc("alarms", "CloudWatch 알람 ×3", "mc-was-unhealthy-host (≥1, 2분)<br>mc-alb-p95-latency (&gt;2s, 3분)<br>mc-rds-connections-high (&gt;60, 3분)", "cloudwatch", "ops", 2445, 190, w=225, h=125)
d.svc("sns", "SNS", "mc-alerts (KMS)<br>email 구독 = var.alert_emails<br>(Slack 은 Grafana Alerting 에서 · 백업 경로)", "simple_notification_service", "ops", 2190, 335, w=240, h=118)
d.svc("grafana", "Amazon Managed Grafana (선택)", "enable_grafana=false<br>mc-ops · CLOUDWATCH 데이터소스<br>mc-grafana-role", "managed_service_for_grafana", "ops", 2445, 335, w=225, h=118, optional=True)
d.svc("trail", "CloudTrail", "mc-trail · 다중리전 · 로그 파일 검증<br>→ S3 mc-cloudtrail-&lt;account&gt;<br>(KMS · 90일 후 IA · 365일 만료)", "cloudtrail", "ops", 2190, 475, w=240, h=118)
d.svc("s3-logs", "S3 로그 버킷", "mc-logs-&lt;account&gt; · SSE-S3<br>alb/public · alb/internal · was/* · web/*<br>90일 만료(alb) · 30일(was/web)", "simple_storage_service", "stor", 2445, 475, w=225, h=118)
d.svc("backup", "AWS Backup", "mc-backup-vault (KMS) · mc-rds-daily<br>daily-7d 규칙 → RDS 선택 · mc-backup-role<br>(RDS 자동백업 7일과 별개 볼트)", "backup", "ops", 2190, 615, w=240, h=118)
d.svc("ssm", "SSM Session Manager", "SSM-SessionManagerRunShell 문서<br>세션 로그 → /petclinic/ssm/sessions (KMS)<br>22번 포트·키페어 없음", "systems_manager", "sec", 2445, 615, w=225, h=118)
d.svc("iam", "IAM mc-ec2-role", "SSM Core · CW Agent · 인라인:<br>GetSecretValue(rds!db-…) · kms:Decrypt<br>ASG 훅 Complete/Heartbeat · s3:PutObject logs", "identity_and_access_management", "sec", 2190, 755, w=240, h=118)
d.svc("secrets", "Secrets Manager", "rds!db-… (RDS 관리형 · 7일 교체)<br>WAS 부팅 시 조회 → mvnw 빌드 주입<br>RDS Proxy 도 같은 비밀로 인증(mc-rds-proxy-role)", "secrets_manager", "sec", 2445, 755, w=225, h=118)
d.note("ops-why", "<b>왜</b><br>• 로그 5종(앱·ALB·WAF·CloudTrail·SSM) 은 OT 필수 — 앱 로그는 CW Agent, ALB 는 S3 직접, WAF/SSM 은 CW Logs<br>• 알림은 SNS email 백업 + Grafana Alerting(Slack) 이중화 · Cognito·Lambda·Chatbot 은 9/15 제거<br>• KMS 1개 CMK 로 S3·RDS·Secrets·Logs·SNS 통일 (키 정책에 CloudFront OAC·로그 전송 서비스 허용)<br>• EC2 종료 훅 300s: ASG 축소 시 마지막 로그를 S3 로 sync 후 종료", 2190, 895, 480, 170)
d.note("ops-files", "<b>파일 → 리소스 (infra/terraform, 1,941줄)</b><br>network.tf · security.tf(SG 6: alb-public/web/alb-internal/was/rds-proxy/rds) · iam.tf · alb.tf · compute.tf(LT·ASG·정책·예약·훅) · rds.tf(RDS·Proxy·Backup) · edge.tf(R53·ACM·WAF·CF) · kms_s3.tf(CMK·버킷 3) · observability.tf(Logs·알람·SNS·Trail·SSM·Grafana) · user_data/web.sh · was.sh", 2190, 1085, 480, 130)

# ---- edges ----
d.edge("e0", "user", "grp-r53", label="DNS", exit=(1, 0.5), entry=(0, 0.5))
d.edge("e1", "user", "grp-cf", label="HTTPS", pts=[(128, 322), (420, 322)], exit=(0.5, 1), entry=(0.5, 0), lx=0.3)
d.edge("e1w", "grp-waf", "grp-cf", "edgeStyle=orthogonalEdgeStyle;html=1;endArrow=open;strokeColor=#DD344C;dashed=1;" + FONT, label="web_acl_id", exit=(1, 0.3), entry=(0, 0.3), ly=-8)
d.edge("e1m", "grp-cf", "grp-s3-maint", "edgeStyle=orthogonalEdgeStyle;html=1;endArrow=block;endFill=1;strokeColor=#1B8B3B;dashed=1;" + FONT, label="OAC · failover / maintenance.html", pts=[(390, 620), (200, 620)], exit=(0.35, 1), entry=(0.5, 0), lx=0.2)
d.edge("e2", "grp-cf", "igw", label="① HTTPS 443 + X-Origin-Verify (CloudFront origin-facing 프리픽스만 허용)", pts=[(420, 138), (1355, 138)], exit=(0.5, 0), entry=(0.5, 0), lx=0.25)
d.edge("e3", "igw", "grp-alb-pub", exit=(0.5, 1), entry=(0.5, 0))
d.edge("e4a", "grp-alb-pub", "grp-web-a", label="② tg-web :80 (헤더 불일치 시 403)", pts=[(1355, 455), (810, 455)], exit=(0.5, 1), entry=(0.5, 0), lx=0.1)
d.edge("e4c", "grp-alb-pub", "grp-web-c", pts=[(1355, 455), (1910, 455)], exit=(0.5, 1), entry=(0.5, 0))
d.edge("e5a", "grp-web-a", "grp-alb-int", label="③ ProxyPass /petclinic/ → :8080", pts=[(810, 655), (1355, 655)], exit=(0.5, 1), entry=(0.5, 0), lx=0.1)
d.edge("e5c", "grp-web-c", "grp-alb-int", pts=[(1910, 655), (1355, 655)], exit=(0.5, 1), entry=(0.5, 0))
d.edge("e6a", "grp-alb-int", "grp-was-a", label="④ tg-was /petclinic/", exit=(0, 0.5), entry=(1, 0.5))
d.edge("e6c", "grp-alb-int", "grp-was-c", exit=(1, 0.5), entry=(0, 0.5))
d.edge("e7a", "grp-was-a", "grp-proxy", EDGE_RED, label="⑤", exit=(0.5, 1), entry=(0.5, 0), lx=0.6)
d.edge("e7c", "grp-was-c", "grp-proxy-c", EDGE_RED, exit=(0.5, 1), entry=(0.5, 0))
d.edge("e8", "grp-proxy", "grp-rds-a", EDGE_RED, label="⑥ 풀링된 커넥션", exit=(0.5, 1), entry=(0.5, 0), lx=0.6)
d.edge("e8c", "grp-proxy-c", "grp-rds-a", EDGE_RED, pts=[(1885, 1015), (960, 1015)], exit=(0.5, 1), entry=(0.9, 0))
d.edge("e9", "grp-rds-a", "grp-rds-c", EDGE_BI, label="동기 복제 (Multi-AZ)", pts=[(785, 1170), (1885, 1170)], exit=(0.5, 1), entry=(0.5, 1), ly=10)
d.edge("e10", "grp-secrets", "grp-was-c", EDGE_BI, label="비밀 조회", pts=[(2140, 814), (2140, 760)], exit=(0, 0.5), entry=(1, 0.5), lx=0.3)
d.edge("e11", "grp-web-c", "grp-cwlogs", "edgeStyle=orthogonalEdgeStyle;html=1;endArrow=open;strokeColor=#E7157B;dashed=1;" + FONT, label="CW Agent 로그", pts=[(2140, 559), (2140, 252)], exit=(1, 0.5), entry=(0, 0.5), lx=0.3)
d.edge("e12", "grp-alarms", "grp-sns", "edgeStyle=orthogonalEdgeStyle;html=1;endArrow=open;strokeColor=#E7157B;dashed=1;" + FONT, label="alarm_actions", pts=[(2557, 325), (2310, 325)], exit=(0.5, 1), entry=(0.5, 0))
d.edge("e13", "grp-backup", "grp-rds-c", "edgeStyle=orthogonalEdgeStyle;html=1;endArrow=open;strokeColor=#E7157B;dashed=1;" + FONT, label="daily-7d", pts=[(2140, 674), (2140, 1087)], exit=(0, 0.5), entry=(1, 0.5), lx=0.3)
d.text("legend", "■ 실선 = 요청 흐름(①~⑥) · <span style='color:#D32F2F'>■ 붉은 실선 = DB 경로(RDS Proxy)</span> · ■ 점선 = 로그·알림·백업·비밀 · ■ 회색 점선 박스 = 변수로 끄는 선택 리소스 · ■ 주황 점선 = Auto Scaling Group",
       70, 1325, 2000, 24, size=11, color="#555555")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "architecture-test-terraform.drawio")
d.write(OUT)


def render(drawio, png, w=2760, h=1400):
    xml = open(drawio, encoding="utf-8").read()
    cfg = json.dumps({"xml": xml, "nav": False, "resize": True, "toolbar": "", "highlight": "#0000ff", "lightbox": False})
    html = f"<html><body style='margin:0;background:#fff'><div class='mxgraph' style='max-width:100%;border:0' data-mxgraph='{_html.escape(cfg, quote=True)}'></div><script src='https://viewer.diagrams.net/js/viewer-static.min.js'></script></body></html>"
    tmp = os.path.join(os.environ.get("SCRATCH", "/tmp"), "test-render.html")
    open(tmp, "w", encoding="utf-8").write(html)
    subprocess.run(["google-chrome", "--headless=new", "--disable-gpu", "--no-sandbox", "--hide-scrollbars", "--virtual-time-budget=30000",
                    "--force-device-scale-factor=2", f"--window-size={w},{h}", f"--screenshot={png}", "file://" + tmp], check=True, capture_output=True)
    print("wrote", png)


if __name__ == "__main__" and "--png" in sys.argv:
    render(OUT, OUT.replace(".drawio", ".png"))
