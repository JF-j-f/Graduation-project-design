FROM node:lts-alpine AS builder

WORKDIR /src

COPY package.json webpack.config.js .swcrc ./
COPY src ./src

RUN npm install \
    && npm run build

FROM node:lts-alpine

RUN set -ex \
    && mkdir /app \
    && apk add --no-cache python3 youtube-dl \
    && wget https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp -O /usr/local/bin/yt-dlp \
    && chmod a+rx /usr/local/bin/yt-dlp \
    && printf '%s\n%s\n' '--cache-dir /var/cache/yt-dlp' '--js-runtimes node:/usr/local/bin/node' > /etc/yt-dlp.conf

COPY --from=builder /src/precompiled/* /app/
COPY ./*.crt /app/
COPY ./*.key /app/

ENV SIGN_CERT=/app/server.crt
ENV SIGN_KEY=/app/server.key
ENV NODE_ENV=production

WORKDIR /app

EXPOSE 8080 8081

ENTRYPOINT ["node", "app.js"]
