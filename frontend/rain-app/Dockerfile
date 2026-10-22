# The RAIN frontend: Vite build served by nginx, with /api, /ultra and /health proxied to the
# backend service. Build context is frontend/rain-app. Vite bakes env at BUILD time: .env.local
# (the per-persona VITE_RAIN_KEY_* bearer tokens) is read from the context, and VITE_API_BASE is
# forced empty so every request is same-origin and goes through the nginx proxy.
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
ENV VITE_API_BASE=""
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
