FROM node:22-alpine AS base
RUN corepack enable
WORKDIR /app
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile
COPY . .

# Desarrollo: docker-compose usa este target (next dev con recarga en caliente).
FROM base AS dev
EXPOSE 3000
CMD ["pnpm", "dev", "--hostname", "0.0.0.0", "--port", "3000"]

# Producción (Render): NEXT_PUBLIC_API_URL se incrusta en el bundle al compilar,
# por eso debe llegar como argumento de build.
FROM base AS prod
ARG NEXT_PUBLIC_API_URL
ARG INTERNAL_API_URL
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL \
    INTERNAL_API_URL=$INTERNAL_API_URL \
    NODE_ENV=production
RUN pnpm build
EXPOSE 3000
CMD ["sh", "-c", "pnpm start --hostname 0.0.0.0 --port ${PORT:-3000}"]
