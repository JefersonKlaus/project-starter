output "api_id" {
  value = aws_apigatewayv2_api.this.id
}

output "execution_arn" {
  description = "Execution ARN of the API, e.g. to grant execute-api:ManageConnections on \"<execution_arn>/<stage>/POST/@connections/*\""
  value       = aws_apigatewayv2_api.this.execution_arn
}

output "stage_name" {
  value = aws_apigatewayv2_stage.this.name
}

output "websocket_url" {
  description = "URL clients connect to: wss://<id>.execute-api.<region>.amazonaws.com/<stage>"
  value       = aws_apigatewayv2_stage.this.invoke_url
}

output "connections_url" {
  description = "HTTPS endpoint of the @connections management API (post_to_connection), same host and stage as the wss:// URL"
  value       = replace(aws_apigatewayv2_stage.this.invoke_url, "wss://", "https://")
}
