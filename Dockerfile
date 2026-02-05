# Use official Python runtime as base image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies required by some Python packages
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (for better Docker layer caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Create .streamlit directory for config
RUN mkdir -p .streamlit

# Create streamlit config
RUN echo "[server]\nheadless = true\nport = 8501\nenableCORS = false\n[client]\ntoolbarMode = \"minimal\"" > .streamlit/config.toml

# Expose port
EXPOSE 8501

# Health check
HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health || exit 1

# Run Streamlit app
CMD ["streamlit", "run", "credit_decision_ui.py", "--logger.level=info"]
