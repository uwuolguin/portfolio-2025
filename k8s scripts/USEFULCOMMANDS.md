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
# ──────────────────────────────────────────────────────────────────────────────