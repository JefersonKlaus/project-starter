output "function_name" {
  value = aws_lambda_function.this.function_name
}

output "function_arn" {
  value = aws_lambda_function.this.arn
}

output "invoke_arn" {
  description = "ARN used by API Gateway integrations to invoke the function"
  value       = aws_lambda_function.this.invoke_arn
}

output "function_url" {
  value = aws_lambda_function_url.this.function_url
}
