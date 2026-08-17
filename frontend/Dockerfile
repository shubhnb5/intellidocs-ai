# Multi-stage, unlike the Python services' Dockerfiles: Node/npm and the
# whole source tree are only needed to produce the static bundle, not to
# serve it -- shipping them in the final image would mean a much larger
# image for zero runtime benefit.
FROM node:20-alpine AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# Vite bakes import.meta.env.VITE_* values into the JS bundle at build time,
# not read at container start -- there's no "runtime env var" for a static
# SPA the way a server-rendered app has. That means this must be the
# *browser-reachable* backend URL (e.g. http://localhost:8000), never an
# internal Docker Compose service name like http://backend:8000 -- the
# browser running this bundle isn't on the Compose network and can't resolve
# it. Deploying somewhere other than localhost means rebuilding this image
# with a different build arg, not just changing an env var at runtime.
ARG VITE_API_BASE_URL=http://localhost:8000
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

RUN npm run build

FROM nginx:alpine

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD wget --quiet --spider http://localhost:80/ || exit 1
