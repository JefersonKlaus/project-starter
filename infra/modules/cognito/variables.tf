variable "name" {
  description = "Name of the user pool; the app client is named <name>-client"
  type        = string
}

variable "allow_self_signup" {
  description = "Let anyone sign up. When false (default) only an administrator creates users (aws cognito-idp admin-create-user)."
  type        = bool
  default     = false
}

variable "deletion_protection" {
  description = "Refuse to destroy the user pool (and its users) through Terraform"
  type        = bool
  default     = false
}

variable "token_validity_minutes" {
  description = "Lifetime of the access and ID tokens (5 minutes to 1 day)"
  type        = number
  default     = 60
}

variable "refresh_token_validity_days" {
  description = "Lifetime of the refresh token (1 hour to 10 years, in days)"
  type        = number
  default     = 30
}
