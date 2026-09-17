<callout icon="🚨" color="blue_bg">
	**이 단계의 목표**: WEB 구간에서 날 수 있는 장애를 상태 코드로 분류하고, 각 경우에 사용자 화면·로그·지표가 어떻게 되는지 미리 안다. 그리고 직접 하나 내 본다. 하루 분량.
</callout>
# 1. 장애 6가지
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
		<td>약 30초간 그 서버로 간 요청 → ALB **502**(연결 거부). 이후 unhealthy 로 제외되면 정상</td>
		<td>잠깐 502 또는 점검 페이지 → 곧 정상(다른 서버)</td>
		<td>`UnHealthyHostCount 1` · ELB_5XX 소량 · ALB 로그 target `-`</td>
		<td>자동(헬스체크). 서버는 `systemctl restart httpd` 또는 교체</td>
	</tr>
	<tr>
		<td>B</td>
		<td>WEB 2대 모두 죽음</td>
		<td>정상 대상 0 → ALB **503** → CloudFront 가 `/maintenance.html` 을 **503** 으로</td>
		<td>**점검 페이지**</td>
		<td>`HealthyHostCount 0` · ELB_5XX 급증 · WAF·CloudFront 로그는 정상</td>
		<td>교체(Terraform `-replace`) · ASG 였다면 자동</td>
	</tr>
	<tr>
		<td>C</td>
		<td>WAS 죽음 (WEB 정상)</td>
		<td>Apache 가 Internal ALB 에서 503 을 받아 그대로 → 사용자 **503** → CloudFront 점검 페이지. 단 `/`·`/static` 은 200</td>
		<td>앱 경로만 점검 페이지, 랜딩은 정상</td>
		<td>`mc-was-unhealthy-host` 알람 · Target_5XX(WEB 대상이 503 을 돌려줌)</td>
		<td>WAS 재시작 · Tomcat 404 면 was.sh 의 자동 재시작 3회</td>
	</tr>
	<tr>
		<td>D</td>
		<td>느린 응답 (DB 잠금 · GC)</td>
		<td>30초 넘으면 CloudFront **504** · 60초 넘으면 ALB **504**</td>
		<td>점검 페이지 (원인은 DB 인데 화면은 WEB 장애처럼 보임)</td>
		<td>`TargetResponseTime p95` 알람 · RDS `slowquery` 로그(9/17 켬)</td>
		<td>쿼리·풀 확인. 7단계 타임아웃 표</td>
	</tr>
	<tr>
		<td>E</td>
		<td>도장(헤더) 불일치 (배포 교체 중 값 어긋남)</td>
		<td>ALB 규칙 미매치 → **403** 고정 응답</td>
		<td>403 Forbidden 흰 화면 (점검 페이지 아님 — 4xx 는 오류 응답 대상이 아님)</td>
		<td>ALB 로그 `matched_rule_priority 0` · elb 403 · target `-`</td>
		<td>tfvars 값 일치시켜 apply</td>
	</tr>
	<tr>
		<td>F</td>
		<td>CloudFront 캐시가 옛 css</td>
		<td>장애는 아니지만 "화면이 깨짐" 신고</td>
		<td>레이아웃 깨짐</td>
		<td>x-cache: Hit</td>
		<td>무효화 `/static/*` `/images/*` `/petclinic/resources/*`</td>
	</tr>
</table>
# 2. 점검 페이지가 뜨는 조건 (정확히)
CloudFront 사용자 지정 오류 응답: 오리진(ALB)이 **502 · 503 · 504** 를 주면 `/maintenance.html` 을 **503** 으로 대체, 10초 캐시. 오리진 그룹 failover 도 500·502·503·504 에서 S3 로 넘어감(GET 만). **403·404·500 은 그대로** 사용자에게 간다 — 그래서 E 는 흰 403.
# 3. 직접 내 보기 — 장애 A (안전 · 30초 · 서비스 유지)

```bash
# 터미널 1: 상태 감시 (5초마다)
TG=$(aws elbv2 describe-target-groups --names mc-tg-web --profile mc-deploy --query 'TargetGroups[0].TargetGroupArn' --output text)
while true; do date +%T; aws elbv2 describe-target-health --target-group-arn $TG --profile mc-deploy --query 'TargetHealthDescriptions[].[Target.Id,TargetHealth.State]' --output text; sleep 5; done

# 터미널 2: web-a 의 Apache 를 60초 멈춤 (Bastion 경유)
ssh -i infra/terraform-kdt5/.keys/mc-ssh.pem -J ec2-user@52.78.145.87 ec2-user@10.0.10.189 'sudo systemctl stop httpd; sleep 60; sudo systemctl start httpd'

# 터미널 3: 사용자 입장 — 1초마다 상태 코드 (약 30초 동안 절반쯤 502/503 섞이다가 정상)
for i in $(seq 1 90); do curl -s -o /dev/null -w "%{http_code} " -m 5 https://petclinic.mission-critical.site/; sleep 1; done; echo

# 뒤처리: 5분 뒤 ALB 로그에서 elb 코드 != target 코드 줄 확인 (8단계 2번)
```

관찰 포인트: (1) 정지 후 몇 초 만에 unhealthy 로 바뀌나(기대 ≈ 30s) (2) 그 사이 사용자 코드에 502 가 몇 개 섞이나 (3) 시작 후 healthy 복귀까지(기대 ≈ 20s) (4) 알람은 WEB 엔 없다 — WAS 만 있음 → WEB 용 `HealthyHostCount ‹ 2` 알람 추가가 로드맵.
# 4. 눈으로 확인 (실험 없이)

```bash
# 1) CloudFront 오류 응답 설정 — 502/503/504 → /maintenance.html 503
aws cloudfront get-distribution-config --id E2PWXW3LUYTDEE --profile mc-deploy --query 'DistributionConfig.CustomErrorResponses.Items[].[ErrorCode,ResponseCode,ResponsePagePath,ErrorCachingMinTTL]' --output table
# 2) 점검 페이지 자체는 지금도 열린다
curl -sI https://petclinic.mission-critical.site/maintenance.html | head -1
# 3) 지난 24시간 ALB 5XX (0 이어야)
aws cloudwatch get-metric-statistics --namespace AWS/ApplicationELB --metric-name HTTPCode_ELB_5XX_Count --dimensions Name=LoadBalancer,Value=app/mc-alb-public/0780e6e7d84abe76 --start-time $(date -u -d '-24 hour' +%FT%TZ) --end-time $(date -u +%FT%TZ) --period 86400 --statistics Sum --profile mc-deploy --region ap-northeast-2 --query 'Datapoints[0].Sum'
```

# 5. 다음 단계 진입 기준
<details>
<summary>Q1. 사용자가 점검 페이지를 본다. WEB 장애인지 WAS 장애인지 1초 안에 가르는 법은?</summary>
	랜딩 `/` 를 열어 본다. 200 이면 WEB 은 살아있고 WAS(C) 문제, 점검 페이지면 WEB(B) 또는 ALB. 그다음 대상 그룹 상태.
</details>
<details>
<summary>Q2. 403 흰 화면은 왜 점검 페이지로 안 바뀌나?</summary>
	CloudFront 오류 응답이 502·503·504 만 대체하도록 설정돼 있고, 403 은 '요청 거부' 라 점검 안내가 맞지 않는다. 헤더 불일치(E) 나 WAF 차단이면 403.
</details>
<details>
<summary>Q3. 한 대 장애 때 사용자가 502 를 잠깐이라도 보는 걸 없애려면?</summary>
	헬스체크 간격·임계값을 줄이면(5s · 2회) 제외가 빨라지지만 오탐도 늘어난다. 근본적으로는 대수를 늘리거나(3대면 영향 1/3) ASG 로 자동 교체 + Apache 를 systemd `Restart=always` 로.
</details>
# 6. 읽을 자료
- AWS 문서 — *Troubleshoot your Application Load Balancers* (HTTP 502/503/504 원인 표)
- AWS 문서 — *Generating custom error responses* (CloudFront)
- 콘솔 구축 가이드 **2-3 오류 응답 · 3-3 점검 페이지**
<callout icon="🗺️" color="gray_bg">
	**로드맵 위치**: 0 VPC 입구 → 1 HTTP 기초 → 2 TLS 종료 지점 → 3 ALB 해부 → 4 오리진 보호(헤더) → 5 헬스체크 → 6 Apache 프록시 → 7 분산·타임아웃 → 8 WEB 관측 → **9 장애 모드(이 페이지)** → 10 ASG·AMI.
</callout>