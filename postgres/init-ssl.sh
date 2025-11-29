set -e

SSL_DIR="$PGDATA/ssl"
mkdir -p "$SSL_DIR"
chown postgres:postgres "$SSL_DIR"
chmod 700 "$SSL_DIR"
openssl req -new -x509 -days 3650 -nodes \
  -text -out "$SSL_DIR/server.crt" \
  -keyout "$SSL_DIR/server.key" \
  -subj "/CN=postgres"

chown postgres:postgres "$SSL_DIR/server.crt" "$SSL_DIR/server.key"
chmod 600 "$SSL_DIR/server.key"

echo "ssl = on" >> "$PGDATA/postgresql.conf"
echo "ssl_cert_file = 'ssl/server.crt'" >> "$PGDATA/postgresql.conf"
echo "ssl_key_file  = 'ssl/server.key'" >> "$PGDATA/postgresql.conf"

echo "# FORCE TLS ONLY" >> "$PGDATA/pg_hba.conf"
echo "hostssl all all 0.0.0.0/0 md5" >> "$PGDATA/pg_hba.conf"
echo "hostssl all all ::0/0 md5"     >> "$PGDATA/pg_hba.conf"

sed -i '/^host /d' "$PGDATA/pg_hba.conf"

echo "TLS-only policy applied to pg_hba.conf"
