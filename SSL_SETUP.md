# SSL Setup with Let's Encrypt + Certbot (k3s)

> **When to use this guide:** This guide requires a clean droplet — nothing running on port 80.
> If you cannot afford to reset what is currently deployed, do not use this guide.

---

## Prerequisites

- DigitalOcean droplet with k3s installed (Or something equivalent), nothing else running
- Domain DNS configured:
  - **In DigitalOcean:** A records pointing `@` and `www` to your droplet IP
  - **In GoDaddy:** Nameservers set to `ns1.digitalocean.com`, `ns2.digitalocean.com`, `ns3.digitalocean.com`
- DNS propagated — verify before proceeding:

```bash
nslookup yourdomain.com
# Must return your droplet IP before continuing
```

---

## Step 1 — Install Certbot

```bash
sudo apt-get update && sudo apt-get install -y certbot
```

---

## Step 2 — Confirm Port 80 is Free

```bash
sudo ss -tlnp | grep :80
# Must return nothing
```

---

## Step 3 — Get the Certificate

Certbot uses `--standalone` here: it spins up a temporary HTTP server on port 80
to serve the ACME challenge file and prove domain ownership to Let's Encrypt.
This works because port 80 is free at this point.

After the app is deployed, nginx will own port 80 — so standalone would fail on
renewal. Step 4 patches the renewal config to use webroot instead before that
happens.

```bash
sudo certbot certonly --standalone \
  -d yourdomain.com \
  -d www.yourdomain.com
```

---

## Step 4 — Switch Renewal to Webroot

Certbot stores renewal settings in `/etc/letsencrypt/renewal/yourdomain.com.conf`.
It was written with `authenticator = standalone` by the command above. If left
unchanged, every future `certbot renew` will try to bind port 80 — which will fail
once nginx is running.

Patch it now, before deploying anything:

```bash
# Create the directory certbot will write challenge files into.
# Nginx will serve this path via the /.well-known/acme-challenge/ location block.
sudo mkdir -p /var/www/certbot

# Switch the authenticator from standalone to webroot.
sudo sed -i 's/authenticator = standalone/authenticator = webroot/' \
  /etc/letsencrypt/renewal/yourdomain.com.conf

# Add the webroot path so certbot knows where to write the challenge files.
sudo sed -i '/authenticator = webroot/a webroot_path = /var/www/certbot' \
  /etc/letsencrypt/renewal/yourdomain.com.conf
```

Verify the result:

```bash
sudo cat /etc/letsencrypt/renewal/yourdomain.com.conf | grep -E 'authenticator|webroot'
# Expected:
# authenticator = webroot
# webroot_path = /var/www/certbot
```

---

## Step 5 — Make Certs Accessible to Your Deploy User

Certbot saves certs as root. Copy them to your deploy user's home directory:

```bash
mkdir -p /home/deploy/certs
sudo cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem /home/deploy/certs/
sudo cp /etc/letsencrypt/live/yourdomain.com/privkey.pem /home/deploy/certs/
sudo chown -R deploy:deploy /home/deploy/certs/
```

---

## Step 6 — Deploy the App

The TLS secret is in the cluster. Run your normal deploy script:

```bash
./deploy-k3s-local.sh
```

---

## 7 — Required Production Configuration

This section documents the configuration elements that must be present when the
application is deployed with HTTPS enabled and `DEBUG=false`.

The purpose of this section is to describe the required production state.

The required configuration consists of three primary areas:

1. nginx configuration
2. application configuration
3. deployment configuration

The backend source code is also reviewed below. Most files already contain the
necessary production logic and satisfy the requirements without modification.

---

### 7.1 — `k8s/10-nginx.yaml`

The nginx configuration must satisfy the following requirements.

#### ACME challenge endpoint on port 80

The nginx configuration must contain a dedicated ACME challenge location on
port 80 for Let's Encrypt certificate issuance and renewal.

Example:

```nginx
server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        return 301 https://$host$request_uri;
    }
}
```

The ACME endpoint must remain accessible via plain HTTP because Let's Encrypt
validates domain ownership using requests similar to:

```text
http://yourdomain.com/.well-known/acme-challenge/<token>
```

All non-ACME traffic on port 80 must be redirected to HTTPS.

#### ConfigMap requirements

The nginx ConfigMap must contain two server blocks.

##### HTTP server (port 80)

Responsibilities:

* Serve `/.well-known/acme-challenge/`
* Redirect all other requests to HTTPS using HTTP 301

##### HTTPS server (port 443)

Responsibilities:

* Load TLS certificates
* Serve all application traffic
* Preserve all existing proxy locations

TLS certificates must be loaded from:

```text
/etc/nginx/certs/tls.crt
/etc/nginx/certs/tls.key
```

These files must be provided through a Kubernetes Secret mounted into the nginx
container.

#### Service requirements

The Service must expose:

* Port 80
* Port 443

#### Deployment requirements

The nginx Deployment must expose:

```yaml
containerPort: 443
```

The Deployment must include the following volume mounts:

```yaml
volumeMounts:
  - name: nginx-config
    mountPath: /etc/nginx/nginx.conf
    subPath: nginx.conf

  - name: tls-certs
    mountPath: /etc/nginx/certs
    readOnly: true

  - name: acme-challenge
    mountPath: /var/www/certbot
```

The Deployment must include the following volumes:

```yaml
volumes:
  - name: nginx-config
    configMap:
      name: nginx-config

  - name: tls-certs
    secret:
      secretName: tls-secret

  - name: acme-challenge
    hostPath:
      path: /var/www/certbot
      type: DirectoryOrCreate
```

##### Volume purpose

**tls-certs**

Provides nginx access to:

* `tls.crt`
* `tls.key`

from the Kubernetes Secret named `tls-secret`.

**acme-challenge**

Provides a shared filesystem path between:

* certbot running on the host
* nginx running inside Kubernetes

Certbot writes challenge files into:

```text
/var/www/certbot
```

and nginx serves those same files through the mounted volume.

---

### 7.2 — `k8s/01-configmap.yaml`

The production configuration must define:

```yaml
DEBUG: "false"
```

This enables production behaviour throughout the application, including:

* HTTPS-only cookies
* HSTS headers
* Production error handling
* HTTPS redirect enforcement

---

### 7.3 — `k8s/scripts/deploy-k3s-local.sh`

The production deployment configuration must use HTTPS URLs for:

* `API_BASE_URL`
* `ALLOWED_ORIGINS`

Required examples:

```bash
--from-literal=API_BASE_URL="https://yourdomain.com"
```

```bash
kubectl patch configmap portfolio-config -n portfolio --type merge \
  -p "{\"data\":{\"ALLOWED_ORIGINS\":\"[\\\"https://yourdomain.com\\\",\\\"https://www.yourdomain.com\\\"]\"}}"
```

HTTP origins should not be used in the production configuration.

---

### 7.4 — Backend source files

The following files contain production-aware logic controlled by
`settings.debug`.

The listed requirements are already satisfied by the existing implementation
unless otherwise noted.

---

#### `backend/app/middleware/security.py` — `HTTPSRedirectMiddleware`

The application must redirect HTTP requests to HTTPS when `DEBUG=false`.

The middleware must respect:

```text
X-Forwarded-Proto: https
```

which nginx forwards using:

```nginx
proxy_set_header X-Forwarded-Proto $scheme;
```

Expected traffic flow:

```text
Browser
  ↓ HTTPS
nginx
  ↓ HTTP + X-Forwarded-Proto=https
Backend
```

This prevents redirect loops when TLS is terminated by nginx.

---

#### `backend/app/middleware/security.py` — health probe handling

If Kubernetes liveness or readiness probes access the backend directly over
HTTP, health endpoints must be exempt from HTTPS redirection.

Example endpoints:

```text
/health
/livez
/readyz
```

Probe behaviour should be verified before deployment.

---

#### `backend/app/middleware/security.py` — `SecurityHeadersMiddleware`

When `DEBUG=false`, the application must emit the following HSTS header:

```python
if not settings.debug:
    response.headers["Strict-Transport-Security"] = (
        "max-age=31536000; includeSubDomains; preload"
    )
```

This instructs browsers to use HTTPS for future requests.

---

#### `backend/app/middleware/cors.py`

Allowed origins must be supplied through configuration.

Production origins must use HTTPS URLs.

---

#### `backend/app/routers/users.py`

Authentication and CSRF cookies must use secure transmission when
`DEBUG=false`.

Current implementation:

```python
secure=not settings.debug
```

This ensures cookies become HTTPS-only in production.

---

#### `backend/app/main.py`

Swagger documentation is disabled automatically when `DEBUG=false`.

Current behaviour:

```python
docs_url="/docs" if settings.debug else None,
redoc_url="/redoc" if settings.debug else None,
```

If API documentation is intended to remain available in production, documentation
endpoints must be explicitly enabled.

---

#### `backend/app/utils/exceptions.py`

Production error responses must not expose internal exception details or
tracebacks.

The current implementation satisfies this requirement when `DEBUG=false`.

---

#### `backend/app/config.py`

Runtime configuration must provide the `DEBUG` value through environment
configuration.

The ConfigMap-provided value overrides the class default.

---

### 7.5 — Production Configuration Summary

| Component                      | Required Element                     |
| ------------------------------ | ------------------------------------ |
| `k8s/10-nginx.yaml` ConfigMap  | HTTP server on port 80               |
| `k8s/10-nginx.yaml` ConfigMap  | ACME challenge endpoint present      |
| `k8s/10-nginx.yaml` ConfigMap  | HTTP-to-HTTPS redirect present       |
| `k8s/10-nginx.yaml` ConfigMap  | HTTPS server on port 443             |
| `k8s/10-nginx.yaml` ConfigMap  | TLS certificate loading configured   |
| `k8s/10-nginx.yaml` Service    | Port 80 exposed                      |
| `k8s/10-nginx.yaml` Service    | Port 443 exposed                     |
| `k8s/10-nginx.yaml` Deployment | Container port 443 exposed           |
| `k8s/10-nginx.yaml` Deployment | TLS secret mounted                   |
| `k8s/10-nginx.yaml` Deployment | ACME challenge volume mounted        |
| `k8s/01-configmap.yaml`        | `DEBUG=false` defined                |
| `deploy-k3s-local.sh`          | HTTPS URLs configured                |
| `middleware/security.py`       | HTTPS enforcement enabled            |
| `middleware/security.py`       | Health probes handled correctly      |
| `middleware/security.py`       | HSTS enabled                         |
| `middleware/cors.py`           | HTTPS origins configured             |
| `routers/users.py`             | Secure cookies enabled               |
| `main.py`                      | Documentation behaviour defined      |
| `utils/exceptions.py`          | Internal error details suppressed    |
| `app/config.py`                | Runtime DEBUG configuration supplied |

```
## Step 8 — Auto-Renewal

Certs expire every 90 days. This cron job renews them automatically.

`certbot renew` reads `/etc/letsencrypt/renewal/yourdomain.com.conf` which was
patched in Step 4 to use webroot. So no flags are needed here — certbot already
knows to write challenge files to `/var/www/certbot`, which nginx serves via the
`/.well-known/acme-challenge/` location block. No port conflict, no downtime.

### Why user context matters here

Three things in this job require elevated privileges:
- `certbot renew` — must run as root
- Reading `/etc/letsencrypt/live/` — directory is root-owned, unreadable by other users
- `cp` from that directory — same reason

`kubectl` commands do **not** need root — they run fine as the deploy user as long
as the kubeconfig is reachable.

This means you have two options:

---

### Option A — Root's crontab (recommended)

Root owns certbot and the certs, so no `sudo` needed inside the job. The only
catch is that root's cron runs in a bare environment with no `$HOME`, so
`KUBECONFIG` must be set explicitly or kubectl won't find the config.

Open root's crontab:

```bash
sudo crontab -e
```

Add this line:

```cron
0 3 * * * certbot renew --quiet && cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem /home/deploy/certs/ && cp /etc/letsencrypt/live/yourdomain.com/privkey.pem /home/deploy/certs/ && chown -R deploy:deploy /home/deploy/certs/ && KUBECONFIG=/home/deploy/.kube/config kubectl create secret tls tls-secret --cert=/home/deploy/certs/fullchain.pem --key=/home/deploy/certs/privkey.pem -n portfolio --dry-run=client -o yaml | KUBECONFIG=/home/deploy/.kube/config kubectl apply -f - && KUBECONFIG=/home/deploy/.kube/config kubectl rollout restart deployment nginx -n portfolio
```

---

### Option B — Deploy user's crontab

If you prefer the cron to live under the deploy user, the deploy user must have
passwordless sudo for `cp` and `certbot`. This requires editing `/etc/sudoers`
which is a larger security decision. Not recommended unless you have a specific
reason.

---

### Manual one-time run (to test before the cron fires)

Run this as the deploy user to verify the whole chain works:

```bash
sudo cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem /home/deploy/certs/ && \
sudo cp /etc/letsencrypt/live/yourdomain.com/privkey.pem /home/deploy/certs/ && \
kubectl create secret tls tls-secret \
  --cert=/home/deploy/certs/fullchain.pem \
  --key=/home/deploy/certs/privkey.pem \
  -n portfolio --dry-run=client -o yaml | kubectl apply -f - && \
kubectl rollout restart deployment nginx -n portfolio
```

No `chown` needed here — `sudo cp` as the deploy user lands the files owned by
root, but the deploy user can still read them for the `kubectl` step. If you want
deploy to own them add `sudo chown -R deploy:deploy /home/deploy/certs/` after
the copy.

---

## Verify

```bash
# HTTPS works
curl -I https://yourdomain.com
# Should return HTTP/2 200

# HTTP redirects
curl -I http://yourdomain.com
# Should return 301 and Location: https://yourdomain.com/

# HSTS header is present
curl -sI https://yourdomain.com | grep Strict-Transport-Security
# Should return: Strict-Transport-Security: max-age=31536000; includeSubDomains; preload

# Cookies are secure-flagged (check browser DevTools → Application → Cookies)
# access_token and csrf_token should both show Secure: true
```