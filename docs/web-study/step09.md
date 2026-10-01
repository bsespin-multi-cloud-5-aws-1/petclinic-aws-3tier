<callout icon="🚨" color="blue_bg">
	**이 단계의 목표**: WEB 구간에서 날 수 있는 장애를 "누가 어떤 코드를 내나" 로 분류하고, 각 경우에 사용자 화면 · 로그 · 지표가 어떻게 되는지 미리 알며, 신고 한 통에서 원인까지 5분 안에 가는 순서를 몸에 익힌다. 그리고 하나는 직접 내 본다. 하루 분량. 값은 2026-09-17 mc-deploy 실측(5xx 는 지난 24h 0 건 — 그래서 미리 표로).
</callout>
# 0. 그림 한 장

```text
사용자 화면            CloudFront                 ALB                       WEB(Apache)            WAS(Tomcat)
"점검 페이지"  ◀── ① 502/503/504 를 503 점검 페이지로 대체 ──┐
                    ② 오리진 그룹: 500·502·503·504 면 S3 로 폴백(GET)   ├── 503: 정상 대상 0 ──── B WEB 2대 죽음
                                                            ├── 502: 연결 끊김 ────── A WEB 1대 죽음(30초) · keep-alive 불일치
                                                            └── 504: 60s 무응답 ──── D 느린 WAS(DB·GC) — CloudFront 30s 가 먼저
"흰 403"       ◀── ① 4xx 는 그대로 ──────────────────────────── 규칙 403 ─────────────────────── E 도장 불일치
"앱만 점검"    ◀── 랜딩 / 는 200, /petclinic/* 만 503 ────────────────────── Apache 가 Internal ALB 503 전달 ── C WAS 죽음
"화면 깨짐"    ◀── 캐시가 옛 css ──────────────────────────────────────────────────────────────────── F 무효화 누락
   ③ 장애 6가지 A~F           ④ 직접 내 보기(A · 30초 · 안전)          ⑤ 1초 진단: 랜딩 200 이면 WEB 살아 있음 → 대상 상태 → 로그
```

핵심 하나: 사용자 신고는 거의 항상 **"점검 페이지가 떠요"** 다. 진짜 코드(502/503/504)와 낸 주체(CloudFront/ALB/서버)는 로그에서 찾는다 — 그래서 8단계가 먼저였다.
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
		<td>5xx 는 누가 내나</td>
		<td>**503** 정상 대상 0(ALB) · **502** 연결 끊김/이상 응답(ALB) · **504** 기다리다 포기(CloudFront 30s 또는 ALB 60s) · **500** 은 앱(Tomcat)</td>
		<td>지난 24h ELB_5XX 0 · Target_5XX 0 · ELB_4XX 0 — 그래서 아래는 "미리 아는" 표</td>
	</tr>
	<tr>
		<td>②</td>
		<td>점검 페이지가 뜨는 조건</td>
		<td>CloudFront 사용자 지정 오류 응답: 오리진이 **502·503·504** → `/maintenance.html` 을 **503** 으로(오류 캐시 10s). 오리진 그룹은 500·502·503·504 에 S3 폴백(GET/HEAD). **403·404·500 은 그대로**</td>
		<td>`CustomErrorResponses 502→503 · 503→503 · 504→503 · TTL 10` · 오리진 그룹 `alb-with-maintenance-failover [503,502,500,504]` · `/maintenance.html` 지금도 200(S3)</td>
	</tr>
	<tr>
		<td>③</td>
		<td>장애 6가지 A~F</td>
		<td>WEB 1대 · WEB 2대 · WAS · 느림 · 도장 불일치 · 캐시 — 각각 코드 · 화면 · 로그 · 복구가 다르다</td>
		<td>표 2-3</td>
	</tr>
	<tr>
		<td>④</td>
		<td>직접 내 보기</td>
		<td>장애 A(web-a httpd 60초 정지)는 서비스가 유지되는 안전한 실험 — 30초 unhealthy · 20초 복귀를 눈으로</td>
		<td>Bastion 경유 필요(공인 IP 허용 후) · 관찰 명령 2-4</td>
	</tr>
	<tr>
		<td>⑤</td>
		<td>1초 진단 · 복구 순서</td>
		<td>랜딩 `/` 가 200 이면 WEB 은 살아 있다(→ WAS) · 점검 페이지면 WEB/ALB → 대상 상태 → ALB 로그 elb/target 코드 → 서버 로그</td>
		<td>랜딩 200 · 대상 healthy 2/2 · 알람 OK — 정상 기준선</td>
	</tr>
</table>
# 2. 자세히 — 항목마다 "무슨 일 · 우리 값 · 없으면 · 눈으로 확인"
## 2-1. ① 5xx 는 누가 내나 — 코드는 사과하는 사람의 이름표
**무슨 일이 일어나나**
1. **500** 은 끝 서버(Tomcat 예외 · Apache 내부 오류)가 낸다. ALB 로그엔 `elb 500 · target 500`(같음). 서버 로그(`/petclinic/was/catalina` 스택 트레이스)를 본다.
2. **502 Bad Gateway** 는 중간(ALB)이 "뒤와 얘기가 이상하게 끝났다" — 대상이 연결을 거부(httpd 죽음) · 먼저 닫음(keep-alive 5 ‹ 60) · 응답 형식 오류. ALB 로그 `elb 502 · target -` · `error_reason`. CloudFront 도 오리진과 TLS/연결이 깨지면 502 를 낸다(인증서 불일치 등).
3. **503 Service Unavailable** 은 ALB 가 "보낼 정상 대상이 없다"(WEB 2대 unhealthy · 대상 그룹 비어 있음). `elb 503 · target -`. Apache 가 Internal ALB 의 503 을 **그대로 전달**하면 `elb 503 · target 503`(같음 = 서버가 준 것) — 이건 WAS 장애.
4. **504 Gateway Timeout** 은 "기다리다 포기" — CloudFront 30s(사용자가 보는 것) 또는 ALB 60s(로그). 원인은 느린 WAS/DB.
5. 사용자는 502·503·504 를 못 본다 — CloudFront 가 **전부 점검 페이지(503)** 로 바꾼다(②). 그래서 코드는 CloudFront 로그(`sc-status` · `x-edge-result-type`)와 ALB 로그에서 찾는다.

**우리 값 — 코드 · 주체 · 로그 표시**
<table header-row="true" fit-page-width="true">
	<tr>
		<td>코드</td>
		<td>누가</td>
		<td>ALB 로그</td>
		<td>원인 후보</td>
		<td>먼저 볼 것</td>
	</tr>
	<tr>
		<td>500</td>
		<td>Tomcat / Apache</td>
		<td>`500 500`</td>
		<td>앱 예외 · DB 연결 실패(Proxy TLS · 자격 증명)</td>
		<td>`/petclinic/was/catalina` · `/aws/rds/proxy/mc-rds-proxy`</td>
	</tr>
	<tr>
		<td>502</td>
		<td>ALB</td>
		<td>`502 -` · `error_reason`</td>
		<td>httpd 죽음(판정 전 30s) · keep-alive 불일치 · 재시작 중</td>
		<td>대상 상태 · `/petclinic/web/error` · 7단계 표</td>
	</tr>
	<tr>
		<td>503</td>
		<td>ALB</td>
		<td>`503 -`</td>
		<td>정상 대상 0</td>
		<td>`HealthyHostCount` · 대상 Reason</td>
	</tr>
	<tr>
		<td>503</td>
		<td>WAS(Internal ALB) → Apache 전달</td>
		<td>`503 503`</td>
		<td>WAS 정상 대상 0</td>
		<td>`mc-was-unhealthy-host` · mc-tg-was 상태</td>
	</tr>
	<tr>
		<td>504</td>
		<td>CloudFront(30s) / ALB(60s)</td>
		<td>ALB 는 `200`(늦게 성공) 또는 `504 -`</td>
		<td>느린 쿼리 · GC · 외부 호출</td>
		<td>`TargetResponseTime p95` · `slowquery` 로그</td>
	</tr>
	<tr>
		<td>403</td>
		<td>ALB 규칙 / WAF / S3</td>
		<td>`403 -` rule 0 / (없음) / —</td>
		<td>도장 불일치 / 차단 / 없는 키</td>
		<td>`matched_rule_priority` · WAF 로그 · 경로</td>
	</tr>
</table>
**없으면 · 오해**
- "5xx 는 다 서버 잘못" — 502·503·504 는 **중간이 대신 사과**하는 코드. 서버는 죽었거나(503) 느리거나(504) 끊겼거나(502).
- 같은 503 도 `503 -`(ALB 가 냄 · WEB 장애)와 `503 503`(WAS 장애를 Apache 가 전달)이 다르다 — 로그의 두 코드를 항상 같이.
- CloudFront 로그의 `x-edge-result-type: Error` 는 오리진 오류가 아니라 "오류 응답을 처리했다" 는 뜻 — 404 도 Error 로 찍힌다(1단계).
- 실제로 있었던 일(9/17 00:19 KST): 스캐너 한 IP 가 10분에 277건(`/.env` · `/zend/.env` · `phpinfo.php` …). WAF 가 186건 차단(403 · CloudFront 로그 time-taken 0.001s = 오리진에 안 감), 91건은 Apache 가 404. 장애가 아니라 **정상 방어** — 하지만 ALB `Target_4XX` 가 갑자기 오르면 이걸 먼저 의심.

**눈으로 확인**

```bash
# 1) 지난 24h — 코드 계열별 개수 (ALB 가 낸 것 · 대상이 낸 것 · 4xx)
for m in HTTPCode_ELB_5XX_Count HTTPCode_Target_5XX_Count HTTPCode_ELB_4XX_Count HTTPCode_Target_4XX_Count; do printf "%-30s " $m; aws cloudwatch get-metric-statistics --namespace AWS/ApplicationELB --metric-name $m --dimensions Name=LoadBalancer,Value=app/mc-alb-public/0780e6e7d84abe76 --start-time $(date -u -d '-24 hour' +%FT%TZ) --end-time $(date -u +%FT%TZ) --period 86400 --statistics Sum --profile mc-deploy --region ap-northeast-2 --query 'Datapoints[0].Sum' --output text; done
# 2) 오늘 ALB 로그의 코드 분포 (elb, target 쌍)
for K in $(aws s3 ls s3://mc-logs-528821350786/alb/public/ --recursive --profile mc-deploy | grep -v TestFile | grep "$(date -u +%Y/%m/%d)" | awk '{print $4}'); do aws s3 cp "s3://mc-logs-528821350786/$K" - --profile mc-deploy | zcat; done | awk '{print $9, $10}' | sort | uniq -c
# 3) CloudFront 쪽 코드 분포 (sc-status · x-edge-result-type)
for k in $(aws s3 ls s3://mc-logs-528821350786/cloudfront/ --profile mc-deploy | grep "$(date -u +%Y-%m-%d)" | awk '{print $4}'); do aws s3 cp "s3://mc-logs-528821350786/cloudfront/$k" - --profile mc-deploy | zcat; done | grep -v '^#' | awk -F'\t' '{print $9, $14}' | sort | uniq -c
```

기대: 1) 5XX 둘 다 `None` · ELB_4XX `None` · Target_4XX `119`(스캐너가 친 없는 경로의 Apache 404) 2) `200 200` 다수 · `301 301` · `302 302` · `404 404` (5xx 없음 · `-` 없음) 3) `200 Miss/Hit` · `404 Error 92` · **`403 Error 193`** · `301 Redirect` — 403 193건은 **9/17 00:19 KST 스캐너**(34.41.116.206 · `/.env` 류 277건 중 186건을 WAF KnownBadInputs·Common 이 차단, 91건은 오리진까지 가서 Apache 404). WAF 로그(us-east-1)로 확인 — 4단계 ⑤
## 2-2. ② 점검 페이지가 뜨는 조건 — 정확히
**무슨 일이 일어나나**
1. CloudFront **사용자 지정 오류 응답**: 오리진(ALB)이 **502 · 503 · 504** 를 주면 CloudFront 가 `/maintenance.html`(S3 `mc-maintenance` 오리진의 동작)을 가져와 **503** 으로 사용자에게 준다. `ErrorCachingMinTTL 10` — 10초 동안은 오리진에 다시 안 묻고 점검 페이지를 준다(폭주 시 오리진 보호).
2. **오리진 그룹** `alb-with-maintenance-failover`: 기본 오리진 ALB 가 **500 · 502 · 503 · 504** 를 주거나 연결이 안 되면 두 번째 오리진 S3 로 **같은 요청**을 다시 보낸다(GET/HEAD/OPTIONS 만). `/petclinic/resources/*` · `/petclinic/images/*` 동작이 이 그룹을 쓴다 — 정적 자원은 장애 때 S3 에서.
3. **403 · 404 · 500 은 그대로** 사용자에게 간다. 403(도장 불일치 · WAF)은 "거부" 라 점검 안내가 맞지 않고, 404 는 정상 동작, 500 은 앱 오류 페이지(Tomcat 기본)가 그대로. 그래서 장애 E 는 **흰 403**.
4. 점검 페이지 자체는 S3 정적 파일이라 WEB·WAS·DB 가 전부 죽어도 뜬다(지금도 `/maintenance.html` 200). CloudFront → S3 는 OAC 라 버킷은 비공개.
5. 배포 중 잠깐 나는 502 도 점검 페이지로 바뀐다 — 사용자에겐 "점검 중" 이 "오류" 보다 낫다는 설계.

**우리 값**
<table header-row="true" fit-page-width="true">
	<tr>
		<td>설정</td>
		<td>값 (실측)</td>
		<td>뜻</td>
	</tr>
	<tr>
		<td>사용자 지정 오류 응답</td>
		<td>`502 → 503 /maintenance.html` · `503 → 503 /maintenance.html` · `504 → 503 /maintenance.html` · TTL 10s</td>
		<td>세 코드만 대체 · 응답 코드는 503 으로 통일</td>
	</tr>
	<tr>
		<td>오리진 그룹</td>
		<td>`alb-with-maintenance-failover` · 멤버 `alb-public` → `s3-maintenance` · 기준 `[503, 502, 500, 504]`</td>
		<td>정적 자원 경로의 폴백</td>
	</tr>
	<tr>
		<td>그룹을 쓰는 동작</td>
		<td>`/petclinic/resources/*` · `/petclinic/images/*`</td>
		<td>기본 `*` 는 ALB 단독(오류 응답으로 처리)</td>
	</tr>
	<tr>
		<td>점검 페이지</td>
		<td>`https://petclinic.mission-critical.site/maintenance.html` → 200 · `server: AmazonS3` · `x-cache: RefreshHit`</td>
		<td>지금도 열린다</td>
	</tr>
	<tr>
		<td>그대로 가는 코드</td>
		<td>403 · 404 · 500 · 4xx 전부</td>
		<td>장애 E 는 흰 403</td>
	</tr>
</table>
**없으면 · 오해**
- 오류 응답을 안 두면 사용자는 ALB 의 기본 502/503 텍스트("503 Service Temporarily Unavailable")를 본다 — 브랜드 없는 흰 화면.
- TTL 10s 를 길게(예: 300s) 두면 복구 뒤에도 5분간 점검 페이지가 남는다. 짧게 두는 이유.
- "500 도 점검 페이지로 바꾸자" — 앱 버그(500)를 점검 페이지로 가리면 원인이 늦게 발견된다. 500 은 그대로 두고 알람(로드맵)으로.

**눈으로 확인**

```bash
# 1) 오류 응답 설정 — 502/503/504 → /maintenance.html 503 · TTL 10
aws cloudfront get-distribution-config --id E2PWXW3LUYTDEE --profile mc-deploy --query 'DistributionConfig.CustomErrorResponses.Items[].[ErrorCode,ResponseCode,ResponsePagePath,ErrorCachingMinTTL]' --output table
# 2) 오리진 그룹 — 기준 코드 · 멤버
aws cloudfront get-distribution-config --id E2PWXW3LUYTDEE --profile mc-deploy --query 'DistributionConfig.OriginGroups.Items[].[Id,FailoverCriteria.StatusCodes.Items,Members.Items[].OriginId]' --output json
# 3) 어느 동작이 그룹을 쓰나
aws cloudfront get-distribution-config --id E2PWXW3LUYTDEE --profile mc-deploy --query 'DistributionConfig.CacheBehaviors.Items[].[PathPattern,TargetOriginId]' --output text
# 4) 점검 페이지는 지금도 열린다 (S3)
curl -sI https://petclinic.mission-critical.site/maintenance.html | grep -iE "^HTTP|^server|^x-cache"
# 5) 403·404 는 그대로 — 점검 페이지가 아니다
curl -s -o /dev/null -w "%{http_code} " https://petclinic.mission-critical.site/nope; curl -s https://petclinic.mission-critical.site/nope | grep -ci "maintenance"
```

기대: 1) 세 줄 `502/503/504 → 503 /maintenance.html 10` 2) `alb-with-maintenance-failover [503,502,500,504] [alb-public, s3-maintenance]` 3) `/petclinic/resources/* alb-with-maintenance-failover` · `/petclinic/images/* …` · `/static/* s3-static` · `/images/* s3-static-images` · `/maintenance.html s3-maintenance` 4) `HTTP/2 200 · server: AmazonS3` 5) `404 0`
## 2-3. ③ 장애 6가지 A~F — 코드 · 화면 · 로그 · 복구
**무슨 일이 일어나나**
1. WEB 구간에서 실제로 나는 장애는 여섯 패턴으로 거의 다 덮인다. 각각 **누가 어떤 코드를**, **사용자가 무엇을**, **로그·지표에 무엇이**, **복구는 누가** 가 다르다.
2. A·B 는 WEB 자체, C 는 WAS(WEB 은 정상), D 는 느림(원인은 대개 DB), E 는 설정 불일치(헬스체크로 못 잡음), F 는 장애가 아닌 캐시 문제(신고는 온다).
3. 자동 복구는 A 만(헬스체크가 트래픽을 뺌). 나머지는 사람이(ASG 를 켜면 B·C 도 자동 교체 — 10단계).

**우리 값 — 표**
<table header-row="true" fit-page-width="true">
	<tr>
		<td>#</td>
		<td>상황</td>
		<td>누가 어떤 코드를</td>
		<td>사용자 화면</td>
		<td>로그·지표에서 보이는 것</td>
		<td>복구</td>
	</tr>
	<tr>
		<td>A</td>
		<td>WEB 1대 httpd 죽음</td>
		<td>≈30초간 그 서버로 간 요청 → ALB **502**(연결 거부). 이후 unhealthy 로 제외되면 정상</td>
		<td>잠깐(절반) 점검 페이지 → 곧 정상</td>
		<td>`UnHealthyHostCount 1` · ELB_5XX 소량 · ALB 로그 `502 -` · 대상 Reason `Target.FailedHealthChecks`</td>
		<td>자동(헬스체크). 서버는 `systemctl restart httpd` 또는 교체. **WEB 알람 없음**(로드맵)</td>
	</tr>
	<tr>
		<td>B</td>
		<td>WEB 2대 모두 죽음</td>
		<td>정상 대상 0 → ALB **503** → CloudFront 점검 페이지 **503**</td>
		<td>**점검 페이지** (랜딩 포함 전부)</td>
		<td>`HealthyHostCount 0` · ELB_5XX 급증 · ALB 로그 `503 -` · CloudFront 로그 `503 Error`</td>
		<td>교체(Terraform `-replace` 한 대씩) · ASG 였다면 자동</td>
	</tr>
	<tr>
		<td>C</td>
		<td>WAS 죽음 (WEB 정상)</td>
		<td>Apache 가 Internal ALB 의 503 을 그대로 → **503** → 점검 페이지. 단 `/` · `/health.html` · 정적은 200</td>
		<td>**앱 경로만** 점검 페이지 · 랜딩은 정상</td>
		<td>`mc-was-unhealthy-host` ALARM · ALB 로그 `503 503`(target 이 준 것) · Target_5XX 증가 · WEB 은 healthy 2</td>
		<td>WAS 재시작 · Tomcat 404 면 was.sh 의 자동 재시작 3회 · 교체</td>
	</tr>
	<tr>
		<td>D</td>
		<td>느린 응답 (DB 잠금 · GC · 풀 고갈)</td>
		<td>30초 넘으면 CloudFront **504** · 60초 넘으면 ALB **504**</td>
		<td>점검 페이지 (원인은 DB 인데 WEB 장애처럼 보임)</td>
		<td>`TargetResponseTime p95` ALARM · ALB 로그 target_processing 큼 · RDS `slowquery` · `mc-rds-connections-high`</td>
		<td>쿼리·풀 확인 · 7단계 타임아웃 표 · 앱 수정</td>
	</tr>
	<tr>
		<td>E</td>
		<td>도장(헤더) 불일치 (비밀값 교체 중 · 규칙 삭제)</td>
		<td>ALB 규칙 미매치 → **403** 고정 응답</td>
		<td>**흰 403 Forbidden** (점검 페이지 아님)</td>
		<td>ALB 로그 `403 -` · `matched_rule_priority 0` · ELB_4XX 급증 · **헬스체크는 healthy**(못 잡음)</td>
		<td>tfvars 값 일치시켜 apply · 규칙 복구</td>
	</tr>
	<tr>
		<td>F</td>
		<td>CloudFront 캐시가 옛 css/js</td>
		<td>장애 아님 — "화면이 깨짐" 신고</td>
		<td>레이아웃 깨짐 · 옛 화면</td>
		<td>응답 `x-cache: Hit` · 배포 직후</td>
		<td>무효화 `/static/*` `/images/*` `/petclinic/resources/*` (또는 파일명 버전)</td>
	</tr>
</table>
**없으면 · 오해**
- C 를 B 로 오진하면 WEB 을 재시작하느라 시간을 버린다 — 랜딩 `/` 부터 열어 보면 1초에 구분(⑤).
- D 를 WEB 장애로 오진하기 쉽다(화면은 같은 점검 페이지) — p95 와 slowquery 를 먼저.
- E 는 헬스체크가 healthy 라 "대상 그룹은 정상인데 전면 403" — 도장/규칙을 의심. 배포·비밀값 교체 직후면 거의 확실.

**눈으로 확인**

```bash
# 1) 정상 기준선 — A~F 어느 것도 아닌 상태 (비교용으로 지금 값을 적어 둔다)
curl -s -o /dev/null -w "landing=%{http_code} " https://petclinic.mission-critical.site/; curl -s -o /dev/null -w "app=%{http_code}\n" https://petclinic.mission-critical.site/petclinic/vets
TG=$(aws elbv2 describe-target-groups --names mc-tg-web --profile mc-deploy --region ap-northeast-2 --query 'TargetGroups[0].TargetGroupArn' --output text)
aws elbv2 describe-target-health --target-group-arn $TG --profile mc-deploy --region ap-northeast-2 --query 'TargetHealthDescriptions[].[Target.Id,TargetHealth.State]' --output text
aws cloudwatch describe-alarms --alarm-name-prefix mc- --profile mc-deploy --region ap-northeast-2 --query 'MetricAlarms[].[AlarmName,StateValue]' --output text
# 2) F 를 흉내 — 정적 자산의 캐시 상태 (Hit 이면 무효화 대상)
curl -sI https://petclinic.mission-critical.site/static/resources/css/petclinic.css | grep -iE "^x-cache|^cache-control|^etag"
```

기대: 1) `landing=200 app=200` · 두 대상 `healthy` · 알람 전부 `OK`(p95 는 트래픽 없으면 INSUFFICIENT_DATA) 2) `x-cache: Hit/Miss from cloudfront` · `max-age=86400`
## 2-4. ④ 직접 내 보기 — 장애 A (안전 · 60초 · 서비스 유지)
**무슨 일이 일어나나**
1. web-a 의 httpd 를 60초 멈춘다. web-c 가 살아 있으니 서비스는 유지되고, 5단계의 30초/20초를 눈으로 본다. 부하가 없는 시간에.
2. 준비: **Bastion 접속이 되어야 한다**(0단계 — 지금 PC 공인 IP `221.148.195.245` 는 `bastion_allowed_cidrs` 에 없어 SSH 가 timeout. 추가는 SG 변경이라 명시 지시 후 apply).
3. 관찰 셋: (1) 정지 후 unhealthy 까지 몇 초(기대 ≈30s) (2) 그 사이 사용자 코드에 502/503 이 몇 개 섞이나(절반 정도) (3) 시작 후 healthy 까지(기대 ≈20s). (4) **알람은 WEB 엔 없다** → 아무것도 안 울린다는 것 자체가 배움.
4. 뒤처리: 5분 뒤 ALB 로그에서 `elb ≠ target` 줄(502 · target `-`)을 세어 본다. CloudFront 로그에선 `503 Error`(점검 페이지 대체) 로 보인다.

**우리 값 — 실험 명령**

```bash
# 터미널 1: 상태 감시 (5초마다)
TG=$(aws elbv2 describe-target-groups --names mc-tg-web --profile mc-deploy --region ap-northeast-2 --query 'TargetGroups[0].TargetGroupArn' --output text)
while true; do date +%T; aws elbv2 describe-target-health --target-group-arn $TG --profile mc-deploy --region ap-northeast-2 --query 'TargetHealthDescriptions[].[Target.Id,TargetHealth.State,TargetHealth.Reason]' --output text; sleep 5; done

# 터미널 2: web-a 의 Apache 를 60초 멈춤 (Bastion 경유 · 공인 IP 허용 후)
ssh -i infra/terraform-kdt5/.keys/mc-ssh.pem -o ProxyCommand="ssh -i infra/terraform-kdt5/.keys/mc-ssh.pem -W %h:%p ec2-user@52.78.145.87" ec2-user@10.0.10.189 'sudo systemctl stop httpd; sleep 60; sudo systemctl start httpd'

# 터미널 3: 사용자 입장 — 1초마다 상태 코드 (약 30초 동안 절반쯤 503(점검 페이지) 섞이다가 정상)
for i in $(seq 1 90); do curl -s -o /dev/null -w "%{http_code} " -m 5 https://petclinic.mission-critical.site/; sleep 1; done; echo

# 뒤처리 (5분 뒤): ALB 가 스스로 낸 응답 수 · CloudFront 의 503
K=$(aws s3 ls s3://mc-logs-528821350786/alb/public/ --recursive --profile mc-deploy | grep -v TestFile | tail -1 | awk '{print $4}')
aws s3 cp "s3://mc-logs-528821350786/$K" - --profile mc-deploy | zcat | awk '$9 != $10' | wc -l
```

<table header-row="true" fit-page-width="true">
	<tr>
		<td>관찰</td>
		<td>기대</td>
		<td>배우는 것</td>
	</tr>
	<tr>
		<td>unhealthy 까지</td>
		<td>≈30s (`Target.FailedHealthChecks`)</td>
		<td>10s × 3회</td>
	</tr>
	<tr>
		<td>그 사이 사용자</td>
		<td>`200 503 200 200 503 …` 절반쯤 503(점검 페이지)</td>
		<td>라운드 로빈 · 판정 전엔 죽은 서버로도 보냄</td>
	</tr>
	<tr>
		<td>healthy 복귀</td>
		<td>시작 후 ≈20s</td>
		<td>10s × 2회</td>
	</tr>
	<tr>
		<td>알람</td>
		<td>아무것도 안 울림</td>
		<td>WEB 알람 부재 · SNS 구독 0</td>
	</tr>
	<tr>
		<td>로그</td>
		<td>ALB `502 -` 수 건 · CloudFront `503 Error`</td>
		<td>코드 변환(502 → 점검 페이지 503)</td>
	</tr>
</table>
**없으면 · 오해**
- 실험 없이 표만 외우면 "30초" 가 얼마나 긴지 모른다. 한 번 보면 알람·대수 논의가 현실이 된다.
- `systemctl stop` 대신 인스턴스를 **중지**하면 EC2 상태 검사까지 걸려 복구가 느리다. 프로세스만.
- 두 대를 동시에 멈추면 장애 B — 점검 페이지 전면. 실험은 한 대만.

**눈으로 확인** — 위 실험 자체. 실험 전 조건만:

```bash
# Bastion 이 열려 있나 (5초 안에 배너가 오면 OK · timeout 이면 공인 IP 허용 필요)
timeout 5 ssh -i infra/terraform-kdt5/.keys/mc-ssh.pem -o BatchMode=yes ec2-user@52.78.145.87 'hostname' || echo "Bastion 접속 불가 — bastion_allowed_cidrs 에 $(curl -s https://checkip.amazonaws.com)/32 추가 필요(SG 변경 · 명시 지시 후 apply)"
```

기대: `ip-10-0-0-13…` 또는 "접속 불가 — … 추가 필요"
## 2-5. ⑤ 1초 진단과 복구 순서 — 신고 한 통에서 원인까지
**무슨 일이 일어나나**
1. **1초**: 랜딩 `https://petclinic.mission-critical.site/` 를 연다. **200 이면 WEB · ALB · CloudFront 는 살아 있다** → C(WAS) 또는 D(느림). 점검 페이지면 B(WEB 전멸) 또는 ALB/CloudFront 문제. 흰 403 이면 E. 화면이 깨지면 F.
2. **10초**: 대상 상태. `mc-tg-web` healthy 수(2/2?) · `mc-tg-was` healthy 수. 알람 상태.
3. **1분**: ALB 로그 마지막 5분 — `elb / target` 코드 쌍과 `matched_rule_priority`. `503 -` 면 B, `503 503` 이면 C, `502 -` 면 A/keep-alive, `403 -` rule 0 이면 E, 200 인데 사용자는 504 면 D(CloudFront 30s).
4. **5분**: 서버 로그 — `/petclinic/web/error`(httpd) · `/petclinic/was/catalina`(Tomcat 예외) · `/aws/rds/instance/mc-petclinic/slowquery`(느린 쿼리) · `/aws/rds/proxy/mc-rds-proxy`(연결 거부).
5. 복구는 **가장 싼 것부터**: 프로세스 재시작 → 인스턴스 교체(`terraform apply -replace` 한 대씩) → 설정 롤백(tfvars) → 캐시 무효화. 복구 뒤 **같은 순서로 다시 확인**하고 기록(콘솔 가이드 ⑬).

**우리 값 — 진단 순서표**
<table header-row="true" fit-page-width="true">
	<tr>
		<td>순서</td>
		<td>무엇을</td>
		<td>어떻게</td>
		<td>가르는 것</td>
	</tr>
	<tr>
		<td>1초</td>
		<td>랜딩 `/`</td>
		<td>브라우저 · `curl -sI …/`</td>
		<td>200 → WEB 정상(C/D) · 점검 페이지 → B · 403 → E · 깨짐 → F</td>
	</tr>
	<tr>
		<td>10초</td>
		<td>대상 상태 · 알람</td>
		<td>`describe-target-health` (web · was) · `describe-alarms`</td>
		<td>WEB 0/2 → B · WAS 0/2 → C · 전부 정상 → D/E</td>
	</tr>
	<tr>
		<td>1분</td>
		<td>ALB 로그 코드 쌍</td>
		<td>최신 객체 `awk '$9 != $10'` · rule</td>
		<td>`503 -` B · `503 503` C · `502 -` A · `403 -` E · 느린 200 D</td>
	</tr>
	<tr>
		<td>5분</td>
		<td>서버·DB 로그</td>
		<td>`aws logs tail /petclinic/was/catalina` · `…/slowquery` · `…/proxy`</td>
		<td>예외 스택 · 느린 쿼리 · 연결 거부</td>
	</tr>
	<tr>
		<td>복구</td>
		<td>싼 것부터</td>
		<td>재시작 → `-replace` 한 대 → tfvars 롤백 → 무효화</td>
		<td>복구 후 1초 진단부터 재확인</td>
	</tr>
</table>
**없으면 · 오해**
- 순서를 안 정해 두면 장애 때 콘솔을 헤맨다. 다섯 명령을 스크립트 하나(`mc-triage.sh`)로 묶어 두는 게 로드맵.
- "알람이 안 울렸으니 장애 아님" — WEB 알람이 없고 SNS 구독이 0 이다(8단계). 지금은 알람이 침묵해도 장애일 수 있다.
- 복구를 인스턴스 교체부터 하면 원인 로그가 사라진다(로그는 CloudWatch 에 남지만 서버 안 상태는 사라짐). 재시작·로그 확보가 먼저.

**눈으로 확인**

```bash
# 한 번에 도는 진단 5줄 (정상일 때 결과를 기억해 두면 장애 때 차이가 보인다)
curl -s -o /dev/null -w "landing=%{http_code} " https://petclinic.mission-critical.site/; curl -s -o /dev/null -w "app=%{http_code}\n" https://petclinic.mission-critical.site/petclinic/vets
for tg in mc-tg-web mc-tg-was; do A=$(aws elbv2 describe-target-groups --names $tg --profile mc-deploy --region ap-northeast-2 --query 'TargetGroups[0].TargetGroupArn' --output text); printf "%s: " $tg; aws elbv2 describe-target-health --target-group-arn $A --profile mc-deploy --region ap-northeast-2 --query 'TargetHealthDescriptions[].TargetHealth.State' --output text; done
aws cloudwatch describe-alarms --alarm-name-prefix mc- --profile mc-deploy --region ap-northeast-2 --query 'MetricAlarms[].[AlarmName,StateValue]' --output text
K=$(aws s3 ls s3://mc-logs-528821350786/alb/public/ --recursive --profile mc-deploy | grep -v TestFile | tail -1 | awk '{print $4}'); aws s3 cp "s3://mc-logs-528821350786/$K" - --profile mc-deploy | zcat | awk '{print $9, $10}' | sort | uniq -c
aws logs tail /petclinic/was/catalina --since 10m --profile mc-deploy --region ap-northeast-2 --format short | grep -iE "exception|error" | tail -3
```

기대: `landing=200 app=200` · `mc-tg-web: healthy healthy` · `mc-tg-was: healthy healthy` · 알람 OK · `200 200` 다수 · catalina 에 exception 없음
## 2-6. 신고 한 통의 여행 — "점검 페이지가 떠요" 를 받았을 때
<table header-row="true" fit-page-width="true">
	<tr>
		<td>t</td>
		<td>행동</td>
		<td>보이는 것 (예: 장애 C · WAS 죽음)</td>
		<td>판단</td>
	</tr>
	<tr>
		<td>0s</td>
		<td>신고 접수 "점검 페이지"</td>
		<td>—</td>
		<td>502/503/504 중 하나가 오리진에서 났다</td>
	</tr>
	<tr>
		<td>1s</td>
		<td>랜딩 `/` 열기</td>
		<td>**200** (랜딩 정상)</td>
		<td>WEB · ALB · CloudFront 정상 → C 또는 D</td>
	</tr>
	<tr>
		<td>3s</td>
		<td>`/petclinic/vets` 열기</td>
		<td>점검 페이지(503)</td>
		<td>앱 경로만 → WAS 쪽</td>
	</tr>
	<tr>
		<td>10s</td>
		<td>대상 상태 · 알람</td>
		<td>`mc-tg-was` unhealthy 2/2 · `mc-was-unhealthy-host` **ALARM** (구독 0 이라 알림은 없음)</td>
		<td>**C 확정**</td>
	</tr>
	<tr>
		<td>1m</td>
		<td>ALB 로그</td>
		<td>`503 503` (target 이 준 503 = Internal ALB)</td>
		<td>WEB 은 전달만 함 — 재시작 대상 아님</td>
	</tr>
	<tr>
		<td>3m</td>
		<td>`/petclinic/was/catalina` · `/aws/rds/proxy/…`</td>
		<td>예: `Communications link failure` / Proxy `Connections using insecure transport…`</td>
		<td>원인: DB 연결(TLS · 자격 증명 · Proxy)</td>
	</tr>
	<tr>
		<td>5m</td>
		<td>복구</td>
		<td>Tomcat 재시작(was.sh 자동 3회 포함) → healthy 복귀 20s</td>
		<td>랜딩 → 앱 → 대상 → 알람 순서로 재확인</td>
	</tr>
	<tr>
		<td>후속</td>
		<td>기록 · 개선</td>
		<td>SNS 구독 등록 · WEB 알람 추가 · 재발 방지(콘솔 가이드 ⑬ 운영 절)</td>
		<td>—</td>
	</tr>
</table>
기억할 것 셋: **사용자는 항상 점검 페이지를 본다 — 진짜 코드는 로그에** · **랜딩 200 이면 WEB 은 무죄** · **502·503·504 는 각각 끊김·대상 없음·느림** — 그리고 지금은 알람이 울려도 아무도 못 받는다.
# 3. 용어 — 이 단계에서만 쓰는 것
<table header-row="true" fit-page-width="true">
	<tr>
		<td>용어</td>
		<td>한 줄</td>
		<td>비유</td>
	</tr>
	<tr>
		<td>사용자 지정 오류 응답</td>
		<td>CloudFront 가 특정 오류 코드를 다른 페이지·코드로 바꿔 주는 설정</td>
		<td>"공사 중" 안내판</td>
	</tr>
	<tr>
		<td>오류 캐시 TTL</td>
		<td>오류 응답을 얼마나 캐시할지(10s)</td>
		<td>안내판을 몇 초 두나</td>
	</tr>
	<tr>
		<td>오리진 그룹 · 페일오버</td>
		<td>기본 오리진 실패 시 두 번째 오리진으로 같은 요청</td>
		<td>1차 창구 닫히면 2차 창구</td>
	</tr>
	<tr>
		<td>502 · 503 · 504 · 500</td>
		<td>끊김 · 대상 없음 · 느림 · 앱 오류</td>
		<td>전화 끊김 · 받을 사람 없음 · 대답 늦음 · 담당자 실수</td>
	</tr>
	<tr>
		<td>장애 모드</td>
		<td>어떤 부품이 어떻게 죽었을 때 시스템이 보이는 모습</td>
		<td>고장 유형표</td>
	</tr>
	<tr>
		<td>트리아지(triage)</td>
		<td>신고를 받고 원인 범위를 빠르게 좁히는 순서</td>
		<td>응급실 분류</td>
	</tr>
	<tr>
		<td>무효화(invalidation)</td>
		<td>CloudFront 캐시에서 경로를 지워 새로 받게 함</td>
		<td>게시판 옛 공지 떼기</td>
	</tr>
	<tr>
		<td>`-replace`</td>
		<td>Terraform 으로 인스턴스 하나만 새로 만들기</td>
		<td>한 대씩 교체</td>
	</tr>
</table>
# 4. 왜 이렇게 만들었나 (멘토가 물을 만한 것)
- **왜 502·503·504 만 점검 페이지로?** 그 셋은 "지금 서비스가 안 된다" 는 뜻이라 안내가 맞다. 403·404·500 은 각각 거부·없음·앱 오류라 안내로 가리면 오진.
- **왜 오류 캐시가 10초?** 폭주 때 오리진을 보호하되, 복구 뒤 10초면 정상 화면. 길면 복구가 늦어 보인다.
- **왜 정적 경로만 오리진 그룹?** 페일오버는 GET/HEAD 만 되고 POST 를 S3 로 보낼 수 없다. 정적 자원은 S3 사본이 있어 의미 있음.
- **왜 WAS 장애 때 랜딩은 살려 두나?** 얕은 헬스체크(5단계) 덕. 장애 범위를 앱 경로로 국소화해 사용자에게 "일부 점검" 을 준다.
- **왜 장애를 직접 내 보나?** 30초·20초·"알람이 안 울림" 을 몸으로 알아야 알람·대수·ASG 결정이 현실이 된다.
# 5. 다음 단계(10. ASG · AMI) 진입 기준
<details>
<summary>Q1. 사용자가 점검 페이지를 본다. WEB 장애인지 WAS 장애인지 1초 안에 가르는 법은?</summary>
	랜딩 `/` 를 열어 본다. 200 이면 WEB 은 살아 있고 WAS(C) 또는 느림(D), 점검 페이지면 WEB(B) 또는 ALB. 그다음 대상 그룹 상태.
</details>
<details>
<summary>Q2. 403 흰 화면은 왜 점검 페이지로 안 바뀌나?</summary>
	CloudFront 오류 응답이 502·503·504 만 대체하도록 설정돼 있고, 403 은 '요청 거부' 라 점검 안내가 맞지 않는다. 헤더 불일치(E) 나 WAF 차단이면 403 — ALB 로그 `matched_rule_priority 0` 이면 E.
</details>
<details>
<summary>Q3. 한 대 장애 때 사용자가 502/503 을 잠깐이라도 보는 걸 없애려면?</summary>
	헬스체크 간격·임계값을 줄이면(5s · 2회) 제외가 빨라지지만 오탐도 늘어난다. 근본적으로는 대수를 늘리거나(3대면 영향 1/3) ASG 로 자동 교체 + `Restart=always`.
</details>
<details>
<summary>Q4. ALB 로그에 `503 503` 과 `503 -` 는 어떻게 다른가?</summary>
	`503 503` 은 대상(WEB)이 503 을 돌려준 것 = Apache 가 Internal ALB 의 503 을 전달 → WAS 장애(C). `503 -` 는 ALB 가 스스로 낸 것 = 정상 대상 0 → WEB 장애(B).
</details>
# 6. 읽을 자료
- AWS 문서 — *Troubleshoot your Application Load Balancers* (HTTP 502/503/504 원인 표)
- AWS 문서 — *Generating custom error responses* · *Optimizing high availability with CloudFront origin failover*
- 콘솔 구축 가이드 **2-3 오류 응답 · 3-3 점검 페이지 · ⑬ 운영** 절 · 5단계(타임라인) · 8단계(로그 읽기)
<callout icon="🗺️" color="gray_bg">
	**로드맵 위치**: 0 VPC 입구 → 1 HTTP 기초 → 2 TLS 종료 지점 → 3 ALB 해부 → 4 오리진 보호(헤더) → 5 헬스체크 → 6 Apache 프록시 → 7 분산·타임아웃 → 8 WEB 관측 → **9 장애 모드(이 페이지)** → 10 ASG·AMI.
</callout>
