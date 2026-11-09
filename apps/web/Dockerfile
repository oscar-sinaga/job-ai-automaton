FROM node:24-slim AS build
WORKDIR /app
COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci --ignore-scripts
COPY apps/web ./
ARG OSCAR_BASE_PATH=
ENV OSCAR_BASE_PATH=$OSCAR_BASE_PATH
RUN npm run build

FROM node:24-slim
WORKDIR /app
ENV NODE_ENV=production
COPY --from=build /app/build ./build
COPY --from=build /app/package.json /app/package-lock.json ./
RUN npm ci --omit=dev --ignore-scripts
COPY --chmod=0555 apps/web/healthcheck.sh /usr/local/bin/oscar-web-healthcheck
CMD ["node", "build"]
