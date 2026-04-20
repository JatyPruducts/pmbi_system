FROM node:20-alpine AS frontend_builder
WORKDIR /app
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM nginx:1.25-alpine
COPY infra/nginx/default.conf /etc/nginx/conf.d/default.conf
COPY --from=frontend_builder /app/dist /usr/share/nginx/html
