# ---------- 콘솔로 만든 RDS(database-1) 를 코드로 편입 ----------
# 도면 ④(파라미터 그룹 require_secure_transport · 백업 7일 PITR · 삭제 방지)는 인스턴스 속성 변경이라
# data 로는 불가 → import 블록으로 상태에 들여온 뒤 rds.tf 의 aws_db_instance.main 이 관리.
# 첫 plan 에서 보여야 하는 차이: parameter_group_name · backup_retention_period · deletion_protection · copy_tags_to_snapshot · 태그 뿐.
# 다른 차이가 보이면 variables.tf 의 db.* 를 콘솔 값에 맞출 것 (교체(replace) 가 뜨면 절대 apply 금지).
import {
  to = aws_db_instance.main
  id = "database-1"
}
