# Frontend image: build the SPA with a locked install, serve it with an
# unprivileged Nginx that proxies /api to the API service.

FROM oven/bun:1.3 AS builder

WORKDIR /app

# Locked install from the committed lockfile.
COPY package.json bun.lock ./
RUN bun install --frozen-lockfile

COPY . .
# The Vite build runs under Node to avoid a Bun/Rolldown server crash seen in
# some environments; the type check still runs via the project's scripts.
RUN bun run typecheck && node ./node_modules/vite/bin/vite.js build


FROM nginxinc/nginx-unprivileged:1.27-alpine AS runtime

# Unprivileged Nginx listens on 8080 as a non-root user by default.
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 8080
