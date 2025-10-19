# Build stage
FROM node:18-alpine AS builder
WORKDIR /app

# Copy dependency files
COPY server/package*.json ./

# Install production dependencies only for the final image
RUN npm ci --only=production && \
    npm cache clean --force

# Copy all source code for potential build steps or full access
COPY server/. .

# Production stage
FROM node:18-alpine

# Create non-root user
RUN addgroup -g 1001 -S nodejs && \
    adduser -S nodejs -u 1001

WORKDIR /app

# Copy production dependencies
COPY --from=builder --chown=nodejs:nodejs /app/node_modules ./node_modules

# Copy application files (adjusting based on the actual entry point and structure)
COPY --from=builder --chown=nodejs:nodejs /app/package*.json ./
COPY --from=builder --chown=nodejs:nodejs /app/server.js ./server.js
COPY --from=builder --chown=nodejs:nodejs /app/middleware ./middleware
COPY --from=builder --chown=nodejs:nodejs /app/models ./models
COPY --from=builder --chown=nodejs:nodejs /app/routes ./routes

# Switch to non-root user
USER nodejs

# Expose port
EXPOSE 4000

# Health check (assuming a /health endpoint is available)
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD node -e "require('http').get('http://localhost:4000/health', (r) => {process.exit(r.statusCode === 200 ? 0 : 1)})" || exit 1

# Start application
CMD ["node", "server.js"]