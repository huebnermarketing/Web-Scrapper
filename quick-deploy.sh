#!/bin/bash

# Quick Deployment Script for Web Content Scraper
# This is a simplified version for quick deployment

echo "🚀 Quick Deployment for Web Content Scraper"

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   echo "❌ Don't run as root. Use a regular user with sudo privileges."
   exit 1
fi

# Update system
echo "📦 Updating system..."
sudo apt update && sudo apt upgrade -y

# Install dependencies
echo "🔧 Installing dependencies..."
sudo apt install -y python3 python3-pip python3-venv nginx

# Create app directory
echo "📁 Creating application directory..."
sudo mkdir -p /var/www/web-scraper
sudo chown $USER:$USER /var/www/web-scraper

# Copy files
echo "📋 Copying application files..."
cp -r . /var/www/web-scraper/
cd /var/www/web-scraper

# Setup virtual environment
echo "🐍 Setting up Python environment..."
python3 -m venv venv
source venv/bin/activate
pip install -r requirements-production.txt

# Create systemd service
echo "⚙️ Creating systemd service..."
sudo tee /etc/systemd/system/web-scraper.service > /dev/null << 'EOF'
[Unit]
Description=Web Content Scraper
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/web-scraper
Environment="PATH=/var/www/web-scraper/venv/bin"
ExecStart=/var/www/web-scraper/venv/bin/gunicorn --workers 3 --bind 127.0.0.1:8089 wsgi:application
ExecReload=/bin/kill -s HUP $MAINPID
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# Create Nginx config
echo "🌐 Configuring Nginx..."
sudo tee /etc/nginx/sites-available/web-scraper > /dev/null << 'EOF'
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:8089;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF

# Set permissions
sudo chown -R www-data:www-data /var/www/web-scraper
sudo chmod -R 755 /var/www/web-scraper

# Enable services
echo "🚀 Starting services..."
sudo systemctl daemon-reload
sudo systemctl enable web-scraper
sudo systemctl start web-scraper

sudo ln -sf /etc/nginx/sites-available/web-scraper /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx

# Configure firewall
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw --force enable

# Get server IP
SERVER_IP=$(curl -s http://checkip.amazonaws.com/ || echo "your-server-ip")

echo ""
echo "✅ Deployment Complete!"
echo "🌐 Visit: http://$SERVER_IP"
echo "📊 Check status: sudo systemctl status web-scraper"
echo "📝 View logs: sudo journalctl -u web-scraper -f"
echo ""
