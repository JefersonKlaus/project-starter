variable "environment" {
  description = "Target environment: dev, stage or prod"
  type        = string

  validation {
    condition     = contains(["dev", "stage", "prod"], var.environment)
    error_message = "environment must be dev, stage or prod."
  }
}

variable "project" {
  type    = string
  default = "backend-ia"
}

variable "aws_region" {
  type    = string
  default = "us-east-2"
}

variable "groq_api_key" {
  description = "Set with: export TF_VAR_groq_api_key=gsk_..."
  type        = string
  sensitive   = true
}

variable "cors_origins" {
  description = "Browser origins lambda_create echoes in Access-Control-Allow-Origin (Function URL calls)"
  type        = list(string)
  default     = []
}

variable "rag_bucket_name" {
  description = "Base name of the RAG bucket; its prefix is sandbox, stage or production according to the environment. Set with TF_VAR_rag_bucket_name."
  type        = string
}

variable "manage_api_gateway_account" {
  description = "Manage the account-level CloudWatch Logs role of API Gateway here (required by WebSocket access logs; one per account and region). Set to false if another stack owns it."
  type        = bool
  default     = true
}

variable "ws_access_logs" {
  description = "Write access logs of the WebSocket API to CloudWatch. Needs the account-level role (manage_api_gateway_account or an existing one)."
  type        = bool
  default     = true
}
