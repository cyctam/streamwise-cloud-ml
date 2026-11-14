output "api_url" {
  description = "API Gateway base URL; use as VITE_API_URL for the React frontend"
  value       = aws_api_gateway_stage.this.invoke_url
}

output "model_bucket" {
  description = "Private, versioned S3 bucket storing the trained model artifact"
  value       = aws_s3_bucket.models.bucket
}

output "lambda_function_name" {
  description = "FastAPI application Lambda function name"
  value       = aws_lambda_function.api.function_name
}
