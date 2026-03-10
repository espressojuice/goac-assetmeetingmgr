#!/bin/bash
set -euo pipefail

# GOAC Asset Meeting Manager — One-time VPS setup
# Run as root on a fresh Hetzner CX21 (Ubuntu 22.04)

echo "=== GOAC Server Setup ==="

# Update system
apt-get update && apt-get upgrade -y

# Install Docker
curl -fsSL https://get.docker.com | sh

# Install docker-compose-plugin
apt-get install -y docker-compose-plugin

# Create deploy user
useradd -m -d /home/deploy -s /bin/bash deploy
usermod -aG docker deploy

# Copy SSH keys
mkdir -p /home/deploy/.ssh
cp /root/.ssh/authorized_keys /home/deploy/.ssh/authorized_keys
chown -R deploy:deploy /home/deploy/.ssh
chmod 700 /home/deploy/.ssh
chmod 600 /home/deploy/.ssh/authorized_keys

# Firewall
apt-get install -y ufw
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

# Fail2ban
apt-get install -y fail2ban
systemctl enable fail2ban
systemctl start fail2ban

# Automatic security updates
apt-get install -y unattended-upgrades
dpkg-reconfigure -plow unattended-upgrades

# Harden SSH
sed -i 's/^#\?PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config
sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
systemctl restart sshd

# Clone repo and set up directory
su - deploy -c "git clone https://github.com/gregg-orr/goac-assetmeetingmgr.git /home/deploy/goac-assetmeetingmgr"
su - deploy -c "mkdir -p /home/deploy/goac-assetmeetingmgr/backups"

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Next steps:"
echo "  1. SSH in as deploy user: ssh deploy@$(hostname -I | awk '{print $1}')"
echo "  2. cd /home/deploy/goac-assetmeetingmgr"
echo "  3. cp .env.example .env && nano .env  (fill in secrets)"
echo "  4. docker compose -f docker-compose.prod.yml up -d"
echo "  5. docker compose -f docker-compose.prod.yml exec api alembic upgrade head"
echo "  6. Point your domain DNS A record to this server"
