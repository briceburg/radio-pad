FROM node:22-alpine AS base

WORKDIR /app
COPY package*.json ./
RUN npm ci

FROM base AS dev
HEALTHCHECK --interval=2s --timeout=2s --start-period=3s --retries=5 \
  CMD wget --spider -q http://127.0.0.1:5173/ || exit 1
CMD ["npm", "run", "start", "--", "--host", "0.0.0.0"]

FROM base AS builder
COPY . .
RUN npm run build

FROM nginx:alpine AS prod
# Copy built static files from the builder stage to Nginx's default public dir
COPY --from=builder /app/dist /usr/share/nginx/html
# Inform Docker that the container listens on the standard HTTP port
EXPOSE 80

HEALTHCHECK --interval=2s --timeout=2s --start-period=3s --retries=5 \
  CMD wget --spider -q http://127.0.0.1/ || exit 1
  
USER nginx
CMD ["nginx", "-g", "daemon off;"]
