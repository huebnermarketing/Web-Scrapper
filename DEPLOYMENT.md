# Production Deployment Guide

This guide will help you deploy the Web Content Scraper to AWS EC2 with Nginx as a reverse proxy.

## Prerequisites

- AWS EC2 instance running (Ubuntu 20.04+ recommended)
- Nginx installed and running
- Domain name (optional, for SSL)
- Basic knowledge of Linux commands

## Step 1: Server Setup

### 1.1 Update System
```bash
sudo apt update && sudo apt upgrade -y
```

### 1.2 Install Python and pip
```bash
sudo apt install python3 python3-pip python3-venv nginx -y
```

### 1.3 Install additional dependencies
```bash
sudo apt install build-essential libxml2-dev libxslt1-dev zlib1g-dev libffi-dev libssl-dev -y
```

## Step 2: Application Deployment

### 2.1 Create Application Directory
```bash
sudo mkdir -p /var/www/web-scraper
sudo chown ubuntu:www-data /var/www/web-scraper
cd /var/www/web-scraper
```

### 2.2 Upload Application Files
Upload your application files to `/var/www/web-scraper/`:
- `app.py`
- `requirements.txt`
- `templates/` directory

### 2.3 Create Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2.4 Test Application
```bash
python app.py
# Test on http://your-server-ip:8077
# Press Ctrl+C to stop
```

## Step 3: Production Configuration

### 3.1 Create Production App Configuration
Create `/var/www/web-scraper/app_production.py`:

```python
from app import app
import os

if __name__ == '__main__':
    # Production configuration
    app.run(
        host='127.0.0.1',
        port=8077,  
        debug=False,
        threaded=True
    )
```

### 3.2 Create WSGI Entry Point
Create `/var/www/web-scraper/wsgi.py`:

```python
#!/usr/bin/python3
import sys
import os

# Add the project directory to the Python path
sys.path.insert(0, '/var/www/web-scraper/')

from app import app as application

if __name__ == "__main__":
    application.run()
```

### 3.3 Install Gunicorn
```bash
source venv/bin/activate
pip install gunicorn
```

## Step 4: Systemd Service Configuration

### 4.1 Create Systemd Service File
Create `/etc/systemd/system/web-scraper.service`:

```ini
[Unit]
Description=Web Content Scraper
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/web-scraper/Web-Scrapper
Environment="PATH=/var/www/web-scraper/Web-Scrapper/.venv/bin"
ExecStart=/var/www/web-scraper/Web-Scrapper/.venv/bin/gunicorn --workers 3 --bind 127.0.0.1:8077 wsgi:application
ExecReload=/bin/kill -s HUP $MAINPID
Restart=always

[Install]
WantedBy=multi-user.target
```

### 4.2 Enable and Start Service
```bash
sudo systemctl daemon-reload
sudo systemctl enable web-scraper
sudo systemctl start web-scraper
sudo systemctl status web-scraper
```

## Step 5: Nginx Configuration

### 5.1 Create Nginx Configuration
Create `/etc/nginx/sites-available/web-scraper`:

```nginx
server {
    listen 80;
    server_name scrapper.wliq.ai;  # Replace with your domain or IP

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "no-referrer-when-downgrade" always;
    add_header Content-Security-Policy "default-src 'self' http: https: data: blob: 'unsafe-inline'" always;

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api:10m rate=10r/m;
    limit_req zone=api burst=20 nodelay;

    location / {
        proxy_pass http://127.0.0.1:8077;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Timeout settings
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # Static files (if any)
    location /static {
        alias /var/www/web-scraper/Web-Scrapper/static;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # Security - deny access to sensitive files
    location ~ /\. {
        deny all;
    }
}
```

### 5.2 Enable Site
```bash
sudo ln -s /etc/nginx/sites-available/web-scraper /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

## Step 6: SSL Configuration (Optional but Recommended)

### 6.1 Install Certbot
```bash
sudo apt install certbot python3-certbot-nginx -y
```

### 6.2 Get SSL Certificate
```bash
sudo certbot --nginx -d your-domain.com -d www.your-domain.com
```

### 6.3 Auto-renewal
```bash
sudo crontab -e
# Add this line:
0 12 * * * /usr/bin/certbot renew --quiet
```

## Step 7: Firewall Configuration

### 7.1 Configure UFW
```bash
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw --force enable
```

## Step 8: Monitoring and Logs

### 8.1 View Application Logs
```bash
sudo journalctl -u web-scraper -f
```

### 8.2 View Nginx Logs
```bash
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

### 8.3 Application Logs
```bash
sudo tail -f /var/log/web-scraper/app.log
```

## Step 9: Performance Optimization

### 9.1 Update Nginx Configuration
Add to your Nginx config:

```nginx
# Gzip compression
gzip on;
gzip_vary on;
gzip_min_length 1024;
gzip_types text/plain text/css text/xml text/javascript application/javascript application/xml+rss application/json;

# Client settings
client_max_body_size 10M;
client_body_timeout 60s;
client_header_timeout 60s;
```

### 9.2 Update Systemd Service
Modify `/etc/systemd/system/web-scraper.service`:

```ini
[Unit]
Description=Web Content Scraper
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/web-scraper
Environment="PATH=/var/www/web-scraper/venv/bin"
ExecStart=/var/www/web-scraper/venv/bin/gunicorn --workers 4 --worker-class gevent --worker-connections 1000 --bind 127.0.0.1:8077 wsgi:application
ExecReload=/bin/kill -s HUP $MAINPID
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

## Step 10: Backup and Maintenance

### 10.1 Create Backup Script
Create `/var/www/web-scraper/backup.sh`:

```bash
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/var/backups/web-scraper"
mkdir -p $BACKUP_DIR

# Backup application
tar -czf $BACKUP_DIR/web-scraper_$DATE.tar.gz /var/www/web-scraper

# Keep only last 7 days
find $BACKUP_DIR -name "web-scraper_*.tar.gz" -mtime +7 -delete

echo "Backup completed: $BACKUP_DIR/web-scraper_$DATE.tar.gz"
```

### 10.2 Make Backup Script Executable
```bash
chmod +x /var/www/web-scraper/backup.sh
```

### 10.3 Schedule Backups
```bash
sudo crontab -e
# Add this line for daily backups at 2 AM:
0 2 * * * /var/www/web-scraper/backup.sh
```

## Troubleshooting

### Common Issues:

1. **Service won't start:**
   ```bash
   sudo systemctl status web-scraper
   sudo journalctl -u web-scraper -n 50
   ```

2. **Nginx 502 Bad Gateway:**
   - Check if the service is running: `sudo systemctl status web-scraper`
   - Check Nginx config: `sudo nginx -t`
   - Check firewall: `sudo ufw status`

3. **Permission issues:**
   ```bash
   sudo chown -R www-data:www-data /var/www/web-scraper
   sudo chmod -R 755 /var/www/web-scraper
   ```

4. **Port conflicts:**
   ```bash
   sudo netstat -tlnp | grep :8077
   sudo lsof -i :8077
   ```

## Security Checklist

- [ ] Firewall configured (UFW)
- [ ] SSL certificate installed
- [ ] Security headers added
- [ ] Rate limiting configured
- [ ] Sensitive files protected
- [ ] Regular updates scheduled
- [ ] Backup system in place
- [ ] Log monitoring set up

## Performance Monitoring

### Install monitoring tools:
```bash
sudo apt install htop iotop nethogs -y
```

### Monitor resources:
```bash
htop                    # CPU and memory usage
iotop                   # Disk I/O
nethogs                 # Network usage
sudo systemctl status web-scraper  # Service status
```

Your Web Content Scraper is now production-ready! 🚀
