data "aws_caller_identity" "current" {}

locals {
  name = "${var.project}-${var.environment}"

  # Key schemas match what the Lambda functions read.
  tables = {
    users = {
      hash_key  = "user_id"
      range_key = null
    }
    content_embeddings = {
      hash_key  = "content_id"
      range_key = null
    }
    stream_history = {
      hash_key  = "content_id"
      range_key = "stream_date"
    }
    user_interactions = {
      hash_key  = "user_id"
      range_key = "timestamp"
    }
  }
}

resource "aws_s3_bucket" "models" {
  bucket = "${local.name}-models-${data.aws_caller_identity.current.account_id}"
}

resource "aws_s3_bucket_public_access_block" "models" {
  bucket                  = aws_s3_bucket.models.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "models" {
  bucket = aws_s3_bucket.models.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "models" {
  bucket = aws_s3_bucket.models.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_dynamodb_table" "this" {
  for_each = local.tables

  name         = "${local.name}-${replace(each.key, "_", "-")}"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = each.value.hash_key
  range_key    = each.value.range_key

  attribute {
    name = each.value.hash_key
    type = "S"
  }

  dynamic "attribute" {
    for_each = each.value.range_key == null ? [] : [each.value.range_key]

    content {
      name = attribute.value
      type = "S"
    }
  }

  point_in_time_recovery {
    enabled = true
  }

  server_side_encryption {
    enabled = true
  }
}
