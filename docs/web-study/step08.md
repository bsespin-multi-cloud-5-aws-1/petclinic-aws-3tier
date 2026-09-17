<callout icon="🔎" color="blue_bg">
	**이 단계의 목표**: 요청 하나가 남기는 로그 다섯 곳(CloudFront · WAF · ALB · Apache · Tomcat)을 한 줄씩 읽고, CloudWatch 지표 네 개로 "ALB 잘못인지 서버 잘못인지" 를 가르고, 알람이 어디로 가는지 안다. 하루 분량. 값은 전부 2026-09-17 14:19:57 KST 의 실제 요청 하나(`HEAD /petclinic/vets`)로.
</callout>
# 0. 그림 한 장

```text
브라우저 ─▶ CloudFront ─▶ WAF ─▶ ALB ─▶ Apache ─▶ Internal ALB ─▶ Tomcat
             │ ① CloudFront 로그   │ ① WAF 로그      │ ① ALB 로그(34필드)  │ ② Apache access_log        │ ② Tomcat access log
             │ S3 cloudfront/      │ us-east-1 LogGroup │ S3 alb/public/      │ CloudWatch /mc/web/access  │ CloudWatch /mc/was/access
             └────────────────────────── ③ 지표: ELB_5XX · Target_5XX · TargetResponseTime · Healthy/UnHealthyHostCount ──▶ ④ 알람 3개 → SNS mc-alerts(구독 0!) ──▶ ⑤ 보관: S3 1년(cwlogs/) · 로그 그룹 30일
```

원칙 하나: **로그는 "누가 냈나", 지표는 "얼마나", 알람은 "언제 알릴까"**. 셋을 섞으면 진단이 꼬인다.
# 1. 딱 필요한 다섯 가지 — 한 표
<table header-row="true" fit-page-width="true">
	<tr>
		<td>#</td>
		<td>항목</td>
		<td>무슨 일이 일어나나</td>
		<td>우리 값 (실측)</td>
	</tr>
	<tr>
		<td>①</td>
		<td>ALB 액세스 로그 한 줄</td>
		<td>요청마다 34개 필드. client(CloudFront IP) · target · 처리 시간 3개 · **elb 코드 / target 코드** · TLS · 매치 규칙 · 노드 IP</td>
		<td>`3.172.65.112:48058 10.0.10.189:80 0.000 0.055 0.000 200 200 … matched_rule 10 … ip_address 3.34.116.99` · S3 `alb/public/` 5분마다 gzip</td>
	</tr>
	<tr>
		<td>②</td>
		<td>Apache · Tomcat 로그 — 진짜 IP 는 어디에</td>
		<td>첫 필드는 **연결 상대**(ALB 노드 · Internal ALB 노드). 사용자 IP 는 `X-Forwarded-For` 에만. 서버 접속 없이 CloudWatch Logs 로 본다</td>
		<td>Apache `10.0.1.212 … "HEAD /petclinic/vets HTTP/1.1" 200` · Tomcat `10.0.21.43 … 200` · 발견: 헬스체크 1,442줄/h · 일반 요청 2중 기록</td>
	</tr>
	<tr>
		<td>③</td>
		<td>지표 4개 — ALB 잘못인가 서버 잘못인가</td>
		<td>`HTTPCode_ELB_5XX`(ALB 가 만든) vs `HTTPCode_Target_5XX`(서버가 준) · `TargetResponseTime`(p95) · `HealthyHostCount/UnHealthyHostCount`</td>
		<td>24h: ELB_5XX 0 · Target_5XX 0 · RequestCount 206 · p95 0.35s · Healthy 2 / UnHealthy 0</td>
	</tr>
	<tr>
		<td>④</td>
		<td>알람 3개 → SNS</td>
		<td>지표가 임계를 N분 넘으면 SNS 토픽으로. **토픽에 구독자가 없으면 아무도 못 받는다**</td>
		<td>`mc-alb-p95-latency`(›2s·3분) · `mc-was-unhealthy-host`(≥1·2분) · `mc-rds-connections-high`(›60·3분) → `mc-alerts` **구독 0건**(`alert_emails` 비어 있음 · 로드맵)</td>
	</tr>
	<tr>
		<td>⑤</td>
		<td>로그 지도 — 어디에 얼마나</td>
		<td>실시간(CloudWatch Logs 30일) → 구독 필터 → Firehose → S3 `cwlogs/‹tier›/yyyy/MM/dd/` 1년. ALB · CloudFront 는 S3 직접. WAF 는 us-east-1</td>
		<td>로그 그룹 9개(`/mc/*` 6 · `/aws/rds/*` 3) · Firehose 4개(`mc-cwlogs-web/was/bastion/db`) · S3 프리픽스 `alb/ cloudfront/ cwlogs/ web/ was/ bastion/ db/` · `aws-waf-logs-mc`(us-east-1 · 30일)</td>
	</tr>
</table>
# 2. 자세히 — 항목마다 "무슨 일 · 우리 값 · 없으면 · 눈으로 확인"
## 2-1. ① ALB 액세스 로그 한 줄 — 34개 필드 중 볼 것
**무슨 일이 일어나나**
1. ALB 는 처리한 **모든 요청**(헬스체크 제외 · WAF 차단분은 CloudFront 단이라 없음)을 5분마다 gzip 으로 S3 `alb/public/AWSLogs/…/yyyy/mm/dd/` 에 쓴다(0 바이트 `ELBAccessLogTestFile` 은 무시). 지연 ≈ 5분.
2. 한 줄은 공백 구분 34개 필드(문서 순서 고정 · 새 필드는 뒤에 추가). 진단에 쓰는 건 열 개 남짓: client · target · 처리 시간 3개 · **elb_status / target_status** · request · ssl · target_group · trace_id · matched_rule_priority · actions_executed · **ip_address(노드)**.
3. **elb 코드 ≠ target 코드**이거나 target 이 `-` 면 ALB 가 스스로 낸 응답(규칙 403 · 503 · 504 · 460). 같으면 서버 응답을 그대로 전달한 것.
4. 처리 시간 세 개: `request_processing`(ALB 가 대상에 보내기까지) · **`target_processing`(대상이 답하기까지 — 느림의 주범)** · `response_processing`(응답을 돌려주기까지). 오늘 `/petclinic/vets` 는 `0.000 0.055 0.000` — Tomcat 55ms.
5. user_agent 에 공백이 있어 `awk` 필드 번호가 어긋난다 — 따옴표(`-F'"'`)로 자르거나 Athena 테이블(AWS 문서 예제)을 만든다.

**우리 값 — 14:19:57 KST 의 실제 한 줄**

```text
https 2026-09-17T05:19:57.006409Z app/mc-alb-public/0780e6e7d84abe76 3.172.65.112:48058 10.0.10.189:80 0.000 0.055 0.000 200 200 360 199 "HEAD https://petclinic.mission-critical.site:443/petclinic/vets HTTP/1.1" "curl/8.5.0" TLS_AES_128_GCM_SHA256 TLSv1.3 arn:…:targetgroup/mc-tg-web/5ae742de9f467369 "Root=1-6aab787c-27aaf3f93f32ff1f5a67dc16" "petclinic.mission-critical.site" "session-reused" 10 2026-09-17T05:19:56.950000Z "forward" "-" "-" "10.0.10.189:80" "200" "-" "-" TID_f412ec94f0d7274a995f1719b4f4f35e "-" "-" "-" 3.34.116.99 "-" "-"
```

<table header-row="true" fit-page-width="true">
	<tr>
		<td>필드(위치)</td>
		<td>값</td>
		<td>뜻</td>
	</tr>
	<tr>
		<td>type(1) · time(2)</td>
		<td>`https` · `05:19:57.006Z`</td>
		<td>HTTPS 리스너 · 응답 완료 시각(UTC · KST +9)</td>
	</tr>
	<tr>
		<td>client:port(4)</td>
		<td>`3.172.65.112:48058`</td>
		<td>**CloudFront 오리진 쪽 엣지** — 사용자 IP 아님(그건 CloudFront 로그 c-ip)</td>
	</tr>
	<tr>
		<td>target:port(5)</td>
		<td>`10.0.10.189:80`</td>
		<td>web-a 가 받았다(2a) — 노드는 2c 였으니 교차 영역</td>
	</tr>
	<tr>
		<td>처리 시간(6·7·8)</td>
		<td>`0.000 0.055 0.000`</td>
		<td>대상(Apache→Tomcat)이 55ms</td>
	</tr>
	<tr>
		<td>**elb_status(9) · target_status(10)**</td>
		<td>`200 200`</td>
		<td>같다 = 서버 응답 그대로. 다르면 ALB 가 낸 것</td>
	</tr>
	<tr>
		<td>received · sent(11·12)</td>
		<td>`360 199`</td>
		<td>요청 바이트 · 응답 바이트(HEAD 라 본문 없음)</td>
	</tr>
	<tr>
		<td>request(13) · user_agent(14)</td>
		<td>`HEAD https://petclinic.…:443/petclinic/vets HTTP/1.1` · `curl/8.5.0`</td>
		<td>오리진 쪽은 HTTP/1.1</td>
	</tr>
	<tr>
		<td>ssl(15·16) · domain_name(19)</td>
		<td>`TLS_AES_128_GCM_SHA256 TLSv1.3` · `petclinic.mission-critical.site`</td>
		<td>2단계 CloudFront→ALB TLS · SNI</td>
	</tr>
	<tr>
		<td>trace_id(18)</td>
		<td>`Root=1-6aab787c-…`</td>
		<td>`X-Amzn-Trace-Id` — Apache 에 넘어가는 헤더(LogFormat 에 넣으면 대조 가능)</td>
	</tr>
	<tr>
		<td>chosen_cert(20) · **matched_rule_priority(21)**</td>
		<td>`session-reused` · `10`</td>
		<td>TLS 세션 재사용 · **규칙 10 = 도장 통과**(0 이면 기본 403)</td>
	</tr>
	<tr>
		<td>request_creation(22) · actions(23)</td>
		<td>`05:19:56.950Z` · `forward`</td>
		<td>받은 시각(응답까지 56ms) · 실행 작업</td>
	</tr>
	<tr>
		<td>conn_trace_id(30)</td>
		<td>`TID_f412ec94…`</td>
		<td>같은 연결의 요청들을 묶는 ID(keep-alive 분석)</td>
	</tr>
	<tr>
		<td>**ip_address(34)**</td>
		<td>`3.34.116.99`</td>
		<td>받은 **ALB 노드**(2c) — 0단계의 그 IP</td>
	</tr>
</table>
**없으면 · 오해**
- 액세스 로그를 안 켜면 "누가 403/504 를 냈나" 를 알 길이 없다 — 지표는 개수만 준다. S3 비용은 하루 수 KB.
- client 필드를 사용자 IP 로 오해하면 "3.172.x 에서 공격이 온다" 는 오진. 사용자 IP 는 CloudFront 로그 `c-ip` 또는 XFF.
- 5분 지연이 있어 "지금 막 난 장애" 는 지표·대상 상태로 먼저 보고, 로그는 사후 분석.

**눈으로 확인**

```bash
# 1) 최신 로그 객체 → 마지막 요청 줄 (헬스체크 제외)
K=$(aws s3 ls s3://mc-logs-528821350786/alb/public/ --recursive --profile mc-deploy | grep -v TestFile | tail -1 | awk '{print $4}')
aws s3 cp "s3://mc-logs-528821350786/$K" - --profile mc-deploy | zcat | grep -v health.html | tail -1
# 2) 진단용 열 개만 뽑기 — client · target · 3개 시간 · elb/target 코드 · 규칙 · 노드
aws s3 cp "s3://mc-logs-528821350786/$K" - --profile mc-deploy | zcat | grep -v health.html | awk -F'"' '{split($1,h," "); split($11,r," "); n=split($0,w," "); print h[4], h[5], h[6], h[7], h[8], "elb="h[9], "tgt="h[10], "rule="r[1], "node="w[n-2]}' | tail -3
# 3) ALB 가 스스로 낸 응답만 (elb ≠ target) — 오늘 0 이어야
aws s3 cp "s3://mc-logs-528821350786/$K" - --profile mc-deploy | zcat | awk '$9 != $10'
```

기대: 1) 위 형태의 한 줄 2) `3.172.65.112:48058 10.0.10.189:80 0.000 0.055 0.000 elb=200 tgt=200 rule=10 node=3.34.116.99` 류 3) 없음
## 2-2. ② Apache · Tomcat 로그 — 첫 IP 는 노드, 진짜 IP 는 헤더에
**무슨 일이 일어나나**
1. Apache `combined` 형식: `연결IP - - [시각] "요청줄" 코드 바이트 "Referer" "User-Agent"`. 첫 필드는 **연결 상대** = ALB 노드 사설 IP(`10.0.0.212` / `10.0.1.212`). 사용자 IP 는 `X-Forwarded-For` 헤더 안에 있는데 combined 는 그걸 **안 찍는다**.
2. Tomcat AccessLogValve(`common` 류): 첫 필드 = Internal ALB 노드(`10.0.20.193` / `10.0.21.43`). 같은 문제.
3. 두 가지 해법(로드맵): (a) LogFormat 에 `%｛X-Forwarded-For｝i` 를 추가한 `combined_xff` · (b) `mod_remoteip` 로 `%h` 자체를 XFF 의 사용자 IP 로 바꾸기(`RemoteIPHeader X-Forwarded-For` · `RemoteIPInternalProxy 10.0.0.0/16`). Tomcat 은 `RemoteIpValve`. XFF 값 형태: `221.148.195.245, 15.158.254.101` — **맨 앞이 사용자**.
4. 로그는 CloudWatch Agent 가 실시간으로 `/mc/web/access` · `/mc/web/error` · `/mc/was/access` · `/mc/was/catalina` · `/mc/was/gc` 로 올린다(스트림 = 인스턴스 ID). **서버 접속 없이** `aws logs tail` 로 본다 — Bastion 이 막혀도 관측 가능.
5. **오늘 발견(5·6단계)**: `/mc/web/access` 에 헬스체크가 시간당 1,442줄, 일반 요청은 같은 줄이 2번(httpd.conf 기본 CustomLog 중복). 로그로 요청 수를 세면 2배 — 요청 수는 ALB 로그·지표로 센다.

**우리 값 — 같은 요청의 서버 쪽 줄**
<table header-row="true" fit-page-width="true">
	<tr>
		<td>어디</td>
		<td>실제 줄 (14:19:56~57 KST)</td>
		<td>첫 IP 의 정체</td>
	</tr>
	<tr>
		<td>Apache (web-a) `/mc/web/access`</td>
		<td>`10.0.1.212 - - [17/Sep/2026:05:19:56 +0000] "HEAD /petclinic/vets HTTP/1.1" 200 - "-" "curl/8.5.0"`</td>
		<td>ALB 2c 노드(교차 영역으로 web-a 에)</td>
	</tr>
	<tr>
		<td>Tomcat (was) `/mc/was/access`</td>
		<td>`10.0.21.43 - - [17/Sep/2026:05:19:57 +0000] "HEAD /petclinic/vets HTTP/1.1" 200 -`</td>
		<td>Internal ALB 2c 노드</td>
	</tr>
	<tr>
		<td>Apache error `/mc/web/error`</td>
		<td>9/16 10:47 `AH00489 … resuming normal operations` 이후 없음</td>
		<td>—</td>
	</tr>
	<tr>
		<td>사용자 IP 가 있는 곳</td>
		<td>CloudFront 로그 `c-ip 221.148.195.245` · (헤더) XFF `221.148.195.245, 3.172.65.112`</td>
		<td>서버 로그엔 현재 없음</td>
	</tr>
	<tr>
		<td>잡음 (발견)</td>
		<td>헬스체크 1,442줄/h · 일반 요청 ×2</td>
		<td>web.sh 한 줄 수정 대상</td>
	</tr>
</table>
**없으면 · 오해**
- "10.0.0.212 가 우리 서버를 계속 친다" — 헬스체크(`ELB-HealthChecker/2.0`)와 ALB 노드다. 공격이 아니다.
- 서버 로그로 "몇 명이 왔나" 를 세면 지금은 2배(중복). 요청 수는 ALB `RequestCount` 나 ALB 로그.
- 로그가 서버 디스크에만 있으면 인스턴스 교체·ASG 축소 때 사라진다 — Agent 실시간 전송 + S3 아카이브가 그 답(⑤).

**눈으로 확인**

```bash
# 1) Apache 로그 — 첫 IP 가 ALB 노드
aws logs tail /mc/web/access --since 1h --profile mc-deploy --region ap-northeast-2 --format short | grep -v ELB-HealthChecker | tail -3
# 2) Tomcat 로그 — 첫 IP 가 Internal ALB 노드
aws logs tail /mc/was/access --since 1h --profile mc-deploy --region ap-northeast-2 --format short | grep -v '"GET /petclinic/ ' | tail -3
# 3) 스트림 = 인스턴스 ID (서버가 바뀌어도 로그는 남는다)
aws logs describe-log-streams --log-group-name /mc/web/access --profile mc-deploy --region ap-northeast-2 --query 'logStreams[].[logStreamName,lastEventTimestamp]' --output table
# 4) 발견 재확인 — 헬스체크 줄 수 · 중복
aws logs tail /mc/web/access --since 1h --profile mc-deploy --region ap-northeast-2 --format short | grep -c ELB-HealthChecker
# 5) 개선안 미리보기 — XFF 를 찍는 LogFormat (web.sh 에 넣을 줄 · 지금은 실행 안 함)
echo 'LogFormat "%{X-Forwarded-For}i %h %l %u %t \"%r\" %>s %b \"%{Referer}i\" \"%{User-Agent}i\"" combined_xff'
```

기대: 1) `10.0.0.212` 또는 `10.0.1.212 … "GET / HTTP/1.1" 200 8133` 2) `10.0.20.193` / `10.0.21.43 …` 3) 현재 2대 `i-01a195cff8acb28d8` · `i-01d1734d081d8bc57` **+ 교체돼 사라진 옛 인스턴스 ID 10개** — 서버가 없어져도 로그는 남는다 4) 약 1,400 5) (출력만)
## 2-3. ③ 지표 4개 — ALB 잘못인가 서버 잘못인가
**무슨 일이 일어나나**
1. ALB 는 `AWS/ApplicationELB` 네임스페이스에 1분 단위 지표를 **무료**로 낸다. 차원은 로드 밸런서(`app/mc-alb-public/0780e6e7d84abe76`) 와 대상 그룹(`targetgroup/mc-tg-web/5ae742de9f467369`).
2. **`HTTPCode_ELB_5XX_Count`** = ALB 가 **만든** 5xx(503 대상 없음 · 504 유휴 초과 · 502 대상 연결 실패). 오르면 대상 그룹 · 타임아웃 · 헬스체크를 본다(5·7단계).
3. **`HTTPCode_Target_5XX_Count`** = 대상이 **돌려준** 5xx(Apache/Tomcat 500 · Apache 가 전달한 Internal ALB 503). 오르면 서버 로그(`/mc/web/error` · `/mc/was/catalina`)를 본다.
4. **`TargetResponseTime`** = 대상이 답하는 데 걸린 시간 분포. 평균이 아니라 **p95/p99** 로 본다(알람은 p95 › 2s). ALB 로그의 target_processing_time 과 같은 것.
5. **`HealthyHostCount` / `UnHealthyHostCount`**(대상 그룹 차원) = 정상/비정상 대상 수. WEB 2/0 · WAS 2/0 이어야. + `RequestCount` · `ActiveConnectionCount` 는 부하 기준선(Phase 3 폭주 실험).

**우리 값 (지난 24h · 1h)**
<table header-row="true" fit-page-width="true">
	<tr>
		<td>지표</td>
		<td>값</td>
		<td>읽기</td>
	</tr>
	<tr>
		<td>`HTTPCode_ELB_5XX_Count` (24h)</td>
		<td>0 (`None`)</td>
		<td>ALB 가 낸 5xx 없음</td>
	</tr>
	<tr>
		<td>`HTTPCode_Target_5XX_Count` (24h)</td>
		<td>0</td>
		<td>서버가 낸 5xx 없음</td>
	</tr>
	<tr>
		<td>`HTTPCode_ELB_4XX_Count` (24h)</td>
		<td>0</td>
		<td>규칙 403 없음 = 도장 없는 요청이 리스너까지 온 적 없음</td>
	</tr>
	<tr>
		<td>`RequestCount` (24h)</td>
		<td>206</td>
		<td>헬스체크 제외 실제 요청 — 서버 로그(×2 · 헬스체크 포함)와 다름</td>
	</tr>
	<tr>
		<td>`TargetResponseTime` p95 (1h)</td>
		<td>0.35s</td>
		<td>임계 2s 에 한참 미달</td>
	</tr>
	<tr>
		<td>`HealthyHostCount` / `UnHealthyHostCount` (mc-tg-web · 1h)</td>
		<td>2 / 0</td>
		<td>정상</td>
	</tr>
</table>
**없으면 · 오해**
- ELB_5XX 와 Target_5XX 를 합쳐 "5xx 율" 만 보면 원인 방향(ALB 설정 vs 서버 코드)을 잃는다. 반드시 둘로.
- 평균 응답 시간은 느린 1% 를 숨긴다 — p95/p99.
- 지표는 1분 해상도 · 최대 15개월 보관(1분 해상도는 15일). 장기 추세는 대시보드로 남긴다(CloudWatch 대시보드 `mc-*` — 콘솔 가이드 ⑪).

**눈으로 확인**

```bash
LB=app/mc-alb-public/0780e6e7d84abe76; TG=targetgroup/mc-tg-web/5ae742de9f467369
# 1) 지난 24h — ALB 5XX · Target 5XX · ELB 4XX · 요청 수
for m in HTTPCode_ELB_5XX_Count HTTPCode_Target_5XX_Count HTTPCode_ELB_4XX_Count RequestCount; do printf "%-28s " $m; aws cloudwatch get-metric-statistics --namespace AWS/ApplicationELB --metric-name $m --dimensions Name=LoadBalancer,Value=$LB --start-time $(date -u -d '-24 hour' +%FT%TZ) --end-time $(date -u +%FT%TZ) --period 86400 --statistics Sum --profile mc-deploy --region ap-northeast-2 --query 'Datapoints[0].Sum' --output text; done
# 2) 응답 시간 p95 (1h)
aws cloudwatch get-metric-statistics --namespace AWS/ApplicationELB --metric-name TargetResponseTime --dimensions Name=LoadBalancer,Value=$LB --start-time $(date -u -d '-1 hour' +%FT%TZ) --end-time $(date -u +%FT%TZ) --period 3600 --extended-statistics p95 --profile mc-deploy --region ap-northeast-2 --query 'Datapoints[0].ExtendedStatistics.p95' --output text
# 3) 정상/비정상 대상 수 (1h 최소/최대)
for m in HealthyHostCount UnHealthyHostCount; do printf "%s " $m; aws cloudwatch get-metric-statistics --namespace AWS/ApplicationELB --metric-name $m --dimensions Name=LoadBalancer,Value=$LB Name=TargetGroup,Value=$TG --start-time $(date -u -d '-1 hour' +%FT%TZ) --end-time $(date -u +%FT%TZ) --period 3600 --statistics Minimum Maximum --profile mc-deploy --region ap-northeast-2 --query 'Datapoints[0].[Minimum,Maximum]' --output text; done
```

기대: 1) `None None None 206`(None = 0) 2) `0.3x` 3) `HealthyHostCount 2.0 2.0` · `UnHealthyHostCount 0.0 0.0`
## 2-4. ④ 알람 3개 → SNS — 지금은 아무도 안 받는다
**무슨 일이 일어나나**
1. 알람 = 지표 + 임계 + 기간 + 상태(`OK` / `ALARM` / `INSUFFICIENT_DATA`). 임계를 **N 회 연속** 넘으면 ALARM 이 되고 SNS 토픽에 발행한다. 데이터가 없으면 INSUFFICIENT_DATA(트래픽 0 이면 정상).
2. 우리 알람 3개(Terraform `observability.tf`): WEB 응답 지연 · WAS 비정상 대상 · RDS 연결 수. 전부 SNS `mc-alerts` 로.
3. **발견: `mc-alerts` 토픽에 구독이 0건** — tfvars `alert_emails` 가 비어 있다. 알람이 울려도 이메일·Slack 어디에도 안 간다. 값을 넣고 apply → 이메일 확인 링크 클릭이 필요.
4. 빠진 알람(로드맵): WEB `HealthyHostCount ‹ 2` · `HTTPCode_ELB_5XX_Count ≥ 1` · ACM 만료 · Bastion 로그인 실패. 알람 추가는 비용 거의 0.
5. 지표 알람은 **로그를 못 본다** — 특정 문자열(예: `OutOfMemoryError`)로 알리려면 로그 그룹의 **지표 필터**를 만들어 지표로 바꾼 뒤 알람을 건다(로드맵).

**우리 값**
<table header-row="true" fit-page-width="true">
	<tr>
		<td>알람</td>
		<td>지표 · 차원</td>
		<td>조건</td>
		<td>상태 (9/17)</td>
	</tr>
	<tr>
		<td>`mc-alb-p95-latency`</td>
		<td>`TargetResponseTime` p95 · mc-alb-public</td>
		<td>› 2.0s · 60s × 3</td>
		<td>OK (트래픽 없을 땐 INSUFFICIENT_DATA)</td>
	</tr>
	<tr>
		<td>`mc-was-unhealthy-host`</td>
		<td>`UnHealthyHostCount` Maximum · mc-tg-was + mc-alb-internal</td>
		<td>≥ 1 · 60s × 2</td>
		<td>OK</td>
	</tr>
	<tr>
		<td>`mc-rds-connections-high`</td>
		<td>`DatabaseConnections` · mc-petclinic</td>
		<td>› 60 · 60s × 3</td>
		<td>OK</td>
	</tr>
	<tr>
		<td>SNS 토픽</td>
		<td>`arn:aws:sns:ap-northeast-2:528821350786:mc-alerts`</td>
		<td>구독 **0건**</td>
		<td>⚠️ 알림 수신자 없음</td>
	</tr>
	<tr>
		<td>없는 알람</td>
		<td>WEB HealthyHostCount · ELB_5XX · ACM 만료</td>
		<td>로드맵</td>
		<td>—</td>
	</tr>
</table>
**없으면 · 오해**
- "알람이 OK 니 안전" — 구독자가 없으면 ALARM 이 돼도 아무 일도 안 일어난다. 알람은 **수신자까지** 있어야 완성.
- INSUFFICIENT_DATA 를 장애로 오해하지 말 것 — 트래픽이 없어 p95 를 계산할 데이터가 없는 상태.
- 알람 임계를 너무 낮게 잡으면(예: p95 › 0.5s) 잡음으로 무시하게 된다 — 2s 는 "사용자가 느끼는" 선.

**눈으로 확인**

```bash
# 1) 알람 3개 — 이름 · 지표 · 임계 · 상태 · 보낼 곳
aws cloudwatch describe-alarms --alarm-name-prefix mc- --profile mc-deploy --region ap-northeast-2 --query 'MetricAlarms[].[AlarmName,MetricName,ComparisonOperator,Threshold,EvaluationPeriods,StateValue,AlarmActions[0]]' --output table
# 2) 토픽 구독 — 0 이면 아무도 안 받는다
aws sns list-subscriptions-by-topic --topic-arn arn:aws:sns:ap-northeast-2:528821350786:mc-alerts --profile mc-deploy --region ap-northeast-2 --query 'length(Subscriptions)'
# 3) 코드 근거 — 구독은 alert_emails 로 만들어진다
grep -n "alert_emails" infra/terraform-kdt5/variables.tf infra/terraform-kdt5/observability.tf
```

기대: 1) 3줄 · 전부 `arn:aws:sns:…:mc-alerts` 2) `0` 3) `variable "alert_emails"` 와 `for_each = toset(var.alert_emails)` 류
## 2-5. ⑤ 로그 지도 — 어디에 얼마나 남나
**무슨 일이 일어나나**
1. **서버 로그**: CloudWatch Agent → 로그 그룹(`/mc/web/access` 등 · 보존 30일 · KMS) → **구독 필터** → Kinesis Firehose(`mc-cwlogs-‹tier›` · 5MB/300s 버퍼 · GZIP · 압축 해제 + 줄바꿈) → S3 `cwlogs/‹tier›/yyyy/MM/dd/` (수명 주기 **1년**). 실시간은 로그 그룹, 장기는 S3.
2. **ALB 로그**: ALB → S3 `alb/public/` 직접(5분). **CloudFront 로그**: 표준 로깅 → S3 `cloudfront/`(시간별 · 최대 24h 지연 · 오늘은 ≈30분). 둘 다 CloudWatch Logs 를 안 거친다.
3. **WAF 로그**: 배포가 글로벌이라 **us-east-1** 로그 그룹 `aws-waf-logs-mc`(30일)로만 간다 — 서울 Firehose 아카이브엔 없다. 필요하면 us-east-1 에 Firehose 를 하나 더.
4. **DB 로그**(9/17): RDS `error` · `slowquery`(`long_query_time=2`) 내보내기 + Proxy 로그 → `/aws/rds/…` 그룹 → Firehose `mc-cwlogs-db` → S3 `cwlogs/db/`. **Bastion**: sshd → `/mc/bastion/secure`(90일) → `cwlogs/bastion/`.
5. 로그 그룹 스트림 이름 = 인스턴스 ID 라서 인스턴스가 사라져도 로그는 남고, ASG(10단계)에서도 그대로 동작한다.

**우리 값 — 지도**
<table header-row="true" fit-page-width="true">
	<tr>
		<td>로그</td>
		<td>실시간 위치 · 보존</td>
		<td>아카이브 · 보존</td>
	</tr>
	<tr>
		<td>Apache access / error</td>
		<td>`/mc/web/access` · `/mc/web/error` (30일)</td>
		<td>Firehose `mc-cwlogs-web` → `s3://mc-logs-528821350786/cwlogs/web/` (1년)</td>
	</tr>
	<tr>
		<td>Tomcat access / catalina / gc</td>
		<td>`/mc/was/access` · `/mc/was/catalina` · `/mc/was/gc` (30일)</td>
		<td>`mc-cwlogs-was` → `cwlogs/was/`</td>
	</tr>
	<tr>
		<td>Bastion sshd</td>
		<td>`/mc/bastion/secure` (90일)</td>
		<td>`mc-cwlogs-bastion` → `cwlogs/bastion/`</td>
	</tr>
	<tr>
		<td>RDS error / slowquery / Proxy</td>
		<td>`/aws/rds/instance/mc-petclinic/error` · `…/slowquery` · `/aws/rds/proxy/mc-rds-proxy` (30일)</td>
		<td>`mc-cwlogs-db` → `cwlogs/db/`</td>
	</tr>
	<tr>
		<td>ALB 액세스</td>
		<td>—</td>
		<td>`alb/public/` (5분 · gzip)</td>
	</tr>
	<tr>
		<td>CloudFront 표준</td>
		<td>—</td>
		<td>`cloudfront/` (시간별 · 지연)</td>
	</tr>
	<tr>
		<td>WAF</td>
		<td>`aws-waf-logs-mc` **us-east-1** (30일)</td>
		<td>없음 (로드맵)</td>
	</tr>
	<tr>
		<td>구독 필터 확인</td>
		<td>`/mc/web/access → mc-cwlogs-web` · `/mc/web/error → mc-cwlogs-web` · `/mc/was/catalina → mc-cwlogs-was` · `/aws/rds/…/error → mc-cwlogs-db`</td>
		<td>실측</td>
	</tr>
</table>
**없으면 · 오해**
- 로그 그룹 30일만 있으면 "지난달 장애" 를 못 본다 — S3 1년이 그 답. 반대로 S3 만 있으면 실시간 `tail` 이 안 된다.
- "WAF 로그도 서울 S3 에 있겠지" — 없다. us-east-1 에 있다. 장애 분석 때 리전을 바꿔야 한다.
- Firehose 버퍼(300s) 때문에 S3 엔 최대 5분 뒤에 나타난다. 실시간은 로그 그룹.

**눈으로 확인**

```bash
# 1) 로그 그룹 9개 · 보존
aws logs describe-log-groups --log-group-name-prefix /mc/ --profile mc-deploy --region ap-northeast-2 --query 'logGroups[].[logGroupName,retentionInDays]' --output text
aws logs describe-log-groups --log-group-name-prefix /aws/rds --profile mc-deploy --region ap-northeast-2 --query 'logGroups[].[logGroupName,retentionInDays]' --output text
# 2) 구독 필터 → Firehose
for g in /mc/web/access /mc/was/catalina /aws/rds/instance/mc-petclinic/error; do aws logs describe-subscription-filters --log-group-name $g --profile mc-deploy --region ap-northeast-2 --query 'subscriptionFilters[].[logGroupName,destinationArn]' --output text; done
# 3) S3 아카이브 — 오늘 프리픽스
aws s3 ls s3://mc-logs-528821350786/cwlogs/web/$(date -u +%Y/%m/%d)/ --profile mc-deploy | tail -2
# 4) WAF 로그는 us-east-1 에
aws logs tail aws-waf-logs-mc --region us-east-1 --since 10m --profile mc-deploy --format short | tail -1 | cut -c1-200
```

기대: 1) `/mc/*` 6개(30·90일) · `/aws/rds/*` 3개(30일) 2) `… mc-cwlogs-web` · `… mc-cwlogs-was` · `… mc-cwlogs-db` 3) `mc-cwlogs-web-1-2026-09-17-…gz` 류 4) `｛"timestamp":…,"action":"ALLOW",…｝`
## 2-6. 한 요청이 남기는 흔적 다섯 곳 — 14:19:57 KST `HEAD /petclinic/vets`
<table header-row="true" fit-page-width="true">
	<tr>
		<td>어디</td>
		<td>실제 줄 (발췌)</td>
		<td>여기서만 알 수 있는 것</td>
	</tr>
	<tr>
		<td>① CloudFront 로그 `cloudfront/`</td>
		<td>`05:19:57 ICN80-P4 401 221.148.195.245 HEAD d2p7som2iuyba.cloudfront.net /petclinic/vets 200 … Miss … https 67 0.061 … TLSv1.3 TLS_AES_128_GCM_SHA256 Miss HTTP/2.0 … 53642 0.061`</td>
		<td>**사용자 IP** `221.148.195.245` · 엣지 `ICN80-P4` · 캐시 `Miss` · 뷰어 `HTTP/2.0` · 전체 시간 61ms</td>
	</tr>
	<tr>
		<td>① WAF 로그 `aws-waf-logs-mc` (us-east-1)</td>
		<td>`｛"action":"ALLOW","terminatingRuleId":"Default_Action", … "httpRequest":｛"clientIp":"221.148.195.245", "uri":"/petclinic/vets"…｝｝`</td>
		<td>어느 규칙이 통과/차단했나(`Default_Action` = 전부 통과)</td>
	</tr>
	<tr>
		<td>① ALB 로그 `alb/public/`</td>
		<td>`3.172.65.112:48058 10.0.10.189:80 0.000 0.055 0.000 200 200 … "petclinic.mission-critical.site" "session-reused" 10 … "forward" … 3.34.116.99`</td>
		<td>엣지 IP · **대상 web-a** · 대상 처리 55ms · **규칙 10** · **노드 2c**</td>
	</tr>
	<tr>
		<td>② Apache `/mc/web/access` (web-a)</td>
		<td>`10.0.1.212 - - [17/Sep/2026:05:19:56 +0000] "HEAD /petclinic/vets HTTP/1.1" 200 -`</td>
		<td>ALB 2c 노드가 왔다 · Apache 가 프록시했다</td>
	</tr>
	<tr>
		<td>② Tomcat `/mc/was/access`</td>
		<td>`10.0.21.43 - - [17/Sep/2026:05:19:57 +0000] "HEAD /petclinic/vets HTTP/1.1" 200 -`</td>
		<td>Internal ALB 2c 노드 · Tomcat 이 200</td>
	</tr>
	<tr>
		<td>③ 지표</td>
		<td>`RequestCount +1` · `TargetResponseTime 0.055` · 5XX 0</td>
		<td>개수와 분포 — 개별 요청은 안 보임</td>
	</tr>
	<tr>
		<td>④ 알람</td>
		<td>변화 없음 (p95 0.35s ‹ 2s)</td>
		<td>—</td>
	</tr>
	<tr>
		<td>⑤ 5분 뒤</td>
		<td>Firehose → `cwlogs/web/2026/09/17/` · `cwlogs/was/…` 에 같은 줄</td>
		<td>1년 보관</td>
	</tr>
</table>
기억할 것 셋: **사용자 IP 는 CloudFront 로그에, 대상·규칙·노드는 ALB 로그에, 서버 로그의 첫 IP 는 노드** · **5xx 는 ELB 것과 Target 것을 따로** · **알람은 수신자까지 있어야 완성**(지금 0건).
# 3. 용어 — 이 단계에서만 쓰는 것
<table header-row="true" fit-page-width="true">
	<tr>
		<td>용어</td>
		<td>한 줄</td>
		<td>비유</td>
	</tr>
	<tr>
		<td>액세스 로그</td>
		<td>요청 한 건마다 한 줄. ALB · CloudFront · Apache · Tomcat 이 각자 남김</td>
		<td>방문 기록부</td>
	</tr>
	<tr>
		<td>elb_status_code vs target_status_code</td>
		<td>ALB 가 준 코드 vs 대상이 준 코드. 다르면 ALB 가 스스로 낸 것</td>
		<td>창구가 대신 답한 경우</td>
	</tr>
	<tr>
		<td>matched_rule_priority</td>
		<td>어느 규칙이 잡았나(10 = 도장 통과 · 0 = 기본 403)</td>
		<td>어느 지침으로 처리했나</td>
	</tr>
	<tr>
		<td>X-Forwarded-For · c-ip</td>
		<td>서버 쪽에서 사용자 IP 를 찾는 두 곳(헤더 · CloudFront 로그)</td>
		<td>원래 방문자 이름표</td>
	</tr>
	<tr>
		<td>지표 · 차원 · 통계</td>
		<td>이름(RequestCount) · 어느 리소스(LB · TG) · 어떻게 집계(Sum · p95)</td>
		<td>항목 · 부서 · 합계/상위 5%</td>
	</tr>
	<tr>
		<td>p95</td>
		<td>느린 순으로 5% 지점 값 — "대부분의 사용자가 겪는 최악"</td>
		<td>줄 서기 상위 5% 대기 시간</td>
	</tr>
	<tr>
		<td>알람 · SNS 구독</td>
		<td>임계 초과 시 토픽 발행 · 토픽을 받는 이메일/Slack</td>
		<td>경보기 · 경보를 받을 사람</td>
	</tr>
	<tr>
		<td>구독 필터 · Firehose</td>
		<td>로그 그룹의 줄을 실시간으로 S3 로 흘려보내는 통로</td>
		<td>기록부 복사본을 창고로</td>
	</tr>
	<tr>
		<td>보존(retention) · 수명 주기</td>
		<td>로그 그룹 30일 · S3 1년 뒤 삭제</td>
		<td>보관 기한</td>
	</tr>
</table>
# 4. 왜 이렇게 만들었나 (멘토가 물을 만한 것)
- **왜 서버 로그를 CloudWatch Logs 로 보내나?** 서버 접속 없이 보고, 인스턴스가 사라져도 남고(ASG 전제), 지표 필터·알람으로 이어진다.
- **왜 S3 아카이브까지?** 로그 그룹 보존을 길게 두면 비쌈. S3 는 싸고 Athena 로 분석 가능. 1년은 프로젝트 기간 + 여유.
- **왜 ALB·CloudFront 로그는 S3 직접인가?** 서비스가 S3 만 지원(CloudWatch Logs 미지원). 실시간이 필요하면 Athena 파티션 프로젝션이나 S3 이벤트 → Lambda.
- **왜 WAF 로그는 us-east-1 인가?** CloudFront 용 WAF 는 글로벌(us-east-1)이라 로그 대상도 거기여야 한다.
- **왜 알람이 3개뿐인가?** 초기 구축 최소. 구독자 등록(`alert_emails`)과 WEB 알람 추가가 다음 순서 — 비용 거의 0.
# 5. 다음 단계(9. 장애 모드) 진입 기준
<details>
<summary>Q1. 로그 한 줄에서 "ALB 가 직접 낸 응답" 을 어떻게 알아보나?</summary>
	`elb_status_code` 와 `target_status_code` 가 다르거나 target 이 `-`. 규칙 403 · 503 · 504 가 그렇다. `matched_rule_priority` 가 0 이면 기본 작업(403).
</details>
<details>
<summary>Q2. Apache access_log 첫 IP 가 10.0.1.212 인 이유와, 사용자 IP 를 찾는 두 가지 방법은?</summary>
	연결 상대가 ALB 노드라서. (1) CloudFront 로그 `c-ip`(오늘 `221.148.195.245`) (2) 서버 로그에 XFF 를 찍기 — LogFormat `%｛X-Forwarded-For｝i` 또는 mod_remoteip(로드맵).
</details>
<details>
<summary>Q3. Target_5XX 는 0 인데 ELB_5XX 가 오른다. 어디를 보나?</summary>
	서버는 멀쩡히 응답했다는 뜻. 대상 그룹 정상 대상 수(503) · 유휴·응답 시간(504) · keep-alive 불일치(502) — 5·7단계 항목. ALB 로그 `error_reason`.
</details>
<details>
<summary>Q4. 알람이 ALARM 이 됐는데 아무도 못 받았다. 왜?</summary>
	SNS `mc-alerts` 에 구독이 0건(`alert_emails` 비어 있음). 이메일을 넣고 apply 한 뒤 확인 메일의 링크를 눌러야 구독이 활성화된다.
</details>
# 6. 읽을 자료
- AWS 문서 — *Access logs for your Application Load Balancer* (34개 필드 표 · Athena 예제)
- AWS 문서 — *CloudWatch metrics for your Application Load Balancer* · *Standard logging (CloudFront)* 필드 표
- Apache 문서 — *mod_log_config* (`%｛header｝i`) · *mod_remoteip*
- 🗂️ CloudWatch Logs 총정리 · 로그 흐름 도면(`docs/architecture-log-flow.png`) · 콘솔 구축 가이드 **⑩ · ⑪** 절
<callout icon="🗺️" color="gray_bg">
	**로드맵 위치**: 0 VPC 입구 → 1 HTTP 기초 → 2 TLS 종료 지점 → 3 ALB 해부 → 4 오리진 보호(헤더) → 5 헬스체크 → 6 Apache 프록시 → 7 분산·타임아웃 → **8 WEB 관측(이 페이지)** → 9 장애 모드 → 10 ASG·AMI.
</callout>
