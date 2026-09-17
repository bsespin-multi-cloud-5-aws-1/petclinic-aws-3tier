<callout icon="🚪" color="blue_bg">
	**이 단계의 목표**: CloudFront 를 떠난 요청이 **인터넷 → Internet Gateway → 퍼블릭 서브넷의 ALB 노드 → 보안 그룹 → 리스너 443** 까지 어떻게 닿는지, "지도" 수준에서 이해한다. 네트워크(VPC) 이야기라 1단계(HTTP) 보다 먼저. 이틀 분량. 아래 값은 전부 mc-deploy 에서 2026-09-17 에 실측한 것.
</callout>
# 0. 그림 한 장
```text
CloudFront 엣지 ──(공용 인터넷)──▶ Internet Gateway(mc-igw) ──▶ 퍼블릭 서브넷의 ALB 노드(ENI) ──▶ [SG mc-sg-alb-public] ──▶ 리스너 443 ──▶ (여기부터 WEB단)
                                     공인 IP ↔ 사설 IP 1:1          AZ 마다 노드 1개               CloudFront IP 대역 · 443 만
```
핵심 오해 하나: CloudFront → 우리 VPC 는 전용선이 아니라 **그냥 인터넷**이다. 그래서 (a) 이 구간을 HTTPS 로 다시 잠그고, (b) 아무나 그 공인 IP 를 칠 수 있으니 SG + 도장(헤더)으로 막는다.
# 1. 요청이 닿는 순서 — 다섯 단계
<table header-row="true" fit-page-width="true">
	<tr>
		<td>#</td>
		<td>단계</td>
		<td>무슨 일이 일어나나</td>
		<td>우리 값 (실측)</td>
	</tr>
	<tr>
		<td>1</td>
		<td>CloudFront 가 ALB 주소를 찾음</td>
		<td>오리진 도메인을 DNS 로 풀면 **공인 IP 2개**(AZ 당 1개)가 나옴. ALB 는 장비 한 대가 아니라 **AZ 마다 노드 하나**</td>
		<td>`mc-alb-public-485062926.ap-northeast-2.elb.amazonaws.com` → `13.124.71.239`(2a) · `3.34.116.99`(2c)</td>
	</tr>
	<tr>
		<td>2</td>
		<td>인터넷을 타고 IGW 도착</td>
		<td>공인 IP 로 보낸 패킷은 AWS 망을 거쳐 **VPC 의 문 = Internet Gateway** 에 닿음. IGW 는 "공인 IP ↔ VPC 안 사설 IP" 를 1:1 로 바꿔주는 문지기</td>
		<td>`mc-igw` = `igw-0a8434fc99a6e7715` (VPC 에 하나)</td>
	</tr>
	<tr>
		<td>3</td>
		<td>퍼블릭 서브넷</td>
		<td>"퍼블릭" 의 뜻 = 그 서브넷의 **라우팅 테이블에 `0.0.0.0/0 → IGW`** 가 있다는 것뿐. 그래서 ALB 노드는 퍼블릭 서브넷에, WEB·WAS 는 IGW 경로가 없는 프라이빗 서브넷에 둔다</td>
		<td>`mc-rt-public`(`rtb-072d4b3827056d319`): `10.0.0.0/16 → local` · `0.0.0.0/0 → igw-0a8434fc99a6e7715` · 연결 서브넷 `mc-public-a`(10.0.0.0/24) · `mc-public-c`(10.0.1.0/24)</td>
	</tr>
	<tr>
		<td>4</td>
		<td>ALB 노드의 ENI + 보안 그룹</td>
		<td>ALB 노드는 서브넷 안에 **네트워크 카드(ENI)** 로 존재하고 사설 IP + 공인 IP 를 가짐. 패킷이 ENI 에 닿기 전 **SG** 가 검사: "CloudFront IP 대역에서 온 443 만"</td>
		<td>ENI 2a: `10.0.0.212` ↔ `13.124.71.239` · ENI 2c: `10.0.1.212` ↔ `3.34.116.99` · SG `mc-sg-alb-public`(`sg-0cd291c8a096146ea`) 인바운드 = `443 ← pl-22a6434b`(cloudfront.origin-facing) **한 줄뿐**</td>
	</tr>
	<tr>
		<td>5</td>
		<td>리스너 443</td>
		<td>SG 를 통과한 443 연결을 리스너가 받아 TLS 를 풀고 규칙(도장 `X-Origin-Verify` 검사) 적용 → 맞으면 `mc-tg-web`, 아니면 403</td>
		<td>여기부터가 WEB단 (1단계 이후)</td>
	</tr>
</table>
# 2. 용어 — 이 단계에서만 쓰는 것
<table header-row="true" fit-page-width="true">
	<tr>
		<td>용어</td>
		<td>한 줄</td>
		<td>비유</td>
	</tr>
	<tr>
		<td>VPC</td>
		<td>우리만 쓰는 사설 IP 공간 `10.0.0.0/16` (65,536개)</td>
		<td>병원 부지</td>
	</tr>
	<tr>
		<td>서브넷</td>
		<td>VPC 를 AZ 별·용도별로 자른 조각. 우리는 8개(public·web·was·db × a·c)</td>
		<td>층·구역</td>
	</tr>
	<tr>
		<td>라우팅 테이블</td>
		<td>"이 목적지는 어느 문으로" 표. 서브넷마다 하나 연결</td>
		<td>구역별 안내판</td>
	</tr>
	<tr>
		<td>Internet Gateway</td>
		<td>인터넷 ↔ VPC 문. **들어오고 나가고** 둘 다(공인 IP 가진 것만)</td>
		<td>정문</td>
	</tr>
	<tr>
		<td>NAT Gateway</td>
		<td>프라이빗 서브넷이 **나가기만** 할 때(dnf · git · Maven). 밖에서 들어올 수 없음. AZ 당 1개(`mc-nat-a`·`mc-nat-c`) — 한 AZ 가 죽어도 다른 AZ 는 계속 나감</td>
		<td>직원 전용 뒷문(밖으로만)</td>
	</tr>
	<tr>
		<td>ENI</td>
		<td>서브넷 안의 네트워크 카드. EC2 도 ALB 도 RDS Proxy 도 전부 ENI 로 서브넷에 앉는다</td>
		<td>구역에 놓인 전화기</td>
	</tr>
	<tr>
		<td>보안 그룹(SG)</td>
		<td>ENI 앞의 방화벽. **상태 저장** — 들어온 연결의 응답은 자동 허용. 소스는 CIDR · 다른 SG · 접두사 목록</td>
		<td>구역 출입문 경비</td>
	</tr>
	<tr>
		<td>접두사 목록(prefix list)</td>
		<td>AWS 가 관리하는 IP 대역 묶음. `com.amazonaws.global.cloudfront.origin-facing` = 오리진으로 나가는 CloudFront IP 전부. CIDR 을 손으로 적으면 CloudFront IP 가 바뀔 때마다 깨지므로 이걸 씀</td>
		<td>"택배 회사 차량 번호판 목록"</td>
	</tr>
	<tr>
		<td>ALB 노드 · DNS 이름</td>
		<td>AZ 마다 노드 1개, IP 는 바뀔 수 있어 항상 **이름**으로 참조(CloudFront 오리진도 이름)</td>
		<td>안내데스크는 층마다 하나, 위치는 바뀔 수 있으니 "안내데스크" 라고 부름</td>
	</tr>
</table>
# 3. 왜 이렇게 만들었나 (멘토가 물을 만한 것)
- **왜 ALB 만 퍼블릭 서브넷에?** 인터넷에서 직접 닿아야 하는 건 ALB 뿐. WEB·WAS·DB 는 IGW 경로가 없어 밖에서 절대 못 들어온다(나갈 땐 NAT).
- **왜 SG 소스가 CIDR 이 아니라 접두사 목록?** CloudFront IP 는 수시로 바뀜. 접두사 목록은 AWS 가 갱신.
- **SG 로 CloudFront IP 만 열었는데 왜 도장(헤더)까지?** 그 IP 대역은 **전 세계 모든 고객의 CloudFront 가 공유**. 남이 자기 CloudFront 배포의 오리진을 우리 ALB 로 지정하면 SG 는 통과한다 → 우리 배포만 아는 비밀 헤더로 2차 검사. (WEB단 4단계에서 자세히)
- **NAT 를 왜 2개?** AZ 당 1개. NAT 하나면 그 AZ 장애 때 반대편 AZ 의 서버들도 인터넷(dnf·Secrets)을 못 나감. 멘토링에서 확인.
- **CloudFront → ALB 를 왜 HTTPS 로 다시?** 공용 인터넷 구간이라. ALB 에 서울 ACM 인증서가 붙어 있고 CloudFront 오리진 프로토콜은 HTTPS only.
# 4. 눈으로 확인 — 4개
```bash
# 1) ALB 이름 → 공인 IP 2개 (AZ 당 노드 1개)
dig +short mc-alb-public-485062926.ap-northeast-2.elb.amazonaws.com

# 2) 그 노드들이 퍼블릭 서브넷의 ENI 라는 것 (AZ · 서브넷 · 사설 IP · 공인 IP)
aws ec2 describe-network-interfaces --profile mc-deploy --region ap-northeast-2 \
  --filters "Name=description,Values=ELB app/mc-alb-public/*" \
  --query 'NetworkInterfaces[].[AvailabilityZone,SubnetId,PrivateIpAddress,Association.PublicIp]' --output table

# 3) 퍼블릭 서브넷의 라우팅 테이블에 IGW 경로가 있는지
aws ec2 describe-route-tables --profile mc-deploy --region ap-northeast-2 \
  --filters "Name=tag:Name,Values=mc-rt-public" \
  --query 'RouteTables[0].Routes[].[DestinationCidrBlock,GatewayId]' --output table

# 4) ALB 의 SG 인바운드 = 접두사 목록 443 만
SG=$(aws ec2 describe-security-groups --profile mc-deploy --region ap-northeast-2 --filters Name=group-name,Values=mc-sg-alb-public --query 'SecurityGroups[0].GroupId' --output text)
aws ec2 describe-security-group-rules --profile mc-deploy --region ap-northeast-2 --filters "Name=group-id,Values=$SG" \
  --query 'SecurityGroupRules[?IsEgress==`false`].[FromPort,ToPort,PrefixListId,CidrIpv4]' --output table
```
<table header-row="true" fit-page-width="true">
	<tr>
		<td>확인</td>
		<td>기대 결과 (9/17 실측)</td>
		<td>배우는 것</td>
	</tr>
	<tr>
		<td>1</td>
		<td>`13.124.71.239` · `3.34.116.99`</td>
		<td>ALB = 노드 2개 · 항상 이름으로</td>
	</tr>
	<tr>
		<td>2</td>
		<td>2a `subnet-0d546d02b6be9f330` `10.0.0.212` ↔ `13.124.71.239` · 2c `subnet-0a2f8e0cccc9c9b4e` `10.0.1.212` ↔ `3.34.116.99`</td>
		<td>ENI 가 퍼블릭 서브넷에 앉아 사설·공인 IP 를 둘 다 가짐 = IGW 1:1 변환</td>
	</tr>
	<tr>
		<td>3</td>
		<td>`10.0.0.0/16 local` · `0.0.0.0/0 igw-0a8434fc99a6e7715`</td>
		<td>"퍼블릭" = IGW 경로 한 줄</td>
	</tr>
	<tr>
		<td>4</td>
		<td>`443 443 pl-22a6434b None` 한 줄</td>
		<td>CloudFront 대역 443 만 · 80 없음 · CIDR 없음</td>
	</tr>
</table>
# 5. 다음 단계(1. HTTP 기초) 진입 기준
<details>
<summary>Q1. "퍼블릭 서브넷" 과 "프라이빗 서브넷" 의 차이는 딱 하나다. 무엇인가?</summary>
	라우팅 테이블에 `0.0.0.0/0 → Internet Gateway` 경로가 있느냐. 있으면 퍼블릭(공인 IP 를 가진 ENI 가 인터넷과 직접 통신), 없으면 프라이빗(나갈 땐 NAT, 들어올 길 없음).
</details>
<details>
<summary>Q2. ALB 의 IP 를 CloudFront 오리진에 직접 적으면 안 되는 이유는?</summary>
	ALB 노드 IP 는 바뀔 수 있다(스케일·장애). DNS 이름은 AWS 가 현재 노드 IP 로 유지해 준다. 그래서 오리진·레코드 전부 이름으로 참조.
</details>
<details>
<summary>Q3. SG 에 CloudFront 접두사 목록만 열면 남의 CloudFront 도 통과한다. 그럼 SG 는 왜 두나?</summary>
	1차 필터. 인터넷 전체 → CloudFront 대역으로 공격면을 크게 줄이고, 그 안에서 우리 배포만 골라내는 건 헤더(2차). 둘이 겹쳐야 우회를 막는다.
</details>
# 6. 읽을 자료 (각 5~10분)
- AWS 문서 — *VPC 의 작동 방식* (서브넷 · 라우팅 테이블 · 인터넷 게이트웨이 절)
- AWS 문서 — *Application Load Balancer 의 작동 방식* ("로드 밸런서 노드" · "가용 영역" 절)
- AWS 문서 — *Restricting access to Application Load Balancers* (CloudFront 접두사 목록 + 커스텀 헤더 — 우리 설계 그대로)
- 콘솔 구축 가이드 **0-1 · 0-2 · 4-3** 절 (실제 만든 값)
<callout icon="🗺️" color="gray_bg">
	**로드맵 위치**: **0 VPC 입구(이 페이지)** → 1 HTTP 기초 → 2 TLS 종료 지점 → 3 ALB 해부 → 4 오리진 보호(헤더) → 5 헬스체크 → 6 Apache 프록시 → 7 분산·타임아웃 → 8 WEB 관측 → 9 장애 모드 → 10 ASG·AMI.
</callout>
