# Build stage
FROM node:18-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

# Production stage
FROM nginx:alpine
# A custom nginx.conf is expected to be in the client directory.
# It should be configured to serve the React app and handle routing.
# Example: COPY nginx.conf /etc/nginx/nginx.conf
# If no custom config is provided, a minimal default one is generated.
RUN echo "events { worker_connections 1024; }" > /etc/nginx/nginx.conf \
    && echo "http { include /etc/nginx/mime.types; default_type application/octet-stream;" >> /etc/nginx/nginx.conf \
    && echo "server { listen 80; location / { root /usr/share/nginx/html; index index.html; try_files \$uri \$uri/ /index.html; } }" >> /etc/nginx/nginx.conf \
    && echo "}" >> /etc/nginx/nginx.conf

COPY --from=builder /app/build /usr/share/nginx/html
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD wget --quiet --tries=1 --spider http://localhost:80 || exit 1
CMD ["nginx", "-g", "daemon off;"]