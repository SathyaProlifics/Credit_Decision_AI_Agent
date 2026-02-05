# AWS EC2 Deployment Guide - Credit Decision Agent

## EC2 vs Other Options

| Feature | EC2 | App Runner | Beanstalk | ECS |
|---------|-----|-----------|-----------|-----|
| **Setup Time** | 20 min | 30 min | 1 hour | 2+ hours |
| **Monthly Cost** | $10-30* | $37-100 | $50-200 | $30-200 |
| **Cost Predictability** | Fixed | Variable | Variable | Variable |
| **Scaling** | Manual | Auto | Auto | Auto |
| **Best For** | Always-on, constant load | Variable traffic | Traditional apps | Complex setups |
| **Server Control** | Full | None | Limited | Limited |
| **SSH Access** | Yes | No | Limited | No |

*EC2 pricing: t3.micro ($10.08/month) + RDS $40 + data transfer = ~$50-80/month for basic setup

**Best EC2 Instance for This App:**
- **t3.small** ($20.74/month) - Recommended for light-medium traffic
- **t3.micro** ($10.08/month) - Minimum (limited for peak traffic)
- **t3.medium** ($41.47/month) - For higher traffic

---

## EC2 Deployment Architecture

```
┌─────────────────────────────────────────────┐
│            Internet / Users                 │
└────────────────────┬────────────────────────┘
                     │
                     ▼
        ┌────────────────────────┐
        │   Security Group       │
        │   (Port 80, 443, 22)   │
        └────────┬───────────────┘
                 │
                 ▼
    ┌────────────────────────────────┐
    │   EC2 Instance (t3.small)      │
    │  ┌──────────────────────────┐  │
    │  │ Streamlit App (8501)     │  │
    │  │ (in Docker or direct)    │  │
    │  └──────────────────────────┘  │
    │  ┌──────────────────────────┐  │
    │  │ Nginx (reverse proxy)    │  │
    │  │ (port 80/443)            │  │
    │  └──────────────────────────┘  │
    └────────────┬───────────────────┘
                 │
                 ▼
    ┌────────────────────────────────┐
    │   RDS MySQL Database           │
    │   (us-east-1)                  │
    └────────────────────────────────┘
```

---

## Step-by-Step EC2 Deployment

### Prerequisites
- AWS Account with EC2 permissions
- AWS CLI configured
- PEM key pair for EC2 (create in AWS Console)
- ~5 minutes per step

### Step 1: Create EC2 Instance (5 min)

#### Option A: Via AWS Console (Easiest)
1. Go to **EC2 Dashboard**
2. Click **"Launch Instances"**
3. **Name**: `credit-decision-agent`
4. **AMI**: Select **"Ubuntu 22.04 LTS"** (free tier eligible)
5. **Instance Type**: 
   - **t3.micro** (Free tier - limited)
   - **t3.small** (Recommended - $20.74/month)
6. **Key Pair**: Create or select existing `.pem` file
7. **Network Settings**:
   - VPC: Default
   - Auto-assign IP: Enable (public IP)
   - Create new Security Group:
     - **Name**: `credit-decision-sg`
     - **Inbound Rules**:
       - SSH (22) from your IP
       - HTTP (80) from 0.0.0.0/0
       - HTTPS (443) from 0.0.0.0/0
8. **Storage**: 20 GB (default is fine)
9. Click **"Launch Instance"**
10. Wait 1-2 minutes for instance to start

#### Option B: Via AWS CLI
```bash
# Get latest Ubuntu 22.04 AMI ID
AMI_ID=$(aws ec2 describe-images \
  --owners 099720109477 \
  --filters "Name=name,Values=ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*" \
  --query 'Images | sort_by(@, &CreationDate) | [-1].ImageId' \
  --output text)

# Create instance
aws ec2 run-instances \
  --image-id $AMI_ID \
  --instance-type t3.small \
  --key-name your-key-name \
  --security-groups credit-decision-sg \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=credit-decision-agent}]'

# Get public IP
aws ec2 describe-instances \
  --filters "Name=tag:Name,Values=credit-decision-agent" \
  --query 'Reservations[0].Instances[0].PublicIpAddress' \
  --output text
```

**Result**: You'll have a public IP address (e.g., `54.123.45.67`)

---

### Step 2: Connect to EC2 & Install Dependencies (10 min)

```bash
# Connect via SSH (use your key pair file)
ssh -i /path/to/your-key.pem ubuntu@YOUR_PUBLIC_IP

# Update system packages
sudo apt-get update
sudo apt-get upgrade -y

# Install required packages
sudo apt-get install -y \
  python3-pip \
  python3-venv \
  git \
  curl \
  wget \
  nginx \
  mysql-client

# Install Docker (optional - for containerized deployment)
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker ubuntu

# Verify installations
python3 --version
pip3 --version
nginx -v
docker --version
```

---

### Step 3: Deploy Application - Option A (Direct Installation)

#### 3A: Clone Repository
```bash
# Create app directory
mkdir -p /home/ubuntu/apps
cd /home/ubuntu/apps

# Clone your GitHub repository (if you have one)
git clone https://github.com/YOUR_USERNAME/credit-decision-agent.git
cd credit-decision-agent

# Or download files directly if no git repo
# (manually SCP files or use wget)
```

#### 3B: Set Up Virtual Environment
```bash
# Create Python virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install additional server packages
pip install gunicorn
```

#### 3C: Set Environment Variables
```bash
# Create .env file
cat > .env << EOF
DB_HOST=sathya-database.cilmgugy4iud.us-east-1.rds.amazonaws.com
DB_PORT=3306
DB_USER=admin
DB_PASSWORD=za*~[VF7v>rgCMg6mCWc_S9JS*ZG
DB_NAME=dev
CREDIT_DECISION_LOG=/var/log/credit_decision.log
EOF

# Set proper permissions
chmod 600 .env
```

#### 3D: Test Streamlit Locally
```bash
# Test if app runs
streamlit run credit_decision_ui.py --server.port=8501 --server.headless=true

# Should see: "You can now view your Streamlit app in your browser"
# Ctrl+C to stop
```

---

### Step 3: Deploy Application - Option B (Docker)

#### 3B: Build Docker Image
```bash
cd /home/ubuntu/apps/credit-decision-agent

# Build image
docker build -t credit-decision-agent:latest .

# Test locally
docker run -p 8501:8501 \
  -e DB_HOST=sathya-database.cilmgugy4iud.us-east-1.rds.amazonaws.com \
  -e DB_USER=admin \
  -e DB_PASSWORD=za*~[VF7v>rgCMg6mCWc_S9JS*ZG \
  -e DB_NAME=dev \
  credit-decision-agent:latest

# Should see app running on http://localhost:8501
# Ctrl+C to stop
```

---

### Step 4: Set Up Nginx as Reverse Proxy (10 min)

#### 4A: Create Nginx Configuration
```bash
# Create config file
sudo tee /etc/nginx/sites-available/credit-decision << EOF
upstream streamlit_app {
    server localhost:8501;
}

server {
    listen 80 default_server;
    listen [::]:80 default_server;
    
    server_name _;
    
    # Increase timeouts for Streamlit
    proxy_read_timeout 300s;
    proxy_connect_timeout 75s;
    client_max_body_size 50M;
    
    location / {
        proxy_pass http://streamlit_app;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        
        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
    }
    
    location /_stcore/stream {
        proxy_pass http://streamlit_app/_stcore/stream;
        proxy_http_version 1.1;
        proxy_buffering off;
        proxy_request_buffering off;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "Upgrade";
    }
}
EOF

# Enable config
sudo ln -s /etc/nginx/sites-available/credit-decision /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default  # Remove default

# Test config
sudo nginx -t

# Restart Nginx
sudo systemctl restart nginx
sudo systemctl enable nginx  # Start on boot
```

#### 4B: Verify Nginx
```bash
sudo systemctl status nginx
# Should show "active (running)"
```

---

### Step 5: Create Systemd Service for Streamlit (10 min)

#### 5A: For Direct Installation (Non-Docker)
```bash
# Create service file
sudo tee /etc/systemd/system/streamlit.service << EOF
[Unit]
Description=Streamlit Credit Decision App
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/apps/credit-decision-agent
Environment="PATH=/home/ubuntu/apps/credit-decision-agent/venv/bin"
Environment="DB_HOST=sathya-database.cilmgugy4iud.us-east-1.rds.amazonaws.com"
Environment="DB_USER=admin"
Environment="DB_PASSWORD=za*~[VF7v>rgCMg6mCWc_S9JS*ZG"
Environment="DB_NAME=dev"
Environment="DB_PORT=3306"
ExecStart=/home/ubuntu/apps/credit-decision-agent/venv/bin/streamlit run credit_decision_ui.py --server.port=8501 --server.headless=true --logger.level=info
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable streamlit
sudo systemctl start streamlit

# Check status
sudo systemctl status streamlit

# View logs
sudo journalctl -u streamlit -f
```

#### 5B: For Docker Deployment
```bash
# Create service file
sudo tee /etc/systemd/system/streamlit-docker.service << EOF
[Unit]
Description=Streamlit Credit Decision App (Docker)
After=network.target docker.service
Requires=docker.service

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/apps/credit-decision-agent
ExecStart=docker run --rm \
  --name streamlit-app \
  -p 8501:8501 \
  -e DB_HOST=sathya-database.cilmgugy4iud.us-east-1.rds.amazonaws.com \
  -e DB_USER=admin \
  -e DB_PASSWORD=za*~[VF7v>rgCMg6mCWc_S9JS*ZG \
  -e DB_NAME=dev \
  -e STREAMLIT_SERVER_HEADLESS=true \
  credit-decision-agent:latest
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable streamlit-docker
sudo systemctl start streamlit-docker
sudo systemctl status streamlit-docker
```

---

### Step 6: Test Your Deployment

```bash
# From your local machine (or any browser)
# Open: http://YOUR_PUBLIC_IP

# Your IP is shown in:
# aws ec2 describe-instances --filters "Name=tag:Name,Values=credit-decision-agent" --query 'Reservations[0].Instances[0].PublicIpAddress' --output text

# OR in EC2 Console under "Public IPv4 address"
```

**You should see the Streamlit app!**

---

## Optional: Add SSL Certificate (HTTPS)

### Option 1: Free SSL with Let's Encrypt

```bash
# Install Certbot
sudo apt-get install -y certbot python3-certbot-nginx

# Get certificate (replace with your domain)
sudo certbot certonly --nginx -d your-domain.com

# Auto-renew certificates
sudo systemctl enable certbot.timer
sudo systemctl start certbot.timer

# Update Nginx config for HTTPS
sudo tee /etc/nginx/sites-available/credit-decision << 'EOF'
# ... (replace entire file with HTTPS version below)
EOF
```

### Full HTTPS Nginx Config
```nginx
# /etc/nginx/sites-available/credit-decision

upstream streamlit_app {
    server localhost:8501;
}

# Redirect HTTP to HTTPS
server {
    listen 80;
    listen [::]:80;
    server_name your-domain.com www.your-domain.com;
    return 301 https://$server_name$request_uri;
}

# HTTPS server
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    
    server_name your-domain.com www.your-domain.com;
    
    # SSL certificates from Let's Encrypt
    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;
    
    # SSL settings
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    
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
```

---

## Monitoring & Maintenance

### View Application Logs
```bash
# Systemd service logs
sudo journalctl -u streamlit -f
sudo journalctl -u streamlit -n 100

# Application logs
tail -f /var/log/credit_decision.log

# Nginx logs
tail -f /var/log/nginx/access.log
tail -f /var/log/nginx/error.log
```

### Monitor Resource Usage
```bash
# CPU and memory
top
free -h
df -h

# Network connections
netstat -tulnp | grep 8501

# Check service status
sudo systemctl status streamlit
sudo systemctl status nginx
```

### Restart Services
```bash
# Restart Streamlit
sudo systemctl restart streamlit

# Restart Nginx
sudo systemctl restart nginx

# View all running services
sudo systemctl list-units --type service
```

---

## Database Connection Test

```bash
# Test MySQL connection from EC2
mysql -h sathya-database.cilmgugy4iud.us-east-1.rds.amazonaws.com \
  -u admin -p dev -e "SELECT 1;"

# If it works, you'll see: "1"
# If it fails, check:
# 1. RDS security group allows EC2 security group
# 2. Database credentials are correct
# 3. Database is running
```

---

## Security Best Practices for EC2

### 1. Restrict Security Group
```bash
# SSH only from your IP
aws ec2 authorize-security-group-ingress \
  --group-name credit-decision-sg \
  --protocol tcp \
  --port 22 \
  --cidr YOUR_IP/32

# Or specify in console:
# SSH (22): YOUR_IP/32
# HTTP (80): 0.0.0.0/0
# HTTPS (443): 0.0.0.0/0
```

### 2. Use IAM Roles (instead of hardcoding credentials)
```bash
# Create IAM role, attach to instance
# (More complex - see AWS docs)
```

### 3. Keep System Updated
```bash
sudo apt-get update && sudo apt-get upgrade -y
sudo reboot
```

### 4. Backup Your Data
```bash
# Automated RDS backups (already enabled)
# Create manual snapshots:
aws rds create-db-snapshot \
  --db-instance-identifier credit-db \
  --db-snapshot-identifier credit-db-$(date +%Y%m%d)
```

### 5. Monitor for Intrusions
```bash
# Install CloudWatch agent (optional)
sudo apt-get install -y awscloudwatch-agent

# View CloudWatch logs from console
aws logs tail /aws/ec2/credit-decision-agent --follow
```

---

## Cost Breakdown (EC2 vs Alternatives)

### Option: EC2 t3.small + RDS
```
EC2 (t3.small):         $20.74/month
Data transfer:          $2-5/month
RDS (db.t3.micro):      $40-60/month
Elastic IP (optional):  $3.65/month
─────────────────────────────────────
TOTAL:                  $66-89/month
```

### Comparison
- **App Runner**: $37-100+ (auto-scales, no management)
- **EC2**: $66-89 (fixed cost, full control)
- **Beanstalk**: $50-200 (managed, auto-scales)
- **ECS**: $30-200 (container, flexible)

**Winner**: EC2 for consistent, predictable costs!

---

## Troubleshooting EC2 Issues

### Port 8501 not accessible
```bash
# Check if Streamlit is running
curl http://localhost:8501
ps aux | grep streamlit

# Check firewall
sudo ufw status

# Restart service
sudo systemctl restart streamlit
```

### "Connection refused" error
```bash
# Streamlit crashed - check logs
sudo journalctl -u streamlit -n 50

# Check database connectivity
mysql -h sathya-database... -u admin -p dev -e "SELECT 1;"

# Check port binding
netstat -tulnp | grep 8501
```

### App running but not accessible via browser
```bash
# Check Nginx is working
sudo systemctl status nginx
sudo nginx -t

# Check proxy settings
curl -I http://localhost   # Should hit Nginx
curl -I http://localhost:8501  # Should hit Streamlit

# Check security group
# Web console > Security Groups > credit-decision-sg
# Must have port 80 open to 0.0.0.0/0
```

### High CPU/Memory usage
```bash
# Top processes
top
# Kill runaway process if needed
kill -9 PID

# Check if multiple instances running
ps aux | grep streamlit

# Restart cleanly
sudo systemctl stop streamlit
sudo systemctl start streamlit
```

---

## Scaling EC2

### Vertical Scaling (bigger instance)
```bash
# Stop instance
aws ec2 stop-instances --instance-ids i-xxxxx

# Change instance type
aws ec2 modify-instance-attribute \
  --instance-id i-xxxxx \
  --instance-type "{\"Value\": \"t3.medium\"}"

# Start instance
aws ec2 start-instances --instance-ids i-xxxxx
```

### Horizontal Scaling (multiple instances + load balancer)
```bash
# Create Load Balancer (more complex)
# 1. Create AMI from current instance
# 2. Create Launch Template
# 3. Create Auto Scaling Group
# 4. Create Application Load Balancer
# (See AWS docs for detailed steps)
```

---

## Automatic Backups & Recovery

### Enable EC2 Backups
```bash
# Create EBS snapshot
aws ec2 create-snapshot \
  --volume-id vol-xxxxx \
  --description "Credit Decision Agent backup"

# Create AMI (machine image)
aws ec2 create-image \
  --instance-id i-xxxxx \
  --name "credit-decision-agent-backup-$(date +%Y%m%d)"
```

### Automated Backup Script
```bash
#!/bin/bash
# /home/ubuntu/backup.sh

DATE=$(date +%Y%m%d-%H%M%S)

# Backup database
mysqldump -h sathya-database... -u admin -p$DB_PASSWORD dev \
  | gzip > /backups/db-$DATE.sql.gz

# Backup application files
tar -czf /backups/app-$DATE.tar.gz /home/ubuntu/apps/credit-decision-agent

# Keep only last 30 days
find /backups -name "*.sql.gz" -mtime +30 -delete
find /backups -name "*.tar.gz" -mtime +30 -delete

echo "Backup completed: $DATE"
```

Schedule with cron:
```bash
# Run daily at 2 AM
crontab -e
# Add: 0 2 * * * /home/ubuntu/backup.sh >> /var/log/backup.log 2>&1
```

---

## Quick Recap: EC2 Advantages

✅ **Fixed, predictable monthly cost**  
✅ **Full server control & SSH access**  
✅ **Better for always-on applications**  
✅ **Easy to scale up single instance**  
✅ **Can run additional services (cron, workers, etc.)**  
✅ **Standard Linux server - no vendor lock-in**  

---

## Quick Recap: EC2 Disadvantages

❌ **Must manage yourself** (security patches, restarts)  
❌ **No automatic scaling** (need load balancer for that)  
❌ **Manual deployment** (no CI/CD built-in)  
❌ **Downtime during restarts** (unless multi-instance)  

---

## Summary: EC2 in 6 Steps

1. **Launch instance** (t3.small) - 5 min
2. **SSH & install** dependencies - 10 min
3. **Clone app** & install requirements - 5 min
4. **Configure environment** variables - 2 min
5. **Set up Nginx** reverse proxy - 10 min
6. **Create Systemd service** - 5 min

**Total: 37 minutes from zero to running app!**
