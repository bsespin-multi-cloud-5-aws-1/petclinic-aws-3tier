import xml.etree.ElementTree as ET, re, sys
sys.path.insert(0, '/tmp/claude-1000/-home-grapefruit-middleproject/ea49e0ac-1cba-496b-9716-276427ea4bc6/scratchpad')

# ---------- shared style helpers (same as full diagram) ----------
PTS = "points=[[0,0,0],[0.25,0,0],[0.5,0,0],[0.75,0,0],[1,0,0],[0,1,0],[0.25,1,0],[0.5,1,0],[0.75,1,0],[1,1,0],[0,0.25,0],[0,0.5,0],[0,0.75,0],[1,0.25,0],[1,0.5,0],[1,0.75,0]]"
GPTS = "points=[[0,0],[0.25,0],[0.5,0],[0.75,0],[1,0],[1,0.25],[1,0.5],[1,0.75],[1,1],[0.75,1],[0.5,1],[0.25,1],[0,1],[0,0.75],[0,0.5],[0,0.25]]"
FONT = "fontFamily=Helvetica;"
CAT = {"net": ("#EDE7F6", "#8C4FFF", "#8C4FFF"), "compute": ("#FFF2E8", "#ED7100", "#ED7100"), "db": ("#F5E6F7", "#C925D1", "#C925D1"),
       "storage": ("#E8F5E9", "#3F8624", "#3F8624"), "integ": ("#FCE4EC", "#E7157B", "#E7157B"), "sec": ("#FFEBEE", "#DD344C", "#DD344C")}
GROUP_BASE = f"{GPTS};outlineConnect=0;gradientColor=none;html=1;whiteSpace=wrap;fontSize=12;fontStyle=0;shape=mxgraph.aws4.group;"
STY = {
 "cloud": GROUP_BASE + "grIcon=mxgraph.aws4.group_aws_cloud;strokeColor=#232F3E;fillColor=light-dark(#232F3E0D,#232F3E0D);fillStyle=auto;verticalAlign=top;align=left;spacingLeft=30;fontColor=#232F3E;dashed=0;container=0;pointerEvents=0;collapsible=0;recursiveResize=0;fontSize=14;fontStyle=1;" + FONT,
 "vpc": GROUP_BASE + "grIcon=mxgraph.aws4.group_vpc2;strokeColor=#8C4FFF;fillColor=light-dark(#8C4FFF0D,#8C4FFF0D);fillStyle=auto;verticalAlign=top;align=left;spacingLeft=30;fontColor=#8C4FFF;dashed=0;container=0;pointerEvents=0;collapsible=0;recursiveResize=0;fontSize=14;fontStyle=1;" + FONT,
 "az": "fillColor=none;strokeColor=#147EBA;dashed=1;verticalAlign=top;fontStyle=1;fontSize=12;fontColor=#147EBA;whiteSpace=wrap;html=1;container=0;pointerEvents=0;" + FONT,
 "pub": GROUP_BASE + "grIcon=mxgraph.aws4.group_public_subnet;strokeColor=#248814;fillColor=light-dark(#2488140D,#2488140D);fillStyle=auto;verticalAlign=top;align=left;spacingLeft=30;fontColor=#248814;dashed=0;container=0;pointerEvents=0;" + FONT,
 "priv": GROUP_BASE + "grIcon=mxgraph.aws4.group_private_subnet;strokeColor=#147EBA;fillColor=light-dark(#147EBA0D,#147EBA0D);fillStyle=auto;verticalAlign=top;align=left;spacingLeft=30;fontColor=#147EBA;dashed=0;container=0;pointerEvents=0;" + FONT,
 "asg": GROUP_BASE + "grIcon=mxgraph.aws4.group_auto_scaling_group;strokeColor=#ED7100;fillColor=none;verticalAlign=top;align=left;spacingLeft=30;fontColor=#ED7100;dashed=1;container=0;pointerEvents=0;fontStyle=1;" + FONT,
}
EDGE = "edgeStyle=orthogonalEdgeStyle;html=1;endArrow=block;elbow=vertical;startArrow=none;endFill=1;strokeColor=#545B64;rounded=0;" + FONT
EDGE_D = EDGE + "dashed=1;"
EDGE_BI = "edgeStyle=orthogonalEdgeStyle;html=1;endArrow=block;elbow=vertical;startArrow=block;startFill=1;endFill=1;strokeColor=#545B64;rounded=0;" + FONT

class Page:
    def __init__(self, name, pid, w, h):
        self.d = ET.Element("diagram", name=name, id=pid)
        m = ET.SubElement(self.d, "mxGraphModel", dx="1600", dy="1000", grid="0", gridSize="10", guides="1", tooltips="1", connect="1", arrows="1", fold="1", page="0", pageScale="1", pageWidth=str(w), pageHeight=str(h), math="0", shadow="0")
        self.root = ET.SubElement(m, "root")
        ET.SubElement(self.root, "mxCell", id="0"); ET.SubElement(self.root, "mxCell", id="1", parent="0")
    def vertex(self, cid, value, style, x, y, w, h, parent="1"):
        c = ET.SubElement(self.root, "mxCell", id=cid, value=value, style=style, vertex="1", parent=parent)
        ET.SubElement(c, "mxGeometry", x=str(x), y=str(y), width=str(w), height=str(h)).set("as", "geometry")
    def text(self, cid, value, x, y, w, h, color="#232F3E", size=14, bold=True, align="left"):
        self.vertex(cid, value, f"text;html=1;whiteSpace=wrap;strokeColor=none;fillColor=none;align={align};verticalAlign=middle;fontSize={size};fontStyle={1 if bold else 0};fontColor={color};{FONT}", x, y, w, h)
    def service(self, cid, cat_label, name, sub, res, cat, x, y, kind="svc"):
        tint, stroke, fill = CAT[cat]
        self.vertex(f"grp-{cid}", cat_label, f"fillColor={tint};strokeColor={stroke};rounded=1;whiteSpace=wrap;html=1;verticalAlign=top;fontStyle=1;fontSize=12;fontColor={stroke};{FONT}container=1;collapsible=0;shadow=1;strokeWidth=1.5;", x, y, 120, 120)
        val = f"{name}<div><i>{sub}</i></div>" if sub else name
        if kind == "svc":
            st = f"sketch=0;{PTS};outlineConnect=0;fontColor=#232F3E;fillColor={fill};strokeColor=#ffffff;dashed=0;verticalLabelPosition=bottom;verticalAlign=top;align=center;html=1;fontSize=10;fontStyle=0;aspect=fixed;shape=mxgraph.aws4.resourceIcon;resIcon=mxgraph.aws4.{res};{FONT}shadow=1;"
        else:
            st = f"sketch=0;outlineConnect=0;fontColor=#232F3E;gradientColor=none;fillColor={fill};strokeColor=none;dashed=0;verticalLabelPosition=bottom;verticalAlign=top;align=center;html=1;fontSize=10;fontStyle=0;aspect=fixed;pointerEvents=1;shape=mxgraph.aws4.{res};{FONT}"
        self.vertex(cid, val, st, 36, 30, 48, 48, parent=f"grp-{cid}")
    def stub(self, cid, label, x, y, w=170, h=70):
        self.vertex(cid, label, f"rounded=1;whiteSpace=wrap;html=1;fillColor=light-dark(#EEEEEE,#3A3A3A);strokeColor=#888888;dashed=1;fontSize=11;fontStyle=1;fontColor=#444444;{FONT}", x, y, w, h)
    def actor(self, cid, label, x, y, res="users"):
        self.vertex(cid, label, f"fillColor=#f5f5f5;strokeColor=light-dark(#666666,#D4D4D4);rounded=1;whiteSpace=wrap;html=1;verticalAlign=top;fontStyle=1;fontSize=12;fontColor=#333333;{FONT}container=1;collapsible=0;shadow=1;strokeWidth=1;", x, y, 107, 98)
        self.vertex(f"{cid}-icon", "", f"sketch=0;{PTS};outlineConnect=0;fontColor=#232F3E;fillColor=#232F3D;strokeColor=#ffffff;dashed=0;verticalLabelPosition=bottom;verticalAlign=top;align=center;html=1;fontSize=12;aspect=fixed;shape=mxgraph.aws4.resourceIcon;resIcon=mxgraph.aws4.{res};{FONT}", 30, 30, 48, 48, parent=cid)
    def edge(self, cid, src, dst, style, pts=None, label=None, lx=0.0, ly=0, exit=None, entry=None):
        st = style
        if exit: st += f"exitX={exit[0]};exitY={exit[1]};exitDx=0;exitDy=0;"
        if entry: st += f"entryX={entry[0]};entryY={entry[1]};entryDx=0;entryDy=0;"
        c = ET.SubElement(self.root, "mxCell", id=cid, style=st, edge="1", parent="1", source=src, target=dst)
        g = ET.SubElement(c, "mxGeometry", relative="1"); g.set("as", "geometry")
        if pts:
            arr = ET.SubElement(g, "Array"); arr.set("as", "points")
            for (px, py) in pts: ET.SubElement(arr, "mxPoint", x=str(px), y=str(py))
        if label:
            l = ET.SubElement(self.root, "mxCell", id=f"{cid}-label", value=label, style=f"edgeLabel;html=1;align=center;verticalAlign=middle;resizable=0;points=[];labelBackgroundColor=none;fontSize=11;{FONT}", connectable="0", vertex="1", parent=cid)
            lg = ET.SubElement(l, "mxGeometry", relative="1", x=str(lx), y=str(ly)); lg.set("as", "geometry")
            ET.SubElement(lg, "mxPoint").set("as", "offset")
    def badge(self, n, x, y):
        self.vertex(f"step-{n}", str(n), f"rounded=1;whiteSpace=wrap;html=1;fillColor=#007CBD;strokeColor=default;fontColor=#FFFFFF;fontStyle=1;fontSize=16;{FONT}shadow=1;glass=0;strokeWidth=2;align=center;verticalAlign=middle;labelBackgroundColor=none;", x, y, 28, 28)
    def title(self, t, sub, w):
        tg = ET.SubElement(self.root, "mxCell", id="title-group", value="", style=f"group;{FONT}", connectable="0", vertex="1", parent="1")
        ET.SubElement(tg, "mxGeometry", x="50", y="30", width=str(w), height="83").set("as", "geometry")
        a = ET.SubElement(self.root, "mxCell", id="title-text", value=t, style=f"text;html=1;resizable=1;points=[];autosize=1;align=left;verticalAlign=top;spacingTop=-4;fontSize=30;fontStyle=1;{FONT}", vertex="1", parent="title-group")
        ET.SubElement(a, "mxGeometry", width=str(w-200), height="42").set("as", "geometry")
        b = ET.SubElement(self.root, "mxCell", id="subtitle-text", value=sub, style=f"text;html=1;resizable=0;points=[];autosize=1;align=left;verticalAlign=top;spacingTop=-4;fontSize=16;{FONT}", vertex="1", parent="title-group")
        ET.SubElement(b, "mxGeometry", x="5", y="40", width=str(w-200), height="25").set("as", "geometry")
        c = ET.SubElement(self.root, "mxCell", id="title-separator", value="", style=f"line;strokeWidth=2;html=1;fontSize=14;strokeColor=#FF9900;{FONT}", vertex="1", parent="title-group")
        ET.SubElement(c, "mxGeometry", x="5", y="70", width=str(w-10), height="10").set("as", "geometry")
    def legend(self, x, y, h, title, steps, note=None):
        self.vertex("legend-bg", "", "verticalLabelPosition=bottom;verticalAlign=top;html=1;shape=mxgraph.basic.rect;fillColor2=none;strokeWidth=1;size=20;indent=5;fillColor=light-dark(#EDF3FF,#305363);strokeColor=#6c8ebf;", x, y, 600, h)
        lc = ET.SubElement(self.root, "mxCell", id="legend-container", value="", style="group", connectable="0", vertex="1", parent="1")
        ET.SubElement(lc, "mxGeometry", x=str(x+20), y=str(y+24), width="560", height=str(h-40)).set("as", "geometry")
        t = ET.SubElement(self.root, "mxCell", id="legend-title", value=title, style=f"text;html=1;align=left;verticalAlign=top;fontSize=15;fontStyle=1;{FONT}", vertex="1", parent="legend-container")
        ET.SubElement(t, "mxGeometry", width="540", height="24").set("as", "geometry")
        yy = 34
        for i, (tt, desc) in enumerate(steps, 1):
            g = ET.SubElement(self.root, "mxCell", id=f"lg-{i}", value="", style=f"group;{FONT}", connectable="0", vertex="1", parent="legend-container")
            ET.SubElement(g, "mxGeometry", x="0", y=str(yy), width="556", height="96").set("as", "geometry")
            b = ET.SubElement(self.root, "mxCell", id=f"lg-b-{i}", value=str(i), style=f"rounded=1;whiteSpace=wrap;html=1;fillColor=#007CBD;strokeColor=default;fontColor=#FFFFFF;fontStyle=1;fontSize=20;labelBackgroundColor=none;{FONT}shadow=1;glass=0;strokeWidth=2;", vertex="1", parent=f"lg-{i}")
            ET.SubElement(b, "mxGeometry", y="2", width="38", height="36").set("as", "geometry")
            val = f'<div><b>{tt}</b></div><div><span style="color: light-dark(rgb(0,0,0), rgb(255,255,255));">{desc}</span></div>'
            d = ET.SubElement(self.root, "mxCell", id=f"lg-d-{i}", value=val, style=f"text;html=1;align=left;verticalAlign=top;spacingTop=-4;fontSize=12;labelBackgroundColor=none;whiteSpace=wrap;{FONT}", vertex="1", parent=f"lg-{i}")
            ET.SubElement(d, "mxGeometry", x="48", width="508", height="96").set("as", "geometry")
            yy += 100
        if note:
            n = ET.SubElement(self.root, "mxCell", id="legend-note", value=f'<i><span style="color: light-dark(rgb(0,0,0), rgb(255,255,255));">{note}</span></i>', style=f"text;html=1;align=left;verticalAlign=top;fontSize=11;whiteSpace=wrap;{FONT}", vertex="1", parent="legend-container")
            ET.SubElement(n, "mxGeometry", x="0", y=str(yy+4), width="556", height="60").set("as", "geometry")

mxfile = ET.Element("mxfile", host="Electron", version="29.6.1")
# ---- tab 1: full diagram (copy from existing file) ----
full = ET.parse('/home/grapefruit/middleproject/docs/architecture-tiered-detail.drawio').getroot().find('diagram')
full.set('name', '0. 전체 아키텍처'); full.set('id', 'tab-full')
mxfile.append(full)

# ================= tab 2: 진입 계층 =================
p = Page("1. 네트워크 진입 계층 · 글로벌 엣지", "tab-entry", 2300, 1000)
p.title("① 네트워크 진입 계층 · 글로벌 엣지", "사용자 → Route 53 → WAF(먼저 검사) → CloudFront(Behavior 분기) → ALB / S3 · ACM(us-east-1) · Cognito(ALB 인증) · WAF 로그", 2200)
p.vertex("cloud", "AWS Cloud (글로벌 엣지 · us-east-1)", STY["cloud"], 260, 150, 1330, 760)
p.actor("users", "사용자 (의료진·환자)", 60, 330)
p.service("r53", "DNS", "Amazon Route 53", "별칭 A/AAAA → CloudFront<br>Failover 없음(오리진 그룹으로 대체)", "route_53", "net", 320, 320)
p.service("cf", "CDN · 엣지", "Amazon CloudFront", "WAF Web ACL 연결 · Behavior 3개<br>보안 헤더 · HTTP→HTTPS · TLSv1.2_2021", "cloudfront", "net", 880, 320)
p.service("waf", "웹 방화벽 (먼저 검사)", "AWS WAF", "관리형 3 + rate 2 · Count→Block<br>차단은 캐시·오리진 미도달", "waf", "sec", 600, 320)
p.service("acm", "인증서", "AWS Certificate Manager", "us-east-1 · DNS 검증<br>13개월 자동 갱신", "certificate_manager", "sec", 1160, 170)
p.service("cwl-waf", "진입 계층 로그", "CloudWatch Logs", "aws-waf-logs-mc · 30일<br>차단 건수 · IP", "cloudwatch_logs", "integ", 600, 170, kind="sub")
p.service("cognito", "로그인", "Amazon Cognito", "Hosted UI · MFA · 그룹 vets/admins<br>ALB authenticate-cognito", "cognito", "sec", 320, 620)
p.service("s3-img", "공개 이미지", "Amazon S3", "mc-images · OAC<br>시설·수의사·후기 사진", "s3", "storage", 880, 620)
p.service("s3maint", "점검 페이지", "Amazon S3", "오리진 그룹 secondary · OAC<br>버킷 정책 SourceArn", "s3", "storage", 1160, 620)
p.stub("to-web", "→ ② WEB 계층<br>IGW → Public ALB 443 (ACM 서울)", 1360, 345)
p.stub("to-alb", "→ ② Public ALB 443 리스너 규칙<br>/petclinic/* → authenticate-cognito<br>콜백 /oauth2/idpresponse", 600, 640, 220, 80)
p.edge("e1", "users", "r53", EDGE, label="DNS 조회", ly=-12, exit=(1,0.5), entry=(0,0.5))
p.edge("e2", "r53", "waf", EDGE, label="별칭", ly=-12, exit=(1,0.5), entry=(0,0.5))
p.edge("e3", "waf", "cf", EDGE, label="통과 요청만", ly=-12, exit=(1,0.5), entry=(0,0.5))
p.edge("e4", "acm", "cf", EDGE_D, pts=[(1220,300),(980,300)], label="TLS 인증서", ly=-11, exit=(0.5,1), entry=(0.8,0))
p.edge("e5", "waf", "cwl-waf", EDGE_D, label="WAF 로그 · 차단", lx=0, ly=0, exit=(0.5,0), entry=(0.5,1))
p.edge("e6", "cf", "to-web", EDGE, label="동적 · 로그인 · /resources 캐시 미스 → ALB (HTTPS only · X-Origin-Verify)", lx=0.05, ly=-12, exit=(1,0.5), entry=(0,0.5))
p.edge("e7", "cf", "s3-img", EDGE, label="/images/* → S3 오리진 (OAC · 캐시 1일+ · 서버 미경유)", lx=0, ly=0, exit=(0.5,1), entry=(0.5,0))
p.edge("e8", "cf", "s3maint", EDGE_D, pts=[(980,560),(1220,560)], label="오리진 5xx → 점검 페이지", lx=0.3, ly=-11, exit=(0.85,1), entry=(0.5,0))
p.edge("e9", "users", "cognito", EDGE_D, pts=[(113,680)], label="Hosted UI 로그인 (ALB가 리다이렉트)", lx=0.4, ly=12, exit=(0.5,1), entry=(0,0.5))
p.edge("e10", "cognito", "to-alb", EDGE_D, label="code → ALB가 토큰 교환 · 세션 쿠키", ly=-12, exit=(1,0.5), entry=(0,0.5))
for n,(x,y) in {1:(215,340),2:(500,300),3:(1330,300),4:(1000,545),5:(150,690)}.items(): p.badge(n,x,y)
p.text("beh", "처리 순서: Route 53 → WAF(Web ACL 평가) → CloudFront Behavior (주소로 분기)<br>1) /petclinic/resources/* → ALB · CachingOptimized 1일<br>2) /images/* → S3 mc-images(OAC) · 캐시 1일+<br>3) 기본(/*, 로그인 콜백 /oauth2/idpresponse 포함) → ALB · CachingDisabled · AllViewer", 300, 790, 760, 90, "#8C4FFF", 11, False)
p.legend(1640, 30, 900, "진입 계층 · 흐름과 설정", [
 ("사용자 → Route 53", "hospital.example.com A/AAAA 별칭 → CloudFront. Route 53 Failover 없음(단일 리전). 리전 DR 시 로드맵"),
 ("WAF → CloudFront + ACM", "WAF가 CloudFront Web ACL로 먼저 평가(관리형 3 + rate 2, Count→Block). 차단은 캐시·오리진 미도달, 로그 → CloudWatch Logs. 통과한 요청만 CloudFront: 정적은 엣지 캐시, 동적은 캐시 없이 ALB. ACM은 us-east-1, 자동 갱신"),
 ("CloudFront → ALB", "Origin HTTPS only(ALB 443 + 서울 ACM), X-Origin-Verify 헤더로 우회 차단, SG는 CloudFront 접두사 목록만. 보안 헤더는 Response Headers Policy(HSTS·CSP·nosniff)"),
 ("CloudFront → S3 (OAC)", "/images/*는 mc-images 버킷을 직접 읽어 서버 미경유. 오리진 5xx면 점검 페이지 버킷. 둘 다 OAC(SigV4) + 버킷 정책 SourceArn 조건, 공개 읽기 없음. 환자 개인 이미지는 캐시 안 함(Presigned URL)"),
 ("로그인 (ALB authenticate-cognito)", "Public ALB 443 리스너 규칙이 /petclinic/* 요청을 Cognito Hosted UI로 보내고 콜백 /oauth2/idpresponse 를 ALB가 처리해 세션 쿠키 발급(8h). 앱 수정 없음. 역할별 인가는 로드맵"),
], note="이 탭의 로그: WAF 로그(CloudWatch Logs, 30일). ACM DaysToExpiry 알람은 운영 탭 CloudWatch에서.")
mxfile.append(p.d)

# ================= tab 3: WEB 계층 =================
p = Page("2. WEB 계층", "tab-web", 2720, 1100)
p.title("② WEB 계층 · Public ALB → Apache Auto Scaling", "IGW → Public ALB(443 · 헬스체크 /health.html) → WEB ASG(AL2023 · Apache MPM event) → Internal ALB | 로그: CloudWatch Agent · ALB 액세스 로그 · SSM 세션", 2200)
p.vertex("vpc", "VPC 10.0.0.0/16", STY["vpc"], 260, 150, 1330, 860)
p.vertex("az-a", "가용영역 A", STY["az"], 290, 210, 480, 560)
p.vertex("az-c", "가용영역 C", STY["az"], 1080, 210, 480, 560)
p.vertex("pub-a", "퍼블릭 서브넷 A · 10.0.0.0/24", STY["pub"], 310, 240, 440, 190)
p.vertex("pub-c", "퍼블릭 서브넷 C · 10.0.1.0/24", STY["pub"], 1100, 240, 440, 190)
p.vertex("asg", "Auto Scaling — WEB (min 2 · max 6 · CPU 60% 대상 추적 · 워밍업 180s)", STY["asg"], 300, 470, 1250, 280)
p.vertex("web-a-sub", "프라이빗 WEB-A · 10.0.10.0/24", STY["priv"], 310, 500, 440, 230)
p.vertex("web-c-sub", "프라이빗 WEB-C · 10.0.11.0/24", STY["priv"], 1100, 500, 440, 230)
p.stub("from-cf", "① CloudFront에서<br>HTTPS only · X-Origin-Verify", 60, 300)
p.service("igw", "인터넷 연결", "Internet Gateway", "VPC ↔ 인터넷", "internet_gateway", "net", 860, 100, kind="sub")
p.service("alb", "부하 분산 (외부)", "Public ALB", "443 · ACM(서울) · authenticate-cognito<br>헬스체크 /health.html 10s·2/3", "application_load_balancer", "net", 860, 270, kind="sub")
p.service("nat-a", "아웃바운드", "NAT Gateway", "dnf · Agent · SSM<br>인바운드 불가", "nat_gateway", "net", 350, 280, kind="sub")
p.service("nat-c", "아웃바운드", "NAT Gateway", "AZ당 1개<br>AZ 손실 대비", "nat_gateway", "net", 1140, 280, kind="sub")
p.service("web-a", "WEB", "WEB-A · Apache 2.4", "AL2023 · MPM event<br>정적 직접 서빙 · /health.html", "ec2", "compute", 350, 560)
p.service("web-c", "WEB", "WEB-C · Apache 2.4", "CloudWatch Agent · SSM Agent<br>ProxyPass /petclinic/", "ec2", "compute", 1140, 560)
p.stub("to-was", "→ ③ WAS 계층<br>Internal ALB 8080<br>ProxyPass /petclinic/ · ProxyPreserveHost On", 840, 780, 200, 80)
p.service("cwl-web", "WEB 로그", "CloudWatch Logs", "/mc/web/access · error<br>Agent · 30일", "cloudwatch_logs", "integ", 1680, 280, kind="sub")
p.service("s3-logs", "액세스 로그", "Amazon S3", "mc-logs/alb · 90일<br>p95 · 5XX 대상별", "s3", "storage", 1680, 480)
p.service("ssm", "운영자 접속", "SSM Session Manager", "22번 없음 · IAM 인증<br>세션 로그 /mc/ssm 90일", "systems_manager_session_manager", "integ", 1680, 680, kind="sub")
p.actor("ops", "운영자 (관리자)", 1930, 690, res="user")
p.edge("e1", "from-cf", "igw", EDGE, pts=[(230,335),(230,160),(920,160)], exit=(1,0.5), entry=(0.5,0))
p.edge("e2", "igw", "alb", EDGE, exit=(0.5,1), entry=(0.5,0))
p.edge("e3", "alb", "web-a", EDGE, pts=[(890,445),(410,445)], label="tg-web · 두 AZ 분산", lx=0.2, ly=-12, exit=(0.25,1), entry=(0.5,0))
p.edge("e4", "alb", "web-c", EDGE, pts=[(950,445),(1200,445)], exit=(0.75,1), entry=(0.5,0))
p.edge("e5", "web-a", "to-was", EDGE, pts=[(410,760),(840,760)], label="ProxyPass /petclinic/", lx=0.2, ly=-12, exit=(0.5,1), entry=(0,0.25))
p.edge("e6", "web-c", "to-was", EDGE, pts=[(1200,760),(1040,760)], exit=(0.5,1), entry=(1,0.25))
p.edge("e7", "web-c", "cwl-web", EDGE_D, pts=[(1290,620),(1290,340)], label="CloudWatch Agent (전 인스턴스)", lx=0.3, ly=12, exit=(1,0.5), entry=(0,0.5))
p.edge("e8", "alb", "s3-logs", EDGE_D, pts=[(1020,330),(1050,330),(1050,540)], label="ALB 액세스 로그", lx=0.6, ly=-12, exit=(1,0.5), entry=(0,0.5))
p.edge("e9", "ops", "ssm", EDGE, label="Session Manager", ly=-12, exit=(0,0.5), entry=(1,0.5))
p.edge("e10", "ssm", "web-c", EDGE_D, pts=[(1650,740),(1650,650)], label="세션 · 포트 없이 접속", lx=0.3, ly=12, exit=(0,0.5), entry=(1,0.75))
for n,(x,y) in {1:(240,270),2:(880,240),3:(870,455),4:(430,770),5:(1300,600),6:(1900,660)}.items(): p.badge(n,x,y)
p.legend(2080, 30, 1000, "WEB 계층 · 흐름과 설정", [
 ("CloudFront → IGW → Public ALB", "ALB 443 리스너 + 서울 ACM. 규칙 순서: 부하기 IP 우회(실험 시) → /health.html·/ 공개 → /petclinic/* authenticate-cognito(세션 8h) → 나머지. 전부 X-Origin-Verify 헤더 필수, 불일치 403. SG는 CloudFront 접두사 목록만(80 없음)"),
 ("헬스체크 (얕게)", "tg-web 경로 /health.html(정적, Apache 생존만) 10s·5s·정상 2/비정상 3, 등록 취소 30s. WAS 장애는 Internal ALB·RDS 알람이 잡음(연쇄 unhealthy 방지)"),
 ("Auto Scaling — WEB", "CPU 60% 대상 추적, min 2·max 6, 두 AZ 균등, 워밍업 180s, 헬스체크 유형 ELB. 골든 AMI(AL2023·Apache MPM event·CloudWatch Agent) 기동"),
 ("Apache → Internal ALB", "ProxyPass /petclinic/ → 내부 ALB DNS:8080, ProxyPreserveHost On(Host·X-Forwarded-For 유지). 정적 /resources는 Apache가 직접 서빙(캐시 미스 시)"),
 ("로그", "CloudWatch Agent → /mc/web/access·error 30일(EC2 종료돼도 남음). ALB 액세스 로그 → S3 mc-logs 90일(p95·5XX 대상별). 헬스체크 요청은 access log 제외"),
 ("운영자 접속 (SSM)", "Bastion·22번 없음. 인스턴스 프로파일 AmazonSSMManagedInstanceCore, 아웃바운드 443은 NAT. 세션 로그 → CloudWatch Logs /mc/ssm 90일"),
], note="NAT Gateway는 아웃바운드 전용(dnf·Agent·SSM). SSM은 사람이 들어가는 길, NAT는 서버가 나가는 길 — 둘 다 필요.")
mxfile.append(p.d)

# ================= tab 4: WAS 계층 =================
p = Page("3. WAS 계층", "tab-was", 2720, 1100)
p.title("③ WAS 계층 · Internal ALB → Tomcat Auto Scaling", "Internal ALB(8080 · sticky · 헬스체크 /petclinic/) → WAS ASG(Corretto 17 · Tomcat 9 · Spring Security OAuth2 Client) → RDS Proxy | 로그: Agent · 종료 훅 · 증설 정책", 2200)
p.vertex("vpc", "VPC 10.0.0.0/16", STY["vpc"], 260, 150, 1330, 860)
p.vertex("az-a", "가용영역 A", STY["az"], 290, 210, 480, 520)
p.vertex("az-c", "가용영역 C", STY["az"], 1080, 210, 480, 520)
p.vertex("asg", "Auto Scaling — WAS (min 2 · max 8 · 대상당 요청 수 + CPU · 예약 증설 · 워밍업 300s)", STY["asg"], 300, 380, 1250, 330)
p.vertex("was-a-sub", "프라이빗 WAS-A · 10.0.20.0/24", STY["priv"], 310, 410, 440, 280)
p.vertex("was-c-sub", "프라이빗 WAS-C · 10.0.21.0/24", STY["priv"], 1100, 410, 440, 280)
p.stub("from-web", "② WEB 계층에서<br>Apache ProxyPass /petclinic/", 60, 300)
p.service("ialb", "부하 분산 (내부)", "Internal ALB", "8080 · tg-was · sticky(AWSALB 1일)<br>헬스체크 /petclinic/", "application_load_balancer", "net", 860, 240, kind="sub")
p.service("was-a", "WAS", "WAS-A · Tomcat 9.0.121", "Corretto 17 · maxThreads·acceptCount<br>예약 등록 시 이벤트 로그 1줄", "ec2", "compute", 350, 470)
p.service("was-c", "WAS", "WAS-C · Tomcat 9.0.121", "AZ당 2대<br>한 AZ 손실 시 피크 100%", "ec2", "compute", 1140, 470)
p.stub("to-db", "→ ④ DB 계층<br>RDS Proxy 3306 · JDBC sslMode=REQUIRED", 840, 780, 200, 70)
p.stub("cog", "② Public ALB에서 인증 완료<br>x-amzn-oidc-data 헤더로 사용자 전달", 60, 560, 190, 70)
p.stub("evt", "⑤ CloudWatch Logs /mc/was/events<br>예약 이벤트 → Lambda → Slack", 60, 680, 190, 60)
p.service("cwl-was", "WAS 로그", "CloudWatch Logs", "/mc/was catalina·access·gc<br>/mc/was/auth 로그인 이벤트", "cloudwatch_logs", "integ", 1680, 280, kind="sub")
p.service("asg-svc", "증설 정책", "Auto Scaling", "대상당 요청 수 300/분 + CPU 60%<br>예약: 이벤트 15분 전 desired 4", "autoscaling", "compute", 1680, 480)
p.service("s3-logs", "종료 로그", "Amazon S3", "mc-logs/was · 종료 수명 주기 훅<br>마지막 로그 · 힙 덤프 sync", "s3", "storage", 1680, 680)
p.stub("cw", "⑤ CloudWatch 알람<br>→ 증설 · 축소 트리거", 1950, 505, 170, 70)
p.edge("e1", "from-web", "ialb", EDGE, pts=[(230,335),(230,190),(920,190)], exit=(1,0.5), entry=(0.5,0))
p.edge("e2", "ialb", "was-a", EDGE, pts=[(890,360),(410,360)], label="tg-was · 두 AZ", lx=0.2, ly=-12, exit=(0.25,1), entry=(0.5,0))
p.edge("e3", "ialb", "was-c", EDGE, pts=[(950,360),(1200,360)], exit=(0.75,1), entry=(0.5,0))
p.edge("e4", "was-a", "to-db", EDGE, pts=[(410,750),(840,750)], label="JDBC (풀 validationQuery)", lx=0.2, ly=-12, exit=(0.5,1), entry=(0,0.3))
p.edge("e5", "was-c", "to-db", EDGE, pts=[(1200,750),(1040,750)], exit=(0.5,1), entry=(1,0.3))
p.edge("e6", "cog", "was-a", EDGE_D, label="로그인 사용자 헤더", ly=-12, exit=(1,0.5), entry=(0,0.4))
p.edge("e7", "was-a", "evt", EDGE_D, pts=[(300,560),(300,710)], label="RESERVATION_CREATED 로그", lx=0.5, ly=12, exit=(0,0.75), entry=(1,0.5))
p.edge("e8", "was-c", "cwl-was", EDGE_D, pts=[(1290,530),(1290,340)], label="CloudWatch Agent", lx=0.3, ly=12, exit=(1,0.5), entry=(0,0.5))
p.edge("e9", "cw", "asg-svc", EDGE_D, label="알람", ly=-12, exit=(0,0.5), entry=(1,0.5))
p.edge("e10", "asg-svc", "s3-logs", EDGE_D, label="종료 훅 → sync", lx=0, ly=0, exit=(0.5,1), entry=(0.5,0))
p.edge("e11", "asg-svc", "was-c", EDGE_D, pts=[(1620,540),(1620,600)], label="증설·교체", lx=0.5, ly=12, exit=(0,0.5), entry=(1,0.75))
for n,(x,y) in {1:(240,270),2:(870,370),3:(430,760),4:(240,540),5:(1300,545),6:(1900,470)}.items(): p.badge(n,x,y)
p.legend(2080, 30, 1000, "WAS 계층 · 흐름과 설정", [
 ("Internal ALB (깊게)", "tg-was 헬스체크 /petclinic/(슬래시 필수, permitAll이라 로그인 리다이렉트 없음) 10s·2/3, 등록 취소 30s. 로그인 세션 때문에 stickiness(AWSALB 쿠키 1일) 켬 — Apache는 쿠키 그대로 전달"),
 ("Tomcat 튜닝", "maxThreads·acceptCount 상향, connectionTimeout 단축, JVM -Xms=-Xmx. 커넥션 풀 크기 = maxThreads와 DB 상한 사이"),
 ("WAS → RDS Proxy", "JDBC sslMode=REQUIRED, 풀 validationQuery. 8대로 늘어도 Proxy가 DB 연결 상한을 지킴(④ 탭)"),
 ("로그인 · 예약 이벤트", "로그인은 ② Public ALB의 authenticate-cognito가 처리(앱 수정 없음). ALB가 x-amzn-oidc-data 헤더로 사용자 정보를 전달하므로 test.jsp에서 출력 가능. 고객이 예약을 등록하면 구조화 로그 1줄(RESERVATION_CREATED vet·time) → CloudWatch Logs → ⑤ 탭에서 Slack 알림"),
 ("로그", "Agent → /mc/was catalina·access·gc 30일 + 로그인 성공/실패 이벤트 /mc/was/auth. 종료 수명 주기 훅(300s)으로 마지막 로그·덤프를 S3 mc-logs/was에 sync 후 종료"),
 ("증설", "대상당 요청 수 + CPU 대상 추적, 예약 증설(영상 공개 15분 전 4대), min 2·max 8, AZ당 2대. 알람은 ⑤ CloudWatch에서"),
], note="Redis(Spring Session)는 로드맵: 축소·전환 중 로그인 유지가 필요할 때. 현재는 sticky + 재로그인 허용.")
mxfile.append(p.d)

# ================= tab 5: DB 계층 · 확장 =================
p = Page("4. DB 계층", "tab-db", 2720, 800)
p.title("④ DB 계층 — RDS Multi-AZ · Proxy · 비밀 · 백업 (개인정보 저장소)", "WAS → RDS Proxy → RDS Primary ⇄ Standby(동기) | Secrets Manager 로테이션 · KMS · AWS Backup | 개인정보(이름·전화번호·예약)는 RDS, 진료 파일 저장은 시나리오 제외", 2200)
p.vertex("vpc", "VPC 10.0.0.0/16 · DB 서브넷 (인터넷 경로 없음) · 개인정보 저장소", STY["vpc"], 260, 150, 1330, 480)
p.vertex("az-a", "가용영역 A", STY["az"], 290, 210, 480, 390)
p.vertex("az-c", "가용영역 C", STY["az"], 1080, 210, 480, 390)
p.vertex("db-a", "프라이빗 DB-A · 10.0.30.0/24", STY["priv"], 310, 250, 440, 320)
p.vertex("db-c", "프라이빗 DB-C · 10.0.31.0/24", STY["priv"], 1100, 250, 440, 320)
p.stub("from-was", "③ WAS 계층에서<br>JDBC sslMode=REQUIRED", 60, 330)
p.service("proxy", "커넥션 관리", "RDS Proxy", "다중화 · failover 단축<br>Require TLS · Secrets 직접 조회", "rds_proxy", "db", 860, 300, kind="sub")
p.service("rds-p", "관계형 DB (주) · 개인정보", "RDS MySQL 8.0 Primary", "개인정보 저장소(owners·pets·visits)<br>db.t3.small · KMS · TLS", "rds", "db", 400, 330)
p.service("rds-s", "관계형 DB (대기)", "RDS Standby", "동기 복제 (RPO 0)<br>자동 failover 60~120s", "rds", "db", 1180, 330)
p.service("secrets", "비밀 관리", "Secrets Manager", "RDS 관리형 비밀<br>7일 자동 로테이션", "secrets_manager", "sec", 1680, 200)
p.service("kms", "암호화 키", "AWS KMS", "CMK · 버킷 키<br>S3 · RDS · Secrets", "key_management_service", "sec", 1680, 400)
p.service("backup", "백업", "AWS Backup", "자동 백업 7일 · PITR 5분<br>Phase 전 스냅샷 · 삭제 방지", "backup", "storage", 1680, 600)
p.edge("e1", "from-was", "proxy", EDGE, pts=[(230,365),(230,190),(920,190)], exit=(1,0.5), entry=(0.5,0))
p.edge("e2", "proxy", "rds-p", EDGE, label="Primary 엔드포인트", ly=-12, exit=(0,0.5), entry=(1,0.5))
p.edge("e3", "rds-p", "rds-s", EDGE_BI, pts=[(460,520),(1240,520)], label="동기 복제 · 자동 failover", lx=0, ly=-11, exit=(0.5,1), entry=(0.5,1))
p.edge("e4", "secrets", "proxy", EDGE_D, pts=[(1740,170),(920,170)], label="자격증명 · 로테이션은 Proxy 뒤에서(앱 무영향)", lx=0.3, ly=-11, exit=(0.5,0), entry=(0.5,0))
p.edge("e5", "kms", "secrets", EDGE_D, exit=(0.5,0), entry=(0.5,1))
p.edge("e6", "rds-s", "backup", EDGE_D, pts=[(1240,560),(1600,560),(1600,660)], label="Standby에서 백업", lx=0.5, ly=12, exit=(0.5,1), entry=(0,0.5))
for n,(x,y) in {1:(240,300),2:(880,330),3:(470,528),4:(1700,150),5:(1300,565)}.items(): p.badge(n,x,y)
p.legend(2080, 30, 760, "DB 계층 — 흐름과 설정", [
 ("WAS → RDS Proxy", "JDBC sslMode=REQUIRED + 파라미터 그룹 require_secure_transport. Proxy: 커넥션 다중화(풀×서버 수 > DB 상한 방지), failover 중 연결 유지, Require TLS"),
 ("Primary 엔드포인트", "Proxy → Primary만 쓰기. Read Replica는 앱이 읽기/쓰기 데이터소스를 나눠야 해서 로드맵"),
 ("Multi-AZ 동기 복제 · 개인정보 저장소", "개인정보는 RDS에 저장(PetClinic owners·pets·visits 그대로). 요구 'RPO 0(24시간 무손실)' = 동기 복제. failover 60~120s, 엔드포인트 동일. Multi-AZ는 백업이 아님(실수 삭제는 복제됨) → PITR"),
 ("Secrets Manager + KMS", "RDS 관리형 비밀 7일 로테이션, Proxy가 직접 조회 → 앱 무영향. Secrets·RDS·S3 모두 KMS CMK, S3는 버킷 키로 비용 절감"),
 ("백업", "자동 백업 7일(Standby에서, 19:00 UTC), PITR 5분, Phase 전 수동 스냅샷(mc-before-phase2/3), 삭제 방지, 도쿄 스냅샷 복사는 로드맵. 6일차 failover·PITR 드릴"),
], note="개인정보는 RDS(PetClinic owners·pets·visits). 진료 파일 S3 저장·Object Lock Compliance·Macie는 시나리오에서 제외(되돌릴 수 없고 발표 축과 무관). Redis는 로드맵. 감사(CloudTrail 관리 이벤트)는 ⑤ 운영 탭.")
mxfile.append(p.d)

# ================= tab 6: 운영 · 관측 공통 =================
p = Page("5. 운영 · 관측 공통", "tab-ops", 2720, 1100)
p.title("⑤ 운영 · 관측 공통 — CloudWatch · Grafana · Slack · CloudTrail · SSM", "계층별 로그 5종 → CloudWatch / S3 → Managed Grafana 대시보드 → Slack | 알람 → SNS → Chatbot → Slack · Auto Scaling 트리거", 2200)
p.vertex("cloud", "AWS Cloud (ap-northeast-2)", STY["cloud"], 260, 150, 1330, 780)
p.stub("in-web", "② WEB Agent 로그<br>/mc/web", 60, 200, 170, 60)
p.stub("in-was", "③ WAS Agent 로그<br>/mc/was · auth · events(예약)", 60, 290, 170, 60)
p.stub("in-alb", "② ALB 액세스 로그<br>S3 mc-logs", 60, 380, 170, 60)
p.stub("in-waf", "① WAF 로그<br>aws-waf-logs-mc", 60, 470, 170, 60)
p.stub("in-ssm", "② SSM 세션 로그<br>/mc/ssm", 60, 560, 170, 60)
p.service("cwl", "로그 저장", "CloudWatch Logs", "/mc/* · aws-waf-logs-mc<br>보존 30~90일 · Logs Insights", "cloudwatch_logs", "integ", 340, 330, kind="sub")
p.service("cw", "지표 · 알람", "Amazon CloudWatch", "RequestCount · p95 · 5XX · HealthyHost<br>DB 연결 · CPU · DaysToExpiry", "cloudwatch", "integ", 640, 330)
p.service("grafana", "대시보드", "Amazon Managed Grafana", "Identity Center 로그인<br>계층별 행 · 전/후 비교", "managed_service_for_grafana", "integ", 940, 200)
p.service("sns", "알림 주제", "Amazon SNS", "mc-alerts", "sns", "integ", 940, 460)
p.service("chatbot", "채팅 연동", "AWS Chatbot", "SNS → Slack #mc-alerts", "chatbot", "integ", 1220, 460)
p.service("trail", "감사 추적", "AWS CloudTrail", "관리 이벤트 + S3 데이터 이벤트<br>다중 리전 · 검증", "cloudtrail", "integ", 640, 680)
p.service("s3-trail", "감사 로그", "Amazon S3", "mc-cloudtrail · 1년", "s3", "storage", 940, 680)
p.service("ssm", "운영자 접속", "SSM Session Manager", "22번 없음 · 세션 로그<br>Run Command · 패치", "systems_manager_session_manager", "integ", 1220, 680, kind="sub")
p.service("lambda-notify", "예약 알림", "AWS Lambda", "구독 필터 RESERVATION_CREATED<br>수의사·시간·링크 → Slack", "lambda", "compute", 340, 680)
p.actor("vet", "수의사 (Slack → Cognito 로그인)", 1680, 200, res="user")
p.stub("to-asg", "③ WAS Auto Scaling<br>대상 추적 · 알람 트리거", 1220, 230, 170, 60)
p.actor("slack", "Slack (#mc-alerts)", 1680, 360, res="users")
p.actor("ops", "운영자 (관리자)", 1680, 700, res="user")
for i,(src,yy) in enumerate([("in-web",230),("in-was",320),("in-alb",410),("in-waf",500),("in-ssm",590)],1):
    if src=="in-alb": continue
    p.edge(f"i{i}", src, "cwl", EDGE_D, exit=(1,0.5), entry=(0,0.5))
p.edge("i3", "in-alb", "cw", EDGE_D, pts=[(300,410),(300,470),(700,470)], label="S3 → Athena/Logs Insights 분석", lx=0.4, ly=12, exit=(1,0.5), entry=(0.5,1))
p.edge("e1", "cwl", "cw", EDGE_D, label="지표 필터", ly=-12, exit=(1,0.5), entry=(0,0.5))
p.edge("e2", "cw", "grafana", EDGE, pts=[(700,260)], label="지표 · 로그 쿼리", lx=0.3, ly=-12, exit=(0.5,0), entry=(0,0.5))
p.edge("e3", "cw", "sns", EDGE, pts=[(700,520)], label="알람 3개 (HealthyHost<2 · DB 연결 80% · p95≥2s)", lx=0.3, ly=12, exit=(0.5,1), entry=(0,0.5))
p.edge("e4", "sns", "chatbot", EDGE, exit=(1,0.5), entry=(0,0.5))
p.edge("e5", "chatbot", "slack", EDGE, pts=[(1500,520),(1500,409)], label="#mc-alerts", lx=0.5, ly=-12, exit=(1,0.5), entry=(0,0.5))
p.edge("e6", "grafana", "slack", EDGE_D, pts=[(1500,260),(1500,390)], label="Grafana Alerting → Slack 직접", lx=0.3, ly=-12, exit=(1,0.5), entry=(0,0.3))
p.edge("e7", "cw", "to-asg", EDGE_D, pts=[(760,160),(1305,160)], label="대상 추적 알람 → 증설·축소", lx=0.5, ly=-11, exit=(0.75,0), entry=(0.5,0))
p.edge("e8", "trail", "s3-trail", EDGE, label="1년 · 검증", ly=-12, exit=(1,0.5), entry=(0,0.5))
p.edge("e9", "ops", "ssm", EDGE, label="IAM · MFA", ly=-12, exit=(0,0.5), entry=(1,0.5))
p.edge("e10", "ssm", "cwl", EDGE_D, pts=[(1280,650),(1280,600),(430,600)], label="세션 로그", lx=0.6, ly=12, exit=(0.5,0), entry=(0.75,1))
p.edge("e11", "cwl", "lambda-notify", EDGE_D, label="구독 필터 (예약 이벤트)", lx=0, ly=0, exit=(0.25,1), entry=(0.25,0))
p.edge("e12", "lambda-notify", "slack", EDGE, pts=[(400,860),(1560,860),(1560,440)], label="#mc-reservations 예약 알림 (수의사·시간·링크)", lx=0.2, ly=12, exit=(0.5,1), entry=(0,0.8))
p.edge("e13", "slack", "vet", EDGE_D, label="링크 클릭 → Cognito 로그인 → 예약 확인", lx=0, ly=-12, exit=(0.5,0), entry=(0.5,1))
for n,(x,y) in {1:(300,300),2:(610,300),3:(720,215),4:(720,540),5:(1490,375),6:(1300,120),7:(770,650),8:(1640,670),9:(470,650)}.items(): p.badge(n,x,y)
p.legend(2080, 30, 1000, "운영 · 관측 공통 — 흐름과 설정", [
 ("로그 수집 (필수 5)", "① WAF 로그 ② WEB Agent ③ WAS Agent ④ ALB 액세스(S3) ⑤ SSM 세션. VPC Flow Logs·RDS 로그는 제외(필요 시 로드맵). 로그는 항상 인스턴스 밖에"),
 ("CloudWatch 지표 · 알람", "ALB RequestCount·TargetResponseTime p95·5XX·HealthyHost, ASG 인스턴스 수, RDS CPU·DatabaseConnections, ACM DaysToExpiry. 알람 3개 + 대상 추적 알람"),
 ("Grafana 대시보드", "Amazon Managed Grafana(Identity Center 로그인, 편집자 $9/월). CloudWatch 데이터소스. 행: 진입 → ALB → EC2 → RDS. Phase 3 전/후 비교는 Time shift"),
 ("알람 → Slack (2경로)", "AWS 자체 알람: CloudWatch → SNS mc-alerts → AWS Chatbot → #mc-alerts(코드 없음). 대시보드 지표 알림: Grafana Alerting → Slack webhook 직접. 6일차 WAS 1대 중지로 수신 테스트"),
 ("Slack", "webhook URL은 Grafana Contact point에만(저장소에 남기지 않음). Chatbot은 Slack 워크스페이스 인증 후 채널에 SNS 구독"),
 ("알람 → Auto Scaling", "WAS ASG 대상 추적(대상당 요청 수·CPU)이 CloudWatch 알람으로 동작. 예약 증설과 병행"),
 ("감사", "CloudTrail 관리 이벤트 90일 무료 + 추적으로 S3 1년 보관, S3 데이터 이벤트로 의료 파일 열람 기록"),
 ("운영자 접속", "SSM Session Manager(IAM·MFA) → 세션 로그 CloudWatch Logs. Run Command로 다수 인스턴스 설정 배포, Patch Manager로 롤링 패치"),
 ("예약 알림 (업무 이벤트)", "고객 예약 등록 → WAS 로그 1줄(RESERVATION_CREATED vet·time·id) → CloudWatch Logs 구독 필터 → Lambda(20줄) → Slack #mc-reservations(수의사·시간·링크). 수의사가 링크 클릭 → Cognito OIDC 로그인 → 예약 화면. 같은 로그의 지표 필터로 예약 건수 대시보드·폭주 알람"),
], note="Systems Manager 하나로 접속·명령·패치 처리, Bastion 없음. 예약 알림은 시스템 알람(SNS→Chatbot)과 채널을 분리(#mc-alerts / #mc-reservations).")
mxfile.append(p.d)

tree = ET.ElementTree(mxfile); ET.indent(tree, space="  ")
out = "/home/grapefruit/middleproject/docs/architecture-tiered-tabs.drawio"
tree.write(out, encoding="utf-8", xml_declaration=False); print("wrote", out)
