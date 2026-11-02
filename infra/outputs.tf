output "lambda_create_function_name" {
  value = module.lambda_create.function_name
}

output "lambda_create_url" {
  description = "Public HTTPS endpoint (POST) - generates the architecture (Function URL)"
  value       = module.lambda_create.function_url
}

output "lambda_status_function_name" {
  value = module.lambda_status.function_name
}

output "lambda_status_url" {
  description = "Public HTTPS endpoint (GET) - health check (Function URL)"
  value       = module.lambda_status.function_url
}

output "lambda_ws_connect_function_name" {
  value = module.lambda_ws_connect.function_name
}

output "lambda_ws_prompt_function_name" {
  value = module.lambda_ws_prompt.function_name
}

output "lambda_ws_worker_function_name" {
  value = module.lambda_ws_worker.function_name
}

output "ws_api_url" {
  description = "WebSocket endpoint (wss://) - routes $connect and prompt"
  value       = module.api_gateway_websocket.websocket_url
}

output "cognito_user_pool_id" {
  description = "Cognito user pool whose tokens open WebSocket connections"
  value       = module.cognito.user_pool_id
}

output "cognito_app_client_id" {
  description = "App client to authenticate with (aws cognito-idp initiate-auth --client-id ...)"
  value       = module.cognito.app_client_id
}

output "ws_connections_url" {
  description = "HTTPS endpoint of the @connections management API used by lambda_ws_worker"
  value       = module.api_gateway_websocket.connections_url
}
