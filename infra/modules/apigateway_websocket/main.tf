# API Gateway (WebSocket API): open API (no authorizer), one Lambda proxy integration per
# route, explicit deployment + named stage (WebSocket stages have no auto-deploy) and
# access logs in CloudWatch.
#
# Route keys are either the predefined ones ($connect, $disconnect, $default) or the value
# of the field selected by route_selection_expression in the client's JSON message
# (e.g. {"action": "prompt", ...} -> route "prompt").

locals {
  # "$connect" -> "connect": route keys are used inside IAM statement ids
  route_ids = { for key, route in var.routes : key => replace(key, "$", "") }

  # Routes whose integration response is sent back to the client (two-way communication)
  responding_routes = { for key, route in var.routes : key => route if route.respond }
}

# --- API --------------------------------------------------------------------

resource "aws_apigatewayv2_api" "this" {
  name                       = var.api_name
  protocol_type              = "WEBSOCKET"
  route_selection_expression = var.route_selection_expression
}

# --- Routes -> Lambda -------------------------------------------------------

resource "aws_apigatewayv2_integration" "this" {
  for_each = var.routes

  api_id             = aws_apigatewayv2_api.this.id
  integration_type   = "AWS_PROXY"
  integration_method = "POST" # Lambda is always invoked with POST
  integration_uri    = each.value.invoke_arn
}

# No authorization at the API level: $connect decides (2xx accepts, anything else rejects).
resource "aws_apigatewayv2_route" "this" {
  for_each = var.routes

  api_id             = aws_apigatewayv2_api.this.id
  route_key          = each.key
  target             = "integrations/${aws_apigatewayv2_integration.this[each.key].id}"
  authorization_type = "NONE"
}

# Without a route response the Lambda's answer never reaches the client (one-way route).
resource "aws_apigatewayv2_route_response" "this" {
  for_each = local.responding_routes

  api_id             = aws_apigatewayv2_api.this.id
  route_id           = aws_apigatewayv2_route.this[each.key].id
  route_response_key = "$default"
}

# Lets this API (any stage) invoke the function, restricted to the route
resource "aws_lambda_permission" "this" {
  for_each = var.routes

  statement_id  = "AllowInvokeFrom-${var.api_name}-${local.route_ids[each.key]}"
  action        = "lambda:InvokeFunction"
  function_name = each.value.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.this.execution_arn}/*/${each.key}"
}

# --- Deployment + stage (with access logs) ----------------------------------

# A new deployment is created whenever a route, integration or route response changes.
resource "aws_apigatewayv2_deployment" "this" {
  api_id      = aws_apigatewayv2_api.this.id
  description = "Managed by Terraform"

  triggers = {
    redeployment = sha1(join(",", tolist([
      jsonencode(aws_apigatewayv2_integration.this),
      jsonencode(aws_apigatewayv2_route.this),
      jsonencode(aws_apigatewayv2_route_response.this),
    ])))
  }

  lifecycle {
    create_before_destroy = true
  }

  depends_on = [aws_apigatewayv2_route.this, aws_apigatewayv2_route_response.this]
}

resource "aws_cloudwatch_log_group" "access" {
  name              = "/aws/apigateway/${var.api_name}"
  retention_in_days = var.log_retention_in_days
}

resource "aws_apigatewayv2_stage" "this" {
  api_id        = aws_apigatewayv2_api.this.id
  name          = var.stage_name # served at wss://<id>.execute-api.<region>.amazonaws.com/<stage>
  deployment_id = aws_apigatewayv2_deployment.this.id

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.access.arn
    format = jsonencode({
      requestId        = "$context.requestId"
      requestTime      = "$context.requestTime"
      connectionId     = "$context.connectionId"
      eventType        = "$context.eventType"
      routeKey         = "$context.routeKey"
      messageDirection = "$context.messageDirection"
      status           = "$context.status"
      integrationError = "$context.integration.error"
      ip               = "$context.identity.sourceIp"
      userAgent        = "$context.identity.userAgent"
    })
  }
}
