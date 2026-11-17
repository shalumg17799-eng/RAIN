# Ultra for RAIN (the new UI), wired to the RAIN v0.4 backend: Vite build served by nginx, with /api and
# /health proxied to the backend service. Vite bakes env at BUILD time: the ENV lines below override any
# .env.local in the context (process env wins in Vite), forcing the Ultra API client into http mode against
# the same-origin path that nginx proxies to the backend's /api/v4/ui2 (rain-api/ui2_v4.py). The data boot
# (GET /api/v4/ui2/data), the persona queries (/api/v4/queries) and the write-back (/api/v4/flow) use the
# same origin. Vite 8 needs Node 22.12 or later.
FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
ENV VITE_ULTRA_API_MODE=http
ENV VITE_ULTRA_API_BASE=/api/v4/ui2
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
