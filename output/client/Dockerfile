# Build stage
FROM node:18-alpine AS builder
WORKDIR /app

# Copy dependency files
COPY client/package*.json ./

# Install dependencies
RUN npm ci && \
    npm cache clean --force

# Copy source code
COPY client/. .

# Build application (Vite outputs to /dist)
RUN npm run build

# Production stage
FROM nginx:alpine

# Copy nginx configuration
COPY client/nginx.conf /etc/nginx/nginx.conf

# Copy built application from /dist (VITE)
COPY --from=builder /app/dist /usr/share/nginx/html

# Expose port
EXPOSE 80

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD wget --quiet --tries=1 --spider http://localhost:80 || exit 1

# Start Nginx
CMD ["nginx", "-g", "daemon off;"]