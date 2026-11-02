# ---------------------------------------------------------------------------
# API Gateway account settings (one per AWS account and region)
#
# WebSocket (and REST) stages can only write access logs when API Gateway's account
# settings point at an IAM role it may assume to push logs to CloudWatch; without it
# CreateStage fails with "CloudWatch Logs role ARN must be set in account settings to
# enable logging".
#
# Because the setting is account-wide, it is managed here at the root, not inside the
# module. If another stack already manages it in this account, set
# manage_api_gateway_account = false (or disable ws_access_logs).
# ---------------------------------------------------------------------------

resource "aws_iam_role" "api_gateway_logs" {
  count = var.manage_api_gateway_account ? 1 : 0

  name = "${local.prefix}-apigateway-logs-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Action    = "sts:AssumeRole"
      Principal = { Service = "apigateway.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "api_gateway_logs" {
  count = var.manage_api_gateway_account ? 1 : 0

  role       = aws_iam_role.api_gateway_logs[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonAPIGatewayPushToCloudWatchLogs"
}

resource "aws_api_gateway_account" "this" {
  count = var.manage_api_gateway_account ? 1 : 0

  cloudwatch_role_arn = aws_iam_role.api_gateway_logs[0].arn

  depends_on = [aws_iam_role_policy_attachment.api_gateway_logs]
}
