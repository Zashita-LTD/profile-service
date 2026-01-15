FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir .

# Copy source code
COPY src/ src/

# Set Python path
ENV PYTHONPATH=/app/src

# Expose port
EXPOSE 8002

# Run the application
CMD ["uvicorn", "profile_service.main:app", "--host", "0.0.0.0", "--port", "8002"]
