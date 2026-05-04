FROM python:3.11-slim
WORKDIR /app
RUN pip install uv

# Install deps first for layer caching — rebuild only when pyproject.toml changes
COPY pyproject.toml .
RUN mkdir -p app && touch app/__init__.py && \
    uv pip install --system -e . && \
    rm app/__init__.py

# Copy full source (overwrites the stub above)
COPY . .
RUN mkdir -p workspace

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
