<callout icon="🧩" color="blue_bg">
	**이 단계의 목표**: ALB 를 부품 4개(리스너 · 규칙 · 대상 그룹 · 대상)로 분해해서, 요청 하나가 어느 부품을 어떤 순서로 지나는지 콘솔 화면과 1:1 로 맞춘다. 하루 분량.
</callout>
# 0. 그림 한 장

```text
                 ┌─ 리스너 443 (TLS 풀기 · 보안 정책) ─────────────────────────────┐
요청 ──▶ [SG] ──▶ │  규칙 10: 헤더 X-Origin-Verify == 비밀값 ?  → forward mc-tg-web │ ──▶ 대상 그룹 mc-tg-web ──▶ 대상 i-01a1…(web-a) :80
                 │  기본 작업: fixed-response 403                                  │        (헬스체크 · 알고리즘)   대상 i-01d1…(web-c) :80
                 └───────────────────────────────────────────────────────────────┘
```

# 1. 부품 4개
<table header-row="true" fit-page-width="true">
	<tr>
		<td>부품</td>
		<td>하는 일</td>
		<td>우리 값 (실측)</td>
		<td>콘솔 위치</td>
	</tr>
	<tr>
		<td>**로드 밸런서**</td>
		<td>노드가 있는 서브넷·SG·속성(유휴 시간 등)을 가진 껍데기</td>
		<td>`mc-alb-public` · internet-facing · 서브넷 mc-public-a/c · SG mc-sg-alb-public · 유휴 60s · 교차 영역 on</td>
		<td>EC2 → 로드 밸런서</td>
	</tr>
	<tr>
		<td>**리스너**</td>
		<td>"이 포트·프로토콜로 오는 연결을 받는다" + TLS 종료 + 규칙 목록</td>
		<td>**443 HTTPS 하나뿐**(80 없음) · 정책 TLS13-1-2-2021-06 · 인증서 B</td>
		<td>로드 밸런서 → 리스너 및 규칙 탭</td>
	</tr>
	<tr>
		<td>**규칙**</td>
		<td>조건(경로·헤더·호스트·쿼리·IP…)이 맞으면 작업(forward · redirect · fixed-response · authenticate). **우선순위 숫자가 작은 것부터**, 맨 마지막이 **기본 작업**</td>
		<td>우선순위 **10**: `http-header X-Origin-Verify` 일치 → **forward mc-tg-web** · **기본**: fixed-response **403** `Forbidden`</td>
		<td>리스너 → 규칙 보기/편집</td>
	</tr>
	<tr>
		<td>**대상 그룹**</td>
		<td>보낼 서버들의 명단 + 포트 + 헬스체크 + 분산 알고리즘</td>
		<td>`mc-tg-web` · 인스턴스 · HTTP **80** · HTTP/1.1 · 헬스체크 `/health.html` 10s/5s/2/3 · 등록 취소 30s · **round_robin** · 스티키 off · slow start 0</td>
		<td>EC2 → 대상 그룹</td>
	</tr>
	<tr>
		<td>**대상**</td>
		<td>명단에 등록된 실제 서버 + 상태</td>
		<td>`i-01a195cff8acb28d8`(web-a) · `i-01d1734d081d8bc57`(web-c) 둘 다 **healthy**</td>
		<td>대상 그룹 → 대상 탭</td>
	</tr>
</table>
# 2. 규칙 평가 — 위에서 아래로, 첫 매치에서 끝
<table header-row="true" fit-page-width="true">
	<tr>
		<td>순서</td>
		<td>규칙</td>
		<td>조건</td>
		<td>결과</td>
	</tr>
	<tr>
		<td>1</td>
		<td>우선순위 10</td>
		<td>요청 헤더 `X-Origin-Verify` 값이 우리 비밀값과 같다</td>
		<td>`mc-tg-web` 로 전달(forward). 여기서 끝 — 아래는 안 봄</td>
	</tr>
	<tr>
		<td>2</td>
		<td>기본(default)</td>
		<td>위에서 아무것도 안 맞음</td>
		<td>**403** 고정 응답. 대상에 닿지 않음</td>
	</tr>
</table>
조건 유형 중 우리가 쓰는 건 `http-header` 하나. 경로 기반(`/api/*` → 다른 대상 그룹)이나 호스트 기반(도메인별) 분기도 같은 자리에서 한다 — WAS 를 API 서버와 나누게 되면 여기에 규칙이 늘어난다.
# 3. 대상 그룹이 하는 두 가지 일
- **누구에게 보낼지**: `round_robin` — 정상 대상에 번갈아. `교차 영역 on` 이라 2a 노드가 2c 서버로도 보낸다(AZ 균등).
- **누가 정상인지**: 10초마다 `/health.html` 을 GET, 5초 안에 200 이면 성공. 2번 연속 성공 → healthy, 3번 연속 실패 → unhealthy(5단계).
# 4. 요청 하나 따라가기 — `GET /petclinic/vets`
1. CloudFront 가 ALB 노드(0단계)로 HTTPS 연결 · 헤더에 `X-Origin-Verify` 를 붙여 보냄
2. 리스너 443 이 TLS 를 풀고(2단계) 규칙 평가 시작
3. 규칙 10 매치 → 대상 그룹 `mc-tg-web`
4. 대상 그룹이 healthy 인 web-a/web-c 중 하나를 라운드로빈으로 선택, `10.0.10.189:80` 으로 평문 전달 · `X-Forwarded-For/Proto/Port` 헤더 추가
5. Apache 응답 → ALB → CloudFront → 브라우저
# 5. 눈으로 확인

```bash
ALB=$(aws elbv2 describe-load-balancers --names mc-alb-public --profile mc-deploy --query 'LoadBalancers[0].LoadBalancerArn' --output text)
# 1) 리스너 — 443 하나, 기본 작업 403
aws elbv2 describe-listeners --load-balancer-arn $ALB --profile mc-deploy --query 'Listeners[].[Port,Protocol,DefaultActions[0].Type,DefaultActions[0].FixedResponseConfig.StatusCode]' --output table
# 2) 규칙 — 우선순위 10 헤더 조건 → forward, default → fixed-response
L=$(aws elbv2 describe-listeners --load-balancer-arn $ALB --profile mc-deploy --query 'Listeners[0].ListenerArn' --output text)
aws elbv2 describe-rules --listener-arn $L --profile mc-deploy --query 'Rules[].[Priority,Conditions[0].Field,Conditions[0].HttpHeaderConfig.HttpHeaderName,Actions[0].Type]' --output table
# 3) 대상 그룹 속성 — 알고리즘 · 등록 취소 · 스티키
TG=$(aws elbv2 describe-target-groups --names mc-tg-web --profile mc-deploy --query 'TargetGroups[0].TargetGroupArn' --output text)
aws elbv2 describe-target-group-attributes --target-group-arn $TG --profile mc-deploy --query 'Attributes[].[Key,Value]' --output table
# 4) 대상과 상태
aws elbv2 describe-target-health --target-group-arn $TG --profile mc-deploy --query 'TargetHealthDescriptions[].[Target.Id,Target.Port,TargetHealth.State]' --output table
```

<table header-row="true" fit-page-width="true">
	<tr>
		<td>확인</td>
		<td>기대 결과</td>
		<td>배우는 것</td>
	</tr>
	<tr>
		<td>1</td>
		<td>`443 HTTPS fixed-response 403`</td>
		<td>80 리스너가 없다 · 기본은 거부</td>
	</tr>
	<tr>
		<td>2</td>
		<td>`10 http-header X-Origin-Verify forward` · `default … fixed-response`</td>
		<td>규칙은 딱 하나, 나머지는 403</td>
	</tr>
	<tr>
		<td>3</td>
		<td>`load_balancing.algorithm.type round_robin` · `deregistration_delay 30` · `stickiness.enabled false`</td>
		<td>무상태 앱이라 스티키 불필요</td>
	</tr>
	<tr>
		<td>4</td>
		<td>두 인스턴스 `healthy`</td>
		<td>대상 = 실제 EC2, 상태는 헬스체크 결과</td>
	</tr>
</table>
# 6. 다음 단계 진입 기준
<details>
<summary>Q1. 규칙 10 을 지우면 무슨 일이 생기나?</summary>
	모든 요청이 기본 작업 403 으로 떨어진다 — CloudFront 를 거친 정상 요청도. 사이트 전체가 403.
</details>
<details>
<summary>Q2. 80 리스너를 추가하고 tg-web 으로 forward 하면?</summary>
	ALB DNS 로 http 직접 접근이 열려 CloudFront·WAF 를 우회하는 길이 생긴다(4단계). 그래서 없앴다(`public_http_listener=false`).
</details>
<details>
<summary>Q3. 대상 그룹의 포트 80 과 리스너 443 이 다른데 어떻게 되나?</summary>
	리스너는 뷰어(CloudFront) 쪽 포트, 대상 그룹 포트는 서버 쪽 포트. ALB 가 중간에서 443 → 80 으로 바꿔 보낸다(TLS 종료 = 2단계).
</details>
# 7. 읽을 자료
- AWS 문서 — *Listener rules for your Application Load Balancer* (조건·작업 유형 표)
- AWS 문서 — *Target groups for your Application Load Balancers* (알고리즘 · 속성)
- 콘솔 구축 가이드 **4-2 · 4-3** 절
<callout icon="🗺️" color="gray_bg">
	**로드맵 위치**: 0 VPC 입구 → 1 HTTP 기초 → 2 TLS 종료 지점 → **3 ALB 해부(이 페이지)** → 4 오리진 보호(헤더) → 5 헬스체크 → 6 Apache 프록시 → 7 분산·타임아웃 → 8 WEB 관측 → 9 장애 모드 → 10 ASG·AMI.
</callout>