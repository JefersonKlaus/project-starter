variable "lambda_function_name" {
  type = string
}

variable "source_dir" {
  description = "Folder zipped as the function code (flat layout): its files land at the zip root, e.g. <source_dir>/main.py"
  type        = string
}

variable "handler" {
  description = "Entry point, e.g. main.lambda_handler (file main.py at the zip root, function lambda_handler)"
  type        = string
}

variable "excludes" {
  description = "Paths inside source_dir that must not be shipped (relative to source_dir, glob allowed)"
  type        = list(string)
  default = [
    "tests", "pytest.ini", ".env", "*/.env", ".venv",
    "__pycache__", "*/__pycache__", "*/*/__pycache__",
    "requirements.txt", "requirements-dev.txt",
  ]
}

variable "requirements_file" {
  description = "requirements.txt to install into a dependencies layer (optional)"
  type        = string
  default     = null
}

variable "memory_size" {
  type    = number
  default = 1024
}

variable "timeout" {
  type    = number
  default = 300
}

variable "environment_variables" {
  type    = map(string)
  default = {}
}

variable "policy_json" {
  description = "IAM policy document (JSON) with the function's extra permissions (optional)"
  type        = string
  default     = null
}
