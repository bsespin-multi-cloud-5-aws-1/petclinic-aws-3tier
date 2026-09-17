<callout icon="📚" color="blue_bg">
	**범위**: 요청이 **CloudFront 를 떠나 Apache 에 닿을 때까지** — 도면의 ④ Public ALB → WEB · ⑤ WEB → Internal ALB 구간. 패킷이 지나가는 순서대로 10단계. 각 단계는 "개념 → 우리 설계에서 어디 → 직접 확인하는 명령 → 진입 기준" 으로 정리한다. 기준 코드: `infra/terraform-kdt5` (alb.tf · modules/base/alb.tf · security.tf · user_data/web.sh), 콘솔 가이드 ④·⑤ 절.
</callout>
# 10단계 로드맵
<table header-row="true" fit-page-width="true">
	<tr>
		<td>#</td>
		<td>주제</td>
		<td>핵심 질문</td>
		<td>우리 설계에서</td>
		<td>상태</td>
	</tr>
	<tr>
		<td>0</td>
		<td>VPC 입구</td>
		<td>CloudFront → 인터넷 → Internet Gateway → 퍼블릭 서브넷의 ALB 노드(ENI) → SG → 리스너 443. 퍼블릭 = IGW 경로 한 줄 · 접두사 목록 · NAT 는 나가기만</td>
		<td>mc-igw · mc-rt-public · mc-public-a/c · ALB 노드 2 · mc-sg-alb-public 443 ← pl-22a6434b</td>
		<td>✅ 하위 페이지</td>
	</tr>
	<tr>
		<td>1</td>
		<td>HTTP 기초</td>
		<td>Host · 상태 코드 · X-Forwarded-* · keep-alive · 리다이렉트 원리</td>
		<td>Apache 302 · ALB 403 · CloudFront 오류 응답</td>
		<td>✅ 하위 페이지</td>
	</tr>
	<tr>
		<td>2</td>
		<td>TLS 종료 지점</td>
		<td>HTTPS 는 어디서 끝나나 · 인증서가 왜 2장(us-east-1 · 서울) · 보안 정책 이름의 뜻</td>
		<td>ACM ×2 · 리스너 443 · ALB → Apache 는 평문 80</td>
		<td>예정</td>
	</tr>
	<tr>
		<td>3</td>
		<td>ALB 해부</td>
		<td>리스너 → 규칙(조건·작업·우선순위) → 대상 그룹 → SG. 규칙은 위에서부터, 기본 작업은 마지막</td>
		<td>443 기본 403 + 우선순위 10 헤더 규칙 → mc-tg-web</td>
		<td>예정</td>
	</tr>
	<tr>
		<td>4</td>
		<td>오리진 보호 (헤더를 붙이는 이유)</td>
		<td>ALB DNS 를 알아내 CloudFront·WAF 를 우회하는 위협. SG 프리픽스(1차)는 전 세계 CloudFront 공용 IP 라 남의 배포도 통과 → 비밀 헤더(2차)</td>
		<td>② 커스텀 헤더 X-Origin-Verify = ④ 규칙 10</td>
		<td>예정</td>
	</tr>
	<tr>
		<td>5</td>
		<td>헬스체크 설계</td>
		<td>얕게 vs 깊게 · 10s·5s·2/3 의 의미 · 등록 취소 지연 30s · WEB 을 얕게 보는 이유(연쇄 unhealthy 방지)</td>
		<td>mc-tg-web /health.html vs mc-tg-was /petclinic/</td>
		<td>예정</td>
	</tr>
	<tr>
		<td>6</td>
		<td>Apache 리버스 프록시</td>
		<td>mod_proxy_http vs mod_jk · ProxyPass/Reverse · ProxyPreserveHost · ProxyPass ! · Alias · RewriteCond X-Forwarded-Proto · SetEnvIf nolog</td>
		<td>web.sh 의 petclinic.conf 한 줄씩</td>
		<td>예정</td>
	</tr>
	<tr>
		<td>7</td>
		<td>분산 동작 · 타임아웃</td>
		<td>라운드로빈 · 교차 영역 · 스티키(안 씀) · ALB 유휴 60s 와 Apache KeepAlive 정렬 · HTTP/2 는 CloudFront 까지</td>
		<td>④ 속성 · web.sh MPM</td>
		<td>예정</td>
	</tr>
	<tr>
		<td>8</td>
		<td>WEB 관측</td>
		<td>ALB 액세스 로그 필드(elb vs target 상태 코드 · target_processing_time) · Apache 로그 XFF · HealthyHostCount · p95 · ELB_5XX vs Target_5XX</td>
		<td>/mc/web/* · S3 alb/public · p95 알람</td>
		<td>예정</td>
	</tr>
	<tr>
		<td>9</td>
		<td>장애 모드</td>
		<td>502 · 503 · 504 가 각각 언제 · CloudFront 오류 응답이 걸리는 코드 · httpd 한 대 내리고 관찰</td>
		<td>② custom error → /maintenance.html</td>
		<td>예정</td>
	</tr>
	<tr>
		<td>10</td>
		<td>ASG · AMI</td>
		<td>고정 EC2 2대 → 시작 템플릿 + ASG · Golden AMI</td>
		<td>base.enable_asg · modules/base/compute.tf</td>
		<td>예정</td>
	</tr>
</table>
> 0 = 네트워크 지도(먼저), 1~5 = ALB 쪽, 6~9 = Apache 쪽. 이틀씩 나누면 닷새에 한 바퀴.
