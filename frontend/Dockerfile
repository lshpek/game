# --- build ---------------------------------------------------------------
FROM node:22-alpine AS build

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci --no-audit --no-fund

COPY . .
ARG VITE_API_BASE_URL=http://localhost:8000
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build

# --- runtime -------------------------------------------------------------
FROM nginx:1.27-alpine AS runtime

# `listen ${PORT};` in nginx.conf is substituted at container start because the
# platform assigns a random port; nginx itself only expands env vars at runtime
# for a handful of directives, so envsubst is used to bake it in.
ENV PORT=80

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/templates/default.conf.template

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD wget -qO- http://127.0.0.1:${PORT}/ >/dev/null || exit 1

CMD ["nginx", "-g", "daemon off;"]
