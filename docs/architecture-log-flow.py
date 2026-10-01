"""로그 흐름 도면 (2026-09-17): 각 계층의 로그가 어디서 만들어져 어떤 경로로 CloudWatch Logs / S3 에 놓이는지.
DB 계층은 Agent 가 아니라 RDS 로그 내보내기(error·slowquery) + Proxy 자체 로그 → CloudWatch Logs → 구독 필터 → Firehose → S3 사본.
실행: python3 docs/architecture-log-flow.py [--png] → docs/architecture-log-flow.drawio / .png"""
import html as _html, json, os, subprocess, sys
import xml.etree.ElementTree as ET

PTS = "points=[[0,0,0],[0.25,0,0],[0.5,0,0],[0.75,0,0],[1,0,0],[0,1,0],[0.25,1,0],[0.5,1,0],[0.75,1,0],[1,1,0],[0,0.25,0],[0,0.5,0],[0,0.75,0],[1,0.25,0],[1,0.5,0],[1,0.75,0]]"
FONT = "fontFamily=Helvetica;"
CAT = {"compute": ("#FFF2E8", "#ED7100"), "db": ("#F5E6F7", "#C925D1"), "net": ("#EDE7F6", "#8C4FFF"), "sec": ("#FFEBEE", "#DD344C"),
       "ops": ("#FCE4EC", "#E7157B"), "stor": ("#E8F5E9", "#1B8B3B"), "gen": ("#F5F5F5", "#666666")}
PINK, GREEN, GREY = "#E7157B", "#1B8B3B", "#9E9E9E"
E_BASE = "edgeStyle=orthogonalEdgeStyle;html=1;elbow=horizontal;rounded=0;strokeWidth=1.5;" + FONT
E_CW = E_BASE + f"endArrow=block;endFill=1;strokeColor={PINK};"           # → CloudWatch Logs (이벤트)
E_S3 = E_BASE + f"endArrow=block;endFill=1;strokeColor={GREEN};"          # → S3 (객체)
E_S3D = E_BASE + f"endArrow=block;endFill=1;strokeColor={GREEN};dashed=1;" # 사본
E_GREY = E_BASE + f"endArrow=open;strokeColor={GREY};dashed=1;"

mxfile = ET.Element("mxfile", host="Electron", version="29.6.1")
dg = ET.SubElement(mxfile, "diagram", name="로그 흐름 (2026-09-17)", id="logflow-1")
model = ET.SubElement(dg, "mxGraphModel", dx="1600", dy="900", grid="0", gridSize="10", guides="1", tooltips="1", connect="1", arrows="1", fold="1",
                      page="0", pageScale="1", pageWidth="2000", pageHeight="1250", math="0", shadow="0")
root = ET.SubElement(model, "root"); ET.SubElement(root, "mxCell", id="0"); ET.SubElement(root, "mxCell", id="1", parent="0")

def v(cid, value, style, x, y, w, h, parent="1"):
    c = ET.SubElement(root, "mxCell", id=cid, value=value, style=style, vertex="1", parent=parent)
    ET.SubElement(c, "mxGeometry", x=str(x), y=str(y), width=str(w), height=str(h)).set("as", "geometry")
def text(cid, value, x, y, w, h, color="#232F3E", size=13, bold=False, align="left"):
    v(cid, value, f"text;html=1;whiteSpace=wrap;strokeColor=none;fillColor=none;align={align};verticalAlign=top;fontSize={size};fontStyle={1 if bold else 0};fontColor={color};{FONT}", x, y, w, h)
def box(cid, title, sub, res, cat, x, y, w=200, h=112, optional=False):
    tint, stroke = (("#FAFAFA", GREY) if optional else CAT[cat]); dashed = "dashed=1;dashPattern=6 4;" if optional else ""
    v(f"grp-{cid}", title, f"fillColor={tint};strokeColor={stroke};rounded=1;whiteSpace=wrap;html=1;verticalAlign=top;fontStyle=1;fontSize=12;fontColor={stroke};{FONT}container=1;collapsible=0;shadow=1;strokeWidth=1.5;{dashed}", x, y, w, h)
    v(cid, sub, f"sketch=0;{PTS};outlineConnect=0;fontColor=#232F3E;fillColor={GREY if optional else stroke};strokeColor=#ffffff;dashed=0;verticalLabelPosition=bottom;verticalAlign=top;align=center;html=1;fontSize=10;fontStyle=0;aspect=fixed;shape=mxgraph.aws4.resourceIcon;resIcon=mxgraph.aws4.{res};{FONT}", w // 2 - 22, 24, 44, 44, parent=f"grp-{cid}")
def edge(cid, s, t, style, label=None, pts=None, exit=None, entry=None, lx=0, ly=-11):
    st = style + (f"exitX={exit[0]};exitY={exit[1]};exitDx=0;exitDy=0;" if exit else "") + (f"entryX={entry[0]};entryY={entry[1]};entryDx=0;entryDy=0;" if entry else "")
    c = ET.SubElement(root, "mxCell", id=cid, style=st, edge="1", parent="1", source=s, target=t); g = ET.SubElement(c, "mxGeometry", relative="1"); g.set("as", "geometry")
    if pts:
        a = ET.SubElement(g, "Array"); a.set("as", "points")
        for px, py in pts: ET.SubElement(a, "mxPoint", x=str(px), y=str(py))
    if label:
        l = ET.SubElement(root, "mxCell", id=f"{cid}-l", value=label, style=f"edgeLabel;html=1;align=center;verticalAlign=middle;resizable=0;points=[];labelBackgroundColor=#FFFFFF;fontSize=11;{FONT}", connectable="0", vertex="1", parent=cid)
        lg = ET.SubElement(l, "mxGeometry", relative="1", x=str(lx), y=str(ly)); lg.set("as", "geometry"); ET.SubElement(lg, "mxPoint").set("as", "offset")
def lane(cid, title, x, y, w, h, color):
    v(cid, title, f"rounded=0;fillColor=none;dashed=1;strokeColor={color};verticalAlign=top;align=left;spacingLeft=8;fontColor={color};fontStyle=1;fontSize=13;whiteSpace=wrap;html=1;container=0;pointerEvents=0;{FONT}", x, y, w, h)
def note(cid, value, x, y, w, h, color="#0B5394", fill="#F3F6FB"):
    v(cid, value, f"rounded=1;whiteSpace=wrap;html=1;fillColor={fill};strokeColor={color};strokeWidth=1.5;align=left;verticalAlign=top;fontSize=11;fontColor=#232F3E;spacing=8;{FONT}", x, y, w, h)

# ---------- 제목 ----------
text("title", "로그 흐름 — 어디서 만들어져 어디에 놓이나 (mc-deploy · 2026-09-17)", 40, 20, 1500, 36, size=24, bold=True)
text("sub", "분홍 = CloudWatch Logs 로 (로그 이벤트 · 자체 저장소) · 초록 = S3 객체로 (5분 단위 .gz) · 초록 점선 = CloudWatch Logs 의 <b>사본</b>(구독 필터 → Firehose) · 회색 = 로드맵. DB 계층은 Agent 가 없고 <b>RDS 로그 내보내기 · Proxy 자체 로그</b>가 CloudWatch Logs 로 간다.",
     40, 58, 1800, 24, size=12, color="#555555")

# ---------- 레인 ----------
lane("lane-src", "① 로그가 만들어지는 곳 (계층)", 40, 100, 470, 1080, "#666666")
lane("lane-cw", "② CloudWatch Logs — 계정에 1개 · VPC 밖 · 로그 그룹만 계층별", 560, 100, 500, 640, PINK)
lane("lane-fh", "③ 사본 전달 — 구독 필터 → Kinesis Data Firehose (계층당 1개)", 1110, 100, 400, 640, GREEN)
lane("lane-s3", "④ S3 — 객체 (장기 보관)", 1520, 100, 440, 1080, GREEN)

# ---------- ① 소스 ----------
box("web", "② WEB ×2 · Apache", "mc-web-a/c<br>access_log · error_log", "ec2", "compute", 70, 140)
box("was", "③ WAS ×2 · Tomcat", "mc-was-a/c<br>catalina.out · access · gc.log", "ec2", "compute", 70, 280)
box("bastion", "⑬ Bastion", "mc-bastion<br>/var/log/secure (sshd)", "ec2", "compute", 70, 420)
box("rds", "④ RDS MySQL 8.4 Multi-AZ", "mc-petclinic<br>error · <b>slowquery</b>(long_query_time 2s)", "rds", "db", 70, 580)
box("proxy", "④ RDS Proxy", "mc-rds-proxy<br>연결·인증 로그", "rds_proxy", "db", 300, 580)
box("waf", "① WAF Web ACL (us-east-1)", "mc-web-acl<br>규칙 매치 · 차단", "waf", "sec", 70, 760)
box("alb", "②③ ALB ×2", "mc-alb-public · mc-alb-internal<br>액세스 로그", "application_load_balancer", "net", 70, 900)
box("cf", "① CloudFront", "E2PWXW3LUYTDEE<br>표준 액세스 로그", "cloudfront", "net", 300, 900)
box("trail", "계정 · CloudTrail", "mc-trail · 다중 리전<br>관리 이벤트 (누가 무엇을 바꿨나)", "cloudtrail", "ops", 70, 1040)
text("agent-note", "CloudWatch Agent (user_data 설치 · 설정은 Parameter Store /petclinic/cwagent/*)", 290, 228, 220, 44, size=11, color=PINK, bold=True)

# ---------- ② CloudWatch Logs ----------
box("cwl", "CloudWatch Logs (서울) · KMS mc-cmk", "로그 이벤트 저장소<br>스트림 = 인스턴스 ID", "cloudwatch_logs", "ops", 590, 380, w=200, h=118)
note("groups", "<b>로그 그룹 (보존)</b><br>/petclinic/web/access · /petclinic/web/error · 30일<br>/petclinic/was/catalina · access · gc · 30일<br>/petclinic/bastion/secure · 90일<br><b>/aws/rds/instance/mc-petclinic/error · /slowquery · 30일</b><br><b>/aws/rds/proxy/mc-rds-proxy · 30일</b><br><i>(RDS·Proxy 그룹은 이름이 고정 → 코드가 먼저 만들어 보존·KMS 적용)</i>", 800, 212, 240, 160, color=PINK, fill="#FCE4EC")
box("cwl-waf", "CloudWatch Logs (us-east-1)", "aws-waf-logs-mc · 30일<br>리전이 달라 사본 제외", "cloudwatch_logs", "ops", 590, 580, w=200, h=118)
note("cw-note", "<b>S3 가 아니다</b> — 파일·객체·블록 어느 것도 아닌 로그 이벤트 DB. 검색은 Logs Insights. 아래 ③은 <b>사본</b>을 S3 에 두는 것이고 원본은 여기 남는다.", 590, 132, 450, 70)

# ---------- ③ Firehose ----------
box("fh", "Kinesis Data Firehose ×4", "mc-cwlogs-web · was · bastion · <b>db</b><br>5분 / 5MB 버퍼 · gzip 해제 → 줄 JSON", "kinesis_data_firehose", "ops", 1190, 380, w=220, h=118)
note("fh-note", "<b>구독 필터</b> (로그 그룹마다 1개 · 필터 없음 = 전부)<br>역할 mc-cwlogs-to-firehose-role → PutRecordBatch<br>Firehose 역할 mc-firehose-cwlogs-role → S3 PutObject<br>레코드 = {logGroup, logStream, logEvents[]}", 1130, 520, 320, 110, color=GREEN, fill="#E8F5E9")

# ---------- ④ S3 ----------
box("s3logs", "S3 mc-logs-528821350786", "SSE-S3 · 버전 관리 · 퍼블릭 차단", "simple_storage_service", "stor", 1600, 380, w=220, h=118)
note("s3-prefix", "<b>접두사 · 보관</b><br>cwlogs/web|was|bastion|db/yyyy/MM/dd/ · <b>1년</b> (CloudWatch Logs 사본)<br>cwlogs-errors/ · 30일<br>alb/public · alb/internal · 90일<br>cloudfront/ · 90일<br>was/ web/ · 30일 (ASG 종료 훅 · 로드맵)", 1550, 520, 380, 150, color=GREEN, fill="#E8F5E9")
box("s3trail", "S3 mc-cloudtrail-528821350786", "SSE-KMS · 로그 파일 검증<br>90일 → Glacier IR · 1년", "simple_storage_service", "stor", 1600, 1030, w=220, h=118)
note("s3-note", "<b>객체</b> — 5분마다 새 .gz 가 생기고 append 는 없다. 조회는 Athena. 서버가 사라져도 남는다.", 1550, 700, 380, 50, color=GREEN, fill="#E8F5E9")

# ---------- 화살표 ----------
edge("e-web", "grp-web", "grp-cwl", E_CW, label="Agent", pts=[(520, 196), (520, 415)], exit=(1, 0.5), entry=(0, 0.3), lx=0.05)
edge("e-was", "grp-was", "grp-cwl", E_CW, label="Agent", pts=[(520, 336), (520, 433)], exit=(1, 0.5), entry=(0, 0.45), lx=0.1)
edge("e-bastion", "grp-bastion", "grp-cwl", E_CW, label="Agent", pts=[(520, 476), (520, 451)], exit=(1, 0.5), entry=(0, 0.6), lx=0.1)
edge("e-rds", "grp-rds", "grp-cwl", E_CW, label="RDS 로그 내보내기 (error · slowquery) — Agent 없음", pts=[(170, 730), (565, 730), (565, 486)], exit=(0.5, 1), entry=(0, 0.9), lx=-0.1, ly=12)
edge("e-proxy", "grp-proxy", "grp-cwl", E_CW, label="Proxy 자체 로그", pts=[(540, 636), (540, 468)], exit=(1, 0.5), entry=(0, 0.75), lx=0.55, ly=-11)
edge("e-waf", "grp-waf", "grp-cwl-waf", E_CW, label="WAF 로깅 (같은 리전 us-east-1)", pts=[(578, 816), (578, 657)], exit=(1, 0.5), entry=(0, 0.65), lx=-0.35, ly=-11)
edge("e-cw-fh", "grp-cwl", "grp-fh", E_S3D, label="구독 필터 (사본)", exit=(1, 0.5), entry=(0, 0.5))
edge("e-fh-s3", "grp-fh", "grp-s3logs", E_S3D, label="cwlogs/‹tier›/ · gzip", exit=(1, 0.5), entry=(0, 0.5), lx=-0.35)
edge("e-alb", "grp-alb", "grp-s3logs", E_S3, label="서비스가 5분마다 직접 → alb/", pts=[(1540, 956), (1540, 468)], exit=(1, 0.5), entry=(0, 0.75), lx=-0.25, ly=-11)
edge("e-cf", "grp-cf", "grp-s3logs", E_S3, label="서비스가 직접 (≤1시간) → cloudfront/", pts=[(370, 1000), (1560, 1000), (1560, 486)], exit=(0.5, 1), entry=(0, 0.9), lx=-0.2, ly=12)
edge("e-trail", "grp-trail", "grp-s3trail", E_S3, label="서비스가 5분마다 직접 (계정 수준 · VPC·리전 밖)", exit=(1, 0.5), entry=(0, 0.5))
edge("e-waf-x", "grp-cwl-waf", "grp-fh", E_GREY, label="사본 없음 (리전 다름) — 필요하면 us-east-1 에 Firehose 별도", pts=[(1080, 639), (1080, 468)], exit=(1, 0.5), entry=(0, 0.75), lx=-0.15, ly=12)

# ---------- 범례 ----------
note("legend", "<b>한 줄 요약</b> — 서버(WEB·WAS·Bastion)는 <b>Agent</b> 로, 관리형(RDS·Proxy·WAF)은 <b>서비스 설정</b>으로 CloudWatch Logs 에 남기고, ALB·CloudFront·CloudTrail 은 <b>S3 로 직접</b>. CloudWatch Logs 의 모든 그룹은 <b>구독 필터 → Firehose → S3 cwlogs/</b> 로 1년 사본을 둔다. 서버(EBS)에는 로그를 두지 않는다 → 교체·축소해도 유실 0.<br>"
     "<b>DB 계층 답</b>: RDS → CloudWatch Logs(내보내기) → Firehose(mc-cwlogs-db) → S3 mc-logs/cwlogs/db/. 코드: <code>infra/terraform-kdt5/logs_archive.tf</code> · <code>rds.tf</code> (9/17)",
     560, 770, 900, 122)
note("cost", "<b>비용 감</b> Firehose GB 당 ≈ $0.03 + S3 GB·월 $0.025 — 우리 로그 MB 단위 → 월 $1 미만. Logs Insights 는 스캔 GB 당 $0.005.", 560, 898, 900, 40, color="#666666", fill="#F5F5F5")

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "architecture-log-flow.drawio")
tree = ET.ElementTree(mxfile); ET.indent(tree, space="  "); tree.write(OUT, encoding="utf-8", xml_declaration=False); print("wrote", OUT)

def render(drawio, png, w=2000, h=1250):
    xml = open(drawio, encoding="utf-8").read()
    cfg = json.dumps({"xml": xml, "nav": False, "resize": True, "toolbar": "", "lightbox": False})
    html = f"<html><body style='margin:0;background:#fff'><div class='mxgraph' style='max-width:100%;border:0' data-mxgraph='{_html.escape(cfg, quote=True)}'></div><script src='https://viewer.diagrams.net/js/viewer-static.min.js'></script></body></html>"
    tmp = os.path.join(os.environ.get("SCRATCH", "/tmp"), "logflow-render.html"); open(tmp, "w", encoding="utf-8").write(html)
    subprocess.run(["google-chrome", "--headless=new", "--disable-gpu", "--no-sandbox", "--hide-scrollbars", "--virtual-time-budget=30000", "--force-device-scale-factor=2", f"--window-size={w},{h}", f"--screenshot={png}", "file://" + tmp], check=True, capture_output=True)
    print("wrote", png)
if __name__ == "__main__" and "--png" in sys.argv:
    render(OUT, OUT.replace(".drawio", ".png"))
