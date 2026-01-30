FROM python:3.13-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install Rust
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"

# Copy requirements (setup.py/pyproject.toml)
COPY pyproject.toml .
COPY README.md .

# Install dependencies
RUN pip install --no-cache-dir .

# Copy application code
COPY . .

# Expose ports
EXPOSE 8080 9090

# Default command
CMD ["python", "scripts/run_node.py", "--mode", "production", "--config", "config/live/production.yaml"]

