# Stage 1: Build & Install Dependencies
FROM node:20-alpine AS builder

WORKDIR /app

# Install build dependencies for sqlite3 (python3, make, g++)
RUN apk add --no-cache python3 make g++

# Copy package files
COPY package.json ./

# Install dependencies (including native sqlite3 build)
RUN npm install --production

# Copy source code
COPY . .

# Stage 2: Production Runner
FROM node:20-alpine AS runner

WORKDIR /app

# Install runtime dependencies for sqlite3
RUN apk add --no-cache libstdc++

# Create data directory for persistence
RUN mkdir -p /data/cascade

# Copy built node_modules and source from builder
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/server ./server
COPY --from=builder /app/package.json ./

# Environment variables
ENV NODE_ENV=production
ENV CASCADE_DB_PATH=/data/cascade/cascade.db

# Entrypoint
CMD ["node", "server/index.js"]
