# ---------- Cognito = IdP. 로그인은 Public ALB authenticate-cognito 액션 (앱 수정 없음) ----------
resource "aws_cognito_user_pool" "main" {
  name = "${local.p}-users"

  username_attributes      = ["email"]
  auto_verified_attributes = ["email"]
  mfa_configuration        = "OPTIONAL"

  software_token_mfa_configuration {
    enabled = true
  }

  password_policy {
    minimum_length    = 8
    require_lowercase = true
    require_uppercase = true
    require_numbers   = true
    require_symbols   = false
  }

  admin_create_user_config {
    allow_admin_create_user_only = true # 셀프 가입 끔: 관리자가 계정 생성
  }

  account_recovery_setting {
    recovery_mechanism {
      name     = "verified_email"
      priority = 1
    }
  }

  tags = merge(local.tier_tag.edge, { Name = "${local.p}-users" })
}

resource "aws_cognito_user_pool_domain" "main" {
  domain       = "${local.p}-hospital-${data.aws_caller_identity.current.account_id}"
  user_pool_id = aws_cognito_user_pool.main.id
}

resource "aws_cognito_user_group" "vets" {
  name         = "vets"
  user_pool_id = aws_cognito_user_pool.main.id
  description  = "수의사 → ROLE_VET"
  precedence   = 10
}

resource "aws_cognito_user_group" "admins" {
  name         = "admins"
  user_pool_id = aws_cognito_user_pool.main.id
  description  = "관리자 → ROLE_ADMIN"
  precedence   = 1
}

resource "aws_cognito_user_pool_client" "petclinic" {
  name            = "${local.p}-petclinic"
  user_pool_id    = aws_cognito_user_pool.main.id
  generate_secret = true

  allowed_oauth_flows                  = ["code"]
  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_scopes                 = ["openid", "email", "profile"]
  supported_identity_providers         = ["COGNITO"]
  callback_urls                        = ["https://${var.domain_name}/oauth2/idpresponse"]
  logout_urls                          = ["https://${var.domain_name}${local.app_context}/"]
  explicit_auth_flows                  = ["ALLOW_REFRESH_TOKEN_AUTH", "ALLOW_USER_SRP_AUTH"]
  prevent_user_existence_errors        = "ENABLED"

  access_token_validity  = 60
  id_token_validity      = 60
  refresh_token_validity = 8
  token_validity_units {
    access_token  = "minutes"
    id_token      = "minutes"
    refresh_token = "hours"
  }
}

