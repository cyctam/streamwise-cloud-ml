resource "aws_lambda_layer_version" "dependencies" {
  s3_bucket           = aws_s3_bucket.models.bucket
  s3_key              = aws_s3_object.lambda_layer.key
  layer_name          = "${local.name}-python-dependencies"
  source_code_hash    = filebase64sha256("${path.module}/.build/python-dependencies.zip")
  compatible_runtimes      = ["python3.12"]
  compatible_architectures = ["x86_64"]
}

resource "aws_cloudwatch_log_group" "api" {
  name              = "/aws/lambda/${local.name}-api"
  retention_in_days = var.log_retention_days
}

resource "aws_lambda_function" "api" {
  function_name    = "${local.name}-api"
  role             = aws_iam_role.api.arn
  runtime          = "python3.12"
  handler          = "api.lambda_handler.handler"
  filename         = "${path.module}/.build/streamwise-api.zip"
  source_code_hash = filebase64sha256("${path.module}/.build/streamwise-api.zip")
  memory_size      = var.lambda_memory_mb
  timeout          = var.lambda_timeout_s
  layers           = [aws_lambda_layer_version.dependencies.arn]

  environment {
    variables = {
      DATA_DIR      = "/var/task/data/raw"
      ARTIFACT_DIR  = "/tmp/artifacts"
      MODEL_BUCKET  = aws_s3_bucket.models.bucket
      MODEL_KEY     = aws_s3_object.model.key
      METRICS_KEY   = aws_s3_object.metrics.key
      CORS_ORIGINS  = join(",", var.cors_origins)
    }
  }

  depends_on = [aws_cloudwatch_log_group.api]
}
