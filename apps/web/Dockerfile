FROM node:22-alpine AS builder

WORKDIR /app

COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci

COPY apps/web ./

ARG VITE_API_BASE=http://127.0.0.1:8000/api/v1
ENV VITE_API_BASE=$VITE_API_BASE

RUN npm run build

FROM nginx:stable-alpine

COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]

