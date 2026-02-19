# Stage 1: Build & Install Dependencies
FROM node:20-slim AS builder

WORKDIR /app

# better-sqlite3 ships prebuilt binaries for most platforms (including ARM64)
# Build tools only needed as fallback if no prebuilt binary exists
RUN apt-get update && apt-get install -y python3 make g++ && rm -rf /var/lib/apt/lists/*

# Copy package files
COPY package.json ./

# Install dependencies (better-sqlite3 with prebuilt binaries)
RUN npm install --production

# Copy source code
COPY . .

# Stage 2: Production Runner
FROM node:20-slim AS runner

WORKDIR /app

# Create non-root user for security (UID 1001 to avoid conflict with node user at 1000)
RUN useradd -m -u 1001 cascade

# Create data directory for persistence with correct ownership
RUN mkdir -p /data/cascade && chown -R cascade:cascade /data/cascade

# Copy built node_modules and source from builder
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/server ./server
COPY --from=builder /app/ram_disk_manager ./ram_disk_manager
COPY --from=builder /app/package.json ./

# Create RAM disk directory with correct ownership (matches docker-compose tmpfs mount at /ram_disk)
RUN mkdir -p /ram_disk && chown -R cascade:cascade /ram_disk

# Set ownership of app directory
RUN chown -R cascade:cascade /app

# Environment variables
ENV NODE_ENV=production
ENV CASCADE_DB_PATH=/data/cascade
ENV CASCADE_RAM_PATH=/ram_disk
# Note: docker-compose mounts tmpfs at /ram_disk. Without tmpfs, this is a regular directory.

# Expose StdIO (MCP uses StdIO by default, but if you add HTTP later, expose port here)
# EXPOSE 3000

# Health check - verifies at least one SQLite database is accessible and responds
# Runs every 30s, gives 10s for startup, retries 3 times before marking unhealthy
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
  CMD ["node", "server/healthcheck.js"]

# Switch to non-root user
USER cascade

# Entrypoint
CMD ["node", "server/index.js"]
