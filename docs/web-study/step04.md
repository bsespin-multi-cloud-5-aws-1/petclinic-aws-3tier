<callout icon="🛡️" color="blue_bg">
	**이 단계의 목표**: "헤더를 왜 붙이나" 를 위협 모델부터 이해한다. 누가 무엇을 우회하려 하고, SG 가 어디까지 막고, 헤더가 나머지를 어떻게 막고, 그 위에 WAF 가 어떻게 얹히는지. 반나절 분량. 값은 전부 2026-09-17 mc-deploy 실측(비밀값 제외).
</callout>
# 0. 그림 한 장

```text
정상:    브라우저 ─▶ CloudFront(WAF · 캐시 · 로그) ══ +X-Origin-Verify ══▶ [SG: CloudFront 대역 443] ─▶ 리스너 규칙 10 (도장 검사) ─▶ WEB
우회 ①:  공격자 ────────────────────────────────────────────────▶ [SG] ✖ timeout          ← ALB DNS/IP 를 알아내 직접 (WAF·rate limit·로그 전부 건너뜀)
우회 ②:  공격자 ─▶ 남의 CloudFront 배포(오리진 = 우리 ALB) ══ 도장 없음 ══▶ [SG] ✔ 통과 ─▶ 규칙 10 ✖ 403 ← CloudFront IP 대역은 공유. 도장이 없어 기본 작업
   ① 위협        ② 1차 SG(접두사 목록)          ③ 2차 도장(CloudFront 커스텀 헤더 = ALB 규칙 조건)          ④ 비밀값 관리(tfvars)   ⑤ WAF 는 CloudFront 에
```

ALB DNS 이름은 비밀이 아니다(인증서 투명성 로그 · DNS 스캔으로 찾힌다). "모르겠지" 가 아니라 **막아야** 한다.
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
		<td>위협 모델</td>
		<td>CloudFront 를 건너뛰는 길 두 가지 — 직접 접속(①) · 남의 배포를 오리진으로(②). 둘 다 WAF · rate limit · 캐시 · 로그를 건너뛴다</td>
		<td>ALB DNS `mc-alb-public-485062926.ap-northeast-2.elb.amazonaws.com` · 공인 IP 2개 — 공개 정보</td>
	</tr>
	<tr>
		<td>②</td>
		<td>1차 — SG</td>
		<td>인바운드 443 ← CloudFront **origin-facing** 접두사 목록만. 우회 ① 을 **연결 단계**에서 버림(timeout)</td>
		<td>`mc-sg-alb-public` `443 ← pl-22a6434b` 한 줄 · 46개 CIDR · 내 PC 에서 직접 → `000 exit=28`</td>
	</tr>
	<tr>
		<td>③</td>
		<td>2차 — 비밀 헤더(도장)</td>
		<td>우리 CloudFront 가 오리진 요청마다 `X-Origin-Verify: ‹비밀값›` 을 붙이고, ALB 규칙 10 이 검사. 우회 ② 는 값을 몰라 **403**</td>
		<td>CloudFront 오리진 `alb-public` 커스텀 헤더 = `X-Origin-Verify` · ALB 규칙 10 조건 = 같은 이름 · 오늘 로그 매치 규칙 전부 `10`</td>
	</tr>
	<tr>
		<td>④</td>
		<td>비밀값 관리</td>
		<td>값은 Terraform 변수 하나(`origin_verify_secret`)에서 두 곳으로 들어가 불일치가 없다. 교체는 tfvars 수정 → apply</td>
		<td>`terraform.tfvars`(gitignore) 에만 · 노션·저장소·채팅에 없음 · 콘솔에선 보임</td>
	</tr>
	<tr>
		<td>⑤</td>
		<td>WAF 와의 관계</td>
		<td>WAF 는 **CloudFront 에** 붙어 있다. 우회가 성공하면 WAF 를 통째로 건너뛴다 → 오리진 보호 = WAF 를 의미 있게 만드는 장치</td>
		<td>`mc-web-acl`(us-east-1 · CLOUDFRONT) · 규칙 6개: allow-loadgen · 관리형 3 · rate-all 2,000/5분 · rate-booking 100/5분</td>
	</tr>
</table>
# 2. 자세히 — 항목마다 "무슨 일 · 우리 값 · 없으면 · 눈으로 확인"
## 2-1. ① 위협 모델 — 무엇을 막으려 하나
**무슨 일이 일어나나**
1. CloudFront 앞에 둔 것들(WAF 관리형 규칙 · rate limit · 캐시 · 오류 페이지 · 로그)은 **요청이 CloudFront 를 지날 때만** 작동한다. 그래서 공격자의 첫 시도는 "CloudFront 를 안 거치는 길" 찾기.
2. **우회 ①** — ALB 에 직접. ALB DNS 이름은 인증서(CT 로그) · DNS 브루트포스 · 과거 문서에서 찾힌다. 공인 IP 2개도 `dig` 한 번. 이 길이 열려 있으면 rate limit 없이 무제한 요청(예약 폭주 시나리오 그대로).
3. **우회 ②** — 공격자가 **자기 계정의 CloudFront 배포**를 만들고 오리진을 우리 ALB 로 지정. 요청은 CloudFront IP 대역에서 오므로 IP 기반 필터는 통과한다. 우리 WAF 는 우리 배포에만 붙어 있으니 무력.
4. 둘 다 "CloudFront 인 척" 또는 "CloudFront 없이" 다. 대책도 둘: **어디서 왔나**(IP · SG) 와 **우리 배포가 보낸 게 맞나**(비밀 헤더).

**우리 값 — 공격자가 알 수 있는 것**
<table header-row="true" fit-page-width="true">
	<tr>
		<td>정보</td>
		<td>값</td>
		<td>어떻게 알아내나</td>
	</tr>
	<tr>
		<td>ALB DNS 이름</td>
		<td>`mc-alb-public-485062926.ap-northeast-2.elb.amazonaws.com`</td>
		<td>DNS 스캔 · 유출 문서 · 이름 규칙 추측</td>
	</tr>
	<tr>
		<td>ALB 공인 IP</td>
		<td>`13.124.71.239` · `3.34.116.99`</td>
		<td>`dig`</td>
	</tr>
	<tr>
		<td>도메인 · 인증서</td>
		<td>`petclinic.mission-critical.site` (CT 로그에 발급 기록)</td>
		<td>crt.sh</td>
	</tr>
	<tr>
		<td>헤더 **이름**</td>
		<td>`X-Origin-Verify` (관례라 추측 가능)</td>
		<td>—</td>
	</tr>
	<tr>
		<td>헤더 **값**</td>
		<td>모름 — 이것만이 비밀</td>
		<td>tfvars · 콘솔 권한자만</td>
	</tr>
</table>
**없으면 · 오해**
- "ALB 주소를 아무 데도 안 적었으니 안전" — 보안을 비밀 주소에 기대는 것(security by obscurity). 찾히는 순간 끝.
- "WAF 가 있으니 됐다" — WAF 는 CloudFront 를 지나는 요청만 본다. 오리진 보호 없는 WAF 는 우회 가능한 문.
- 위협은 외부 공격자만이 아니다: 팀원이 실수로 ALB 주소를 직접 쓰면 WAF·캐시·로그 없이 운영되는 경로가 생긴다 — 막혀 있어야 실수도 못 한다.

**눈으로 확인**

```bash
# 1) 공격자 입장에서 30초 — 이름과 IP 는 공개
dig +short mc-alb-public-485062926.ap-northeast-2.elb.amazonaws.com
# 2) 인증서 투명성 로그에 우리 도메인 발급 기록 (브라우저에서) https://crt.sh/?q=petclinic.mission-critical.site
# 3) 우리 배포의 WAF 는 CloudFront 에만 붙어 있다 — ALB 엔 WAF 없음
aws cloudfront get-distribution --id E2PWXW3LUYTDEE --profile mc-deploy --query 'Distribution.DistributionConfig.WebACLId' --output text
aws wafv2 get-web-acl-for-resource --resource-arn $(aws elbv2 describe-load-balancers --names mc-alb-public --profile mc-deploy --region ap-northeast-2 --query 'LoadBalancers[0].LoadBalancerArn' --output text) --region ap-northeast-2 --profile mc-deploy --query 'WebACL.Name' --output text
```

기대: 1) IP 2개 2) 발급 기록 3) `arn:aws:wafv2:us-east-1:…:global/webacl/mc-web-acl/…` · ALB 쪽은 `None`(ALB 에 붙은 WAF 없음 → 우회하면 WAF 0)
## 2-2. ② 1차 방어 — SG 가 연결 자체를 버린다
**무슨 일이 일어나나**
1. ALB 노드 ENI 의 SG `mc-sg-alb-public` 인바운드는 **한 줄**: TCP 443 ← 접두사 목록 `pl-22a6434b`(`com.amazonaws.global.cloudfront.origin-facing`). CloudFront 가 오리진에 연결할 때 쓰는 IP 대역 46개(≈34만 IP)만.
2. 우회 ① 의 SYN 은 목록 밖 IP 에서 오므로 SG 가 **응답 없이 버린다**. TLS 핸드셰이크·규칙 평가까지 가지도 않는다 → 공격 트래픽이 ALB 자원을 거의 안 쓴다(DDoS 표면 축소).
3. 접두사 목록은 AWS 가 갱신한다. CloudFront 대역이 늘어도 규칙은 그대로. 손으로 CIDR 46줄을 적었다면 갱신 때마다 구멍이 생긴다.
4. 한계: 이 대역은 **AWS 의 모든 고객의 CloudFront 가 공유**한다. 남의 배포(우회 ②)도 같은 대역에서 온다 → SG 는 통과. 그래서 ③ 이 필요.

**우리 값**
<table header-row="true" fit-page-width="true">
	<tr>
		<td>항목</td>
		<td>값</td>
	</tr>
	<tr>
		<td>SG 인바운드</td>
		<td>`mc-sg-alb-public`(`sg-0cd291c8a096146ea`) · `tcp 443 ← pl-22a6434b` "HTTPS from CloudFront origin-facing prefix list" — 80 없음 · CIDR 없음</td>
	</tr>
	<tr>
		<td>접두사 목록</td>
		<td>46개 CIDR · 예 `3.172.64.0/18` · `15.158.0.0/16`(오늘 로그의 client IP 가 든 대역)</td>
	</tr>
	<tr>
		<td>실측 — 우회 ① 흉내</td>
		<td>내 PC(221.148.195.245 · 목록 밖)에서 `https://13.124.71.239/` → **6초 timeout(exit 28)** · `http://…:80` 도 timeout</td>
	</tr>
	<tr>
		<td>실측 — 정상</td>
		<td>같은 순간 `https://petclinic.mission-critical.site/` → 200</td>
	</tr>
</table>
**없으면 · 오해**
- 인바운드를 `443 ← 0.0.0.0/0` 로 두면: 우회 ① 이 열린다. 콘솔로 ALB 를 만들 때 기본 제안이 이것이라 **직접 고쳐야** 한다.
- 뷰어 쪽 CloudFront IP(`54.230.x`) 를 넣으면 안 된다 — 오리진에 연결하는 건 origin-facing 대역(0단계 ④).
- "timeout 이면 서버가 죽은 것" — 아니다. SG 가 버린 것. 죽었으면 `connection refused` 나 503 이 온다.

**눈으로 확인**

```bash
# 1) SG 인바운드 — 접두사 목록 443 한 줄
aws ec2 describe-security-group-rules --profile mc-deploy --region ap-northeast-2 --filters Name=group-id,Values=sg-0cd291c8a096146ea --query 'SecurityGroupRules[?IsEgress==`false`].[IpProtocol,FromPort,ToPort,PrefixListId,CidrIpv4,Description]' --output table
# 2) 우회 ① 흉내 — 내 PC 에서 직접: 8초 timeout
curl -sk -m 8 -o /dev/null -w "direct=%{http_code} exit=" https://mc-alb-public-485062926.ap-northeast-2.elb.amazonaws.com/; echo $?
# 3) 정상 경로는 200 (+ via 헤더 = CloudFront 를 지났다는 표시)
curl -sI https://petclinic.mission-critical.site/ | grep -iE "^HTTP|^via"
# 4) 오늘 로그의 client IP 들이 전부 접두사 목록 안인지 (SG 가 제대로 골랐다는 증거)
K=$(aws s3 ls s3://mc-logs-528821350786/alb/public/ --recursive --profile mc-deploy | grep -v TestFile | tail -1 | awk '{print $4}')
aws s3 cp "s3://mc-logs-528821350786/$K" - --profile mc-deploy | zcat | awk '{split($4,c,":"); print c[1]}' | sort -u
```

기대: 1) `tcp 443 443 pl-22a6434b None HTTPS from CloudFront origin-facing prefix list` 2) `direct=000 exit=28` 3) `HTTP/2 200` · `via: 1.1 ….cloudfront.net (CloudFront)` 4) `3.172.x.x` · `15.158.x.x` 같은 CloudFront 대역만
## 2-3. ③ 2차 방어 — 도장(비밀 헤더)이 "우리 배포" 를 고른다
**무슨 일이 일어나나**
1. 우리 CloudFront 배포의 오리진 `alb-public` 설정에 **오리진 커스텀 헤더** `X-Origin-Verify: ‹비밀값›` 이 있다. CloudFront 는 오리진으로 보내는 **모든** 요청에 이 헤더를 붙인다(뷰어가 같은 이름의 헤더를 보내도 CloudFront 값으로 덮어씀).
2. ALB 리스너 규칙 10 의 조건은 `http-header X-Origin-Verify = ‹같은 값›`. 맞으면 `forward mc-tg-web`, 안 맞으면 기본 작업 **403**(3단계). 남의 배포(우회 ②)는 값을 모르니 도장이 없거나 틀림 → 403.
3. 비교는 ALB 가 리스너에서 한다 — **TLS 를 푼 뒤**라 헤더가 보인다. 그래서 이 방식은 HTTPS 리스너에서만 안전하다(평문이면 값이 노출).
4. 검사 결과는 로그에 남는다: `matched_rule_priority 10`(도장 OK) / `0`(도장 없음 · elb 403 · target `-`). 오늘 로그는 전부 10.
5. 이름은 비밀이 아니다(`X-Origin-Verify` 는 AWS 문서의 관례). **값만 비밀**. 이름을 바꿔도 보안이 늘지 않는다.

**우리 값**
<table header-row="true" fit-page-width="true">
	<tr>
		<td>어디</td>
		<td>무엇 (실측)</td>
	</tr>
	<tr>
		<td>CloudFront 오리진 `alb-public`</td>
		<td>CustomHeaders 이름 `X-Origin-Verify` (값은 안 뽑음)</td>
	</tr>
	<tr>
		<td>ALB 리스너 규칙 10</td>
		<td>조건 `http-header` 이름 `X-Origin-Verify` → `forward mc-tg-web`</td>
	</tr>
	<tr>
		<td>기본 작업</td>
		<td>`fixed-response 403`</td>
	</tr>
	<tr>
		<td>오늘 로그</td>
		<td>`matched_rule_priority` 값 분포 = `10` 만 · `0` 없음</td>
	</tr>
</table>
**없으면 · 오해**
- 규칙 10 만 있고 기본 작업이 forward 면: 도장이 있든 없든 대상으로 간다 — 검사 무의미. **기본은 반드시 거부**.
- "SG 가 CloudFront 대역만 허용하니 헤더는 과하다" — 우회 ② 가 정확히 그 틈. AWS 문서 *Restricting access to ALB* 가 둘을 **함께** 쓰라고 하는 이유.
- 도장 검사를 Apache(`RequireAny` · `SetEnvIf`)에서 해도 되지만, 그러면 도장 없는 요청이 **WEB 서버까지** 온다. ALB 규칙이면 VPC 문턱(리스너)에서 끝난다.

**눈으로 확인**

```bash
# 1) CloudFront 가 붙이는 커스텀 헤더 이름 (값은 일부러 안 뽑는다)
aws cloudfront get-distribution-config --id E2PWXW3LUYTDEE --profile mc-deploy --query 'DistributionConfig.Origins.Items[?Id==`alb-public`].CustomHeaders.Items[].HeaderName' --output text
# 2) ALB 규칙 10 이 보는 헤더 이름 — 같은 이름
L=$(aws elbv2 describe-listeners --load-balancer-arn $(aws elbv2 describe-load-balancers --names mc-alb-public --profile mc-deploy --query 'LoadBalancers[0].LoadBalancerArn' --output text) --profile mc-deploy --query 'Listeners[0].ListenerArn' --output text)
aws elbv2 describe-rules --listener-arn $L --profile mc-deploy --query 'Rules[?Priority==`10`].[Conditions[0].HttpHeaderConfig.HttpHeaderName,Actions[0].Type]' --output text
# 3) 뷰어가 같은 이름의 헤더를 보내도 CloudFront 값으로 덮인다 — 엉터리 값으로 보내도 200 (우리 배포가 붙인 도장이 이김)
curl -s -o /dev/null -w "%{http_code}\n" -H "X-Origin-Verify: wrong-value" https://petclinic.mission-critical.site/
# 4) 오늘 로그 — 매치된 규칙 분포 (0 이 없어야)
K=$(aws s3 ls s3://mc-logs-528821350786/alb/public/ --recursive --profile mc-deploy | grep -v TestFile | tail -1 | awk '{print $4}')
aws s3 cp "s3://mc-logs-528821350786/$K" - --profile mc-deploy | zcat | awk -F'"' '{split($11,a," "); print a[1]}' | sort | uniq -c
```

기대: 1) `X-Origin-Verify` 2) `X-Origin-Verify forward` 3) `200` 4) `N 10` 한 줄
## 2-4. ④ 비밀값 관리 — 한 곳에서 두 곳으로
**무슨 일이 일어나나**
1. 값은 Terraform 변수 **`origin_verify_secret`** 하나. `terraform.tfvars`(gitignore) 에만 있고, apply 때 ① CloudFront 오리진 커스텀 헤더 ② ALB 규칙 10 조건 **두 곳에 같은 값**이 들어간다. 손으로 두 곳을 맞추는 일이 없으니 불일치 사고가 없다.
2. **콘솔에서 보면 보인다**: CloudFront 오리진 설정 화면과 ALB 규칙 화면 모두 값을 그대로 표시한다. 즉 "콘솔 읽기 권한 = 비밀 접근 권한". IAM 을 그렇게 다뤄야 한다.
3. **교체(rotate)**: tfvars 값 변경 → apply → CloudFront 배포 갱신(수 분)과 ALB 규칙 갱신이 **동시에 끝나지 않는다** → 그 사이 도장 불일치로 403 이 잠깐 난다. 무중단으로 하려면 규칙 조건에 **옛 값·새 값 둘 다**(OR) 두었다가 배포 완료 후 옛 값을 빼는 2단계 apply — 현재 코드는 단일 값이라 개선 여지.
4. 유출 징후: 로그에 `matched_rule_priority 10` 인데 client IP 가 우리 배포의 요청이 아닌 경우는 구분이 어렵다(둘 다 CloudFront 대역). CloudFront 로그(`x-edge-…`)와 ALB 로그의 요청 수를 대조하는 게 방법.

**우리 값**
<table header-row="true" fit-page-width="true">
	<tr>
		<td>항목</td>
		<td>내용</td>
	</tr>
	<tr>
		<td>저장</td>
		<td>`infra/terraform-kdt5/terraform.tfvars` — gitignore · 노션·저장소·채팅에 적지 않는다</td>
	</tr>
	<tr>
		<td>주입</td>
		<td>`edge.tf` 오리진 custom_header + `alb.tf` 리스너 규칙 조건 — 같은 변수 `var.origin_verify_secret`</td>
	</tr>
	<tr>
		<td>노출 면</td>
		<td>콘솔(CloudFront · EC2 로드 밸런서) 읽기 권한자 · Terraform state(S3 백엔드 · 암호화)</td>
	</tr>
	<tr>
		<td>교체 절차(현재)</td>
		<td>tfvars 수정 → `terraform apply` → 수 분간 일부 403 가능 → 완료. 점검 시간에</td>
	</tr>
	<tr>
		<td>교체 절차(개선)</td>
		<td>규칙 조건 값 2개(옛·새) → apply → CloudFront Deployed 확인 → 옛 값 제거 → apply (무중단)</td>
	</tr>
</table>
**없으면 · 오해**
- 값을 노션에 "참고용" 으로 적는 순간 노션 열람 권한이 비밀 권한이 된다. **이름만** 적는다(이 페이지도 그렇게).
- Terraform state 에도 값이 들어간다 — state 버킷 접근 권한도 비밀 권한.
- "값을 아주 길게 하면 안전" — 길이보다 **어디에 흘렸나**가 문제. 32자 무작위면 충분하고, 유출 시 교체가 답.

**눈으로 확인**

```bash
# 1) 값이 저장소 어디에도 없다 (이름만 있어야) — 저장소 전체 grep
grep -rn "origin_verify_secret" --include=*.tf --include=*.md . | grep -v tfvars | head
# 2) tfvars 는 gitignore
git check-ignore -v infra/terraform-kdt5/terraform.tfvars
# 3) 두 곳이 한 변수에서 나온다 — 코드 근거 (edge.tf 오리진 헤더 · alb.tf 규칙 조건)
grep -n "origin_verify_secret" infra/terraform-kdt5/variables.tf infra/terraform-kdt5/edge.tf infra/terraform-kdt5/alb.tf
```

기대: 1) 변수 선언·참조만(값 없음) 2) `infra/terraform-kdt5/.gitignore:5:terraform.tfvars` 3) `variables.tf` 선언 · `edge.tf:… value = var.origin_verify_secret` · `alb.tf:… values = [var.origin_verify_secret]`
## 2-5. ⑤ WAF 와의 관계 — 오리진 보호가 WAF 를 살린다
**무슨 일이 일어나나**
1. WAF `mc-web-acl` 은 **CloudFront 배포에** 연결돼 있다(us-east-1 · scope CLOUDFRONT). 요청이 엣지에 닿으면 WAF 규칙을 **우선순위 순**으로 평가하고, Block 이면 403 을 엣지가 낸다(오리진에 안 감).
2. 규칙 6개: `allow-loadgen`(부하 테스트 IP 허용) → 관리형 3개(IP 평판 · Common · KnownBadInputs) → `rate-all` 2,000/5분 → `rate-booking` `/visits/new` 100/5분. 기본 작업 Allow.
3. **우회 ①②가 성공하면 이 여섯 줄이 전부 무의미**하다. 요청이 CloudFront 를 안 지나니까. 오리진 보호(②③)는 WAF 의 전제 조건이다.
4. 멘토링에서 "WAF 관리 어려움" 얘기가 나왔지만 팀은 **유지** 결정(9/16). 그 결정이 유효하려면 이 4단계가 반드시 있어야 한다.
5. WAF 로그는 `aws-waf-logs-mc`(us-east-1) 로 간다 — 서울의 Firehose 아카이브엔 안 들어간다(8단계).

**우리 값**
<table header-row="true" fit-page-width="true">
	<tr>
		<td>우선순위</td>
		<td>규칙</td>
		<td>동작</td>
		<td>뜻</td>
	</tr>
	<tr>
		<td>0</td>
		<td>`allow-loadgen`</td>
		<td>Allow (IP set)</td>
		<td>부하 테스트 발생기는 rate limit 예외</td>
	</tr>
	<tr>
		<td>1</td>
		<td>`AWSManagedRulesAmazonIpReputationList`</td>
		<td>관리형(그룹 동작 유지)</td>
		<td>알려진 악성 IP 차단</td>
	</tr>
	<tr>
		<td>2</td>
		<td>`AWSManagedRulesCommonRuleSet`</td>
		<td>관리형</td>
		<td>OWASP 계열 — XSS · 경로 조작 등</td>
	</tr>
	<tr>
		<td>3</td>
		<td>`AWSManagedRulesKnownBadInputsRuleSet`</td>
		<td>관리형</td>
		<td>Log4Shell 류 알려진 악성 입력</td>
	</tr>
	<tr>
		<td>4</td>
		<td>`rate-all`</td>
		<td>Block · **2,000 / 5분** / IP</td>
		<td>전체 폭주 완화</td>
	</tr>
	<tr>
		<td>5</td>
		<td>`rate-booking`</td>
		<td>Block · **100 / 5분** / IP · 경로 `/visits/new`</td>
		<td>예약 폭주 시나리오 방어</td>
	</tr>
	<tr>
		<td>연결</td>
		<td>`E2PWXW3LUYTDEE`</td>
		<td>WebACLId = `arn:aws:wafv2:us-east-1:…:global/webacl/mc-web-acl/6b30aaf5…`</td>
		<td>ALB 엔 WAF 없음</td>
	</tr>
	<tr>
		<td>실측 — 9/17 00:19 KST</td>
		<td>스캐너 `34.41.116.206`</td>
		<td>10분 277건 중 **186건 BLOCK**(KnownBadInputs 182 · Common 4 — `/.env` · `/.env.bak` · `phpinfo.php` …) · 91건 ALLOW → Apache 404</td>
		<td>WAF 로그 us-east-1 · CloudFront 로그 403 `time-taken 0.001`(오리진에 안 감)</td>
	</tr>
</table>
**없으면 · 오해**
- "WAF 가 있으니 ALB 는 안 막아도" — 반대. WAF 가 있으니 **더더욱** ALB 를 막아야 한다.
- rate limit 은 **IP 기준**이다. CloudFront 가 본 뷰어 IP(XFF 맨 앞이 아니라 실제 연결 IP)라 위조가 안 된다.
- WAF Block 의 403 과 ALB 규칙의 403 은 다르다: WAF 403 은 엣지가 내며 `x-cache: Error from cloudfront` 에 `server: CloudFront`, ALB 403 은 서버 헤더 없이 본문 `Forbidden`(로그 `matched_rule 0`).

**눈으로 확인**

```bash
# 1) WAF 규칙 목록 · rate 값
aws wafv2 get-web-acl --scope CLOUDFRONT --region us-east-1 --profile mc-deploy --name mc-web-acl --id 6b30aaf5-d1d2-47dd-a991-f17859bc0374 --query 'WebACL.Rules[].[Priority,Name,Statement.RateBasedStatement.Limit]' --output table
# 2) 어느 배포에 붙었나
aws cloudfront get-distribution --id E2PWXW3LUYTDEE --profile mc-deploy --query 'Distribution.DistributionConfig.WebACLId' --output text
# 3) 어젯밤 스캐너를 WAF 가 막은 기록 — us-east-1 로그에서 BLOCK 만 세기 (9/16 15:15~15:25 UTC = 9/17 00:15~00:25 KST)
S=$(date -u -d '2026-09-16 15:15:00' +%s); E=$(date -u -d '2026-09-16 15:25:00' +%s)
aws logs filter-log-events --log-group-name aws-waf-logs-mc --region us-east-1 --profile mc-deploy --start-time ${S}000 --end-time ${E}000 --filter-pattern '{ $.action = "BLOCK" }' --query 'events[].message' --output text | grep -o '"terminatingRuleId":"[^"]*"' | sort | uniq -c
# 4) WAF 가 실제로 막는지 — KnownBadInputs 가 잡는 전형적 문자열 (엣지가 403 · server: CloudFront)
curl -s -o /dev/null -w "%{http_code}\n" "https://petclinic.mission-critical.site/?x=\${jndi:ldap://x}"
curl -sI "https://petclinic.mission-critical.site/?x=\${jndi:ldap://x}" | grep -iE "^HTTP|^server|^x-cache"
```

기대: 1) 6줄 · rate-all `2000` · rate-booking `100` 2) `…mc-web-acl/…` 3) `182 …KnownBadInputsRuleSet` · `4 …CommonRuleSet` 4) `403` · `server: CloudFront` · `x-cache: Error from cloudfront`(오리진에 안 감 — ALB 로그에 없음)
## 2-6. 요청 다섯 종류의 운명 — 어디서 멈추나
<table header-row="true" fit-page-width="true">
	<tr>
		<td>요청</td>
		<td>WAF(엣지)</td>
		<td>SG(0단계 ④)</td>
		<td>규칙 10(도장)</td>
		<td>결과 · 로그</td>
	</tr>
	<tr>
		<td>정상 — 브라우저 → 우리 CloudFront</td>
		<td>통과</td>
		<td>통과 (origin-facing 대역)</td>
		<td>매치 (CloudFront 가 도장 붙임)</td>
		<td>**200** · ALB 로그 rule 10 · Apache 로그 있음</td>
	</tr>
	<tr>
		<td>WAF 차단 — 악성 입력 · rate 초과</td>
		<td>**Block 403**</td>
		<td>—</td>
		<td>—</td>
		<td>엣지 403 (`server: CloudFront`) · ALB 로그 **없음** · WAF 로그(us-east-1)</td>
	</tr>
	<tr>
		<td>우회 ① — 내 PC → ALB 직접</td>
		<td>없음(안 지남)</td>
		<td>**drop → timeout**</td>
		<td>—</td>
		<td>`000 exit=28` · 어떤 로그에도 없음(VPC Flow Log 켜면 REJECT)</td>
	</tr>
	<tr>
		<td>우회 ② — 남의 CloudFront → ALB</td>
		<td>남의 WAF(무관)</td>
		<td>통과 (같은 대역)</td>
		<td>**미매치 → 기본 403**</td>
		<td>ALB 로그 `elb 403` · target `-` · `matched_rule_priority 0`</td>
	</tr>
	<tr>
		<td>뷰어가 가짜 도장 헤더를 보냄</td>
		<td>통과</td>
		<td>통과</td>
		<td>매치 — CloudFront 가 **우리 값으로 덮어씀**</td>
		<td>**200** (실측 `-H "X-Origin-Verify: wrong-value"` → 200) — 뷰어 값은 무시됨</td>
	</tr>
</table>
기억할 것 셋: **SG 는 "어디서 왔나", 도장은 "우리 배포가 보냈나"** · **둘 다 있어야 WAF 가 의미** · **비밀은 값뿐, 한 변수에서 두 곳으로**.
# 3. 용어 — 이 단계에서만 쓰는 것
<table header-row="true" fit-page-width="true">
	<tr>
		<td>용어</td>
		<td>한 줄</td>
		<td>비유</td>
	</tr>
	<tr>
		<td>오리진 보호</td>
		<td>오리진(ALB)이 CloudFront 를 거친 요청만 받게 하는 것</td>
		<td>뒷문 잠그기</td>
	</tr>
	<tr>
		<td>origin-facing 접두사 목록</td>
		<td>CloudFront 가 오리진에 연결할 때 쓰는 IP 대역(AWS 관리 · 46개)</td>
		<td>택배 차량 번호판 목록</td>
	</tr>
	<tr>
		<td>오리진 커스텀 헤더</td>
		<td>CloudFront 가 오리진 요청마다 붙이는 고정 헤더(뷰어 값 덮어씀)</td>
		<td>우리 회사 도장</td>
	</tr>
	<tr>
		<td>http-header 조건</td>
		<td>ALB 규칙이 특정 헤더 값을 검사하는 조건</td>
		<td>도장 검사대</td>
	</tr>
	<tr>
		<td>기본 작업 403</td>
		<td>어느 규칙도 안 맞을 때 ALB 가 직접 거부</td>
		<td>"도장 없으면 반려"</td>
	</tr>
	<tr>
		<td>비밀 교체(rotate)</td>
		<td>값을 바꾸고 두 곳에 다시 넣는 절차</td>
		<td>도장 새로 파기</td>
	</tr>
	<tr>
		<td>WAF · 관리형 규칙 · rate-based</td>
		<td>엣지에서 요청을 검사·차단. AWS 가 관리하는 규칙 묶음 · IP 당 요청 수 제한</td>
		<td>정문 보안 검색대</td>
	</tr>
	<tr>
		<td>CT 로그 (인증서 투명성)</td>
		<td>발급된 모든 공개 인증서의 공개 기록 — 도메인이 공개됨</td>
		<td>관보</td>
	</tr>
</table>
# 4. 왜 이렇게 만들었나 (멘토가 물을 만한 것)
- **SG 만으로 충분하지 않은 이유?** CloudFront origin-facing 대역은 AWS 모든 고객이 공유 → 남의 배포가 우리 ALB 를 오리진으로 지정하면 SG 는 통과.
- **헤더만으로 충분하지 않은 이유?** SG 없이는 인터넷 전체가 리스너까지 닿아 TLS 핸드셰이크·규칙 평가를 소모시키고(DDoS 표면), 값 유출 시 즉시 전면 노출. SG 가 표면을 줄인다.
- **도장 검사를 왜 Apache 가 아니라 ALB 에서?** 도장 없는 요청이 VPC 문턱에서 끝나 WEB 서버 자원을 안 쓴다. 또 ALB 로그에 `matched_rule 0` 으로 남아 관측이 쉽다.
- **왜 WAF 를 ALB 가 아니라 CloudFront 에?** 엣지에서 막는 게 가장 싸고(오리진 트래픽 0) 캐시·오류 페이지와 한 곳에서 관리. 단 그러려면 오리진 보호가 전제.
- **비밀값 교체가 무중단이 아닌 이유?** CloudFront 배포 갱신과 ALB 규칙 갱신 시각이 다르다. 규칙에 두 값을 잠시 병행하면 해결(로드맵).
# 5. 다음 단계(5. 헬스체크) 진입 기준
<details>
<summary>Q1. SG 만으로 충분하지 않은 이유를 한 문장으로.</summary>
	CloudFront origin-facing IP 대역은 AWS 의 모든 고객이 공유하므로, 남이 자기 배포의 오리진을 우리 ALB 로 지정하면 SG 는 통과한다 — 그 요청엔 우리 도장이 없어 규칙 10 이 걸러 403.
</details>
<details>
<summary>Q2. 뷰어(공격자)가 `X-Origin-Verify` 헤더를 직접 만들어 보내면 통과하나?</summary>
	아니다. 우리 CloudFront 를 지나면 CloudFront 가 자기 값으로 덮어써서 오히려 정상 처리되고(실측 200), CloudFront 를 안 지나면 SG(직접) 또는 값 불일치(남의 배포)로 막힌다. 값을 모르는 한 위조가 안 된다.
</details>
<details>
<summary>Q3. 비밀값이 유출됐다. 무엇을 하나?</summary>
	tfvars 의 `origin_verify_secret` 을 새 값으로 바꿔 apply(CloudFront + ALB 규칙 동시 갱신). 무중단이 필요하면 규칙에 새·옛 값을 잠시 병행. 유출 경로(콘솔 권한 · state 접근)도 점검.
</details>
<details>
<summary>Q4. 403 을 봤다. WAF 가 낸 것인지 ALB 규칙이 낸 것인지 어떻게 구분하나?</summary>
	WAF 403 은 엣지가 내서 `server: CloudFront` · `x-cache: Error` 이고 ALB 로그에 없다(WAF 로그에 있음). ALB 규칙 403 은 ALB 로그에 `elb 403 · target - · matched_rule_priority 0` 으로 남는다.
</details>
# 6. 읽을 자료
- AWS 문서 — *Restricting access to Application Load Balancers* (이 설계의 원문: 접두사 목록 + 커스텀 헤더)
- AWS 블로그 — *Limit access to your origins using the AWS-managed prefix list for Amazon CloudFront*
- AWS 문서 — *AWS Managed Rules rule groups list* · *Rate-based rule statement*
- 콘솔 구축 가이드 **2-3 오리진 표 · 3-1 WAF · 4-3** 절
<callout icon="🗺️" color="gray_bg">
	**로드맵 위치**: 0 VPC 입구 → 1 HTTP 기초 → 2 TLS 종료 지점 → 3 ALB 해부 → **4 오리진 보호(헤더)(이 페이지)** → 5 헬스체크 → 6 Apache 프록시 → 7 분산·타임아웃 → 8 WEB 관측 → 9 장애 모드 → 10 ASG·AMI.
</callout>
