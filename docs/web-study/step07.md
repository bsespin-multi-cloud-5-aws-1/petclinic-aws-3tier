<callout icon="⏱️" color="blue_bg">
	**이 단계의 목표**: 요청이 두 WEB 중 어디로 가는지(분산), 연결이 언제 끊기는지(타임아웃)를 ALB·CloudFront·Apache 세 곳의 값으로 맞춰 본다. 값이 어긋나면 나는 502·504 의 원인이 여기. 반나절 분량.
</callout>
# 1. 분산 — 누가 받나
<table header-row="true" fit-page-width="true">
	<tr>
		<td>설정</td>
		<td>우리 값</td>
		<td>뜻</td>
	</tr>
	<tr>
		<td>알고리즘</td>
		<td>`round_robin`</td>
		<td>정상 대상에 번갈아. 대안 `least_outstanding_requests`(처리 중 요청이 적은 쪽) — 요청 길이가 들쭉날쭉하면 그쪽이 낫다</td>
	</tr>
	<tr>
		<td>교차 영역(cross-zone)</td>
		<td>**on**</td>
		<td>2a 노드가 받은 요청을 2c 서버로도 보냄 → 서버 대수가 AZ 별로 달라도 균등. ALB 는 기본 on</td>
	</tr>
	<tr>
		<td>스티키 세션</td>
		<td>**off**</td>
		<td>PetClinic 은 세션에 의존하지 않는 무상태 앱. 켜면 특정 서버로 쏠려 분산이 깨짐</td>
	</tr>
	<tr>
		<td>slow start</td>
		<td>0</td>
		<td>새 대상에 처음부터 100% 보냄. 워밍업이 필요한 JVM(WAS)엔 30~60s 를 줄 수 있음(로드맵)</td>
	</tr>
	<tr>
		<td>HTTP/2</td>
		<td>ALB `routing.http2.enabled=true`</td>
		<td>뷰어(CloudFront)와의 얘기. **오리진 쪽은 항상 HTTP/1.1** — CloudFront→ALB 도, ALB→Apache 도</td>
	</tr>
</table>
# 2. 타임아웃 — 세 곳의 값을 한 줄에

```text
CloudFront ──(응답 대기 30s · keep-alive 5s)──▶ ALB ──(유휴 60s)──▶ Apache ──(Timeout 60 · KeepAliveTimeout 5 · MaxKeepAliveRequests 100 = httpd 기본값 · web.sh 가 안 바꿈)──▶ Internal ALB ──▶ Tomcat
```

<table header-row="true" fit-page-width="true">
	<tr>
		<td>지점</td>
		<td>값</td>
		<td>의미</td>
		<td>어긋나면</td>
	</tr>
	<tr>
		<td>CloudFront 오리진 응답 제한</td>
		<td>**30s**</td>
		<td>ALB 가 30초 안에 첫 바이트를 안 주면 CloudFront 가 **504** 로 사용자에게</td>
		<td>느린 페이지(리포트 등)가 30초 넘으면 사용자는 504 + 점검 페이지 — 실제 서버는 계속 처리 중(낭비)</td>
	</tr>
	<tr>
		<td>CloudFront 오리진 keep-alive</td>
		<td>5s</td>
		<td>ALB 로의 연결을 5초 유휴까지 재사용</td>
		<td>—</td>
	</tr>
	<tr>
		<td>ALB 유휴 제한</td>
		<td>**60s**</td>
		<td>클라이언트·대상 양쪽 연결이 60초 동안 데이터가 없으면 ALB 가 끊음</td>
		<td>Apache 의 KeepAliveTimeout 이 이보다 **길어야** 안전: Apache 가 먼저 끊으면 ALB 가 닫힌 연결에 요청을 써서 **502**</td>
	</tr>
	<tr>
		<td>Apache KeepAliveTimeout</td>
		<td>**5s (기본값 · 서버 미확인)**</td>
		<td>Apache 가 유휴 연결을 5초 뒤 닫음. web.sh 가 이 값을 안 바꾸므로 httpd 기본값 — 실습 4 로 서버에서 확인</td>
		<td>⚠️ 60s 보다 짧다 — 이론상 502 위험. 다만 ALB 는 대상 연결을 끊기 전에 재시도하고 실측 5XX 0 이라 현재 문제는 없음. 안전하게 하려면 `KeepAliveTimeout 75` (권고: ALB 유휴 + 여유)</td>
	</tr>
	<tr>
		<td>Apache Timeout</td>
		<td>60s (기본)</td>
		<td>한 요청의 I/O 가 60초 멈추면 끊음</td>
		<td>ALB 60s 와 같음 — 동시에 끊겨 애매. 65~70 으로 두면 ALB 가 먼저 판단</td>
	</tr>
</table>
AWS 권고: **대상(Apache)의 keep-alive 타임아웃 › ALB 유휴 타임아웃**. 우리 web.sh 는 Apache 기본값을 안 건드린다 — 개선 항목(아래 실습 4).
# 3. 어디서 몇 초를 세나 — 상태 코드로 역추적
<table header-row="true" fit-page-width="true">
	<tr>
		<td>사용자가 본 것</td>
		<td>누가 냈나</td>
		<td>원인 후보</td>
	</tr>
	<tr>
		<td>504 + 점검 페이지</td>
		<td>CloudFront (30s) 또는 ALB (60s)</td>
		<td>WAS 가 느림(DB 쿼리 · GC) · Internal ALB 뒤 응답 없음</td>
	</tr>
	<tr>
		<td>502</td>
		<td>ALB</td>
		<td>Apache 가 연결을 먼저 닫음(keep-alive 불일치) · Apache 응답이 깨짐 · 프로세스 재시작 중</td>
	</tr>
	<tr>
		<td>503</td>
		<td>ALB</td>
		<td>정상 대상 0 (5단계)</td>
	</tr>
</table>
# 4. 눈으로 확인

```bash
# 1) ALB 속성 — 유휴 60 · 교차 영역 · http2
ALB=$(aws elbv2 describe-load-balancers --names mc-alb-public --profile mc-deploy --query 'LoadBalancers[0].LoadBalancerArn' --output text)
aws elbv2 describe-load-balancer-attributes --load-balancer-arn $ALB --profile mc-deploy --query 'Attributes[?Key==`idle_timeout.timeout_seconds`||Key==`load_balancing.cross_zone.enabled`||Key==`routing.http2.enabled`].[Key,Value]' --output table
# 2) 대상 그룹 — 알고리즘 · 스티키 · slow start
TG=$(aws elbv2 describe-target-groups --names mc-tg-web --profile mc-deploy --query 'TargetGroups[0].TargetGroupArn' --output text)
aws elbv2 describe-target-group-attributes --target-group-arn $TG --profile mc-deploy --query 'Attributes[?Key==`load_balancing.algorithm.type`||Key==`stickiness.enabled`||Key==`slow_start.duration_seconds`].[Key,Value]' --output table
# 3) CloudFront 오리진 — 응답 30 · keep-alive 5
aws cloudfront get-distribution-config --id E2PWXW3LUYTDEE --profile mc-deploy --query 'DistributionConfig.Origins.Items[?Id==`alb-public`].CustomOriginConfig.[OriginReadTimeout,OriginKeepaliveTimeout]' --output table
# 4) Apache 값 (Bastion 경유) — 아무것도 안 나오면 기본값(KeepAliveTimeout 5 · Timeout 60)
ssh -i infra/terraform-kdt5/.keys/mc-ssh.pem -J ec2-user@52.78.145.87 ec2-user@10.0.10.189 'grep -rhE "^\s*(Timeout|KeepAlive|KeepAliveTimeout|MaxKeepAliveRequests)\b" /etc/httpd/conf /etc/httpd/conf.d; httpd -M 2>/dev/null | grep mpm'
# 5) 분산이 실제로 번갈아 가는지 — 서버마다 다른 값이 없어 ALB 로그의 target 필드로 본다 (8단계)
#    응답 헤더로 보려면 web.sh 에 `Header set X-Served-By "%{HOSTNAME}e"` 를 넣는 방법이 있다(로드맵)
```

# 5. 다음 단계 진입 기준
<details>
<summary>Q1. Apache KeepAliveTimeout 5 · ALB 유휴 60 이면 이론상 무엇이 위험한가?</summary>
	Apache 가 유휴 연결을 먼저 닫아, ALB 가 그 연결에 다음 요청을 보냈을 때 502. 권고는 대상 › ALB (예: 75s).
</details>
<details>
<summary>Q2. 사용자가 504 를 봤다. CloudFront 와 ALB 중 누가 냈는지 어떻게 구분하나?</summary>
	ALB 액세스 로그의 `elb_status_code` 가 504 면 ALB(60s), 로그에 요청이 200 인데 사용자는 504 면 CloudFront(30s) 가 먼저 포기한 것. 8단계.
</details>
<details>
<summary>Q3. 스티키 세션을 켜야 하는 앱은?</summary>
	서버 메모리에 세션을 두는 앱(로그인 상태 등). PetClinic 은 세션이 없어 불필요. 필요해지면 ElastiCache(Redis) 로 세션을 밖으로 빼는 게 스티키보다 낫다(멘토링 질문지).
</details>
# 6. 읽을 자료
- AWS 문서 — *Application Load Balancer idle timeout* · *Cross-zone load balancing*
- Apache 문서 — *KeepAliveTimeout* · *mod_mpm_event*
- 콘솔 구축 가이드 **4-3 속성 · 2-3 오리진** 절
<callout icon="🗺️" color="gray_bg">
	**로드맵 위치**: 0 VPC 입구 → 1 HTTP 기초 → 2 TLS 종료 지점 → 3 ALB 해부 → 4 오리진 보호(헤더) → 5 헬스체크 → 6 Apache 프록시 → **7 분산·타임아웃(이 페이지)** → 8 WEB 관측 → 9 장애 모드 → 10 ASG·AMI.
</callout>