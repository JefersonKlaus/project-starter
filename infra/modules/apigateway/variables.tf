variable "api_name" {
  type = string
}

variable "routes" {
  description = <<-EOT
    Routes exposed by the API, keyed by route key ("METHOD /path"), each pointing at the
    Lambda that serves it, e.g. { "POST /prompt" = { function_name = ..., invoke_arn = ... } }
  EOT
  type = map(object({
    function_name = string
    invoke_arn    = string
  }))

  validation {
    condition = alltrue([
      for key in keys(var.routes) : can(regex("^(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS|ANY) /", key))
    ])
    error_message = "Every route key must look like \"METHOD /path\", e.g. \"POST /prompt\"."
  }
}

variable "cors_allow_origins" {
  description = "Browser origins allowed by the API (preflight handled by API Gateway). Empty list disables CORS."
  type        = list(string)
  default     = []
}

variable "log_retention_in_days" {
  description = "Retention of the access log group"
  type        = number
  default     = 14
}
