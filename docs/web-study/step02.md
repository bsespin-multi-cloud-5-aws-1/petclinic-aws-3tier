<callout icon="🔐" color="blue_bg">
	**이 단계의 목표**: HTTPS(자물쇠)가 어디서 잠기고 어디서 풀리는지, 인증서가 왜 2장인지, 보안 정책 이름이 무슨 뜻인지, 그리고 그 결과로 Apache 가 "나는 http" 라고 믿게 되는 이유. 하루 분량. 값은 전부 2026-09-17 mc-deploy 실측.
</callout>
# 0. 그림 한 장

```text
브라우저 ══HTTPS · 인증서 A(us-east-1) · TLS1.3══▶ CloudFront ══HTTPS · 인증서 B(서울) · TLS1.3══▶ ALB ──평문 80──▶ Apache ──평문 8080──▶ Internal ALB ──▶ Tomcat ══TLS 필수══▶ RDS Proxy
            ▲ ① 1차 종료(풀림)                              ▲ ① 2차 종료(풀림)          ④ VPC 안은 평문 · X-Forwarded-Proto: https 만 남음      ⑤ 예외: DB 는 잠금
   ② 인증서 A                                       ② 인증서 B      ③ 정책 TLSv1.2_2021 / ELBSecurityPolicy-TLS13-1-2-2021-06 · SNI
```

"TLS 종료(termination)" = 암호를 풀고 평문을 보는 지점. 우리는 **두 곳**(CloudFront · ALB)에서 풀고, VPC 안(ALB → Apache → Internal ALB → Tomcat)은 **평문**, DB 구간만 다시 잠근다.
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
		<td>종료 지점은 두 곳</td>
		<td>공용 인터넷 구간(브라우저→CloudFront · CloudFront→ALB)만 잠그고, 각 구간 끝에서 푼다. 푸는 쪽이 내용을 봐야 캐시·WAF·규칙 평가를 할 수 있다</td>
		<td>1차 CloudFront(엣지 ICN80) · 2차 ALB 리스너 443. 둘 다 **TLSv1.3 · TLS_AES_128_GCM_SHA256**</td>
	</tr>
	<tr>
		<td>②</td>
		<td>인증서 2장</td>
		<td>CloudFront 는 **us-east-1** ACM 만, ALB 는 **자기 리전(서울)** ACM 만 받는다 → 같은 도메인으로 2장</td>
		<td>A `us-east-1 …/0e22f93b` · B `ap-northeast-2 …/14198286` · 둘 다 `petclinic.mission-critical.site` · RSA-2048 · ISSUED · 만료 2027-04-01</td>
	</tr>
	<tr>
		<td>③</td>
		<td>보안 정책 · SNI</td>
		<td>"어떤 TLS 버전·암호를 허용할지" 묶음. SNI 는 한 IP 에서 도메인별 인증서를 고르는 방법</td>
		<td>CloudFront `TLSv1.2_2021` · `sni-only` / ALB `ELBSecurityPolicy-TLS13-1-2-2021-06` / CloudFront→ALB 오리진 `TLSv1.2` 이상 · `https-only`</td>
	</tr>
	<tr>
		<td>④</td>
		<td>VPC 안은 평문</td>
		<td>ALB→Apache 80 · Apache→Internal ALB 8080 은 HTTP. 원래 https 였다는 사실은 `X-Forwarded-Proto: https` 로만 전달</td>
		<td>대상 그룹 `mc-tg-web` HTTP 80 · Internal ALB 리스너 `8080 HTTP` · `mc-tg-was` HTTP 8080</td>
	</tr>
	<tr>
		<td>⑤</td>
		<td>예외 — DB 구간은 다시 잠금</td>
		<td>개인정보가 흐르는 Tomcat→RDS Proxy→RDS 는 사설망이어도 TLS 를 **강제**</td>
		<td>RDS Proxy `RequireTLS true` · JDBC `sslMode=REQUIRED` · 파라미터 그룹 `require_secure_transport`</td>
	</tr>
</table>
# 2. 자세히 — 항목마다 "무슨 일 · 우리 값 · 없으면 · 눈으로 확인"
## 2-1. ① 종료 지점은 두 곳 — 풀어야 볼 수 있다
**무슨 일이 일어나나**
1. TLS 는 **두 끝점**이 키를 나눠 갖고 중간은 못 읽는 터널이다. 그래서 중간 장비가 내용(경로 · 헤더 · 본문)을 보려면 **자기가 끝점**이 되어 풀어야 한다. CloudFront 는 캐시 여부 · WAF 규칙 · 동작(behavior) 선택을 위해, ALB 는 규칙(도장 헤더) 평가 · 대상 선택을 위해 내용을 봐야 한다 → 각각 종료.
2. 1차: 브라우저가 엣지에 TLS 핸드셰이크 — SNI 로 `petclinic.mission-critical.site` 를 말하고, 엣지가 **인증서 A** 를 내민다. 브라우저가 검증(체인 · 이름 · 기간) 후 대칭키 합의. 이후 요청은 엣지 안에서 평문.
3. 엣지가 오리진에 가야 하면 **새 TLS**(CloudFront→ALB)를 맺는다: 오리진 프로토콜 `https-only`, ALB 가 **인증서 B** 를 내밀고 CloudFront 가 검증한다 — 이때 CloudFront 는 인증서 이름이 **요청의 Host** 와 맞는지 본다(1단계 AllViewer 가 필요한 이유).
4. 2차: ALB 리스너 443 이 푼 뒤부터는 평문. 즉 "브라우저↔CloudFront" 와 "CloudFront↔ALB" 는 **별개의 TLS 세션**이다. 버전·암호도 각각 협상된다(오늘은 둘 다 1.3 이 나왔다).
5. 어디서 풀리든 **사용자 브라우저는 한 자물쇠만 본다** — 주소창의 자물쇠는 인증서 A 다.

**우리 값**
<table header-row="true" fit-page-width="true">
	<tr>
		<td>구간</td>
		<td>협상 결과 (실측)</td>
		<td>어디서 확인했나</td>
	</tr>
	<tr>
		<td>브라우저 → CloudFront</td>
		<td>`TLSv1.3` · `TLS_AES_128_GCM_SHA256` · 인증서 A (`CN=petclinic.mission-critical.site`, issuer `Amazon RSA 2048 M01`, 2026-09-15 ~ 2027-03-31 GMT)</td>
		<td>`openssl s_client` 내 PC</td>
	</tr>
	<tr>
		<td>CloudFront → ALB</td>
		<td>`TLSv1.3` · `TLS_AES_128_GCM_SHA256` · 인증서 B · SNI `petclinic.mission-critical.site`</td>
		<td>ALB 액세스 로그 `ssl_cipher ssl_protocol domain_name` 필드</td>
	</tr>
	<tr>
		<td>어느 엣지가 풀었나</td>
		<td>`x-amz-cf-pop: ICN80-P4` (서울)</td>
		<td>응답 헤더</td>
	</tr>
</table>
**없으면 · 오해**
- CloudFront 에서 안 풀면(패스스루): 캐시·WAF·오류 페이지 대체가 전부 불가. CloudFront 를 쓰는 의미가 없다.
- "한 번 잠갔으니 끝까지 암호화" — 아니다. 우리 구성은 두 번 잠그고 두 번 푼다. 종단간(브라우저↔Tomcat) 암호화가 아니다. 그래서 중간(CloudFront · ALB)은 **AWS 를 신뢰**하는 구조.
- "CloudFront→ALB 는 AWS 안이니 평문이어도" — 0단계에서 본 대로 주소 체계상 공용 인터넷이다. `https-only` 가 맞다.

**눈으로 확인**

```bash
# 1) 1차(브라우저 쪽) — 버전 · 암호 · 인증서 A 의 이름·발급자·기간
echo | openssl s_client -connect petclinic.mission-critical.site:443 -servername petclinic.mission-critical.site 2>/dev/null | grep -E "^New,|subject=|issuer=|Verify return"
echo | openssl s_client -connect petclinic.mission-critical.site:443 -servername petclinic.mission-critical.site 2>/dev/null | openssl x509 -noout -dates
# 2) 2차(CloudFront→ALB) — ALB 로그의 TLS 필드 (15 · 16번째) 와 SNI (19번째)
K=$(aws s3 ls s3://mc-logs-528821350786/alb/public/ --recursive --profile mc-deploy | grep -v TestFile | tail -1 | awk '{print $4}')
aws s3 cp "s3://mc-logs-528821350786/$K" - --profile mc-deploy | zcat | tail -1 | awk -F'"' '{split($5,t," "); print "cipher="t[1], "proto="t[2], "sni="$8}'
# 3) 어느 엣지가 풀었나
curl -sI https://petclinic.mission-critical.site/ | grep -iE "^x-amz-cf-pop|^via"
```

기대: 1) `New, TLSv1.3, Cipher is TLS_AES_128_GCM_SHA256` · `subject=CN = petclinic.mission-critical.site` · `issuer=… Amazon RSA 2048 M01` · `Verify return code: 0 (ok)` · `notAfter=Mar 31 23:59:59 2027 GMT` 2) `cipher=TLS_AES_128_GCM_SHA256 proto=TLSv1.3 sni=petclinic.mission-critical.site` 3) `x-amz-cf-pop: ICN80-P4`
## 2-2. ② 인증서 2장 — 리전 규칙 때문
**무슨 일이 일어나나**
1. 인증서 = "이 도메인은 이 공개키의 주인 것" 을 CA(Amazon)가 서명한 문서. 브라우저는 CA 체인을 믿으므로 자물쇠가 뜬다. ACM 이 무료로 발급·**자동 갱신**한다(만료 60일 전부터).
2. **CloudFront 는 글로벌 서비스**라 인증서를 **us-east-1(버지니아) ACM** 에서만 읽는다. **ALB 는 리전 리소스**라 **같은 리전(서울) ACM** 만 붙는다. 그래서 같은 도메인으로 **2장**이 필요하다 — 내용은 같고 사는 곳만 다르다.
3. 발급 검증은 DNS 방식: ACM 이 준 CNAME(`_xxxx.petclinic.mission-critical.site → _yyyy.acm-validations.aws`)을 Route 53 에 두면 발급되고, 이 CNAME 을 **계속 두어야 자동 갱신**된다. 두 장이 같은 도메인이라 CNAME 도 하나.
4. 갱신은 자동이지만 "갱신된 인증서를 CloudFront·ALB 가 쓰는지" 는 InUse 로 확인한다. 만료 알림은 ACM 이 45일 전부터 이벤트로 보낸다(현재 알람 미구성 · 로드맵).

**우리 값**
<table header-row="true" fit-page-width="true">
	<tr>
		<td>인증서</td>
		<td>리전</td>
		<td>붙는 곳</td>
		<td>실측</td>
	</tr>
	<tr>
		<td>A</td>
		<td>**us-east-1**</td>
		<td>CloudFront `E2PWXW3LUYTDEE` ViewerCertificate</td>
		<td>`arn:aws:acm:us-east-1:…:certificate/0e22f93b-8c49-4bc7-88fd-abb4ff915986` · ISSUED · RSA-2048 · InUse · 만료 2027-04-01 08:59 KST</td>
	</tr>
	<tr>
		<td>B</td>
		<td>**ap-northeast-2**</td>
		<td>ALB `mc-alb-public` 리스너 443</td>
		<td>`arn:aws:acm:ap-northeast-2:…:certificate/14198286-7863-4608-b164-3de4bb97f784` · ISSUED · RSA-2048 · InUse · 만료 2027-04-01 08:59 KST</td>
	</tr>
	<tr>
		<td>같은 계정 us-east-1 의 다른 인증서</td>
		<td>us-east-1</td>
		<td>`kinetra.site` — 다른 프로젝트</td>
		<td>우리 것 아님 · 콘솔에서 헷갈리지 말 것</td>
	</tr>
</table>
**없으면 · 오해**
- 서울 인증서를 CloudFront 에 붙이려 하면 콘솔 목록에 **아예 안 뜬다**(us-east-1 만 조회). 초보가 가장 자주 막히는 지점.
- 검증 CNAME 을 "정리" 한다고 지우면: 지금은 멀쩡하지만 갱신 시점에 `PENDING_VALIDATION` 으로 멈추고, 만료일에 사이트가 죽는다.
- "인증서 하나를 export 해서 양쪽에 올리면" — ACM 공개 인증서는 내보내기 불가. 2장이 정석.

**눈으로 확인**

```bash
# 1) 두 리전의 ACM — 같은 도메인 · 둘 다 ISSUED · InUse
aws acm list-certificates --profile mc-deploy --region us-east-1      --query 'CertificateSummaryList[?DomainName==`petclinic.mission-critical.site`].[DomainName,Status,KeyAlgorithm,InUse,NotAfter]' --output table
aws acm list-certificates --profile mc-deploy --region ap-northeast-2 --query 'CertificateSummaryList[?DomainName==`petclinic.mission-critical.site`].[DomainName,Status,KeyAlgorithm,InUse,NotAfter]' --output table
# 2) 누가 어느 인증서를 쓰나 — CloudFront 는 us-east-1, ALB 는 서울
aws cloudfront get-distribution-config --id E2PWXW3LUYTDEE --profile mc-deploy --query 'DistributionConfig.ViewerCertificate.ACMCertificateArn' --output text
aws elbv2 describe-listeners --load-balancer-arn $(aws elbv2 describe-load-balancers --names mc-alb-public --profile mc-deploy --query 'LoadBalancers[0].LoadBalancerArn' --output text) --profile mc-deploy --query 'Listeners[0].Certificates[0].CertificateArn' --output text
# 3) 검증 CNAME 이 Route 53 에 살아 있나 (자동 갱신 조건)
Z=$(aws route53 list-hosted-zones --profile mc-deploy --query 'HostedZones[?Name==`mission-critical.site.`].Id' --output text)
aws route53 list-resource-record-sets --hosted-zone-id $Z --profile mc-deploy --query 'ResourceRecordSets[?Type==`CNAME` && contains(Name, `petclinic`)].[Name,ResourceRecords[0].Value]' --output text
```

기대: 1) 각 리전 한 줄씩 `ISSUED RSA-2048 True 2027-04-01…` 2) `arn:aws:acm:us-east-1:…/0e22f93b…` · `arn:aws:acm:ap-northeast-2:…/14198286…` 3) `_….petclinic.mission-critical.site. _….acm-validations.aws.`
## 2-3. ③ 보안 정책과 SNI — 이름을 읽는 법
**무슨 일이 일어나나**
1. 핸드셰이크 첫 단계에서 클라이언트가 "나는 이 버전들·이 암호들 됨" 을 보내고, 서버가 **정책 안에서** 하나를 고른다. 정책 = 허용 버전 + 암호 스위트 목록. 오래된 버전(TLS 1.0 · 1.1)을 빼는 게 정책의 목적.
2. `ELBSecurityPolicy-TLS13-1-2-2021-06` = TLS **1.3 과 1.2** 허용 · 2021-06 판 스위트. `TLSv1.2_2021` = 최소 1.2 · 2021 스위트. 둘 다 1.0/1.1 거부. 이름의 연도는 "그 시점의 권장 스위트 묶음".
3. **SNI**: 한 IP(엣지 · ALB 노드)가 여러 도메인을 서비스하므로, 클라이언트가 핸드셰이크 첫 메시지에 **어느 도메인인지** 평문으로 적어 준다(Server Name Indication). 서버는 그걸로 인증서를 고른다. CloudFront `sni-only` 는 "SNI 못 하는 아주 옛날 클라이언트는 포기하고 전용 IP 비용을 안 낸다" 는 뜻.
4. CloudFront → ALB 도 SNI 를 쓴다: ALB 로그 `domain_name` 필드에 `petclinic.mission-critical.site` 가 찍힌 게 그것. 오리진 SSL 프로토콜 `TLSv1.2` 는 "오리진에 최소 1.2 로 붙는다".
5. HTTP/2·3 은 TLS 위에서 협상된다(ALPN). 브라우저↔CloudFront 는 `http2and3`, 오리진 쪽은 항상 HTTP/1.1.

**우리 값**
<table header-row="true" fit-page-width="true">
	<tr>
		<td>어디</td>
		<td>정책 · 설정</td>
		<td>뜻</td>
	</tr>
	<tr>
		<td>CloudFront 뷰어</td>
		<td>`TLSv1.2_2021` · `sni-only` · `http2and3`</td>
		<td>1.0/1.1 브라우저 거부 · 전용 IP 없음 · 뷰어와 HTTP/2·3</td>
	</tr>
	<tr>
		<td>CloudFront → 오리진</td>
		<td>`https-only` · `OriginSslProtocols [TLSv1.2]` · 443</td>
		<td>오리진에 평문으로 안 감 · 1.2 이상</td>
	</tr>
	<tr>
		<td>ALB 리스너 443</td>
		<td>`ELBSecurityPolicy-TLS13-1-2-2021-06`</td>
		<td>1.3·1.2 만 · 실제 협상 1.3</td>
	</tr>
	<tr>
		<td>ALB 속성</td>
		<td>`routing.http2.enabled true`</td>
		<td>뷰어(CloudFront)와 HTTP/2 가능하지만 CloudFront 는 오리진에 1.1 로 붙음</td>
	</tr>
</table>
**없으면 · 오해**
- 정책을 옛것(`ELBSecurityPolicy-2016-08`)으로 두면 TLS 1.0 이 열려 보안 점검에서 지적. 반대로 `TLS13-1-3` 같은 1.3 전용은 1.2 만 되는 클라이언트를 자른다 — 뷰어가 CloudFront 뿐인 ALB 는 사실 1.3 전용도 가능.
- "SNI 는 암호화된다" — 아니다. 도메인 이름은 핸드셰이크에 **평문**으로 흐른다(ECH 가 아직 일반화 전). 경로·헤더는 암호화. SNI 를 안 보내면 CloudFront(`sni-only`)는 인증서를 주지 않고 핸드셰이크를 끊는다(실측 `handshake failure`).
- "HTTP/2 를 켰으니 오리진도 2" — 아니다(1단계). 오리진 쪽은 1.1.

**눈으로 확인**

```bash
# 1) TLS 1.2 로만 붙어도 되는지 (정책은 1.2·1.3 허용 — 1.0/1.1 은 요즘 OpenSSL 이 로컬에서부터 시도조차 안 함)
curl -sv --tlsv1.2 --tls-max 1.2 https://petclinic.mission-critical.site/ -o /dev/null 2>&1 | grep -E "SSL connection using|^< HTTP"
# 2) SNI 없이 붙으면 — sni-only 라 CloudFront 가 인증서를 아예 안 준다
echo | openssl s_client -connect petclinic.mission-critical.site:443 -noservername 2>&1 | grep -E "alert|no peer certificate"
# 3) 정책 이름들 한 번에
aws cloudfront get-distribution-config --id E2PWXW3LUYTDEE --profile mc-deploy --query 'DistributionConfig.[ViewerCertificate.MinimumProtocolVersion,ViewerCertificate.SSLSupportMethod,HttpVersion,Origins.Items[?Id==`alb-public`].CustomOriginConfig.OriginSslProtocols.Items|[0]]' --output json
aws elbv2 describe-listeners --load-balancer-arn $(aws elbv2 describe-load-balancers --names mc-alb-public --profile mc-deploy --query 'LoadBalancers[0].LoadBalancerArn' --output text) --profile mc-deploy --query 'Listeners[0].SslPolicy' --output text
```

기대: 1) `SSL connection using TLSv1.2 / ECDHE-RSA-AES128-GCM-SHA256` + `HTTP/2 200`(1.2 도 됨 · 기본은 1.3) 2) `sslv3 alert handshake failure` · `no peer certificate available`(SNI 없인 인증서를 못 고름) 3) `TLSv1.2_2021 · sni-only · http2and3 · ["TLSv1.2"]` · `ELBSecurityPolicy-TLS13-1-2-2021-06`
## 2-4. ④ VPC 안은 평문 — 그래서 Apache 는 https 를 모른다
**무슨 일이 일어나나**
1. ALB 가 2차로 푼 뒤 대상 그룹 `mc-tg-web` 으로 **HTTP 80** 평문 연결을 연다. Apache 는 자기가 받은 연결이 평문이므로 "요청은 http" 라고 믿는다. 원래 https 였다는 사실은 ALB 가 붙인 **`X-Forwarded-Proto: https`** 에만 있다(1단계).
2. Apache 가 `/petclinic/*` 를 Internal ALB **8080 HTTP** 로 넘기고, Internal ALB 가 Tomcat 8080 으로 넘긴다 — 전부 평문. Tomcat 도 `X-Forwarded-Proto` 를 봐야 절대 URL 을 https 로 만든다(Tomcat 의 RemoteIpValve · WAS 단계).
3. 왜 평문을 허용하나: VPC 안은 **SG 로 격리된 사설망**이고(0단계), 여기까지 TLS 를 걸면 서버마다 인증서를 두고 갱신·회전해야 해서 운영 부담이 크다. 규제로 요구되면 대상 그룹을 **HTTPS 443** 으로 바꾸고 Apache 에 인증서를 두면 된다(ALB 는 대상 인증서를 검증하지 않아 사설 인증서도 됨).
4. 평문 구간의 위험은 "같은 VPC 안에서 패킷을 볼 수 있는 자" 뿐 — VPC 는 다른 고객과 격리되고, 우리 안에서 볼 수 있는 건 우리 EC2 뿐(그것도 스니핑 불가 구조).

**우리 값**
<table header-row="true" fit-page-width="true">
	<tr>
		<td>구간</td>
		<td>프로토콜 · 포트 (실측)</td>
		<td>근거</td>
	</tr>
	<tr>
		<td>ALB → Apache</td>
		<td>`HTTP 80 · HTTP1`</td>
		<td>대상 그룹 `mc-tg-web` Protocol/Port/ProtocolVersion</td>
	</tr>
	<tr>
		<td>Apache → Internal ALB</td>
		<td>`http://internal-mc-alb-internal-692352220.ap-northeast-2.elb.amazonaws.com:8080/petclinic/`</td>
		<td>petclinic.conf `ProxyPass` (6단계)</td>
	</tr>
	<tr>
		<td>Internal ALB → Tomcat</td>
		<td>리스너 `8080 HTTP` → `mc-tg-was` HTTP 8080</td>
		<td>Internal ALB 리스너 · 대상 그룹</td>
	</tr>
	<tr>
		<td>"원래 https" 의 흔적</td>
		<td>`X-Forwarded-Proto: https` · `X-Forwarded-Port: 443`</td>
		<td>ALB 가 붙임 · Apache RewriteCond 가 사용</td>
	</tr>
</table>
**없으면 · 오해**
- Apache 가 XFP 를 안 보면 `Location: http://…` → CloudFront 301 → 루프(1단계 ⑤). 오늘 실측 Location 이 전부 https 인 것이 XFP 처리의 증거.
- "평문이니 누구나 볼 수 있다" — VPC 밖에선 물리적으로 닿지 않는다(IGW 경로 없음 · SG). 위험 모델을 정확히: **VPC 안 침해 시** 노출.
- 대상 그룹을 HTTPS 로 바꾸면 헬스체크도 HTTPS 로 맞춰야 하고(5단계), Apache 에 mod_ssl · 인증서 · 갱신 절차가 생긴다. "왜 안 하나" 의 답은 비용 대비 위험.

**눈으로 확인**

```bash
# 1) 대상 그룹 두 개의 프로토콜·포트 — 전부 HTTP
for tg in mc-tg-web mc-tg-was; do aws elbv2 describe-target-groups --names $tg --profile mc-deploy --query 'TargetGroups[0].[TargetGroupName,Protocol,Port,ProtocolVersion,HealthCheckProtocol]' --output text; done
# 2) Internal ALB 리스너 — 8080 HTTP
aws elbv2 describe-listeners --load-balancer-arn $(aws elbv2 describe-load-balancers --names mc-alb-internal --profile mc-deploy --query 'LoadBalancers[0].LoadBalancerArn' --output text) --profile mc-deploy --query 'Listeners[].[Port,Protocol]' --output text
# 3) Apache 가 XFP 를 보는 규칙 (web.sh 원문)
grep -n "X-Forwarded-Proto" infra/terraform-kdt5/modules/base/user_data/web.sh
# 4) 그 결과 — Location 이 https
curl -sI https://petclinic.mission-critical.site/petclinic | grep -i "^location"
```

기대: 1) `mc-tg-web HTTP 80 HTTP1 HTTP` · `mc-tg-was HTTP 8080 HTTP1 HTTP` 2) `8080 HTTP` 3) `RewriteCond %｛HTTP:X-Forwarded-Proto｝ =https` 세 곳 4) `location: https://petclinic.mission-critical.site/petclinic/`
## 2-5. ⑤ 예외 — DB 구간은 사설망이어도 다시 잠근다
**무슨 일이 일어나나**
1. Tomcat → RDS Proxy → RDS 는 전부 VPC 안이지만 **개인정보(주인·반려동물·방문 기록)와 DB 자격 증명**이 흐른다. 규정(개인정보 암호화 전송)과 "VPC 안 침해 시에도 DB 트래픽은 못 읽게" 를 위해 TLS 를 **강제**한다.
2. 세 곳에서 맞물린다: RDS Proxy `RequireTLS = true`(평문 접속 거부) · JDBC URL `sslMode=REQUIRED`(앱이 TLS 로만 붙음) · RDS 파라미터 그룹 `require_secure_transport`(DB 자체도 평문 거부). 하나만 있어도 막히지만 셋이 있어야 "어느 쪽이 실수해도" 평문이 안 생긴다.
3. 여기 인증서는 AWS 가 관리(RDS/Proxy 의 서버 인증서, 리전 CA 번들). 우리가 발급·갱신할 게 없다. 앱 쪽은 `sslMode=REQUIRED`(암호화만) 라 서버 인증서 검증은 안 한다 — `VERIFY_CA` 로 올리면 CA 번들을 JVM 에 넣어야 한다(로드맵).
4. WEB 계층 공부 범위 밖이지만, "왜 여기만 잠그고 ALB→Apache 는 안 잠그나" 를 설명할 수 있어야 ④ 의 결정이 원칙 있는 결정이 된다: **민감도 × 노출 범위**로 정한다.

**우리 값**
<table header-row="true" fit-page-width="true">
	<tr>
		<td>어디</td>
		<td>값 (실측)</td>
	</tr>
	<tr>
		<td>RDS Proxy</td>
		<td>`mc-rds-proxy` · `RequireTLS true` · available</td>
	</tr>
	<tr>
		<td>JDBC (was.sh)</td>
		<td>`jdbc:mysql://‹proxy›:3306/petclinic?…&sslMode=REQUIRED`</td>
	</tr>
	<tr>
		<td>파라미터 그룹</td>
		<td>`mc-mysql84` · `require_secure_transport=1`</td>
	</tr>
	<tr>
		<td>Proxy 로그</td>
		<td>`/aws/rds/proxy/mc-rds-proxy` — 연결 성공/거부 기록</td>
	</tr>
</table>
**없으면 · 오해**
- `sslMode` 를 빼면: Proxy 가 평문을 거부해 앱이 **기동 실패**(9/16 초기 구축 때 실제로 겪은 유형의 오류 — "Connections using insecure transport are prohibited").
- "VPC 안이니 DB 도 평문" — 개인정보는 전송 구간 암호화가 요구된다. 멘토링 질문에 대비할 표준 답.

**눈으로 확인**

```bash
# 1) Proxy 가 TLS 를 강제하는지
aws rds describe-db-proxies --profile mc-deploy --region ap-northeast-2 --query 'DBProxies[].[DBProxyName,RequireTLS]' --output text
# 2) DB 파라미터 — require_secure_transport
aws rds describe-db-parameters --db-parameter-group-name mc-mysql84 --profile mc-deploy --region ap-northeast-2 --query 'Parameters[?ParameterName==`require_secure_transport`].[ParameterName,ParameterValue]' --output text
# 3) 앱 쪽 JDBC 옵션 (was.sh 원문 · 비밀값 없음)
grep -n "sslMode" infra/terraform-kdt5/modules/base/user_data/was.sh
```

기대: 1) `mc-rds-proxy True` 2) `require_secure_transport 1` 3) `sslMode=REQUIRED` 가 든 JDBC_URL 줄
## 2-6. 한 요청의 자물쇠 여행 — 어디서 잠기고 풀리나
<table header-row="true" fit-page-width="true">
	<tr>
		<td>구간</td>
		<td>잠김?</td>
		<td>누가 풀고 왜</td>
		<td>실측</td>
	</tr>
	<tr>
		<td>브라우저 → CloudFront 엣지</td>
		<td>🔒 TLS 1.3 · 인증서 A</td>
		<td>엣지가 푼다 — 캐시 · WAF · 동작 선택</td>
		<td>`TLS_AES_128_GCM_SHA256` · `ICN80-P4`</td>
	</tr>
	<tr>
		<td>엣지 → ALB 노드 (공용 인터넷)</td>
		<td>🔒 TLS 1.3 · 인증서 B · SNI</td>
		<td>ALB 리스너가 푼다 — 규칙(도장) 평가 · 대상 선택</td>
		<td>ALB 로그 `TLSv1.3` · `domain_name petclinic…`</td>
	</tr>
	<tr>
		<td>ALB → Apache</td>
		<td>🔓 평문 HTTP 80</td>
		<td>— (`X-Forwarded-Proto: https` 만 남음)</td>
		<td>`mc-tg-web HTTP 80`</td>
	</tr>
	<tr>
		<td>Apache → Internal ALB → Tomcat</td>
		<td>🔓 평문 HTTP 8080</td>
		<td>—</td>
		<td>`ProxyPass http://internal-…:8080` · 리스너 `8080 HTTP`</td>
	</tr>
	<tr>
		<td>Tomcat → RDS Proxy → RDS</td>
		<td>🔒 TLS 강제</td>
		<td>DB 가 푼다 — 개인정보 구간</td>
		<td>`RequireTLS true` · `sslMode=REQUIRED` · `require_secure_transport=1`</td>
	</tr>
</table>
기억할 것 셋: **자물쇠는 두 번 풀린다**(CloudFront · ALB) · **인증서는 리전 때문에 2장** · **VPC 안은 평문, DB 만 예외** — 그래서 Apache 는 `X-Forwarded-Proto` 없이는 https 를 모른다.
# 3. 용어 — 이 단계에서만 쓰는 것
<table header-row="true" fit-page-width="true">
	<tr>
		<td>용어</td>
		<td>한 줄</td>
		<td>비유</td>
	</tr>
	<tr>
		<td>TLS 종료</td>
		<td>암호를 풀어 평문을 보는 지점. 뒤로는 평문이거나 새 TLS</td>
		<td>봉인된 서류를 뜯는 창구</td>
	</tr>
	<tr>
		<td>인증서 · CA · 체인</td>
		<td>도메인 소유를 CA 가 서명한 문서. 브라우저는 CA(Amazon)를 신뢰</td>
		<td>공증된 신분증</td>
	</tr>
	<tr>
		<td>ACM</td>
		<td>AWS 인증서 발급·자동 갱신 서비스. 리전 단위 · 내보내기 불가</td>
		<td>구청 민원실(지점마다 따로)</td>
	</tr>
	<tr>
		<td>SNI</td>
		<td>핸드셰이크 첫 메시지에 도메인 이름을 적어 인증서를 고르게 함(평문)</td>
		<td>"○○병원 앞으로요" 라고 먼저 말하기</td>
	</tr>
	<tr>
		<td>보안 정책</td>
		<td>허용 TLS 버전 + 암호 스위트 묶음의 이름</td>
		<td>자물쇠 규격표</td>
	</tr>
	<tr>
		<td>암호 스위트</td>
		<td>`TLS_AES_128_GCM_SHA256` 처럼 키 교환·암호·해시 조합</td>
		<td>자물쇠 모델명</td>
	</tr>
	<tr>
		<td>ALPN</td>
		<td>TLS 안에서 HTTP/2 등 상위 프로토콜을 고르는 확장</td>
		<td>봉투 뜯기 전 "안에 든 서식 종류" 표시</td>
	</tr>
	<tr>
		<td>X-Forwarded-Proto</td>
		<td>종료 뒤 평문 구간에 "원래 https" 를 알리는 헤더</td>
		<td>"원래 봉인돼 있었음" 도장</td>
	</tr>
</table>
# 4. 왜 이렇게 만들었나 (멘토가 물을 만한 것)
- **왜 CloudFront 에서도 풀고 ALB 에서도 푸나?** 둘 다 내용을 봐야 일한다(캐시·WAF / 규칙·대상). 안 풀면 패스스루 로드밸런싱(NLB) 구조가 되어 WAF·헤더 검증이 불가.
- **왜 인증서를 2장 관리하나?** CloudFront(us-east-1)와 ALB(서울)의 리전 규칙. 같은 도메인·같은 검증 CNAME 이라 운영 부담은 "만료 알림 하나" 수준.
- **왜 ALB→Apache 는 평문인데 DB 는 TLS 인가?** 민감도 × 노출 범위. 페이지 HTML 은 어차피 공개 정보에 가깝고 VPC 안이라 위험이 낮다. DB 트래픽은 개인정보·자격 증명이라 사설망 안이어도 잠근다.
- **왜 TLS 1.2 이상만?** 1.0/1.1 은 알려진 취약점. 2021 정책은 현재 브라우저 전부 호환.
- **HTTPS 를 "다시" 거는 CloudFront→ALB 구간이 느리지 않나?** keep-alive 5s 로 연결을 재사용하고 TLS 1.3 은 핸드셰이크가 1-RTT. 실측 `request_processing_time 0.001`.
# 5. 다음 단계(3. ALB 해부) 진입 기준
<details>
<summary>Q1. ALB 에 us-east-1 인증서를 붙일 수 있나? CloudFront 에 서울 인증서는?</summary>
	둘 다 불가. ALB 는 자기 리전(서울) ACM 만, CloudFront 는 us-east-1 ACM 만. 그래서 같은 도메인으로 2장(A `0e22f93b` · B `14198286`).
</details>
<details>
<summary>Q2. ALB → Apache 를 평문으로 두는 게 왜 허용되나? 그럼 DB 는 왜 TLS 인가?</summary>
	VPC 사설망 + SG 로 격리돼 외부가 볼 수 없는 구간이라 위험 대비 운영 비용이 크다. DB 구간은 개인정보·자격 증명이 흘러 사설망이어도 암호화(Proxy RequireTLS · sslMode=REQUIRED · require_secure_transport).
</details>
<details>
<summary>Q3. TLS 1.1 브라우저가 우리 사이트에 접속하면?</summary>
	CloudFront 가 `TLSv1.2_2021` 정책으로 핸드셰이크를 거부한다(`alert protocol version`). 의도된 동작.
</details>
<details>
<summary>Q4. 브라우저↔CloudFront 와 CloudFront↔ALB 의 TLS 는 같은 세션인가?</summary>
	아니다. 별개의 두 세션이고 버전·암호가 따로 협상된다(오늘은 우연히 둘 다 1.3 · AES_128_GCM). 그래서 인증서도 각각(A · B).
</details>
# 6. 읽을 자료
- AWS 문서 — *Security policies for your Application Load Balancer* (정책 이름표)
- AWS 문서 — *Requirements for using SSL/TLS certificates with CloudFront* (us-east-1 이유)
- AWS 문서 — *Using TLS with RDS Proxy* · MySQL Connector/J `sslMode`
- 콘솔 구축 가이드 **①-4 ACM · 2-1 · 4-1 · 4-3** 절
<callout icon="🗺️" color="gray_bg">
	**로드맵 위치**: 0 VPC 입구 → 1 HTTP 기초 → **2 TLS 종료 지점(이 페이지)** → 3 ALB 해부 → 4 오리진 보호(헤더) → 5 헬스체크 → 6 Apache 프록시 → 7 분산·타임아웃 → 8 WEB 관측 → 9 장애 모드 → 10 ASG·AMI.
</callout>
