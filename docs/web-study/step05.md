<callout icon="🩺" color="blue_bg">
	**이 단계의 목표**: ALB 가 "이 서버 살아있나" 를 판단하는 방식과, WEB 은 얕게·WAS 는 깊게 보는 이유, 10s·5s·2/3·30s 가 실제로 몇 초를 뜻하는지. 반나절 분량.
</callout>
# 0. 두 대상 그룹의 헬스체크 비교
<table header-row="true" fit-page-width="true">
	<tr>
		<td></td>
		<td>mc-tg-web (WEB)</td>
		<td>mc-tg-was (WAS)</td>
	</tr>
	<tr>
		<td>경로</td>
		<td>`/health.html` — Apache 가 직접 주는 정적 파일 `ok`</td>
		<td>`/petclinic/` — Tomcat 의 앱 홈(Spring 컨텍스트가 떠야 200)</td>
	</tr>
	<tr>
		<td>무엇을 증명</td>
		<td>**Apache 프로세스가 살아 요청을 받는다** (얕게)</td>
		<td>**Tomcat + 앱 + (초기화 시) DB** 까지 정상 (깊게)</td>
	</tr>
	<tr>
		<td>간격 · 타임아웃</td>
		<td>10s · 5s</td>
		<td>10s · 5s</td>
	</tr>
	<tr>
		<td>정상 / 비정상 임계값</td>
		<td>2 / 3</td>
		<td>2 / 3</td>
	</tr>
	<tr>
		<td>등록 취소 지연</td>
		<td>30s</td>
		<td>30s</td>
	</tr>
	<tr>
		<td>성공 코드</td>
		<td>200</td>
		<td>200 (슬래시 없으면 301 이라 실패 — 경로에 `/` 필수)</td>
	</tr>
</table>
# 1. 왜 WEB 은 얕게 보나
WEB 헬스체크를 `/petclinic/`(프록시 경유) 로 하면 **WAS 가 죽었을 때 WEB 까지 unhealthy** 가 된다. 그러면 ALB 는 보낼 곳이 없어 503 — 사실 Apache 는 멀쩡해서 랜딩 `/` 와 점검 안내는 줄 수 있는데도. 계층마다 **자기 계층만** 검사하고, WAS 장애는 Internal ALB 의 헬스체크 + `mc-was-unhealthy-host` 알람이 잡는다. `SetEnvIf … nolog` 로 헬스체크 요청은 access_log 에서 뺀다(10초마다 두 노드가 찍으면 로그가 헬스체크로 가득 참).
# 2. 숫자를 시간으로 번역
<table header-row="true" fit-page-width="true">
	<tr>
		<td>설정</td>
		<td>뜻</td>
		<td>실제 시간</td>
	</tr>
	<tr>
		<td>간격 10s</td>
		<td>노드마다 10초에 한 번 GET</td>
		<td>ALB 노드가 2개라 서버 입장에선 ~5초에 한 번 요청이 옴</td>
	</tr>
	<tr>
		<td>타임아웃 5s</td>
		<td>5초 안에 200 이 안 오면 그 회차 실패</td>
		<td>—</td>
	</tr>
	<tr>
		<td>비정상 임계값 3</td>
		<td>연속 3회 실패해야 unhealthy</td>
		<td>장애 발생 → 제외까지 **최대 약 30초**(10s×3) + 타임아웃</td>
	</tr>
	<tr>
		<td>정상 임계값 2</td>
		<td>연속 2회 성공해야 다시 healthy</td>
		<td>복구 → 재투입까지 **약 20초**</td>
	</tr>
	<tr>
		<td>등록 취소 지연 30s</td>
		<td>대상을 뺄 때(교체·축소) 진행 중인 요청을 30초 기다려 줌(draining)</td>
		<td>롤링 교체 때 끊김 없이. 새 요청은 즉시 안 감</td>
	</tr>
</table>
9/16 저녁 롤링 교체 실측: 새 인스턴스가 healthy 되기까지 WEB ≈ 2분(Apache 설치 + index 복사), WAS ≈ 6분(Tomcat 다운로드 + Maven 빌드 + Proxy 로그인 대기). 그래서 ASG 를 켤 때 `health_check_grace_period` 를 WEB 300s · WAS 900s 로 잡아 두었다(10단계).
# 3. 헬스체크가 실패하면 실제로 무슨 일이
1. 대상 상태 `unhealthy` → 대상 그룹이 그 서버로 **새 요청을 안 보냄**(진행 중인 건 끝까지)
2. 정상 대상이 하나라도 남으면 사용자는 모름(다른 서버가 받음)
3. 정상 대상이 **0** 이면 ALB 가 **503** → CloudFront 가 `/maintenance.html` 을 503 으로 보여줌(9단계)
4. 지표 `UnHealthyHostCount` 가 오르고, WAS 쪽은 알람 `mc-was-unhealthy-host`(≥1, 2분) → SNS
# 4. 눈으로 확인

```bash
TG=$(aws elbv2 describe-target-groups --names mc-tg-web --profile mc-deploy --query 'TargetGroups[0].TargetGroupArn' --output text)
# 1) 헬스체크 설정
aws elbv2 describe-target-groups --target-group-arns $TG --profile mc-deploy --query 'TargetGroups[0].[HealthCheckPath,HealthCheckIntervalSeconds,HealthCheckTimeoutSeconds,HealthyThresholdCount,UnhealthyThresholdCount,Matcher.HttpCode]' --output table
# 2) 현재 상태 + 이유
aws elbv2 describe-target-health --target-group-arn $TG --profile mc-deploy --query 'TargetHealthDescriptions[].[Target.Id,TargetHealth.State,TargetHealth.Reason]' --output table
# 3) WEB 의 헬스체크 파일 (Bastion 경유)
ssh -i infra/terraform-kdt5/.keys/mc-ssh.pem -J ec2-user@52.78.145.87 ec2-user@10.0.10.189 'curl -si http://localhost/health.html | head -1; cat /var/www/html/health.html'
# 4) 실험(선택): web-a 의 httpd 를 40초 멈추고 상태 변화 관찰 → 30초쯤 뒤 unhealthy, 켜면 20초 뒤 healthy
#   sudo systemctl stop httpd; sleep 40; sudo systemctl start httpd  (다른 터미널에서 2) 를 5초마다 반복)
```

# 5. 다음 단계 진입 기준
<details>
<summary>Q1. WEB 헬스체크를 `/petclinic/` 로 바꾸면 어떤 장애 때 손해인가?</summary>
	WAS 만 죽었을 때. Apache 는 살아있는데도 WEB 2대가 전부 unhealthy 로 빠져 503 이 된다. 얕은 체크면 WEB 은 남아 랜딩·점검 안내가 가능.
</details>
<details>
<summary>Q2. 서버가 죽고 사용자가 영향을 받을 수 있는 최대 시간은?</summary>
	약 30초(10s 간격 × 비정상 3회) — 그동안 라운드로빈으로 그 서버에 간 요청은 실패(502/504). 두 대라 절반의 요청.
</details>
<details>
<summary>Q3. 등록 취소 지연 30초는 언제 쓰이나?</summary>
	인스턴스 교체·축소로 대상을 뺄 때. 새 요청은 즉시 안 보내고 진행 중인 요청만 30초까지 마무리시킨다(연결 드레이닝).
</details>
# 6. 읽을 자료
- AWS 문서 — *Health checks for your target groups*
- AWS 문서 — *Deregistration delay*
- 콘솔 구축 가이드 **4-2 · ⑥** 절
<callout icon="🗺️" color="gray_bg">
	**로드맵 위치**: 0 VPC 입구 → 1 HTTP 기초 → 2 TLS 종료 지점 → 3 ALB 해부 → 4 오리진 보호(헤더) → **5 헬스체크(이 페이지)** → 6 Apache 프록시 → 7 분산·타임아웃 → 8 WEB 관측 → 9 장애 모드 → 10 ASG·AMI.
</callout>