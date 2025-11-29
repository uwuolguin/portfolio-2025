FROM postgres:15-alpine
RUN apk add --no-cache openssl
COPY init-ssl.sh /docker-entrypoint-initdb.d/01-init-ssl.sh
RUN chmod 755 /docker-entrypoint-initdb.d/01-init-ssl.sh
