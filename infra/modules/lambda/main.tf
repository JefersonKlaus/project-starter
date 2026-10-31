# AWS Lambda: code zip, dependencies layer, execution role, log group, function and public URL

locals {
  name = replace(var.lambda_function_name, "-", "_")
}

# --- Function code ---------------------------------------------------------

data "archive_file" "lambda_zip" {
  type        = "zip"
  source_dir  = var.source_dir
  output_path = "${path.module}/zip/${local.name}_function_payload.zip"
  excludes    = var.excludes
}

# --- Dependencies layer (only when a requirements file is given) -----------
# pip installs the requirements into build/<name>/python, which is zipped as a layer.
# The install runs on every apply (a fresh CI checkout has no build folder); a new
# layer version is published only when the resulting zip actually changes.

resource "terraform_data" "deps" {
  count = var.requirements_file == null ? 0 : 1

  triggers_replace = timestamp()

  provisioner "local-exec" {
    command = "pip install -q -r ${var.requirements_file} -t ${path.module}/build/${local.name}/python --platform manylinux2014_x86_64 --python-version 3.12 --only-binary=:all: --no-compile --upgrade"
  }
}

data "archive_file" "layer_zip" {
  count = var.requirements_file == null ? 0 : 1

  type        = "zip"
  source_dir  = "${path.module}/build/${local.name}"
  output_path = "${path.module}/zip/${local.name}_layer_payload.zip"

  depends_on = [terraform_data.deps]
}

resource "aws_lambda_layer_version" "deps" {
  count = var.requirements_file == null ? 0 : 1

  layer_name          = "${var.lambda_function_name}-deps"
  filename            = data.archive_file.layer_zip[0].output_path
  source_code_hash    = data.archive_file.layer_zip[0].output_base64sha256
  compatible_runtimes = ["python3.12"]
}

# --- IAM execution role ----------------------------------------------------

resource "aws_iam_role" "this" {
  name = "${var.lambda_function_name}-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Action    = "sts:AssumeRole"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
}

# CloudWatch Logs access
resource "aws_iam_role_policy_attachment" "logs" {
  role       = aws_iam_role.this.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# Function-specific permissions supplied by the caller (optional)
resource "aws_iam_role_policy" "this" {
  count = var.policy_json == null ? 0 : 1

  name   = "${var.lambda_function_name}-policy"
  role   = aws_iam_role.this.id
  policy = var.policy_json
}

# --- Log group (created first so the retention applies) --------------------

resource "aws_cloudwatch_log_group" "this" {
  name              = "/aws/lambda/${var.lambda_function_name}"
  retention_in_days = 14
}

# --- Function --------------------------------------------------------------

resource "aws_lambda_function" "this" {
  function_name = var.lambda_function_name
  role          = aws_iam_role.this.arn
  handler       = var.handler
  runtime       = "python3.12"
  memory_size   = var.memory_size
  timeout       = var.timeout

  filename         = data.archive_file.lambda_zip.output_path
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256
  layers           = aws_lambda_layer_version.deps[*].arn

  environment {
    variables = var.environment_variables
  }

  depends_on = [aws_cloudwatch_log_group.this, aws_iam_role_policy_attachment.logs]
}

# Public endpoint. No CORS block here: the Python code builds its own CORS headers.
resource "aws_lambda_function_url" "this" {
  function_name      = aws_lambda_function.this.function_name
  authorization_type = "NONE"
}
