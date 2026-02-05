# AWS Deployment Guide for OrchestrateAI Credit Decision Agent

## Overview
This guide covers deploying the Streamlit app to AWS using three approaches:
1. **AWS App Runner** (Recommended - Easiest)
2. **AWS Elastic Beanstalk** (Good for scales, more control)
3. **Amazon ECS + Fargate** (Most flexible, containers)

---

## Prerequisites

### Required
- AWS Account with appropriate permissions (EC2, RDS, IAM, etc.)
- AWS CLI installed and configured: https://aws.amazon.com/cli/
- Docker installed locally (for App Runner and ECS)
- Git repository (push code to GitHub/CodeCommit)

### AWS Credentials Setup
```bash
aws configure
# Enter your AWS Access Key ID
# Enter your AWS Secret Access Key
# Choose region: us-east-1
```

---

## Project Structure Changes Needed

### 1. **Update requirements.txt** ✅ (Already done)
```bash
pip freeze > requirements.txt
```

### 2. **Update .env handling** (Use AWS Secrets Manager or Parameter Store)
Instead of `.env` file, use:
- **AWS Secrets Manager** (Recommended for sensitive data)
- **AWS Systems Manager Parameter Store** (For less sensitive config)
- **Environment variables in ECR/ECS** (Via task definition or AppRunner config)

### 3. **Update credit_decision_ui.py** for AWS
```python
# Add at the top after imports
import boto3

def load_aws_secrets():
    """Load secrets from AWS Secrets Manager"""
    try:
        secrets_client = boto3.client('secretsmanager', region_name='us-east-1')
        secret = secrets_client.get_secret_value(SecretId='credit-decision-db-secret')
        db_creds = json.loads(secret['SecretString'])
        os.environ['DB_HOST'] = db_creds['host']
        os.environ['DB_USER'] = db_creds['username']
        os.environ['DB_PASSWORD'] = db_creds['password']
    except Exception as e:
        print(f"Warning: Could not load AWS secrets: {e}")
        # Fallback to .env or environment variables
        pass

# Call at startup (after logging setup)
load_aws_secrets()
```

---

## Option 1: AWS App Runner (Recommended - Easiest ⭐)

### Step-by-Step Deployment

#### 1. Push Code to GitHub
```bash
# Initialize git (if not already done)
git init
git add .
git commit -m "Initial commit"

# Create repo on GitHub and push
git remote add origin https://github.com/YOUR_USERNAME/AIAgents.git
git push -u origin main
```

#### 2. Create AWS Secrets Manager Secret
```bash
aws secretsmanager create-secret \
    --name credit-decision-db-secret \
    --secret-string '{
        "host": "sathya-database.cilmgugy4iud.us-east-1.rds.amazonaws.com",
        "username": "admin",
        "password": "za*~[VF7v>rgCMg6mCWc_S9JS*ZG",
        "database": "dev",
        "port": "3306"
    }'
```

#### 3. Create ECR Repository
```bash
aws ecr create-repository --repository-name credit-decision-agent
```

#### 4. Build and Push Docker Image
```bash
# Login to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com

# Build image
docker build -t credit-decision-agent .

# Tag image
docker tag credit-decision-agent:latest <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/credit-decision-agent:latest

# Push to ECR
docker push <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/credit-decision-agent:latest
```

#### 5. Create App Runner Service via AWS Console
1. Go to **AWS App Runner** console
2. Click **Create Service**
3. **Source**: Choose "Container registry"
4. **Provider**: Amazon ECR
5. **Container image URI**: `<ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/credit-decision-agent:latest`
6. **Service name**: `credit-decision-agent`
7. **Port**: `8501`
8. **Environment variables**:
   ```
   STREAMLIT_SERVER_HEADLESS=true
   STREAMLIT_SERVER_PORT=8501
   STREAMLIT_SERVER_ENABLECORS=false
   CREDIT_DECISION_LOG=/tmp/credit_decision.log
   ```
9. Click **Create & Deploy**

---

## Option 2: AWS Elastic Beanstalk (More Control)

### Step-by-Step Deployment

#### 1. Install Elastic Beanstalk CLI
```bash
pip install awsebcli --upgrade --user
```

#### 2. Create Procfile
Create `Procfile` in project root:
```
web: streamlit run credit_decision_ui.py --server.port=8501 --server.headless=true
```

#### 3. Create .ebextensions/python.config
Create `.ebextensions/python.config`:
```yaml
option_settings:
  aws:elasticbeanstalk:container:python:
    WSGIPath: "app:app"
  aws:elasticbeanstalk:application:environment:
    STREAMLIT_SERVER_HEADLESS: "true"
    STREAMLIT_SERVER_PORT: "8501"
```

#### 4. Initialize EB Project
```bash
eb init -p python-3.11 credit-decision-agent --region us-east-1
```

#### 5. Set Environment Variables
```bash
eb setenv DB_HOST=sathya-database.cilmgugy4iud.us-east-1.rds.amazonaws.com
eb setenv DB_USER=admin
eb setenv DB_PASSWORD=za*~[VF7v>rgCMg6mCWc_S9JS*ZG
eb setenv DB_NAME=dev
eb setenv DB_PORT=3306
```

#### 6. Create and Deploy
```bash
eb create credit-decision-env --instance-type t3.medium
eb deploy
```

#### 7. View Logs
```bash
eb logs
eb open  # Opens app in browser
```

---

## Option 3: Amazon ECS + Fargate (Most Flexible)

### Step-by-Step Deployment

#### 1. Create ECS Cluster
```bash
aws ecs create-cluster --cluster-name credit-decision-cluster
```

#### 2. Create Task Definition
Create `ecs-task-definition.json`:
```json
{
  "family": "credit-decision-agent",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "256",
  "memory": "512",
  "containerDefinitions": [
    {
      "name": "credit-decision-agent",
      "image": "<ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/credit-decision-agent:latest",
      "portMappings": [
        {
          "containerPort": 8501,
          "hostPort": 8501,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {
          "name": "STREAMLIT_SERVER_HEADLESS",
          "value": "true"
        },
        {
          "name": "STREAMLIT_SERVER_PORT",
          "value": "8501"
        }
      ],
      "secrets": [
        {
          "name": "DB_HOST",
          "valueFrom": "arn:aws:secretsmanager:us-east-1:ACCOUNT_ID:secret:credit-decision-db-secret:host::"
        },
        {
          "name": "DB_USER",
          "valueFrom": "arn:aws:secretsmanager:us-east-1:ACCOUNT_ID:secret:credit-decision-db-secret:username::"
        },
        {
          "name": "DB_PASSWORD",
          "valueFrom": "arn:aws:secretsmanager:us-east-1:ACCOUNT_ID:secret:credit-decision-db-secret:password::"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/credit-decision-agent",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "ecs"
        }
      }
    }
  ],
  "executionRoleArn": "arn:aws:iam::ACCOUNT_ID:role/ecsTaskExecutionRole"
}
```

#### 3. Register Task Definition
```bash
aws ecs register-task-definition --cli-input-json file://ecs-task-definition.json
```

#### 4. Create Fargate Service
```bash
aws ecs create-service \
  --cluster credit-decision-cluster \
  --service-name credit-decision-service \
  --task-definition credit-decision-agent \
  --desired-count 1 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxxxx],securityGroups=[sg-xxxxx],assignPublicIp=ENABLED}" \
  --load-balancers "targetGroupArn=arn:aws:elasticloadbalancing:us-east-1:ACCOUNT_ID:targetgroup/credit-decision/xxxxx,containerName=credit-decision-agent,containerPort=8501"
```

---

## Critical Changes for Production

### 1. **Database Connection**
- ✅ Use AWS RDS (already configured)
- Keep credentials in AWS Secrets Manager (not in code)
- Use IAM database authentication (optional, more secure)

### 2. **Logging**
- ✅ Use CloudWatch Logs instead of file logs
- Update code:
```python
import logging
from pythonjsonlogger import jsonlogger

handler = logging.StreamHandler()
formatter = jsonlogger.JsonFormatter()
handler.setFormatter(formatter)
logger.addHandler(handler)
```

### 3. **Scale Considerations**
- Streamlit is single-threaded (not ideal for multi-user)
- Use **Snowflake's Streamlit** for better scaling
- Or run multiple replicas with load balancer
- Set `min_replicas=2` in App Runner for auto-scaling

### 4. **Security**
- Enable SSL/TLS (CloudFront + Certificate Manager)
- Restrict RDS security group to only Streamlit app
- Use IAM roles instead of hardcoded credentials
- Enable CloudTrail for audit logs

### 5. **Cost Optimization**
- App Runner: ~$37/month (minimal usage)
- Elastic Beanstalk: ~$50-200/month depending on instance type
- ECS Fargate: ~$30/month (light usage)
- RDS: ~$40-100/month (db.t3.micro)
- **Total estimated: $100-200/month**

---

## Post-Deployment Checklist

- [ ] App loads successfully
- [ ] Database connection works
- [ ] Can submit credit applications
- [ ] Results display correctly
- [ ] Logs are being sent to CloudWatch
- [ ] Set up CloudWatch alarms
- [ ] Enable auto-scaling (if needed)
- [ ] Configure custom domain (Route 53)
- [ ] Set up backup strategy for database
- [ ] Enable AWS WAF for security

---

## Monitoring & Logs

### View CloudWatch Logs
```bash
aws logs tail /ecs/credit-decision-agent --follow
```

### Set Up CloudWatch Alarms
```bash
aws cloudwatch put-metric-alarm \
  --alarm-name credit-decision-high-error-rate \
  --alarm-description "Alert if error rate is high" \
  --metric-name ErrorCount \
  --namespace AWS/AppRunner \
  --statistic Sum \
  --period 300 \
  --threshold 10 \
  --comparison-operator GreaterThanThreshold
```

---

## Rollback Strategy

```bash
# App Runner
aws apprunner start-deployment --service-arn <service-arn> --image-repository<previous-image>

# Elastic Beanstalk
eb swap

# ECS
aws ecs update-service --cluster credit-decision-cluster \
  --service credit-decision-service \
  --force-new-deployment
```

---

## Quick Summary

| Method | Setup Time | Cost | Scalability | Best For |
|--------|-----------|------|-------------|----------|
| **App Runner** | 30 min | Low ($37+) | Medium | Quick deployment, managed service |
| **Elastic Beanstalk** | 1 hour | Medium ($50+) | Good | Traditional Python web apps |
| **ECS Fargate** | 2 hours | Medium ($30+) | Excellent | Custom configurations, full control |

**Recommended: Start with App Runner for simplicity, migrate to ECS as you scale.**
