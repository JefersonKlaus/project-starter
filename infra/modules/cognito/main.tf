# Amazon Cognito: a user pool (the users allowed to open WebSocket connections) and one
# public app client (no secret: browsers and the AWS CLI authenticate with it directly).
#
# WebSocket APIs cannot use Cognito/JWT authorizers (HTTP and REST APIs only), so the
# tokens this pool issues are verified by lambda_ws_connect itself on $connect.

resource "aws_cognito_user_pool" "this" {
  name = var.name

  username_attributes      = ["email"] # users sign in with their e-mail
  auto_verified_attributes = ["email"]
  deletion_protection      = var.deletion_protection ? "ACTIVE" : "INACTIVE"

  admin_create_user_config {
    allow_admin_create_user_only = !var.allow_self_signup
  }

  password_policy {
    minimum_length                   = 12
    require_lowercase                = true
    require_uppercase                = true
    require_numbers                  = true
    require_symbols                  = true
    temporary_password_validity_days = 7
  }

  account_recovery_setting {
    recovery_mechanism {
      name     = "verified_email"
      priority = 1
    }
  }
}

resource "aws_cognito_user_pool_client" "this" {
  name         = "${var.name}-client"
  user_pool_id = aws_cognito_user_pool.this.id

  generate_secret = false # public client: usable from a browser or the CLI
  explicit_auth_flows = [
    "ALLOW_USER_SRP_AUTH",      # browsers (Amplify / amazon-cognito-identity-js)
    "ALLOW_USER_PASSWORD_AUTH", # CLI / scripts: aws cognito-idp initiate-auth
    "ALLOW_REFRESH_TOKEN_AUTH",
  ]
  prevent_user_existence_errors = "ENABLED"
  enable_token_revocation       = true

  access_token_validity  = var.token_validity_minutes
  id_token_validity      = var.token_validity_minutes
  refresh_token_validity = var.refresh_token_validity_days

  token_validity_units {
    access_token  = "minutes"
    id_token      = "minutes"
    refresh_token = "days"
  }
}
