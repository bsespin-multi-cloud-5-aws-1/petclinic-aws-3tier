> **이 단계의 목표**: CloudFront 를 떠난 요청이 **인터넷 → Internet Gateway → 퍼블릭 서브넷의 ALB 노드 → 보안 그룹 → 리스너 443** 까지 어떻게 닿는지, 패킷의 **주소가 어디서 어떻게 바뀌는지**까지 따라간다. 네트워크(VPC) 이야기라 1단계(HTTP) 보다 먼저. 이틀 분량. 아래 값은 전부 mc-deploy 에서 2026-09-17 에 실측한 것.
# 0. 그림 한 장

```text
CloudFront 엣지 ──(공용 인터넷)──▶ Internet Gateway(mc-igw) ──▶ 퍼블릭 서브넷의 ALB 노드(ENI) ──▶ [SG mc-sg-alb-public] ──▶ 리스너 443 ──▶ (여기부터 WEB단)
   ① DNS 로 노드 IP 찾기          ② 공인 IP ↔ 사설 IP 1:1        ③ 0.0.0.0/0 → igw 경로       ④ CloudFront 대역·443 만    ⑤ TLS 풀고 규칙 검사
```

핵심 오해 하나: CloudFront → 우리 VPC 는 전용선이 아니라 **그냥 인터넷**이다. 그래서 (a) 이 구간을 HTTPS 로 다시 잠그고, (b) 아무나 그 공인 IP 를 칠 수 있으니 SG + 도장(헤더)으로 막는다.
# 1. 요약 — 다섯 단계 한 표
| # | 단계 | 무슨 일이 일어나나 | 우리 값 (실측) |
|---|---|---|---|
| ① | CloudFront 가 ALB 주소를 찾음 | 오리진 도메인을 DNS 로 풀면 **공인 IP 2개**(AZ 당 1개)가 나옴. ALB 는 장비 한 대가 아니라 **AZ 마다 노드 하나** | `mc-alb-public-485062926.ap-northeast-2.elb.amazonaws.com` → `13.124.71.239`(2a) · `3.34.116.99`(2c) · TTL 60 |
| ② | 인터넷을 타고 IGW 도착 | 공인 IP 로 보낸 패킷은 AWS 망을 거쳐 **VPC 의 문 = Internet Gateway** 에 닿음. IGW 는 "공인 IP ↔ VPC 안 사설 IP" 를 1:1 로 바꿔주는 문지기 | `mc-igw` = `igw-0a8434fc99a6e7715` (VPC 에 하나) |
| ③ | 퍼블릭 서브넷 | "퍼블릭" 의 뜻 = 그 서브넷의 **라우팅 테이블에 `0.0.0.0/0 → IGW`** 가 있다는 것뿐. 그래서 ALB 노드는 퍼블릭 서브넷에, WEB·WAS 는 IGW 경로가 없는 프라이빗 서브넷에 둔다 | `mc-rt-public`(`rtb-072d4b3827056d319`): `10.0.0.0/16 → local` · `0.0.0.0/0 → igw-0a8434fc99a6e7715` · 연결 서브넷 `mc-public-a`(10.0.0.0/24) · `mc-public-c`(10.0.1.0/24) |
| ④ | ALB 노드의 ENI + 보안 그룹 | ALB 노드는 서브넷 안에 **네트워크 카드(ENI)** 로 존재하고 사설 IP + 공인 IP 를 가짐. 패킷이 ENI 에 닿기 전 **SG** 가 검사: "CloudFront IP 대역에서 온 443 만" | ENI 2a: `10.0.0.212` ↔ `13.124.71.239` · ENI 2c: `10.0.1.212` ↔ `3.34.116.99` · SG `mc-sg-alb-public`(`sg-0cd291c8a096146ea`) 인바운드 = `443 ← pl-22a6434b`(cloudfront.origin-facing) **한 줄뿐** |
| ⑤ | 리스너 443 | SG 를 통과한 443 연결을 리스너가 받아 TLS 를 풀고 규칙(도장 `X-Origin-Verify` 검사) 적용 → 맞으면 `mc-tg-web`, 아니면 403 | 여기부터가 WEB단 (1단계 이후) |
# 2. 자세히 — 단계마다 "무슨 일 · 우리 값 · 없으면 · 눈으로 확인"
## 2-1. ① CloudFront 가 ALB 주소를 찾음 — DNS 조회는 두 번
**무슨 일이 일어나나**
1. DNS 조회는 **두 번** 일어난다. 첫 번째는 **사용자 브라우저**가 `petclinic.mission-critical.site` 를 푸는 것 — Route 53 호스티드 존의 A/AAAA **별칭(alias)** 레코드가 `d2p7som2iuyba.cloudfront.net` 을 가리키고, 답은 사용자 근처 CloudFront 엣지의 **뷰어 쪽** IP(오늘 `54.230.62.17 · .28 · .45 · .29`). 여기까지는 0단계 밖(사용자 → CloudFront).
2. 두 번째가 이 단계의 시작. 캐시에 없는 요청을 오리진으로 보내야 하는 **엣지**가 오리진 도메인 `mc-alb-public-485062926.ap-northeast-2.elb.amazonaws.com` 을 푼다. 이 이름은 AWS 가 관리하는 ELB 전용 DNS 이고, 답은 **A 레코드 2개 · TTL 60초**: `13.124.71.239`(2a 노드) · `3.34.116.99`(2c 노드).
3. 왜 2개인가: ALB 는 "장비 한 대" 가 아니라 **활성화한 AZ(서브넷)마다 노드 하나 이상**이다. 우리는 ALB 를 만들 때 `mc-public-a` · `mc-public-c` 두 서브넷을 골랐으니 노드도 2개. 부하가 늘면 AWS 가 AZ 안에 노드를 더 띄우고 IP 도 늘어날 수 있다 — 그래서 IP 는 "지금의 답" 일 뿐이고, 응답 순서도 매번 바뀐다(라운드 로빈).
4. 엣지는 그중 하나에 TCP 연결을 시도한다. 실패하면 **다른 IP 로 다시** — CloudFront 오리진 설정 `ConnectionAttempts 3 · ConnectionTimeout 10s`(실측). 노드 하나가 죽어도 최대 10초 뒤 다른 노드로 붙는다.
5. TTL 60초라 엣지는 1분마다 다시 묻는다 → AWS 가 노드를 바꿔도 1분 안에 따라간다. 이것이 "ALB 는 항상 이름으로" 의 실제 메커니즘.

**우리 값**
| 항목 | 값 (9/17) |
|---|---|
| 사용자 → CloudFront | `petclinic.mission-critical.site` A/AAAA alias → `d2p7som2iuyba.cloudfront.net` (Route 53 존 `Z0299891BL9WGKOA2LW9`) · 답 `54.230.62.x` 4개 = 뷰어 쪽 엣지 |
| CloudFront → 오리진 | 오리진 ID `alb-public` · 도메인 = ALB DNS 이름(IP 아님) · `https-only` · 443 · TLSv1.2 · 연결 시도 **3회** · 연결 제한 **10s** · 응답 대기 30s · keep-alive 5s |
| ALB DNS 의 답 | `13.124.71.239`(ap-northeast-2a) · `3.34.116.99`(ap-northeast-2c) · TTL **60** |
**없으면 · 오해**
- ALB 에는 **고정 IP 가 없다**(EIP 못 붙임). 어딘가에 IP 를 적어 두면 언젠가 깨진다. 고정 IP 가 꼭 필요하면 NLB 나 Global Accelerator 를 앞에 두는 게 정석.
- "CloudFront 는 우리 VPC 안에 있다" — 아니다. 엣지는 우리 계정 밖 AWS 의 전 세계 거점이고, 오리진에는 **공인 IP 로 인터넷을 통해** 온다. 그래서 ② 가 필요하다.
- 뷰어 쪽 IP(`54.230.x`) 와 오리진 쪽 IP(④ 의 접두사 목록)는 **다른 대역**이다. SG 에 뷰어 쪽 IP 를 넣으면 CloudFront 가 못 들어온다.

**눈으로 확인**

```bash
# 1) 오리진 이름 → 노드 IP 2개 · TTL 60 (두 번 실행하면 순서가 바뀜)
dig mc-alb-public-485062926.ap-northeast-2.elb.amazonaws.com A +noall +answer
# 2) 사용자 쪽은 다른 답 — CloudFront 뷰어 IP 4개
dig +short petclinic.mission-critical.site
# 3) CloudFront 오리진 설정 — 이름 · 시도 3 · 제한 10 · https-only
aws cloudfront get-distribution-config --id E2PWXW3LUYTDEE --profile mc-deploy --query 'DistributionConfig.Origins.Items[?Id==`alb-public`].[DomainName,ConnectionAttempts,ConnectionTimeout,CustomOriginConfig.OriginProtocolPolicy]' --output table
```

기대: 1) `60 IN A 3.34.116.99` · `60 IN A 13.124.71.239` 2) `54.230.62.x` 4줄 3) `mc-alb-public-… 3 10 https-only`
## 2-2. ② 인터넷을 타고 IGW 도착 — 주소가 바뀌는 유일한 곳
**무슨 일이 일어나나**
1. 엣지가 `3.34.116.99:443` 으로 TCP SYN 을 보낸다. 출발지는 그 엣지의 **오리진 쪽** IP — 오늘 ALB 로그에 찍힌 `15.158.254.101` 같은 주소.
2. 공인 IP 는 전 세계에서 유일하고, `3.34.x.x` 대역은 AWS 서울 리전이 인터넷에 "내 것" 이라고 광고한다. 그래서 어느 나라 엣지에서 보내든 패킷은 서울 리전 망에 도착한다. (CloudFront → 리전 구간은 대부분 AWS 백본을 타지만 **주소 체계는 공용 인터넷** — 우리 VPC 와 전용선이 있는 게 아니다.)
3. 리전 망은 "`3.34.116.99` 는 `vpc-04e04849604e2fadb` 의 ENI `eni-0e503b259544d7136` 에 **연결(association)** 된 주소" 라는 걸 안다. 그 VPC 에 붙은 **Internet Gateway(mc-igw)** 가 패킷의 **목적지를 `3.34.116.99` → `10.0.1.212` 로 바꿔** VPC 안으로 넣는다. 출발지 `15.158.254.101` 은 그대로 — 그래서 ALB 로그의 client 필드에 CloudFront IP 가 남는다.
4. 응답은 반대. `10.0.1.212 → 15.158.254.101` 로 나가는 패킷의 **출발지**를 IGW 가 `3.34.116.99` 로 되돌려 인터넷으로 내보낸다. 이 "1:1 변환" 이 IGW 가 하는 일의 전부다.

**IGW 가 하는 것 · 안 하는 것**
| 한다 | 안 한다 (그건 누가) |
|---|---|
| 공인 IP ↔ 사설 IP **1:1** 변환 | 패킷 거르기 — SG(④) · NACL(③) |
| VPC ↔ 인터넷 **양방향** 통로 (공인 IP 가진 ENI 만) | 경로 결정 — 라우팅 테이블(③) |
| 수평 확장·이중화 (AWS 관리 · 대역폭 한도·단일 장애점 없음 · 무료) | 암호 풀기 — 리스너(⑤) |
| VPC 당 1개 · 서브넷이 아니라 **VPC 에 연결(attach)** · 자체 IP 없음 | 여러 사설 IP 를 공인 IP 하나로 — 그건 NAT Gateway |
**IGW vs NAT Gateway — 둘 다 "게이트웨이" 인데 방향이 반대**
|  | Internet Gateway | NAT Gateway |
|---|---|---|
| 방향 | 들어오고 나가고 | **나가기만** (밖에서 시작한 연결은 못 들어옴) |
| 변환 | 공인 1 ↔ 사설 1 | 사설 여러 개 → NAT 의 공인 IP **하나** (포트로 구분) |
| 누가 쓰나 | 공인 IP 가진 ENI: ALB 노드 · NAT GW 자신 · Bastion | 공인 IP 없는 WEB·WAS (dnf · git · Maven · Secrets Manager) |
| 우리 값 | `mc-igw` `igw-0a8434fc99a6e7715` | `mc-nat-a` 43.202.96.72(10.0.0.135) · `mc-nat-c` 52.78.238.44(10.0.1.184) — **퍼블릭 서브넷에 앉아** IGW 로 나간다 |
| 비용 | 무료 | 시간당 + GB 당 |
**없으면 · 오해**
- IGW 를 VPC 에서 떼면: 공인 IP 가 있어도 아무것도 못 들어오고 못 나간다. NAT 도 IGW 를 통해 나가므로 WEB·WAS 의 dnf·git 까지 멈춘다.
- "IGW 가 방화벽" — 아니다, 아무것도 안 막는다. "IGW 를 붙이면 VPC 전체가 인터넷에 열린다" — 아니다, ③ 의 경로가 있는 서브넷 + 공인 IP 가진 ENI 만.
- 계정엔 기본 VPC(172.31.0.0/16)의 IGW `igw-03d9f74dc07a502b0` 도 있다 — 우리 것 아님. 콘솔에서 헷갈리지 말 것.

**눈으로 확인**

```bash
# 1) IGW 가 우리 VPC 에 붙어 있나
aws ec2 describe-internet-gateways --profile mc-deploy --region ap-northeast-2 --query 'InternetGateways[].[InternetGatewayId,Tags[?Key==`Name`].Value|[0],Attachments[0].VpcId,Attachments[0].State]' --output table
# 2) 공인 IP 로 "짝" 사설 IP 를 역추적 — IGW 가 바꿔 주는 그 쌍
aws ec2 describe-network-interfaces --profile mc-deploy --region ap-northeast-2 --filters Name=association.public-ip,Values=3.34.116.99 --query 'NetworkInterfaces[].[NetworkInterfaceId,PrivateIpAddress,SubnetId,RequesterId]' --output table
# 3) ALB 로그에 남은 CloudFront 오리진 쪽 IP (client 필드 = 4번째) — 출발지는 안 바뀐다는 증거
K=$(aws s3 ls s3://mc-logs-528821350786/alb/public/ --recursive --profile mc-deploy | grep -v TestFile | tail -1 | awk '{print $4}')
aws s3 cp "s3://mc-logs-528821350786/$K" - --profile mc-deploy | zcat | grep -v health.html | tail -1 | awk '{print "client="$4, "target="$5}'
```

기대: 1) `igw-0a8434fc99a6e7715 mc-igw vpc-04e04849604e2fadb available` 2) `eni-0e503b259544d7136 10.0.1.212 subnet-0a2f8e0cccc9c9b4e amazon-elb` 3) `client=15.158.254.101:19438 target=10.0.11.89:80` (IP 는 그때그때 다름)
## 2-3. ③ 퍼블릭 서브넷 — "퍼블릭" 은 속성이 아니라 경로 한 줄
**무슨 일이 일어나나**
1. IGW 가 넣어 준 패킷의 목적지 `10.0.1.212` 는 `mc-public-c`(10.0.1.0/24) 안이다. 서브넷 = VPC(10.0.0.0/16) 를 **AZ 하나 안에서** 잘라 낸 조각. 서브넷은 AZ 를 넘지 못한다 — 그래서 a·c 두 벌.
2. AWS 에 "퍼블릭 서브넷" 이라는 설정은 **없다**. 그 서브넷에 연결된 **라우팅 테이블에 `0.0.0.0/0 → igw-…` 행이 있으면** 우리가 퍼블릭이라 부를 뿐이다.
3. 라우팅 테이블은 **나가는** 패킷의 문을 정한다. 목적지와 가장 길게 맞는 행이 이긴다(longest prefix match). `10.0.x.x` 로 가면 `10.0.0.0/16 local`(VPC 안 서브넷끼리는 AZ 가 달라도 항상 통함 · 자동 생성 · 삭제 불가), 그 밖의 모든 곳은 `0.0.0.0/0` 행 — 이 행이 IGW 면 퍼블릭, NAT 면 프라이빗, **없으면** 인터넷으로 나갈 길조차 없는 서브넷.
4. 인터넷과 **직접** 통신하려면 조건이 둘: (a) 서브넷 경로에 IGW (b) ENI 에 공인 IP. ALB 노드 ENI 는 둘 다 있다. WEB EC2 는 둘 다 없다(공인 IP 없음 · 경로는 NAT) → 밖에서 절대 못 들어온다.
5. 응답 패킷 `10.0.1.212 → 15.158.254.101` 은 `10.0.0.0/16` 이 아니므로 `0.0.0.0/0 → igw` 행을 타고 ② 로 돌아간다.

**우리 값 — 라우팅 테이블 5개 · 서브넷 8개**
| 라우팅 테이블 | `0.0.0.0/0` 행 | 연결 서브넷 | 뜻 |
|---|---|---|---|
| `mc-rt-public` rtb-072d4b3827056d319 | → `igw-0a8434fc99a6e7715` | mc-public-a 10.0.0.0/24 · mc-public-c 10.0.1.0/24 | **퍼블릭** — ALB 노드 · NAT · Bastion 이 산다 |
| `mc-rt-private-a` rtb-021d58f11c8d88e66 | → `nat-002efce15d5c6e531`(mc-nat-a) | mc-web-a 10.0.10.0/24 · mc-was-a 10.0.20.0/24 | 프라이빗 — 나가기만. a 는 a 의 NAT 로 |
| `mc-rt-private-c` rtb-06c9927a9a1c0a750 | → `nat-0166fba96fbc08859`(mc-nat-c) | mc-web-c 10.0.11.0/24 · mc-was-c 10.0.21.0/24 | 프라이빗 — c 는 c 의 NAT 로 (AZ 장애 격리) |
| `mc-rt-db` rtb-0ad4130b7b8557059 | **없음** (local 만) | mc-db-a 10.0.30.0/24 · mc-db-c 10.0.31.0/24 | 격리 — DB 는 인터넷으로 나갈 길도 없음 |
| (기본 · main) rtb-0372527df00c51e4a | 없음 | 연결 서브넷 0 | 안 씀. 새 서브넷을 만들면 기본으로 여기 붙는다 — 주의 |
모든 서브넷이 `MapPublicIpOnLaunch = False` — EC2 를 퍼블릭 서브넷에 만들어도 공인 IP 가 자동으로 안 붙는다. ALB 노드의 공인 IP 는 ALB 서비스가, Bastion 의 것은 EIP 로 **따로** 붙인 것.

**NACL 한 줄**: 서브넷 단위의 또 다른 필터(SG 와 달리 **상태 비저장** — 응답 방향도 규칙이 있어야 통과). 우리는 VPC 기본 NACL `acl-0db588d653ae2e392` 하나가 8개 서브넷 전부에 붙어 있고 규칙은 `100 allow 0.0.0.0/0`(인·아웃) 뿐 = **다 통과**. 막는 일은 ④ SG 가 한다.

**없으면 · 오해**
- internet-facing ALB 를 프라이빗(NAT) 서브넷에 두면: 요청은 IGW 로 들어와도 응답이 NAT 로 나가며 출발지가 NAT IP 로 바뀌어 연결이 성립하지 않는다 → 콘솔도 경고. **반드시 퍼블릭 서브넷 2개 이상(AZ 2개)**, 서브넷당 여유 IP 8개 이상(/27 이상). 우리 /24 는 248개 남음.
- "프라이빗 서브넷 = 인터넷 못 씀" — 나가는 건 NAT 로 된다(dnf · git). 못 하는 건 **밖에서 시작하는 연결**.
- 새 서브넷을 만들고 라우팅 테이블 연결을 잊으면 기본(main) 테이블에 붙어 인터넷 경로가 없다 — "NAT 있는데 왜 안 나가지" 의 흔한 원인.

**눈으로 확인**

```bash
# 1) 우리 VPC 의 라우팅 테이블 전부 — 이름 · 0.0.0.0/0 의 문 · 연결 서브넷
aws ec2 describe-route-tables --profile mc-deploy --region ap-northeast-2 --filters Name=vpc-id,Values=vpc-04e04849604e2fadb --query 'RouteTables[].{name:Tags[?Key==`Name`].Value|[0],routes:Routes[].[DestinationCidrBlock,GatewayId,NatGatewayId],subnets:Associations[].SubnetId}' --output json
# 2) 서브넷 8개 — CIDR · AZ · 공인 IP 자동 할당(전부 False) · 남은 IP
aws ec2 describe-subnets --profile mc-deploy --region ap-northeast-2 --filters Name=vpc-id,Values=vpc-04e04849604e2fadb --query 'sort_by(Subnets,&CidrBlock)[].[Tags[?Key==`Name`].Value|[0],CidrBlock,AvailabilityZone,MapPublicIpOnLaunch,AvailableIpAddressCount]' --output table
# 3) NACL — 기본 하나 · 8개 서브넷 · allow all
aws ec2 describe-network-acls --profile mc-deploy --region ap-northeast-2 --filters Name=vpc-id,Values=vpc-04e04849604e2fadb --query 'NetworkAcls[].[NetworkAclId,IsDefault,length(Associations),Entries[?RuleNumber==`100`].[Egress,RuleAction,CidrBlock]]' --output json
```

기대: 1) public 만 `igw-…`, private-a/c 는 `nat-…`, db 는 local 한 줄 2) 8줄 전부 `False` 3) `acl-0db588d653ae2e392 true 8` + allow 두 줄
## 2-4. ④ ALB 노드의 ENI + 보안 그룹 — 실제로 막는 곳
**무슨 일이 일어나나**
1. **ENI** = 서브넷 안의 가상 네트워크 카드. MAC · 사설 IP · (선택) 공인 IP 연결 · **보안 그룹** 을 가진다. EC2 를 만들면 ENI 가 자동으로 하나 생기고, ALB · NAT GW · RDS Proxy 처럼 **AWS 가 대신 운영하는 서비스도 우리 서브넷에 들어올 땐 ENI 를 하나 만들어 앉는다**. 그래서 EC2 콘솔 → 네트워크 인터페이스 에서 "ELB app/mc-alb-public/…" 설명의 ENI 2개가 보인다(요청자 `amazon-elb` — 우리가 지울 수 없음, ALB 가 스케일하면 늘어남 = ① 에서 IP 가 바뀌는 이유).
2. 패킷이 ENI 에 닿기 **직전** SG 가 검사한다. SG 규칙은 **허용만** 쓸 수 있고(deny 없음), 어느 한 규칙에라도 맞으면 통과, 하나도 안 맞으면 **조용히 버린다**(거부 응답 없음 → 상대는 "timeout").
3. SG 는 **상태 저장**: 인바운드로 허용된 연결의 응답 패킷은 아웃바운드 규칙과 상관없이 나간다(반대도). 그래서 인바운드 443 한 줄이면 응답은 신경 안 써도 된다.
4. 우리 인바운드는 **한 줄**: TCP 443 ← 접두사 목록 `pl-22a6434b`. 아웃바운드는 기본값 전체 허용 — ALB 노드가 ⑤ 에서 WEB 서버 80 으로 **새 연결을 여는** 쪽이라 필요하다.
5. 받는 쪽 짝: `mc-sg-web` 인바운드 = **80 ← sg-0cd291c8a096146ea(ALB 의 SG)**. IP 가 아니라 **SG 를 소스**로 적었기 때문에 ALB 노드 IP 가 바뀌어도 규칙은 그대로다. (+ 22 ← Bastion SG)

**우리 값**
| 항목 | 값 (9/17) |
|---|---|
| ENI 2a | `eni-02ac8872c2eb25b2a` · subnet-0d546d02b6be9f330(mc-public-a) · `10.0.0.212` ↔ `13.124.71.239` · SG sg-0cd291c8a096146ea |
| ENI 2c | `eni-0e503b259544d7136` · subnet-0a2f8e0cccc9c9b4e(mc-public-c) · `10.0.1.212` ↔ `3.34.116.99` · 같은 SG |
| 같은 서브넷의 이웃 | NAT `10.0.0.135`↔43.202.96.72 · `10.0.1.184`↔52.78.238.44 · Bastion `10.0.0.13`↔52.78.145.87 — 퍼블릭 서브넷엔 이 셋(ALB 노드·NAT·Bastion)만 산다 |
| SG `mc-sg-alb-public` 인바운드 | `tcp 443 ← pl-22a6434b` "HTTPS from CloudFront origin-facing prefix list" — **이 한 줄뿐** (80 없음 · CIDR 없음) |
| SG 아웃바운드 | `all → 0.0.0.0/0` (기본값) |
| 접두사 목록 `pl-22a6434b` | `com.amazonaws.global.cloudfront.origin-facing` · 소유 AWS · **46개 CIDR ≈ 34만 IP** · AWS 가 갱신 |
| 짝 `mc-sg-web` 인바운드 | `80 ← sg-0cd291c8a096146ea` · `22 ← sg-087572b9531c73e17(Bastion)` |
**접두사 목록 — 이름의 "origin-facing" 이 핵심**: CloudFront 는 IP 가 두 종류다. 사용자가 접속하는 **뷰어 쪽**(① 의 `54.230.62.x`) 과 오리진에 **연결할 때 출발지로 쓰는 오리진 쪽**. SG 엔 오리진 쪽만 있으면 된다. 실측: ALB 로그의 client `15.158.254.101` 은 목록의 `15.158.0.0/16` 안, 다른 줄의 `3.172.65.112` 는 `3.172.64.0/18` 안. 반면 뷰어 쪽 `54.230.62.29` 와 내 PC `221.148.195.245` 는 **없음**. 46개를 손으로 CIDR 로 적으면 AWS 가 대역을 늘릴 때마다 깨진다 — 목록이면 규칙 한 줄로 끝.

**막히면 어떻게 보이나 (실측)**: 내 PC(221.148.195.245)에서 `https://13.124.71.239/` → 6초 후 timeout(curl exit 28), `http://…:80` 도 timeout. 같은 순간 CloudFront 경유 `https://petclinic.mission-critical.site/` → 200. **"연결 거부(refused)" 가 아니라 "시간 초과"** 인 게 SG 의 특징 — 포트가 열렸는지조차 안 알려 준다.

**80 을 왜 안 여나**: HTTP → HTTPS 리다이렉트는 CloudFront 가 한다(뷰어 프로토콜 정책 `redirect-to-https`, 실측 `http://petclinic…` → 301 → https). ALB 는 80 을 듣지도 않고 SG 도 안 연다 → 평문 요청은 VPC 문턱에도 못 온다.

**없으면 · 오해**
- 인바운드를 `443 ← 0.0.0.0/0` 로 열면: 인터넷 전체가 ALB 를 직접 친다 → WAF·CloudFront 우회. SG 는 1차 필터 — 공격면을 "인터넷 전체" 에서 "CloudFront 대역" 으로 줄인다.
- "CloudFront 대역만 열었으니 남은 못 들어온다" — **남의 CloudFront 배포**도 같은 대역에서 온다. 누가 자기 배포의 오리진을 우리 ALB 로 지정하면 SG 는 통과 → 2차 검사가 ⑤ 의 도장 헤더(4단계).
- WEB SG 에 `80 ← 10.0.0.0/24` 처럼 IP 로 적으면: 지금은 맞지만 ALB 가 노드를 옮기거나 서브넷을 바꾸면 깨진다. SG 참조가 정석.

**눈으로 확인**

```bash
# 1) ENI 2개 — AZ · 서브넷 · 사설 · 공인 · SG
aws ec2 describe-network-interfaces --profile mc-deploy --region ap-northeast-2 --filters "Name=description,Values=ELB app/mc-alb-public/*" --query 'NetworkInterfaces[].[AvailabilityZone,SubnetId,PrivateIpAddress,Association.PublicIp,Groups[0].GroupId]' --output table
# 2) SG 규칙 전부 (인·아웃) — 인바운드 한 줄
aws ec2 describe-security-group-rules --profile mc-deploy --region ap-northeast-2 --filters Name=group-id,Values=sg-0cd291c8a096146ea --query 'SecurityGroupRules[].[IsEgress,IpProtocol,FromPort,ToPort,PrefixListId,CidrIpv4]' --output table
# 3) 접두사 목록 — 항목 수 · 로그의 CloudFront IP 가 든 대역
aws ec2 get-managed-prefix-list-entries --profile mc-deploy --region ap-northeast-2 --prefix-list-id pl-22a6434b --query 'length(Entries)'
aws ec2 get-managed-prefix-list-entries --profile mc-deploy --region ap-northeast-2 --prefix-list-id pl-22a6434b --query 'Entries[?starts_with(Cidr, `15.158.`)].Cidr' --output text
# 4) 내 PC 에서 직접 → timeout (SG 가 버림) · CloudFront 경유 → 200 · http → 301
curl -sk -o /dev/null -m 6 -w "direct http=%{http_code} exit=" https://13.124.71.239/; echo $?
curl -s -o /dev/null -w "via-cf http=%{http_code}\n" https://petclinic.mission-critical.site/
curl -s -o /dev/null -w "http-> %{http_code} %{redirect_url}\n" http://petclinic.mission-critical.site/
# 5) WEB SG 는 ALB SG 를 소스로
aws ec2 describe-security-group-rules --profile mc-deploy --region ap-northeast-2 --filters Name=group-id,Values=sg-069f3c3368649799b --query 'SecurityGroupRules[?IsEgress==`false`].[FromPort,ReferencedGroupInfo.GroupId,Description]' --output table
```

기대: 1) 2a `10.0.0.212 13.124.71.239` · 2c `10.0.1.212 3.34.116.99`, SG 같음 2) `False tcp 443 443 pl-22a6434b None` + `True -1 … 0.0.0.0/0` 3) `46` · `15.158.0.0/16` 4) `direct http=000 exit=28` · `via-cf http=200` · `301 https://…` 5) `80 sg-0cd291c8a096146ea` · `22 sg-087572b9531c73e17 SSH from Bastion`
## 2-5. ⑤ 리스너 443 — 문 안에서 처음 하는 일
**무슨 일이 일어나나**
리스너 = "이 포트·프로토콜로 오는 연결을 받겠다" 는 ALB 의 귀. 우리는 **443 HTTPS 하나뿐**(80 없음). SG 를 통과한 TCP 연결이 리스너에 닿으면 순서대로:
1. **TLS 핸드셰이크** — CloudFront 가 SNI 로 `petclinic.mission-critical.site` 를 말하면 리스너가 그 이름의 ACM 인증서(서울 리전 · RSA-2048 · 만료 2027-04-01)를 내밀고, 보안 정책 `ELBSecurityPolicy-TLS13-1-2-2021-06`(TLS 1.2·1.3 만) 안에서 암호를 고른다. 로그 실측: `TLSv1.3 TLS_AES_128_GCM_SHA256`. 여기서 암호가 **풀린다** — 이 뒤 VPC 안은 평문 HTTP(2단계).
2. **HTTP 요청 해석** — 메서드 · 경로 · 헤더를 읽고 `X-Forwarded-For`(뒤에 CloudFront IP 를 **덧붙임**, `xff_header_processing.mode = append`) · `X-Forwarded-Proto: https` · `X-Forwarded-Port: 443` 을 붙인다(1단계).
3. **규칙 평가** — 우선순위 숫자가 작은 것부터, **첫 매치에서 끝**. 규칙 10: 조건 `http-header X-Origin-Verify` = (비밀 값 · tfvars 에만) → 작업 `forward → mc-tg-web`. 어느 규칙도 안 맞으면 **기본 작업 = fixed-response 403**. 로그의 `matched_rule_priority` 가 10 이면 통과, 0 이면 403.
4. **대상 그룹 → 대상** — `mc-tg-web` 의 정상 대상(web-a `10.0.10.189:80` · web-c `10.0.11.89:80`) 중 하나로, ALB 노드가 **자기 사설 IP(10.0.0.212 / 10.0.1.212)에서 새 HTTP/1.1 평문 연결**을 연다. Apache access_log 첫 필드에 그 IP 가 찍히는 이유(8단계). 교차 영역이 켜져 있어 2c 노드가 web-a 로도 보낸다(7단계).

여기까지가 "입구". 리스너·규칙·대상 그룹의 속살은 3단계, 도장은 4단계, 정상/비정상 판정은 5단계.

**우리 값**
| 항목 | 값 (9/17) |
|---|---|
| 리스너 | `443 HTTPS` 하나 · 정책 `ELBSecurityPolicy-TLS13-1-2-2021-06` · 인증서 ACM `…/14198286-7863-4608-b164-3de4bb97f784` (`petclinic.mission-critical.site` · ISSUED · RSA-2048 · 2027-04-01 만료) |
| 기본 작업 | `fixed-response 403` |
| 규칙 10 | `http-header X-Origin-Verify` (값 비공개) → `forward mc-tg-web` |
| ALB 속성 | `idle_timeout 60` · `http2 true`(뷰어 쪽만) · `xff append` · `drop_invalid_header_fields false` |
| 대상 | web-a `10.0.10.189:80` · web-c `10.0.11.89:80` (둘 다 공인 IP 없음) |
**없으면 · 오해**
- 규칙 10 이 사라지거나 값이 어긋나면 **모든 요청이 403** — 9단계 장애 E. 점검 페이지도 안 뜬다(CloudFront 는 502·503·504 만 바꿈).
- 80 리스너를 추가해도 SG 가 80 을 안 열어 아무도 못 닿는다 — 리스너와 SG 는 **둘 다** 맞아야 한다(자주 하는 실수: 리스너만 만들고 "왜 안 되지").
- "ALB 가 요청을 그대로 전달한다" — 아니다. TCP 연결은 **두 개**(엣지↔ALB · ALB↔Apache)로 끊어져 있고, 두 번째는 ALB 가 새로 만든 평문 연결이다. 그래서 타임아웃·keep-alive 를 양쪽 따로 본다(7단계).

**눈으로 확인**

```bash
ALB=$(aws elbv2 describe-load-balancers --names mc-alb-public --profile mc-deploy --region ap-northeast-2 --query 'LoadBalancers[0].LoadBalancerArn' --output text)
# 1) 리스너 — 443 하나 · 정책 · 기본 403
aws elbv2 describe-listeners --load-balancer-arn $ALB --profile mc-deploy --region ap-northeast-2 --query 'Listeners[].[Port,Protocol,SslPolicy,DefaultActions[0].Type,DefaultActions[0].FixedResponseConfig.StatusCode]' --output table
# 2) 규칙 — 10: http-header X-Origin-Verify → forward · default: fixed-response  (값(Values)은 일부러 안 뽑는다)
L=$(aws elbv2 describe-listeners --load-balancer-arn $ALB --profile mc-deploy --region ap-northeast-2 --query 'Listeners[0].ListenerArn' --output text)
aws elbv2 describe-rules --listener-arn $L --profile mc-deploy --region ap-northeast-2 --query 'Rules[].[Priority,Conditions[].HttpHeaderConfig.HttpHeaderName,Actions[].Type]' --output json
# 3) 인증서 — 이름 · 상태 · 만료
C=$(aws elbv2 describe-listeners --load-balancer-arn $ALB --profile mc-deploy --region ap-northeast-2 --query 'Listeners[0].Certificates[0].CertificateArn' --output text)
aws acm describe-certificate --certificate-arn $C --profile mc-deploy --region ap-northeast-2 --query 'Certificate.[DomainName,Status,NotAfter]' --output text
# 4) ALB 로그 마지막 줄 — client · target · 코드 · 매치된 규칙(10 이면 도장 통과)
K=$(aws s3 ls s3://mc-logs-528821350786/alb/public/ --recursive --profile mc-deploy | grep -v TestFile | tail -1 | awk '{print $4}')
aws s3 cp "s3://mc-logs-528821350786/$K" - --profile mc-deploy | zcat | grep -v health.html | tail -1 | awk -F'"' '{split($1,h," "); split($11,a," "); print "client="h[4], "target="h[5], "elb="h[9], "tgt="h[10], "rule="a[1]}'
```

기대: 1) `443 HTTPS ELBSecurityPolicy-TLS13-1-2-2021-06 fixed-response 403` 2) `["10",["X-Origin-Verify"],["forward"]]` · `["default",[],["fixed-response"]]` 3) `petclinic.mission-critical.site ISSUED 2027-04-01…` 4) `… elb=200 tgt=200 rule=10`
## 2-6. 한 패킷의 여행 — 주소가 어떻게 바뀌나 (9/17 13:37 실측 요청)
내 PC 에서 `curl https://petclinic.mission-critical.site/` 한 번이 남긴 흔적으로 ①~⑤ 를 한 줄에 잇는다.
| 구간 | 출발지 → 목적지 | 누가 정했나 |
|---|---|---|
| 내 PC → CloudFront | 221.148.195.245 → 54.230.62.29:443 (뷰어 쪽 엣지) | Route 53 alias (0단계 밖) |
| ① 엣지 → 인터넷 | 15.158.254.101:19438 → 3.34.116.99:443 | 엣지가 ALB DNS 답 2개 중 2c 노드를 고름 |
| ② IGW 통과 | 15.158.254.101:19438 → **10.0.1.212**:443 | IGW 가 목적지만 공인 → 사설 |
| ③ 서브넷 | 10.0.1.212 ∈ mc-public-c (10.0.1.0/24) · 경로표 mc-rt-public | — |
| ④ SG 검사 | 15.158.254.101 ∈ pl-22a6434b(15.158.0.0/16) · tcp 443 → 통과 | mc-sg-alb-public |
| ⑤ 리스너 | TLS 1.3 해제 → 규칙 10 매치(도장 OK) → mc-tg-web | ALB |
| ⑤ 노드 → 대상 (새 연결) | 10.0.1.212:(임의 포트) → 10.0.11.89:80 (web-c · 평문) | 라운드 로빈 · mc-sg-web `80 ← ALB SG` 통과 |
| 응답 대상 → 노드 | 10.0.11.89:80 → 10.0.1.212 | `10.0.0.0/16 local` |
| 응답 노드 → 엣지 | 10.0.1.212:443 → 15.158.254.101 ⇒ IGW 가 출발지를 **3.34.116.99** 로 | `0.0.0.0/0 → igw` |
| 로그 (ALB) | client `15.158.254.101:19438` · target `10.0.11.89:80` · `200 200` · ip_address(34번째 필드) `3.34.116.99` | 8단계 |
기억할 것 셋: **TCP 연결은 2개**(엣지↔노드 · 노드↔Apache) · **주소를 바꾸는 건 IGW 뿐**(SG·라우팅은 안 바꿈) · **막는 건 SG 뿐**(IGW·NACL 은 다 통과).
# 3. 용어 — 이 단계에서만 쓰는 것
| 용어 | 한 줄 | 비유 |
|---|---|---|
| VPC | 우리만 쓰는 사설 IP 공간 `10.0.0.0/16` (65,536개) | 병원 부지 |
| 서브넷 | VPC 를 AZ 별·용도별로 자른 조각. 우리는 8개(public·web·was·db × a·c) | 층·구역 |
| 라우팅 테이블 | "이 목적지는 어느 문으로" 표. 서브넷마다 하나 연결. 우리는 5개(public · private-a · private-c · db · 기본) | 구역별 안내판 |
| Internet Gateway | 인터넷 ↔ VPC 문. **들어오고 나가고** 둘 다(공인 IP 가진 것만). 공인↔사설 1:1 변환 | 정문 |
| NAT Gateway | 프라이빗 서브넷이 **나가기만** 할 때(dnf · git · Maven). 밖에서 들어올 수 없음. AZ 당 1개(`mc-nat-a`·`mc-nat-c`) — 한 AZ 가 죽어도 다른 AZ 는 계속 나감 | 직원 전용 뒷문(밖으로만) |
| ENI | 서브넷 안의 네트워크 카드. EC2 도 ALB 도 NAT 도 RDS Proxy 도 전부 ENI 로 서브넷에 앉는다 | 구역에 놓인 전화기 |
| 보안 그룹(SG) | ENI 앞의 방화벽. **상태 저장** — 들어온 연결의 응답은 자동 허용. 허용 규칙만 · 안 맞으면 조용히 버림. 소스는 CIDR · 다른 SG · 접두사 목록 | 구역 출입문 경비 |
| NACL | 서브넷 앞의 방화벽. **상태 비저장**(응답도 규칙 필요) · allow/deny 둘 다. 우리는 기본값 = 다 통과 | 층 입구 안내원(지금은 다 들여보냄) |
| 접두사 목록(prefix list) | AWS 가 관리하는 IP 대역 묶음. `com.amazonaws.global.cloudfront.origin-facing` = 오리진으로 나가는 CloudFront IP 전부(46개 CIDR). CIDR 을 손으로 적으면 CloudFront IP 가 바뀔 때마다 깨지므로 이걸 씀 | "택배 회사 차량 번호판 목록" |
| 뷰어 쪽 IP vs 오리진 쪽 IP | CloudFront 가 사용자를 맞는 IP(`54.230.x`) 와 오리진에 연결할 때 쓰는 IP(접두사 목록)는 다르다. SG 엔 오리진 쪽만 | 택배 회사의 "접수 창구" 와 "배송 차량" |
| ALB 노드 · DNS 이름 | AZ 마다 노드 1개, IP 는 바뀔 수 있어 항상 **이름**으로 참조(CloudFront 오리진도 이름). TTL 60 | 안내데스크는 층마다 하나, 위치는 바뀔 수 있으니 "안내데스크" 라고 부름 |
# 4. 왜 이렇게 만들었나 (멘토가 물을 만한 것)
- **왜 ALB 만 퍼블릭 서브넷에?** 인터넷에서 직접 닿아야 하는 건 ALB 뿐. WEB·WAS·DB 는 IGW 경로가 없어 밖에서 절대 못 들어온다(나갈 땐 NAT).
- **왜 DB 서브넷엔 NAT 경로도 없나?** RDS 는 패치·백업을 AWS 가 하므로 나갈 이유가 없다. 경로를 안 주는 게 "실수로도 못 나가는" 가장 싼 격리.
- **왜 SG 소스가 CIDR 이 아니라 접두사 목록?** CloudFront IP 는 수시로 바뀜(9/17 기준 46개 대역). 접두사 목록은 AWS 가 갱신.
- **SG 로 CloudFront IP 만 열었는데 왜 도장(헤더)까지?** 그 IP 대역은 **전 세계 모든 고객의 CloudFront 가 공유**. 남이 자기 CloudFront 배포의 오리진을 우리 ALB 로 지정하면 SG 는 통과한다 → 우리 배포만 아는 비밀 헤더로 2차 검사. (WEB단 4단계에서 자세히)
- **NAT 를 왜 2개?** AZ 당 1개. NAT 하나면 그 AZ 장애 때 반대편 AZ 의 서버들도 인터넷(dnf·Secrets)을 못 나감. 멘토링에서 확인.
- **CloudFront → ALB 를 왜 HTTPS 로 다시?** 공용 인터넷 구간이라. ALB 에 서울 ACM 인증서가 붙어 있고 CloudFront 오리진 프로토콜은 HTTPS only.
- **80 리스너는 왜 없나?** HTTP→HTTPS 리다이렉트는 CloudFront 가 이미 한다. ALB 가 80 을 들으면 SG 도 80 을 열어야 하고, 그러면 평문이 VPC 까지 들어온다.
# 5. 다음 단계(1. HTTP 기초) 진입 기준
**Q1. "퍼블릭 서브넷" 과 "프라이빗 서브넷" 의 차이는 딱 하나다. 무엇인가?**
라우팅 테이블에 `0.0.0.0/0 → Internet Gateway` 경로가 있느냐. 있으면 퍼블릭(공인 IP 를 가진 ENI 가 인터넷과 직접 통신), 없으면 프라이빗(나갈 땐 NAT, 들어올 길 없음). 우리 db 서브넷은 그 행 자체가 없어 나갈 길도 없다.

**Q2. 패킷의 IP 주소를 바꾸는 건 누구이고, 무엇을 언제 바꾸나?**
IGW 뿐. 들어올 때 **목적지**를 공인(3.34.116.99) → 사설(10.0.1.212) 로, 나갈 때 **출발지**를 사설 → 공인으로. 출발지(CloudFront IP)는 들어올 때 안 바뀌어 ALB 로그의 client 에 남는다. SG·라우팅 테이블·NACL 은 주소를 건드리지 않는다.

**Q3. 내 PC 에서 ALB 공인 IP 를 직접 치면 "거부" 가 아니라 "시간 초과" 다. 왜?**
SG 는 안 맞는 패킷을 응답 없이 버린다(drop). 포트가 닫혔다는 RST 도 안 보내므로 상대는 열렸는지조차 모른다. 내 IP 가 CloudFront 오리진 쪽 접두사 목록에 없기 때문.

**Q4. SG 에 CloudFront 접두사 목록만 열면 남의 CloudFront 도 통과한다. 그럼 SG 는 왜 두나?**
1차 필터. 인터넷 전체 → CloudFront 대역으로 공격면을 크게 줄이고, 그 안에서 우리 배포만 골라내는 건 리스너 규칙의 헤더(2차). 둘이 겹쳐야 우회를 막는다.

# 6. 읽을 자료 (각 5~10분)
- AWS 문서 — *VPC 의 작동 방식* (서브넷 · 라우팅 테이블 · 인터넷 게이트웨이 절)
- AWS 문서 — *Application Load Balancer 의 작동 방식* ("로드 밸런서 노드" · "가용 영역" 절)
- AWS 문서 — *Restricting access to Application Load Balancers* (CloudFront 접두사 목록 + 커스텀 헤더 — 우리 설계 그대로)
- AWS 문서 — *Access logs for your Application Load Balancer* (필드 4 client · 5 target · 21 matched_rule_priority · 34 ip_address)
- 콘솔 구축 가이드 **0-1 · 0-2 · 4-3** 절 (실제 만든 값)
> **로드맵 위치**: **0 VPC 입구(이 페이지)** → 1 HTTP 기초 → 2 TLS 종료 지점 → 3 ALB 해부 → 4 오리진 보호(헤더) → 5 헬스체크 → 6 Apache 프록시 → 7 분산·타임아웃 → 8 WEB 관측 → 9 장애 모드 → 10 ASG·AMI.
