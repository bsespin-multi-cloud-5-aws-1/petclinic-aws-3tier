import base64, os
R = '/home/grapefruit/.local/share/aws-diagram-mcp-server/venv/lib/python3.12/site-packages/resources/aws'
ICON = {
 'users': 'general/users.png', 'jmeter': 'compute/ec2-instance.png', 'route53': 'network/route-53.png',
 'cloudfront': 'network/cloudfront.png', 'waf': 'security/waf.png', 'igw': 'network/internet-gateway.png',
 'alb': 'network/elb-application-load-balancer.png', 'nat': 'network/nat-gateway.png', 'ec2': 'compute/ec2-instance.png',
 'rds': 'database/rds.png', 'proxy': 'database/rds-instance.png', 'cw': 'management/cloudwatch.png',
 'sns': 'integration/simple-notification-service-sns.png', 'secrets': 'security/secrets-manager.png', 'ssm': 'management/systems-manager.png',
}
def b64(k):
    with open(os.path.join(R, ICON[k]), 'rb') as f: return 'data:image/png;base64,' + base64.b64encode(f.read()).decode()

W, H = 1920, 1080
NAVY='#232F3E'; GRAY='#545B64'; MUTE='#6B7280'
out = []
def add(s): out.append(s)
def esc(t): return t.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')

def box(x,y,w,h,stroke,fill='none',dash=None,label=None,lcolor=None,lpos='tl',sw=1.6,rx=6,fs=15,lx=12):
    d = f' stroke-dasharray="{dash}"' if dash else ''
    add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{d}/>')
    if label:
        lc = lcolor or stroke
        if lpos=='tl': add(f'<text x="{x+lx}" y="{y+20}" font-size="{fs}" font-weight="700" fill="{lc}">{esc(label)}</text>')
        else: add(f'<text x="{x+w-12}" y="{y+20}" font-size="{fs}" font-weight="700" fill="{lc}" text-anchor="end">{esc(label)}</text>')

def icon(k,cx,cy,size,title=None,sub=None,badge=None,backdrop=False,lw=None):
    if backdrop:
        add(f'<rect x="{cx-size/2-8}" y="{cy-size/2-8}" width="{size+16}" height="{size+16}" rx="8" fill="#FFFFFF"/>')
    add(f'<image href="{b64(k)}" x="{cx-size/2}" y="{cy-size/2}" width="{size}" height="{size}"/>')
    ty = cy+size/2+18
    if backdrop and (title or sub):
        bw = max(len(title or '')*9, len(sub or '')*7)+12
        add(f'<rect x="{cx-bw/2}" y="{ty-14}" width="{bw}" height="{36 if sub else 20}" rx="4" fill="#FFFFFF"/>')
    if title: add(f'<text x="{cx}" y="{ty}" font-size="13.5" font-weight="700" fill="{NAVY}" text-anchor="middle">{esc(title)}</text>')
    if sub: add(f'<text x="{cx}" y="{ty+16}" font-size="11.5" font-style="italic" fill="{MUTE}" text-anchor="middle">{esc(sub)}</text>')
    if badge is not None:
        bx, by = cx+size/2-6, cy-size/2-6
        add(f'<rect x="{bx}" y="{by-14}" width="26" height="26" rx="4" fill="#1B6AC9" stroke="#FFFFFF" stroke-width="2"/>')
        add(f'<text x="{bx+13}" y="{by+5}" font-size="15" font-weight="700" fill="#FFFFFF" text-anchor="middle">{badge}</text>')

def badge(x,y,n):
    add(f'<rect x="{x}" y="{y}" width="26" height="26" rx="4" fill="#1B6AC9" stroke="#FFFFFF" stroke-width="2"/>')
    add(f'<text x="{x+13}" y="{y+19}" font-size="15" font-weight="700" fill="#FFFFFF" text-anchor="middle">{n}</text>')

def path(pts,dash=None,arrow=True,color=GRAY,sw=1.8,both=False):
    d = 'M ' + ' L '.join(f'{x} {y}' for x,y in pts)
    da = f' stroke-dasharray="{dash}"' if dash else ''
    me = ' marker-end="url(#arr)"' if arrow else ''
    ms = ' marker-start="url(#arrs)"' if both else ''
    add(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{sw}"{da}{me}{ms}/>')

def label(x,y,t,size=12,color=GRAY,anchor='middle',bg=True,rot=None,weight=400):
    tr = f' transform="rotate({rot} {x} {y})"' if rot else ''
    if bg:
        w = len(t)*size*0.62+12
        ax = x - (w/2 if anchor=='middle' else (0 if anchor=='start' else w))
        add(f'<rect x="{ax}" y="{y-size}" width="{w}" height="{size+6}" fill="#FFFFFF" opacity="0.9"{tr}/>')
    add(f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" fill="{color}" text-anchor="{anchor}"{tr}>{esc(t)}</text>')

# ---------- canvas ----------
add(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="Noto Sans CJK KR, Noto Sans KR, Helvetica, Arial, sans-serif">')
add('<defs><marker id="arr" markerWidth="10" markerHeight="10" refX="9" refY="5" orient="auto" markerUnits="userSpaceOnUse"><path d="M0,0 L10,5 L0,10 z" fill="#545B64"/></marker>'
    '<marker id="arrs" markerWidth="10" markerHeight="10" refX="1" refY="5" orient="auto-start-reverse" markerUnits="userSpaceOnUse"><path d="M0,0 L10,5 L0,10 z" fill="#545B64"/></marker></defs>')
add(f'<rect width="{W}" height="{H}" fill="#FFFFFF"/>')

# groups
box(230,50,1650,1018,NAVY,'#FFFFFF',label='AWS Cloud',lcolor=NAVY,fs=16)
box(430,90,1290,960,'#00A4A6',dash='8 5',label='ap-northeast-2 (Seoul)',lpos='tr')
box(460,150,1230,880,'#8C4FFF','#FCFBFF',label='VPC 10.0.0.0/16')
for ax,name in ((490,'Availability Zone A'),(1140,'Availability Zone C')):
    box(ax,220,520,790,'#147EBA',dash='6 4',label=name,sw=1.4)
    box(ax+10,250,500,110,'#7AA116','#F2F6E8',label=f'Public subnet {name[-1]} · 10.0.{0 if name[-1]=="A" else 1}.0/24',fs=13)
# ASG boxes (span both AZ)
box(480,385,1190,190,'#ED7100',dash='8 4',label='ASG — WEB  (min 2 · CPU 60% Target Tracking)',sw=1.8,lx=30)
box(480,605,1190,200,'#ED7100',dash='8 4',label='ASG — WAS  (AZ당 2대 · 예약 증설 + Target Tracking)',sw=1.8,lx=30)
badge(1000,392,3); badge(982,612,4)
for ax,z,cidr in ((490,'A',10),(1140,'C',11)):
    box(ax+10,410,500,145,'#147EBA','#E6F2F8',label=f'Private subnet WEB-{z} · 10.0.{cidr}.0/24',fs=13,lpos='tr')
    box(ax+10,630,500,155,'#147EBA','#E6F2F8',label=f'Private subnet WAS-{z} · 10.0.{cidr+10}.0/24',fs=13,lpos='tr')
    box(ax+10,865,500,135,'#147EBA','#E6F2F8',label=f'Private subnet DB-{z} · 10.0.{cidr+20}.0/24',fs=13,lpos='tr')

# ---------- icons ----------
icon('users',110,240,64,'사용자 (보호자)')
icon('jmeter',110,560,60,'부하 발생기','JMeter EC2')
icon('route53',340,240,64,'Route 53','도메인 → CloudFront',badge=1)
icon('cloudfront',340,400,64,'CloudFront','정적 캐시 · HTTPS(ACM)',badge=2)
icon('waf',340,560,64,'AWS WAF','rate-based · 경로별 제한')
icon('igw',1075,150,64,backdrop=True)
add(f'<text x="1118" y="145" font-size="13.5" font-weight="700" fill="{NAVY}">Internet Gateway</text>')
icon('alb',1075,300,64,'Public ALB','internet-facing · 80/443',backdrop=True)
icon('nat',560,305,48,'NAT Gateway'); icon('nat',1210,305,48,'NAT Gateway')
for cx,t,s in ((600,'WEB-A1','Apache 2.4 · MPM 튜닝'),(800,'WEB-A2','Apache 2.4'),(1250,'WEB-C1','Apache 2.4 · MPM 튜닝'),(1450,'WEB-C2','Apache 2.4')):
    icon('ec2',cx,455,56,t,s)
icon('alb',1075,590,56,'Internal ALB','WEB → WAS · 8080',backdrop=True)
for cx,t,s in ((600,'WAS-A1','Tomcat 9 · maxThreads 튜닝'),(800,'WAS-A2','Tomcat 9'),(1250,'WAS-C1','Tomcat 9 · maxThreads 튜닝'),(1450,'WAS-C2','Tomcat 9')):
    icon('ec2',cx,700,56,t,s)
icon('proxy',1075,845,56,'RDS Proxy','커넥션 다중화 · failover 단축',badge=5,backdrop=True)
icon('rds',700,925,64,'RDS MySQL 8.0 Primary','Multi-AZ · 파라미터 그룹',badge=6)
icon('rds',1350,925,64,'RDS Standby','동기 복제 · 자동 failover')
icon('ssm',1790,300,60,'Systems Manager','Session Manager')
icon('cw',1790,545,60,'CloudWatch','대시보드 · 알람',badge=7)
icon('sns',1790,690,60,'SNS','알람 → 팀 채널')
icon('secrets',1790,845,60,'Secrets Manager','DB 자격증명')

# ---------- edges ----------
path([(142,240),(306,240)]); label(224,232,'HTTPS')
path([(340,306),(340,366)])
path([(340,466),(340,526)]); label(352,500,'Web ACL',anchor='start')
path([(372,400),(445,400),(445,112),(1075,112),(1075,116)])           # CloudFront -> IGW
label(760,104,'캐시 미스(동적)만 오리진으로')
path([(140,560),(250,560),(250,400),(306,400)],dash='6 4'); label(195,552,'폭주 재현')
path([(1075,182),(1075,266)])                                            # IGW -> Public ALB
path([(1075,372),(1075,380),(600,380),(600,425)])                        # ALB -> WEB-A1
path([(1075,380),(1250,380),(1250,425)])
path([(600,520),(600,590),(1045,590)]); label(830,583,'/petclinic/ ProxyPass')   # WEB -> Internal ALB
path([(1250,520),(1250,590),(1105,590)])
path([(1075,653),(1075,658),(600,658),(600,670)])                        # Internal ALB -> WAS
path([(1075,658),(1250,658),(1250,670)])
path([(600,768),(600,795),(1075,795),(1075,815)]); label(830,788,'JDBC (풀 validationQuery)')  # WAS -> Proxy
path([(1250,768),(1250,795),(1075,795)],arrow=False)
path([(1045,845),(700,845),(700,891)])                                   # Proxy -> Primary
path([(732,942),(1316,942)],both=True); label(1025,966,'동기 복제 (Multi-AZ)')
path([(1758,845),(1107,845)],dash='6 4'); label(1440,837,'자격증명')     # Secrets -> Proxy
path([(1790,612),(1790,656)]); label(1806,640,'알람 통보',anchor='start')  # CW -> SNS
path([(1758,545),(1712,545),(1712,700),(1672,700)],dash='6 4')           # CW -> ASG WAS
label(1697,625,'Target Tracking · 예약 증설',rot=-90,size=11.5)
add('</svg>')

svg = '\n'.join(out)
open('arch.svg','w',encoding='utf-8').write(svg)
open('arch.html','w',encoding='utf-8').write('<!doctype html><meta charset="utf-8"><style>html,body{margin:0;background:#fff}svg{width:3840px;height:2160px;display:block}</style>'+svg)
print('ok', len(svg))
