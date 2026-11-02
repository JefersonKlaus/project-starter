variable "api_name" {
  type = string
}

variable "routes" {
  description = <<-EOT
    Routes exposed by the WebSocket API, keyed by route key ("$connect", "$disconnect",
    "$default" or a custom key matched by route_selection_expression), each pointing at the
    Lambda that serves it. Set respond = true when the Lambda's response body must be sent
    back to the client (two-way route), e.g.
    { "prompt" = { function_name = ..., invoke_arn = ..., respond = true } }
  EOT
  type = map(object({
    function_name = string
    invoke_arn    = string
    respond       = optional(bool, false)
  }))

  validation {
    condition = alltrue([
      for key in keys(var.routes) : can(regex("^(\\$connect|\\$disconnect|\\$default|[A-Za-z0-9_.-]+)$", key))
    ])
    error_message = "Every route key must be $connect, $disconnect, $default or a custom key such as \"prompt\"."
  }
}

variable "route_selection_expression" {
  description = "Field of the client's JSON message that selects the custom route"
  type        = string
  default     = "$request.body.action"
}

variable "stage_name" {
  description = "Name of the stage, i.e. the last path segment of the wss:// URL (WebSocket APIs do not support the $default stage)"
  type        = string
}

variable "log_retention_in_days" {
  description = "Retention of the access log group"
  type        = number
  default     = 14
}
