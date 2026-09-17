<callout icon="⏱️" color="blue_bg">
	**이 단계의 목표**: 요청이 두 WEB 중 어디로 가는지(분산)와 연결이 언제 끊기는지(타임아웃)를 CloudFront · ALB · Apache · Internal ALB · Tomcat 다섯 곳의 값으로 맞춰 본다. 값이 어긋나면 나는 502·504 의 원인이 여기. 반나절 분량. 값은 2026-09-17 mc-deploy 실측(서버 안 값은 코드 근거 · 미확인 표시).
</callout>
# 0. 그림 한 장

```text
CloudFront ──연결 3회×10s · 응답 30s · keep-alive 5s──▶ ALB(유휴 60s) ──① round_robin · 교차 영역 on──▶ Apache(Timeout 60 · KeepAliveTimeout 5 · 기본값) ──▶ Internal ALB(유휴 60s) ──▶ Tomcat(connectionTimeout 20s · 기본값)
      연결 A                                      연결 B                                  연결 C                                   연결 D
  ② 스티키 off · slow start 0      ③ 연결은 네 개, keep-alive 는 각각      ④ 타임아웃 다섯 곳 — 뒤가 앞보다 먼저 끊으면 502      ⑤ 코드로 역추적: 504 는 30/60s, 502 는 끊김, 503 은 대상 0
```

두 질문만 기억한다: **"누가 받나"**(①②) 와 **"언제 끊기나"**(③④). 나머지(⑤)는 그 둘을 상태 코드로 거꾸로 읽는 법.
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
		<td>누가 받나 — 알고리즘 · 교차 영역</td>
		<td>정상 대상에 **번갈아**(round_robin). 교차 영역 on 이라 2c 노드가 2a 서버로도 보냄 → AZ 별 대수가 달라도 균등</td>
		<td>`round_robin` · `cross_zone on` · 오늘 로그: 2c 노드(`3.34.116.99`) → `10.0.10.189`(web-a · 2a) 와 `10.0.11.89`(web-c · 2c) 둘 다</td>
	</tr>
	<tr>
		<td>②</td>
		<td>스티키 · slow start · HTTP/2</td>
		<td>같은 사용자를 같은 서버에 묶지 않음(무상태 앱) · 새 대상에 처음부터 100% · HTTP/2 는 뷰어 쪽만</td>
		<td>`stickiness false` · `slow_start 0` · `routing.http2 true`(오리진 쪽은 항상 1.1)</td>
	</tr>
	<tr>
		<td>③</td>
		<td>연결은 네 개, keep-alive 는 각각</td>
		<td>CloudFront↔ALB · ALB↔Apache · Apache↔Internal ALB · Internal ALB↔Tomcat. 각 구간이 "얼마나 놀면 끊을지" 를 따로 정한다</td>
		<td>A keep-alive **5s** · B ALB 유휴 **60s** / Apache 5s(기본) · C Apache 프록시 재사용 / Internal ALB 유휴 **60s** · D Tomcat 20s(기본)</td>
	</tr>
	<tr>
		<td>④</td>
		<td>타임아웃 다섯 곳</td>
		<td>**뒤쪽이 앞쪽보다 먼저 끊으면** 앞쪽이 닫힌 연결에 요청을 써서 502. AWS 권고: 대상 keep-alive › ALB 유휴</td>
		<td>CloudFront 30s(응답) · ALB 60s · Apache `KeepAliveTimeout 5`(**권고 위반 · 서버 미확인**) · Internal ALB 60s · Tomcat 20s(**권고 위반 · 미확인**) — 실측 5XX 0</td>
	</tr>
	<tr>
		<td>⑤</td>
		<td>코드로 역추적</td>
		<td>504 = 누군가 기다리다 포기(30s CloudFront / 60s ALB) · 502 = 연결이 이상하게 끊김 · 503 = 정상 대상 0</td>
		<td>지난 24h `ELB_5XX 0` · `Target_5XX 0` · p95 알람 임계 2s(OK)</td>
	</tr>
</table>
# 2. 자세히 — 항목마다 "무슨 일 · 우리 값 · 없으면 · 눈으로 확인"
## 2-1. ① 누가 받나 — round_robin 과 교차 영역
**무슨 일이 일어나나**
1. 대상 그룹 알고리즘 `round_robin`: 노드가 **정상(healthy) 대상 목록**을 돌아가며 고른다. 요청 단위이지 연결 단위가 아니다 — 같은 keep-alive 연결로 온 두 요청이 다른 서버로 갈 수 있다.
2. **교차 영역(cross-zone) on**: 2a 노드가 받은 요청을 2c 서버로도 보낸다(반대도). off 면 노드는 자기 AZ 서버에게만 → AZ 별 대수가 다르면 불균형, 자기 AZ 서버가 전멸하면 그 노드는 503. ALB 는 기본 on(무료) 이라 그대로 둔다.
3. 대안 `least_outstanding_requests`: 처리 중 요청이 가장 적은 서버로. 요청 처리 시간이 들쭉날쭉(리포트 · 업로드)하면 이쪽이 낫다. 우리 앱은 짧고 균일해 round_robin 으로 충분.
4. 실측: 오늘 로그에서 2c 노드(`3.34.116.99`)가 web-a(`10.0.10.189` · 2a)와 web-c(`10.0.11.89` · 2c) 둘 다에게 보냈다 — 교차 영역의 증거. Apache 로그엔 `10.0.0.212`(2a 노드)와 `10.0.1.212`(2c 노드)가 섞여 온다.

**우리 값**
<table header-row="true" fit-page-width="true">
	<tr>
		<td>항목</td>
		<td>값</td>
		<td>근거</td>
	</tr>
	<tr>
		<td>알고리즘</td>
		<td>`round_robin` (mc-tg-web · mc-tg-was)</td>
		<td>대상 그룹 속성</td>
	</tr>
	<tr>
		<td>교차 영역</td>
		<td>ALB `load_balancing.cross_zone.enabled true` · 대상 그룹 `use_load_balancer_configuration`</td>
		<td>로드 밸런서 · 대상 그룹 속성</td>
	</tr>
	<tr>
		<td>실측 — 노드 → 대상</td>
		<td>`3.34.116.99`(2c) → `10.0.10.189:80`(web-a) · `3.34.116.99`(2c) → `10.0.11.89:80`(web-c)</td>
		<td>ALB 로그 ip_address · target 필드</td>
	</tr>
	<tr>
		<td>실측 — 서버가 보는 노드</td>
		<td>Apache 로그 첫 IP `10.0.0.212` / `10.0.1.212` 번갈아</td>
		<td>`/mc/web/access`</td>
	</tr>
</table>
**없으면 · 오해**
- 교차 영역 off + web-c 만 살아 있으면 2a 노드로 온 요청의 절반이 503 — DNS 는 여전히 두 노드를 주므로.
- "라운드 로빈이니 정확히 50:50" — 요청 단위 순환이라 짧은 구간에선 치우칠 수 있고, keep-alive 재사용·헬스체크 제외 등으로 완전 균등은 아니다. 하루 단위로 보면 균등.
- 서버별 응답 차이를 보려면 응답 헤더에 서버 이름을 넣는 방법(`Header set X-Served-By "%｛HOSTNAME｝e"`)이 있다 — 로드맵. 지금은 ALB 로그 target 필드로 본다.

**눈으로 확인**

```bash
TG=$(aws elbv2 describe-target-groups --names mc-tg-web --profile mc-deploy --region ap-northeast-2 --query 'TargetGroups[0].TargetGroupArn' --output text)
ALB=$(aws elbv2 describe-load-balancers --names mc-alb-public --profile mc-deploy --region ap-northeast-2 --query 'LoadBalancers[0].LoadBalancerArn' --output text)
# 1) 알고리즘 · 교차 영역
aws elbv2 describe-target-group-attributes --target-group-arn $TG --profile mc-deploy --region ap-northeast-2 --query 'Attributes[?Key==`load_balancing.algorithm.type`||Key==`load_balancing.cross_zone.enabled`].[Key,Value]' --output table
aws elbv2 describe-load-balancer-attributes --load-balancer-arn $ALB --profile mc-deploy --region ap-northeast-2 --query 'Attributes[?Key==`load_balancing.cross_zone.enabled`].Value' --output text
# 2) 분산 실측 — 오늘 ALB 로그에서 (노드 IP, 대상) 조합 세기 (34번째 필드 = 노드 · 5번째 = 대상)
for K in $(aws s3 ls s3://mc-logs-528821350786/alb/public/ --recursive --profile mc-deploy | grep -v TestFile | grep "$(date -u +%Y/%m/%d)" | awk '{print $4}'); do aws s3 cp "s3://mc-logs-528821350786/$K" - --profile mc-deploy | zcat; done | awk -F'"' '{split($1,h," "); n=split($0,w," "); print "node="w[n-2]" target="h[5]}' | sort | uniq -c
# 3) 서버 쪽 — 두 노드 IP 가 섞여 오는지
aws logs tail /mc/web/access --since 1h --profile mc-deploy --region ap-northeast-2 --format short | grep -v ELB-HealthChecker | awk '{print $2}' | sort | uniq -c
```

기대: 1) `round_robin` · `use_load_balancer_configuration` · `true` 2) `node=3.34.116.99 target=10.0.10.189:80`(2c 노드 → 2a 서버 = 교차) · `node=13.124.71.239 target=10.0.11.89:80`(2a 노드 → 2c 서버) 등 네 조합 전부 3) `10.0.0.212` 와 `10.0.1.212` 둘 다
## 2-2. ② 스티키 · slow start · HTTP/2 — 끄고 0 이고 뷰어만
**무슨 일이 일어나나**
1. **스티키 세션**: 켜면 ALB 가 쿠키(`AWSALB`)를 심어 같은 클라이언트를 같은 서버로 보낸다. 서버 메모리에 세션(로그인 상태)을 두는 앱에 필요. PetClinic 은 세션에 의존하지 않는 **무상태** 앱이라 끈다. 켜면 CloudFront 엣지 몇 개가 특정 서버로 쏠려 분산이 깨진다(뷰어가 CloudFront 뿐이라 쿠키 기준이 엣지 단위).
2. **slow start(0)**: 새 대상이 healthy 가 되면 즉시 100% 트래픽. JVM(WAS)처럼 워밍업(JIT · 커넥션 풀)이 필요하면 30~60s 를 주어 서서히 늘린다 — WAS 대상 그룹의 로드맵.
3. **HTTP/2**: ALB `routing.http2.enabled true` 는 **뷰어와의** 얘기. 우리 뷰어는 CloudFront 뿐이고 CloudFront 는 오리진에 **HTTP/1.1** 로만 붙는다. 그래서 켜져 있어도 실제 사용은 없다(무해). 오리진 쪽 HTTP/2 는 ALB 대상 그룹 프로토콜 버전 `HTTP2`(gRPC 용)로 따로.
4. 세션이 필요해지면(로그인 기능): 스티키보다 **세션 저장소를 밖으로**(ElastiCache Redis) 빼는 게 정석 — 서버가 죽어도 로그인 유지. 멘토링 질문지 항목.

**우리 값**
<table header-row="true" fit-page-width="true">
	<tr>
		<td>항목</td>
		<td>값</td>
		<td>뜻</td>
	</tr>
	<tr>
		<td>`stickiness.enabled`</td>
		<td>false (web · was)</td>
		<td>무상태 앱 · 균등 분산</td>
	</tr>
	<tr>
		<td>`slow_start.duration_seconds`</td>
		<td>0 (web · was)</td>
		<td>즉시 100%. WAS 는 30~60s 고려(로드맵)</td>
	</tr>
	<tr>
		<td>`routing.http2.enabled`</td>
		<td>true</td>
		<td>뷰어용 · CloudFront→ALB 는 1.1(로그 `HTTP/1.1`)</td>
	</tr>
	<tr>
		<td>CloudFront 뷰어</td>
		<td>`http2and3`</td>
		<td>브라우저↔엣지는 HTTP/2·3</td>
	</tr>
</table>
**없으면 · 오해**
- 스티키를 켜면 "한 서버만 바쁘다" 는 신고가 온다 — CloudFront 엣지 단위로 묶이기 때문. 뷰어가 브라우저 직접인 구조와 다르다.
- "HTTP/2 를 켰는데 Apache 로그가 1.1" 은 정상(1단계 ①).
- slow start 를 WAS 에 켜면 새 인스턴스 헬스체크 통과 후에도 트래픽이 서서히 늘어 ASG 확장 효과가 늦게 나타난다 — 값은 30s 정도로.

**눈으로 확인**

```bash
# 1) 두 대상 그룹의 스티키 · slow start
for tg in mc-tg-web mc-tg-was; do A=$(aws elbv2 describe-target-groups --names $tg --profile mc-deploy --region ap-northeast-2 --query 'TargetGroups[0].TargetGroupArn' --output text); printf "%s " $tg; aws elbv2 describe-target-group-attributes --target-group-arn $A --profile mc-deploy --region ap-northeast-2 --query 'Attributes[?Key==`stickiness.enabled`||Key==`slow_start.duration_seconds`].Value' --output text; done
# 2) 스티키가 꺼져 있으니 ALB 가 쿠키를 안 심는다 — 응답에 AWSALB 쿠키 없음
curl -sI https://petclinic.mission-critical.site/petclinic/vets | grep -ic "set-cookie: AWSALB"
# 3) 오리진 쪽 버전은 1.1 — ALB 로그 요청줄
K=$(aws s3 ls s3://mc-logs-528821350786/alb/public/ --recursive --profile mc-deploy | grep -v TestFile | tail -1 | awk '{print $4}')
aws s3 cp "s3://mc-logs-528821350786/$K" - --profile mc-deploy | zcat | tail -1 | awk -F'"' '{print $2}'
```

기대: 1) `mc-tg-web 0 false` · `mc-tg-was 0 false`(순서는 키 정렬) 2) `0` 3) `GET https://petclinic.mission-critical.site:443/… HTTP/1.1`
## 2-3. ③ 연결은 네 개 — keep-alive 는 구간마다
**무슨 일이 일어나나**
1. 요청 하나가 지나는 TCP 연결은 **네 개**(A~D)다. 각각 독립적으로 열리고, 재사용(keep-alive)되고, 닫힌다. 브라우저↔CloudFront 까지 세면 다섯.
2. **A CloudFront→ALB**: 엣지가 ALB 노드로 연 연결. `OriginKeepaliveTimeout 5s` — 5초 놀면 CloudFront 가 닫고 다음 요청 때 새로 연다(TLS 핸드셰이크 비용). 트래픽이 많으면 60s 로 늘려 재사용률을 높인다(로드맵).
3. **B ALB→Apache**: 노드가 대상으로 연 평문 연결. ALB 유휴 60s. Apache 쪽은 `KeepAliveTimeout`(기본 5s) · `MaxKeepAliveRequests`(기본 100). **Apache 가 먼저 닫는다**(5 ‹ 60).
4. **C Apache→Internal ALB**: mod_proxy_http 가 연 연결(워커별 재사용). Internal ALB 유휴 60s.
5. **D Internal ALB→Tomcat**: Tomcat HTTP 커넥터 `connectionTimeout`(server.xml 기본 20000ms = 20s) · `keepAliveTimeout`(기본 = connectionTimeout). was.sh 가 server.xml 을 안 건드리므로 기본값 — **Tomcat 이 먼저 닫는다**(20 ‹ 60). 미확인(서버).
6. "먼저 닫는 쪽" 이 뒤(대상)면 위험: 앞(ALB)이 닫힌 줄 모르고 요청을 쓰면 실패 → ALB 는 이를 감지해 **한 번 재시도**하기도 하지만 보장은 없다 → 502. 그래서 AWS 권고는 **대상 keep-alive › ALB 유휴**.

**우리 값**
<table header-row="true" fit-page-width="true">
	<tr>
		<td>연결</td>
		<td>앞쪽 값</td>
		<td>뒤쪽 값</td>
		<td>누가 먼저 닫나</td>
	</tr>
	<tr>
		<td>A CloudFront → ALB</td>
		<td>keep-alive 5s (실측)</td>
		<td>ALB 유휴 60s (실측)</td>
		<td>앞(CloudFront) — 안전</td>
	</tr>
	<tr>
		<td>B ALB → Apache</td>
		<td>ALB 유휴 60s (실측)</td>
		<td>`KeepAliveTimeout 5` · `Timeout 60` · `MaxKeepAliveRequests 100` (httpd 기본 · web.sh 미변경 · **서버 미확인**)</td>
		<td>**뒤(Apache)** — 권고 위반</td>
	</tr>
	<tr>
		<td>C Apache → Internal ALB</td>
		<td>mod_proxy 재사용(기본 on)</td>
		<td>Internal ALB 유휴 60s (실측)</td>
		<td>뒤(ALB) 가 60s — Apache 워커는 요청 때만 쓰므로 실질 안전</td>
	</tr>
	<tr>
		<td>D Internal ALB → Tomcat</td>
		<td>Internal ALB 유휴 60s (실측)</td>
		<td>`connectionTimeout 20000` (Tomcat 9 server.xml 기본 · was.sh 미변경 · **미확인**)</td>
		<td>**뒤(Tomcat)** — 권고 위반</td>
	</tr>
</table>
**없으면 · 오해**
- B·D 가 권고와 어긋나지만 실측 5XX 0 — 트래픽이 적어 유휴 연결이 거의 없고, ALB 가 닫힌 연결을 만나면 재시도하기 때문. 부하 테스트(Phase 3)에서 502 가 산발적으로 나오면 **이 표부터** 본다.
- 고치는 값: Apache `KeepAliveTimeout 75`(ALB 60 + 여유) · Tomcat `keepAliveTimeout="65000"`(ms) — 둘 다 user_data 한 줄 + 인스턴스 교체. 로드맵.
- "keep-alive 를 끄면 안전" — 502 는 줄지만 매 요청 새 연결(지연 · 소켓 낭비). 값을 맞추는 게 답(1단계 ④).

**눈으로 확인**

```bash
# 1) A — CloudFront 오리진 keep-alive · 응답 대기 · 연결 시도/제한
aws cloudfront get-distribution-config --id E2PWXW3LUYTDEE --profile mc-deploy --query 'DistributionConfig.Origins.Items[?Id==`alb-public`].[CustomOriginConfig.OriginKeepaliveTimeout,CustomOriginConfig.OriginReadTimeout,ConnectionAttempts,ConnectionTimeout]' --output text
# 2) B·D 앞쪽 — 두 ALB 의 유휴 타임아웃
for n in mc-alb-public mc-alb-internal; do printf "%s " $n; aws elbv2 describe-load-balancer-attributes --load-balancer-arn $(aws elbv2 describe-load-balancers --names $n --profile mc-deploy --region ap-northeast-2 --query 'LoadBalancers[0].LoadBalancerArn' --output text) --profile mc-deploy --region ap-northeast-2 --query 'Attributes[?Key==`idle_timeout.timeout_seconds`].Value' --output text; done
# 3) B·D 뒤쪽 — 코드 근거: web.sh / was.sh 가 KeepAlive · Connector 를 안 건드린다
grep -nE "KeepAlive|^Timeout" infra/terraform-kdt5/modules/base/user_data/web.sh || echo "web.sh: 없음 → httpd 기본값(KeepAliveTimeout 5 · Timeout 60)"
grep -nE "connectionTimeout|keepAliveTimeout|Connector" infra/terraform-kdt5/modules/base/user_data/was.sh || echo "was.sh: 없음 → Tomcat 기본값(connectionTimeout 20000)"
# 4) 서버에서 직접 (Bastion 허용 후) — 아무것도 안 나오면 기본값
#   ssh … ec2-user@10.0.10.189 'grep -rhE "^\s*(Timeout|KeepAlive|KeepAliveTimeout|MaxKeepAliveRequests)\b" /etc/httpd/conf /etc/httpd/conf.d'
#   ssh … ec2-user@10.0.20.53  'grep -n "Connector port=\"8080\"" -A3 /opt/tomcat/conf/server.xml'
```

기대: 1) `5 30 3 10` 2) `mc-alb-public 60` · `mc-alb-internal 60` 3) 두 줄 다 "없음 → 기본값" 4) (Bastion 후)
## 2-4. ④ 타임아웃 다섯 곳 — 한 줄에 놓고 읽기
**무슨 일이 일어나나**
1. 타임아웃은 두 종류다. **유휴(idle)**: 데이터가 안 오가는 시간 상한(연결 재사용용 · ③). **응답 대기(read)**: 요청을 보낸 뒤 **첫 바이트**를 기다리는 상한(느린 서버 감지용). 헷갈리면 502/504 진단이 꼬인다.
2. **CloudFront 응답 대기 30s**: ALB 가 30초 안에 응답 헤더를 안 주면 CloudFront 가 **504** 를 만들어 사용자에게(→ 점검 페이지). 이때 ALB↔서버는 계속 처리 중(낭비). 연결 자체가 안 되면 10s × 3회 뒤 다른 노드.
3. **ALB 유휴 60s**: 클라이언트·대상 양쪽 연결에서 60초 동안 데이터가 없으면 ALB 가 끊는다. 대상이 60초 안에 아무 바이트도 안 주면 **504**(ALB 가 낸 것 · 로그 elb 504 · target `-`).
4. **Apache Timeout 60**: 한 요청의 I/O 가 60초 멈추면 Apache 가 끊는다. ALB 60 과 같아 애매 — 누가 먼저 판단하는지 경쟁. 65~70 으로 두면 ALB 가 먼저 504 를 내고 Apache 는 뒤처리만.
5. **Internal ALB 60 · Tomcat connectionTimeout 20s**: Tomcat 의 20s 는 "요청 줄을 받기까지" 기다리는 시간(=유휴). 처리 중 요청엔 적용 안 됨. 느린 DB 쿼리는 Tomcat 이 기다려 주고, 대신 Internal ALB(60) 나 CloudFront(30)가 먼저 포기한다.
6. 순서대로 놓으면: **CloudFront 30s 가 가장 먼저 포기**한다. 즉 사용자가 보는 504 는 거의 CloudFront 의 것. ALB 504 는 CloudFront 30s 보다 늦어 사용자에겐 안 보인다(CloudFront 가 이미 504 를 줬음).

**우리 값 — 한 줄**

```text
CloudFront ──(연결 10s×3 · 응답 30s · keep-alive 5s)──▶ ALB ──(유휴 60s)──▶ Apache ──(Timeout 60 · KeepAliveTimeout 5 · 기본값)──▶ Internal ALB ──(유휴 60s)──▶ Tomcat ──(connectionTimeout 20s · 기본값)──▶ RDS Proxy(연결 대기 · 풀)
```

<table header-row="true" fit-page-width="true">
	<tr>
		<td>지점</td>
		<td>값</td>
		<td>종류</td>
		<td>넘으면 누가 뭘 내나</td>
	</tr>
	<tr>
		<td>CloudFront 오리진 응답</td>
		<td>**30s**</td>
		<td>응답 대기</td>
		<td>CloudFront **504** → 점검 페이지(오류 캐시 10s)</td>
	</tr>
	<tr>
		<td>CloudFront 오리진 연결</td>
		<td>10s × 3회</td>
		<td>연결</td>
		<td>다른 노드 IP 로 재시도 → 전부 실패면 504/502</td>
	</tr>
	<tr>
		<td>ALB 유휴</td>
		<td>**60s**</td>
		<td>유휴(양쪽)</td>
		<td>ALB **504**(대상 무응답) — 사용자에겐 CloudFront 30s 가 먼저</td>
	</tr>
	<tr>
		<td>Apache KeepAliveTimeout / Timeout</td>
		<td>5s / 60s (기본 · 미확인)</td>
		<td>유휴 / I/O</td>
		<td>keep-alive 불일치 → ALB **502** 가능 · Timeout 은 ALB 와 동률</td>
	</tr>
	<tr>
		<td>Internal ALB 유휴</td>
		<td>60s</td>
		<td>유휴</td>
		<td>Internal ALB 504 → Apache 가 그대로 → 사용자 504(CloudFront 가 이미 30s 에)</td>
	</tr>
	<tr>
		<td>Tomcat connectionTimeout</td>
		<td>20s (기본 · 미확인)</td>
		<td>유휴</td>
		<td>Tomcat 이 먼저 닫음 → Internal ALB 502 가능</td>
	</tr>
</table>
**없으면 · 오해**
- CloudFront 30s 를 늘리면(최대 60s · 지원 요청 시 180s) 느린 페이지가 통과하지만, 그만큼 장애 때 사용자 대기도 길어진다. 30s 안에 못 주는 페이지는 앱을 고치는 게 답.
- "504 면 서버가 죽었다" — 죽은 게 아니라 **느린** 것(DB 잠금 · GC · 외부 호출). 죽었으면 502/503.
- 타임아웃을 전부 크게 잡으면 느린 요청이 연결과 스레드를 오래 잡아 **폭주 때 전체가 멈춘다**(Tomcat maxThreads 소진). 타임아웃은 방어선이다.

**눈으로 확인**

```bash
# 1) 다섯 값 한 번에 (서버 안 두 개는 코드 근거)
aws cloudfront get-distribution-config --id E2PWXW3LUYTDEE --profile mc-deploy --query 'DistributionConfig.Origins.Items[?Id==`alb-public`].CustomOriginConfig.[OriginReadTimeout,OriginKeepaliveTimeout]' --output text
for n in mc-alb-public mc-alb-internal; do printf "%s idle=" $n; aws elbv2 describe-load-balancer-attributes --load-balancer-arn $(aws elbv2 describe-load-balancers --names $n --profile mc-deploy --region ap-northeast-2 --query 'LoadBalancers[0].LoadBalancerArn' --output text) --profile mc-deploy --region ap-northeast-2 --query 'Attributes[?Key==`idle_timeout.timeout_seconds`].Value' --output text; done
# 2) 지금 실제 응답 시간 — ALB 로그의 세 처리 시간 (요청/대상/응답)
K=$(aws s3 ls s3://mc-logs-528821350786/alb/public/ --recursive --profile mc-deploy | grep -v TestFile | tail -1 | awk '{print $4}')
aws s3 cp "s3://mc-logs-528821350786/$K" - --profile mc-deploy | zcat | grep -v health.html | awk '{print $6, $7, $8, $9}' | tail -5
# 3) 지표 — 대상 응답 시간 p95 (지난 1시간) · 알람 임계 2s
aws cloudwatch get-metric-statistics --namespace AWS/ApplicationELB --metric-name TargetResponseTime --dimensions Name=LoadBalancer,Value=app/mc-alb-public/0780e6e7d84abe76 --start-time $(date -u -d '-1 hour' +%FT%TZ) --end-time $(date -u +%FT%TZ) --period 3600 --extended-statistics p95 --profile mc-deploy --region ap-northeast-2 --query 'Datapoints[0].ExtendedStatistics.p95' --output text
```

기대: 1) `30 5` · `mc-alb-public idle=60` · `mc-alb-internal idle=60` 2) `0.001 0.363 0.000 200` 류(초 단위 · 두 번째가 대상 처리 시간) 3) `0.35` 정도(초 · 임계 2 에 한참 미달 · 오늘 실측 p95 0.35s)
## 2-5. ⑤ 코드로 역추적 — 사용자가 본 숫자에서 원인으로
**무슨 일이 일어나나**
1. 5xx 중 **502 · 503 · 504 는 중간(ALB · CloudFront)이 낸다**. 누가 냈는지는 ALB 로그의 `elb_status_code` 와 `target_status_code` 가 다르면 ALB, ALB 로그에 없거나 200 인데 사용자는 5xx 면 CloudFront(8단계).
2. **504 = 기다리다 포기**: CloudFront 30s(사용자가 봄) · ALB 60s(로그) · Internal ALB 60s. 원인 후보는 느린 WAS(DB 잠금 · GC · 외부 API). 지표 `TargetResponseTime p95` 와 RDS `slowquery` 로그.
3. **502 = 연결이 이상하게 끊김/이상한 응답**: 대상이 연결을 먼저 닫음(keep-alive 불일치 · 프로세스 재시작 중) · 응답 형식 오류 · 대상 연결 거부(httpd 죽음 · 헬스체크 판정 전 30s). ALB 로그 `error_reason` 필드.
4. **503 = 보낼 대상 없음**: 정상 대상 0(5단계) · 대상 그룹 비어 있음 · (WAS 쪽 503 을 Apache 가 그대로 전달한 경우는 target 503 이라 구분됨).
5. 사용자 화면: 502·503·504 는 CloudFront 가 **점검 페이지(503)** 로 바꾼다. 그래서 사용자 신고는 항상 "점검 페이지가 떠요" — 진짜 코드는 ALB 로그·CloudFront 로그에서 찾는다(9단계).

**우리 값 — 진단표**
<table header-row="true" fit-page-width="true">
	<tr>
		<td>사용자가 본 것</td>
		<td>누가 냈나</td>
		<td>원인 후보</td>
		<td>어디서 확인</td>
	</tr>
	<tr>
		<td>점검 페이지 (원래 504)</td>
		<td>CloudFront (30s) 또는 ALB (60s)</td>
		<td>WAS 느림(DB 쿼리 · GC) · Internal ALB 뒤 응답 없음</td>
		<td>`TargetResponseTime p95` · ALB 로그 target_processing_time · RDS slowquery</td>
	</tr>
	<tr>
		<td>점검 페이지 (원래 502)</td>
		<td>ALB</td>
		<td>Apache 가 연결을 먼저 닫음(keep-alive 5 ‹ 60) · httpd 재시작 중 · 응답 깨짐</td>
		<td>ALB 로그 `elb 502 · target -` · `error_reason` · `/mc/web/error`</td>
	</tr>
	<tr>
		<td>점검 페이지 (원래 503)</td>
		<td>ALB</td>
		<td>정상 대상 0 (WEB 2대 unhealthy)</td>
		<td>`HealthyHostCount 0` · 대상 상태 Reason</td>
	</tr>
	<tr>
		<td>느리지만 성공</td>
		<td>—</td>
		<td>30s 안에 응답 · 사용자 체감</td>
		<td>p95 알람 `mc-alb-p95-latency`(› 2s · 3분)</td>
	</tr>
	<tr>
		<td>지난 24h 실측</td>
		<td>`ELB_5XX 0` · `Target_5XX 0` · `RequestCount 206`</td>
		<td>—</td>
		<td>CloudWatch</td>
	</tr>
</table>
**없으면 · 오해**
- 502 와 504 를 뭉뚱그려 "서버 장애" 로 보면 원인이 정반대(끊김 vs 느림)라 엉뚱한 곳을 고친다.
- CloudFront 가 낸 504 는 **ALB 로그엔 200 이 찍힐 수 있다**(ALB 는 뒤늦게 성공) — 두 로그의 시각을 맞춰 봐야 한다(8단계).
- p95 알람은 트래픽이 없으면 `INSUFFICIENT_DATA` — 장애가 아니라 데이터 없음.

**눈으로 확인**

```bash
# 1) 지난 24시간 5xx — ALB 가 낸 것 · 대상이 낸 것 · 총 요청
for m in HTTPCode_ELB_5XX_Count HTTPCode_Target_5XX_Count RequestCount; do printf "%s " $m; aws cloudwatch get-metric-statistics --namespace AWS/ApplicationELB --metric-name $m --dimensions Name=LoadBalancer,Value=app/mc-alb-public/0780e6e7d84abe76 --start-time $(date -u -d '-24 hour' +%FT%TZ) --end-time $(date -u +%FT%TZ) --period 86400 --statistics Sum --profile mc-deploy --region ap-northeast-2 --query 'Datapoints[0].Sum' --output text; done
# 2) 오늘 로그에서 elb 코드 ≠ target 코드인 줄 (ALB 가 스스로 낸 응답) — 없어야
for K in $(aws s3 ls s3://mc-logs-528821350786/alb/public/ --recursive --profile mc-deploy | grep -v TestFile | grep "$(date -u +%Y/%m/%d)" | awk '{print $4}'); do aws s3 cp "s3://mc-logs-528821350786/$K" - --profile mc-deploy | zcat; done | awk '$9 != $10' | wc -l
# 3) 알람 상태
aws cloudwatch describe-alarms --alarm-names mc-alb-p95-latency --profile mc-deploy --region ap-northeast-2 --query 'MetricAlarms[0].[StateValue,Threshold,EvaluationPeriods]' --output text
```

기대: 1) `None None 206`(None = 0) 2) `0` 3) `OK 2.0 3`(트래픽 없으면 `INSUFFICIENT_DATA`)
## 2-6. 한 요청의 시계 — 느린 요청 하나가 겪는 일 (가정: WAS 가 40초 걸리는 쿼리)
<table header-row="true" fit-page-width="true">
	<tr>
		<td>t</td>
		<td>어디</td>
		<td>무슨 일</td>
		<td>기록</td>
	</tr>
	<tr>
		<td>0s</td>
		<td>브라우저 → CloudFront → ALB(round_robin → web-c) → Apache → Internal ALB → Tomcat</td>
		<td>요청 도착 · Tomcat 이 DB 쿼리 시작</td>
		<td>—</td>
	</tr>
	<tr>
		<td>5s</td>
		<td>CloudFront↔ALB 연결 A</td>
		<td>keep-alive 5s 는 **유휴** 기준 — 응답 대기 중이라 안 끊김</td>
		<td>—</td>
	</tr>
	<tr>
		<td>20s</td>
		<td>Tomcat</td>
		<td>connectionTimeout 20s 도 유휴 기준 — 처리 중이라 안 끊김</td>
		<td>—</td>
	</tr>
	<tr>
		<td>**30s**</td>
		<td>CloudFront</td>
		<td>응답 대기 30s 초과 → **504** 생성 → 점검 페이지(503)로 대체해 사용자에게</td>
		<td>CloudFront 로그 504 · 사용자 "점검 페이지"</td>
	</tr>
	<tr>
		<td>30~40s</td>
		<td>ALB · Apache · Tomcat</td>
		<td>아무도 모른 채 계속 처리(낭비)</td>
		<td>—</td>
	</tr>
	<tr>
		<td>40s</td>
		<td>Tomcat → … → ALB</td>
		<td>200 완성 · ALB 는 CloudFront 에 보내려 하나 연결이 이미 닫힘</td>
		<td>ALB 로그 `200 200 · target_processing 40.0` (사용자는 못 봄)</td>
	</tr>
	<tr>
		<td>만약 70s</td>
		<td>ALB</td>
		<td>60s 동안 대상에서 한 바이트도 없었다면 ALB 가 **504** (CloudFront 30s 뒤라 사용자 화면은 그대로)</td>
		<td>ALB 로그 `504 -`</td>
	</tr>
</table>
기억할 것 셋: **누가 받나 = round_robin + 교차 영역** · **연결은 네 개, 뒤가 먼저 끊으면 502** · **가장 먼저 포기하는 건 CloudFront 30s — 사용자의 504 는 거의 그것**.
# 3. 용어 — 이 단계에서만 쓰는 것
<table header-row="true" fit-page-width="true">
	<tr>
		<td>용어</td>
		<td>한 줄</td>
		<td>비유</td>
	</tr>
	<tr>
		<td>round_robin · least_outstanding_requests</td>
		<td>번갈아 vs 한가한 쪽으로</td>
		<td>순번 vs 빈 창구</td>
	</tr>
	<tr>
		<td>교차 영역 분산</td>
		<td>노드가 다른 AZ 대상에게도 보냄</td>
		<td>1층 데스크가 2층 진료실로도</td>
	</tr>
	<tr>
		<td>스티키 세션</td>
		<td>같은 클라이언트를 같은 서버로(쿠키)</td>
		<td>지정 담당의</td>
	</tr>
	<tr>
		<td>slow start</td>
		<td>새 대상에 트래픽을 서서히</td>
		<td>신입 첫 주 환자 수 조절</td>
	</tr>
	<tr>
		<td>유휴 타임아웃</td>
		<td>데이터가 안 오갈 때 끊기까지</td>
		<td>통화 중 침묵 N초면 끊김</td>
	</tr>
	<tr>
		<td>응답 대기 타임아웃</td>
		<td>첫 바이트를 기다리는 상한</td>
		<td>대답을 기다려 주는 시간</td>
	</tr>
	<tr>
		<td>KeepAliveTimeout · connectionTimeout</td>
		<td>Apache · Tomcat 의 유휴 타임아웃 이름</td>
		<td>같은 개념, 다른 이름</td>
	</tr>
	<tr>
		<td>502 · 503 · 504</td>
		<td>끊김/이상 · 대상 없음 · 느림</td>
		<td>전화가 끊김 · 받을 사람 없음 · 대답이 늦음</td>
	</tr>
</table>
# 4. 왜 이렇게 만들었나 (멘토가 물을 만한 것)
- **왜 round_robin 인가?** 요청이 짧고 균일한 앱. 처리 시간이 들쭉날쭉해지면 least_outstanding_requests 로.
- **왜 스티키를 끄나?** 세션이 없고, 뷰어가 CloudFront 뿐이라 켜면 엣지 단위로 쏠린다. 세션이 생기면 Redis 로 밖에 둔다.
- **왜 CloudFront 응답 대기가 30s 인가?** 기본값. 30초 넘는 페이지는 앱이 고쳐야 할 대상. 늘리면 장애 때 사용자 대기만 길어진다.
- **왜 Apache·Tomcat 기본값을 아직 안 바꿨나?** 실측 5XX 0 · 트래픽 적음. 부하 테스트에서 502 가 보이면 `KeepAliveTimeout 75` · `keepAliveTimeout 65000` 을 넣는다(user_data 한 줄 · 교체 필요).
- **ALB 유휴 60s 를 왜 안 바꾸나?** 기본값이고 CloudFront 30s 가 먼저 포기하므로 사용자 경험엔 영향 없음. 긴 업로드가 생기면 검토.
# 5. 다음 단계(8. WEB 관측) 진입 기준
<details>
<summary>Q1. Apache KeepAliveTimeout 5 · ALB 유휴 60 이면 이론상 무엇이 위험한가? 고치는 값은?</summary>
	Apache 가 유휴 연결을 먼저 닫아, ALB 가 그 연결에 다음 요청을 보냈을 때 502. 권고는 대상 › ALB — `KeepAliveTimeout 75`. Tomcat 도 같은 관계(20s ‹ 60s) → `keepAliveTimeout 65000`.
</details>
<details>
<summary>Q2. 사용자가 504 를 봤다. CloudFront 와 ALB 중 누가 냈는지 어떻게 구분하나?</summary>
	ALB 로그 `elb_status_code` 가 504 면 ALB(60s). ALB 로그에 그 요청이 200(느리게 성공)인데 사용자는 504 면 CloudFront(30s)가 먼저 포기한 것. 대부분 후자 — 30 ‹ 60.
</details>
<details>
<summary>Q3. 스티키 세션을 켜야 하는 앱은? 우리는 왜 안 켜나?</summary>
	서버 메모리에 세션을 두는 앱(로그인 상태). PetClinic 은 세션이 없다. 필요해지면 스티키보다 ElastiCache(Redis)로 세션을 밖으로 빼는 게 낫다 — 서버가 죽어도 유지.
</details>
<details>
<summary>Q4. 교차 영역 분산이 꺼져 있고 web-c 만 살아 있다. 무슨 일이 생기나?</summary>
	DNS 는 여전히 두 노드 IP 를 주므로 2a 노드로 온 요청은 자기 AZ 에 정상 대상이 없어 503 — 절반 실패. 켜져 있으면 2a 노드가 web-c 로 보내 정상.
</details>
# 6. 읽을 자료
- AWS 문서 — *Application Load Balancer idle timeout* · *Cross-zone load balancing* · *Troubleshoot: HTTP 502/504*
- AWS 문서 — *CloudFront origin response timeout / keep-alive timeout*
- Apache 문서 — *KeepAliveTimeout* · *mod_mpm_event* / Tomcat 문서 — *HTTP Connector* (`connectionTimeout` · `keepAliveTimeout`)
- 콘솔 구축 가이드 **2-3 오리진 · 4-3 속성** 절
<callout icon="🗺️" color="gray_bg">
	**로드맵 위치**: 0 VPC 입구 → 1 HTTP 기초 → 2 TLS 종료 지점 → 3 ALB 해부 → 4 오리진 보호(헤더) → 5 헬스체크 → 6 Apache 프록시 → **7 분산·타임아웃(이 페이지)** → 8 WEB 관측 → 9 장애 모드 → 10 ASG·AMI.
</callout>
