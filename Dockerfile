# Stage 1: Build & Install Dependencies
FROM node:20-slim AS builder

WORKDIR /app

# Install build dependencies for sqlite3
RUN apt-get update && apt-get install -y python3 make g++ && rm -rf /var/lib/apt/lists/*

# Copy package files
COPY package.json ./

# Install dependencies (including native sqlite3 build)
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

# Create RAM disk directory with correct ownership
RUN mkdir -p /app/ram_disk && chown -R cascade:cascade /app/ram_disk

# Set ownership of app directory
RUN chown -R cascade:cascade /app

# Environment variables
ENV NODE_ENV=production
ENV CASCADE_DB_PATH=/data/cascade/cascade.db
ENV CASCADE_RAM_PATH=/app/ram_disk
# Note: In Docker, RAM disk is usually just a folder unless tmpfs is mounted

# Expose StdIO (MCP uses StdIO by default, but if you add HTTP later, expose port here)
# EXPOSE 3000

# Healthcheck (Optional - hard for StdIO apps)

# Switch to non-root user
USER cascade

# Entrypoint
CMD ["node", "server/index.js"]
