#!/usr/bin/env bash
# Automated Deployment Script for Kamatera Cloud Server (103.125.218.205 / happyroli.com.au)
# Optimized for 1 vCPU / 2048 MB RAM / 10 GB SSD
set -e

APP_DIR="/opt/happyroli_web"
DOMAIN="happyroli.com.au"

echo "=== [1/4] Installing lightweight system dependencies (Python3 + Nginx) ==="
sudo apt-get update -y
sudo apt-get install -y python3 python3-minimal nginx

echo "=== [2/4] Setting up application directory at ${APP_DIR} ==="
sudo mkdir -p "${APP_DIR}"
sudo cp -r ./* "${APP_DIR}/"
sudo chown -R www-data:www-data "${APP_DIR}"

echo "=== [3/4] Creating systemd service (happyrolly.service) ==="
sudo tee /etc/systemd/system/happyrolly.service > /dev/null <<EOF
[Unit]
Description=HappyRolly Standalone Roster & Payroll Web Server
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=${APP_DIR}
Environment="PORT=8080"
ExecStart=/usr/bin/python3 ${APP_DIR}/server.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable happyrolly
sudo systemctl restart happyrolly

echo "=== [4/4] Configuring Nginx Reverse Proxy for ${DOMAIN} (103.125.218.205) ==="
sudo tee /etc/nginx/sites-available/happyrolly > /dev/null <<EOF
server {
    listen 80;
    server_name ${DOMAIN} www.${DOMAIN} 103.125.218.205;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    }
}
EOF

sudo ln -sf /etc/nginx/sites-available/happyrolly /etc/nginx/sites-enabled/happyrolly
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx

echo "✅ Deployment Complete! HappyRolly Web is live on http://103.125.218.205 and http://${DOMAIN}"
