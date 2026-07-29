# ---------- Base ----------
FROM node:20-alpine AS base
WORKDIR /app

# ---------- Dependencies ----------
FROM base AS deps
COPY package.json package-lock.json* ./
RUN npm ci

# ---------- Development ----------
FROM base AS development
ENV NODE_ENV=development
COPY --from=deps /app/node_modules ./node_modules
COPY . .
EXPOSE 3000
CMD ["npm", "run", "dev"]

# ---------- Build ----------
FROM base AS build
ENV NODE_ENV=production
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

# ---------- Production ----------
FROM base AS production
ENV NODE_ENV=production
COPY --from=build /app/public ./public
COPY --from=build /app/.next/standalone ./
COPY --from=build /app/.next/static ./.next/static
EXPOSE 3000
CMD ["node", "server.js"]
