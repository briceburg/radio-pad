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

FROM caddy:alpine AS prod
RUN printf ':80 {\n\troot * /srv\n\ttry_files {path} /index.html\n\tfile_server\n}\n' > /etc/caddy/Caddyfile
COPY --from=builder /app/dist /srv
EXPOSE 80

HEALTHCHECK --interval=2s --timeout=2s --start-period=3s --retries=5 \
  CMD wget --spider -q http://127.0.0.1/ || exit 1
