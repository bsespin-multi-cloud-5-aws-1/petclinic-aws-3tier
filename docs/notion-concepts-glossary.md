# 개념 정리 — 멘토링 질문(⑬)을 이해하기 위한 용어 풀이, 같은 계층 순서로

> ⑬ 질문지의 묶음·번호와 1:1로 맞춤. 흐름 복습: 브라우저 → Route 53 → **CloudFront**(+WAF) → Public ALB → **Apache(WEB)** → Internal ALB → **Tomcat(WAS)** → RDS Proxy → RDS (도면은 ⑪).

---

## 1. 네트워크 · 진입

### 1-1. CloudFront · WAF 범위 · VPC origins (질문 ①②)
- **CloudFront(CDN)** = 전 세계 엣지 서버가 우리 서버 앞에서 요청을 먼저 받는 서비스. 캐시(같은 파일을 대신 응답)뿐 아니라 **경계** 역할: 공격을 엣지에서 끊고(Shield·WAF), 진짜 서버 주소를 숨기고, 뒤가 다 죽어도 점검 페이지를 보여줌.
- **WAF 범위**: CLOUDFRONT(전 세계 엣지에서 차단) vs REGIONAL(서울 ALB 바로 앞에서 차단). CloudFront를 빼면 WAF를 ALB에 직접 붙인다(REGIONAL).
- **오리진 은닉**: 우리 ALB는 CloudFront IP 대역(프리픽스 리스트)에서 온 요청 + 비밀 헤더(`X-Origin-Verify`)가 맞을 때만 응답. ALB 주소를 알아도 직접 접속은 타임아웃(9/16 확인).
- **VPC origins** = CloudFront가 인터넷에 안 열린(프라이빗) ALB에 직접 붙는 신기능. ALB를 완전히 숨김. 질문 ②는 "여기까지 가야 하나".

### 1-2. Behavior · 캐시 키 · 캐시 버스팅 · 정적 흡수 (질문 ③④)
**Behavior(비헤이비어)** — CloudFront에서 "이 경로 패턴은 이렇게 처리해라"는 규칙. 우리는 4개:
| Behavior(경로 패턴) | 처리 | 왜 |
|---|---|---|
| `/static/*` · `/images/*` · `/petclinic/resources/*` | **캐시함**(1일) | css·js·이미지·영상은 누가 요청해도 같다 → 엣지에 한 번 받아두고 다시 줌 |
| `/maintenance.html` | S3에서 가져옴 | 점검 페이지 |
| `*` (나머지: `/petclinic/vets`, `/owners/find`…) | **캐시 안 함**, 매번 ALB로 | 사용자·시점마다 내용이 달라지는 JSP 응답(동적) |
- "**정적 Behavior**" = 캐시하는 규칙(첫 줄). "**동적**" = 마지막 줄.
- "**CloudFront가 정적을 흡수한다**" = css·이미지·영상 요청은 엣지가 캐시에서 응답하므로 **ALB·Apache·Tomcat은 그 요청을 아예 보지 않는다**. 9/16 확인: `hero.mp4` 첫 요청 `Miss` → 두 번째 `Hit`.
- **캐시 키** — "같은 파일이다/다르다"를 판단하는 기준. 우리는 **URL 경로만** 본다(쿼리·쿠키 무시) → `/static/a.css`와 `/static/a.css?v=2`는 **같은 것**.
- **캐시 버스팅** — 파일을 바꿨는데 옛 파일이 계속 보이는 문제를 깨는 기법. 보통 `a.css?v=2`처럼 URL을 바꾼다. 우리는 쿼리를 무시해 이게 **안 통하고**, 대신 ① **무효화**(`create-invalidation`: 엣지 캐시 지우기) 또는 ② **경로 버전**(`/static/v2/a.css`). 9/16 Green 전환 뒤 CSS가 옛것으로 보인 게 이 문제(무효화로 해결). 질문 ③.
- **읽기 API 짧은 캐시** — `/petclinic/vets.json` 같은 조회 응답을 5~10초만 캐시하면 폭주 때 DB 부하가 크게 준다. 대신 그 몇 초 동안 새 데이터가 안 보일 수 있다(정합성). 질문 ④.

### 1-3. rate-based rule (질문 ⑤⑥)
- **rate-based rule** = WAF 규칙 중 "**같은 IP가 5분 안에 N번 넘게 요청하면 차단**". 관리형 규칙(IpReputation·Common·KnownBadInputs)은 요청의 "모양"을, rate는 "양"을 본다.
- 우리 규칙: `rate-all` = 모든 경로 IP당 5분 **2,000** 초과 → 403. `rate-booking` = `/visits/new`(예약 폼)만 IP당 5분 **100** 초과 → 403.
- 숫자 근거는 보통 평시 최대 RPS·부하 테스트 결과로 잡는데 우리는 감으로 정함(질문 ⑤). **오탐** = 회사·학교처럼 한 공인 IP를 여럿이 쓰면 정상 사용자가 합산돼 차단될 수 있음(질문 ⑥). 부하 테스트 발생기는 `loadgen_cidrs`로 예외.

### 1-4. NAT Gateway · Bastion · SSM (질문 ⑦⑧)
- **NAT Gateway** = 프라이빗 서브넷 서버가 인터넷으로 **나가는** 문(패치 `dnf`, Secrets Manager·SSM API). 들어오는 건 못 들어옴. AZ당 1개면 한 AZ 장애 때도 다른 AZ 서버가 나갈 수 있지만 개당 ≈ $43/월 고정비.
- **Bastion(점프 서버)** = 22번 포트를 연 공인 IP 서버에 먼저 SSH로 들어간 뒤 내부 서버로 건너감. 키 파일 배포·패치·공인 IP 노출이 따라옴.
- **SSM Session Manager** = 포트·키 없이 IAM 권한으로 브라우저/CLI에서 서버 셸을 열고, 세션 내용이 CloudWatch Logs에 기록됨. 서버에 SSM Agent + IAM 역할(인스턴스 프로파일)만 있으면 됨. 질문 ⑧은 "팀원을 설득할 근거".

---

## 2. WEB 티어

### 2-1. 랜딩 · 리버스 프록시 · mod_proxy vs mod_jk (질문 ⑨⑩)
- **랜딩(landing) 페이지** = 첫 화면 `index.html`(병원 소개 + 영상). 지금은 **WEB EC2의 Apache가 파일로** 직접 서빙(`/static/`에 css·영상 9.6MB 복사).
- "**랜딩을 옮긴다**" = index.html과 자산을 EC2가 아니라 **S3 버킷에 올리고 CloudFront가 S3에서 읽게** 하는 것. 정적 파일에 서버가 필요 없어짐(비용↓·패치↓). 대신 WEB 계층이 할 일이 줄어 "왜 WEB이 있나"가 더 도드라짐(질문 ⑨⑩).
- **리버스 프록시(mod_proxy)** = Apache가 `/petclinic/…` 요청을 받아 뒤의 Internal ALB(→Tomcat)로 대신 전달하고 응답을 돌려줌. 사용자는 Tomcat 주소를 모른다. 헤더(Host·X-Forwarded-For)를 유지·추가하는 지점.
- **mod_jk** = 같은 일을 AJP라는 별도 프로토콜로 하는 모듈. ALB가 AJP를 이해 못 해 우리 구조(중간에 Internal ALB)에선 못 씀 → mod_proxy_http 선택.

### 2-2. user_data · Golden AMI · Image Builder (질문 ⑪)
- **user_data(init script)** = EC2가 처음 켜질 때 실행되는 스크립트. 지금은 여기서 Apache/Tomcat 설치·앱 빌드·CloudWatch Agent 설치까지 다 한다(WEB 1분·WAS 8분).
- **Golden AMI** = 설치가 끝난 상태를 통째로 이미지로 떠 둔 것. 그걸로 켜면 설치 없이 1~2분 만에 뜬다. 패치가 나오면 다시 구워야 함.
- **EC2 Image Builder** = AMI를 자동으로 굽는 AWS 서비스(레시피 → 주기적 빌드·테스트). 수동 `create-image`는 사람이 인스턴스 하나 세팅하고 버튼 누르는 것. 질문 ⑪은 "3주에 자동화까지 갈 가치".
- **CloudWatch Agent** = 서버 안 로그 파일(access_log·catalina.out)과 메모리·디스크 지표를 CloudWatch로 보내는 프로그램. 설정은 SSM 파라미터(`/mc/cwagent/web|was`)에서 받음.

---

## 3. WAS 티어

### 3-1. ASG · Target Tracking · 워밍업 · 예약 증설 (질문 ⑫⑬)
- **Auto Scaling Group(ASG)** = 서버 수를 자동으로 늘리고 줄이는 묶음. **Target Tracking** = "이 지표를 이 값 근처로 유지해라"(온도 조절기). 예: CPU 평균 60% → 넘으면 추가, 남으면 축소.
- **지표 후보** ① CPU(`ASGAverageCPUUtilization`) — 단순하지만 Java 앱은 CPU가 늦게 오른다. ② **한 대당 요청 수**(`ALBRequestCountPerTarget`) — 트래픽에 바로 반응. 우리 설계값 **300/대** = "한 대가 1분에 300요청 넘으면 늘려라"인데 근거 없이 정한 숫자. 보통은 부하 테스트로 "한 대가 p95 2초 안에 버티는 최대 RPS"를 재서 그 70~80%로 둔다(질문 ⑫).
- **워밍업** = 새 서버가 켜져서 실제로 요청을 받기까지 걸리는 시간. 우리는 부팅 때 빌드까지 하므로 **8분** → "폭주 감지 → 증설 → 8분 뒤 투입"이면 늦다. Golden AMI면 1~2분.
- **예약 증설(Scheduled scaling)** = "매일 09:45에 4대로"처럼 시간표로 미리 늘리는 것(영상 공개 15분 전). 질문 ⑬은 "워밍업이 길면 예약 증설이 답인가, AMI가 먼저인가".
- **종료 훅** = 서버를 줄일 때 바로 끄지 않고 300초 기다려 마지막 로그를 S3에 올린 뒤 종료.

### 3-2. WAR에 DB 정보가 박힘 · JNDI (질문 ⑭)
- PetClinic은 Maven이 빌드할 때 `datasource-config.xml`의 `${jdbc.url}` 자리에 실제 값을 **글자로 써넣는다**(Maven 필터링). 그래서 `petclinic.war` 안에 `jdbc:mysql://mc-rds-proxy…`와 비밀번호가 문자 그대로 들어 있다.
- 결과: WAR는 **그 환경 전용**(다른 계정·DB면 다시 빌드) → AMI에 WAR를 넣으면 AMI도 환경 전용 + 비밀번호 포함.
- 환경 독립적으로 만드는 방법 세 가지:
  1. **JNDI**: Tomcat 설정 파일(`context.xml`)에 DB 접속 정보를 두고, 앱은 `java:comp/env/jdbc/petclinic`이라는 **이름**만 찾는다. WAR는 어디서나 같고 부팅 때 context.xml만 쓰면 됨. PetClinic에 이미 `javaee` 프로필로 준비돼 있어 **코드 수정 없이** 가능.
  2. **환경변수**: 앱이 시작할 때 `DB_URL` 같은 값을 읽음 — Spring Boot 방식이라 이 앱은 코드 수정 필요.
  3. **Parameter Store/Secrets Manager 부팅 시 조회**: 지금 우리 방식(조회 → 빌드). 조회한 값을 WAR에 굽는 대신 설정 파일에 쓰는 게 이상적.
- 질문 ⑭는 "옛날식 Spring XML 앱에서 실무자는 보통 JNDI로 가나".

### 3-3. 세션 · Redis · SQS (질문 ⑮⑯)
- **세션** = 로그인 상태 같은 "이 사용자와의 대화 기억". WAS가 2대면 1번에 기억이 있고 2번엔 없다 → 공유 저장소(**Redis/ElastiCache**)에 두거나, ALB가 같은 사용자를 같은 서버로 보냄(**스티키 세션**). PetClinic은 로그인이 없어 기억할 게 없다.
- **SQS(큐)** = 요청을 줄 세워 두고 뒤에서 천천히 처리하는 통. 예약 폭주 때 "일단 접수(큐)"하고 DB에는 순서대로 쓰면 DB가 안 죽는다. 단 앱이 큐에 넣고(producer) 꺼내는(consumer) 코드가 필요 → "소스 0줄" 원칙과 충돌.
- **RDS Proxy 풀링** = 서버가 8대로 늘어도 Proxy가 DB 연결을 재사용해 DB 연결 상한(db.t3.small ≈ 85)을 넘지 않게 하는 것. 질문 ⑯은 "SQS vs Proxy+증설".

### 3-4. 롤링 · Blue/Green · 가중치 전환 (질문 ⑰)
- **롤링(Rolling)** = 서버를 한 묶음씩 새 버전으로 교체. 우리는 AZ-a 교체 → healthy 확인 → AZ-c 교체(9/16 실제로 3번 수행). 한 번에 한 버전만 존재, 되돌리려면 다시 교체.
- **Blue/Green** = 현재 버전(Blue) 서버 묶음을 그대로 두고 새 버전(Green) 묶음을 따로 띄운 뒤 트래픽을 옮기는 방식. **가중치 전환** = ALB 리스너에서 Blue:Green 비율을 90:10 → 50:50 → 0:100으로 바꿈, 문제 나면 100:0으로 즉시 롤백. 서버 2배·대상 그룹 2개 필요.

---

## 4. DB 티어

### 4-1. 비밀 교체 · 앱 전용 계정 · VPC 엔드포인트 (질문 ⑱⑲)
- **비밀 교체(rotation)** = 비밀번호를 주기적으로 새로 바꾸는 것. RDS가 만든 admin 비밀(`rds!db-…`)은 **7일마다 자동 교체**되고 끌 수 없다.
- 문제: WAS는 빌드할 때의 비밀번호를 WAR에 굽는다 → 7일 뒤 admin 비밀번호가 바뀌면 새 연결 실패(9/22쯤). 해법으로 **앱 전용 사용자(`petclinic_app`)**를 만들고 그 비밀은 **교체하지 않기로**(코드 `441e4a7`, 미적용). 최소 권한(admin 미사용)도 함께 충족.
- 교체를 하려면 (a) 교체 때마다 WAS 재빌드·재기동, (b) JNDI로 바꿔 설정 파일만 갱신, (c) **IAM 인증**(비밀번호 대신 15분짜리 토큰, 앱 코드 필요) — 질문 ⑱.
- **VPC 엔드포인트** = Secrets Manager·SSM 같은 AWS 서비스에 **인터넷(NAT)으로 나가지 않고 VPC 안 사설 경로**로 가게 하는 문. AZ당 ≈ $8/월이지만 NAT 전송비가 줄고 트래픽이 VPC를 안 벗어남. 질문 ⑲.
- **TLS 3중** = Proxy `require_tls` + 파라미터 그룹 `require_secure_transport=1` + JDBC `sslMode=REQUIRED` → DB 구간 평문 연결 불가.

### 4-2. Multi-AZ · RPO (질문 ⑳)
- **Multi-AZ** = RDS 대기 복제본을 다른 AZ에 항상 켜 두고 동기 복제. 장애 시 1~2분 안에 자동 전환, 엔드포인트 주소는 그대로. **RPO 0** = 잃는 데이터 0(동기 복제라서). 비용 2배(≈ $40 → $80). Multi-AZ는 **백업이 아님**(실수로 지운 행도 복제됨) → 백업·PITR은 별도.

### 4-3. 개인정보 파기 증명 · 진료 파일 S3 (질문 ㉑㉒)
- 우리 개인정보 = RDS의 `owners`(이름·주소·전화)·`pets`·`visits` **행(row)**. 파일이 아니라 DB 안 데이터.
- "**보존·파기를 증명**" = 개인정보 보호법이 "보존 기간이 지나면 파기하라"고 하므로 "기간을 정했고, 지나면 지운다(지웠다)"를 보여줘야 함. DB 행은 S3처럼 자동 만료(lifecycle) 규칙이 없어 **정책 문서 + 주기적 삭제 작업(예약 SQL) + 삭제 로그**로 증명. 질문 ㉑.
- **진료 파일 S3** = 원래 시나리오(9/14 이전)에 X-ray·진료기록 파일을 S3에 저장하고 **Object Lock**(삭제·변조 불가)·**Macie**(개인정보 자동 탐지)까지 넣었다가 범위를 줄이며 뺐다. 질문 ㉒는 "발표용으로 다시 넣나".
- **PITR** = 시점 복구. 자동 백업 7일 + 5분 단위 로그로 "어제 14:03 상태"로 되돌릴 수 있음.

---

## 5. 전 계층 공통

### 5-1. 로그 5종 · Flow Logs · slow query log (질문 ㉓㉔)
- 우리 5종: 앱 로그(Apache·Tomcat → CloudWatch Logs) · ALB 접속 로그(S3) · WAF 로그 · SSM 세션 기록 · **CloudTrail**(누가 AWS에서 뭘 했나).
- 안 켠 것: **VPC Flow Logs**(어떤 IP가 어떤 포트로 통신했나) · **RDS slow query log**(설정 시간, 예 2초 넘게 걸린 SQL 목록) · S3 데이터 이벤트(누가 파일을 열었나).
- 질문 ㉓㉔는 "사고 때 실제로 쓰는 로그"와 "Phase 3 병목 분석에 slow query log가 값어치 있나".

### 5-2. 암묵적 거부 · ABAC · SCP (질문 ㉕㉖)
- IAM은 허용하지 않은 건 전부 거부(**암묵적 거부**). 우리 역할들은 "이 비밀 하나", "이 S3 접두사"처럼 **자원 단위로만 허용**.
- **ABAC(태그 기반)** = "Project=petclinic-3tier 태그가 붙은 자원만 만질 수 있다"처럼 **태그로 권한 범위**를 정하는 방식. 자원이 늘어도 정책을 안 고친다. 단 태그를 안 붙이거나 바꿔치기하면 뚫리므로 **태그 변경 권한**도 막아야 함(질문 ㉖).
- **SCP** = 조직(Organizations) 단위로 계정 전체에 거는 상위 정책. kdt5 팀 계정엔 없음 → IAM 사용자 정책만으로 해야 함(질문 ㉕).

### 5-3. 네이밍 · 이름 변경 불가 자원 (질문 ㉗㉘)
- 우리 규칙: `mc-<계층>-<구분>-<AZ>`(`mc-was-c`, `mc-sg-rds`), 버킷은 계정 ID 접미(전역 유일), 로그 그룹 `/mc/<계층>/<종류>`. 환경(lab/prod)은 태그로.
- "환경·계정을 이름에 넣나" = `mc-alb-public` vs `mc-lab-alb-public`. 이름에 넣으면 한눈에 보이지만 길이 제한(ALB 32자)에 걸림. 태그로 두면 이름은 짧고 필터는 태그로(질문 ㉗).
- "이름 변경 불가 자원" = ALB·대상 그룹은 만든 뒤 이름을 못 바꾼다(RDS 식별자는 바꿀 수 있으나 엔드포인트가 바뀜). kdt5의 `test-Public-ALB`·`Targetgroup-web`을 규칙에 맞추려면 **지웠다 다시 만들어야** 함(질문 ㉘).
