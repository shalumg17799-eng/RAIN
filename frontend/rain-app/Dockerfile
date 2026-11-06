# The RAIN v0.3 frontend (Ultra build): Vite build served by nginx, with /api and /health
# proxied to the backend service. Vite bakes env at BUILD time: the ENV lines below override
# any .env.local in the context (process env wins in Vite), forcing the Ultra API client into
# http mode against the same-origin path that nginx proxies to the backend's /api/v3/ui.
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
ENV VITE_ULTRA_API_MODE=http
ENV VITE_ULTRA_API_BASE=/api/v3/ui
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
