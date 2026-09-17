<callout icon="🩺" color="blue_bg">
	**이 단계의 목표**: ALB 가 "이 서버 살아 있나" 를 판단하는 방식과, WEB 은 얕게·WAS 는 깊게 보는 이유, 10s·5s·2/3·30s 가 실제로 몇 초를 뜻하는지, 실패하면 무슨 일이 생기는지. 반나절 분량. 값은 전부 2026-09-17 mc-deploy 실측.
</callout>
# 0. 그림 한 장

```text
ALB 노드 2a (10.0.0.212) ──GET /health.html:80 · 10s 마다──▶ web-a Apache ──▶ 파일 "ok" 200  ─┐
ALB 노드 2c (10.0.1.212) ──GET /health.html:80 · 10s 마다──▶ web-c Apache ──▶ 파일 "ok" 200  ─┤ ② 얕게: Apache 만 본다
Internal ALB 노드 ────────GET /petclinic/:8080 · 10s 마다──▶ was Tomcat ──▶ 앱 홈 200 ───────┘ ② 깊게: Tomcat + 앱 까지
   ① 누가·무엇을·언제         ③ 5s 안에 200 · 3번 연속 실패 → unhealthy(≈30s) · 2번 성공 → healthy(≈20s)   ④ 뺄 땐 30s 드레이닝   ⑤ 정상 0 → 503 → 점검 페이지
```

헬스체크는 **로드 밸런서가 대상에게 주기적으로 보내는 진짜 HTTP 요청**이다. 마법이 아니라 그냥 GET — 그래서 SG · 경로 · 응답 코드 세 가지가 맞아야 통과한다.
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
		<td>누가 · 무엇을 · 언제</td>
		<td>ALB **노드마다** 대상 그룹의 경로로 GET. 대상 포트(traffic-port) · 지정 코드(200)면 성공</td>
		<td>`ELB-HealthChecker/2.0` 가 `GET /health.html` → `200 · 3바이트("ok")`. 서버엔 약 **2.5초에 한 번** 옴(노드 2개 × 체커)</td>
	</tr>
	<tr>
		<td>②</td>
		<td>얕게 vs 깊게</td>
		<td>WEB 은 **Apache 만** 검사(정적 파일), WAS 는 **Tomcat+앱** 검사(앱 홈). 계층마다 자기 계층만</td>
		<td>`mc-tg-web` `/health.html`(Apache 직접 · `ProxyPass ! ` 제외) · `mc-tg-was` `/petclinic/`(welcome.jsp 200 · 12,358바이트)</td>
	</tr>
	<tr>
		<td>③</td>
		<td>숫자 번역</td>
		<td>간격 10s · 타임아웃 5s · 정상 2회 · 비정상 3회 → 제외까지 **≈30s**, 복귀까지 **≈20s**</td>
		<td>두 대상 그룹 모두 `10 / 5 / 2 / 3 / 200`</td>
	</tr>
	<tr>
		<td>④</td>
		<td>등록 취소 지연(드레이닝)</td>
		<td>대상을 **일부러 뺄 때**(교체 · 축소) 새 요청은 즉시 안 보내고 진행 중 요청만 N초 기다림</td>
		<td>`deregistration_delay 30s` · 9/16 롤링 교체 때 사용</td>
	</tr>
	<tr>
		<td>⑤</td>
		<td>실패하면</td>
		<td>unhealthy → 새 요청 안 감 → 정상 대상 0 이면 ALB **503** → CloudFront 점검 페이지 · 지표 `UnHealthyHostCount` · 알람(WAS 만)</td>
		<td>WEB 2/0 healthy · 알람 `mc-was-unhealthy-host`(≥1 · 2분 · SNS mc-alerts) · WEB 알람 **없음**(로드맵)</td>
	</tr>
</table>
<callout icon="🔎" color="yellow_bg">
	**오늘 발견 (9/17)**: petclinic.conf 의 `SetEnvIf … nolog` + `CustomLog … env=!nolog` 는 헬스체크를 로그에서 빼려는 의도인데, **실제 로그엔 헬스체크가 그대로 찍히고**(1시간에 1,442줄) **일반 요청은 두 번씩** 찍힌다. 원인: httpd.conf 의 기본 `CustomLog "logs/access_log" combined` 가 살아 있어 같은 파일에 **두 CustomLog** 가 쓴다 — 기본 것은 헬스체크를 안 거르고, conf.d 것은 거른다. 수정안: web.sh 에서 기본 CustomLog 를 주석 처리(한 줄 `sed`) 후 인스턴스 교체. 2-1 · 2-2 에서 실측으로 확인.
</callout>
# 2. 자세히 — 항목마다 "무슨 일 · 우리 값 · 없으면 · 눈으로 확인"
## 2-1. ① 누가 · 무엇을 · 언제 — 헬스체크는 그냥 GET 이다
**무슨 일이 일어나나**
1. 대상 그룹에 "경로 · 프로토콜 · 포트 · 간격 · 타임아웃 · 임계값 · 성공 코드" 가 있다(3단계 ④). ALB 의 **각 노드**가 이 설정대로 대상마다 독립적으로 요청을 보낸다. 요청의 출발지는 노드 **사설 IP**(`10.0.0.212` · `10.0.1.212`), User-Agent 는 `ELB-HealthChecker/2.0`.
2. 요청은 일반 요청과 같은 길로 간다: 노드 → (대상 SG `80 ← ALB SG`) → Apache 80 → `/health.html` 파일 → `200 ok`. **SG 가 막히면 헬스체크도 막힌다** — "서버는 멀쩡한데 unhealthy" 의 1순위.
3. 헬스체크 요청엔 `X-Origin-Verify` 도장이 없다 — 리스너 규칙을 안 거치기 때문(노드 → 대상 직접). 그래서 규칙 10 과 무관하게 동작한다.
4. 대상 포트는 `traffic-port` = 대상 그룹 포트(80). 별도 포트(예: 8081 관리 포트)로 바꿀 수도 있다.
5. 실측 빈도: 설정은 10s 인데 서버 로그엔 약 2.5s 마다 온다 — 노드 2개 × 노드당 체커 복수. 서버당 하루 ≈ 3만 5천 번, 부하는 무시할 수준이지만 **로그엔 큰 잡음**(오늘 발견 참고).

**우리 값**
<table header-row="true" fit-page-width="true">
	<tr>
		<td>항목</td>
		<td>값</td>
	</tr>
	<tr>
		<td>요청 (Apache 로그 실측)</td>
		<td>`10.0.0.212 - - [17/Sep/2026:05:38:36 +0000] "GET /health.html HTTP/1.1" 200 3 "-" "ELB-HealthChecker/2.0"`</td>
	</tr>
	<tr>
		<td>출발지</td>
		<td>ALB 노드 사설 IP `10.0.0.212`(2a) · `10.0.1.212`(2c) — 번갈아</td>
	</tr>
	<tr>
		<td>응답</td>
		<td>`200` · 본문 `ok`(3바이트) — `/var/www/html/health.html`, web.sh 의 `echo ok › …`</td>
	</tr>
	<tr>
		<td>빈도</td>
		<td>1시간 1,442줄 ≈ 2.5초에 1번 (설정 간격 10s · 노드 2개)</td>
	</tr>
	<tr>
		<td>WAS 쪽</td>
		<td>Internal ALB 노드(`10.0.20.193` · `10.0.21.43`) → `GET /petclinic/ HTTP/1.1` 200 12358 · 10분에 238줄</td>
	</tr>
</table>
**없으면 · 오해**
- 헬스체크 경로 파일이 없으면 404 → 성공 코드(200) 불일치 → unhealthy. `echo ok › health.html` 한 줄이 서비스 생사를 가른다.
- "헬스체크는 ALB 가 내부적으로 하는 것" — 아니다. 서버 로그에 찍히는 **진짜 요청**이고, SG · Apache 설정 · 파일 권한 전부 일반 요청과 같이 적용된다.
- 헬스체크가 도장 규칙을 안 거친다는 건 "규칙이 틀려도 healthy" 라는 뜻 — 장애 E(403 전면)는 헬스체크로 못 잡는다(9단계).

**눈으로 확인**

```bash
# 1) 헬스체크 설정 — 경로 · 포트 · 간격 · 타임아웃 · 임계값 · 코드
for tg in mc-tg-web mc-tg-was; do aws elbv2 describe-target-groups --names $tg --profile mc-deploy --region ap-northeast-2 --query 'TargetGroups[0].[TargetGroupName,HealthCheckProtocol,HealthCheckPort,HealthCheckPath,HealthCheckIntervalSeconds,HealthCheckTimeoutSeconds,HealthyThresholdCount,UnhealthyThresholdCount,Matcher.HttpCode]' --output text; done
# 2) 서버에 실제로 오는 요청 — CloudWatch Logs (서버 접속 불필요)
aws logs tail /mc/web/access --since 1m --profile mc-deploy --region ap-northeast-2 --format short | grep health.html | tail -4
# 3) 빈도 — 1시간에 몇 줄
aws logs tail /mc/web/access --since 1h --profile mc-deploy --region ap-northeast-2 --format short | grep -c health.html
# 4) 같은 파일을 CloudFront 를 거쳐도 열 수 있다 (헬스체크와 같은 200 ok)
curl -s https://petclinic.mission-critical.site/health.html; echo
```

기대: 1) `mc-tg-web HTTP traffic-port /health.html 10 5 2 3 200` · `mc-tg-was … /petclinic/ 10 5 2 3 200` 2) `10.0.0.212 … "GET /health.html HTTP/1.1" 200 3 … "ELB-HealthChecker/2.0"` 3) 약 1,400 4) `ok`
## 2-2. ② 얕게 vs 깊게 — 계층마다 자기 계층만
**무슨 일이 일어나나**
1. WEB 헬스체크 `/health.html` 은 `ProxyPass /health.html !` 로 프록시에서 **제외**돼 Apache 가 파일을 직접 준다(6단계). 증명하는 것: "Apache 프로세스가 살아 요청을 받는다". WAS 가 죽어도 WEB 은 healthy.
2. WAS 헬스체크 `/petclinic/` 는 Tomcat 의 앱 홈(welcome.jsp) — Spring 컨텍스트가 떠야 200. 증명하는 것: "Tomcat + 앱(+ 초기화 시 DB 연결)까지 정상". 슬래시가 없으면(`/petclinic`) Tomcat 이 301 을 줘서 실패한다 — 경로에 `/` 필수.
3. 왜 WEB 을 `/petclinic/`(프록시 경유) 로 안 하나: WAS 가 죽으면 WEB 2대가 **전부 unhealthy** → ALB 는 보낼 곳이 없어 503. 그런데 Apache 는 멀쩡해서 랜딩 `/` · 정적 파일 · 점검 안내를 줄 수 있는데도 못 준다. 계층별로 끊어 보면 장애가 **국소화**된다: WAS 장애 = 앱 경로만 점검 페이지, 랜딩은 정상(9단계 장애 C).
4. WAS 장애는 누가 잡나: Internal ALB 의 헬스체크 + 알람 `mc-was-unhealthy-host`. WEB 은 Apache 가 Internal ALB 에서 503 을 받아 그대로 넘기고, CloudFront 가 점검 페이지로 바꾼다.
5. 헬스체크 로그 잡음을 막으려고 `SetEnvIf Request_URI "^/health.html$" nolog` + `CustomLog … env=!nolog` 를 두었지만 **오늘 실측으로 안 걸러지는 것을 확인**(아래).

**우리 값**
<table header-row="true" fit-page-width="true">
	<tr>
		<td></td>
		<td>mc-tg-web (WEB)</td>
		<td>mc-tg-was (WAS)</td>
	</tr>
	<tr>
		<td>경로</td>
		<td>`/health.html` — 정적 파일 `ok`</td>
		<td>`/petclinic/` — Tomcat 앱 홈(12,358바이트 HTML)</td>
	</tr>
	<tr>
		<td>무엇을 증명</td>
		<td>**Apache 가 살아 요청을 받는다** (얕게)</td>
		<td>**Tomcat + 앱 + (초기화 시) DB** 까지 정상 (깊게)</td>
	</tr>
	<tr>
		<td>프록시 제외</td>
		<td>`ProxyPass /health.html !`</td>
		<td>—</td>
	</tr>
	<tr>
		<td>성공 코드</td>
		<td>200</td>
		<td>200 (슬래시 없으면 301 이라 실패)</td>
	</tr>
	<tr>
		<td>로그 제외</td>
		<td>의도: `SetEnvIf … nolog` — **실측: 안 걸러짐**(기본 CustomLog 중복)</td>
		<td>없음 — Tomcat 액세스 로그에 10분 238줄</td>
	</tr>
</table>
**없으면 · 오해**
- WEB 헬스체크를 깊게(`/petclinic/`) 하면 WAS 장애가 WEB 장애로 번져 **랜딩까지** 점검 페이지. 한 계층의 장애가 두 계층 장애처럼 보인다.
- 반대로 WAS 를 얕게(예: Tomcat 기본 페이지 `/`) 하면 앱이 안 떠도 healthy → 사용자는 404/500 을 본다. WAS 는 깊게가 맞다.
- "헬스체크 로그를 빼면 장애 추적이 어렵다" — unhealthy 판정은 ALB 지표·대상 상태(Reason)로 보면 된다. 로그엔 진짜 요청만 있는 게 낫다.

**눈으로 확인**

```bash
# 1) WEB 헬스체크는 프록시 제외 — web.sh 원문
grep -n "health.html" infra/terraform-kdt5/modules/base/user_data/web.sh
# 2) WAS 헬스체크 — 슬래시 없는 경로는 301 (CloudFront 경유로 같은 동작 확인)
curl -sI https://petclinic.mission-critical.site/petclinic | grep -iE "^HTTP"
# 3) 오늘 발견 — 헬스체크가 로그에 찍히고(있으면 안 됨) 일반 요청이 두 번씩(중복) 찍힌다
aws logs tail /mc/web/access --since 1h --profile mc-deploy --region ap-northeast-2 --format short | grep -c health.html
aws logs tail /mc/web/access --since 1h --profile mc-deploy --region ap-northeast-2 --format short | grep -v health.html | cut -d' ' -f2- | sort | uniq -c | sort -rn | head -3
# 4) 수정안 미리보기 — 기본 CustomLog 한 줄을 끄면 conf.d 의 필터만 남는다 (인스턴스 교체 필요 · 지금은 실행 안 함)
echo 'sed -i "s|^\s*CustomLog \"logs/access_log\" combined|#&|" /etc/httpd/conf/httpd.conf'
```

기대: 1) `ProxyPass /health.html !` · `SetEnvIf Request_URI "^/health.html$" nolog` · `CustomLog … env=!nolog` · `echo ok › /var/www/html/health.html` 2) `HTTP/2 301` 3) 약 1,400 · 같은 줄 앞에 `2` 또는 `4`(중복) 4) (출력만)
## 2-3. ③ 숫자를 시간으로 — 30초와 20초
**무슨 일이 일어나나**
1. **간격(10s)**: 노드마다 10초에 한 번. **타임아웃(5s)**: 5초 안에 응답 코드가 안 오면 그 회차 실패.
2. **비정상 임계값(3)**: 연속 3회 실패해야 `unhealthy`. 장애 발생 → 다음 체크까지 최대 10s + 2회 더 = **최대 ≈30s**(타임아웃이 걸리면 +5s 씩). 그 사이 라운드 로빈으로 그 서버에 간 요청은 실패(502/504).
3. **정상 임계값(2)**: 연속 2회 성공해야 다시 `healthy`. 복구 → 재투입 **≈20s**. 새로 등록한 대상도 `initial` 에서 2회 통과해야 트래픽을 받는다.
4. 노드가 2개라 각자 따로 판정하지만, 대상 상태는 대상 그룹 수준으로 합쳐 보인다(하나라도 unhealthy 로 판정하면 그 노드는 안 보냄).
5. 값을 줄이면(5s · 2회) 제외가 빨라지지만 **오탐**(GC 멈춤 · 순간 부하)으로 멀쩡한 서버를 뺄 수 있다. 늘리면 장애 노출 시간이 길어진다. 10/5/2/3 은 AWS 기본값에 가까운 무난한 값.

**우리 값 — 시간 번역표**
<table header-row="true" fit-page-width="true">
	<tr>
		<td>설정</td>
		<td>값</td>
		<td>실제 시간</td>
	</tr>
	<tr>
		<td>간격</td>
		<td>10s</td>
		<td>노드당 10s · 서버 입장 ≈2.5s(실측)</td>
	</tr>
	<tr>
		<td>타임아웃</td>
		<td>5s</td>
		<td>5초 안에 200 없으면 실패 1회</td>
	</tr>
	<tr>
		<td>비정상 임계값</td>
		<td>3</td>
		<td>장애 → 제외 **≈30s** (10s × 3)</td>
	</tr>
	<tr>
		<td>정상 임계값</td>
		<td>2</td>
		<td>복구 → 재투입 **≈20s** (10s × 2)</td>
	</tr>
	<tr>
		<td>새 인스턴스가 healthy 까지 (9/16 실측)</td>
		<td>—</td>
		<td>WEB ≈ 2분(Apache 설치 + index 복사) · WAS ≈ 6분(Tomcat 다운로드 + Maven 빌드 + Proxy 대기) → ASG grace WEB 300s · WAS 900s(10단계)</td>
	</tr>
</table>
**없으면 · 오해**
- "unhealthy 가 되는 즉시 사용자 영향 0" — 아니다. 판정까지 ≈30s 동안 절반의 요청(2대 중 1대)이 실패한다. 이걸 줄이려면 대수를 늘리거나(3대면 1/3) 임계값을 줄인다.
- 타임아웃(5s)을 간격(10s)보다 크게 둘 수 없다(콘솔이 막음).
- ASG 의 `health_check_grace_period` 는 이 값과 별개 — 부팅 중 헬스체크 실패를 "고장" 으로 안 보게 하는 유예(10단계).

**눈으로 확인**

```bash
TG=$(aws elbv2 describe-target-groups --names mc-tg-web --profile mc-deploy --region ap-northeast-2 --query 'TargetGroups[0].TargetGroupArn' --output text)
# 1) 현재 상태 + 이유 (정상이면 Reason 없음)
aws elbv2 describe-target-health --target-group-arn $TG --profile mc-deploy --region ap-northeast-2 --query 'TargetHealthDescriptions[].[Target.Id,TargetHealth.State,TargetHealth.Reason,TargetHealth.Description]' --output table
# 2) 실험(선택 · Bastion 허용 후): web-a 의 httpd 를 60초 멈추고 5초마다 상태 관찰 → ≈30s 뒤 unhealthy, 켜면 ≈20s 뒤 healthy
#   터미널 1: while true; do date +%T; aws elbv2 describe-target-health --target-group-arn $TG --profile mc-deploy --region ap-northeast-2 --query 'TargetHealthDescriptions[].[Target.Id,TargetHealth.State]' --output text; sleep 5; done
#   터미널 2: ssh -i infra/terraform-kdt5/.keys/mc-ssh.pem -J ec2-user@52.78.145.87 ec2-user@10.0.10.189 'sudo systemctl stop httpd; sleep 60; sudo systemctl start httpd'
```

기대: 1) 두 줄 `healthy None None` 2) 정지 후 ≈30초에 `unhealthy`(Reason `Target.FailedHealthChecks`), 시작 후 ≈20초에 `healthy`
## 2-4. ④ 등록 취소 지연 — 뺄 때 30초
**무슨 일이 일어나나**
1. 헬스체크 실패(③)는 "갑작스런 장애" 용이고, 등록 취소 지연은 **"일부러 뺄 때"** 용이다: 인스턴스 교체 · 축소 · 배포에서 대상을 대상 그룹에서 제거하면 상태가 `draining` 이 된다.
2. draining 동안 **새 요청은 즉시 안 보내고**, 이미 진행 중인 요청·연결만 최대 N초(30s) 기다린다. N초가 지나거나 요청이 다 끝나면 `unused` → 제거. 이걸 연결 드레이닝(connection draining) 이라고도 부른다.
3. 값이 너무 짧으면 긴 요청(리포트 · 업로드)이 끊기고, 너무 길면 교체가 느려진다(ASG 축소 시 N초 동안 인스턴스가 살아 비용). 30s 는 PetClinic 처럼 짧은 요청 앱에 적당.
4. 9/16 롤링 교체 실측: Terraform 이 옛 인스턴스의 attachment 를 지울 때 30s 드레이닝 → 새 인스턴스가 `initial` → 2회 통과 → healthy. 이 순서를 지키면 사용자 끊김이 없다(단, `-target` 로 4대를 한꺼번에 바꾼 실수는 README 참고).

**우리 값**
<table header-row="true" fit-page-width="true">
	<tr>
		<td>항목</td>
		<td>값</td>
	</tr>
	<tr>
		<td>`deregistration_delay.timeout_seconds`</td>
		<td>**30** (mc-tg-web · mc-tg-was 동일)</td>
	</tr>
	<tr>
		<td>상태 흐름</td>
		<td>`healthy` → (제거) `draining` 최대 30s → `unused`</td>
	</tr>
	<tr>
		<td>어디서 쓰이나</td>
		<td>Terraform attachment 삭제 · ASG 축소/새로 고침(10단계) · 콘솔 "등록 취소"</td>
	</tr>
	<tr>
		<td>ASG 와 짝</td>
		<td>WAS 종료 훅 300s 는 드레이닝 **뒤** 로그 sync 용 — 다른 목적</td>
	</tr>
</table>
**없으면 · 오해**
- 0 으로 두면 제거 즉시 연결이 끊겨 사용자가 502/ERR_CONNECTION_RESET 을 본다.
- "unhealthy 도 30초 기다린다" — 아니다. unhealthy 는 즉시 새 요청을 안 보내고 진행 중 요청은 서버가 답하면 답한다(드레이닝 개념은 등록 취소에만).
- 드레이닝은 **대상 그룹**의 속성이다. 로드 밸런서 속성(유휴 60s)과 다르다.

**눈으로 확인**

```bash
# 1) 두 대상 그룹의 등록 취소 지연
for tg in mc-tg-web mc-tg-was; do A=$(aws elbv2 describe-target-groups --names $tg --profile mc-deploy --region ap-northeast-2 --query 'TargetGroups[0].TargetGroupArn' --output text); printf "%s " $tg; aws elbv2 describe-target-group-attributes --target-group-arn $A --profile mc-deploy --region ap-northeast-2 --query 'Attributes[?Key==`deregistration_delay.timeout_seconds`].Value' --output text; done
# 2) 코드 근거 — Terraform 이 이 값을 준다
grep -rn "deregistration_delay" infra/terraform-kdt5/modules/base/alb.tf infra/terraform-kdt5/alb.tf 2>/dev/null
```

기대: 1) `mc-tg-web 30` · `mc-tg-was 30` 2) `deregistration_delay = 30` 류
## 2-5. ⑤ 실패하면 실제로 무슨 일이
**무슨 일이 일어나나**
1. 대상 `unhealthy` → 그 노드는 그 서버로 **새 요청을 안 보냄**(진행 중인 건 끝까지). 정상 대상이 하나라도 남으면 사용자는 모른다(다른 서버가 받음).
2. 정상 대상이 **0** 이면 ALB 가 **503** 을 낸다(로그 `elb 503` · target `-`). CloudFront 는 503 을 받으면 `/maintenance.html` 을 503 으로 대체(9단계).
3. 지표: `HealthyHostCount` · `UnHealthyHostCount`(대상 그룹 차원). 알람: **WAS 만** `mc-was-unhealthy-host`(UnHealthyHostCount ≥ 1 · 1분 × 2 · Maximum) → SNS `mc-alerts`. WEB 용 알람은 없다 — `HealthyHostCount ‹ 2` 알람 추가가 로드맵.
4. 자동 복구: 고정 EC2 방식(지금)은 **사람이** 서버를 고치거나 교체한다. ASG(10단계)면 ELB 헬스체크 실패 → 인스턴스 종료 → 새 인스턴스.
5. 헬스체크로 **못 잡는** 장애: 도장 불일치(403 전면 · 헬스체크는 규칙을 안 거침) · 느린 응답(5s 안에 200 만 오면 통과) · 정적 파일은 되는데 앱만 안 되는 경우(WEB 얕은 체크). 이건 다른 지표(ELB 4XX/5XX · TargetResponseTime)로 본다(8단계).

**우리 값**
<table header-row="true" fit-page-width="true">
	<tr>
		<td>항목</td>
		<td>값 (9/17)</td>
	</tr>
	<tr>
		<td>WEB 대상 상태</td>
		<td>web-a · web-c 둘 다 healthy · `HealthyHostCount` 지난 1h 최소 2</td>
	</tr>
	<tr>
		<td>WAS 대상 상태</td>
		<td>was-a · was-c 둘 다 healthy</td>
	</tr>
	<tr>
		<td>알람</td>
		<td>`mc-was-unhealthy-host`: `AWS/ApplicationELB UnHealthyHostCount` · 차원 `mc-tg-was` + `mc-alb-internal` · ≥1 · 60s × 2 · OK → SNS `mc-alerts`</td>
	</tr>
	<tr>
		<td>WEB 알람</td>
		<td>없음 (로드맵: `HealthyHostCount ‹ 2` 1분 × 2)</td>
	</tr>
	<tr>
		<td>정상 대상 0 일 때</td>
		<td>ALB 503 → CloudFront `/maintenance.html` 503 (오류 캐시 10s)</td>
	</tr>
</table>
**없으면 · 오해**
- WEB 알람이 없으니 WEB 1대가 죽어도 아무도 모른 채 1대로 버틴다 — 남은 1대마저 죽으면 그때 점검 페이지. 알람 추가가 싸고 효과 큰 개선.
- "unhealthy 면 ALB 가 서버를 재시작한다" — 안 한다. 트래픽만 뺀다. 재시작·교체는 ASG 나 사람.
- 모든 대상이 unhealthy 면 ALB 는 **전부에게** 보내기도 한다(fail-open) — 그래도 응답이 없으니 사용자는 실패. "전부 unhealthy 인데 왜 요청이 오지?" 의 답.

**눈으로 확인**

```bash
# 1) 정상/비정상 대상 수 지표 (지난 1시간)
for m in HealthyHostCount UnHealthyHostCount; do printf "%s " $m; aws cloudwatch get-metric-statistics --namespace AWS/ApplicationELB --metric-name $m --dimensions Name=LoadBalancer,Value=app/mc-alb-public/0780e6e7d84abe76 Name=TargetGroup,Value=targetgroup/mc-tg-web/5ae742de9f467369 --start-time $(date -u -d '-1 hour' +%FT%TZ) --end-time $(date -u +%FT%TZ) --period 3600 --statistics Minimum Maximum --profile mc-deploy --region ap-northeast-2 --query 'Datapoints[0].[Minimum,Maximum]' --output text; done
# 2) 알람 — WAS 만 있고 WEB 은 없다
aws cloudwatch describe-alarms --alarm-name-prefix mc- --profile mc-deploy --region ap-northeast-2 --query 'MetricAlarms[].[AlarmName,MetricName,Threshold,StateValue]' --output table
# 3) 정상 대상 0 일 때 사용자가 볼 페이지 — 지금도 열린다
curl -sI https://petclinic.mission-critical.site/maintenance.html | grep -iE "^HTTP|^server"
```

기대: 1) `HealthyHostCount 2.0 2.0` · `UnHealthyHostCount 0.0 0.0` 2) `mc-was-unhealthy-host UnHealthyHostCount 1.0 OK`(+ p95 · rds) · WEB 항목 없음 3) `HTTP/2 200` · `server: AmazonS3`
## 2-6. 장애 하나의 타임라인 — web-a 의 httpd 가 60초 멈추면
<table header-row="true" fit-page-width="true">
	<tr>
		<td>t</td>
		<td>무슨 일</td>
		<td>대상 상태</td>
		<td>사용자</td>
	</tr>
	<tr>
		<td>0s</td>
		<td>`systemctl stop httpd` (web-a)</td>
		<td>healthy (아직 모름)</td>
		<td>web-a 로 간 요청 → 연결 거부 → ALB **502** (절반)</td>
	</tr>
	<tr>
		<td>~0–10s</td>
		<td>다음 헬스체크 실패 1회</td>
		<td>healthy</td>
		<td>계속 절반 502 (또는 CloudFront 점검 페이지)</td>
	</tr>
	<tr>
		<td>~20s</td>
		<td>실패 2회</td>
		<td>healthy</td>
		<td>동일</td>
	</tr>
	<tr>
		<td>**~30s**</td>
		<td>실패 3회 → 판정</td>
		<td>**unhealthy** (`Target.FailedHealthChecks`)</td>
		<td>web-c 만 받음 → **정상**(느낌 없음)</td>
	</tr>
	<tr>
		<td>60s</td>
		<td>`systemctl start httpd`</td>
		<td>unhealthy</td>
		<td>정상</td>
	</tr>
	<tr>
		<td>~70s</td>
		<td>성공 1회</td>
		<td>unhealthy</td>
		<td>정상</td>
	</tr>
	<tr>
		<td>**~80s**</td>
		<td>성공 2회 → 판정</td>
		<td>**healthy**</td>
		<td>다시 2대 분산</td>
	</tr>
	<tr>
		<td>기록</td>
		<td>지표 `UnHealthyHostCount 1` 약 50초 · ALB 로그 `elb 502 · target -` 수 건 · WEB 알람 **없음**</td>
		<td></td>
		<td>9단계에서 실제로 해 본다</td>
	</tr>
</table>
기억할 것 셋: **헬스체크는 진짜 GET**(SG · 경로 · 코드) · **얕게/깊게는 장애를 국소화하려는 선택** · **숫자는 시간이다**(30s 제외 · 20s 복귀 · 30s 드레이닝).
# 3. 용어 — 이 단계에서만 쓰는 것
<table header-row="true" fit-page-width="true">
	<tr>
		<td>용어</td>
		<td>한 줄</td>
		<td>비유</td>
	</tr>
	<tr>
		<td>헬스체크</td>
		<td>로드 밸런서가 대상에게 주기적으로 보내는 확인 요청</td>
		<td>"계세요?" 노크</td>
	</tr>
	<tr>
		<td>healthy · unhealthy · initial · draining · unused</td>
		<td>대상 상태 5가지</td>
		<td>출근 · 결근 · 수습 · 퇴근 준비 · 미배정</td>
	</tr>
	<tr>
		<td>간격 · 타임아웃</td>
		<td>얼마나 자주 묻나 · 얼마나 기다리나</td>
		<td>노크 주기 · 대답 기다리는 시간</td>
	</tr>
	<tr>
		<td>임계값(정상/비정상)</td>
		<td>연속 몇 번 성공/실패해야 판정을 바꾸나</td>
		<td>몇 번 대답 없으면 결근 처리</td>
	</tr>
	<tr>
		<td>얕은 체크 · 깊은 체크</td>
		<td>프로세스만 vs 앱·DB 까지</td>
		<td>불 켜졌나 vs 진료 가능한가</td>
	</tr>
	<tr>
		<td>등록 취소 지연(드레이닝)</td>
		<td>일부러 뺄 때 진행 중 요청을 기다리는 시간</td>
		<td>퇴근 전 보던 환자 마무리</td>
	</tr>
	<tr>
		<td>Reason 코드</td>
		<td>`Target.Timeout` · `Target.ResponseCodeMismatch` · `Target.FailedHealthChecks` …</td>
		<td>결근 사유</td>
	</tr>
	<tr>
		<td>fail-open</td>
		<td>전부 unhealthy 면 전부에게 보내 보는 ALB 동작</td>
		<td>다 결근이면 아무나 불러 봄</td>
	</tr>
</table>
# 4. 왜 이렇게 만들었나 (멘토가 물을 만한 것)
- **왜 WEB 은 정적 파일로 체크하나?** WAS 장애가 WEB 장애로 번지지 않게. WAS 가 죽어도 랜딩·정적·점검 안내는 WEB 이 준다.
- **왜 WAS 는 앱 홈으로 체크하나?** Tomcat 이 떠도 앱이 안 뜨면 의미 없다. `/petclinic/` 200 은 Spring 컨텍스트가 살아 있다는 뜻.
- **왜 10/5/2/3 인가?** 기본값에 가까운 균형. 더 공격적(5/2)이면 오탐, 더 느슨하면 장애 노출이 길다. 실측 문제 없어 유지.
- **왜 등록 취소 30s 인가?** 요청이 짧은 앱이라 충분하고, 교체·축소가 빠르다. 긴 요청이 생기면 늘린다.
- **왜 WEB 알람이 없나?** 초기 구축에서 WAS 만 넣었다. `HealthyHostCount ‹ 2` 알람은 비용 0 에 가까운 개선 — 로드맵 1순위.
- **헬스체크 로그 제외가 왜 안 되나?** httpd.conf 기본 CustomLog 가 남아 있어 두 CustomLog 가 같은 파일에 쓴다. 기본 것을 끄면 해결(web.sh 한 줄 + 인스턴스 교체).
# 5. 다음 단계(6. Apache 프록시) 진입 기준
<details>
<summary>Q1. WEB 헬스체크를 `/petclinic/` 로 바꾸면 어떤 장애 때 손해인가?</summary>
	WAS 만 죽었을 때. Apache 는 살아 있는데도 WEB 2대가 전부 unhealthy 로 빠져 503 이 된다. 얕은 체크면 WEB 은 남아 랜딩·정적·점검 안내가 가능.
</details>
<details>
<summary>Q2. 서버가 죽고 사용자가 영향을 받을 수 있는 최대 시간은? 줄이려면?</summary>
	약 30초(10s 간격 × 비정상 3회) — 그동안 라운드 로빈으로 그 서버에 간 요청(절반)은 502. 줄이려면 임계값·간격을 줄이거나(오탐 증가) 대수를 늘린다(3대면 1/3).
</details>
<details>
<summary>Q3. 등록 취소 지연 30초는 언제 쓰이나? unhealthy 와 무엇이 다른가?</summary>
	인스턴스 교체·축소로 대상을 **일부러** 뺄 때. 새 요청은 즉시 안 보내고 진행 중 요청만 30초까지 마무리시킨다. unhealthy 는 장애 판정이라 지연 개념이 없다.
</details>
<details>
<summary>Q4. 헬스체크는 healthy 인데 사용자는 전부 403 을 본다. 왜 헬스체크가 못 잡나?</summary>
	헬스체크는 노드 → 대상 직접이라 리스너 규칙(도장)을 안 거친다. 도장 불일치(장애 E)는 ALB 4XX 지표·로그 `matched_rule_priority 0` 으로 본다.
</details>
# 6. 읽을 자료
- AWS 문서 — *Health checks for your target groups* (상태 · Reason · 실패 시 동작)
- AWS 문서 — *Deregistration delay* · *Target group attributes*
- Apache 문서 — *mod_log_config* `CustomLog … env=` · *mod_setenvif* (오늘 발견의 원리)
- 콘솔 구축 가이드 **4-2 · ⑥** 절
<callout icon="🗺️" color="gray_bg">
	**로드맵 위치**: 0 VPC 입구 → 1 HTTP 기초 → 2 TLS 종료 지점 → 3 ALB 해부 → 4 오리진 보호(헤더) → **5 헬스체크(이 페이지)** → 6 Apache 프록시 → 7 분산·타임아웃 → 8 WEB 관측 → 9 장애 모드 → 10 ASG·AMI.
</callout>
