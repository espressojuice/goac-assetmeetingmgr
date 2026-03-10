#!/bin/bash
set -euo pipefail

# GOAC Asset Meeting Manager — Server setup for existing Hetzner VPS
# Run as root. Server already has Docker, Traefik, and other apps.
# Traefik runs on ports 80/443 with "web" Docker network.

APP_DIR="/opt/assetmeetinghelper"

echo "=== GOAC Asset Meeting Manager — Server Setup ==="

# Update system
apt-get update && apt-get upgrade -y

# Check if Docker is already installed
if command -v docker &> /dev/null; then
    echo "Docker already installed: $(docker --version)"
else
    echo "Installing Docker..."
    curl -fsSL https://get.docker.com | sh
    apt-get install -y docker-compose-plugin
fi

# Create deploy user if not exists
if id "deploy" &>/dev/null; then
    echo "Deploy user already exists"
else
    echo "Creating deploy user..."
    useradd -m -d /home/deploy -s /bin/bash deploy
    usermod -aG docker deploy
    mkdir -p /home/deploy/.ssh
    cp /root/.ssh/authorized_keys /home/deploy/.ssh/authorized_keys
    chown -R deploy:deploy /home/deploy/.ssh
    chmod 700 /home/deploy/.ssh
    chmod 600 /home/deploy/.ssh/authorized_keys
fi

# Ensure deploy user is in docker group
usermod -aG docker deploy

# Firewall (skip if already configured)
if ufw status | grep -q "Status: active"; then
    echo "UFW already active"
else
    apt-get install -y ufw
    ufw default deny incoming
    ufw default allow outgoing
    ufw allow 22/tcp
    ufw allow 80/tcp
    ufw allow 443/tcp
    ufw --force enable
fi

# Fail2ban
if systemctl is-active --quiet fail2ban; then
    echo "Fail2ban already running"
else
    apt-get install -y fail2ban
    systemctl enable fail2ban
    systemctl start fail2ban
fi

# Configure swap (2GB safety net for OCR memory spikes)
if [ -f /swapfile ]; then
    echo "Swap already configured"
else
    echo "Creating 2GB swap..."
    fallocate -l 2G /swapfile
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    echo '/swapfile none swap sw 0 0' >> /etc/fstab
    echo "Swap enabled: $(swapon --show)"
fi

# Check if "web" Docker network exists (used by Traefik)
if docker network inspect web &>/dev/null; then
    echo "Docker 'web' network already exists"
else
    echo "Creating Docker 'web' network..."
    docker network create web
fi

# Set up app directory
mkdir -p "$APP_DIR"
chown deploy:deploy "$APP_DIR"

# Clone repo
if [ -d "$APP_DIR/.git" ]; then
    echo "Repo already cloned at $APP_DIR"
else
    su - deploy -c "git clone https://github.com/gregg-orr/goac-assetmeetingmgr.git $APP_DIR"
fi

# Create backups directory
su - deploy -c "mkdir -p $APP_DIR/backups"

# Create .env from template if not exists
if [ ! -f "$APP_DIR/.env" ]; then
    su - deploy -c "cp $APP_DIR/.env.example $APP_DIR/.env"
    echo "Created .env from template — edit it with your secrets"
fi

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Next steps:"
echo "  1. SSH in as deploy user: ssh deploy@$(hostname -I | awk '{print $1}')"
echo "  2. cd $APP_DIR"
echo "  3. nano .env  (fill in secrets)"
echo "  4. docker compose -f docker-compose.prod.yml up -d"
echo "  5. docker compose -f docker-compose.prod.yml exec api alembic upgrade head"
echo "  6. Point DNS A record for assetmeeting.goac.io to this server"
