# syntax=docker.io/docker/dockerfile:1

FROM node:20-alpine AS base

# Build-time public env vars that must be embedded into the Next.js client bundle
ARG NEXT_PUBLIC_API_BASE_URL
ARG NEXT_PUBLIC_AUTH0_AUDIENCE
ARG NEXT_PUBLIC_AUTH0_SCOPE
ARG NEXT_PUBLIC_PROFILE_ROUTE
ARG NEXT_PUBLIC_ACCESS_TOKEN_ROUTE
ARG NEXT_PUBLIC_REVIEW_STYLE_ENABLED
ARG NEXT_PUBLIC_REVIEW_COHESION_ENABLED
ARG NEXT_PUBLIC_REVIEW_SUMMARY_ENABLED

# Install dependencies only when needed
FROM base AS deps
# Check https://github.com/nodejs/docker-node/tree/b4117f9333da4138b03a546ec926ef50a31506c3#nodealpine to understand why libc6-compat might be needed.
RUN apk add --no-cache libc6-compat
WORKDIR /app

# Copy only dependency manifests for better caching
COPY ui/package.json ./package.json
COPY ui/package-lock.json ./package-lock.json

# Install dependencies based on the preferred package manager
RUN \
  if [ -f yarn.lock ]; then yarn --frozen-lockfile; \
  elif [ -f package-lock.json ]; then npm ci; \
  elif [ -f pnpm-lock.yaml ]; then corepack enable pnpm && pnpm i --frozen-lockfile; \
  else echo "Lockfile not found." && exit 1; \
  fi


# Rebuild the source code only when needed
FROM base AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY ui/. ./

# Expose build args to Next.js so client bundle gets correct public env values
ARG NEXT_PUBLIC_API_BASE_URL
ARG NEXT_PUBLIC_AUTH0_AUDIENCE
ARG NEXT_PUBLIC_AUTH0_SCOPE
ARG NEXT_PUBLIC_PROFILE_ROUTE
ARG NEXT_PUBLIC_ACCESS_TOKEN_ROUTE
ARG NEXT_PUBLIC_REVIEW_STYLE_ENABLED
ARG NEXT_PUBLIC_REVIEW_COHESION_ENABLED
ARG NEXT_PUBLIC_REVIEW_SUMMARY_ENABLED
ENV NEXT_PUBLIC_API_BASE_URL=${NEXT_PUBLIC_API_BASE_URL}
ENV NEXT_PUBLIC_AUTH0_AUDIENCE=${NEXT_PUBLIC_AUTH0_AUDIENCE}
ENV NEXT_PUBLIC_AUTH0_SCOPE=${NEXT_PUBLIC_AUTH0_SCOPE}
ENV NEXT_PUBLIC_PROFILE_ROUTE=${NEXT_PUBLIC_PROFILE_ROUTE}
ENV NEXT_PUBLIC_ACCESS_TOKEN_ROUTE=${NEXT_PUBLIC_ACCESS_TOKEN_ROUTE}
ENV NEXT_PUBLIC_REVIEW_STYLE_ENABLED=${NEXT_PUBLIC_REVIEW_STYLE_ENABLED}
ENV NEXT_PUBLIC_REVIEW_COHESION_ENABLED=${NEXT_PUBLIC_REVIEW_COHESION_ENABLED}
ENV NEXT_PUBLIC_REVIEW_SUMMARY_ENABLED=${NEXT_PUBLIC_REVIEW_SUMMARY_ENABLED}

# Next.js collects completely anonymous telemetry data about general usage.
# Learn more here: https://nextjs.org/telemetry
# Uncomment the following line in case you want to disable telemetry during the build.
# ENV NEXT_TELEMETRY_DISABLED=1

RUN \
  if [ -f yarn.lock ]; then yarn run build; \
  elif [ -f package-lock.json ]; then npm install && npm run build; \
  elif [ -f pnpm-lock.yaml ]; then corepack enable pnpm && pnpm run build; \
  else echo "Lockfile not found." && exit 1; \
  fi

# Production image, copy all the files and run next
FROM base AS runner
WORKDIR /app

ENV NODE_ENV=production
# Uncomment the following line in case you want to disable telemetry during runtime.
# ENV NEXT_TELEMETRY_DISABLED=1

RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

COPY --from=builder /app/public ./public

# Automatically leverage output traces to reduce image size
# https://nextjs.org/docs/advanced-features/output-file-tracing
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

EXPOSE 3000

ENV PORT=3000

# server.js is created by next build from the standalone output
# https://nextjs.org/docs/pages/api-reference/config/next-config-js/output
ENV HOSTNAME="0.0.0.0"
CMD ["node", "server.js"]
