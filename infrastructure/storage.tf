data "aws_caller_identity" "current" {}

locals {
  name = "${var.project}-${var.environment}"
}

resource "aws_s3_bucket" "models" {
  bucket        = "${local.name}-models-${data.aws_caller_identity.current.account_id}"
  force_destroy = var.force_destroy_bucket
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
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "models" {
  bucket = aws_s3_bucket.models.id
  rule {
    apply_server_side_encryption_by_default { sse_algorithm = "AES256" }
  }
}

resource "aws_s3_object" "model" {
  bucket      = aws_s3_bucket.models.id
  key         = "models/hybrid_recommender.pkl"
  source      = "${path.module}/../artifacts/hybrid_recommender.pkl"
  source_hash = filemd5("${path.module}/../artifacts/hybrid_recommender.pkl")
  content_type = "application/octet-stream"
}

resource "aws_s3_object" "metrics" {
  bucket      = aws_s3_bucket.models.id
  key         = "models/metrics.json"
  source      = "${path.module}/../artifacts/metrics.json"
  source_hash = filemd5("${path.module}/../artifacts/metrics.json")
  content_type = "application/json"
}

resource "aws_s3_object" "lambda_layer" {
  bucket       = aws_s3_bucket.models.id
  key          = "deployments/python-dependencies.zip"
  source       = "${path.module}/.build/python-dependencies.zip"
  source_hash  = filemd5("${path.module}/.build/python-dependencies.zip")
  content_type = "application/zip"
}

resource "aws_s3_bucket_lifecycle_configuration" "models" {
  bucket = aws_s3_bucket.models.id

  rule {
    id     = "expire-noncurrent-artifact-versions"
    status = "Enabled"

    filter {}

    noncurrent_version_expiration {
      noncurrent_days = 30
    }

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
}
