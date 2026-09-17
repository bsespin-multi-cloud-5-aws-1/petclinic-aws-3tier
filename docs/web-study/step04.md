<callout icon="🛡️" color="blue_bg">
	**이 단계의 목표**: "헤더를 왜 붙이나" 를 위협 모델부터 이해한다. 누가 무엇을 우회하려 하고, SG 가 어디까지 막고, 헤더가 나머지를 어떻게 막는지. 반나절 분량.
</callout>
# 0. 위협: CloudFront 를 건너뛰는 길

```text
정상:   브라우저 ─▶ CloudFront(WAF · 캐시 · 로그) ─▶ ALB ─▶ WEB
우회 ①: 공격자 ─────────────────────────────▶ ALB ─▶ WEB      ← ALB DNS/IP 를 알아내 직접 (WAF·rate limit·로그 전부 건너뜀)
우회 ②: 공격자 ─▶ 자기 CloudFront 배포(오리진 = 우리 ALB) ─▶ ALB ─▶ WEB   ← CloudFront IP 대역은 통과하지만 우리 WAF 는 없음
```

ALB DNS 이름은 비밀이 아니다(인증서 투명성 로그 · DNS 스캔으로 찾힘). 그러니 "모르겠지" 가 아니라 **막아야** 한다.
# 1. 두 겹 방어
<table header-row="true" fit-page-width="true">
	<tr>
		<td>겹</td>
		<td>무엇</td>
		<td>막는 것</td>
		<td>못 막는 것</td>
		<td>우리 값</td>
	</tr>
	<tr>
		<td>1차 **SG**</td>
		<td>ALB SG 인바운드 = CloudFront origin-facing 접두사 목록의 443 만</td>
		<td>우회 ① — 인터넷 어디서든 직접 오는 연결은 SG 에서 **타임아웃**(SYN 이 버려짐)</td>
		<td>우회 ② — 접두사 목록은 **전 세계 모든 CloudFront 배포가 공유**하는 IP</td>
		<td>`mc-sg-alb-public`: `443 ← pl-22a6434b` 한 줄</td>
	</tr>
	<tr>
		<td>2차 **비밀 헤더**</td>
		<td>우리 CloudFront 가 오리진 요청마다 `X-Origin-Verify: ‹비밀값›` 을 붙이고, ALB 규칙 10 이 그 값을 검사</td>
		<td>우회 ② — 남의 배포는 우리 비밀값을 모르니 **403**</td>
		<td>비밀값이 유출되면 무력 → 교체 절차 필요</td>
		<td>CloudFront 오리진 커스텀 헤더 = ALB 규칙 10 조건 (값 동일)</td>
	</tr>
</table>
둘의 관계: SG 가 공격면을 "인터넷 전체 → CloudFront 대역" 으로 줄이고, 헤더가 그 안에서 "우리 배포만" 골라낸다. 하나만 있으면 구멍이 남는다.
# 2. 비밀값은 어디에 있고 어떻게 지키나
<table header-row="true" fit-page-width="true">
	<tr>
		<td>항목</td>
		<td>내용</td>
	</tr>
	<tr>
		<td>저장</td>
		<td>Terraform 변수 `origin_verify_secret` — `terraform.tfvars`(gitignore) 에만. 노션·저장소·채팅에 적지 않는다</td>
	</tr>
	<tr>
		<td>두 곳에 같은 값</td>
		<td>① CloudFront 오리진 `alb-public` 의 커스텀 헤더 ② ALB 리스너 규칙 10 의 헤더 조건 — Terraform 이 한 변수에서 둘 다 넣어 불일치가 없다</td>
	</tr>
	<tr>
		<td>콘솔에서 보면</td>
		<td>CloudFront 오리진 설정엔 값이 보이고, ALB 규칙에도 조건 값이 보인다 — 콘솔 접근 권한 자체가 비밀 접근 권한</td>
	</tr>
	<tr>
		<td>교체(rotate)</td>
		<td>새 값으로 tfvars 수정 → apply. CloudFront 배포 갱신(수 분) 동안 잠깐 불일치가 생기므로 **규칙에 옛 값·새 값 둘 다 두었다가** 배포 완료 후 옛 값 제거하는 것이 무중단 방법(현재 코드는 단일 값 · 개선 여지)</td>
	</tr>
	<tr>
		<td>헤더 이름</td>
		<td>`X-Origin-Verify` 는 관례. 이름은 비밀이 아니고 값이 비밀</td>
	</tr>
</table>
# 3. WAF 와의 관계
WAF(관리형 규칙 · rate-all 2,000/5분 · rate-booking 100/5분)는 **CloudFront 에 붙어** 있다. 우회 ①②가 성공하면 WAF 를 통째로 건너뛰므로, 오리진 보호는 곧 **WAF 를 의미 있게 만드는 장치**다. 멘토링에서 "WAF 관리 어려움" 얘기가 나왔지만 팀은 유지 결정 — 그 결정이 유효하려면 이 4단계가 반드시 있어야 한다.
# 4. 눈으로 확인

```bash
# 1) 우회 ① — 내 PC 에서 ALB 로 직접: SG 에서 버려져 타임아웃(000)
curl -sk -m 8 -o /dev/null -w "%{http_code}\n" https://mc-alb-public-485062926.ap-northeast-2.elb.amazonaws.com/

# 2) 우회 ② 흉내 — SG 는 통과했다고 치고 도장 없이 리스너에 닿으면 403 (Bastion 안에서: Bastion 은 VPC 안이라 SG 의 접두사 규칙과 무관하게… 아님! Bastion SG 도 목록에 없어 역시 타임아웃)
#    → 대신 CloudFront 를 거친 정상 요청과 비교: via 헤더가 있고 200
curl -sI https://petclinic.mission-critical.site/ | grep -iE "^HTTP|^via"

# 3) 규칙 10 의 헤더 이름만 확인 (값은 콘솔에서만)
L=$(aws elbv2 describe-listeners --load-balancer-arn $(aws elbv2 describe-load-balancers --names mc-alb-public --profile mc-deploy --query 'LoadBalancers[0].LoadBalancerArn' --output text) --profile mc-deploy --query 'Listeners[0].ListenerArn' --output text)
aws elbv2 describe-rules --listener-arn $L --profile mc-deploy --query 'Rules[?Priority==`10`].Conditions[0].HttpHeaderConfig.HttpHeaderName' --output text

# 4) CloudFront 오리진에 커스텀 헤더가 붙어 있는지 (이름만)
aws cloudfront get-distribution-config --id E2PWXW3LUYTDEE --profile mc-deploy --query 'DistributionConfig.Origins.Items[?Id==`alb-public`].CustomHeaders.Items[].HeaderName' --output text

# 5) SG 인바운드가 접두사 목록 한 줄인지 (0단계와 동일)
aws ec2 describe-security-group-rules --profile mc-deploy --region ap-northeast-2 --filters Name=group-id,Values=$(aws ec2 describe-security-groups --profile mc-deploy --region ap-northeast-2 --filters Name=group-name,Values=mc-sg-alb-public --query 'SecurityGroups[0].GroupId' --output text) --query 'SecurityGroupRules[?IsEgress==`false`].[FromPort,PrefixListId,CidrIpv4]' --output table
```

<table header-row="true" fit-page-width="true">
	<tr>
		<td>확인</td>
		<td>기대 결과</td>
		<td>배우는 것</td>
	</tr>
	<tr>
		<td>1</td>
		<td>`000`(8초 타임아웃)</td>
		<td>SG 1차 — 연결 자체가 안 됨(거부 응답도 없음 = 상태 저장 방화벽이 SYN 을 버림)</td>
	</tr>
	<tr>
		<td>2</td>
		<td>`HTTP/2 200` + `via: 1.1 ….cloudfront.net`</td>
		<td>정상 경로에만 응답이 있다</td>
	</tr>
	<tr>
		<td>3</td>
		<td>`X-Origin-Verify`</td>
		<td>규칙이 이 헤더를 본다</td>
	</tr>
	<tr>
		<td>4</td>
		<td>`X-Origin-Verify`</td>
		<td>CloudFront 가 이 헤더를 붙인다 — 두 곳이 같은 이름</td>
	</tr>
	<tr>
		<td>5</td>
		<td>`443 pl-22a6434b None`</td>
		<td>CIDR 이 아니라 접두사 목록</td>
	</tr>
</table>
# 5. 다음 단계 진입 기준
<details>
<summary>Q1. SG 만으로 충분하지 않은 이유를 한 문장으로.</summary>
	CloudFront origin-facing IP 대역은 AWS 의 모든 고객이 공유하므로, 남이 자기 배포의 오리진을 우리 ALB 로 지정하면 SG 는 통과한다.
</details>
<details>
<summary>Q2. 헤더만으로 충분하지 않은 이유는?</summary>
	충분할 수도 있지만, SG 없이는 인터넷 전체가 리스너까지 닿아 TLS 핸드셰이크·규칙 평가를 소모시키고(DDoS 표면), 비밀값 유출 시 즉시 전면 노출. SG 가 표면을 줄여 준다.
</details>
<details>
<summary>Q3. 비밀값이 유출됐다. 무엇을 하나?</summary>
	tfvars 의 `origin_verify_secret` 을 새 값으로 바꿔 apply(CloudFront + ALB 규칙 동시 갱신). 무중단이 필요하면 규칙에 새·옛 값을 잠시 병행.
</details>
# 6. 읽을 자료
- AWS 문서 — *Restricting access to Application Load Balancers* (이 설계의 원문)
- AWS 블로그 — *Limit access to your origins using the AWS-managed prefix list for Amazon CloudFront*
- 콘솔 구축 가이드 **2-3 오리진 표 · 4-3** 절
<callout icon="🗺️" color="gray_bg">
	**로드맵 위치**: 0 VPC 입구 → 1 HTTP 기초 → 2 TLS 종료 지점 → 3 ALB 해부 → **4 오리진 보호(헤더)(이 페이지)** → 5 헬스체크 → 6 Apache 프록시 → 7 분산·타임아웃 → 8 WEB 관측 → 9 장애 모드 → 10 ASG·AMI.
</callout>