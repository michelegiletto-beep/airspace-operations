FROM node:22-bookworm-slim@sha256:de170b39439eb0e5a3444ad7d60b015614a381e10fecae2e30ec9e735122f38d AS interface
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json frontend/.npmrc ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.13-slim-bookworm@sha256:93498f36dc7e24ef233bfdf6cc17d4b8bd32d94ee737143e906460d5f5a914c5 AS service
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app/backend AIRSPACE_RUNTIME=/data
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir uv==0.11.23 && uv export --locked --no-dev --no-emit-project --format requirements-txt --output-file /tmp/requirements.txt && pip install --no-cache-dir --require-hashes -r /tmp/requirements.txt
COPY backend/ backend/
COPY sources/ sources/
COPY scripts/prepare_corpus.py scripts/prepare_corpus.py
RUN python scripts/prepare_corpus.py
COPY capabilities.json ./
COPY --from=interface /build/frontend/dist frontend/dist/
RUN useradd --uid 10001 --create-home airspace && mkdir /data && chown airspace:airspace /data
USER 10001:10001
EXPOSE 8787
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8787/api/v1/health',timeout=4)"
CMD ["python", "-m", "airspace.cli", "serve", "--host", "0.0.0.0", "--port", "8787"]
