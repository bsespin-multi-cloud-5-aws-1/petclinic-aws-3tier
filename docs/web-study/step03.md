<callout icon="🧩" color="blue_bg">
	**이 단계의 목표**: ALB 를 부품 다섯 개(로드 밸런서 · 리스너 · 규칙 · 대상 그룹 · 대상)로 분해해서, 요청 하나가 어느 부품을 어떤 순서로 지나는지 콘솔 화면과 1:1 로 맞춘다. 하루 분량. 값은 전부 2026-09-17 mc-deploy 실측.
</callout>
# 0. 그림 한 장

```text
                  ① 로드 밸런서 mc-alb-public (노드 2개 · SG · 속성: 유휴 60 · 교차 영역 on)
                  ┌─ ② 리스너 443 HTTPS (인증서 B · 정책 TLS13-1-2) ───────────────────────────────┐
요청 ──▶ [SG] ──▶ │  ③ 규칙 10: http-header X-Origin-Verify == 비밀값 ?  → forward mc-tg-web         │──▶ ④ 대상 그룹 mc-tg-web ──▶ ⑤ 대상 web-a 10.0.10.189:80 (healthy)
                  │  ③ 기본 작업: fixed-response 403                                                │      HTTP 80 · /health.html   ⑤ 대상 web-c 10.0.11.89:80 (healthy)
                  └─────────────────────────────────────────────────────────────────────────────────┘      round_robin · 등록 취소 30s
```

콘솔 지도: EC2 → **로드 밸런서**(①) → 리스너 및 규칙 탭(②③) / EC2 → **대상 그룹**(④) → 대상 탭(⑤). 부품은 따로 만들고 서로 **참조**로 이어진다 — 그래서 대상 그룹을 여러 리스너가 공유할 수도 있다.
# 1. 딱 필요한 다섯 가지 — 한 표
<table header-row="true" fit-page-width="true">
	<tr>
		<td>#</td>
		<td>부품</td>
		<td>하는 일</td>
		<td>우리 값 (실측)</td>
	</tr>
	<tr>
		<td>①</td>
		<td>**로드 밸런서**</td>
		<td>노드가 사는 서브넷 · SG · 속성(유휴 시간 · 교차 영역 · 로그)을 가진 껍데기. IP 는 노드가 갖고 이름은 껍데기가 갖는다</td>
		<td>`mc-alb-public` · internet-facing · 서브넷 mc-public-a/c · SG `mc-sg-alb-public` · 유휴 **60s** · 교차 영역 on · http2 on · 액세스 로그 → `s3://mc-logs/alb/public/`</td>
	</tr>
	<tr>
		<td>②</td>
		<td>**리스너**</td>
		<td>"이 포트·프로토콜로 오는 연결을 받는다" + TLS 종료 + 규칙 목록의 주인</td>
		<td>**443 HTTPS 하나뿐**(80 없음) · 정책 `ELBSecurityPolicy-TLS13-1-2-2021-06` · 인증서 B(서울)</td>
	</tr>
	<tr>
		<td>③</td>
		<td>**규칙**</td>
		<td>조건(경로 · 헤더 · 호스트 · 쿼리 · 소스 IP …)이 맞으면 작업(forward · redirect · fixed-response · authenticate). **우선순위 작은 수부터 · 첫 매치에서 끝** · 맨 마지막이 기본 작업</td>
		<td>우선순위 **10**: `http-header X-Origin-Verify` 일치 → **forward mc-tg-web** / **기본**: fixed-response **403**</td>
	</tr>
	<tr>
		<td>④</td>
		<td>**대상 그룹**</td>
		<td>보낼 서버들의 명단 + 서버 쪽 포트·프로토콜 + 헬스체크 + 분산 알고리즘 + 등록 취소 지연</td>
		<td>`mc-tg-web` · instance · HTTP **80** · HTTP/1.1 · 헬스체크 `/health.html` 10s/5s/2/3 · `round_robin` · 스티키 off · slow start 0 · 등록 취소 30s</td>
	</tr>
	<tr>
		<td>⑤</td>
		<td>**대상**</td>
		<td>명단에 등록된 실제 서버 + 포트 + 현재 상태(healthy/unhealthy/draining …)</td>
		<td>`i-01a195cff8acb28d8`(web-a · 10.0.10.189:80) · `i-01d1734d081d8bc57`(web-c · 10.0.11.89:80) — 둘 다 **healthy**</td>
	</tr>
</table>
# 2. 자세히 — 부품마다 "무슨 일 · 우리 값 · 없으면 · 눈으로 확인"
## 2-1. ① 로드 밸런서 — 껍데기와 노드
**무슨 일이 일어나나**
1. "로드 밸런서" 리소스 자체는 **설정의 묶음**이다: 어느 VPC · 어느 서브넷(=어느 AZ에 노드를 둘지) · 어느 SG · 스킴(internet-facing/internal) · 속성. 실제로 패킷을 받는 건 서브넷마다 생기는 **노드(ENI)** 다(0단계).
2. DNS 이름 `mc-alb-public-485062926.ap-northeast-2.elb.amazonaws.com` 은 껍데기의 것이고, 답으로 나오는 IP 는 노드의 것. 노드가 늘거나 바뀌어도 이름은 그대로.
3. 속성은 "모든 리스너·대상 그룹에 공통" 인 것들: 유휴 타임아웃(60s) · 교차 영역 분산(on) · HTTP/2(뷰어 쪽) · XFF 처리(append) · 액세스 로그(S3) · 잘못된 헤더 삭제(off).
4. 우리는 ALB 가 **두 대**다: 퍼블릭(`mc-alb-public`, CloudFront→WEB)과 내부(`mc-alb-internal`, Apache→WAS). 내부 ALB 는 WAS 서브넷에 노드가 있고 공인 IP 가 없다 — 구조는 같고 스킴만 다르다.

**우리 값**
<table header-row="true" fit-page-width="true">
	<tr>
		<td>항목</td>
		<td>mc-alb-public</td>
		<td>mc-alb-internal (비교)</td>
	</tr>
	<tr>
		<td>스킴 · 유형</td>
		<td>internet-facing · application · ipv4</td>
		<td>internal · application</td>
	</tr>
	<tr>
		<td>서브넷(노드 위치)</td>
		<td>mc-public-a `10.0.0.212` · mc-public-c `10.0.1.212`(공인 13.124.71.239 · 3.34.116.99)</td>
		<td>mc-was-a · mc-was-c (노드 예: `10.0.20.193` · `10.0.21.43` — WAS 로그의 첫 IP)</td>
	</tr>
	<tr>
		<td>SG</td>
		<td>`sg-0cd291c8a096146ea` (443 ← CloudFront 접두사 목록)</td>
		<td>`sg-018270d76f4c564f7` (8080 ← WEB SG)</td>
	</tr>
	<tr>
		<td>속성</td>
		<td>유휴 60 · 교차 영역 on · http2 true · xff append · drop_invalid_header false</td>
		<td>유휴 60</td>
	</tr>
	<tr>
		<td>로그 · 지표 차원</td>
		<td>`s3://mc-logs-528821350786/alb/public/` · `app/mc-alb-public/0780e6e7d84abe76`</td>
		<td>`app/mc-alb-internal/c3a94be66e75b453`</td>
	</tr>
</table>
**없으면 · 오해**
- 서브넷을 하나만 고르면 만들 수 없다(ALB 는 AZ 2개 이상 필수). AZ 하나가 죽어도 다른 노드가 받는 게 설계 목적.
- "로드 밸런서를 지우면 대상 그룹도 지워진다" — 아니다. 대상 그룹은 별개 리소스라 남는다(반대로 리스너·규칙은 로드 밸런서에 딸려 사라짐).
- 속성 유휴 60 은 **모든** 연결(뷰어 쪽·대상 쪽)에 적용된다. 리스너나 대상 그룹별로 다르게 둘 수 없다.

**눈으로 확인**

```bash
ALB=$(aws elbv2 describe-load-balancers --names mc-alb-public --profile mc-deploy --region ap-northeast-2 --query 'LoadBalancers[0].LoadBalancerArn' --output text)
# 1) 껍데기 — 스킴 · VPC · 서브넷(AZ) · SG · DNS 이름
aws elbv2 describe-load-balancers --names mc-alb-public --profile mc-deploy --region ap-northeast-2 --query 'LoadBalancers[0].[Scheme,Type,VpcId,DNSName,AvailabilityZones[].SubnetId,SecurityGroups]' --output json
# 2) 속성 전부
aws elbv2 describe-load-balancer-attributes --load-balancer-arn $ALB --profile mc-deploy --region ap-northeast-2 --query 'Attributes[].[Key,Value]' --output table
# 3) 두 대의 ALB 한눈에
aws elbv2 describe-load-balancers --profile mc-deploy --region ap-northeast-2 --query 'LoadBalancers[].[LoadBalancerName,Scheme,DNSName]' --output table
```

기대: 1) `internet-facing application vpc-04e04849604e2fadb mc-alb-public-485062926… [subnet-0a2f…, subnet-0d54…] [sg-0cd2…]` 2) `idle_timeout.timeout_seconds 60` · `load_balancing.cross_zone.enabled true` · `access_logs.s3.enabled true` · `access_logs.s3.prefix alb/public` 3) `mc-alb-public internet-facing` · `mc-alb-internal internal`
## 2-2. ② 리스너 — 문 하나, 443
**무슨 일이 일어나나**
1. 리스너 = **포트 + 프로토콜** 조합 하나. 로드 밸런서 하나에 여러 리스너를 둘 수 있다(80 · 443 · 8080 …). 우리는 **443 HTTPS 하나**. 80 리스너가 없으니 ALB 는 80 포트를 듣지도 않는다(SG 도 안 열려 있음 — 둘 다 막힌 상태).
2. HTTPS 리스너는 **인증서와 보안 정책**을 가진다(2단계). TLS 를 여기서 풀고, 풀린 요청을 규칙에 넘긴다.
3. 리스너는 **규칙 목록의 주인**이다. 규칙은 리스너에 속하고, 리스너를 지우면 규칙도 사라진다. 기본 작업(default action)은 리스너의 속성이자 "우선순위 마지막 규칙" 이다.
4. 내부 ALB 의 리스너는 **8080 HTTP** 하나 — 인증서 없음, 기본 작업 = forward `mc-tg-was`. 규칙 없이 기본 작업만으로 전부 보낸다.

**우리 값**
<table header-row="true" fit-page-width="true">
	<tr>
		<td>항목</td>
		<td>mc-alb-public 리스너</td>
		<td>mc-alb-internal 리스너</td>
	</tr>
	<tr>
		<td>포트 · 프로토콜</td>
		<td>**443 HTTPS**</td>
		<td>8080 HTTP</td>
	</tr>
	<tr>
		<td>인증서 · 정책</td>
		<td>ACM 서울 `…/14198286…` · `ELBSecurityPolicy-TLS13-1-2-2021-06`</td>
		<td>—</td>
	</tr>
	<tr>
		<td>기본 작업</td>
		<td>`fixed-response 403`</td>
		<td>`forward → mc-tg-was`</td>
	</tr>
	<tr>
		<td>규칙 수</td>
		<td>1 (+기본)</td>
		<td>0 (+기본)</td>
	</tr>
</table>
**없으면 · 오해**
- 리스너가 없으면 로드 밸런서는 아무 포트도 안 듣는다 — "만들었는데 접속이 안 돼요" 의 첫 번째 확인 지점.
- 80 리스너를 "redirect to 443" 으로 두는 관례가 있지만, 우리는 CloudFront 가 http→https 를 하므로 굳이 80 을 열지 않는다(0단계 ④). 열면 SG 도 80 을 열어야 하고 그러면 평문이 VPC 까지 온다.
- "리스너 포트 443 = 서버 포트 443" 아니다. 서버 쪽 포트는 **대상 그룹**이 정한다(80). 리스너는 뷰어 쪽 얘기.

**눈으로 확인**

```bash
ALB=$(aws elbv2 describe-load-balancers --names mc-alb-public --profile mc-deploy --region ap-northeast-2 --query 'LoadBalancers[0].LoadBalancerArn' --output text)
# 1) 리스너 목록 — 443 하나 · 인증서 · 정책 · 기본 작업
aws elbv2 describe-listeners --load-balancer-arn $ALB --profile mc-deploy --region ap-northeast-2 --query 'Listeners[].[Port,Protocol,SslPolicy,Certificates[0].CertificateArn,DefaultActions[0].Type,DefaultActions[0].FixedResponseConfig.StatusCode]' --output table
# 2) 내부 ALB 리스너 — 8080 HTTP · 기본 forward
IALB=$(aws elbv2 describe-load-balancers --names mc-alb-internal --profile mc-deploy --region ap-northeast-2 --query 'LoadBalancers[0].LoadBalancerArn' --output text)
aws elbv2 describe-listeners --load-balancer-arn $IALB --profile mc-deploy --region ap-northeast-2 --query 'Listeners[].[Port,Protocol,DefaultActions[0].Type]' --output table
# 3) 80 은 정말 아무도 안 듣나 — 내 PC 에서 (SG 가 먼저 막아 timeout · 리스너가 있어도 SG 에서 죽는다는 점을 기억)
curl -s -o /dev/null -m 6 -w "http80=%{http_code} exit=" http://mc-alb-public-485062926.ap-northeast-2.elb.amazonaws.com/; echo $?
```

기대: 1) `443 HTTPS ELBSecurityPolicy-TLS13-1-2-2021-06 arn:aws:acm:ap-northeast-2:… fixed-response 403` 한 줄 2) `8080 HTTP forward` 3) `http80=000 exit=28`
## 2-3. ③ 규칙 — 위에서 아래로, 첫 매치에서 끝
**무슨 일이 일어나나**
1. 규칙 = **조건 + 작업 + 우선순위**. 리스너가 요청을 받으면 우선순위 **숫자가 작은 규칙부터** 조건을 검사하고, **처음 맞는 규칙의 작업**을 실행하고 끝낸다. 아무것도 안 맞으면 기본 작업.
2. 조건 유형: `path-pattern`(경로) · `host-header`(도메인) · `http-header`(임의 헤더 값) · `http-request-method` · `query-string` · `source-ip`. 한 규칙에 여러 조건을 넣으면 **AND**, 한 조건에 여러 값은 **OR**.
3. 작업 유형: `forward`(대상 그룹으로 · 가중치로 여러 그룹 분배 가능) · `redirect`(3xx) · `fixed-response`(ALB 가 직접 응답) · `authenticate-cognito/oidc`.
4. 우리 규칙 10: 조건 `http-header` 이름 `X-Origin-Verify` 값 = (비밀) → 작업 `forward mc-tg-web`. 이게 **도장 검사**(4단계). 맞으면 대상 그룹으로, 아니면 기본 작업 **403**(대상에 닿지도 않음 · 로그 target `-`).
5. 로그의 `matched_rule_priority` 가 무엇이 맞았는지 알려 준다: `10` 이면 규칙 10, `0` 이면 기본 작업.

**우리 값**
<table header-row="true" fit-page-width="true">
	<tr>
		<td>순서</td>
		<td>규칙</td>
		<td>조건</td>
		<td>작업</td>
		<td>로그 표시</td>
	</tr>
	<tr>
		<td>1</td>
		<td>우선순위 10</td>
		<td>요청 헤더 `X-Origin-Verify` 값이 우리 비밀값과 같다(값은 tfvars 에만)</td>
		<td>`forward → mc-tg-web`. 여기서 끝 — 아래는 안 봄</td>
		<td>`matched_rule_priority 10` · `actions_executed "forward"`</td>
	</tr>
	<tr>
		<td>2</td>
		<td>기본(default)</td>
		<td>위에서 아무것도 안 맞음</td>
		<td>`fixed-response 403 Forbidden`. 대상에 안 감</td>
		<td>`matched_rule_priority 0` · target `-` · elb 403</td>
	</tr>
</table>
**없으면 · 오해**
- 규칙 10 을 지우면: CloudFront 를 거친 정상 요청도 전부 기본 작업 → **사이트 전체 403**(9단계 장애 E).
- 기본 작업을 forward 로 바꾸면: 도장 검사가 무의미 — 도장 없는 요청도 대상으로 간다. 기본은 반드시 **거부**.
- "규칙 순서는 만든 순서" — 아니다. 우선순위 숫자다. 나중에 경로 분기(`/api/*` → 다른 대상 그룹)를 넣을 땐 도장 검사(10)보다 **뒤** 번호로 두되, 도장 조건을 각 규칙에 다시 넣거나(AND) 도장을 먼저 통과시키는 구조가 필요하다 — ALB 규칙은 체인이 아니라 첫 매치이므로.

**눈으로 확인**

```bash
ALB=$(aws elbv2 describe-load-balancers --names mc-alb-public --profile mc-deploy --region ap-northeast-2 --query 'LoadBalancers[0].LoadBalancerArn' --output text)
L=$(aws elbv2 describe-listeners --load-balancer-arn $ALB --profile mc-deploy --region ap-northeast-2 --query 'Listeners[0].ListenerArn' --output text)
# 1) 규칙 — 우선순위 · 조건 유형 · 헤더 이름 · 작업 (값(Values)은 일부러 안 뽑는다)
aws elbv2 describe-rules --listener-arn $L --profile mc-deploy --region ap-northeast-2 --query 'Rules[].[Priority,IsDefault,Conditions[0].Field,Conditions[0].HttpHeaderConfig.HttpHeaderName,Actions[0].Type,Actions[0].FixedResponseConfig.StatusCode]' --output table
# 2) 오늘 로그에서 어떤 규칙이 맞았나 — 전부 10 이어야 (0 이 있으면 도장 없는 요청이 리스너까지 온 것)
K=$(aws s3 ls s3://mc-logs-528821350786/alb/public/ --recursive --profile mc-deploy | grep -v TestFile | tail -1 | awk '{print $4}')
aws s3 cp "s3://mc-logs-528821350786/$K" - --profile mc-deploy | zcat | awk -F'"' '{split($11,a," "); print a[1]}' | sort | uniq -c
```

기대: 1) `10 False http-header X-Origin-Verify forward None` · `default True None None fixed-response 403` 2) `N 10` 한 줄(0 없음)
## 2-4. ④ 대상 그룹 — 명단 · 포트 · 헬스체크 · 분산
**무슨 일이 일어나나**
1. 대상 그룹 = "이 서버들에게, 이 포트로, 이렇게 나눠서 보내고, 이렇게 살았는지 본다" 의 묶음. 리스너 규칙의 `forward` 가 가리키는 대상이다.
2. **서버 쪽 프로토콜·포트**가 여기 있다: HTTP 80. 뷰어는 443 으로 왔지만 대상엔 80 으로 간다(TLS 종료 = 2단계). 대상 유형은 `instance`(EC2 ID 로 등록 · ASG 가 쓰는 방식) — `ip` · `lambda` 유형도 있다.
3. **헬스체크** 설정이 여기 있다: `/health.html` · 10s 간격 · 5s 타임아웃 · 정상 2회 · 비정상 3회 · 성공 코드 200(5단계).
4. **분산 알고리즘** `round_robin`(번갈아) · 스티키 세션 off(무상태 앱) · slow start 0(새 대상에 즉시 100%) · **등록 취소 지연 30s**(대상을 뺄 때 진행 중 요청을 30초 기다림 = 드레이닝). 교차 영역은 로드 밸런서 설정을 따름(on).
5. 대상 그룹은 로드 밸런서와 **독립** 리소스다. 지표 차원은 `targetgroup/mc-tg-web/5ae742de9f467369` — `HealthyHostCount` 같은 지표가 이 차원에 붙는다.

**우리 값**
<table header-row="true" fit-page-width="true">
	<tr>
		<td>항목</td>
		<td>mc-tg-web</td>
		<td>mc-tg-was (비교)</td>
	</tr>
	<tr>
		<td>프로토콜 · 포트 · 유형</td>
		<td>HTTP **80** · HTTP1 · instance</td>
		<td>HTTP **8080** · HTTP1 · instance</td>
	</tr>
	<tr>
		<td>헬스체크</td>
		<td>`/health.html` · 10s · 5s · 2 / 3 · 200</td>
		<td>`/petclinic/` · 10s · 5s · 2 / 3 · 200</td>
	</tr>
	<tr>
		<td>알고리즘 · 스티키 · slow start</td>
		<td>`round_robin` · false · 0</td>
		<td>`round_robin` · false · 0</td>
	</tr>
	<tr>
		<td>등록 취소 지연</td>
		<td>30s</td>
		<td>30s</td>
	</tr>
	<tr>
		<td>교차 영역</td>
		<td>`use_load_balancer_configuration` (= on)</td>
		<td>동일</td>
	</tr>
	<tr>
		<td>지표 차원</td>
		<td>`targetgroup/mc-tg-web/5ae742de9f467369`</td>
		<td>`targetgroup/mc-tg-was/bfdbf38a18a21751`</td>
	</tr>
</table>
**없으면 · 오해**
- 포트를 443 으로 두면 Apache 는 80 만 듣고 있어 전부 unhealthy → 503. "리스너 443 이니 대상도 443" 은 흔한 실수.
- 헬스체크 경로를 `/petclinic/`(프록시 경유) 로 두면 WAS 장애 때 WEB 까지 unhealthy → 503(5단계 '얕게').
- 스티키를 켜면 CloudFront 엣지 몇 개가 특정 WEB 으로 쏠려 분산이 깨진다. 세션 없는 앱엔 끈다.

**눈으로 확인**

```bash
TG=$(aws elbv2 describe-target-groups --names mc-tg-web --profile mc-deploy --region ap-northeast-2 --query 'TargetGroups[0].TargetGroupArn' --output text)
# 1) 프로토콜 · 포트 · 헬스체크
aws elbv2 describe-target-groups --target-group-arns $TG --profile mc-deploy --region ap-northeast-2 --query 'TargetGroups[0].[Protocol,Port,ProtocolVersion,TargetType,HealthCheckPath,HealthCheckIntervalSeconds,HealthCheckTimeoutSeconds,HealthyThresholdCount,UnhealthyThresholdCount,Matcher.HttpCode]' --output text
# 2) 속성 — 알고리즘 · 스티키 · slow start · 등록 취소
aws elbv2 describe-target-group-attributes --target-group-arn $TG --profile mc-deploy --region ap-northeast-2 --query 'Attributes[?Key==`load_balancing.algorithm.type`||Key==`stickiness.enabled`||Key==`slow_start.duration_seconds`||Key==`deregistration_delay.timeout_seconds`].[Key,Value]' --output table
# 3) 어느 리스너(규칙)가 이 대상 그룹을 쓰나 — 로드 밸런서 ARN 이 붙어 있으면 '연결됨'
aws elbv2 describe-target-groups --target-group-arns $TG --profile mc-deploy --region ap-northeast-2 --query 'TargetGroups[0].LoadBalancerArns' --output text
```

기대: 1) `HTTP 80 HTTP1 instance /health.html 10 5 2 3 200` 2) `round_robin · false · 0 · 30` 3) `…loadbalancer/app/mc-alb-public/0780e6e7d84abe76`
## 2-5. ⑤ 대상 — 실제 서버와 그 상태
**무슨 일이 일어나나**
1. 대상 = 대상 그룹 명단에 오른 **서버 하나** (EC2 ID + 포트). 우리는 Terraform 이 `aws_lb_target_group_attachment` 로 web-a/web-c 를 직접 등록했다. ASG 를 켜면(10단계) ASG 가 등록·해제를 대신한다.
2. 상태(TargetHealth.State)는 헬스체크 결과다: `initial`(등록 직후 · 첫 2회 통과 전) → `healthy` ↔ `unhealthy` · `draining`(등록 취소 중 30s) · `unused`(대상 그룹이 리스너에 안 붙음). 이유(Reason)가 `Target.ResponseCodeMismatch` · `Target.Timeout` · `Target.FailedHealthChecks` 등으로 나온다.
3. ALB 노드는 **healthy 인 대상에게만** 새 요청을 보낸다. 둘 다 unhealthy 면 보낼 곳이 없어 **503**(9단계) — 단, 모든 대상이 unhealthy 면 ALB 는 "fail open" 으로 전부에게 보내기도 한다(그래도 응답이 없으니 사용자는 실패).
4. 대상 쪽 SG 가 열려 있어야 한다: `mc-sg-web` 80 ← ALB SG(0단계). 헬스체크도 같은 경로로 오므로 SG 가 막히면 곧 unhealthy.

**우리 값**
<table header-row="true" fit-page-width="true">
	<tr>
		<td>대상</td>
		<td>서버</td>
		<td>포트</td>
		<td>상태 (9/17)</td>
	</tr>
	<tr>
		<td>`i-01a195cff8acb28d8`</td>
		<td>mc-web-a · `10.0.10.189` · mc-web-a 서브넷(2a)</td>
		<td>80</td>
		<td>healthy</td>
	</tr>
	<tr>
		<td>`i-01d1734d081d8bc57`</td>
		<td>mc-web-c · `10.0.11.89` · mc-web-c 서브넷(2c)</td>
		<td>80</td>
		<td>healthy</td>
	</tr>
	<tr>
		<td>(비교) mc-tg-was</td>
		<td>`i-0ff9a07cd26d34ba0` was-a `10.0.20.53` · `i-0d308599780158a68` was-c `10.0.21.231`</td>
		<td>8080</td>
		<td>둘 다 healthy</td>
	</tr>
	<tr>
		<td>지표</td>
		<td>`HealthyHostCount`(mc-tg-web) 지난 1시간 최소 **2**</td>
		<td></td>
		<td></td>
	</tr>
</table>
**없으면 · 오해**
- 대상을 등록만 하고 SG 를 안 열면 영원히 `initial`/`unhealthy`(`Target.Timeout`). "서버는 멀쩡한데 unhealthy" 의 1순위 원인.
- 대상 그룹에 대상이 0 이면 ALB 는 503 을 낸다 — 리스너·규칙이 아무리 맞아도.
- EC2 를 교체하면 새 인스턴스는 **새 ID** — 고정 등록 방식에선 Terraform 이 attachment 를 다시 만든다(9/16 롤링 교체 때 확인). ASG 방식이면 자동.

**눈으로 확인**

```bash
TG=$(aws elbv2 describe-target-groups --names mc-tg-web --profile mc-deploy --region ap-northeast-2 --query 'TargetGroups[0].TargetGroupArn' --output text)
# 1) 대상과 상태 · 이유
aws elbv2 describe-target-health --target-group-arn $TG --profile mc-deploy --region ap-northeast-2 --query 'TargetHealthDescriptions[].[Target.Id,Target.Port,TargetHealth.State,TargetHealth.Reason]' --output table
# 2) 그 ID 가 어느 서버인지 — 이름 · 사설 IP · 서브넷
aws ec2 describe-instances --instance-ids i-01a195cff8acb28d8 i-01d1734d081d8bc57 --profile mc-deploy --region ap-northeast-2 --query 'Reservations[].Instances[].[Tags[?Key==`Name`].Value|[0],PrivateIpAddress,SubnetId,State.Name]' --output table
# 3) 정상 대상 수 지표 (지난 1시간 최소값)
aws cloudwatch get-metric-statistics --namespace AWS/ApplicationELB --metric-name HealthyHostCount --dimensions Name=LoadBalancer,Value=app/mc-alb-public/0780e6e7d84abe76 Name=TargetGroup,Value=targetgroup/mc-tg-web/5ae742de9f467369 --start-time $(date -u -d '-1 hour' +%FT%TZ) --end-time $(date -u +%FT%TZ) --period 3600 --statistics Minimum --profile mc-deploy --region ap-northeast-2 --query 'Datapoints[0].Minimum' --output text
```

기대: 1) 두 줄 모두 `80 healthy None` 2) `mc-web-a 10.0.10.189 subnet-0068… running` · `mc-web-c 10.0.11.89 subnet-0ad2… running` 3) `2.0`
## 2-6. 요청 하나 따라가기 — `GET /petclinic/vets` (오늘 ALB 로그 한 줄로)
<table header-row="true" fit-page-width="true">
	<tr>
		<td>순서</td>
		<td>부품</td>
		<td>무슨 일</td>
		<td>로그·실측</td>
	</tr>
	<tr>
		<td>1</td>
		<td>① 로드 밸런서 노드</td>
		<td>CloudFront 가 DNS 로 고른 노드(2c `3.34.116.99`)의 ENI 에 SG 통과 후 도착</td>
		<td>ip_address `3.34.116.99` · client `15.158.254.101:19438`</td>
	</tr>
	<tr>
		<td>2</td>
		<td>② 리스너 443</td>
		<td>TLS 1.3 종료(인증서 B) · HTTP 해석 · X-Forwarded-* 추가</td>
		<td>`TLSv1.3 TLS_AES_128_GCM_SHA256` · domain_name `petclinic.mission-critical.site`</td>
	</tr>
	<tr>
		<td>3</td>
		<td>③ 규칙</td>
		<td>우선순위 10 조건(도장) 검사 → 매치 → forward</td>
		<td>`matched_rule_priority 10` · `actions_executed "forward"`</td>
	</tr>
	<tr>
		<td>4</td>
		<td>④ 대상 그룹 mc-tg-web</td>
		<td>healthy 대상 중 라운드 로빈으로 하나 선택 · 서버 포트 80</td>
		<td>target_group_arn `…/mc-tg-web/5ae742de9f467369`</td>
	</tr>
	<tr>
		<td>5</td>
		<td>⑤ 대상 web-c</td>
		<td>노드 `10.0.1.212` 가 `10.0.11.89:80` 으로 평문 연결 · 응답 200</td>
		<td>target `10.0.11.89:80` · `200 200` · target_processing_time `0.00x`</td>
	</tr>
	<tr>
		<td>6</td>
		<td>(Apache 가 다시 프록시)</td>
		<td>`/petclinic/*` 라 Internal ALB 8080 → 기본 작업 forward → mc-tg-was → Tomcat</td>
		<td>WAS access log `10.0.21.43 … "HEAD /petclinic/vets HTTP/1.1" 200`</td>
	</tr>
</table>
기억할 것 셋: **부품은 따로, 참조로 연결**(LB→리스너→규칙→대상 그룹→대상) · **규칙은 첫 매치에서 끝, 기본은 거부** · **서버 포트·헬스체크·분산은 전부 대상 그룹의 것**.
# 3. 용어 — 이 단계에서만 쓰는 것
<table header-row="true" fit-page-width="true">
	<tr>
		<td>용어</td>
		<td>한 줄</td>
		<td>비유</td>
	</tr>
	<tr>
		<td>로드 밸런서(껍데기)</td>
		<td>서브넷·SG·속성을 가진 설정 묶음. IP 는 노드가</td>
		<td>병원 건물</td>
	</tr>
	<tr>
		<td>노드</td>
		<td>AZ(서브넷)마다 생기는 실제 처리 장비(ENI)</td>
		<td>층마다 있는 안내데스크</td>
	</tr>
	<tr>
		<td>리스너</td>
		<td>포트·프로토콜 하나 + 인증서 + 규칙 목록</td>
		<td>정문 창구 "443번"</td>
	</tr>
	<tr>
		<td>규칙 · 우선순위 · 기본 작업</td>
		<td>조건→작업. 작은 번호부터 첫 매치. 안 맞으면 기본</td>
		<td>창구 직원의 안내 지침서(1번부터 읽고 해당되면 끝)</td>
	</tr>
	<tr>
		<td>fixed-response</td>
		<td>ALB 가 대상 없이 직접 응답(403 등)</td>
		<td>창구에서 바로 "돌아가세요"</td>
	</tr>
	<tr>
		<td>대상 그룹</td>
		<td>서버 명단 + 서버 포트 + 헬스체크 + 분산 방식</td>
		<td>진료과(의사 명단 · 호출 방식)</td>
	</tr>
	<tr>
		<td>대상</td>
		<td>명단의 서버 하나 + 상태</td>
		<td>의사 한 명 · 출근 여부</td>
	</tr>
	<tr>
		<td>등록 취소 지연(드레이닝)</td>
		<td>대상을 뺄 때 진행 중 요청을 기다리는 시간(30s)</td>
		<td>퇴근 전 보던 환자 마무리</td>
	</tr>
	<tr>
		<td>교차 영역 분산</td>
		<td>노드가 다른 AZ 의 대상에게도 보냄</td>
		<td>1층 데스크가 2층 진료실로도 안내</td>
	</tr>
</table>
# 4. 왜 이렇게 만들었나 (멘토가 물을 만한 것)
- **왜 리스너를 443 하나만?** 평문 진입로를 없애기 위해. http→https 는 CloudFront 가 하고, 80 리스너가 없으면 SG 도 80 을 열 이유가 없다.
- **왜 기본 작업이 403 인가?** "명시적으로 허용된 것만 통과" 원칙. 도장 규칙 하나만 forward 이고 나머지는 전부 거부.
- **왜 대상 유형이 instance 인가?** EC2 ID 로 등록하면 ASG 가 스스로 등록·해제할 수 있다(10단계). IP 유형은 온프레미스·다른 VPC 대상일 때.
- **왜 대상 그룹을 WEB·WAS 로 나누고 ALB 도 두 대인가?** 계층마다 독립 확장·독립 헬스체크. WAS 만 늘리거나 교체해도 WEB 은 Internal ALB 이름만 알면 된다(6단계).
- **경로 분기(`/api/*`)는 어디에 넣나?** 같은 리스너에 규칙 추가 — 단 도장 검사가 첫 매치라서, 새 규칙에도 도장 조건을 AND 로 넣어야 우회가 안 생긴다.
# 5. 다음 단계(4. 오리진 보호) 진입 기준
<details>
<summary>Q1. 규칙 10 을 지우면 무슨 일이 생기나? 로그엔 어떻게 보이나?</summary>
	모든 요청이 기본 작업 403 으로 떨어진다 — CloudFront 를 거친 정상 요청도. 로그는 `elb 403` · target `-` · `matched_rule_priority 0`.
</details>
<details>
<summary>Q2. 80 리스너를 추가하고 mc-tg-web 으로 forward 하면 무엇이 열리나?</summary>
	SG 까지 80 을 열면 ALB DNS 로 평문 직접 접근이 열려 CloudFront·WAF 를 우회하는 길이 생긴다(4단계). 그래서 없앴다(`public_http_listener=false`).
</details>
<details>
<summary>Q3. 대상 그룹의 포트 80 과 리스너 443 이 다른데 어떻게 되나?</summary>
	리스너는 뷰어(CloudFront) 쪽 포트, 대상 그룹 포트는 서버 쪽 포트. ALB 가 TLS 를 풀고(2단계) 443 → 80 으로 새 평문 연결을 연다.
</details>
<details>
<summary>Q4. "서버는 멀쩡한데 대상이 unhealthy" 일 때 가장 먼저 볼 것은?</summary>
	대상 쪽 SG(`mc-sg-web` 80 ← ALB SG)와 헬스체크 경로·포트·성공 코드. Reason 이 `Target.Timeout` 이면 SG/네트워크, `ResponseCodeMismatch` 면 경로·코드.
</details>
# 6. 읽을 자료
- AWS 문서 — *Listener rules for your Application Load Balancer* (조건·작업 유형 표)
- AWS 문서 — *Target groups for your Application Load Balancers* (알고리즘 · 속성 · 대상 유형)
- AWS 문서 — *Health checks for your target groups* (상태 · Reason 코드)
- 콘솔 구축 가이드 **4-2 · 4-3 · ⑥** 절
<callout icon="🗺️" color="gray_bg">
	**로드맵 위치**: 0 VPC 입구 → 1 HTTP 기초 → 2 TLS 종료 지점 → **3 ALB 해부(이 페이지)** → 4 오리진 보호(헤더) → 5 헬스체크 → 6 Apache 프록시 → 7 분산·타임아웃 → 8 WEB 관측 → 9 장애 모드 → 10 ASG·AMI.
</callout>
