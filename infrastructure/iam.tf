data "aws_iam_policy_document" "lambda_assume" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

# Read-only access to the model bucket and the DynamoDB tables.
data "aws_iam_policy_document" "data_access" {
  statement {
    sid       = "ReadTables"
    actions   = ["dynamodb:GetItem", "dynamodb:BatchGetItem", "dynamodb:Query", "dynamodb:Scan"]
    resources = flatten([for t in aws_dynamodb_table.this : [t.arn, "${t.arn}/index/*"]])
  }

  statement {
    sid       = "ReadModels"
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.models.arn}/*"]
  }
}

# One role per function, so permissions can diverge later.
resource "aws_iam_role" "lambda" {
  for_each = local.functions

  name               = "${local.name}-${each.key}"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

resource "aws_iam_role_policy_attachment" "basic_execution" {
  for_each = local.functions

  role       = aws_iam_role.lambda[each.key].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "data_access" {
  for_each = local.functions

  name   = "data-access"
  role   = aws_iam_role.lambda[each.key].id
  policy = data.aws_iam_policy_document.data_access.json
}
