#!/bin/bash

# Web Content Scraper Deployment Script
# Run this script on your EC2 instance

set -e  # Exit on any error

echo "🚀 Starting Web Content Scraper Deployment..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   print_error "This script should not be run as root. Please run as a regular user with sudo privileges."
   exit 1
fi

# Update system
print_status "Updating system packages..."
sudo apt update && sudo apt upgrade -y

# Install required packages
print_status "Installing required packages..."
sudo apt install -y python3 python3-pip python3-venv nginx build-essential libxml2-dev libxslt1-dev zlib1g-dev libffi-dev libssl-dev

# Create application directory
print_status "Creating application directory..."
sudo mkdir -p /var/www/web-scraper
sudo chown $USER:$USER /var/www/web-scraper

# Copy application files (assuming they're in current directory)
print_status "Copying application files..."
cp -r . /var/www/web-scraper/
cd /var/www/web-scraper

# Create virtual environment
print_status "Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install dependencies
print_status "Installing Python dependencies..."
pip install -r requirements-production.txt

# Create production configuration files
print_status "Creating production configuration..."

# Create WSGI file
cat > wsgi.py << 'EOF'
#!/usr/bin/python3
import sys
import os

# Add the project directory to the Python path
sys.path.insert(0, '/var/www/web-scraper/')

from app import app as application

if __name__ == "__main__":
    application.run()
EOF

# Create systemd service file
print_status "Creating systemd service..."
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
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

# Create Nginx configuration
print_status "Creating Nginx configuration..."
sudo tee /etc/nginx/sites-available/web-scraper > /dev/null << 'EOF'
server {
    listen 80;
    server_name _;  # Replace with your domain

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "no-referrer-when-downgrade" always;
    add_header Content-Security-Policy "default-src 'self' http: https: data: blob: 'unsafe-inline'" always;

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api:10m rate=10r/m;
    limit_req zone=api burst=20 nodelay;

    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_types text/plain text/css text/xml text/javascript application/javascript application/xml+rss application/json;

    # Client settings
    client_max_body_size 10M;
    client_body_timeout 60s;
    client_header_timeout 60s;

    location / {
        proxy_pass http://127.0.0.1:8089;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Timeout settings
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # Security - deny access to sensitive files
    location ~ /\. {
        deny all;
    }
}
EOF

# Set proper permissions
print_status "Setting permissions..."
sudo chown -R www-data:www-data /var/www/web-scraper
sudo chmod -R 755 /var/www/web-scraper

# Enable and start services
print_status "Enabling and starting services..."
sudo systemctl daemon-reload
sudo systemctl enable web-scraper
sudo systemctl start web-scraper

# Enable Nginx site
sudo ln -sf /etc/nginx/sites-available/web-scraper /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx

# Configure firewall
print_status "Configuring firewall..."
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw --force enable

# Create backup script
print_status "Creating backup script..."
sudo tee /var/www/web-scraper/backup.sh > /dev/null << 'EOF'
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/var/backups/web-scraper"
mkdir -p $BACKUP_DIR

# Backup application
tar -czf $BACKUP_DIR/web-scraper_$DATE.tar.gz /var/www/web-scraper

# Keep only last 7 days
find $BACKUP_DIR -name "web-scraper_*.tar.gz" -mtime +7 -delete

echo "Backup completed: $BACKUP_DIR/web-scraper_$DATE.tar.gz"
EOF

sudo chmod +x /var/www/web-scraper/backup.sh

# Check service status
print_status "Checking service status..."
if sudo systemctl is-active --quiet web-scraper; then
    print_status "✅ Web scraper service is running!"
else
    print_error "❌ Web scraper service failed to start"
    sudo systemctl status web-scraper
    exit 1
fi

if sudo systemctl is-active --quiet nginx; then
    print_status "✅ Nginx is running!"
else
    print_error "❌ Nginx failed to start"
    sudo systemctl status nginx
    exit 1
fi

# Get server IP
SERVER_IP=$(curl -s http://checkip.amazonaws.com/ || echo "your-server-ip")

print_status "🎉 Deployment completed successfully!"
echo ""
echo "📋 Next Steps:"
echo "1. Visit: http://$SERVER_IP"
echo "2. Test the web scraper functionality"
echo "3. Configure SSL certificate (optional):"
echo "   sudo apt install certbot python3-certbot-nginx"
echo "   sudo certbot --nginx -d your-domain.com"
echo ""
echo "📊 Monitoring Commands:"
echo "• Service status: sudo systemctl status web-scraper"
echo "• View logs: sudo journalctl -u web-scraper -f"
echo "• Nginx logs: sudo tail -f /var/log/nginx/access.log"
echo "• Restart service: sudo systemctl restart web-scraper"
echo ""
echo "🔧 Configuration Files:"
echo "• Service: /etc/systemd/system/web-scraper.service"
echo "• Nginx: /etc/nginx/sites-available/web-scraper"
echo "• App: /var/www/web-scraper/"
echo ""
print_status "Deployment complete! 🚀"
