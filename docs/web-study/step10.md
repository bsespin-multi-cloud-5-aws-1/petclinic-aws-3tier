<callout icon="📈" color="blue_bg">
	**이 단계의 목표**: 지금의 고정 EC2 2대가 ASG 로 바뀌면 무엇이 달라지는지, 그때 필요한 부품 다섯 개(시작 템플릿 · ASG+정책 · 새로 고침+종료 훅 · 골든 AMI · DB 초기화)를 우리 코드(`base.enable_asg`)와 연결한다. 0~9 단계가 전부 이 위에 그대로 올라간다. 하루 분량. 값은 2026-09-17 코드(`modules/base/compute.tf`)와 mc-deploy 실측 — ASG 는 **아직 꺼져 있다**(코드만).
</callout>
# 0. 그림 한 장

```text
지금 (enable_asg=false)                          ASG (enable_asg=true · 코드만 · 미적용)
aws_instance web-a · web-c  ──attach──▶ mc-tg-web     ② 시작 템플릿 mc-lt-web ($Latest) ──▶ ③ ASG mc-asg-web (min2 · max4 · ELB 헬스체크 · grace 300s) ──자동 등록──▶ mc-tg-web
aws_instance was-a · was-c  ──attach──▶ mc-tg-was     ② 시작 템플릿 mc-lt-was ($Latest) ──▶ ③ ASG mc-asg-was (min2 · max4 · grace 900s · 정책 CPU 60 · 요청/대상 300) ──▶ mc-tg-was
   죽으면 사람이 교체 · 설정 바꾸면 -replace                ④ 죽으면 ASG 가 교체 · 템플릿 바꾸면 인스턴스 새로 고침(Rolling 50%) · 종료 훅 300s(로그 sync)
                                                       ⑤ 골든 AMI(web_ami_id/was_ami_id) 면 부팅 5~8분 → 1~2분 · user_data 는 인스턴스당 1회 · DB 초기화 경합은 멱등 SQL + (선택) GET_LOCK
```

① 한 줄 요약: **"서버가 몇 대인지" 를 사람이 아니라 ASG 가 유지**한다. 그러려면 서버가 "만들면 저절로 준비되는 것"(템플릿 + user_data/AMI)이어야 하고, 사라져도 잃는 게 없어야 한다(로그 · 세션 · 스키마).
# 1. 딱 필요한 다섯 가지 — 한 표
<table header-row="true" fit-page-width="true">
	<tr>
		<td>#</td>
		<td>항목</td>
		<td>무슨 일이 일어나나</td>
		<td>우리 값 (코드 · 실측)</td>
	</tr>
	<tr>
		<td>①</td>
		<td>지금 vs ASG — 무엇이 바뀌나</td>
		<td>서버 정의 · 대상 그룹 등록 · 장애 복구 · 증설 · 설정 변경 · 종료 시 로그 — 여섯 가지가 "사람" 에서 "ASG" 로</td>
		<td>지금 `aws_instance` 2+2 · attachment 직접 · 교체는 `-replace`. 켜면 LT+ASG · 자동 등록 · 자동 교체 · 대상 추적 · 새로 고침 · 종료 훅</td>
	</tr>
	<tr>
		<td>②</td>
		<td>시작 템플릿</td>
		<td>"이런 서버를 만들어라" 명세 — AMI · 유형 · SG · 키 · 프로파일 · **user_data** · 디스크 · IMDSv2. 버전이 있고 ASG 는 `$Latest` 를 본다</td>
		<td>`mc-lt-web` / `mc-lt-was` · `image_id = web_ami_id 또는 AL2023 최신` · gp3 20G 암호화 · `http_tokens required` · user_data = 지금과 같은 web.sh/was.sh</td>
	</tr>
	<tr>
		<td>③</td>
		<td>ASG + 스케일링 정책</td>
		<td>몇 대를 어느 서브넷에 유지할지 · 누가 정상인지(ELB 헬스체크) · 언제 늘리고 줄일지(대상 추적)</td>
		<td>`mc-asg-web` min 2 · max 4 · desired 2 · 서브넷 web-a/c · `health_check_type ELB` · grace **300s** · 정책 CPU 60% / `mc-asg-was` grace **900s**(스톡 AMI) · CPU 60% + `ALBRequestCountPerTarget 300`</td>
	</tr>
	<tr>
		<td>④</td>
		<td>인스턴스 새로 고침 · 종료 훅</td>
		<td>템플릿이 바뀌면 순차 교체(Rolling · 절반 유지). 종료 직전 시간을 벌어 뒷정리(로그 sync)</td>
		<td>`instance_refresh Rolling · min_healthy_percentage 50` · WAS `EC2_INSTANCE_TERMINATING` 훅 `heartbeat 300s · CONTINUE` + was.sh 의 `mc-lifecycle-watch.service`</td>
	</tr>
	<tr>
		<td>⑤</td>
		<td>골든 AMI · user_data 멱등 · DB 초기화</td>
		<td>설치가 끝난 이미지로 부팅 시간을 줄인다. user_data 는 **인스턴스당 한 번** 돌므로 두 번 돌아도 안전해야 하고, WAS 2대가 동시에 뜨면 스키마 초기화가 겹친다</td>
		<td>`base.web_ami_id` · `was_ami_id`(비면 스톡 + 전부 설치 · 있으면 `baked` 로 Tomcat 다운로드·clone 생략) · `db_init_mode = app`(현재 · `IF NOT EXISTS`/`INSERT IGNORE` 멱등) 또는 `userdata`(GET_LOCK 직렬화)</td>
	</tr>
</table>
# 2. 자세히 — 항목마다 "무슨 일 · 우리 값 · 없으면 · 눈으로 확인"
## 2-1. ① 지금 vs ASG — 여섯 가지가 바뀐다
**무슨 일이 일어나나**
1. **서버 정의**: 지금은 `aws_instance.web[0..1]` · `was[0..1]` 이 Terraform state 에 **개별 리소스**로 있다(ID · IP · AZ 고정). ASG 에선 인스턴스가 state 에 없고 **"템플릿 + 대수"** 만 있다. 인스턴스는 ASG 가 만들고 없앤다.
2. **대상 그룹 등록**: 지금은 `aws_lb_target_group_attachment` 로 Terraform 이 직접 붙인다. ASG 는 `target_group_arns` 로 스스로 등록·해제(드레이닝 포함).
3. **장애 복구**: 지금은 unhealthy 로 빠진 채 **사람이** 교체(`terraform apply -replace`). ASG 는 ELB 헬스체크 실패 → 인스턴스 종료 → 새 인스턴스(5단계 30초 + 부팅 시간).
4. **증설**: 지금은 없음. ASG 는 대상 추적 정책이 CPU 60% 를 유지하도록 2 → 4대까지 늘리고, 부하가 빠지면 줄인다(WAS 는 대상당 요청 300 도).
5. **설정 변경(web.sh)**: 지금은 `user_data_replace_on_change` 로 인스턴스 교체(-replace 한 대씩 · 9/16 의 `-target` 실수 교훈). ASG 는 템플릿 새 버전 → **인스턴스 새로 고침**이 절반씩 교체.
6. **종료 시 로그**: 지금은 Agent 가 실시간 전송하니 대부분 안전. ASG 는 축소 때 인스턴스가 갑자기 사라지므로 **종료 훅** 300s 동안 마지막 로그를 S3 로 sync(WAS).

**우리 값**
<table header-row="true" fit-page-width="true">
	<tr>
		<td></td>
		<td>지금 (enable_asg=false · 실측)</td>
		<td>ASG (enable_asg=true · 코드)</td>
	</tr>
	<tr>
		<td>서버</td>
		<td>`aws_instance` 4대 · web-a `i-01a195…` · web-c `i-01d173…` · was-a `i-0ff9a0…` · was-c `i-0d3085…`</td>
		<td>`aws_launch_template` 2 + `aws_autoscaling_group` 2 · 인스턴스는 state 밖</td>
	</tr>
	<tr>
		<td>대상 그룹 등록</td>
		<td>`aws_lb_target_group_attachment` (count = ec2_count)</td>
		<td>ASG `target_group_arns`</td>
	</tr>
	<tr>
		<td>서버가 죽으면</td>
		<td>unhealthy → 사람이 `-replace`</td>
		<td>ELB 체크 실패 → 자동 교체 (grace 뒤)</td>
	</tr>
	<tr>
		<td>트래픽 증가</td>
		<td>그대로 (2대)</td>
		<td>대상 추적 CPU 60% · WAS 요청/대상 300 → 최대 4대</td>
	</tr>
	<tr>
		<td>설정 변경</td>
		<td>`-replace` 한 대씩(다운타임 0 · 6분/대)</td>
		<td>템플릿 `$Latest` → `start-instance-refresh` Rolling 50%</td>
	</tr>
	<tr>
		<td>종료 시 로그</td>
		<td>Agent 실시간 (`/petclinic/*`)</td>
		<td>+ WAS 종료 훅 300s · `mc-lifecycle-watch` → S3 `was/` sync → CONTINUE</td>
	</tr>
	<tr>
		<td>Terraform 스위치</td>
		<td>`base.enable_asg = false` (tfvars)</td>
		<td>`local.ec2_count = 0` · `local.asg_count = 1`</td>
	</tr>
</table>
**없으면 · 오해**
- "ASG 를 켜면 무중단으로 바뀐다" — 아니다. 지금 코드는 고정 EC2 4대 **destroy** + LT/ASG **create** 를 한 apply 에서 하므로 **다운타임**이 있다(2-6). 무중단 전환은 2단계 apply 가 필요(코드 개선 여지).
- "ASG 가 있으면 알람이 필요 없다" — 교체는 자동이지만 **원인**은 안 알려 준다. 알람·로그(8단계)는 그대로 필요.
- ASG 인스턴스는 이름 태그가 `mc-web`(a/c 구분 없음) — 로그 스트림은 인스턴스 ID 라 문제 없지만 콘솔에서 헷갈린다.

**눈으로 확인**

```bash
# 1) 지금은 ASG 가 없다 (mc- 이름 없음)
aws autoscaling describe-auto-scaling-groups --profile mc-deploy --region ap-northeast-2 --query 'AutoScalingGroups[].AutoScalingGroupName' --output text
# 2) 지금은 고정 EC2 4대 + attachment
aws ec2 describe-instances --filters Name=tag:Name,Values=mc-web-a,mc-web-c,mc-was-a,mc-was-c Name=instance-state-name,Values=running --profile mc-deploy --region ap-northeast-2 --query 'Reservations[].Instances[].[Tags[?Key==`Name`].Value|[0],InstanceId,PrivateIpAddress]' --output table
# 3) 스위치와 카운트 — 코드 근거
grep -nE "enable_asg|ec2_count|asg_count" infra/terraform-kdt5/modules/base/locals.tf infra/terraform-kdt5/variables.tf | head
# 4) 켜면 plan 이 어떻게 되는지 — tfvars 의 base 에 enable_asg = true 한 줄만 넣고 plan (apply 는 안 함 · 읽기 전용).
#    -var 로 base 를 통째로 넘기면 tfvars 의 다른 base 값(bastion_allowed_cidrs 등)이 지워져 엉뚱한 변경이 섞여 보인다.
#    cd infra/terraform-kdt5 && terraform plan -no-color | grep -E '^  # |^Plan:' 
```

기대: 1) `mc-` 로 시작하는 것 없음(`saa-asg` 는 다른 프로젝트) 2) 4줄 3) `ec2_count = var.enable_asg ? 0 : 2` · `asg_count = var.enable_asg ? 1 : 0` 4) `# aws_instance.web[0] will be destroyed` ×4 · `aws_launch_template … will be created` ×2 · `aws_autoscaling_group … created` ×2 · 정책 3 · `Plan: N to add, M to change, 8 to destroy`(EC2 4 + attachment 4)
## 2-2. ② 시작 템플릿 — "이런 서버를 만들어라"
**무슨 일이 일어나나**
1. 시작 템플릿(Launch Template) = 인스턴스 생성 파라미터의 묶음: **AMI** · 인스턴스 유형 · SG · 키 페어 · IAM 인스턴스 프로파일 · **user_data**(base64) · 디스크(EBS) · 메타데이터 옵션 · 태그. `aws_instance` 의 인자와 거의 같다 — 지금 고정 EC2 정의를 그대로 옮긴 것.
2. **버전**이 있다. 템플릿을 고치면 새 버전이 생기고(`update_default_version = true`), ASG 는 `$Latest` 를 참조하므로 다음에 만드는 인스턴스부터 새 버전. 기존 인스턴스는 안 바뀐다 → 새로 고침(④).
3. `image_id = local.web_ami`: `base.web_ami_id` 가 있으면 그것(골든), 비면 AL2023 최신(SSM 파라미터로 조회). 스톡이면 부팅 때 web.sh 가 전부 설치(≈2분) · was.sh 가 Tomcat 다운로드 + Maven 빌드(≈6분).
4. `metadata_options http_tokens = required` = **IMDSv2 강제**(SSRF 로 자격 증명 탈취 방지) · `hop_limit 1`. 디스크 gp3 20G 암호화. 지금 고정 EC2 와 동일한 SG(`mc-sg-web` / `mc-sg-was`) · 프로파일(`mc-ec2-profile` · CloudWatch Agent · S3 로그 · Secrets 읽기).
5. 키 이름 `mc-ssh`(Bastion 과 같은 키) — ASG 인스턴스에도 Bastion 경유 SSH 가 된다.

**우리 값 (compute.tf)**
<table header-row="true" fit-page-width="true">
	<tr>
		<td>항목</td>
		<td>mc-lt-web</td>
		<td>mc-lt-was</td>
	</tr>
	<tr>
		<td>AMI</td>
		<td>`web_ami_id` 또는 AL2023 최신</td>
		<td>`was_ami_id` 또는 AL2023 최신</td>
	</tr>
	<tr>
		<td>유형 · SG · 프로파일 · 키</td>
		<td>`web_instance_type` · `mc-sg-web` · `mc-ec2-profile` · `mc-ssh`</td>
		<td>`was_instance_type` · `mc-sg-was` · 동일</td>
	</tr>
	<tr>
		<td>user_data</td>
		<td>`local.web_user_data` (지금 고정 EC2 와 같은 web.sh 렌더링)</td>
		<td>`local.was_user_data` (was.sh · `baked` · `enable_asg` · `db_init_mode` 플래그 반영)</td>
	</tr>
	<tr>
		<td>디스크 · 메타데이터</td>
		<td>gp3 20G 암호화 · IMDSv2 required · hop 1</td>
		<td>동일</td>
	</tr>
	<tr>
		<td>버전 참조</td>
		<td>ASG 가 `$Latest` · `update_default_version = true`</td>
		<td>동일</td>
	</tr>
	<tr>
		<td>태그</td>
		<td>인스턴스·볼륨 `Name = mc-web`</td>
		<td>`Name = mc-was`</td>
	</tr>
</table>
**없으면 · 오해**
- 템플릿 없이 ASG 를 만들 수 없다(옛 "시작 구성" 은 지원 종료). 템플릿이 곧 "서버의 정의".
- `$Latest` 대신 고정 버전 번호를 쓰면 apply 해도 ASG 가 옛 버전을 계속 쓴다 — 콘솔에서 바꾼 템플릿이 반영 안 될 때 확인할 것.
- user_data 에 비밀을 넣지 않는다(IMDS 로 누구나 읽음) — 우리는 Secrets Manager 에서 부팅 때 읽는다(was.sh).

**눈으로 확인**

```bash
# 1) 템플릿 정의 — 코드 (AMI · IMDSv2 · 디스크 · user_data)
sed -n '/resource "aws_launch_template" "web"/,/^}/p' infra/terraform-kdt5/modules/base/compute.tf | grep -E "name |image_id|instance_type|key_name|http_tokens|volume_type|volume_size|user_data|version"
# 2) 지금 고정 EC2 도 같은 메타데이터 옵션인지 (IMDSv2)
aws ec2 describe-instances --instance-ids i-01a195cff8acb28d8 --profile mc-deploy --region ap-northeast-2 --query 'Reservations[0].Instances[0].[MetadataOptions.HttpTokens,IamInstanceProfile.Arn,KeyName,SecurityGroups[0].GroupName]' --output text
# 3) 켜졌을 때 생길 템플릿 이름 (지금은 없음)
aws ec2 describe-launch-templates --profile mc-deploy --region ap-northeast-2 --query 'LaunchTemplates[?starts_with(LaunchTemplateName, `mc-`)].[LaunchTemplateName,LatestVersionNumber]' --output text
```

기대: 1) `name = "$｛local.p｝-lt-web"` · `image_id = local.web_ami` · `http_tokens = "required"` · `gp3 · 20` · `user_data = base64encode(local.web_user_data)` 2) `required arn:…instance-profile/mc-ec2-profile mc-ssh mc-sg-web` 3) 빈 출력
## 2-3. ③ ASG 와 스케일링 정책 — 몇 대를 · 어디에 · 언제
**무슨 일이 일어나나**
1. ASG = **min · max · desired** + 서브넷(`vpc_zone_identifier`) + 템플릿 + 헬스체크 방식 + 대상 그룹. ASG 는 desired 대수를 **항상** 맞춘다: 부족하면 만들고, 넘치면 없앤다. AZ 균형도 맞춘다(web-a/web-c 서브넷에 번갈아).
2. **`health_check_type = ELB`**: EC2 상태 검사(켜져 있나)가 아니라 **대상 그룹 헬스체크**(5단계) 실패를 교체 신호로 쓴다. Apache 가 죽으면 EC2 는 정상이어도 unhealthy → 교체. 
3. **`health_check_grace_period`**: 새 인스턴스가 뜨고 나서 이 시간 동안은 헬스체크 실패를 무시한다. WEB 300s(설치 2분) · WAS 900s(스톡 AMI 빌드 5~8분 · 골든 AMI 면 300s). 짧으면 부팅 중인 인스턴스를 "고장" 으로 보고 **끝없이 교체**한다.
4. **대상 추적 정책**: "평균 CPU 60% 를 유지하도록 대수를 조절해라". CloudWatch 알람 두 개(높음/낮음)를 AWS 가 자동으로 만든다. WAS 는 `ALBRequestCountPerTarget 300`(대상당 분당 요청) 정책이 하나 더 — 둘 중 더 많은 대수를 요구하는 쪽이 이긴다. 축소는 완만하게(기본 쿨다운).
5. `lifecycle ignore_changes = [desired_capacity]`: 정책이 바꾼 대수를 다음 `apply` 가 2 로 되돌리지 않게.

**우리 값 (compute.tf · variables.tf 기본값)**
<table header-row="true" fit-page-width="true">
	<tr>
		<td>항목</td>
		<td>mc-asg-web</td>
		<td>mc-asg-was</td>
	</tr>
	<tr>
		<td>min / max / desired</td>
		<td>2 / 4 / 2</td>
		<td>2 / 4 / 2</td>
	</tr>
	<tr>
		<td>서브넷</td>
		<td>mc-web-a · mc-web-c</td>
		<td>mc-was-a · mc-was-c</td>
	</tr>
	<tr>
		<td>대상 그룹</td>
		<td>`mc-tg-web`</td>
		<td>`mc-tg-was`</td>
	</tr>
	<tr>
		<td>헬스체크 · 유예</td>
		<td>ELB · **300s**</td>
		<td>ELB · **900s**(스톡) / 300s(골든 AMI)</td>
	</tr>
	<tr>
		<td>정책</td>
		<td>`mc-web-cpu-target` — `ASGAverageCPUUtilization` 60</td>
		<td>`ASGAverageCPUUtilization` 60 + `ALBRequestCountPerTarget` 300</td>
	</tr>
	<tr>
		<td>템플릿 참조</td>
		<td>`mc-lt-web` `$Latest`</td>
		<td>`mc-lt-was` `$Latest`</td>
	</tr>
	<tr>
		<td>desired 보호</td>
		<td>`ignore_changes = [desired_capacity]`</td>
		<td>동일</td>
	</tr>
</table>
**없으면 · 오해**
- 유형을 EC2 로 두면 Apache 만 죽은 서버를 "정상" 으로 보고 안 바꾼다 — 5단계의 얕은 체크가 여기서 교체 신호가 된다는 점이 ELB 유형의 가치.
- grace 를 60s 로 두면 WAS 는 빌드 중에 unhealthy 판정 → 종료 → 새로 → 또 종료 … 무한 루프. 900s 인 이유.
- max 4 는 비용 상한. CPU 60% 를 넘는데 4대가 이미 차 있으면 더 못 늘린다 — 그땐 인스턴스 유형을 올리거나 max 를 올린다.

**눈으로 확인**

```bash
# 1) ASG 정의 — 코드 (대수 · 헬스체크 · grace · 정책)
sed -n '/# ---------- ASG (enable_asg=true)/,$p' infra/terraform-kdt5/modules/base/compute.tf | grep -E 'resource |name |min_size|max_size|desired|health_check_type|health_check_grace|predefined_metric_type|target_value|heartbeat_timeout|min_healthy_percentage'
# 2) 기본값 — variables.tf
grep -nE "web_asg|was_asg" infra/terraform-kdt5/variables.tf | head -2
# 3) 지금 CPU 가 얼마인지 — 정책 임계 60% 와 비교 (지난 1시간 평균 · 고정 EC2)
for i in i-01a195cff8acb28d8 i-0ff9a07cd26d34ba0; do printf "%s " $i; aws cloudwatch get-metric-statistics --namespace AWS/EC2 --metric-name CPUUtilization --dimensions Name=InstanceId,Value=$i --start-time $(date -u -d '-1 hour' +%FT%TZ) --end-time $(date -u +%FT%TZ) --period 3600 --statistics Average --profile mc-deploy --region ap-northeast-2 --query 'Datapoints[0].Average' --output text; done
```

기대: 1) `min_size = var.web_asg.min` · `health_check_type = "ELB"` · `grace 300` / `900` · `ASGAverageCPUUtilization` · `ALBRequestCountPerTarget` · `target_value` · `heartbeat_timeout = 300` · `min_healthy_percentage = 50` 2) `｛ min = 2, max = 4, desired = 2, cpu_target = 60 ｝` · `… req_per_target = 300` 3) 한 자리 % (유휴)
## 2-4. ④ 인스턴스 새로 고침과 종료 훅 — 바꿀 때와 없앨 때
**무슨 일이 일어나나**
1. **인스턴스 새로 고침(instance refresh)**: 템플릿이 새 버전이 되어도 기존 인스턴스는 그대로다. 새로 고침을 시작하면 ASG 가 **Rolling** 으로 옛 인스턴스를 하나씩 종료하고 새 템플릿으로 만든다. `min_healthy_percentage 50` = 진행 중에도 **절반은 항상 정상** 유지(2대면 1대씩). 각 인스턴스는 대상 그룹 드레이닝(30s · 5단계) → 종료 → 새 인스턴스 healthy(grace 뒤) → 다음.
2. 시작은 `aws autoscaling start-instance-refresh` 또는 콘솔 "인스턴스 새로 고침 시작". Terraform apply 가 템플릿을 바꿔도 **자동으로 시작되진 않는다**(트리거 설정을 안 넣었으므로) — 의도적: 점검 시간에 사람이 시작.
3. **종료 수명 주기 훅**: ASG 가 인스턴스를 없애기 직전 `Terminating:Wait` 상태로 **최대 heartbeat_timeout(300s)** 멈춰 준다. 그 사이 인스턴스 안의 `mc-lifecycle-watch.service`(was.sh 가 설치)가 IMDS 의 `target-lifecycle-state` 를 폴링하다 `Terminated` 를 보면 Tomcat 로그를 S3 `was/` 로 sync 하고 `complete-lifecycle-action CONTINUE` 를 보낸다. 시간이 다 되면 `default_result CONTINUE` 로 어차피 진행.
4. WEB 엔 훅이 없다 — Apache 로그는 Agent 가 실시간으로 보내고 마지막 몇 초 손실은 감수. WAS 의 catalina 로그는 예외 스택이 중요해 훅을 둔다.
5. 이 두 기능 덕에 "web.sh 한 줄 수정" 이 `-replace` 대신 **템플릿 apply + 새로 고침 클릭**이 된다(9/16 처럼 4대가 동시에 죽는 실수가 구조적으로 불가능).

**우리 값 (compute.tf · was.sh)**
<table header-row="true" fit-page-width="true">
	<tr>
		<td>항목</td>
		<td>값</td>
	</tr>
	<tr>
		<td>새로 고침</td>
		<td>`instance_refresh ｛ strategy = "Rolling" preferences ｛ min_healthy_percentage = 50 ｝ ｝` (web · was)</td>
	</tr>
	<tr>
		<td>시작 방법</td>
		<td>`aws autoscaling start-instance-refresh --auto-scaling-group-name mc-asg-web` · 자동 트리거 없음</td>
	</tr>
	<tr>
		<td>종료 훅 (WAS)</td>
		<td>`initial_lifecycle_hook` `autoscaling:EC2_INSTANCE_TERMINATING` · `heartbeat_timeout 300` · `default_result CONTINUE`</td>
	</tr>
	<tr>
		<td>인스턴스 쪽</td>
		<td>was.sh `%｛ if enable_asg ｝` → `/usr/local/bin/mc-lifecycle-watch.sh` + systemd 서비스 · IMDS `autoscaling/target-lifecycle-state` 폴링 → `aws s3 sync /opt/tomcat/logs s3://mc-logs/was/…` → `complete-lifecycle-action`</td>
	</tr>
	<tr>
		<td>IAM</td>
		<td>ec2 역할에 `autoscaling:CompleteLifecycleAction`(mc-asg-*) · `s3:PutObject` (iam.tf)</td>
	</tr>
	<tr>
		<td>드레이닝과의 순서</td>
		<td>대상 그룹 등록 취소(30s) → Terminating:Wait(훅 ≤300s) → 종료</td>
	</tr>
</table>
**없으면 · 오해**
- 새로 고침 없이 템플릿만 바꾸면 **아무 일도 안 일어난다** — "apply 했는데 서버가 옛 설정" 의 원인.
- `min_healthy_percentage 0` 이면 전부 동시에 교체(다운타임). 50 이 2대 구성의 최소 안전값. 100 으로 두면 새것을 먼저 띄우고 옛것을 빼서(surge) 더 안전하지만 잠깐 3~4대 비용.
- 훅을 두고 인스턴스 쪽 서비스를 안 넣으면 매 종료마다 300s 를 그냥 기다린다(축소가 5분 느려짐). 둘이 짝.

**눈으로 확인**

```bash
# 1) 코드 — 새로 고침 · 훅
grep -nE "instance_refresh|strategy|min_healthy_percentage|lifecycle_transition|heartbeat_timeout|default_result" infra/terraform-kdt5/modules/base/compute.tf
# 2) 인스턴스 쪽 — was.sh 의 lifecycle watch 블록
grep -nE "mc-lifecycle-watch|target-lifecycle-state|complete-lifecycle-action|s3 sync" infra/terraform-kdt5/modules/base/user_data/was.sh
# 3) IAM — 훅 완료 권한
grep -nE "CompleteLifecycleAction|mc-asg" infra/terraform-kdt5/iam.tf
# 4) (켜진 뒤) 새로 고침 상태 보기
#   aws autoscaling describe-instance-refreshes --auto-scaling-group-name mc-asg-web --profile mc-deploy --region ap-northeast-2 --query 'InstanceRefreshes[0].[Status,PercentageComplete,InstancesToUpdate]'
```

기대: 1) `strategy = "Rolling"` · `min_healthy_percentage = 50` ×2 · `EC2_INSTANCE_TERMINATING` · `300` · `CONTINUE` 2) 서비스 설치 · 폴링 · sync · complete 줄 3) `autoscaling:CompleteLifecycleAction` + `mc-asg-*` 4) (켜진 뒤)
## 2-5. ⑤ 골든 AMI · user_data 멱등 · DB 초기화 — 서버가 "저절로 준비" 되려면
**무슨 일이 일어나나**
1. **골든 AMI**: 설치(httpd · Tomcat · 빌드 도구)가 끝난 상태를 이미지로 구워 두면 새 인스턴스가 **1~2분**에 뜬다(스톡은 WAS 5~8분). ASG 의 자동 교체·증설 속도가 여기서 결정된다. 콘솔에서 "이미지 생성" → `base.web_ami_id` / `was_ami_id` 에 넣으면 템플릿이 그 AMI 를 쓴다.
2. **user_data 는 인스턴스당 한 번**(첫 부팅) 돈다. 재부팅 땐 안 돌지만, 골든 AMI 로 **새 인스턴스**를 띄우면 그 인스턴스의 첫 부팅이라 **다시 돈다**. 즉 AMI 에 이미 설치된 것을 스크립트가 또 만나므로 **멱등**이어야 한다. web.sh 는 `dnf install`(이미 있으면 통과) · 파일 덮어쓰기라 안전. was.sh 는 `baked` 플래그(AMI 가 있으면 true)로 Tomcat 다운로드·git clone 을 건너뛰고 **WAR 만 다시 빌드**한다.
3. **WAR 안에 Proxy 주소·앱 비밀이 들어간다** — 그래서 AMI 에 WAR 를 굽지 않고 부팅 때 재빌드(현재). 계정·비밀이 바뀌면 AMI 를 다시 굽거나 재빌드 경로가 필요.
4. **DB 초기화 경합**: ASG 로 WAS 2대가 **동시에** 뜨면 둘 다 `schema.sql` 을 실행한다. 우리 앱은 Spring XML `jdbc:initialize-database` 이고 MySQL 스크립트가 `CREATE TABLE IF NOT EXISTS` · `INSERT IGNORE` 라 **현재도 멱등** — 9/16 동시 부팅 실측 문제 없음(`db_init_mode = app`).
5. 더 엄격히: `db_init_mode = userdata` 면 was.sh 가 MySQL `GET_LOCK` 으로 직렬화해 **한 대만** 스키마를 실행하고, Spring 초기화는 `-Djdbc.initLocation` 으로 빈 스크립트를 가리켜 끈다(Java 0줄). Notion 'was' 페이지의 우려에 대한 답.

**우리 값**
<table header-row="true" fit-page-width="true">
	<tr>
		<td>항목</td>
		<td>값 (코드)</td>
	</tr>
	<tr>
		<td>AMI 변수</td>
		<td>`base.web_ami_id = ""` · `was_ami_id = ""` (비어 있음 → AL2023 최신 + 부팅 설치) · 넣으면 `local.web_ami/was_ami` 가 그 값</td>
	</tr>
	<tr>
		<td>baked 플래그</td>
		<td>`was_ami_id != ""` → was.sh `%｛ if baked ｝` 가 Tomcat 다운로드 · git clone 생략 · WAR 재빌드만 · grace 900 → 300</td>
	</tr>
	<tr>
		<td>user_data 멱등 근거</td>
		<td>web.sh: `dnf install -y`(멱등) · `cat › petclinic.conf`(덮어쓰기) · `rm -rf static && cp`(재생성) / was.sh: `baked` 분기 · `setenv.sh` 덮어쓰기</td>
	</tr>
	<tr>
		<td>DB 초기화</td>
		<td>`db_init_mode = "app"`(현재) — `schema.sql` `CREATE TABLE IF NOT EXISTS` · `data.sql` `INSERT IGNORE` / `"userdata"` — `GET_LOCK('mc_db_init', 300)` 직렬화 + `-Djdbc.initLocation=…/noop.sql`</td>
	</tr>
	<tr>
		<td>비밀 위치</td>
		<td>Secrets Manager(앱 DB 자격) · Parameter Store(`/petclinic/cwagent/*` Agent 설정) — AMI · user_data 에 없음</td>
	</tr>
	<tr>
		<td>Notion 옛 스크립트와의 차이</td>
		<td>'AMI & Auto Scaling' 의 `INTERNAL_ALB=… internal-alb-internal-test-…` 는 kdt5 콘솔 구축본. mc-deploy 는 `internal-mc-alb-internal-692352220…` — 값을 Terraform 변수 한 곳에서만 넣는 이유</td>
	</tr>
</table>
**없으면 · 오해**
- "AMI 에 다 구워 두면 user_data 는 필요 없다" — 인스턴스별 값(Internal ALB 이름 · 비밀 · 브랜치)은 부팅 때 넣어야 한다. AMI = 설치, user_data = 설정.
- "user_data 는 재부팅마다 돈다" — 아니다. 인스턴스당 한 번. 재부팅으로 설정을 다시 적용하려면 `cloud-init clean` 이나 systemd 서비스로.
- "동시에 뜨면 스키마가 깨진다" — 멱등 SQL 이라 현재 안전. 데이터 마이그레이션(ALTER)이 생기면 그때 `userdata` 모드 또는 Flyway 류.

**눈으로 확인**

```bash
# 1) AMI 변수 · baked 분기 — 코드
grep -nE "web_ami_id|was_ami_id|baked" infra/terraform-kdt5/modules/base/locals.tf infra/terraform-kdt5/modules/base/compute.tf | head
grep -n "baked" infra/terraform-kdt5/modules/base/user_data/was.sh | head -5
# 2) DB 초기화 모드 — 코드
grep -nE "db_init_mode|GET_LOCK|initLocation" infra/terraform-kdt5/modules/base/user_data/was.sh | head
# 3) 스키마 스크립트가 멱등인지 — 저장소
grep -cE "IF NOT EXISTS" src/main/resources/db/mysql/schema.sql; grep -cE "INSERT IGNORE" src/main/resources/db/mysql/data.sql
# 4) 지금 인스턴스가 어떤 AMI 인지 (스톡 AL2023)
aws ec2 describe-instances --instance-ids i-01a195cff8acb28d8 i-0ff9a07cd26d34ba0 --profile mc-deploy --region ap-northeast-2 --query 'Reservations[].Instances[].[Tags[?Key==`Name`].Value|[0],ImageId]' --output text
```

기대: 1) `web_ami = var.web_ami_id != "" ? var.web_ami_id : data.aws_ssm_parameter.al2023.value` · was.sh 에 `%｛ if baked ~｝` 2) `%｛ if db_init_mode == "userdata" ~｝` · `GET_LOCK('mc_db_init', 300)` · `-Djdbc.initLocation` 3) `8` · `47`(0 보다 큼) 4) `mc-web-a ami-010bbf6096e7bb791` · `mc-was-a ami-…`(같은 AL2023)
## 2-6. 켜는 순서 — 실제로 할 때 (그리고 다운타임)
<table header-row="true" fit-page-width="true">
	<tr>
		<td>순서</td>
		<td>할 일</td>
		<td>명령 · 확인</td>
		<td>주의</td>
	</tr>
	<tr>
		<td>0</td>
		<td>(선택) 골든 AMI 굽기</td>
		<td>콘솔 EC2 → mc-web-a · mc-was-a → 이미지 생성 → `base.web_ami_id` · `was_ami_id` 에 기입</td>
		<td>WAR 는 안 굽힘(재빌드) · 비밀 없음 확인</td>
	</tr>
	<tr>
		<td>1</td>
		<td>plan 확인</td>
		<td>`base.enable_asg = true` → `terraform plan` — 고정 EC2 4대 destroy + LT 2 · ASG 2 · 정책 3 create</td>
		<td>attachment 4개도 destroy</td>
	</tr>
	<tr>
		<td>2</td>
		<td>apply (점검 시간)</td>
		<td>`terraform apply` → ASG 가 인스턴스 생성 → grace 뒤 healthy</td>
		<td>**다운타임** ≈ WEB 2~3분 · WAS 6~9분(스톡) — 고정 EC2 가 먼저 사라지므로</td>
	</tr>
	<tr>
		<td>3</td>
		<td>확인</td>
		<td>`describe-auto-scaling-groups` · 대상 그룹 healthy 2/2 · 랜딩 200 · 로그 스트림에 새 인스턴스 ID</td>
		<td>9단계 진단 5줄 그대로</td>
	</tr>
	<tr>
		<td>4</td>
		<td>이후 설정 변경</td>
		<td>web.sh 수정 → apply(템플릿 새 버전) → `start-instance-refresh` → 절반씩 교체</td>
		<td>자동 시작 아님 · 진행률 `describe-instance-refreshes`</td>
	</tr>
	<tr>
		<td>무중단 대안</td>
		<td>2단계 apply</td>
		<td>① ASG 를 먼저 만들어 대상 그룹에 **둘 다** 붙임 → healthy 확인 → ② 고정 EC2 제거</td>
		<td>코드 개선 필요(`ec2_count` 와 `asg_count` 를 독립 스위치로) — 로드맵</td>
	</tr>
</table>
기억할 것 셋: **ASG = 대수를 사람이 아니라 시스템이 유지** · **그러려면 서버는 템플릿+user_data(또는 AMI)로 저절로 준비되고, 사라져도 잃는 게 없어야**(로그 Agent · 종료 훅 · 멱등 스키마) · **지금 코드의 전환은 다운타임이 있다 — 점검 시간에**.
# 3. 용어 — 이 단계에서만 쓰는 것
<table header-row="true" fit-page-width="true">
	<tr>
		<td>용어</td>
		<td>한 줄</td>
		<td>비유</td>
	</tr>
	<tr>
		<td>시작 템플릿</td>
		<td>인스턴스 생성 파라미터 묶음 · 버전 있음 · `$Latest`</td>
		<td>직원 채용 공고(자격 · 장비 · 첫날 할 일)</td>
	</tr>
	<tr>
		<td>ASG · min/max/desired</td>
		<td>템플릿으로 몇 대를 유지할지</td>
		<td>근무 인원 최소/최대/현재</td>
	</tr>
	<tr>
		<td>ELB 헬스체크 유형 · grace</td>
		<td>대상 그룹 판정을 교체 신호로 · 부팅 유예</td>
		<td>"진료 가능" 판정 · 수습 기간</td>
	</tr>
	<tr>
		<td>대상 추적 정책</td>
		<td>지표(CPU 60%)를 유지하도록 대수 조절</td>
		<td>대기 시간 보고 창구 열고 닫기</td>
	</tr>
	<tr>
		<td>인스턴스 새로 고침</td>
		<td>템플릿 새 버전으로 순차 교체(Rolling · 50%)</td>
		<td>교대 근무 교체</td>
	</tr>
	<tr>
		<td>수명 주기 훅</td>
		<td>종료(또는 시작) 직전 멈춰 뒷정리 시간</td>
		<td>퇴근 전 인수인계 5분</td>
	</tr>
	<tr>
		<td>골든 AMI</td>
		<td>설치가 끝난 이미지</td>
		<td>미리 세팅된 노트북</td>
	</tr>
	<tr>
		<td>user_data 멱등</td>
		<td>두 번 돌아도 같은 결과</td>
		<td>체크리스트(이미 한 건 건너뜀)</td>
	</tr>
	<tr>
		<td>IMDSv2</td>
		<td>인스턴스 메타데이터를 토큰으로만(SSRF 방어)</td>
		<td>사원증 없인 서류함 못 엶</td>
	</tr>
</table>
# 4. 왜 이렇게 만들었나 (멘토가 물을 만한 것)
- **왜 아직 ASG 를 안 켰나?** 트래픽이 없고, 전환에 다운타임이 있으며, 고정 2대로도 AZ 이중화는 된다. 코드는 준비돼 있어 스위치 하나 — 발표 전 점검 시간에 켤지 결정.
- **왜 헬스체크 유형이 ELB 인가?** EC2 상태 검사는 '켜져 있나' 만 본다. Apache/Tomcat 이 죽어도 EC2 는 정상. 대상 그룹 판정을 써야 앱 수준 장애가 교체 신호가 된다.
- **왜 WAS grace 가 900s 인가?** 스톡 AMI 에서 Tomcat 다운로드 + Maven 빌드 + Proxy 로그인 대기가 5~8분. 그 전에 실패 판정하면 끝없이 교체. 골든 AMI 면 300s.
- **왜 종료 훅이 WAS 에만?** catalina 로그(예외 스택)가 장애 분석에 중요. Apache 로그는 Agent 실시간으로 충분.
- **왜 WAR 를 AMI 에 안 굽나?** WAR 에 Proxy 주소·비밀이 들어가 AMI 가 계정 종속·비밀 포함이 된다. 부팅 때 재빌드가 안전(대신 1~2분).
- **로그는 ASG 에서 어떻게 지키나?** 서버에 두지 않는다 — Agent 실시간 + 스트림 = 인스턴스 ID + 종료 훅 sync + S3 1년(8단계).
# 5. 진입 기준 — 여기까지 오면 WEB 계층 한 바퀴
<details>
<summary>Q1. ASG 의 헬스체크 유형을 EC2 가 아니라 ELB 로 두는 이유는?</summary>
	EC2 상태 검사는 '인스턴스가 켜져 있나' 만 본다. Apache 가 죽어도 EC2 는 정상. ELB 유형이면 대상 그룹 헬스체크(5단계) 실패를 곧 교체 신호로 쓴다.
</details>
<details>
<summary>Q2. grace period 를 WAS 900s 로 둔 이유는? 골든 AMI 면?</summary>
	스톡 AMI 에서 Tomcat 다운로드 + Maven 빌드 + Proxy 로그인 대기가 5~8분. 그 전에 ELB 체크가 실패하면 ASG 가 '고장' 으로 보고 끝없이 교체한다. 골든 AMI 면 300s(코드가 자동 전환).
</details>
<details>
<summary>Q3. 템플릿을 고쳐 apply 했는데 서버가 옛 설정이다. 왜?</summary>
	템플릿 새 버전은 다음에 만드는 인스턴스부터 적용된다. 기존 인스턴스를 바꾸려면 인스턴스 새로 고침(Rolling 50%)을 시작해야 한다 — 자동 트리거를 안 둔 건 점검 시간에 사람이 시작하라는 뜻.
</details>
<details>
<summary>Q4. 로그와 DB 스키마는 ASG 에서 어떻게 지키나?</summary>
	로그: 서버에 두지 않는다 — Agent 실시간 → CloudWatch(스트림 = 인스턴스 ID) → S3 1년, WAS 는 종료 훅 300s 동안 마지막 로그 sync. 스키마: `IF NOT EXISTS`/`INSERT IGNORE` 로 멱등, 더 엄격히는 `db_init_mode=userdata` 의 GET_LOCK 직렬화.
</details>
# 6. 읽을 자료
- Notion — 🤓 AMI & Auto Scaling (팀 콘솔 절차 · v1→v2 교체) · 🧩 was (DB 초기화 우려)
- AWS 문서 — *Auto Scaling instance refresh* · *Amazon EC2 Auto Scaling lifecycle hooks* · *Target tracking scaling policies* · *Health checks for instances in an Auto Scaling group*
- 저장소 `infra/terraform-kdt5/README.md` 'ASG · AMI' 절 · `modules/base/compute.tf` · `user_data/was.sh`
<callout icon="🗺️" color="gray_bg">
	**로드맵 위치**: 0 VPC 입구 → 1 HTTP 기초 → 2 TLS 종료 지점 → 3 ALB 해부 → 4 오리진 보호(헤더) → 5 헬스체크 → 6 Apache 프록시 → 7 분산·타임아웃 → 8 WEB 관측 → 9 장애 모드 → **10 ASG·AMI(이 페이지)**.
</callout>
