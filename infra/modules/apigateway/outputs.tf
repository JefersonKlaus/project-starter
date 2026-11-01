output "api_id" {
  value = aws_apigatewayv2_api.this.id
}

output "api_endpoint" {
  description = "Base URL of the API ($default stage), without trailing slash"
  value       = aws_apigatewayv2_api.this.api_endpoint
}

output "route_urls" {
  description = "Full URL of each route, keyed by route key (\"METHOD /path\")"
  value = {
    for key, route in local.routes : key => "${aws_apigatewayv2_api.this.api_endpoint}${route.path}"
  }
}
