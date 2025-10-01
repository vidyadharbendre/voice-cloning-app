# ================================
# FILE: scripts/production_setup.sh
# ================================

#!/bin/bash

# Production setup script with comprehensive configuration
echo "🚀 Setting up Voice Cloning API for Production..."

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

# Check if running as root (not recommended for production)
if [ "$EUID" -eq 0 ]; then
    print_warning "Running as root is not recommended for production"
fi

# Create directory structure
print_status "Creating directory structure..."
mkdir -p uploads outputs logs temp
chmod 755 uploads outputs logs temp

# Setup Python virtual environment
if [ ! -d "venv" ]; then
    print_status "Creating Python virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
print_status "Upgrading pip..."
pip install --upgrade pip

# Install dependencies
print_status "Installing Python dependencies..."
pip install -r requirements.txt

# Install additional production dependencies
print_status "Installing production dependencies..."
pip install gunicorn==21.2.0 uvicorn[standard]==0.24.0 psutil==5.9.6 gputil==1.4.0

# Setup environment file
if [ ! -f ".env" ]; then
    print_status "Creating production environment file..."
    cp .env.example .env
    
    # Update for production
    sed -i 's/DEBUG=true/DEBUG=false/' .env
    sed -i 's/USE_GPU=true/USE_GPU=true/' .env
    
    print_warning "Please review and update .env file with your configuration"
fi

# Setup systemd service (if running on Linux with systemd)
if command -v systemctl &> /dev/null; then
    print_status "Setting up systemd service..."
    
    SERVICE_FILE="/etc/systemd/system/voice-cloning-api.service"
    CURRENT_DIR=$(pwd)
    CURRENT_USER=$(whoami)
    
    sudo tee $SERVICE_FILE > /dev/null <<EOF
[Unit]
Description=Voice Cloning API
After=network.target

[Service]
Type=exec
User=$CURRENT_USER
Group=$CURRENT_USER
WorkingDirectory=$CURRENT_DIR
Environment="PATH=$CURRENT_DIR/venv/bin"
ExecStart=$CURRENT_DIR/venv/bin/gunicorn app.main:app -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000 --workers 4 --timeout 300
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF
    
    sudo systemctl daemon-reload
    sudo systemctl enable voice-cloning-api.service
    
    print_status "Systemd service created. Use 'sudo systemctl start voice-cloning-api' to start"
fi

# Setup nginx configuration (if nginx is installed)
if command -v nginx &> /dev/null; then
    print_status "Creating nginx configuration..."
    
    NGINX_CONFIG="/etc/nginx/sites-available/voice-cloning-api"
    
    sudo tee $NGINX_CONFIG > /dev/null <<'EOF'
server {
    listen 80;
    server_name your-domain.com;  # Change this to your domain
    
    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api:10m rate=10r/m;
    
    # File upload size
    client_max_body_size 10M;
    
    location / {
        limit_req zone=api burst=5 nodelay;
        
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Timeouts
        proxy_connect_timeout 300s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
    }
    
    # Static files (optional)
    location /static {
        alias /path/to/your/static/files;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
EOF
    
    print_warning "Nginx configuration created at $NGINX_CONFIG"
    print_warning "Please update server_name and enable the site:"
    print_warning "  sudo ln -s $NGINX_CONFIG /etc/nginx/sites-enabled/"
    print_warning "  sudo nginx -t && sudo systemctl reload nginx"
fi

# Setup SSL with Let's Encrypt (if certbot is available)
if command -v certbot &> /dev/null; then
    print_status "Certbot is available for SSL setup"
    print_warning "Run 'sudo certbot --nginx -d your-domain.com' after configuring nginx"
fi

# Setup log rotation
print_status "Setting up log rotation..."
sudo tee /etc/logrotate.d/voice-cloning-api > /dev/null <<EOF
$CURRENT_DIR/logs/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    copytruncate
    su $CURRENT_USER $CURRENT_USER
}
EOF

# Create startup script
print_status "Creating startup script..."
tee start_production.sh > /dev/null <<EOF
#!/bin/bash
cd "$(dirname "\$0")"
source venv/bin/activate
gunicorn app.main:app \\
    -k uvicorn.workers.UvicornWorker \\
    --bind 0.0.0.0:8000 \\
    --workers 4 \\
    --timeout 300 \\
    --access-logfile logs/access.log \\
    --error-logfile logs/error.log \\
    --log-level info \\
    --preload \\
    --max-requests 1000 \\
    --max-requests-jitter 100
EOF

chmod +x start_production.sh

# Create monitoring script
print_status "Creating monitoring script..."
tee monitor.sh > /dev/null <<EOF
#!/bin/bash
# Simple monitoring script

check_service() {
    if pgrep -f "gunicorn app.main:app" > /dev/null; then
        echo "✅ Voice Cloning API is running"
    else
        echo "❌ Voice Cloning API is not running"
        return 1
    fi
}

check_health() {
    if curl -s http://localhost:8000/api/v1/health > /dev/null; then
        echo "✅ Health check passed"
    else
        echo "❌ Health check failed"
        return 1
    fi
}

check_disk_space() {
    USAGE=\$(df . | awk 'NR==2 {print \$5}' | sed 's/%//')
    if [ \$USAGE -gt 90 ]; then
        echo "⚠️  Disk usage high: \${USAGE}%"
        return 1
    else
        echo "✅ Disk usage OK: \${USAGE}%"
    fi
}

echo "🔍 Voice Cloning API Monitor"
echo "=========================="
check_service
check_health
check_disk_space

# Check logs for errors
echo "📋 Recent errors:"
tail -n 5 logs/error.log 2>/dev/null || echo "No error log found"
EOF

chmod +x monitor.sh

# Final instructions
print_status "Production setup complete!"
echo ""
echo "🎯 Next steps:"
echo "1. Review and update .env file with your configuration"
echo "2. Update nginx configuration with your domain name"
echo "3. Setup SSL certificate with: sudo certbot --nginx -d your-domain.com"
echo "4. Start the service:"
echo "   - Development: python run.py"
echo "   - Production: ./start_production.sh"
echo "   - Systemd: sudo systemctl start voice-cloning-api"
echo "5. Monitor with: ./monitor.sh"
echo ""
print_status "Your Voice Cloning API is ready for production! 🚀"
