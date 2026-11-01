terraform {
  required_version = ">= 1.10"

  required_providers {
    aws     = { source = "hashicorp/aws", version = "~> 5.70" }
    archive = { source = "hashicorp/archive", version = "~> 2.4" }
  }

  # Remote state in S3, one bucket per environment, always prefixed with the env name.
  # The bucket is passed at init time (CI builds it from GitHub variables):
  #   terraform init -reconfigure -backend-config="bucket=sandbox-<TF_STATE_BUCKET>"
  backend "s3" {
    key          = "back_end_state_file/terraform.tfstate"
    region       = "us-east-2"
    encrypt      = true
    use_lockfile = true
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = { Environment = var.environment, Project = var.project }
  }
}

locals {
  prefix        = "${var.environment}-${var.project}" # e.g. dev-backend-ia (resources)
  bucket_prefix = lookup({ dev = "sandbox", stage = "stage", prod = "production" }, var.environment)
  rag_s3_bucket = "${local.bucket_prefix}-${var.rag_bucket_name}"
}

locals {
  api_dir = "${path.module}/../backend-ia/api"
}

# ---------------------------------------------------------------------------
# lambda_create: generates an AWS architecture from a product description
# ---------------------------------------------------------------------------

module "lambda_create" {
  source = "./modules/lambda"

  lambda_function_name = "${local.prefix}-lambda-create"
  source_dir           = "${local.api_dir}/lambda_create"
  handler              = "main.lambda_handler" # main.py sits at the zip root
  requirements_file    = "${local.api_dir}/lambda_create/requirements.txt"

  environment_variables = {
    GROQ_API_KEY  = var.groq_api_key
    CORS_ORIGINS  = join(",", var.cors_origins)
    RAG_S3_BUCKET = local.rag_s3_bucket
    RAG_S3_KEY    = "rag_index.json"
  }

  # Least privilege: read only the RAG index object
  policy_json = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "s3:GetObject"
      Resource = "arn:aws:s3:::${local.rag_s3_bucket}/rag_index.json"
    }]
  })
}

# ---------------------------------------------------------------------------
# lambda_status: health check. Verifies the dependencies of lambda_create
# (RAG index in S3, GROQ_API_KEY set, Groq accepts the key) and returns 200 / 503
# ---------------------------------------------------------------------------

module "lambda_status" {
  source = "./modules/lambda"

  lambda_function_name = "${local.prefix}-lambda-status"
  source_dir           = "${local.api_dir}/lambda_status"
  handler              = "main.lambda_handler"
  requirements_file    = "${local.api_dir}/lambda_status/requirements.txt" # groq SDK
  memory_size          = 256
  timeout              = 30 # the Groq "hello" call is capped at 10s by the function itself

  environment_variables = {
    GROQ_API_KEY  = var.groq_api_key
    RAG_S3_BUCKET = local.rag_s3_bucket
    RAG_S3_KEY    = "rag_index.json"
  }

  # HeadObject on the index; ListBucket lets S3 answer 404 (instead of 403) when it is missing
  policy_json = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = "s3:GetObject"
        Resource = "arn:aws:s3:::${local.rag_s3_bucket}/rag_index.json"
      },
      {
        Effect    = "Allow"
        Action    = "s3:ListBucket"
        Resource  = "arn:aws:s3:::${local.rag_s3_bucket}"
        Condition = { StringEquals = { "s3:prefix" = "rag_index.json" } }
      },
    ]
  })
}

# ---------------------------------------------------------------------------
# API Gateway (HTTP API, no authentication): single public entry point
#   POST /prompt      -> lambda_create
#   GET  /healthcheck -> lambda_status
# ---------------------------------------------------------------------------

module "api_gateway" {
  source = "./modules/apigateway"

  api_name           = "${local.prefix}-api"
  cors_allow_origins = var.cors_origins

  routes = {
    "POST /prompt" = {
      function_name = module.lambda_create.function_name
      invoke_arn    = module.lambda_create.invoke_arn
    }
    "GET /healthcheck" = {
      function_name = module.lambda_status.function_name
      invoke_arn    = module.lambda_status.invoke_arn
    }
  }
}
