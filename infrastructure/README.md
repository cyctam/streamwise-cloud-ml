# AWS Infrastructure

Terraform provisions the serverless API boundary for the Streamwise application.

## Resources

- Private S3 bucket with versioning and server-side encryption for the trained model and evaluation report.
- AWS Lambda function running the FastAPI application through Mangum.
- Lambda dependency layer built for Python 3.12 on Linux x86_64.
- API Gateway REST API using Lambda proxy integration for the root and all application routes.
- Dedicated Lambda execution role with read-only access to the two model objects.
- CloudWatch log group with configurable retention and API Gateway throttling.

The benchmark CSV files and API source are included in the Lambda function package. The model pickle and metrics report are uploaded to S3 by Terraform and downloaded by the Lambda application during cold start.

## Deployment prerequisites

From the repository root, train or verify the model and build the Lambda assets:

```bash
python -m backend.ml.train
python scripts/package_lambda.py
```

The packaging script defaults to the official AWS Lambda Python 3.12 container image so native wheels match the Lambda runtime. It requires Docker and network access to the Python package index. The script removes package tests and bytecode, checks the 250 MiB uncompressed Lambda limit, and writes the function and dependency layer ZIPs to `infrastructure/.build/`. These generated assets are intentionally excluded from Git. Use `--build-method pip` only when building from a compatible Linux x86_64 environment.

Then:

```bash
cd infrastructure
terraform init
terraform validate
terraform plan
terraform apply
```

Set `cors_origins` to the exact frontend origin for a public deployment. The default `*` is only intended for initial testing with the synthetic benchmark. Review AWS costs before applying. The model bucket keeps noncurrent versions for 30 days; use `terraform destroy -var='force_destroy_bucket=true'` only when you intentionally want Terraform to remove every version in that bucket.

## State and secrets

Terraform uses local state by default. Configure a remote state backend with locking before collaborating or using this in a shared environment. AWS credentials must be provided through the standard AWS credential chain or an approved CI identity; credentials must never be stored in `.tfvars` or committed to Git.
