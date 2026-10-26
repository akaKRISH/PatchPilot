# PatchPilot Secure Sandbox Image (Python MVP)
# Pinned slim base image
FROM python:3.13-slim

# Create non-root unprivileged execution user
RUN groupadd -g 10001 sandbox && \
    useradd -u 10001 -g sandbox -m -s /bin/bash sandboxuser

# Install pinned Python testing dependencies
RUN pip install --no-cache-dir \
    pytest==8.3.4

# Set up bounded working directory
WORKDIR /workspace
ENV PYTHONPATH=/workspace

# Switch to non-root user
USER sandboxuser

# Default entrypoint
CMD ["python", "-m", "pytest", "-v"]
