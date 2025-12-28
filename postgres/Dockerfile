FROM postgres:15-alpine

RUN apk add --no-cache \
    openssl \
    dos2unix \
    postgresql15-pg-cron

COPY init-ssl.sh /docker-entrypoint-initdb.d/01-init-ssl.sh
RUN dos2unix /docker-entrypoint-initdb.d/01-init-ssl.sh \
    && chmod 755 /docker-entrypoint-initdb.d/01-init-ssl.sh

COPY init-user.sh /docker-entrypoint-initdb.d/02-init-user.sh
RUN dos2unix /docker-entrypoint-initdb.d/02-init-user.sh \
    && chmod 755 /docker-entrypoint-initdb.d/02-init-user.sh
