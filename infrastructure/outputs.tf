output "api_url" {
  description = "Set as PREDICTION_API_URL and FORECAST_API_URL in the web app"
  value       = aws_api_gateway_stage.this.invoke_url
}

output "api_key" {
  description = "Set as API_GATEWAY_KEY in the web app"
  value       = aws_api_gateway_api_key.web.value
  sensitive   = true
}

output "model_bucket" {
  description = "Upload hybrid_model.pkl and forecasting_model.pkl under models/"
  value       = aws_s3_bucket.models.bucket
}

output "dynamodb_tables" {
  description = "Table names to use in the training notebook"
  value       = { for k, t in aws_dynamodb_table.this : k => t.name }
}
