<callout icon="🔐" color="blue_bg">
	**이 단계의 목표**: HTTPS(자물쇠)가 어디서 잠기고 어디서 풀리는지, 인증서가 왜 2장인지, 보안 정책 이름이 무슨 뜻인지. 그리고 그 결과로 Apache 가 "나는 http" 라고 믿게 되는 이유. 하루 분량.
</callout>
# 0. 그림 한 장

```text
브라우저 ══HTTPS(인증서 A: us-east-1)══▶ CloudFront ══HTTPS(인증서 B: 서울)══▶ ALB ──평문 HTTP 80──▶ Apache ──평문 HTTP 8080──▶ Internal ALB ──▶ Tomcat
            ▲ 1차 종료(TLS 풀림)                          ▲ 2차 종료(TLS 풀림)        X-Forwarded-Proto: https 로 "원래 https 였음" 만 전달
```

"TLS 종료(termination)" = 암호를 풀고 평문을 보는 지점. 우리는 **두 곳**(CloudFront · ALB)에서 풀고, VPC 안(ALB → Apache → Internal ALB → Tomcat)은 **평문**으로 간다.
# 1. 왜 두 번 풀고, 왜 안은 평문인가
<table header-row="true" fit-page-width="true">
	<tr>
		<td>구간</td>
		<td>암호화</td>
		<td>왜</td>
	</tr>
	<tr>
		<td>브라우저 → CloudFront</td>
		<td>HTTPS · 인증서 A(us-east-1)</td>
		<td>공용 인터넷. CloudFront 가 캐시·WAF 판단을 하려면 내용을 봐야 하므로 여기서 한 번 푼다</td>
	</tr>
	<tr>
		<td>CloudFront → ALB</td>
		<td>HTTPS · 인증서 B(서울) · 오리진 프로토콜 **https-only** · TLSv1.2</td>
		<td>역시 공용 인터넷(0단계). CloudFront 가 ALB 의 인증서 이름(`petclinic.mission-critical.site`)을 검증한다 — 그래서 Host 를 AllViewer 로 넘겨야 이름이 맞는다</td>
	</tr>
	<tr>
		<td>ALB → Apache</td>
		<td>**평문 80**</td>
		<td>VPC 안, SG 로 격리된 사설망. 여기까지 암호화하면 인증서를 서버마다 두고 갱신해야 해서 운영 부담만 늘어남(요구되면 대상 그룹 HTTPS 로 가능)</td>
	</tr>
	<tr>
		<td>Apache → Internal ALB → Tomcat</td>
		<td>평문 8080</td>
		<td>동일</td>
	</tr>
	<tr>
		<td>Tomcat → RDS Proxy</td>
		<td>**TLS 필수**(sslMode=REQUIRED)</td>
		<td>DB 는 개인정보라 사설망 안이라도 암호화 — WAS 단계에서</td>
	</tr>
</table>
# 2. 인증서가 2장인 이유
<table header-row="true" fit-page-width="true">
	<tr>
		<td>인증서</td>
		<td>리전</td>
		<td>붙는 곳</td>
		<td>실측</td>
	</tr>
	<tr>
		<td>A</td>
		<td>**us-east-1(버지니아)**</td>
		<td>CloudFront 뷰어 인증서 — CloudFront 는 글로벌 서비스라 **us-east-1 의 ACM 만** 받는다</td>
		<td>`petclinic.mission-critical.site` · ISSUED · 만료 2027-04-01 · 자동 갱신</td>
	</tr>
	<tr>
		<td>B</td>
		<td>**ap-northeast-2(서울)**</td>
		<td>ALB 443 리스너 — ALB 는 리전 리소스라 **같은 리전의 ACM 만** 받는다</td>
		<td>`petclinic.mission-critical.site` · ISSUED · RSA-2048 · 만료 2027-04-01</td>
	</tr>
</table>
둘 다 **같은 도메인 · 같은 DNS 검증 CNAME** 이라 Route 53 레코드는 하나. ACM 이 60일 전부터 자동 갱신하니 그 CNAME 을 지우면 안 된다(콘솔 가이드 ①-4).
# 3. 보안 정책 이름 읽기
<table header-row="true" fit-page-width="true">
	<tr>
		<td>이름</td>
		<td>뜻</td>
	</tr>
	<tr>
		<td>ALB `ELBSecurityPolicy-TLS13-1-2-2021-06`</td>
		<td>**TLS 1.3 과 1.2** 만 허용(1.0·1.1 거부) · 2021-06 판 암호 스위트 묶음. 실측 로그: `TLSv1.3 TLS_AES_128_GCM_SHA256`</td>
	</tr>
	<tr>
		<td>CloudFront `TLSv1.2_2021`</td>
		<td>뷰어와 협상할 최소 버전 TLS 1.2 · 2021 스위트. 오래된 브라우저(TLS 1.0)는 접속 불가 — 의도된 것</td>
	</tr>
	<tr>
		<td>SNI</td>
		<td>한 IP 로 여러 도메인의 인증서를 고르는 방식. CloudFront `sni-only` = 전용 IP 비용 없이</td>
	</tr>
	<tr>
		<td>HTTP/2 · HTTP/3</td>
		<td>브라우저 ↔ CloudFront 는 `http2and3`. CloudFront → ALB 는 HTTP/1.1(오리진은 항상 1.1). ALB `routing.http2.enabled=true` 는 뷰어용이지만 우리 뷰어는 CloudFront 뿐</td>
	</tr>
</table>
# 4. 그래서 생기는 일 — Apache 는 https 를 모른다
ALB 가 자물쇠를 풀고 평문 80 으로 넘기므로 Apache 입장에선 **모든 요청이 http**. 원래 https 였다는 사실은 ALB 가 붙이는 `X-Forwarded-Proto: https` 헤더로만 안다. 그래서 Apache 가 리다이렉트를 만들 때 이 헤더를 먼저 본다(6단계). 안 보면 `Location: http://…` 를 돌려주고, CloudFront 가 http→https 로 다시 보내서 **루프**.
# 5. 눈으로 확인

```bash
# 1) 뷰어 쪽 TLS — 어떤 버전·스위트·인증서로 붙었나 (CloudFront 인증서 A)
curl -svo /dev/null https://petclinic.mission-critical.site/ 2>&1 | grep -E "SSL connection|subject:|issuer:|expire"

# 2) ALB 쪽 인증서 B — SNI 로 이름을 주고 직접 (403 이 정상 · 인증서만 확인)
curl -svo /dev/null --resolve petclinic.mission-critical.site:443:$(dig +short mc-alb-public-485062926.ap-northeast-2.elb.amazonaws.com | head -1) https://petclinic.mission-critical.site/ 2>&1 | grep -E "SSL connection|subject:|HTTP/"

# 3) 리스너 보안 정책 · 인증서 ARN
aws elbv2 describe-listeners --load-balancer-arn $(aws elbv2 describe-load-balancers --names mc-alb-public --query 'LoadBalancers[0].LoadBalancerArn' --output text --profile mc-deploy) --profile mc-deploy --query 'Listeners[].[Port,SslPolicy,Certificates[0].CertificateArn]' --output table

# 4) ACM 두 장 (서울 · us-east-1)
aws acm list-certificates --profile mc-deploy --region ap-northeast-2 --query 'CertificateSummaryList[].[DomainName,Status,NotAfter]' --output table
aws acm list-certificates --profile mc-deploy --region us-east-1      --query 'CertificateSummaryList[].[DomainName,Status,NotAfter]' --output table
```

<table header-row="true" fit-page-width="true">
	<tr>
		<td>확인</td>
		<td>기대 결과</td>
		<td>배우는 것</td>
	</tr>
	<tr>
		<td>1</td>
		<td>`TLSv1.3` · `subject: CN=petclinic.mission-critical.site` · issuer Amazon</td>
		<td>브라우저가 만나는 자물쇠는 CloudFront 것</td>
	</tr>
	<tr>
		<td>2</td>
		<td>같은 CN 의 인증서 + `HTTP/1.1 403`</td>
		<td>ALB 도 같은 이름의 인증서(B) — 다만 도장 없이는 403</td>
	</tr>
	<tr>
		<td>3</td>
		<td>`443 ELBSecurityPolicy-TLS13-1-2-2021-06 arn:aws:acm:ap-northeast-2:…`</td>
		<td>리스너에 서울 인증서</td>
	</tr>
	<tr>
		<td>4</td>
		<td>서울 1장 · us-east-1 1장, 둘 다 ISSUED</td>
		<td>인증서 2장의 이유</td>
	</tr>
</table>
# 6. 다음 단계 진입 기준
<details>
<summary>Q1. ALB 에 us-east-1 인증서를 붙일 수 있나? CloudFront 에 서울 인증서는?</summary>
	둘 다 불가. ALB 는 자기 리전(서울) ACM 만, CloudFront 는 us-east-1 ACM 만. 그래서 같은 도메인으로 2장.
</details>
<details>
<summary>Q2. ALB → Apache 를 평문으로 두는 게 왜 허용되나?</summary>
	VPC 사설망 + SG 로 격리돼 외부가 볼 수 없는 구간이라 위험 대비 운영 비용이 크다. 규제로 요구되면 대상 그룹을 HTTPS 로 바꾸고 Apache 에 인증서를 두면 된다. DB 구간은 개인정보라 사설망이어도 TLS.
</details>
<details>
<summary>Q3. TLS 1.0 브라우저가 우리 사이트에 접속하면?</summary>
	CloudFront 가 `TLSv1.2_2021` 정책으로 거부(핸드셰이크 실패). 의도된 동작.
</details>
# 7. 읽을 자료
- AWS 문서 — *Security policies for your Application Load Balancer* (정책 이름표)
- AWS 문서 — *Requirements for using SSL/TLS certificates with CloudFront* (us-east-1 이유)
- 콘솔 구축 가이드 **2-1 · 4-1 · 4-3** 절
<callout icon="🗺️" color="gray_bg">
	**로드맵 위치**: 0 VPC 입구 → 1 HTTP 기초 → **2 TLS 종료 지점(이 페이지)** → 3 ALB 해부 → 4 오리진 보호(헤더) → 5 헬스체크 → 6 Apache 프록시 → 7 분산·타임아웃 → 8 WEB 관측 → 9 장애 모드 → 10 ASG·AMI.
</callout>