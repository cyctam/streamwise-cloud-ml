variable "project" {
  description = "Prefix for all resource names"
  type        = string
  default     = "streamwise"
}

variable "environment" {
  description = "Environment name; also used as the API Gateway stage name"
  type        = string
  default     = "dev"
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "lambda_memory_mb" {
  description = "Memory per Lambda function"
  type        = number
  default     = 256
}

variable "lambda_timeout_s" {
  description = "Timeout per Lambda function, in seconds"
  type        = number
  default     = 30
}

variable "log_retention_days" {
  description = "CloudWatch log retention for the Lambda functions"
  type        = number
  default     = 14
}

variable "throttle_rate_limit" {
  description = "API Gateway steady-state requests per second"
  type        = number
  default     = 5
}

variable "throttle_burst_limit" {
  description = "API Gateway burst requests"
  type        = number
  default     = 10
}

variable "quota_per_day" {
  description = "API Gateway requests per day for the web client key"
  type        = number
  default     = 1000
}
