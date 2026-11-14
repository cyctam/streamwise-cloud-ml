data "aws_iam_policy_document" "lambda_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

data "aws_iam_policy_document" "api_access" {
  statement {
    sid       = "ReadVersionedModelArtifacts"
    actions   = ["s3:GetObject"]
    resources = [
      aws_s3_object.model.arn,
      aws_s3_object.metrics.arn,
    ]
  }
}

resource "aws_iam_role" "api" {
  name               = "${local.name}-api"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

resource "aws_iam_role_policy_attachment" "api_logs" {
  role       = aws_iam_role.api.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "api_assets" {
  name   = "read-model-artifacts"
  role   = aws_iam_role.api.id
  policy = data.aws_iam_policy_document.api_access.json
}
