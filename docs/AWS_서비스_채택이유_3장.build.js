const pptxgen = require('pptxgenjs');
const fs = require('fs');
const pres = new pptxgen();
pres.layout = 'LAYOUT_WIDE'; // 13.33 x 7.5
pres.title = 'AWS 서비스 채택 이유';
const F = 'Arial';
const NAVY='1F2D4E', NAVY2='3A4E7A', STEEL='8A9BBF', TINT='EEF1F7', TXT='333333', MUTE='6B6B6B';
const img = n => 'image/png;base64,' + fs.readFileSync('icons/' + n + '.png').toString('base64');

function header(s, title, page, sub) {
  s.background = { color: 'FFFFFF' };
  s.addText('1팀  /  MISSION CRITICAL', { x: 0.6, y: 0.3, w: 8, h: 0.3, fontFace: F, fontSize: 12, bold: true, color: '000000', margin: 0, isTextBox: true });
  s.addText(title, { x: 0.6, y: 0.62, w: 12, h: 0.75, fontFace: F, fontSize: 34, bold: true, color: NAVY, margin: 0, isTextBox: true });
  if (sub) s.addText(sub, { x: 0.6, y: 1.38, w: 12, h: 0.35, fontFace: F, fontSize: 13, color: TXT, margin: 0, isTextBox: true });
  s.addText(page, { x: 12.2, y: 6.9, w: 0.6, h: 0.3, fontFace: F, fontSize: 11, color: MUTE, align: 'right', margin: 0, isTextBox: true });
}
function pill(s, x, y, w, h, text, fs = 12) {
  s.addShape(pres.ShapeType.roundRect, { x, y, w, h, fill: { color: NAVY }, line: { color: NAVY }, rectRadius: h / 2 });
  s.addText(text, { x, y, w, h, fontFace: F, fontSize: fs, bold: true, color: 'FFFFFF', align: 'center', valign: 'middle', margin: 0, isTextBox: true });
}

/* ================= Slide 1: 전체 그림 ================= */
{
  const s = pres.addSlide();
  header(s, 'AWS 서비스, 왜 쓰나 — 전체 그림', '01', '폭주 시나리오: 유튜브 노출로 요청이 평시의 10배 (초당 50 → 500~1,000)');

  // 요청 흐름: 아이콘 체인
  const chain = [
    { n: 'users', t: '사용자' }, { n: 'route-53', t: 'Route 53' }, { n: 'cloudfront', t: 'CloudFront\n+ WAF' },
    { n: 'elb-application-load-balancer', t: 'Public ALB' }, { n: 'ec2', t: 'WEB\nApache' },
    { n: 'elb-application-load-balancer', t: 'Internal ALB' }, { n: 'ec2', t: 'WAS\nTomcat' },
    { n: 'rds-instance', t: 'RDS Proxy' }, { n: 'rds', t: 'RDS MySQL' },
  ];
  const n = chain.length, ICON = 0.78, x0 = 0.6, span = 12.1;
  const step = (span - ICON) / (n - 1);
  const iy = 2.15;
  chain.forEach((c, i) => {
    const x = x0 + i * step;
    s.addImage({ data: img(c.n), x, y: iy, w: ICON, h: ICON });
    s.addText(c.t, { x: x - 0.35, y: iy + ICON + 0.06, w: ICON + 0.7, h: 0.5, fontFace: F, fontSize: 10.5, bold: true, color: NAVY, align: 'center', valign: 'top', margin: 0, isTextBox: true });
    if (i < n - 1) s.addShape(pres.ShapeType.rightArrow, { x: x + ICON + 0.08, y: iy + ICON / 2 - 0.09, w: step - ICON - 0.16, h: 0.18, fill: { color: STEEL }, line: { color: STEEL } });
  });

  // 구간 브래킷 (3 zones)
  const zones = [
    { from: 1, to: 3, t: '진입 · 앞에서 거른다' },
    { from: 3, to: 6, t: 'WEB · WAS · 부족하면 늘린다' },
    { from: 7, to: 8, t: 'DB · 하나뿐이니 지킨다' },
  ];
  zones.forEach(z => {
    const xa = x0 + z.from * step, xb = x0 + z.to * step + ICON;
    s.addShape(pres.ShapeType.roundRect, { x: xa - 0.1, y: 3.55, w: xb - xa + 0.2, h: 0.36, fill: { color: TINT }, line: { color: TINT }, rectRadius: 0.08 });
    s.addText(z.t, { x: xa - 0.1, y: 3.55, w: xb - xa + 0.2, h: 0.36, fontFace: F, fontSize: 11.5, bold: true, color: NAVY, align: 'center', valign: 'middle', margin: 0, isTextBox: true });
  });

  // 대응 원칙 3 카드
  const cards = [
    { n: '1', t: '앞에서 거른다', d: '이미지 같은 정적 파일과 이상 트래픽은\n서버까지 오지 못하게 한다.', svc: 'CloudFront · WAF' },
    { n: '2', t: '부족하면 늘린다', d: 'WEB·WAS 서버는 복제할 수 있으니\n자동으로 증설한다.', svc: 'ALB · Auto Scaling' },
    { n: '3', t: 'DB는 지킨다', d: 'DB는 마음대로 못 늘리니\n연결 수를 조절하고 예비 DB를 둔다.', svc: 'RDS Proxy · Multi-AZ' },
  ];
  const CW = 3.85, GAP = 0.275;
  cards.forEach((c, i) => {
    const x = 0.6 + i * (CW + GAP), y = 4.3;
    s.addShape(pres.ShapeType.roundRect, { x, y, w: CW, h: 2.3, fill: { color: TINT }, line: { color: TINT }, rectRadius: 0.1 });
    s.addShape(pres.ShapeType.ellipse, { x: x + 0.25, y: y + 0.25, w: 0.55, h: 0.55, fill: { color: NAVY }, line: { color: NAVY } });
    s.addText(c.n, { x: x + 0.25, y: y + 0.25, w: 0.55, h: 0.55, fontFace: F, fontSize: 16, bold: true, color: 'FFFFFF', align: 'center', valign: 'middle', margin: 0, isTextBox: true });
    s.addText(c.t, { x: x + 0.95, y: y + 0.25, w: CW - 1.15, h: 0.55, fontFace: F, fontSize: 17, bold: true, color: NAVY, valign: 'middle', margin: 0, isTextBox: true });
    s.addText(c.d, { x: x + 0.25, y: y + 0.95, w: CW - 0.5, h: 0.8, fontFace: F, fontSize: 12, color: TXT, valign: 'top', margin: 0, isTextBox: true });
    s.addText(c.svc, { x: x + 0.25, y: y + 1.8, w: CW - 0.5, h: 0.3, fontFace: F, fontSize: 11, bold: true, color: NAVY2, margin: 0, isTextBox: true });
  });
  s.addNotes('요청이 지나가는 길: 사용자 → Route 53 → CloudFront + WAF → Public ALB → WEB(Apache) → Internal ALB → WAS(Tomcat) → RDS Proxy → RDS(MySQL). 대응 원칙: 1) 앞에서 거른다 2) 부족하면 늘린다 3) DB는 지킨다. 발표 한 문장: 앞에서 거르고(CloudFront·WAF), 중간은 자동으로 늘리고(ASG), DB는 지킵니다(Proxy·Multi-AZ). 그리고 전부 CloudWatch로 재서 전/후를 비교합니다.');
}

/* ================= Slide 2: 서비스별 한 줄 이유 ================= */
{
  const s = pres.addSlide();
  header(s, '서비스별 한 줄 이유', '02', '한 서비스 = 한 줄.  문제 → 해결만 기억하면 됩니다.');

  const groups = [
    { t: '진입 · 앞에서 거른다', rows: [
      ['route-53', 'Route 53', '도메인 없으면 HTTPS·CloudFront 못 붙임', '도메인을 사서 CloudFront에 연결'],
      ['cloudfront', 'CloudFront', '정적 파일 요청이 서버 대역폭을 잡아먹음', '정적 파일은 캐시로 대신 응답, 서버엔 동적 요청만'],
      ['waf', 'WAF', '특정 IP·봇이 예약 API를 무한 호출', 'IP당 요청 횟수 제한, 이상 요청은 서버 전에 차단'],
    ]},
    { t: 'WEB · WAS · 부족하면 늘린다', rows: [
      ['elb-application-load-balancer', 'ALB', '서버 1대에 몰리면 죽고, 죽은 서버로 요청이 감', '여러 서버에 분산 + 헬스체크로 죽은 서버 자동 제외'],
      ['ec2', 'Apache·Tomcat 튜닝', '기본 설정은 동시 접속 수가 낮음', '서버 늘리기 전에 1대당 처리량부터 올림'],
      ['auto-scaling', 'Auto Scaling', '폭주 때 사람이 서버를 손으로 못 늘림', 'CPU 60% 넘으면 자동 증설, 공개 시각에 맞춰 미리 예약'],
      ['systems-manager', 'SSM Session Manager', 'Bastion 서버 + 22번 포트 + SSH 키 관리 필요', 'Bastion 없이 콘솔에서 접속, 포트 안 열고 기록 자동 저장'],
    ]},
    { t: 'DB · 하나뿐이니 지킨다', rows: [
      ['rds-instance', 'RDS Proxy', 'WAS가 8대로 늘면 DB 연결 한도 초과 → 거부', 'WAS와 DB 사이에서 연결을 모아 관리, 한도 안 넘게'],
      ['rds', 'RDS Multi-AZ', 'DB 1대가 죽으면 서비스 전체 중단', '다른 AZ에 예비 DB를 두고 장애 시 자동 전환'],
    ]},
    { t: '운영 · 보고 알린다', rows: [
      ['cloudwatch', 'CloudWatch', '어디가 느린지 모르면 뭘 고칠지 모름', '계층별 지표를 한 화면에, 전/후 비교'],
      ['simple-notification-service-sns', 'SNS', '알람이 콘솔에만 뜨면 아무도 못 봄', '알람을 팀 채널(이메일·Slack)로 전송'],
      ['secrets-manager', 'Secrets Manager', 'DB 비밀번호가 코드·설정 파일에 남음', '비밀번호를 한 곳에 암호화 저장, 권한으로만 사용'],
    ]},
  ];
  // 2x2 grid
  const GW = 6.0, GH = 2.4, GX = [0.6, 6.73], GY = [1.85, 4.4];
  const ROW = 0.42;
  groups.forEach((g, gi) => {
    const x = GX[gi % 2], y = GY[Math.floor(gi / 2)];
    s.addShape(pres.ShapeType.roundRect, { x, y, w: GW, h: GH, fill: { color: TINT }, line: { color: TINT }, rectRadius: 0.1 });
    s.addText(g.t, { x: x + 0.2, y: y + 0.1, w: GW - 0.4, h: 0.3, fontFace: F, fontSize: 12.5, bold: true, color: NAVY, margin: 0, isTextBox: true });
    // column heads
    s.addText('문제', { x: x + 1.85, y: y + 0.42, w: 2.0, h: 0.2, fontFace: F, fontSize: 9, bold: true, color: NAVY2, margin: 0, isTextBox: true });
    s.addText('해결', { x: x + 3.95, y: y + 0.42, w: 2.0, h: 0.2, fontFace: F, fontSize: 9, bold: true, color: NAVY2, margin: 0, isTextBox: true });
    const startY = y + 0.65;
    const rows = g.rows, rh = Math.min(ROW, (GH - 0.8) / rows.length);
    rows.forEach((r, ri) => {
      const ry = startY + ri * rh;
      s.addImage({ data: img(r[0]), x: x + 0.2, y: ry + (rh - 0.34) / 2, w: 0.34, h: 0.34 });
      s.addText(r[1], { x: x + 0.62, y: ry, w: 1.2, h: rh, fontFace: F, fontSize: 9.5, bold: true, color: NAVY, valign: 'middle', margin: 0, isTextBox: true });
      s.addText(r[2], { x: x + 1.85, y: ry, w: 2.0, h: rh, fontFace: F, fontSize: 9, color: MUTE, valign: 'middle', margin: 0, isTextBox: true });
      s.addText(r[3], { x: x + 3.95, y: ry, w: 1.9, h: rh, fontFace: F, fontSize: 9, color: TXT, valign: 'middle', margin: 0, isTextBox: true });
    });
  });
  s.addNotes('각 서비스는 문제 → 해결 한 줄로만 설명. 설정 수치나 지표 이름은 상세판(docs/03-service-rationale.md) 참고.');
}

/* ================= Slide 3: 헷갈리기 쉬운 것 3가지 ================= */
{
  const s = pres.addSlide();
  header(s, '헷갈리기 쉬운 것 3가지', '03');

  const qa = [
    { q: 'SSM 쓰면 NAT 게이트웨이 없어도 되나?', a: '아니요. 방향이 다릅니다.',
      pts: ['NAT = 서버가 밖으로 나가는 길 (패키지 설치, CloudWatch 전송)', 'SSM = 사람이 서버로 들어가는 길 (Bastion 대신)', '둘 다 필요합니다.'],
      icons: ['systems-manager'] },
    { q: 'NAT가 있는데 SSM은 왜?', a: 'NAT는 들어오는 요청을 못 받습니다.',
      pts: ['접속 수단은 Bastion 아니면 SSM 중 하나가 필요', 'SSM은 서버 1대 · 22번 포트 · SSH 키를 모두 없애 줌', '접속 기록이 자동으로 남음'],
      icons: ['systems-manager'] },
    { q: 'DB도 Auto Scaling 하면 안 되나?', a: 'DB는 데이터가 한 곳에 있어야 해서 복제해 늘릴 수 없습니다.',
      pts: ['그래서 "늘리기" 대신 "지키기" 전략', 'RDS Proxy로 연결 수 조절, Multi-AZ로 예비 DB', '읽기 전용 복제본(Read Replica)은 앱 코드 수정 필요 → 이번 범위 밖'],
      icons: ['rds'] },
  ];
  const CW = 3.85, GAP = 0.275;
  qa.forEach((c, i) => {
    const x = 0.6 + i * (CW + GAP), y = 1.75, H = 4.35;
    s.addShape(pres.ShapeType.roundRect, { x, y, w: CW, h: H, fill: { color: TINT }, line: { color: TINT }, rectRadius: 0.1 });
    s.addShape(pres.ShapeType.ellipse, { x: x + 0.25, y: y + 0.25, w: 0.55, h: 0.55, fill: { color: NAVY }, line: { color: NAVY } });
    s.addText('Q' + (i + 1), { x: x + 0.25, y: y + 0.25, w: 0.55, h: 0.55, fontFace: F, fontSize: 13, bold: true, color: 'FFFFFF', align: 'center', valign: 'middle', margin: 0, isTextBox: true });
    s.addText(c.q, { x: x + 0.95, y: y + 0.2, w: CW - 1.15, h: 0.65, fontFace: F, fontSize: 14, bold: true, color: NAVY, valign: 'middle', margin: 0, isTextBox: true });
    s.addText(c.a, { x: x + 0.25, y: y + 1.05, w: CW - 0.5, h: 0.6, fontFace: F, fontSize: 12.5, bold: true, color: NAVY2, valign: 'top', margin: 0, isTextBox: true });
    s.addText(c.pts.map((p, j) => ({ text: p, options: { bullet: { indent: 12 }, breakLine: j < c.pts.length - 1 } })),
      { x: x + 0.25, y: y + 1.7, w: CW - 0.5, h: 1.7, fontFace: F, fontSize: 11.5, color: TXT, valign: 'top', paraSpaceAfter: 6, margin: 0, isTextBox: true });
    s.addImage({ data: img(c.icons[0]), x: x + CW - 0.95, y: y + H - 0.95, w: 0.7, h: 0.7 });
  });

  // 발표 한 문장
  s.addShape(pres.ShapeType.roundRect, { x: 0.6, y: 6.3, w: 12.1, h: 0.55, fill: { color: NAVY }, line: { color: NAVY }, rectRadius: 0.1 });
  s.addText([
    { text: '발표 한 문장  ', options: { bold: true, color: STEEL } },
    { text: '앞에서 거르고(CloudFront·WAF), 중간은 자동으로 늘리고(ASG), DB는 지킵니다(Proxy·Multi-AZ). 전부 CloudWatch로 재서 전/후를 비교합니다.', options: { color: 'FFFFFF' } },
  ], { x: 0.8, y: 6.3, w: 11.7, h: 0.55, fontFace: F, fontSize: 12, valign: 'middle', margin: 0, isTextBox: true });
  s.addNotes('Q1 SSM과 NAT는 방향이 다르다(들어오는 길 vs 나가는 길). Q2 NAT는 인바운드를 못 받으므로 접속 수단은 별도 필요, SSM이 Bastion보다 관리 부담이 적다. Q3 DB는 상태가 있어 복제 증설이 어렵다. Read Replica는 앱 수정 필요로 로드맵.');
}

pres.writeFile({ fileName: 'AWS_서비스_채택이유_3장.pptx' }).then(f => console.log('wrote', f));
