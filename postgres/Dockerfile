FROM postgres:15-alpine

RUN apk add --no-cache openssl

COPY init-ssl.sh /docker-entrypoint-initdb.d/init-ssl.sh
RUN chmod +x /docker-entrypoint-initdb.d/init-ssl.sh
