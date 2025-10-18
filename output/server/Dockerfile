# Build stage
FROM node:18-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
# Assuming a build step for transpilation (e.g., TypeScript to JavaScript).
# If not needed, you can comment this line out.
RUN npm run build

# Production stage
FROM node:18-alpine
# Create a non-root user for enhanced security
RUN addgroup -g 1001 -S nodejs && adduser -S nodejs -u 1001 nodejs
WORKDIR /app
COPY package*.json ./
# Install only production dependencies
RUN npm ci --only=production
# Copy built artifacts from the builder stage. Assumes 'npm run build' creates a 'dist' directory.
COPY --from=builder /app/dist ./dist
# If no build step was used, copy all source files directly (comment out previous line and uncomment this one):
# COPY --from=builder /app .

# Set proper ownership for the application directory
RUN chown -R nodejs:nodejs /app
# Switch to the non-root user
USER nodejs
EXPOSE 4000
# Health check: Assumes your Node.js app exposes a /health endpoint
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD wget --quiet --tries=1 --spider http://localhost:4000/health || exit 1
# Default start command for the application. Adjust if your entry file is different.
CMD ["node", "dist/index.js"]