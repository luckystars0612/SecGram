# Builder stage
FROM debian:bookworm-slim AS builder

WORKDIR /usr/src/filehandler_service

# Install build tools, libarchive, and librabbitmq
RUN apt-get update && apt-get install -y \
    gcc \
    make \
    libarchive-dev \
    librabbitmq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy source files
COPY Makefile .
COPY main.c .

# Build the binary
RUN make

# Runtime stage
FROM debian:bookworm-slim

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    libarchive13 \
    librabbitmq1 \
    && rm -rf /var/lib/apt/lists/*

# Copy the binary from the builder stage
COPY --from=builder /usr/src/filehandler_service/filehandler_service .

# Mount points for input/output (defined in docker-compose.yml)
VOLUME /app/resources
VOLUME /app/extracted

CMD ["./filehandler_service"]