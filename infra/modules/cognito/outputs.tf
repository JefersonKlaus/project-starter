output "user_pool_id" {
  description = "e.g. us-east-2_AbCdEfGhI (the region is its prefix)"
  value       = aws_cognito_user_pool.this.id
}

output "user_pool_arn" {
  value = aws_cognito_user_pool.this.arn
}

output "app_client_id" {
  description = "Public app client (no secret) that issues the tokens"
  value       = aws_cognito_user_pool_client.this.id
}

output "issuer" {
  description = "iss claim of the tokens; the JWKS lives at <issuer>/.well-known/jwks.json"
  value       = "https://${aws_cognito_user_pool.this.endpoint}"
}
