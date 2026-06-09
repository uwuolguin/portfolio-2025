# CHANGE TO ROOT USER
sudo su -

# CHANGE TO DEPLOY USER
su - deploy

# NAVIGATE AND SEE EVERYTHING
cd /var/log
ls -lah                                        # all files, human readable sizes, hidden
ls -laht                                       # same but sorted by newest first

# JUICE DIRECTORIES
cd /var/log/pods && ls -lah                    # kubernetes pod logs on disk
cd /var/log/containers && ls -lah              # container logs
cd /var/log/journal && ls -lah                 # systemd binary journal
cd /var/log/apt && ls -lah                     # package install history
cd /var/log/letsencrypt && ls -lah             # cert renewal history
cd /proc && ls -lah                            # every running process
cd /etc && ls -laht | head -20                 # recently modified configs

# READ THE JUICE
tail -f /var/log/syslog                        # live system events
tail -f /var/log/kern.log                      # live kernel events
tail -100 /var/log/auth.log                    # last 100 auth events
cat /var/log/dpkg.log | grep install           # what got installed
cat /var/log/cloud-init-output.log             # what happened on first boot

# SIZES — what is eating disk
du -sh /var/log/*                              # size of each log
du -sh /var/lib/rancher                        # k3s data size
du -sh /var/lib/docker 2>/dev/null             # docker data if present
du -sh /home/*                                 # home directory sizes

# HIDDEN FILES — dot files have config and history
ls -lah /home/deploy/                          # deploy home hidden files
ls -lah /root/                                 # root home hidden files
cat /home/deploy/.bash_history                 # every command typed
cat /home/deploy/.ssh/known_hosts              # servers deploy has SSH'd OUT to (not who can SSH in)
cat /home/deploy/.ssh/authorized_keys          # WHO CAN ACTUALLY SSH IN — the real access control file
cat /home/deploy/.profile                      # login environment
cat /home/deploy/.bashrc                       # shell config

# ETC — the config kingdom
ls -laht /etc | head -30                       # most recently changed configs
cat /etc/passwd                                # all users
cat /etc/group                                 # all groups
cat /etc/sudoers                               # sudo permissions
cat /etc/hosts                                 # local DNS overrides
cat /etc/crontab                               # scheduled tasks
ls -lah /etc/cron.d/                           # drop-in cron jobs
ls -lah /etc/ssh/                              # SSH config
cat /etc/ssh/sshd_config                       # SSH daemon config

# ─── SSH HARDENING — do this on every new server ──────────────────────────────
#
# WHY THIS MATTERS
# -----------------------------------------------------------------------------
# Any public IPv4 address gets scanned by bots within minutes of provisioning.
#
# They continuously attempt:
#   - common usernames
#   - leaked passwords
#   - brute-force attacks
#
# Check how noisy it already is:
#
#   grep "Failed password" /var/log/auth.log | wc -l
#
# Thousands of failed attempts is normal on internet-facing servers.
#
#
# THE REAL FIX
# -----------------------------------------------------------------------------
# Disable password authentication entirely and use SSH public-key auth instead.
#
# With key auth:
#
#   server stores:     PUBLIC key
#   your laptop/PC:    PRIVATE key
#
# The PRIVATE key NEVER leaves your local machine.
#
# Bots can guess passwords forever:
#   it no longer matters because passwords are rejected completely.
#
#
# WHERE TO FIND AUTHORIZED KEYS ON THE DROPLET
# -----------------------------------------------------------------------------
# The authorized_keys file lives in the .ssh directory of the user's home folder.
# To inspect it on the droplet:
#
#   cd ~/.ssh/
#   cat authorized_keys
#
# To inspect it on windows generally the directory is:
#
#   C:\Users\<youruser>\.ssh\
#
# Each line is one public key that is allowed to SSH in as that user.
# If your key is not here, you cannot log in with key auth.
#
#
# SSH KEY BASICS
# -----------------------------------------------------------------------------
#
# id_ed25519
#   PRIVATE key
#
#   - secret
#   - NEVER share
#   - stays on your laptop/desktop
#   - proves your identity to servers
#
#
# id_ed25519.pub
#   PUBLIC key
#
#   - safe to share
#   - copied onto servers
#   - server uses it to verify your private key
#
#
# authorized_keys
#   File on the SERVER containing allowed public keys.
#
#   If your public key appears there:
#     SSH allows login.
#
#
# IMPORTANT — GENERATE KEYS ON YOUR LOCAL MACHINE
# -----------------------------------------------------------------------------
# DO NOT generate your login keypair on the server itself.
#
# Wrong flow:
#
#   server generates keys
#   then you copy private key out of server
#
# That works technically but defeats the security model and becomes messy.
#
#
# Correct flow:
#
#   your PC generates keys locally
#   server receives ONLY the public key
#
#
# STEP 1 — GENERATE A KEYPAIR LOCALLY
# -----------------------------------------------------------------------------
#
# WINDOWS (PowerShell):
#
#   ssh-keygen -t ed25519
#
#
# LINUX / MAC:
#
#   ssh-keygen -t ed25519
#
#
# You will see:
#
#   Enter file in which to save the key
#   (C:\Users\youruser\.ssh\id_ed25519):
#
# or on Linux:
#
#   (/home/youruser/.ssh/id_ed25519):
#
#
# IMPORTANT:
# Press ENTER unless you intentionally want a custom path.
#
#
# Correct result:
#
#   ~/.ssh/id_ed25519
#   ~/.ssh/id_ed25519.pub
#
#
# WHAT THESE FILES ARE
# -----------------------------------------------------------------------------
#
# ~/.ssh/id_ed25519
#   PRIVATE key
#
#
# ~/.ssh/id_ed25519.pub
#   PUBLIC key
#
#
# NEVER share:
#
#   id_ed25519
#
#
# Safe to share:
#
#   id_ed25519.pub
#
#
# OPTIONAL — PASSPHRASE
# -----------------------------------------------------------------------------
# ssh-keygen optionally asks for a passphrase.
#
# If set:
#
#   - the private key itself becomes encrypted
#   - stealing the file alone is insufficient
#
# Tradeoff:
#
#   - more secure
#   - but requires entering passphrase when using SSH
#
#
# STEP 2 — SHOW YOUR PUBLIC KEY
# -----------------------------------------------------------------------------
#
# WINDOWS:
#
#   type $HOME\.ssh\id_ed25519.pub
#
#
# LINUX / MAC:
#
#   cat ~/.ssh/id_ed25519.pub
#
#
# Copy the ENTIRE line.
#
# It looks something like:
#
#   ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAI... youruser@hostname
#
#
# STEP 3 — ON THE SERVER
# -----------------------------------------------------------------------------
# Login normally with password ONE LAST TIME:
#
#   ssh deploy@yourserver
#
#
# Create the .ssh directory:
#
#   mkdir -p /home/deploy/.ssh
#
#
# Create/edit authorized_keys:
#
#   nano /home/deploy/.ssh/authorized_keys
#
#
# Paste the PUBLIC key from step 2.
#
#
# IMPORTANT:
# authorized_keys stores PUBLIC keys ONLY.
#
# NEVER paste:
#
#   -----BEGIN OPENSSH PRIVATE KEY-----
#
# into authorized_keys.
#
#
# NANO SHORTCUTS
# -----------------------------------------------------------------------------
#
# CTRL + W
#   Search (equivalent of Ctrl+F)
#
#
# ALT + W
#   Find next match
#
#
# CTRL + O
#   Save file
#
#
# CTRL + X
#   Exit nano
#
#
# ALT + \
#   Jump to beginning of file
#
#
# ALT + /
#   Jump to end of file
#
#
# STEP 4 — FIX SSH PERMISSIONS
# -----------------------------------------------------------------------------
# OpenSSH intentionally rejects insecure permissions.
#
# Required:
#
#   chmod 700 /home/deploy/.ssh
#   chmod 600 /home/deploy/.ssh/authorized_keys
#   chown -R deploy:deploy /home/deploy/.ssh
#
#
# WHAT THESE MEAN
# -----------------------------------------------------------------------------
#
# chmod 700
#
#   owner:
#     read + write + execute
#
#   everyone else:
#     nothing
#
#
# chmod 600
#
#   owner:
#     read + write
#
#   everyone else:
#     nothing
#
#
# STEP 5 — DISABLE PASSWORD AUTH
# -----------------------------------------------------------------------------
#
# Edit SSH daemon config:
#
#   sudo nano /etc/ssh/sshd_config
#
#
# Recommended settings:
#
#   PasswordAuthentication no
#   PubkeyAuthentication yes
#   PermitRootLogin no
#
#
# IMPORTANT — CLOUD-INIT OVERRIDES
# -----------------------------------------------------------------------------
# Ubuntu cloud images often override SSH settings using:
#
#   /etc/ssh/sshd_config.d/
#
#
# Check overrides:
#
#   ls -la /etc/ssh/sshd_config.d
#
#
# Search all SSH config files:
#
#   sudo grep -R "PasswordAuthentication" /etc/ssh/sshd_config*
#
#
# You may find:
#
#   /etc/ssh/sshd_config.d/50-cloud-init.conf
#
# containing:
#
#   PasswordAuthentication yes
#
#
# If so:
#
#   sudo nano /etc/ssh/sshd_config.d/50-cloud-init.conf
#
#
# Change:
#
#   PasswordAuthentication yes
#
# to:
#
#   PasswordAuthentication no
#
#
# WHAT THESE SETTINGS DO
# -----------------------------------------------------------------------------
#
# PasswordAuthentication no
#   disables password login completely
#
#
# PubkeyAuthentication yes
#   allows SSH key login
#
#
# PermitRootLogin no
#   completely disables SSH login as root
#
#
# WHY ROOT LOGIN SHOULD BE DISABLED
# -----------------------------------------------------------------------------
# Root is the #1 brute-force target on the internet.
#
# If root login is disabled:
#
#   bots cannot even ATTEMPT root auth successfully
#
#
# Recommended flow:
#
#   ssh deploy@server
#   sudo -i
#
#
# instead of:
#
#   ssh root@server
#
#
# DO YOU NEED authorized_keys FOR ROOT TOO?
# -----------------------------------------------------------------------------
# Usually:
#
#   NO
#
#
# Best practice:
#
#   - disable direct root SSH login
#   - login as deploy
#   - escalate with sudo
#
#
# You only configure:
#
#   /root/.ssh/authorized_keys
#
# if you intentionally allow:
#
#   ssh root@server
#
# which is generally discouraged on public servers.
#
#
# STEP 6 — VALIDATE SSH CONFIG
# -----------------------------------------------------------------------------
#
# Validate syntax BEFORE restarting:
#
#   sudo sshd -t
#
#
# If no output appears:
#
#   config syntax is valid
#
#
# STEP 7 — RESTART SSH
# -----------------------------------------------------------------------------
#
# Ubuntu/Debian:
#
#   sudo systemctl restart ssh
#
#
# Some distros:
#
#   sudo systemctl restart sshd
#
#
# STEP 8 — VERIFY EFFECTIVE SETTINGS
# -----------------------------------------------------------------------------
#
# Check final effective config:
#
#   sudo sshd -T | grep -E \
#     'passwordauthentication|pubkeyauthentication|permitrootlogin'
#
#
# Expected:
#
#   permitrootlogin no
#   pubkeyauthentication yes
#   passwordauthentication no
#
#
# STEP 9 — TEST BEFORE CLOSING SESSION
# -----------------------------------------------------------------------------
# CRITICAL:
#
# NEVER close your current SSH session yet.
#
#
# Open a SECOND terminal and test:
#
# WINDOWS:
#
#   ssh deploy@yourserver
#
#
# LINUX/MAC:
#
#   ssh deploy@yourserver
#
#
# SUCCESS LOOKS LIKE
# -----------------------------------------------------------------------------
#
#   - no password prompt
#   - login succeeds immediately
#   - possibly asks for PRIVATE KEY passphrase
#
#
# IF IT FAILS
# -----------------------------------------------------------------------------
# Your CURRENT SSH session is still open so you can fix:
#
#   - wrong permissions
#   - wrong authorized_keys contents
#   - wrong sshd_config
#   - missing public key
#   - wrong override file
#
#
# COMMON FAILURE CHECKLIST
# -----------------------------------------------------------------------------
#
# Verify server SSH files:
#
#   ls -la /home/deploy/.ssh
#
#
# Verify authorized_keys contents:
#
#   cat /home/deploy/.ssh/authorized_keys
#
#
# Verify SSH config:
#
#   sudo sshd -T | grep -E \
#     'passwordauthentication|pubkeyauthentication|permitrootlogin'
#
#
# Verify logs while testing:
#
#   sudo tail -f /var/log/auth.log
#
#
# WINDOWS-SPECIFIC PITFALLS
# -----------------------------------------------------------------------------
#
# If ssh-keygen fails with:
#
#   Permission denied
#
# when overwriting keys:
#
#   old file permissions may block modification
#
#
# Delete old keys first:
#
#   del $HOME\.ssh\id_ed25519
#   del $HOME\.ssh\id_ed25519.pub
#
#
# Then regenerate:
#
#   ssh-keygen -t ed25519
#
#
# Another common mistake:
#
#   accidentally saving:
#
#     id_ed25519.txt
#
# instead of:
#
#     id_ed25519
#
#
# FINAL RESULT
# -----------------------------------------------------------------------------
# After this:
#
#   - password brute force becomes irrelevant
#   - only machines possessing your PRIVATE key can authenticate
#   - SSH exposure drops massively
#
# ─── ADDITIONAL SERVER HARDENING ──────────────────────────────────────────────
#
# SSH keys are a HUGE improvement, but security is layers.
#
# Public servers still get:
#
#   - vulnerability scans
#   - exploit attempts
#   - bot traffic
#   - HTTP probing
#   - port scans
#
# Reduce attack surface everywhere possible.
#
#
# YOUR CURRENT SERVER ARCHITECTURE
# -----------------------------------------------------------------------------
#
# Your setup currently looks roughly like:
#
#   Internet
#      ↓
#   k3s LoadBalancer Service
#      ↓
#   nginx service inside Kubernetes
#      ↓
#   backend / grafana / temporal / etc
#
#
# Important:
#
#   nginx is NOT installed directly on Ubuntu host OS.
#
# You verified:
#
#   systemctl status nginx
#
# returned:
#
#   Unit nginx.service could not be found.
#
#
# Instead:
#
#   kubectl get svc -A
#
# showed:
#
#   portfolio/nginx  LoadBalancer
#
#
# This means:
#
#   nginx runs INSIDE Kubernetes
#
# not as a normal Ubuntu systemd service.
#
#
# WHY YOU DID NOT SEE PORT 80/443 IN ss -tulpn
# -----------------------------------------------------------------------------
#
# k3s uses internal networking + iptables forwarding.
#
# Traffic flow is roughly:
#
#   public :80/:443
#      ↓
#   k3s networking layer
#      ↓
#   NodePort
#      ↓
#   nginx pod
#
#
# So:
#
#   kubectl get svc
#
# is often more useful than:
#
#   ss -tulpn
#
# when debugging Kubernetes networking.
#
#
# YOUR CURRENT EXPOSED PORTS
# -----------------------------------------------------------------------------
#
# From your outputs:
#
#   22     → SSH
#   6443   → Kubernetes API server
#   10250  → kubelet API
#
#
# IMPORTANT SECURITY NOTE
# -----------------------------------------------------------------------------
#
# Port 6443:
#
#   Kubernetes API server
#
# Port 10250:
#
#   kubelet API
#
#
# These are HIGH VALUE TARGETS.
#
# If publicly exposed unnecessarily:
#
#   attackers specifically probe them.
#
#
# RECOMMENDATION
# -----------------------------------------------------------------------------
#
# If this is a SINGLE NODE personal project cluster:
#
#   strongly consider firewalling:
#
#     6443
#     10250
#
#
# so ONLY SSH + HTTP/HTTPS remain public.
#
#
# FAIL2BAN
# -----------------------------------------------------------------------------
#
# fail2ban monitors logs and temporarily bans IPs repeatedly failing auth.
#
# Example:
#
#   attacker tries 500 passwords
#   → fail2ban inserts firewall rule
#   → attacker IP blocked automatically
#
#
# INSTALL
# -----------------------------------------------------------------------------
#
#   sudo apt update
#   sudo apt install fail2ban -y
#
#
# ENABLE + START
# -----------------------------------------------------------------------------
#
#   sudo systemctl enable fail2ban
#   sudo systemctl start fail2ban
#
#
# VERIFY
# -----------------------------------------------------------------------------
#
# Overall status:
#
#   sudo fail2ban-client status
#
#
# SSH jail:
#
#   sudo fail2ban-client status sshd
#
#
# WHY THIS MATTERS
# -----------------------------------------------------------------------------
#
# Even with password auth disabled:
#
#   bots still hammer SSH constantly.
#
# fail2ban reduces:
#
#   - log spam
#   - repeated probing
#   - automated noise
#
# UFW FIREWALL
# -----------------------------------------------------------------------------
#
# UFW = Uncomplicated Firewall
#
# Default-deny inbound traffic unless explicitly allowed.
#
#
# INSTALL
# -----------------------------------------------------------------------------
#
# Usually already installed on Ubuntu.
#
# If not:
#
#   sudo apt install ufw -y
#
#
# ⚠️  IMPORTANT: FOLLOW THIS ORDER EXACTLY
# -----------------------------------------------------------------------------
#
# Wrong order = locked out of your server.
#
#   1. Set default policies
#   2. Allow SSH          ← BEFORE enabling UFW
#   3. Allow web ports
#   4. Block k8s ports
#   5. Enable UFW         ← LAST
#
#
# STEP 1 — DEFAULT POLICY
# -----------------------------------------------------------------------------
#
# Deny ALL inbound traffic by default:
#
#   sudo ufw default deny incoming
#
# Allow outbound:
#
#   sudo ufw default allow outgoing
#
#
# STEP 2 — ALLOW SSH
# -----------------------------------------------------------------------------
#
# CRITICAL: Do this BEFORE enabling UFW or you will lock yourself out.
#
#   sudo ufw allow 22/tcp
#
#
# STEP 3 — ALLOW WEB TRAFFIC
# -----------------------------------------------------------------------------
#
# Your Kubernetes nginx LoadBalancer (portfolio/nginx) serves:
#
#   80   → HTTP
#   443  → HTTPS
#
#   sudo ufw allow 80/tcp
#   sudo ufw allow 443/tcp
#
#
# STEP 4 — BLOCK KUBERNETES CONTROL-PLANE / NODE APIS
# -----------------------------------------------------------------------------
#
# Your ss -tulpn shows these are bound on 0.0.0.0 / * (publicly reachable!):
#
#   6443   → k3s API server          (*:6443)
#   10250  → kubelet API             (*:10250)
#   8472   → VXLAN overlay (Flannel) (0.0.0.0:8472 UDP)
#
# These must NOT be reachable from the internet.
# UFW default deny already covers them, but explicit rules are clearer:
#
#   sudo ufw deny 6443/tcp
#   sudo ufw deny 10250/tcp
#   sudo ufw deny 8472/udp
#
# These are safe because k3s internal traffic uses the loopback
# or cluster-internal IPs (127.x / 10.43.x), not the public interface.
#
#
# STEP 5 — ENABLE UFW
# -----------------------------------------------------------------------------
#
# Only enable AFTER all rules are in place:
#
#   sudo ufw enable
#
#
# VERIFY
# -----------------------------------------------------------------------------
#
#   sudo ufw status verbose
#
# Expected output:
#
#   To                Action    From
#   --                ------    ----
#   22/tcp            ALLOW IN  Anywhere
#   80/tcp            ALLOW IN  Anywhere
#   443/tcp           ALLOW IN  Anywhere
#   6443/tcp          DENY IN   Anywhere
#   10250/tcp         DENY IN   Anywhere
#   8472/udp          DENY IN   Anywhere
#
# Your current k3s setup exposes:
#
#   6443  → Kubernetes API server
#   10250 → kubelet API
#
#
# IMPORTANT:
# -----------------------------------------------------------------------------
#
# These services intentionally listen on:
#
#   0.0.0.0
#
# instead of:
#
#   127.0.0.1
#
#
# WHY?
# -----------------------------------------------------------------------------
#
# Kubernetes components communicate over the network.
#
# Even on single-node clusters:
#
#   - kubelets
#   - agents
#   - kubectl
#   - control-plane components
#
# may need network reachability.
#
#
# So binding ONLY to:
#
#   127.0.0.1
#
# could break cluster functionality depending on configuration.
#
#
# IMPORTANT DISTINCTION
# -----------------------------------------------------------------------------
#
# LISTENING on:
#
#   0.0.0.0
#
# does NOT automatically mean:
#
#   publicly reachable from internet
#
#
# Firewall rules can still block external access.
#
#
# GOOD SECURITY MODEL
# -----------------------------------------------------------------------------
#
# Kubernetes internal services:
#
#   can listen internally
#
# while:
#
#   UFW blocks internet traffic to them
#
#
# RECOMMENDED FOR YOUR CURRENT SETUP
# -----------------------------------------------------------------------------
#
# Keep:
#
#   6443
#   10250
#
# listening normally for k3s internal operation,
#
# BUT firewall them from public internet:
#
#   sudo ufw deny 6443/tcp
#   sudo ufw deny 10250/tcp
#
#
# RESULT
# -----------------------------------------------------------------------------
#
# Internal cluster communication:
#   still works
#
#
# Public internet:
#   cannot directly access kube APIs
#
#
# WHY THIS MATTERS
# -----------------------------------------------------------------------------
#
# 6443:
#   Kubernetes control-plane API
#
#
# 10250:
#   kubelet API
#
#
# These are high-value infrastructure targets.
#
# Attackers specifically scan the internet for exposed kube APIs.
#
#
# YOUR CURRENT TEST CONFIRMED THIS
# -----------------------------------------------------------------------------
#
# You successfully reached:
#
#   https://YOUR_SERVER_IP:6443
#
# and received:
#
#   Unauthorized
#
#
# This means:
#
#   the API server is publicly reachable right now.
#
#
# Authentication still protects it,
#
# BUT:
#
#   reducing exposure is better security practice.
#
#
# IDEAL PUBLIC EXPOSURE
# -----------------------------------------------------------------------------
#
# Public:
#
#   22   → SSH
#   80   → HTTP
#   443  → HTTPS
#
#
# Everything else:
#
#   blocked externally by firewall
#
# while remaining usable internally by Kubernetes.
#
#
# AUTOMATIC SECURITY UPDATES
# -----------------------------------------------------------------------------
#
# Linux packages receive security patches continuously.
#
# If you never patch:
#
#   eventually known vulnerabilities accumulate.
#
#
# INSTALL
# -----------------------------------------------------------------------------
#
#   sudo apt install unattended-upgrades -y
#
#
# ENABLE
# -----------------------------------------------------------------------------
#
#   sudo dpkg-reconfigure unattended-upgrades
#
#
# Choose:
#
#   Yes
#
#
# WHY THIS MATTERS
# -----------------------------------------------------------------------------
#
# Security vulnerabilities become public constantly.
#
# Bots scan for:
#
#   outdated kernels
#   outdated OpenSSH
#   outdated nginx
#   outdated container runtimes
#
#
# Automatic updates reduce exposure window.
#
#
# NON-ROOT DEPLOY USER
# -----------------------------------------------------------------------------
#
# Already done correctly.
#
#
# GOOD FLOW
# -----------------------------------------------------------------------------
#
#   ssh deploy@server
#   sudo -i
#
#
# AVOID
# -----------------------------------------------------------------------------
#
#   ssh root@server
#
#
# WHY
# -----------------------------------------------------------------------------
#
# Separates:
#
#   normal operations
#   from
#   full administrative access
#
#
# Also reduces accidental destructive commands.
#
#
# REMOVE UNUSED SERVICES / PORTS
# -----------------------------------------------------------------------------
#
# Every listening service increases attack surface.
#
#
# CHECK HOST PORTS
# -----------------------------------------------------------------------------
#
#   sudo ss -tulpn
#
#
# CHECK KUBERNETES SERVICES
# -----------------------------------------------------------------------------
#
#   kubectl get svc -A
#
#
# THINGS THAT SHOULD NEVER BE PUBLIC
# -----------------------------------------------------------------------------
#
# Usually:
#
#   Redis
#   PostgreSQL
#   MinIO admin
#   Docker daemon
#   kubelet APIs
#   debug/admin ports
#
#
# WHY
# -----------------------------------------------------------------------------
#
# Many infrastructure breaches happen because:
#
#   internal services were accidentally internet exposed.
#
#
# YOUR CURRENT SERVICES LOOK GOOD
# -----------------------------------------------------------------------------
#
# Most services are:
#
#   ClusterIP
#
#
# Meaning:
#
#   internal Kubernetes-only access
#
#
# This is GOOD.
#
#
# KEEP IT THAT WAY
# -----------------------------------------------------------------------------
#
# Avoid changing sensitive services to:
#
#   NodePort
#   LoadBalancer
#
#
# unless absolutely necessary.
#
#
# REMOVE UNUSED PACKAGES
# -----------------------------------------------------------------------------
#
# Less installed software means:
#
#   - fewer vulnerabilities
#   - fewer background services
#   - smaller attack surface
#
#
# PERIODIC CLEANUP
# -----------------------------------------------------------------------------
#
# Remove unused packages:
#
#   sudo apt autoremove
#
#
# LIST INSTALLED SERVICES
# -----------------------------------------------------------------------------
#
#   systemctl list-units --type=service
#
#
# KEEP K3S UPDATED
# -----------------------------------------------------------------------------
#
# Kubernetes components receive security patches too.
#
#
# CHECK VERSION
# -----------------------------------------------------------------------------
#
#   k3s --version
#
#
# UPDATE K3S
# -----------------------------------------------------------------------------
#
# Follow official upgrade docs carefully.
#
#
# WHY THIS MATTERS
# -----------------------------------------------------------------------------
#
# Kubernetes vulnerabilities can become:
#
#   cluster compromise
#   container escape
#   privilege escalation
#
#
# FINAL SECURITY MENTAL MODEL
# -----------------------------------------------------------------------------
#
# SSH keys:
#   protect authentication
#
#
# UFW:
#   protects network exposure
#
#
# fail2ban:
#   slows automated attacks
#
#
# updates:
#   patch vulnerabilities
#
#
# minimal services:
#   reduce attack surface
#
#
# non-root users:
#   reduce blast radius
#
#
# Kubernetes internal-only services:
#   reduce infrastructure exposure
#
#
# Security is layers, not one feature.
#
# ──────────────────────────────────────────────────────────────────────────────