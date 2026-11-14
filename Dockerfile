ARG BUILD_FROM
FROM $BUILD_FROM

# Labels required by HA supervisor
ARG BUILD_ARCH
ARG BUILD_VERSION
LABEL \
    io.hass.version="${BUILD_VERSION}" \
    io.hass.type="addon" \
    io.hass.arch="${BUILD_ARCH}"

# su-exec allows run.sh (root) to drop to a non-root user before exec'ing Python
RUN apk add --no-cache su-exec

# Create a non-root user for the Python process
RUN addgroup -S appgroup && adduser -S -G appgroup appuser

# Avoid .pyc files and ensure stdout/stderr are unbuffered for HA logs
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

# Install uv for lock-based dependency installation
RUN pip3 install --no-cache-dir uv

# Create a non-root application directory
WORKDIR /app

# Copy lockfile and project metadata
COPY pyproject.toml uv.lock README.md ./

# Install pinned dependencies (without the project itself) into a venv
RUN uv sync --frozen --no-dev --no-install-project

# Copy source and install the project (no-deps since deps are already installed)
COPY src/ ./src/
RUN uv sync --frozen --no-dev

# Fix ownership
RUN chown -R appuser:appgroup /app

# Copy and wire up the entrypoint (must run as root so bashio can read /data/options.json)
COPY run.sh /run.sh
RUN chmod a+x /run.sh

CMD ["/run.sh"]
