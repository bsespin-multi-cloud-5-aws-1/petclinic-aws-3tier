import xml.etree.ElementTree as ET

# ---------- style fragments ----------
PTS = "points=[[0,0,0],[0.25,0,0],[0.5,0,0],[0.75,0,0],[1,0,0],[0,1,0],[0.25,1,0],[0.5,1,0],[0.75,1,0],[1,1,0],[0,0.25,0],[0,0.5,0],[0,0.75,0],[1,0.25,0],[1,0.5,0],[1,0.75,0]]"
GPTS = "points=[[0,0],[0.25,0],[0.5,0],[0.75,0],[1,0],[1,0.25],[1,0.5],[1,0.75],[1,1],[0.75,1],[0.5,1],[0.25,1],[0,1],[0,0.75],[0,0.5],[0,0.25]]"
FONT = "fontFamily=Helvetica;"

def svc_icon_style(res, color):
    return (f"sketch=0;{PTS};outlineConnect=0;fontColor=#232F3E;fillColor={color};strokeColor=#ffffff;dashed=0;"
            "verticalLabelPosition=bottom;verticalAlign=top;align=center;html=1;fontSize=10;fontStyle=0;aspect=fixed;"
            f"shape=mxgraph.aws4.resourceIcon;resIcon=mxgraph.aws4.{res};{FONT}shadow=1;")

def sub_icon_style(shape, color):
    return (f"sketch=0;outlineConnect=0;fontColor=#232F3E;gradientColor=none;fillColor={color};strokeColor=none;dashed=0;"
            "verticalLabelPosition=bottom;verticalAlign=top;align=center;html=1;fontSize=10;fontStyle=0;aspect=fixed;"
            f"pointerEvents=1;shape=mxgraph.aws4.{shape};{FONT}")

def container_style(tint, stroke):
    return (f"fillColor={tint};strokeColor={stroke};rounded=1;whiteSpace=wrap;html=1;verticalAlign=top;fontStyle=1;fontSize=12;"
            f"fontColor={stroke};{FONT}container=1;collapsible=0;shadow=1;strokeWidth=1.5;")

CAT = {  # tint, stroke, icon fill
    "net": ("#EDE7F6", "#8C4FFF", "#8C4FFF"),
    "compute": ("#FFF2E8", "#ED7100", "#ED7100"),
    "db": ("#F5E6F7", "#C925D1", "#C925D1"),
    "storage": ("#E8F5E9", "#3F8624", "#3F8624"),
    "integ": ("#FCE4EC", "#E7157B", "#E7157B"),
    "sec": ("#FFEBEE", "#DD344C", "#DD344C"),
    "gen": ("#F5F5F5", "#666666", "#232F3D"),
}

GROUP_BASE = f"{GPTS};outlineConnect=0;gradientColor=none;html=1;whiteSpace=wrap;fontSize=12;fontStyle=0;shape=mxgraph.aws4.group;"
STY = {
    "cloud": GROUP_BASE + "grIcon=mxgraph.aws4.group_aws_cloud;strokeColor=#232F3E;fillColor=light-dark(#232F3E0D,#232F3E0D);fillStyle=auto;verticalAlign=top;align=left;spacingLeft=30;fontColor=#232F3E;dashed=0;container=0;pointerEvents=0;collapsible=0;recursiveResize=0;fontSize=14;fontStyle=1;" + FONT,
    "region": GROUP_BASE + "grIcon=mxgraph.aws4.group_region;strokeColor=#00A4A6;fillColor=light-dark(#0C7B7D0D,#0C7B7D0D);fillStyle=auto;verticalAlign=top;align=left;spacingLeft=30;fontColor=#00A4A6;dashed=1;container=0;pointerEvents=0;collapsible=0;recursiveResize=0;fontSize=14;fontStyle=1;" + FONT,
    "vpc": GROUP_BASE + "grIcon=mxgraph.aws4.group_vpc2;strokeColor=#8C4FFF;fillColor=light-dark(#8C4FFF0D,#8C4FFF0D);fillStyle=auto;verticalAlign=top;align=left;spacingLeft=30;fontColor=#8C4FFF;dashed=0;container=0;pointerEvents=0;collapsible=0;recursiveResize=0;fontSize=14;fontStyle=1;" + FONT,
    "az": "fillColor=none;strokeColor=#147EBA;dashed=1;verticalAlign=top;fontStyle=1;fontSize=12;fontColor=#147EBA;whiteSpace=wrap;html=1;container=0;pointerEvents=0;collapsible=0;recursiveResize=0;" + FONT,
    "pub": GROUP_BASE + "grIcon=mxgraph.aws4.group_public_subnet;strokeColor=#248814;fillColor=light-dark(#2488140D,#2488140D);fillStyle=auto;verticalAlign=top;align=left;spacingLeft=30;fontColor=#248814;dashed=0;container=0;pointerEvents=0;collapsible=0;recursiveResize=0;" + FONT,
    "priv": GROUP_BASE + "grIcon=mxgraph.aws4.group_private_subnet;strokeColor=#147EBA;fillColor=light-dark(#147EBA0D,#147EBA0D);fillStyle=auto;verticalAlign=top;align=left;spacingLeft=30;fontColor=#147EBA;dashed=0;container=0;pointerEvents=0;collapsible=0;recursiveResize=0;" + FONT,
    "asg": GROUP_BASE + "grIcon=mxgraph.aws4.group_auto_scaling_group;strokeColor=#ED7100;fillColor=none;verticalAlign=top;align=left;spacingLeft=30;fontColor=#ED7100;dashed=1;container=0;pointerEvents=0;collapsible=0;recursiveResize=0;fontStyle=1;" + FONT,
}
EDGE = "edgeStyle=orthogonalEdgeStyle;html=1;endArrow=block;elbow=vertical;startArrow=none;endFill=1;strokeColor=#545B64;rounded=0;" + FONT
EDGE_D = EDGE + "dashed=1;"
EDGE_BI = "edgeStyle=orthogonalEdgeStyle;html=1;endArrow=block;elbow=vertical;startArrow=block;startFill=1;endFill=1;strokeColor=#545B64;rounded=0;" + FONT

# ---------- tree ----------
mxfile = ET.Element("mxfile", host="Electron", version="29.6.1")
diagram = ET.SubElement(mxfile, "diagram", name="계층별 상세 아키텍처", id="tiered-1")
model = ET.SubElement(diagram, "mxGraphModel", dx="2400", dy="1600", grid="0", gridSize="10", guides="1", tooltips="1",
                      connect="1", arrows="1", fold="1", page="0", pageScale="1", pageWidth="2900", pageHeight="2200", math="0", shadow="0")
root = ET.SubElement(model, "root")
ET.SubElement(root, "mxCell", id="0")
ET.SubElement(root, "mxCell", id="1", parent="0")

def vertex(cid, value, style, x, y, w, h, parent="1"):
    c = ET.SubElement(root, "mxCell", id=cid, value=value, style=style, vertex="1", parent=parent)
    ET.SubElement(c, "mxGeometry", x=str(x), y=str(y), width=str(w), height=str(h)).set("as", "geometry")
    return c

def text(cid, value, x, y, w, h, color="#232F3E", size=14, bold=True, align="left", parent="1"):
    st = f"text;html=1;whiteSpace=wrap;strokeColor=none;fillColor=none;align={align};verticalAlign=middle;fontSize={size};fontStyle={1 if bold else 0};fontColor={color};{FONT}"
    return vertex(cid, value, st, x, y, w, h, parent)

def service(cid, cat_label, name, sub, res, cat, x, y, kind="svc"):
    tint, stroke, fill = CAT[cat]
    vertex(f"grp-{cid}", cat_label, container_style(tint, stroke), x, y, 120, 120)
    val = f"{name}<div><i>{sub}</i></div>" if sub else name
    st = svc_icon_style(res, fill) if kind == "svc" else sub_icon_style(res, fill)
    vertex(cid, val, st, 36, 30, 48, 48, parent=f"grp-{cid}")

def edge(cid, src, dst, style, pts=None, label=None, lx=0.0, ly=0, exit=None, entry=None):
    st = style
    if exit: st += f"exitX={exit[0]};exitY={exit[1]};exitDx=0;exitDy=0;"
    if entry: st += f"entryX={entry[0]};entryY={entry[1]};entryDx=0;entryDy=0;"
    c = ET.SubElement(root, "mxCell", id=cid, style=st, edge="1", parent="1", source=src, target=dst)
    g = ET.SubElement(c, "mxGeometry", relative="1"); g.set("as", "geometry")
    if pts:
        arr = ET.SubElement(g, "Array"); arr.set("as", "points")
        for (px, py) in pts:
            ET.SubElement(arr, "mxPoint", x=str(px), y=str(py))
    if label:
        l = ET.SubElement(root, "mxCell", id=f"{cid}-label", value=label,
                          style=f"edgeLabel;html=1;align=center;verticalAlign=middle;resizable=0;points=[];labelBackgroundColor=none;fontSize=11;{FONT}",
                          connectable="0", vertex="1", parent=cid)
        lg = ET.SubElement(l, "mxGeometry", relative="1", x=str(lx), y=str(ly)); lg.set("as", "geometry")
        ET.SubElement(lg, "mxPoint").set("as", "offset")

def badge(n, x, y):
    vertex(f"step-{n}", str(n),
           f"rounded=1;whiteSpace=wrap;html=1;fillColor=#007CBD;strokeColor=default;fontColor=#FFFFFF;fontStyle=1;fontSize=16;{FONT}shadow=1;glass=0;strokeWidth=2;align=center;verticalAlign=middle;labelBackgroundColor=none;",
           x, y, 28, 28)

# ---------- title ----------
vertex("title-group", "", f"group;{FONT}", 50, 30, 2000, 83)
ET.SubElement(root.find("./mxCell[@id='title-group']"), "dummy")  # placeholder removed below
root.remove(root.find("./mxCell[@id='title-group']"))
tg = ET.SubElement(root, "mxCell", id="title-group", value="", style=f"group;{FONT}", connectable="0", vertex="1", parent="1")
ET.SubElement(tg, "mxGeometry", x="50", y="30", width="2000", height="83").set("as", "geometry")
t1 = ET.SubElement(root, "mxCell", id="title-text", value="PetClinic 3-Tier on AWS — 계층별 상세 아키텍처 (1팀 Mission Critical)",
                   style=f"text;html=1;resizable=1;points=[];autosize=1;align=left;verticalAlign=top;spacingTop=-4;fontSize=30;fontStyle=1;{FONT}", vertex="1", parent="title-group")
ET.SubElement(t1, "mxGeometry", width="1600", height="42").set("as", "geometry")
t2 = ET.SubElement(root, "mxCell", id="subtitle-text", value="① 네트워크 진입 → ② WEB → ③ WAS → ④ DB 계층별 구성 + 각 계층의 운영·보안 로그  |  개인정보는 RDS · 진료 파일 저장 제외 · 예약 알림 = WAS 이벤트 로그 → CloudWatch → Lambda → Slack · 로그인 = ALB authenticate-cognito",
                   style=f"text;html=1;resizable=0;points=[];autosize=1;align=left;verticalAlign=top;spacingTop=-4;fontSize=16;{FONT}", vertex="1", parent="title-group")
ET.SubElement(t2, "mxGeometry", x="5", y="40", width="1600", height="25").set("as", "geometry")
t3 = ET.SubElement(root, "mxCell", id="title-separator", value="", style=f"line;strokeWidth=2;html=1;fontSize=14;strokeColor=#FF9900;{FONT}", vertex="1", parent="title-group")
ET.SubElement(t3, "mxGeometry", x="5", y="70", width="1990", height="10").set("as", "geometry")

# ---------- groups ----------
vertex("aws-cloud", "AWS Cloud", STY["cloud"], 230, 140, 1820, 2000)
vertex("band-entry", "①  네트워크 진입 계층 · 글로벌 엣지 (Route 53 · CloudFront Behavior 분기 · WAF · ACM us-east-1 · Cognito OIDC · S3 이미지/점검 오리진 OAC)",
       f"rounded=0;fillColor=none;dashed=1;strokeColor=#8C4FFF;verticalAlign=top;align=left;spacingLeft=10;fontColor=#8C4FFF;fontStyle=1;fontSize=14;whiteSpace=wrap;html=1;container=0;pointerEvents=0;{FONT}",
       250, 165, 1780, 300)
vertex("region", "ap-northeast-2 (서울)", STY["region"], 260, 500, 1760, 1580)
vertex("vpc", "VPC 10.0.0.0/16", STY["vpc"], 290, 580, 1210, 1040)
vertex("az-a", "가용영역 A (ap-northeast-2a)", STY["az"], 320, 640, 500, 950)
vertex("az-c", "가용영역 C (ap-northeast-2c)", STY["az"], 980, 640, 500, 950)
vertex("sub-pub-a", "퍼블릭 서브넷 A · 10.0.0.0/24", STY["pub"], 350, 670, 450, 170)
vertex("sub-pub-c", "퍼블릭 서브넷 C · 10.0.1.0/24", STY["pub"], 1010, 670, 450, 170)
vertex("asg-web", "Auto Scaling — WEB (min 2 · max 6 · CPU 60% 대상 추적)", STY["asg"], 335, 875, 1140, 215)
vertex("sub-web-a", "프라이빗 WEB-A · 10.0.10.0/24", STY["priv"], 350, 905, 450, 170)
vertex("sub-web-c", "프라이빗 WEB-C · 10.0.11.0/24", STY["priv"], 1010, 905, 450, 170)
vertex("asg-was", "Auto Scaling — WAS (min 2 · max 8 · 대상당 요청 수 + 예약 증설)", STY["asg"], 335, 1120, 1140, 215)
vertex("sub-was-a", "프라이빗 WAS-A · 10.0.20.0/24", STY["priv"], 350, 1150, 450, 170)
vertex("sub-was-c", "프라이빗 WAS-C · 10.0.21.0/24", STY["priv"], 1010, 1150, 450, 170)
vertex("sub-db-a", "프라이빗 DB-A · 10.0.30.0/24 (인터넷 경로 없음)", STY["priv"], 350, 1380, 450, 180)
vertex("sub-db-c", "프라이빗 DB-C · 10.0.31.0/24 (인터넷 경로 없음)", STY["priv"], 1010, 1380, 450, 180)

# tier labels (left column, outside cloud)
text("lbl-web", "②  WEB 계층", 40, 950, 180, 24, "#ED7100", 16)
text("lbl-web2", "Apache 2.4 · MPM 튜닝<br>Public ALB · 헬스체크 /health.html", 40, 976, 180, 44, "#232F3E", 10, False)
text("lbl-was", "③  WAS 계층", 40, 1195, 180, 24, "#ED7100", 16)
text("lbl-was2", "Tomcat 9 · maxThreads 튜닝<br>Internal ALB · 헬스체크 /petclinic/", 40, 1221, 180, 44, "#232F3E", 10, False)
text("lbl-db", "④  DB 계층", 40, 1425, 180, 24, "#C925D1", 16)
text("lbl-db2", "RDS MySQL 8 Multi-AZ<br>RDS Proxy · Secrets · KMS", 40, 1451, 180, 44, "#232F3E", 10, False)
text("lbl-store", "예약 알림 · 감사", 40, 1725, 180, 24, "#ED7100", 16)
text("lbl-store2", "예약 이벤트 → Lambda → Slack<br>CloudTrail 관리 이벤트 감사", 40, 1751, 180, 44, "#232F3E", 10, False)
text("lbl-ops", "운영 · 관측 공통", 40, 1925, 180, 24, "#E7157B", 16)
text("lbl-ops2", "CloudWatch → Grafana · Slack<br>알람 → SNS → Chatbot", 40, 1951, 180, 44, "#232F3E", 10, False)
text("lbl-store-band", "예약 알림 (업무 이벤트) · 감사 로그", 300, 1630, 520, 22, "#ED7100", 14)
text("lbl-ops-band", "운영 · 관측 공통 (전 계층)", 300, 1845, 400, 22, "#E7157B", 14)
text("lbl-opscol", "계층별 운영 · 보안 로그 (오른쪽 열, 계층 행에 맞춤)", 1550, 515, 440, 24, "#E7157B", 14)
text("lbl-row-web", "WEB 계층 로그 · 접속", 1550, 910, 200, 20, "#ED7100", 12)
text("lbl-row-was", "WAS 계층 로그 · 증설", 1550, 1155, 200, 20, "#ED7100", 12)
text("lbl-row-db", "DB 계층 비밀 · 암호화 · 백업", 1550, 1385, 260, 20, "#C925D1", 12)

# ---------- external actors ----------
def actor(cid, label, x, y, res="users"):
    vertex(cid, label, f"fillColor=#f5f5f5;strokeColor=light-dark(#666666,#D4D4D4);rounded=1;whiteSpace=wrap;html=1;verticalAlign=top;fontStyle=1;fontSize=12;fontColor=#333333;{FONT}container=1;collapsible=0;shadow=1;strokeWidth=1;perimeterSpacing=0;", x, y, 107, 98)
    vertex(f"{cid}-icon", "", svc_icon_style(res, "#232F3D"), 30, 30, 48, 48, parent=cid)
actor("users", "사용자 (의료진·환자)", 60, 290)
actor("ops", "운영자 (관리자)", 2080, 880, res="user")
vertex("slack", "Slack (#mc-alerts)", f"fillColor=#f5f5f5;strokeColor=light-dark(#666666,#D4D4D4);rounded=1;whiteSpace=wrap;html=1;verticalAlign=top;fontStyle=1;fontSize=12;fontColor=#333333;{FONT}container=1;collapsible=0;shadow=1;strokeWidth=1;perimeterSpacing=0;", 2080, 1900, 107, 98)
vertex("slack-icon", "", sub_icon_style("chat", "#232F3D"), 30, 30, 48, 48, parent="slack")

# ---------- ① entry tier ----------
service("r53", "DNS", "Amazon Route 53", "별칭 A/AAAA → CloudFront · Failover 없음", "route_53", "net", 300, 260)
service("waf", "웹 방화벽 (먼저 검사)", "AWS WAF", "관리형 규칙 3 + rate 2<br>차단은 캐시·오리진 미도달", "waf", "sec", 520, 260)
service("cf", "CDN · 엣지", "Amazon CloudFront", "WAF Web ACL 연결 · Behavior 분기<br>/resources·/images 캐시, 동적은 ALB", "cloudfront", "net", 740, 260)
service("acm", "인증서", "AWS Certificate Manager", "us-east-1 · DNS 검증<br>13개월 자동 갱신", "certificate_manager", "sec", 960, 260)
service("cognito", "로그인", "Amazon Cognito", "Hosted UI · MFA · 그룹 vets/admins<br>ALB authenticate-cognito (앱 수정 없음)", "cognito", "sec", 1180, 260)
service("s3maint", "점검 페이지", "Amazon S3", "오리진 그룹 secondary · OAC<br>버킷 정책 SourceArn 조건", "s3", "storage", 1400, 260)
service("s3-img", "공개 이미지", "Amazon S3", "mc-images · /images/* Behavior<br>시설·수의사·후기 사진 · OAC", "s3", "storage", 1620, 260)
service("cwl-waf", "진입 계층 로그", "CloudWatch Logs", "aws-waf-logs-mc · 30일<br>차단 건수 · IP 캡처", "cloudwatch_logs", "integ", 1840, 260, kind="sub")

# ---------- VPC · middle lane ----------
service("igw", "인터넷 연결", "Internet Gateway", "VPC ↔ 인터넷", "internet_gateway", "net", 840, 510, kind="sub")
service("alb", "부하 분산 (외부)", "Public ALB", "443 · ACM(서울) · tg-web<br>헬스체크 /health.html", "application_load_balancer", "net", 840, 690, kind="sub")
service("ialb", "부하 분산 (내부)", "Internal ALB", "8080 · tg-was · sticky(AWSALB)<br>헬스체크 /petclinic/", "application_load_balancer", "net", 840, 1170, kind="sub")
service("proxy", "커넥션 관리", "RDS Proxy", "커넥션 다중화 · failover 단축<br>Require TLS", "rds_proxy", "db", 840, 1410, kind="sub")
# NAT
service("nat-a", "아웃바운드", "NAT Gateway", "dnf · Agent · SSM<br>인바운드 불가", "nat_gateway", "net", 380, 700, kind="sub")
service("nat-c", "아웃바운드", "NAT Gateway", "AZ당 1개<br>AZ 손실 대비", "nat_gateway", "net", 1030, 700, kind="sub")
# WEB
service("web-a", "WEB", "WEB-A · Apache 2.4", "AL2023 · MPM event<br>정적 파일 직접 서빙", "ec2", "compute", 380, 935)
service("web-c", "WEB", "WEB-C · Apache 2.4", "CloudWatch Agent<br>SSM Agent", "ec2", "compute", 1030, 935)
# WAS
service("was-a", "WAS", "WAS-A · Tomcat 9", "Corretto 17 · maxThreads<br>예약 이벤트 로그 1줄", "ec2", "compute", 380, 1180)
service("was-c", "WAS", "WAS-C · Tomcat 9", "AZ당 2대 · 세션은 sticky<br>예약 이벤트 로그 → CloudWatch", "ec2", "compute", 1030, 1180)
# DB
service("rds-p", "관계형 DB (주) · 개인정보", "RDS MySQL 8.0 Primary", "개인정보 저장소(owners·pets·visits)<br>Multi-AZ · KMS 암호화 · TLS", "rds", "db", 380, 1410)
service("rds-s", "관계형 DB (대기)", "RDS Standby", "동기 복제<br>자동 failover 60~120s", "rds", "db", 1030, 1410)

# ---------- ops column (per tier) ----------
service("cwl-web", "WEB 로그", "CloudWatch Logs", "/mc/web/* · Agent<br>보존 30일", "cloudwatch_logs", "integ", 1550, 935, kind="sub")
service("s3-logs", "액세스 · 종료 로그", "Amazon S3", "mc-logs · ALB 액세스 90일<br>ASG 종료 훅 로그", "s3", "storage", 1710, 935)
service("ssm", "운영자 접속", "SSM Session Manager", "22번 포트 없음<br>세션 로그 /mc/ssm 90일", "systems_manager_session_manager", "integ", 1870, 935, kind="sub")
service("cwl-was", "WAS 로그", "CloudWatch Logs", "/mc/was/* · catalina · gc<br>보존 30일", "cloudwatch_logs", "integ", 1550, 1180, kind="sub")
service("asg", "증설 정책", "Auto Scaling", "대상 추적 · 예약 증설<br>종료 수명 주기 훅", "autoscaling", "compute", 1710, 1180)
service("secrets", "비밀 관리", "Secrets Manager", "RDS 관리형 비밀<br>7일 자동 로테이션", "secrets_manager", "sec", 1550, 1410)
service("kms", "암호화 키", "AWS KMS", "CMK · 버킷 키<br>S3 이미지 · RDS · Secrets", "key_management_service", "sec", 1710, 1410)
service("backup", "백업", "AWS Backup", "자동 백업 7일 · PITR<br>Phase 전 스냅샷 (Standby)", "backup", "storage", 1870, 1410)

# ---------- storage / audit band ----------
service("cloudtrail", "감사 추적", "AWS CloudTrail", "관리 이벤트 · 다중 리전<br>로그 파일 검증", "cloudtrail", "integ", 350, 1680)
service("s3-trail", "감사 로그", "Amazon S3", "mc-cloudtrail · 1년<br>누가 무엇을 바꿨나", "s3", "storage", 570, 1680)
service("lambda-notify", "예약 알림", "AWS Lambda", "구독 필터 RESERVATION_CREATED<br>수의사·시간 포함 Slack 메시지", "lambda", "compute", 1300, 1680)

# ---------- common ops band ----------
service("grafana", "대시보드", "Amazon Managed Grafana", "Identity Center 로그인<br>전/후 비교 대시보드", "managed_service_for_grafana", "integ", 790, 1880)
service("cw", "지표 · 알람", "Amazon CloudWatch", "p95 · 5XX · HealthyHost<br>DB 연결 알람", "cloudwatch", "integ", 1010, 1880)
service("sns", "알림 주제", "Amazon SNS", "mc-alerts", "sns", "integ", 1230, 1880)
service("chatbot", "채팅 연동", "AWS Chatbot", "SNS → Slack 채널", "chatbot", "integ", 1450, 1880)

# ---------- edges ----------
edge("e1", "users", "r53", EDGE, label="DNS 조회", lx=-0.1, ly=-12, exit=(1, 0.5), entry=(0, 0.5))
edge("e2", "r53", "waf", EDGE, label="별칭", lx=0, ly=-12, exit=(1, 0.5), entry=(0, 0.5))
edge("e3", "waf", "cf", EDGE, label="통과 요청만", lx=0, ly=-12, exit=(1, 0.5), entry=(0, 0.5))
edge("e4", "acm", "cf", EDGE_D, pts=[(1020, 230), (800, 230)], label="TLS 인증서 (us-east-1)", lx=0, ly=-10, exit=(0.5, 0), entry=(0.5, 0))
edge("e5", "waf", "cwl-waf", EDGE_D, pts=[(580, 210), (1900, 210)], label="WAF 로그 · 차단 건수", lx=0.2, ly=-10, exit=(0.5, 0), entry=(0.5, 0))
edge("e6", "cf", "s3maint", EDGE_D, pts=[(830, 440), (1460, 440)], label="오리진 실패(5xx·타임아웃) → 점검 페이지 (OAC SigV4 서명)", lx=-0.1, ly=12, exit=(0.75, 1), entry=(0.5, 1))
edge("e7", "cf", "igw", EDGE, pts=[(800, 464), (900, 464)], label="HTTPS only · X-Origin-Verify · 캐시 미스만 오리진", lx=-0.45, ly=-12, exit=(0.5, 1), entry=(0.5, 0))
edge("e8", "igw", "alb", EDGE, exit=(0.5, 1), entry=(0.5, 0))
edge("e38", "cf", "s3-img", EDGE, pts=[(848, 412), (1680, 412)], label="/images/* → S3 오리진 (OAC · 캐시 1일+) · 서버 미경유", lx=0.2, ly=12, exit=(0.9, 1), entry=(0.5, 1))
edge("e9", "cognito", "alb", EDGE_D, pts=[(1240, 470), (980, 470), (980, 750)], label="ALB 리스너 규칙 authenticate-cognito → 콜백 /oauth2/idpresponse", lx=-0.15, ly=13, exit=(0.5, 1), entry=(1, 0.5))
edge("e10", "alb", "web-a", EDGE, pts=[(870, 858), (440, 858)], label="tg-web · /health.html 10s · 2/3", lx=0.1, ly=-12, exit=(0.25, 1), entry=(0.5, 0))
edge("e11", "alb", "web-c", EDGE, pts=[(930, 858), (1090, 858)], exit=(0.75, 1), entry=(0.5, 0))
edge("e12", "web-a", "ialb", EDGE, pts=[(440, 1108), (870, 1108)], label="ProxyPass /petclinic/ · ProxyPreserveHost", lx=0.1, ly=-12, exit=(0.5, 1), entry=(0.25, 0))
edge("e13", "web-c", "ialb", EDGE, pts=[(1090, 1108), (930, 1108)], exit=(0.5, 1), entry=(0.75, 0))
edge("e14", "ialb", "was-a", EDGE, label="tg-was · /petclinic/", lx=0.3, ly=-12, exit=(0, 0.5), entry=(1, 0.5))
edge("e15", "ialb", "was-c", EDGE, exit=(1, 0.5), entry=(0, 0.5))
edge("e16", "was-a", "proxy", EDGE, pts=[(440, 1355), (870, 1355)], label="JDBC · sslMode=REQUIRED", lx=0.1, ly=-12, exit=(0.5, 1), entry=(0.25, 0))
edge("e17", "was-c", "proxy", EDGE, pts=[(1090, 1355), (930, 1355)], exit=(0.5, 1), entry=(0.75, 0))
edge("e18", "proxy", "rds-p", EDGE, label="Primary 엔드포인트", lx=0, ly=-12, exit=(0, 0.5), entry=(1, 0.5))
edge("e19", "rds-p", "rds-s", EDGE_BI, pts=[(440, 1545), (1090, 1545)], label="동기 복제 · 자동 failover (RPO 0)", lx=0, ly=-11, exit=(0.5, 1), entry=(0.5, 1))
edge("e20", "secrets", "proxy", EDGE_D, pts=[(1610, 1595), (900, 1595)], label="자격증명 조회 · 로테이션은 Proxy 뒤에서 (앱 무영향)", lx=-0.3, ly=13, exit=(0.5, 1), entry=(0.5, 1))
edge("e21", "rds-s", "backup", EDGE_D, pts=[(1120, 1575), (1930, 1575)], exit=(0.75, 1), entry=(0.5, 1))
edge("e22", "kms", "secrets", EDGE_D, exit=(0, 0.5), entry=(1, 0.5))
edge("e26", "cloudtrail", "s3-trail", EDGE, label="1년 · 검증", lx=0, ly=-12, exit=(1, 0.5), entry=(0, 0.5))
edge("e23", "cwl-was", "lambda-notify", EDGE_D, pts=[(1610, 1345), (1520, 1345), (1520, 1740)], label="구독 필터 · 예약 이벤트 로그", lx=0.6, ly=12, exit=(0.5, 1), entry=(1, 0.5))
edge("e24", "lambda-notify", "slack", EDGE, pts=[(1360, 1660), (2070, 1660), (2070, 1915)], label="예약 알림 → #mc-reservations (수의사 링크 → Cognito 로그인 후 확인)", lx=0.1, ly=-12, exit=(0.5, 0), entry=(0, 0.15))
edge("e27", "cw", "grafana", EDGE, label="지표 · 로그", lx=0, ly=-12, exit=(0, 0.5), entry=(1, 0.5))
edge("e28", "cw", "sns", EDGE, label="알람", lx=0, ly=-12, exit=(1, 0.5), entry=(0, 0.5))
edge("e29", "sns", "chatbot", EDGE, exit=(1, 0.5), entry=(0, 0.5))
edge("e30", "chatbot", "slack", EDGE, label="#mc-alerts", lx=0.2, ly=-12, exit=(1, 0.5), entry=(0, 0.5))
edge("e31", "grafana", "slack", EDGE_D, pts=[(850, 2035), (2060, 2035), (2060, 1983)], label="Grafana Alerting → Slack 직접", lx=-0.3, ly=12, exit=(0.5, 1), entry=(0, 0.85))
edge("e32", "cw", "asg", EDGE_D, pts=[(1070, 1845), (2005, 1845), (2005, 1240)], label="대상 추적 알람 → 증설 · 축소", lx=-0.2, ly=-11, exit=(0.5, 0), entry=(1, 0.5))
edge("e33", "web-c", "cwl-web", EDGE_D, label="CloudWatch Agent (전 인스턴스)", lx=0, ly=-12, exit=(1, 0.5), entry=(0, 0.5))
edge("e34", "was-c", "cwl-was", EDGE_D, label="Agent · catalina · access · gc", lx=0, ly=-12, exit=(1, 0.5), entry=(0, 0.5))
edge("e35", "alb", "s3-logs", EDGE_D, pts=[(830, 702), (830, 572), (1770, 572)], label="ALB 액세스 로그 (외부·내부 동일) → S3", lx=0.15, ly=-11, exit=(0, 0.1), entry=(0.5, 0))
edge("e36", "asg", "s3-logs", EDGE_D, label="종료 훅 → 로그 sync", lx=0, ly=0, exit=(0.5, 0), entry=(0.5, 1))
edge("e37", "ops", "ssm", EDGE, pts=[(2030, 929), (2030, 995)], exit=(0, 0.5), entry=(1, 0.5))

# ---------- badges ----------
for n, (x, y) in {1: (215, 300), 2: (455, 285), 3: (765, 392), 4: (1200, 395), 5: (885, 825), 6: (455, 1070),
                  7: (805, 1205), 8: (455, 1312), 9: (1165, 1500), 10: (1625, 1540), 11: (1265, 1650),
                  12: (1165, 960), 13: (455, 1648), 14: (1030, 1850), 15: (2085, 850)}.items():
    badge(n, x, y)

# ---------- legend ----------
LX, LY, LW, LH = 2230, 30, 650, 2130
vertex("legend-bg", "", "verticalLabelPosition=bottom;verticalAlign=top;html=1;shape=mxgraph.basic.rect;fillColor2=none;strokeWidth=1;size=20;indent=5;fillColor=light-dark(#EDF3FF,#305363);strokeColor=#6c8ebf;", LX, LY, LW, LH)
lc = ET.SubElement(root, "mxCell", id="legend-container", value="", style="group", connectable="0", vertex="1", parent="1")
ET.SubElement(lc, "mxGeometry", x=str(LX + 20), y=str(LY + 30), width="602", height=str(LH - 40)).set("as", "geometry")
lt = ET.SubElement(root, "mxCell", id="legend-title", value="계층별 흐름 · 설정 · 로그  (Notion Q&amp;A 13 결론)", style=f"text;html=1;align=left;verticalAlign=top;fontSize=16;fontStyle=1;{FONT}", vertex="1", parent="legend-container")
ET.SubElement(lt, "mxGeometry", width="580", height="24").set("as", "geometry")
steps = [
 ("① 사용자 → Route 53", "도메인 조회 후 A/AAAA 별칭이 CloudFront를 가리킴. Route 53 Failover는 단일 리전에서 불필요 → CloudFront 오리진 그룹으로 대체(리전 DR 시 로드맵)"),
 ("① WAF → CloudFront + ACM", "WAF가 CloudFront Web ACL로 먼저 평가: IP 평판·Common·KnownBadInputs + rate 전체 2,000/5분·예약 경로 100/5분(Count→Block). 차단된 요청은 캐시·오리진에 도달하지 않음, 로그 → CloudWatch Logs. 통과한 요청만 CloudFront 캐시(정적)·오리진(동적). Response Headers Policy, HTTP→HTTPS. ACM은 us-east-1, 13개월 자동 갱신"),
 ("① CloudFront Behavior 분기 → ALB / S3(OAC)", "주소로 분기: /petclinic/resources/* 는 캐시(오리진 ALB), /images/* 는 S3 mc-images 오리진(시설·수의사·후기 사진, 서버 미경유), /login·/oauth2·나머지 동적은 ALB로 캐시 없이 쿠키·쿼리 전달. ALB 오리진은 HTTPS only + X-Origin-Verify. S3 오리진은 OAC(SigV4) + 버킷 정책 SourceArn, 공개 읽기 없음. 오리진 5xx 시 S3 점검 페이지. 환자 개인 이미지(MRI 등)는 캐시하지 않고 Presigned URL로만"),
 ("① 로그인 = ALB authenticate-cognito (앱 수정 없음)", "Public ALB 443 리스너 규칙: /health.html·/ 는 공개, /petclinic/* 는 Cognito Hosted UI로 인증 후 전달(세션 8h, 콜백 /oauth2/idpresponse 는 ALB가 처리). Cognito는 디렉터리·MFA·그룹. 역할별 인가(Spring Security)는 로드맵. JMeter는 부하기 IP 우회 규칙"),
 ("② Public ALB → WEB ASG", "tg-web 헬스체크 /health.html(얕게) 10s·5s·2/3, 등록 취소 30s. WEB ASG CPU 60% 대상 추적, min 2·max 6, 두 AZ 균등"),
 ("② WEB → Internal ALB", "Apache ProxyPass /petclinic/ + ProxyPreserveHost On(Host·X-Forwarded-For 유지). MPM event 튜닝, 정적 파일 직접 서빙"),
 ("③ Internal ALB → WAS ASG", "tg-was 헬스체크 /petclinic/(슬래시 필수, 302 방지). WAS ASG 대상당 요청 수 + CPU 대상 추적, 예약 증설(이벤트 15분 전 4대), min 2·max 8, 워밍업 300s"),
 ("③→④ WAS → RDS Proxy → RDS", "JDBC sslMode=REQUIRED + 파라미터 그룹 require_secure_transport. Proxy가 커넥션 다중화(풀×서버 수 > DB 상한 방지)·failover 중 연결 유지·Require TLS"),
 ("④ RDS Multi-AZ", "개인정보(이름·전화번호·예약)의 저장소. 동기 복제 Standby(RPO 0), failover 60~120s, 엔드포인트 동일. 자동 백업 7일·PITR(5분)·Phase 전 수동 스냅샷·삭제 방지"),
 ("④ Secrets Manager + KMS", "RDS 관리형 비밀 7일 로테이션, Proxy가 직접 조회하므로 앱 무영향. KMS CMK로 S3 의료파일·RDS·Secrets 암호화, 버킷 키로 비용 절감"),
 ("예약 알림 (업무 이벤트 → Slack)", "고객이 예약을 등록하면 WAS가 구조화 로그 한 줄(RESERVATION_CREATED vet=… time=…)을 남김 → CloudWatch Logs /mc/was/events → 구독 필터 → Lambda(20줄)가 Slack #mc-reservations에 수의사·시간·링크 전송. 수의사가 링크를 열면 Cognito OIDC 로그인 후 예약 확인. 같은 로그의 지표 필터로 예약 건수 대시보드"),
 ("계층별 로그 (필수 5 중 4)", "WEB·WAS: CloudWatch Agent → /mc/web·/mc/was 30일. ALB 액세스 로그 → S3 mc-logs 90일. WAF 로그 → CloudWatch Logs. ASG 종료 훅으로 마지막 로그 S3 sync. VPC Flow Logs·RDS 로그는 제외"),
 ("감사 로그", "CloudTrail 추적(관리 이벤트 · 다중 리전 · 로그 파일 검증) → S3 mc-cloudtrail 1년. 누가 SG·RDS·ASG를 바꿨나. 진료 파일 저장을 뺐으므로 S3 데이터 이벤트는 불필요"),
 ("관측 · 알림 (공통)", "CloudWatch 지표·로그 → Amazon Managed Grafana(Identity Center) 대시보드, Grafana Alerting → Slack 직접. AWS 자체 알람은 SNS → AWS Chatbot → Slack. 알람이 ASG 증설 트리거"),
 ("② ③ 운영자 접속", "Bastion·22번 포트 없음. SSM Session Manager(IAM 인증), 세션 로그 → CloudWatch Logs /mc/ssm 90일, DB 접속은 포트 포워딩. NAT는 아웃바운드(dnf·Agent·SSM)용이라 별개로 필요"),
]
y = 36
for i, (title, desc) in enumerate(steps, 1):
    g = ET.SubElement(root, "mxCell", id=f"step-{i}-legend", value="", style=f"group;{FONT}", connectable="0", vertex="1", parent="legend-container")
    ET.SubElement(g, "mxGeometry", x="0", y=str(y), width="600", height="100").set("as", "geometry")
    b = ET.SubElement(root, "mxCell", id=f"step-{i}-badge-legend", value=str(i), style=f"rounded=1;whiteSpace=wrap;html=1;fillColor=#007CBD;strokeColor=default;fontColor=#FFFFFF;fontStyle=1;fontSize=22;labelBackgroundColor=none;{FONT}shadow=1;glass=0;strokeWidth=2;", vertex="1", parent=f"step-{i}-legend")
    ET.SubElement(b, "mxGeometry", y="2", width="40", height="38").set("as", "geometry")
    val = (f'<div><b>{title}</b></div><div><span style="color: light-dark(rgb(0,0,0), rgb(255,255,255));">'
           f'<b><font style="font-size: 15px;">-</font> </b>{desc}</span></div>')
    d = ET.SubElement(root, "mxCell", id=f"step-{i}-desc-legend", value=val, style=f"text;html=1;align=left;verticalAlign=top;spacingTop=-4;fontSize=13;labelBackgroundColor=none;whiteSpace=wrap;{FONT}", vertex="1", parent=f"step-{i}-legend")
    ET.SubElement(d, "mxGeometry", x="52", width="548", height="100").set("as", "geometry")
    y += 106
note = ET.SubElement(root, "mxCell", id="legend-note", value='<i><span style="color: light-dark(rgb(0,0,0), rgb(255,255,255));">NAT Gateway·IGW는 흐름 번호 없이 표시. Slack은 외부 SaaS. 로그인은 ALB 인증 액션(앱 수정 없음). 예약 이벤트 로그·Lambda 알림은 앱 코드 1줄 추가가 전제. 진료 파일 S3 저장·Object Lock Compliance·Macie는 시나리오에서 제외(개인정보는 RDS). Redis(ElastiCache)는 로드맵.</span></i>', style=f"text;html=1;align=left;verticalAlign=top;fontSize=12;whiteSpace=wrap;{FONT}", vertex="1", parent="legend-container")
ET.SubElement(note, "mxGeometry", x="0", y=str(y + 6), width="600", height="44").set("as", "geometry")
y += 60
lsg = ET.SubElement(root, "mxCell", id="legend-line-styles-group", value="", style=f"group;{FONT}fillColor=light-dark(#F5F5F5,#29393B);strokeColor=#666666;", vertex="1", parent="legend-container")
ET.SubElement(lsg, "mxGeometry", x="0", y=str(y), width="456", height="120").set("as", "geometry")
ls_bg = ET.SubElement(root, "mxCell", id="legend-line-styles-bg", value="선 종류", style=f"rounded=1;whiteSpace=wrap;html=1;fillColor=light-dark(#F5F5F5,#29393B);strokeColor=#666666;verticalAlign=top;fontStyle=1;fontSize=12;{FONT}", vertex="1", parent="legend-line-styles-group")
ET.SubElement(ls_bg, "mxGeometry", width="456", height="120").set("as", "geometry")
for j, (sty, txt) in enumerate([(EDGE, "실선 : 요청 흐름 (사용자 → DB)"), (EDGE_D, "점선 : 로그 · 인증 · 비밀 · 제어 흐름"), (EDGE_BI, "양방향 : Multi-AZ 동기 복제")]):
    yy = 34 + j * 26
    e = ET.SubElement(root, "mxCell", id=f"ls-{j}", style=sty, edge="1", parent="legend-line-styles-group")
    eg = ET.SubElement(e, "mxGeometry", relative="1"); eg.set("as", "geometry")
    ET.SubElement(eg, "mxPoint", x="16", y=str(yy)).set("as", "sourcePoint")
    ET.SubElement(eg, "mxPoint", x="90", y=str(yy)).set("as", "targetPoint")
    t = ET.SubElement(root, "mxCell", id=f"ls-t-{j}", value=f'<span style="color: light-dark(rgb(0,0,0), rgb(255,255,255));">{txt}</span>', style=f"text;html=1;align=left;verticalAlign=middle;fontSize=12;{FONT}", vertex="1", parent="legend-line-styles-group")
    ET.SubElement(t, "mxGeometry", x="100", y=str(yy - 10), width="340", height="20").set("as", "geometry")

tree = ET.ElementTree(mxfile)
ET.indent(tree, space="  ")
out = "/home/grapefruit/middleproject/docs/architecture-tiered-detail.drawio"
tree.write(out, encoding="utf-8", xml_declaration=False)
print("wrote", out)
