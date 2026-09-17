<callout icon="🔎" color="blue_bg">
	**이 단계의 목표**: ALB 액세스 로그 한 줄을 필드별로 읽고, Apache 로그에서 진짜 클라이언트 IP 를 찾고, CloudWatch 지표 4개로 "ALB 잘못인지 서버 잘못인지" 를 가르는 법. 하루 분량.
</callout>
# 1. ALB 액세스 로그 — 실제 한 줄 (9/17 · S3 `mc-logs/alb/public/`)

```text
https 2026-09-17T02:35:37.491476Z app/mc-alb-public/0780e6e7d84abe76 3.172.65.112:63554 10.0.10.189:80 0.001 0.001 0.000 404 404 889 427 "GET https://petclinic.mission-critical.site:443/favicon.ico HTTP/1.1" "Mozilla/5.0 …" TLS_AES_128_GCM_SHA256 TLSv1.3 arn:…:targetgroup/mc-tg-web/5ae742de9f467369 "Root=1-6aab51f9-…" "petclinic.mission-critical.site" "session-reused" 10 2026-09-17T02:35:37.489000Z "forward" "-" "-" "10.0.10.189:80" "404" "-" "-" TID_… "-" "-" "-" 3.34.116.99 "-" "-"
```

<table header-row="true" fit-page-width="true">
	<tr>
		<td>필드</td>
		<td>값</td>
		<td>뜻</td>
	</tr>
	<tr>
		<td>type</td>
		<td>`https`</td>
		<td>리스너 프로토콜</td>
	</tr>
	<tr>
		<td>client:port</td>
		<td>`3.172.65.112:63554`</td>
		<td>**CloudFront 엣지** IP — 진짜 사용자 IP 는 아님(그건 X-Forwarded-For · Apache 로그)</td>
	</tr>
	<tr>
		<td>target:port</td>
		<td>`10.0.10.189:80`</td>
		<td>**web-a** 가 받았다 (분산 확인은 이 필드)</td>
	</tr>
	<tr>
		<td>request_processing / target_processing / response_processing</td>
		<td>`0.001 0.001 0.000`</td>
		<td>ALB 가 대상에 보내기까지 · **대상이 응답하는 데 걸린 시간** · 응답을 돌려주기까지. 느리면 두 번째 값이 큼</td>
	</tr>
	<tr>
		<td>**elb_status_code** / **target_status_code**</td>
		<td>`404 404`</td>
		<td>ALB 가 사용자에게 준 코드 / 대상이 ALB 에 준 코드. **둘이 다르면 ALB 가 스스로 낸 것**(503 · 504 · 460 · 규칙 403 은 target 이 `-`)</td>
	</tr>
	<tr>
		<td>request</td>
		<td>`GET https://petclinic.mission-critical.site:443/favicon.ico HTTP/1.1`</td>
		<td>favicon 없음 → 404 (정상적인 브라우저 동작 · 나중에 favicon 추가하면 사라짐)</td>
	</tr>
	<tr>
		<td>ssl_cipher · ssl_protocol</td>
		<td>`TLS_AES_128_GCM_SHA256 TLSv1.3`</td>
		<td>2단계의 실물</td>
	</tr>
	<tr>
		<td>trace_id</td>
		<td>`Root=1-6aab51f9-…`</td>
		<td>X-Ray 추적 ID · Apache 로그와 대조 가능</td>
	</tr>
	<tr>
		<td>domain_name</td>
		<td>`petclinic.mission-critical.site`</td>
		<td>SNI 로 요청된 이름</td>
	</tr>
	<tr>
		<td>matched_rule_priority</td>
		<td>`10`</td>
		<td>**규칙 10 이 매치** = 도장 검사 통과(4단계). `0` 이면 기본 작업(403)</td>
	</tr>
	<tr>
		<td>actions_executed</td>
		<td>`forward`</td>
		<td>규칙의 작업</td>
	</tr>
	<tr>
		<td>target_status_code_list</td>
		<td>`"404"`</td>
		<td>재시도 시 여러 개</td>
	</tr>
	<tr>
		<td>(뒤쪽) `3.34.116.99`</td>
		<td></td>
		<td>받은 ALB **노드**의 IP(2c 노드). 0단계의 그 IP</td>
	</tr>
</table>
S3 객체는 5분마다 gzip 으로 생긴다(0바이트 테스트 파일 `ELBAccessLogTestFile` 은 무시). 많이 볼 땐 Athena 로 테이블을 만든다(AWS 문서 예제 그대로 쓰면 됨).
# 2. Apache access_log — 진짜 IP 는 어디에
AL2023 기본 `combined` 형식은 첫 필드가 **연결 상대 IP = ALB 노드 사설 IP**(10.0.0.212 / 10.0.1.212). 사용자 IP 는 `X-Forwarded-For` 헤더 안에 있는데 combined 는 그걸 안 찍는다. 두 가지 방법:

```apache
# 방법 1 — 로그 형식에 XFF 추가 (web.sh 개선 · 로드맵)
LogFormat "%{X-Forwarded-For}i %h %l %u %t \"%r\" %>s %b \"%{Referer}i\" \"%{User-Agent}i\"" combined_xff
CustomLog /var/log/httpd/access_log combined_xff env=!nolog

# 방법 2 — mod_remoteip 로 %h 자체를 XFF 의 값으로 바꿈 (RemoteIPHeader X-Forwarded-For · RemoteIPInternalProxy 10.0.0.0/16)
```

XFF 값 예: `183.98.42.129, 3.172.65.112` — **맨 앞이 사용자**, 그다음이 CloudFront. ALB 는 `xff_header_processing.mode=append` 라 뒤에 덧붙이기만 한다.
# 3. CloudWatch 지표 4개 — ALB 잘못인가 서버 잘못인가
<table header-row="true" fit-page-width="true">
	<tr>
		<td>지표 (AWS/ApplicationELB)</td>
		<td>뜻</td>
		<td>어떻게 읽나</td>
	</tr>
	<tr>
		<td>`HTTPCode_ELB_5XX_Count`</td>
		<td>**ALB 가 만든** 5xx (503 정상 대상 없음 · 504 유휴 초과 · 502 대상 연결 실패)</td>
		<td>이게 오르면 대상 그룹·타임아웃·헬스체크를 본다</td>
	</tr>
	<tr>
		<td>`HTTPCode_Target_5XX_Count`</td>
		<td>**대상이 돌려준** 5xx (Apache/Tomcat 500 · 502)</td>
		<td>이게 오르면 서버 로그(`/mc/web/error` · `/mc/was/catalina`)를 본다</td>
	</tr>
	<tr>
		<td>`TargetResponseTime` (p95)</td>
		<td>대상이 응답하는 데 걸린 시간 분포</td>
		<td>알람 `mc-alb-p95-latency` › 2s 3분 — 로그의 target_processing_time 과 같은 것</td>
	</tr>
	<tr>
		<td>`HealthyHostCount` / `UnHealthyHostCount` (대상 그룹 차원)</td>
		<td>정상/비정상 대상 수</td>
		<td>WEB 은 2/0 이어야. WAS 쪽 `mc-was-unhealthy-host` ≥1 2분 알람</td>
	</tr>
	<tr>
		<td>`RequestCount` · `ActiveConnectionCount`</td>
		<td>부하</td>
		<td>Phase 3 폭주 실험 때 기준선</td>
	</tr>
</table>
실측(9/17 11시, 지난 1시간): `RequestCount 0` · 5XX 없음 → 알람 `mc-alb-p95-latency` 는 데이터가 없어 `INSUFFICIENT_DATA`(정상 · 트래픽이 없는 것뿐).
# 4. 눈으로 확인

```bash
# 1) 최신 ALB 로그 객체 한 줄 (헬스체크 제외)
K=$(aws s3 ls s3://mc-logs-528821350786/alb/public/ --recursive --profile mc-deploy | grep -v TestFile | tail -1 | awk '{print $4}')
aws s3 cp "s3://mc-logs-528821350786/$K" - --profile mc-deploy | zcat | grep -v health.html | tail -3
# 2) elb 코드와 target 코드가 다른 줄만 (ALB 가 스스로 낸 응답)
aws s3 cp "s3://mc-logs-528821350786/$K" - --profile mc-deploy | zcat | awk '$9 != $10'
# 3) 지표 — 지난 1시간 ALB 5XX vs Target 5XX
for m in HTTPCode_ELB_5XX_Count HTTPCode_Target_5XX_Count RequestCount; do echo -n "$m "; aws cloudwatch get-metric-statistics --namespace AWS/ApplicationELB --metric-name $m --dimensions Name=LoadBalancer,Value=app/mc-alb-public/0780e6e7d84abe76 --start-time $(date -u -d '-1 hour' +%FT%TZ) --end-time $(date -u +%FT%TZ) --period 3600 --statistics Sum --profile mc-deploy --region ap-northeast-2 --query 'Datapoints[0].Sum' --output text; done
# 4) Apache 로그는 CloudWatch Logs 에서 (서버 접속 없이)
aws logs tail /mc/web/access --since 1h --profile mc-deploy --region ap-northeast-2 | tail -5
# 5) 알람 상태
aws cloudwatch describe-alarms --alarm-name-prefix mc- --profile mc-deploy --region ap-northeast-2 --query 'MetricAlarms[].[AlarmName,StateValue]' --output table
```

# 5. 다음 단계 진입 기준
<details>
<summary>Q1. 로그 한 줄에서 "ALB 가 직접 낸 응답" 을 어떻게 알아보나?</summary>
	`elb_status_code` 와 `target_status_code` 가 다르거나 target 이 `-`. 규칙 403 · 503 · 504 가 그렇다. matched_rule_priority 가 0 이면 기본 작업.
</details>
<details>
<summary>Q2. Apache access_log 첫 IP 가 10.0.0.212 인 이유와 해결은?</summary>
	ALB 노드 사설 IP 다(연결 상대). 사용자 IP 는 X-Forwarded-For 에 있으니 LogFormat 에 `%｛X-Forwarded-For｝i` 를 넣거나 mod_remoteip 를 쓴다.
</details>
<details>
<summary>Q3. Target_5XX 는 0 인데 ELB_5XX 가 오른다. 어디를 보나?</summary>
	서버는 멀쩡히 응답했다는 뜻. 대상 그룹 정상 대상 수(503), 유휴·응답 시간(504), keep-alive 불일치(502) — 5·7단계 항목.
</details>
# 6. 읽을 자료
- AWS 문서 — *Access logs for your Application Load Balancer* (필드 표 · Athena 예제)
- AWS 문서 — *CloudWatch metrics for your Application Load Balancer*
- Apache 문서 — *mod_log_config* (`%｛header｝i`) · *mod_remoteip*
- 🗂️ CloudWatch Logs 총정리 · 로그 흐름 도면(`docs/architecture-log-flow.png`)
<callout icon="🗺️" color="gray_bg">
	**로드맵 위치**: 0 VPC 입구 → 1 HTTP 기초 → 2 TLS 종료 지점 → 3 ALB 해부 → 4 오리진 보호(헤더) → 5 헬스체크 → 6 Apache 프록시 → 7 분산·타임아웃 → **8 WEB 관측(이 페이지)** → 9 장애 모드 → 10 ASG·AMI.
</callout>