"""Adapt the FastAPI application to AWS Lambda + API Gateway."""
from mangum import Mangum

from backend.main import app

handler = Mangum(app, lifespan="off")
