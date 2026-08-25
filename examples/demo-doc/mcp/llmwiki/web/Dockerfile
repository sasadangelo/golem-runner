# Dockerfile for the llmwiki web UI running in LOCAL mode.
#
# Built from the upstream web/ directory of the llmwiki project:
#   /Users/sasadangelo/github.com/lucasastorian/llmwiki/web
#
# NEXT_PUBLIC_MODE=local disables Supabase auth and enables the local
# upload endpoint.  No NEXT_PUBLIC_SUPABASE_* variables are needed.

FROM node:22-alpine AS builder
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# Bake the cluster-internal URLs at build time so Next.js can inline them.
# The API URL is accessed from the browser (via NodePort / port-forward),
# so it uses localhost:8000, overridable with --build-arg.
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ARG NEXT_PUBLIC_MCP_URL=http://localhost:8080/mcp

ENV NEXT_PUBLIC_MODE=local \
    NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL} \
    NEXT_PUBLIC_MCP_URL=${NEXT_PUBLIC_MCP_URL}

RUN npm run build

FROM node:22-alpine
WORKDIR /app
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public
EXPOSE 3000
CMD ["node", "server.js"]
