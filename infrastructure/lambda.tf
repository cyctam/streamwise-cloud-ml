locals {
  functions = {
    prediction = {
      route      = "predict"
      source_dir = "${path.module}/../services/lambda/prediction"
      env = tomap({
        MODEL_BUCKET  = aws_s3_bucket.models.bucket
        MODEL_KEY     = "models/hybrid_model.pkl"
        USERS_TABLE   = aws_dynamodb_table.this["users"].name
        CONTENT_TABLE = aws_dynamodb_table.this["content_embeddings"].name
      })
    }
    forecasting = {
      route      = "forecast"
      source_dir = "${path.module}/../services/lambda/forecasting"
      env = tomap({
        FORECASTING_MODEL_BUCKET = aws_s3_bucket.models.bucket
        FORECASTING_MODEL_KEY    = "models/forecasting_model.pkl"
        CONTENT_EMBEDDINGS_TABLE = aws_dynamodb_table.this["content_embeddings"].name
        STREAM_HISTORY_TABLE     = aws_dynamodb_table.this["stream_history"].name
        USER_INTERACTIONS_TABLE  = aws_dynamodb_table.this["user_interactions"].name
      })
    }
  }
}

data "archive_file" "lambda" {
  for_each = local.functions

  type        = "zip"
  source_dir  = each.value.source_dir
  output_path = "${path.module}/.build/${each.key}.zip"
  excludes    = ["README.md"]
}

resource "aws_cloudwatch_log_group" "lambda" {
  for_each = local.functions

  name              = "/aws/lambda/${local.name}-${each.key}"
  retention_in_days = var.log_retention_days
}

resource "aws_lambda_function" "this" {
  for_each = local.functions

  function_name    = "${local.name}-${each.key}"
  role             = aws_iam_role.lambda[each.key].arn
  runtime          = "python3.12"
  handler          = "lambda_function.lambda_handler"
  filename         = data.archive_file.lambda[each.key].output_path
  source_code_hash = data.archive_file.lambda[each.key].output_base64sha256
  memory_size      = var.lambda_memory_mb
  timeout          = var.lambda_timeout_s

  environment {
    variables = each.value.env
  }

  depends_on = [aws_cloudwatch_log_group.lambda]
}
