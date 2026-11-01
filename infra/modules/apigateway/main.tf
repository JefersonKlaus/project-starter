# API Gateway (HTTP API): open API (no authorizer), one Lambda proxy integration per route,
# $default stage with auto-deploy and access logs in CloudWatch

locals {
  # "POST /prompt" -> { method = "POST", path = "/prompt" }
  routes = {
    for key, route in var.routes : key => merge(route, {
      method = split(" ", key)[0]
      path   = split(" ", key)[1]
    })
  }
}

# --- API --------------------------------------------------------------------

resource "aws_apigatewayv2_api" "this" {
  name          = var.api_name
  protocol_type = "HTTP"

  # Preflight (OPTIONS) is answered by API Gateway itself when origins are given.
  dynamic "cors_configuration" {
    for_each = length(var.cors_allow_origins) > 0 ? [1] : []

    content {
      allow_origins = var.cors_allow_origins
      allow_methods = distinct(concat([for r in local.routes : r.method], ["OPTIONS"]))
      allow_headers = ["content-type"]
      max_age       = 3600
    }
  }
}

# --- Routes -> Lambda -------------------------------------------------------

resource "aws_apigatewayv2_integration" "this" {
  for_each = local.routes

  api_id                 = aws_apigatewayv2_api.this.id
  integration_type       = "AWS_PROXY"
  integration_method     = "POST" # Lambda is always invoked with POST, whatever the route method
  integration_uri        = each.value.invoke_arn
  payload_format_version = "2.0"
}

# No authorization: the routes are public (authorization_type defaults to NONE).
resource "aws_apigatewayv2_route" "this" {
  for_each = local.routes

  api_id             = aws_apigatewayv2_api.this.id
  route_key          = each.key
  target             = "integrations/${aws_apigatewayv2_integration.this[each.key].id}"
  authorization_type = "NONE"
}

# Lets this API (any stage) invoke the function, restricted to the route's method and path
resource "aws_lambda_permission" "this" {
  for_each = local.routes

  statement_id  = "AllowInvokeFrom-${var.api_name}-${each.value.method}-${replace(trimprefix(each.value.path, "/"), "/", "-")}"
  action        = "lambda:InvokeFunction"
  function_name = each.value.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.this.execution_arn}/*/${each.value.method == "ANY" ? "*" : each.value.method}${each.value.path}"
}

# --- Stage (with access logs) ----------------------------------------------

resource "aws_cloudwatch_log_group" "access" {
  name              = "/aws/apigateway/${var.api_name}"
  retention_in_days = var.log_retention_in_days
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.this.id
  name        = "$default" # served at the API root: https://<id>.execute-api.<region>.amazonaws.com/<path>
  auto_deploy = true

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.access.arn
    format = jsonencode({
      requestId        = "$context.requestId"
      requestTime      = "$context.requestTime"
      httpMethod       = "$context.httpMethod"
      routeKey         = "$context.routeKey"
      path             = "$context.path"
      status           = "$context.status"
      responseLength   = "$context.responseLength"
      integrationError = "$context.integrationErrorMessage"
      ip               = "$context.identity.sourceIp"
      userAgent        = "$context.identity.userAgent"
    })
  }
}
