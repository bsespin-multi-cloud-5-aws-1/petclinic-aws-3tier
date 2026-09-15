# ---------- kdt5 모드: 콘솔로 만든 RDS(database-1) 를 코드로 편입. create_base=true 면 import 없음(새로 생성) ----------
# 도면 ④(파라미터 그룹 require_secure_transport · 백업 7일 PITR · 삭제 방지)는 인스턴스 속성 변경이라 data 로는 불가.
# 첫 plan 에서 보여야 하는 차이: parameter_group_name · backup_retention_period · deletion_protection · copy_tags_to_snapshot · 태그 뿐.
# 다른 차이가 보이면 variables.tf 의 db.* 를 콘솔 값에 맞출 것 (교체(replace) 가 뜨면 절대 apply 금지).
import {
  for_each = var.create_base ? {} : { (var.existing.db_identifier) = var.existing.db_identifier }
  to       = aws_db_instance.main
  id       = each.value
}
