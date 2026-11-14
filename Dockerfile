# Build the React application independently from the Python runtime.
FROM node:22-alpine AS frontend-build
WORKDIR /workspace
COPY frontend/package.json ./package.json
RUN npm install --no-audit --no-fund
COPY frontend/ ./
ARG VITE_API_URL=
ENV VITE_API_URL=${VITE_API_URL}
RUN npm run build

FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DATA_DIR=/app/data/raw \
    ARTIFACT_DIR=/app/artifacts
WORKDIR /app

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt \
    && useradd --system --uid 10001 --create-home app

COPY backend/ ./backend/
COPY data/raw/ ./data/raw/
COPY artifacts/ ./artifacts/
COPY dataset/ ./dataset/
# data/ and artifacts/ are gitignored, so build them when the checkout does not have them.
RUN if [ ! -f data/raw/user_interactions.csv ]; then python dataset/generate.py --output data/raw; fi \
    && if [ ! -f artifacts/hybrid_recommender.pkl ]; then python -m backend.ml.train; fi
COPY --from=frontend-build /workspace/dist ./frontend/dist

RUN chown -R app:app /app
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import os; from urllib.request import urlopen; urlopen('http://127.0.0.1:' + os.getenv('PORT', '8000') + '/readyz', timeout=3)"

# Hosting platforms such as Render inject PORT; default to 8000 locally.
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
