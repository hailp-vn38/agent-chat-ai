# --------- Builder Stage ---------
FROM node:20-alpine AS builder

# Accept build arguments
ARG VITE_API_BASE_PATH=/api/v1
ARG VITE_OTA_URL=/api/v1/ota

# Set environment variables for build
ENV VITE_API_BASE_PATH=$VITE_API_BASE_PATH
ENV VITE_OTA_URL=$VITE_OTA_URL

WORKDIR /app

# Copy package files and lock file
COPY package.json package-lock.json ./

# Install dependencies with npm
RUN npm ci

# Copy source code
COPY . .

# Build the application with environment variables
RUN VITE_API_BASE_PATH=$VITE_API_BASE_PATH VITE_OTA_URL=$VITE_OTA_URL npm run build

# --------- Final Stage ---------
FROM nginx:alpine

# Create nginx config for single-page application with best practices
RUN cat > /etc/nginx/conf.d/default.conf <<'EOF'
server {
    listen 3000;
    server_name _;
    root /usr/share/nginx/html;
    index index.html;

    # Enable gzip compression
    gzip on;
    gzip_min_length 1000;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml application/xml+rss;

    # Cache static assets
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # Proxy API requests to backend
    location /api/ {
        proxy_pass http://backend:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }

    # SPA routing - fallback to index.html for all non-file requests
    location / {
        try_files $uri $uri/ /index.html;
        add_header Cache-Control "no-cache";
    }

    # Health check endpoint
    location /health {
        access_log off;
        return 200 "healthy\n";
        add_header Content-Type text/plain;
    }
}
EOF

# Copy built files from builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

# Expose port
EXPOSE 3000

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost:3000/health || exit 1

# Start nginx
CMD ["nginx", "-g", "daemon off;"]
