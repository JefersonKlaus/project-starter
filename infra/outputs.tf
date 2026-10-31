output "lambda_create_function_name" {
  value = module.lambda_create.function_name
}

output "lambda_create_url" {
  description = "Public HTTPS endpoint (POST)"
  value       = module.lambda_create.function_url
}

output "lambda_status_function_name" {
  value = module.lambda_status.function_name
}

output "lambda_status_url" {
  description = "Public HTTPS endpoint (GET) - health check"
  value       = module.lambda_status.function_url
}
