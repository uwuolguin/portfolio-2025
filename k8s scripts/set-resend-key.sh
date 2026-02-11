#!/bin/bash
set -e

# =============================================================================
# Set Resend API Key - Interactive Script
# Securely adds the Resend API key to .env.secrets
# =============================================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info()    { printf '%b\n' "${BLUE}[INFO]${NC} $1"; }
log_success() { printf '%b\n' "${GREEN}[OK]${NC} $1"; }
log_warn()    { printf '%b\n' "${YELLOW}[WARN]${NC} $1"; }
log_error()   { printf '%b\n' "${RED}[ERROR]${NC} $1"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/.env.secrets"

echo "=================================="
echo "Resend API Key Configuration"
echo "=================================="
echo ""

# Check if .env.secrets already exists
if [ -f "$ENV_FILE" ]; then
    log_warn ".env.secrets already exists"
    echo ""
    echo "Current contents:"
    cat "$ENV_FILE"
    echo ""
    read -p "Do you want to update it? (yes/no): " update_confirm
    if [ "$update_confirm" != "yes" ] && [ "$update_confirm" != "y" ]; then
        echo "Aborted."
        exit 0
    fi
fi

echo ""
log_info "Get your Resend API key from: https://resend.com/api-keys"
echo ""
echo "The key should look like: re_xxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
echo ""

# Prompt for API key
read -p "Enter your Resend API key: " resend_key

# Validate format (basic check)
if [[ ! "$resend_key" =~ ^re_[a-zA-Z0-9_]{20,}$ ]]; then
    log_error "Invalid Resend API key format!"
    log_error "Key should start with 're_' followed by alphanumeric characters"
    exit 1
fi

# Create/update .env.secrets
cat > "$ENV_FILE" << EOF
# Local secrets - NEVER commit this file
# Generated: $(date -Iseconds)
RESEND_API_KEY=$resend_key
EOF

chmod 600 "$ENV_FILE"

log_success ".env.secrets created successfully"
echo ""
echo "File location: $ENV_FILE"
echo "Permissions: 600 (owner read/write only)"
echo ""

# Check if key is already in Kubernetes
if command -v kubectl &> /dev/null; then
    if kubectl get secret portfolio-secrets -n portfolio &> /dev/null 2>&1; then
        log_info "Found existing Kubernetes secret"
        echo ""
        read -p "Update Kubernetes secret now? (yes/no): " update_k8s
        
        if [ "$update_k8s" = "yes" ] || [ "$update_k8s" = "y" ]; then
            log_info "Updating Kubernetes secret..."
            
            kubectl patch secret portfolio-secrets -n portfolio --type merge \
              -p '{"data":{"RESEND_API_KEY":"'$(echo -n "$resend_key" | base64)'"}}'
            
            log_success "Secret updated in Kubernetes"
            echo ""
            
            read -p "Restart backend to apply changes? (yes/no): " restart_backend
            if [ "$restart_backend" = "yes" ] || [ "$restart_backend" = "y" ]; then
                kubectl rollout restart deployment backend -n portfolio
                log_success "Backend restarted"
            else
                log_warn "Remember to restart backend manually:"
                echo "  kubectl rollout restart deployment backend -n portfolio"
            fi
        else
            log_info "Skipped Kubernetes update"
            log_info "The key will be used on next deployment"
        fi
    else
        log_info "No existing Kubernetes secret found"
        log_info "The key will be used when you run ./deploy-k3s-local.sh"
    fi
else
    log_warn "kubectl not found - skipping Kubernetes update"
    log_info "The key will be used when you run ./deploy-k3s-local.sh"
fi

echo ""
echo "=================================="
echo "Setup Complete!"
echo "=================================="
echo ""
echo "Next steps:"
echo "  1. If deploying for first time: ./deploy-k3s-local.sh"
echo "  2. If already deployed: kubectl rollout restart deployment backend -n portfolio"
echo ""
echo "To test email verification:"
echo "  1. Sign up a new user via the API"
echo "  2. Check your email for verification link"
echo ""