# SSL Setup with Let's Encrypt + Certbot (k3s)

> **When to use this guide:** This guide requires a clean droplet — nothing running on port 80.
> If you cannot afford to reset what is currently deployed, do not use this guide.

---

## Prerequisites

- DigitalOcean droplet with k3s installed, nothing else running
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

```bash
sudo certbot certonly --standalone \
  -d yourdomain.com \
  -d www.yourdomain.com
```

---

## Step 4 — Make Certs Accessible to Your Deploy User

Certbot saves certs as root. Copy them to your deploy user's home directory:

```bash
mkdir -p /home/deploy/certs
sudo cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem /home/deploy/certs/
sudo cp /etc/letsencrypt/live/yourdomain.com/privkey.pem /home/deploy/certs/
sudo chown -R deploy:deploy /home/deploy/certs/
```

---

## Step 5 — Deploy the App

The TLS secret is in the cluster. Run your normal deploy script:

```bash
./deploy-k3s-local.sh
```

---

## Step 7 — Code Changes Required

This step documents every file that must change when moving to HTTPS and flipping
`DEBUG=false`. There are three areas: nginx, the configmap, and the deploy script.
The backend source files are also reviewed — most need no changes, just an
explanation of what their existing conditional logic does in production mode.

---

### 7.1 — `k8s/10-nginx.yaml`

Replace the entire file with the provided `10-nginx.yaml`. Three things changed:

**ConfigMap** — The single `server` block is replaced with two. The HTTP server
(port 80) now only handles Let's Encrypt ACME challenge paths and redirects
everything else to HTTPS with a 301. The HTTPS server (port 443) has TLS
configured and contains every location block that was previously in the HTTP
server, unchanged.

The certs are read from `/etc/nginx/certs/tls.crt` and `tls.key` — that path is
where the `tls-certs` volume is mounted (see Deployment below).

**Service** — Port 443 added alongside port 80.

**Deployment** — `containerPort: 443` added. A second `volumeMount` added at
`/etc/nginx/certs` backed by a `tls-certs` volume of type `secret`, pointing at
`tls-secret` (the k8s secret created automatically by the deploy script after the
namespace is applied). This is how nginx gets the cert files on disk — Kubernetes
injects the secret data as files into the container's filesystem at the mount
path.

---

### 7.2 — `k8s/01-configmap.yaml`

Flip `DEBUG` to false:

```yaml
DEBUG: "false"
```

That single change cascades into every conditional block in the backend that
checks `settings.debug` (cookies, HSTS, error detail stripping, HTTPS redirect —
all covered below in 7.4).

---

### 7.3 — `k8s scripts/deploy-k3s-local.sh`

Two values need updating: `API_BASE_URL` and `ALLOWED_ORIGINS` must both use
`https://`. Find these two lines and change them:

```bash
# In the kubectl create secret block, change API_BASE_URL:
--from-literal=API_BASE_URL="https://yourdomain.com" \

# Change the ALLOWED_ORIGINS patch (currently uses http://):
kubectl patch configmap portfolio-config -n portfolio --type merge \
  -p "{\"data\":{\"ALLOWED_ORIGINS\":\"[\\\"https://yourdomain.com\\\",\\\"https://www.yourdomain.com\\\"]\"}}"
```

---

### 7.4 — Backend source files

These files all have conditional logic on `settings.debug`. When `DEBUG=false`
each one activates behaviour that was previously skipped. No code changes are
required — this section explains what happens automatically.

---

#### `backend/app/middleware/security.py` — `HTTPSRedirectMiddleware`

No change needed. When `settings.debug = False` the middleware redirects plain
HTTP to HTTPS. It also checks `X-Forwarded-Proto: https` and passes through when
the header is present, which is exactly what happens when nginx terminates TLS and
forwards to the backend. Your nginx config already sets this on every proxy block:

```nginx
proxy_set_header X-Forwarded-Proto $scheme;
```

So traffic flow is: browser → nginx (TLS) → backend (plain HTTP with
X-Forwarded-Proto: https) → middleware sees the header → no redirect loop.
**No change required.**

---

#### `backend/app/middleware/security.py` — `SecurityHeadersMiddleware`

No change needed. The `Strict-Transport-Security` header activates automatically:

```python
if not settings.debug:
    response.headers["Strict-Transport-Security"] = (
        "max-age=31536000; includeSubDomains; preload"
    )
```

Once `DEBUG=false`, every response will carry the HSTS header telling browsers to
always use HTTPS for this domain for one year. **No change required.**

---

#### `backend/app/middleware/cors.py`

No change needed. The allowed origins list is injected from the configmap. The
only action is the deploy script change in 7.3 — switching the origin values from
`http://` to `https://`. The middleware code itself is already correct. **No
change required.**

---

#### `backend/app/routers/users.py` — cookie `secure` flag

No change needed. Both cookies already use `secure=not settings.debug`:

```python
response.set_cookie(
    key="access_token",
    ...
    secure=not settings.debug,   # True when debug=False → HTTPS-only cookies
    samesite="lax",
    ...
)
response.set_cookie(
    key="csrf_token",
    ...
    secure=not settings.debug,
    ...
)
```

Same flag is used in logout and delete_me for `delete_cookie`. When `DEBUG=false`
the browser will refuse to send these cookies over plain HTTP — which is what you
want. Note: this also means you cannot test the login flow over plain HTTP after
the switch. **No change required.**

---

#### `backend/app/main.py` — Swagger docs

When `DEBUG=false`, `/docs` and `/redoc` return 404:

```python
docs_url="/docs" if settings.debug else None,
redoc_url="/redoc" if settings.debug else None,
```

The nginx location block for `/docs` will still proxy to the backend, which will
return 404. That is the correct production behaviour. If you want to keep the docs
accessible (useful for a portfolio demo), change both to:

```python
docs_url="/docs",
redoc_url="/redoc",
```

**Decision required, no change strictly needed.**

---

#### `backend/app/utils/exceptions.py` — error response detail

No change needed. Internal error details and tracebacks are already stripped when
`debug=False`:

```python
if settings.debug:
    message = f"Internal error: {type(exc).__name__}: {str(exc)}"
    details = {"error_type": ..., "traceback": ...}
else:
    message = "An unexpected error occurred. Please try again later."
    details = None
```

**No change required.**

---

#### `backend/app/config.py` — `debug` default

The class default is `debug: bool = True`. In production this is overridden by the
environment variable injected from the configmap (`DEBUG=false`). As long as the
configmap has `DEBUG: "false"`, no code change is needed here. **No change
required.**

---

### 7.5 — Summary table

| File | Change required | What changes |
|---|---|---|
| `k8s/10-nginx.yaml` ConfigMap | **Yes** | HTTP redirect server block + HTTPS server block with TLS |
| `k8s/10-nginx.yaml` Service | **Yes** | Add port 443 |
| `k8s/10-nginx.yaml` Deployment | **Yes** | Add container port 443, mount `tls-secret` volume |
| `k8s/01-configmap.yaml` | **Yes** | `DEBUG: "false"` |
| `deploy-k3s-local.sh` | **Yes** | `API_BASE_URL` and `ALLOWED_ORIGINS` use `https://` |
| `middleware/security.py` | **Yes** | Exempt health endpoints from HTTPS redirect — k8s probes hit backend directly over HTTP and would loop without this |
| `middleware/cors.py` | No | Origins driven by configmap value — change is in deploy script |
| `routers/users.py` cookies | No | `secure=not settings.debug` already correct |
| `main.py` docs | Optional | Docs are disabled when `debug=false` — change if you want them on |
| `utils/exceptions.py` | No | Detail stripping already conditional on `debug` |
| `app/config.py` | No | Default overridden by configmap env var |

---

## Step 7 — Auto-Renewal

Certs expire every 90 days. This cron job renews them automatically.

### Why user context matters here

Three things in this job require elevated privileges:
- `certbot renew` — must run as root
- Reading `/etc/letsencrypt/live/` — directory is root-owned, unreadable by other users
- `cp` from that directory — same reason

`kubectl` commands do **not** need root — they run fine as the deploy user as long as the kubeconfig is reachable.

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

0 3 * * * certbot renew --quiet && cp /etc/letsencrypt/live/testproveoportfolio.xyz/fullchain.pem /home/deploy/certs/ && cp /etc/letsencrypt/live/testproveoportfolio.xyz/privkey.pem /home/deploy/certs/ && chown -R deploy:deploy /home/deploy/certs/ && KUBECONFIG=/home/deploy/.kube/config kubectl create secret tls tls-secret --cert=/home/deploy/certs/fullchain.pem --key=/home/deploy/certs/privkey.pem -n portfolio --dry-run=client -o yaml | KUBECONFIG=/home/deploy/.kube/config kubectl apply -f - && KUBECONFIG=/home/deploy/.kube/config kubectl rollout restart deployment nginx -n portfolio


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
sudo cp /etc/letsencrypt/live/testproveoportfolio.xyz/fullchain.pem /home/deploy/certs/ && \
sudo cp /etc/letsencrypt/live/testproveoportfolio.xyz/privkey.pem /home/deploy/certs/ && \
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