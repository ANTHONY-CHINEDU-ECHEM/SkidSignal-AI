FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
COPY config ./config
COPY knowledge ./knowledge
RUN pip install --no-cache-dir .
# Mount a volume with processed data and the index at /app/data, or run the pipeline inside the container.
ENV SKIDSIGNAL_HOME=/app
EXPOSE 8000
CMD ["uvicorn", "skidsignal.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
