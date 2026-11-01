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

output "api_endpoint" {
  description = "Base URL of the public API Gateway (HTTP API)"
  value       = module.api_gateway.api_endpoint
}

output "api_prompt_url" {
  description = "POST /prompt - generates the architecture (lambda_create)"
  value       = module.api_gateway.route_urls["POST /prompt"]
}

output "api_healthcheck_url" {
  description = "GET /healthcheck - health check (lambda_status)"
  value       = module.api_gateway.route_urls["GET /healthcheck"]
}
