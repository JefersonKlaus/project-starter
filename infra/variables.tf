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
  default = "us-east-1"
}

variable "groq_api_key" {
  description = "Set with: export TF_VAR_groq_api_key=gsk_..."
  type        = string
  sensitive   = true
}

variable "cors_origins" {
  description = "Browser origins allowed to call the Lambda"
  type        = list(string)
  default     = []
}

variable "rag_bucket_name" {
  description = "Base name of the RAG bucket; its prefix is sandbox, stage or production according to the environment. Set with TF_VAR_rag_bucket_name."
  type        = string
}
