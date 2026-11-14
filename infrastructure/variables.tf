variable "project" {
  description = "Prefix used for provisioned resource names"
  type        = string
  default     = "streamwise"
}

variable "environment" {
  description = "Deployment environment and API Gateway stage name"
  type        = string
  default     = "dev"
}

variable "aws_region" {
  description = "AWS region for Streamwise resources"
  type        = string
  default     = "ap-southeast-1"
}

variable "cors_origins" {
  description = "Allowed browser origins for the API; use an explicit frontend URL for production"
  type        = list(string)
  default     = ["*"]
}

variable "lambda_memory_mb" {
  description = "Memory allocated to the FastAPI Lambda runtime"
  type        = number
  default     = 2048
}

variable "lambda_timeout_s" {
  description = "Maximum Lambda request duration in seconds"
  type        = number
  default     = 60
}

variable "log_retention_days" {
  description = "CloudWatch log retention period"
  type        = number
  default     = 14
}

variable "throttle_rate_limit" {
  description = "API Gateway steady-state request limit per second"
  type        = number
  default     = 5
}

variable "throttle_burst_limit" {
  description = "API Gateway burst request limit"
  type        = number
  default     = 10
}

variable "force_destroy_bucket" {
  description = "Allow Terraform destroy to remove all current and noncurrent S3 object versions"
  type        = bool
  default     = false
}
