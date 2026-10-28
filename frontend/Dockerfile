# Production build of the Next.js frontend (used by docker-compose.yml; Vercel builds it itself).
FROM node:22-slim AS build
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
# the engagement extras (src/lib/engagement.ts) are compiled in or out; off unless asked for
ARG NEXT_PUBLIC_ENGAGEMENT_UI=false
ENV NEXT_PUBLIC_ENGAGEMENT_UI=$NEXT_PUBLIC_ENGAGEMENT_UI
RUN npm run build && npm prune --omit=dev

FROM node:22-slim AS runner
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1
# The browser calls this server, which forwards API calls (src/app/api/[...path]/route.ts) to
# API_URL, read at run time. Set PROXY_SECRET too when the API has one.
ENV API_URL=http://localhost:8000
COPY --from=build --chown=node:node /app/package.json /app/next.config.ts ./
COPY --from=build --chown=node:node /app/node_modules ./node_modules
COPY --from=build --chown=node:node /app/.next ./.next
COPY --from=build --chown=node:node /app/public ./public
USER node
EXPOSE 3000
CMD ["node_modules/.bin/next", "start", "-p", "3000"]
