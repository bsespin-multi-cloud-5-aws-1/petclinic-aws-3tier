<callout icon="📈" color="blue_bg">
	**이 단계의 목표**: 지금의 고정 EC2 2대가 ASG 로 바뀌면 무엇이 달라지는지, 그때 필요한 부품(시작 템플릿 · 골든 AMI · 종료 훅 · 로그)을 우리 코드(`base.enable_asg`)와 연결한다. 0~9 단계가 전부 이 위에 그대로 올라간다. 하루 분량.
</callout>
# 0. 지금 vs ASG
<table header-row="true" fit-page-width="true">
	<tr>
		<td></td>
		<td>지금 (enable_asg=false)</td>
		<td>ASG (enable_asg=true)</td>
	</tr>
	<tr>
		<td>서버</td>
		<td>`aws_instance` 2대 · 이름 mc-web-a/c</td>
		<td>시작 템플릿 `mc-lt-web` + ASG `mc-asg-web` (min 2 · max 4 · desired 2)</td>
	</tr>
	<tr>
		<td>대상 그룹 등록</td>
		<td>Terraform 이 직접 attach</td>
		<td>ASG 가 `target_group_arns` 로 스스로 등록·해제</td>
	</tr>
	<tr>
		<td>서버가 죽으면</td>
		<td>unhealthy 로 빠지고 **사람이** 교체</td>
		<td>ELB 헬스체크 실패 → ASG 가 종료 후 **자동으로 새 인스턴스**</td>
	</tr>
	<tr>
		<td>트래픽 증가</td>
		<td>그대로</td>
		<td>대상 추적: 평균 CPU 60% 유지하도록 증설(WAS 는 대상당 요청 300 도)</td>
	</tr>
	<tr>
		<td>설정 변경(web.sh)</td>
		<td>인스턴스 교체(`-replace`)</td>
		<td>템플릿 새 버전 → **인스턴스 새로 고침**(Rolling · 50% 유지) — Notion 'AMI & Auto Scaling' 의 v1→v2 절차</td>
	</tr>
	<tr>
		<td>종료 시 로그</td>
		<td>서버에 없음(Agent 실시간)</td>
		<td>WAS 종료 훅 300s: `mc-lifecycle-watch` 가 마지막 로그 S3 sync 후 CONTINUE</td>
	</tr>
</table>
# 1. 부품
<table header-row="true" fit-page-width="true">
	<tr>
		<td>부품</td>
		<td>뜻</td>
		<td>우리 코드 (`modules/base/compute.tf`)</td>
	</tr>
	<tr>
		<td>**시작 템플릿**</td>
		<td>"이런 서버를 만들어라" 명세: AMI · 유형 · SG · 키 · 프로파일 · **user_data**</td>
		<td>`aws_launch_template.web/was` · `$Latest` 참조 · IMDSv2 · gp3 20G</td>
	</tr>
	<tr>
		<td>**ASG**</td>
		<td>템플릿으로 서버를 몇 대 유지할지 + 어느 서브넷·대상 그룹</td>
		<td>`aws_autoscaling_group.web/was` · 서브넷 web-a/c · `health_check_type = ELB` · grace WEB 300s / WAS 900s(스톡 AMI 빌드 시간)</td>
	</tr>
	<tr>
		<td>**스케일링 정책**</td>
		<td>언제 늘리고 줄일지</td>
		<td>대상 추적 `ASGAverageCPUUtilization 60` · WAS 는 `ALBRequestCountPerTarget 300` 추가</td>
	</tr>
	<tr>
		<td>**인스턴스 새로 고침**</td>
		<td>템플릿이 바뀌면 순차 교체</td>
		<td>`instance_refresh` Rolling · `min_healthy_percentage 50`</td>
	</tr>
	<tr>
		<td>**종료 수명 주기 훅**</td>
		<td>종료 직전에 시간을 벌어 뒷정리</td>
		<td>`initial_lifecycle_hook` TERMINATING 300s + was.sh 의 `mc-lifecycle-watch.service`</td>
	</tr>
	<tr>
		<td>**골든 AMI**</td>
		<td>설치가 끝난 이미지. 부팅이 5~8분 → 1~2분</td>
		<td>`base.web_ami_id` / `was_ami_id` — 있으면 was.sh 가 Tomcat 다운로드·clone 을 건너뛰고 WAR 만 재빌드</td>
	</tr>
</table>
# 2. 골든 AMI 를 구울 때 주의 (Notion 'AMI & Auto Scaling' 반영)
- **user_data 는 "인스턴스당 한 번" 실행된다** — 재부팅 때는 안 돌고, 골든 AMI 로 **새 인스턴스**를 띄우면 그 인스턴스의 첫 부팅이라 다시 돈다. 즉 AMI 에 이미 설치된 것을 스크립트가 또 설치하려 하므로 **멱등**해야 한다. 우리 web.sh 는 `dnf install`(이미 있으면 통과) · 파일 덮어쓰기라 안전. was.sh 는 `baked` 플래그로 Tomcat 다운로드·clone 을 건너뛴다.
- **WAR 안에 Proxy 주소·앱 비밀이 박힌다** → 계정·비밀이 바뀌면 AMI 를 다시 굽거나(권장) 부팅 때 재빌드(현재 방식).
- Notion 페이지의 옛 스크립트(`INTERNAL_ALB=… internal-alb-internal-test-…`)는 kdt5 콘솔 구축본 값 — mc-deploy 에선 `internal-mc-alb-internal-692352220…`. 값을 코드 한 곳(Terraform 변수)에서만 넣는 이유.
# 3. DB 초기화 경합 (Notion 'was' 페이지의 우려)
ASG 로 WAS 2대가 **동시에** 뜨면 둘 다 `schema.sql` 을 실행한다. 우리 앱은 Spring Boot 가 아니라 XML `jdbc:initialize-database` 이고 MySQL 스크립트가 `CREATE TABLE IF NOT EXISTS` · `INSERT IGNORE` 라 **현재도 멱등** — 9/16 롤링 교체·동시 부팅에서 실측 문제 없음. 더 엄격히 하려면 `base.db_init_mode = "userdata"`: was.sh 가 `GET_LOCK` 으로 직렬화해 1회만 실행하고 Spring 초기화는 `-Djdbc.initLocation` 으로 끈다(Java 0줄).
# 4. 켜는 순서 (실제 할 때)
1. (선택) 콘솔에서 mc-web-a · mc-was-a 로 이미지 생성 → `base.web_ami_id` · `was_ami_id`
2. `base.enable_asg = true` → plan 에서 **고정 EC2 4대 destroy + LT·ASG create** 확인 → apply. 이 전환은 **다운타임**이 생기므로(고정 EC2 가 먼저 사라짐) 점검 시간에. 무중단이 필요하면 ASG 를 먼저 만들고 대상 그룹에 둘 다 붙인 뒤 고정 EC2 를 빼는 2단계 apply(코드 개선 여지)
3. 확인: 대상 그룹에 ASG 인스턴스가 healthy · `aws autoscaling describe-auto-scaling-groups`
4. 템플릿을 고칠 땐 apply → 새 버전 → `start-instance-refresh` 또는 콘솔 "인스턴스 새로 고침 시작"
# 5. 눈으로 확인 (지금 · 코드만)

```bash
# 1) 지금은 ASG 가 없다
aws autoscaling describe-auto-scaling-groups --profile mc-deploy --region ap-northeast-2 --query 'AutoScalingGroups[].AutoScalingGroupName' --output text   # (mc- 없음)
# 2) 켰을 때 무엇이 생기는지 코드로 읽기
sed -n '/# ---------- ASG (enable_asg=true)/,$p' infra/terraform-kdt5/modules/base/compute.tf | grep -E 'resource |name |min_size|max_size|health_check_grace|target_value|heartbeat_timeout'
# 3) 켜면 plan 이 어떻게 되는지 (apply 안 함)
cd infra/terraform-kdt5 && terraform plan -no-color -var='base={app_repo_branch="test",tomcat_version="9.0.121",web_index_branch="test",enable_asg=true}' 2>/dev/null | grep -E '^  # |^Plan:'
```

# 6. 진입 기준 — 여기까지 오면 WEB 계층 한 바퀴
<details>
<summary>Q1. ASG 의 헬스체크 유형을 EC2 가 아니라 ELB 로 두는 이유는?</summary>
	EC2 상태 검사는 '인스턴스가 켜져 있나' 만 본다. Apache 가 죽어도 EC2 는 정상. ELB 유형이면 대상 그룹 헬스체크(5단계) 실패를 곧 교체 신호로 쓴다.
</details>
<details>
<summary>Q2. grace period 를 WAS 900s 로 둔 이유는?</summary>
	스톡 AMI 에서 Tomcat 다운로드 + Maven 빌드 + Proxy 로그인 대기가 5~8분. 그 전에 ELB 체크가 실패하면 ASG 가 '고장' 으로 보고 끝없이 교체한다. 골든 AMI 면 300s 로 줄일 수 있다.
</details>
<details>
<summary>Q3. 로그는 ASG 에서 어떻게 지키나?</summary>
	서버에 두지 않는다: Agent 가 실시간으로 CloudWatch Logs 로, 스트림 = 인스턴스 ID, 종료 훅 300s 동안 마지막 줄을 S3 로 sync. 인스턴스가 사라져도 로그는 남는다(🗂️ 총정리).
</details>
# 7. 읽을 자료
- Notion — 🤓 AMI & Auto Scaling (팀 콘솔 절차 · v1→v2 교체)
- AWS 문서 — *Auto Scaling instance refresh* · *Lifecycle hooks* · *Target tracking scaling policies*
- 저장소 `infra/terraform-kdt5/README.md` 'ASG · AMI' 절 · `modules/base/compute.tf`
<callout icon="🗺️" color="gray_bg">
	**로드맵 위치**: 0 VPC 입구 → 1 HTTP 기초 → 2 TLS 종료 지점 → 3 ALB 해부 → 4 오리진 보호(헤더) → 5 헬스체크 → 6 Apache 프록시 → 7 분산·타임아웃 → 8 WEB 관측 → 9 장애 모드 → **10 ASG·AMI(이 페이지)**.
</callout>