#!/bin/bash
# EC2 Automated Setup Script for Credit Decision Agent
# Run this ONCE after SSH'ing into your EC2 instance
# curl -O https://raw.githubusercontent.com/.../setup-ec2.sh && bash setup-ec2.sh

set -e

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}========================================${NC}"
echo -e "${YELLOW}EC2 Setup Script for Credit Decision App${NC}"
echo -e "${YELLOW}========================================${NC}"
echo ""

# Configuration
APP_DIR="/home/ubuntu/apps/credit-decision-agent"
VENV_DIR="$APP_DIR/venv"
SERVICE_NAME="streamlit"

# Step 1: Update system
echo -e "${YELLOW}[1/8] Updating system packages...${NC}"
sudo apt-get update -qq
sudo apt-get upgrade -y -qq
echo -e "${GREEN}OK${NC}"

# Step 2: Install dependencies
echo -e "${YELLOW}[2/8] Installing system dependencies...${NC}"
sudo apt-get install -y -qq \
  python3-pip \
  python3-venv \
  git \
  curl \
  wget \
  nginx \
  mysql-client \
  build-essential > /dev/null 2>&1
echo -e "${GREEN}OK${NC}"

# Step 3: Install Docker (optional)
echo -e "${YELLOW}[3/8] Installing Docker...${NC}"
curl -fsSL https://get.docker.com -o get-docker.sh > /dev/null 2>&1
sudo sh get-docker.sh > /dev/null 2>&1
sudo usermod -aG docker ubuntu
rm get-docker.sh
echo -e "${GREEN}OK${NC}"

# Step 4: Create app directory and clone repo
echo -e "${YELLOW}[4/8] Setting up application directory...${NC}"
mkdir -p /home/ubuntu/apps
sudo chown -R ubuntu:ubuntu /home/ubuntu/apps

cd /home/ubuntu/apps

# Check if already cloned
if [ ! -d "$APP_DIR" ]; then
  echo "Please choose deployment method:"
  echo "1. Clone from GitHub (enter REPO_URL below)"
  echo "2. Manual copy (SCP files manually)"
  echo ""
  read -p "Enter GitHub repo URL (or press Enter to skip): " REPO_URL
  
  if [ ! -z "$REPO_URL" ]; then
    git clone $REPO_URL credit-decision-agent
  else
    echo "Creating empty directory. Copy files via SCP:"
    echo "  scp -r -i your-key.pem ./credit-decision-agent ubuntu@YOUR_IP:/home/ubuntu/apps/"
    mkdir -p credit-decision-agent
  fi
fi

echo -e "${GREEN}OK${NC}"

# Step 5: Set up Python environment
echo -e "${YELLOW}[5/8] Creating Python virtual environment...${NC}"
cd $APP_DIR

python3 -m venv venv
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip setuptools wheel -q

# Install requirements
if [ -f "requirements.txt" ]; then
  pip install -r requirements.txt -q
else
  echo -e "${RED}WARNING: requirements.txt not found${NC}"
fi

pip install gunicorn -q
deactivate

echo -e "${GREEN}OK${NC}"

# Step 6: Create environment variables and resource properties
echo -e "${YELLOW}[6/8] Creating resource/properties and .env files...${NC}"

# Ensure resource directory exists and write DB secrets to a single properties file
mkdir -p $APP_DIR/resource
cat > $APP_DIR/resource/properties << 'EOF'
DB_HOST=sathya-database.cilmgugy4iud.us-east-1.rds.amazonaws.com
DB_PORT=3306

EOF

chmod 600 $APP_DIR/resource/properties

# Create .env with non-database settings; DB values are stored in resource/properties
cat > $APP_DIR/.env << 'EOF'
# Logging
CREDIT_DECISION_LOG=/var/log/credit_decision.log

# Streamlit settings
STREAMLIT_SERVER_HEADLESS=true
STREAMLIT_SERVER_PORT=8501
STREAMLIT_CLIENT_TOOLBARMODE=minimal
EOF

chmod 600 $APP_DIR/.env
sudo touch /var/log/credit_decision.log
sudo chown ubuntu:ubuntu /var/log/credit_decision.log

echo -e "${GREEN}OK${NC}"

# Step 7: Set up Nginx reverse proxy
echo -e "${YELLOW}[7/8] Configuring Nginx...${NC}"
sudo tee /etc/nginx/sites-available/credit-decision > /dev/null << 'EOF'
upstream streamlit_app {
    server localhost:8501;
}

server {
    listen 80 default_server;
    listen [::]:80 default_server;
    
    server_name _;
    
    # Timeouts for Streamlit
    proxy_read_timeout 300s;
    proxy_connect_timeout 75s;
    client_max_body_size 50M;
    
    location / {
        proxy_pass http://streamlit_app;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
    
    location /_stcore/stream {
        proxy_pass http://streamlit_app/_stcore/stream;
        proxy_http_version 1.1;
        proxy_buffering off;
        proxy_request_buffering off;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "Upgrade";
    }
}
EOF

sudo ln -sf /etc/nginx/sites-available/credit-decision /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

# Test and restart Nginx
sudo nginx -t > /dev/null 2>&1
sudo systemctl restart nginx
sudo systemctl enable nginx

echo -e "${GREEN}OK${NC}"

# Step 8: Create Systemd service
echo -e "${YELLOW}[8/8] Creating Systemd service...${NC}"
sudo tee /etc/systemd/system/streamlit.service > /dev/null << EOF
[Unit]
Description=Streamlit Credit Decision App
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=$APP_DIR
# Load DB credentials from resource/properties first, then other envs from .env
EnvironmentFile=$APP_DIR/resource/properties
EnvironmentFile=$APP_DIR/.env
ExecStart=$VENV_DIR/bin/streamlit run credit_decision_ui.py --server.port=8501 --server.headless=true --logger.level=info
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable streamlit
sudo systemctl start streamlit

# Wait for service to start
sleep 3

echo -e "${GREEN}OK${NC}"

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Setup Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo "1. Get your public IP:"
echo "   curl http://169.254.169.254/latest/meta-data/public-ipv4"
echo ""
echo "2. Open in browser:"
echo "   http://YOUR_PUBLIC_IP"
echo ""
echo "3. Verify service is running:"
echo "   sudo systemctl status streamlit"
echo ""
echo "4. View logs:"
echo "   sudo journalctl -u streamlit -f"
echo ""
echo -e "${YELLOW}Useful Commands:${NC}"
echo "  Restart app:     sudo systemctl restart streamlit"
echo "  View logs:       sudo journalctl -u streamlit -f"
echo "  App status:      sudo systemctl status streamlit"
echo "  Stop app:        sudo systemctl stop streamlit"
echo "  Start app:       sudo systemctl start streamlit"
echo ""
echo -e "${YELLOW}Security:${NC}"
echo "  - Update SSH key pair regularly"
echo "  - Restrict security group to your IP"
echo "  - Keep system updated: sudo apt-get update && sudo apt-get upgrade"
echo ""
