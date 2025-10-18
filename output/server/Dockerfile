# Build stage
FROM node:18-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
# Assuming a build step for Node.js projects (e.g., TypeScript compilation)
RUN npm run build

# Production stage
FROM node:18-alpine
RUN addgroup -g 1001 -S nodejs && adduser -S nodejs -u 1001
WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production
# Copy build artifacts from the builder stage
COPY --from=builder /app/dist ./dist
COPY --from=builder /app/src ./src
# Copy any other necessary files (e.g., static assets, templates)
COPY . . 
# Ensure only production dependencies are installed and accessible by the non-root user
RUN chown -R nodejs:nodejs /app
USER nodejs
EXPOSE 3000
# Health check for Node.js application, assumes a /health endpoint
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD wget --quiet --tries=1 --spider http://localhost:3000/health || exit 1
CMD ["node", "dist/index.js"]