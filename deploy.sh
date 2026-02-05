#!/bin/bash

# AWS Deployment Helper Script for Credit Decision Agent
# This script helps automate the deployment process

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
REGION="us-east-1"
SERVICE_NAME="credit-decision-agent"
DEPLOYMENT_METHOD="${1:-app-runner}"  # app-runner, beanstalk, or ecs

echo -e "${YELLOW}AWS Deployment Helper - Credit Decision Agent${NC}"
echo "Deployment Method: $DEPLOYMENT_METHOD"
echo "Region: $REGION"
echo ""

# Check AWS CLI
if ! command -v aws &> /dev/null; then
    echo -e "${RED}ERROR: AWS CLI not found. Please install it first.${NC}"
    exit 1
fi

echo -e "${GREEN}[1/4] Validating AWS credentials...${NC}"
aws sts get-caller-identity > /dev/null 2>&1 || {
    echo -e "${RED}ERROR: AWS credentials not configured${NC}"
    exit 1
}
echo -e "${GREEN}OK${NC}"

# Get AWS Account ID
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo "AWS Account ID: $ACCOUNT_ID"

case $DEPLOYMENT_METHOD in
    app-runner)
        echo -e "\n${YELLOW}[2/4] Preparing Docker image for App Runner...${NC}"
        
        # Create ECR repository
        echo "Creating ECR repository..."
        aws ecr create-repository \
            --repository-name $SERVICE_NAME \
            --region $REGION \
            --image-scanning-configuration scanOnPush=true \
            2>/dev/null || echo "Repository already exists"
        
        echo -e "${GREEN}OK${NC}"
        
        echo -e "\n${YELLOW}[3/4] Building and pushing Docker image...${NC}"
        
        # Login to ECR
        aws ecr get-login-password --region $REGION | \
            docker login --username AWS --password-stdin ${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com
        
        # Build image
        docker build -t $SERVICE_NAME .
        
        # Tag image
        docker tag ${SERVICE_NAME}:latest \
            ${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${SERVICE_NAME}:latest
        
        # Push image
        docker push ${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${SERVICE_NAME}:latest
        
        echo -e "${GREEN}OK${NC}"
        
        echo -e "\n${YELLOW}[4/4] Creating AWS Secrets Manager secret...${NC}"
        
        # Create secrets
        aws secretsmanager create-secret \
            --name credit-decision-db-secret \
            --region $REGION \
            --secret-string '{
                "host": "sathya-database.cilmgugy4iud.us-east-1.rds.amazonaws.com",
                "username": "admin",
                "password": "YOUR_PASSWORD_HERE",
                "database": "dev",
                "port": "3306"
            }' \
            2>/dev/null || echo "Secret already exists"
        
        echo -e "${GREEN}OK${NC}"
        
        echo -e "\n${GREEN}Deployment files ready!${NC}"
        echo "Image URI: ${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${SERVICE_NAME}:latest"
        echo -e "\n${YELLOW}Next steps:${NC}"
        echo "1. Go to AWS App Runner console"
        echo "2. Create service with the above image URI"
        echo "3. Set port to 8501"
        echo "4. Add environment variables from .env file"
        echo "5. Deploy and wait for service to start"
        ;;
        
    beanstalk)
        echo -e "\n${YELLOW}[2/4] Installing Elastic Beanstalk CLI...${NC}"
        pip install awsebcli --quiet
        echo -e "${GREEN}OK${NC}"
        
        echo -e "\n${YELLOW}[3/4] Initializing Elastic Beanstalk...${NC}"
        
        if [ ! -d ".elasticbeanstalk" ]; then
            eb init -p python-3.11 $SERVICE_NAME --region $REGION --interactive
        fi
        
        echo -e "${GREEN}OK${NC}"
        
        echo -e "\n${YELLOW}[4/4] Setting environment variables...${NC}"
        
        eb setenv \
            DB_HOST=sathya-database.cilmgugy4iud.us-east-1.rds.amazonaws.com \
            DB_USER=admin \
            DB_PASSWORD='YOUR_PASSWORD_HERE' \
            DB_NAME=dev \
            DB_PORT=3306
        
        echo -e "${GREEN}OK${NC}"
        
        echo -e "\n${GREEN}Deployment ready!${NC}"
        echo -e "${YELLOW}To deploy, run:${NC}"
        echo "eb create credit-decision-env --instance-type t3.medium"
        echo "eb deploy"
        ;;
        
    ecs)
        echo -e "\n${YELLOW}[2/4] Creating ECS cluster...${NC}"
        
        aws ecs create-cluster \
            --cluster-name $SERVICE_NAME-cluster \
            --region $REGION \
            2>/dev/null || echo "Cluster already exists"
        
        echo -e "${GREEN}OK${NC}"
        
        echo -e "\n${YELLOW}[3/4] Preparing Docker image...${NC}"
        
        aws ecr create-repository \
            --repository-name $SERVICE_NAME \
            --region $REGION \
            2>/dev/null || echo "Repository already exists"
        
        aws ecr get-login-password --region $REGION | \
            docker login --username AWS --password-stdin ${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com
        
        docker build -t $SERVICE_NAME .
        docker tag ${SERVICE_NAME}:latest \
            ${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${SERVICE_NAME}:latest
        docker push ${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${SERVICE_NAME}:latest
        
        echo -e "${GREEN}OK${NC}"
        
        echo -e "\n${YELLOW}[4/4] Creating task definition...${NC}"
        
        # This is a simplified version - you'll need to customize for your setup
        echo "Task definition creation requires manual setup. See AWS_DEPLOYMENT_GUIDE.md"
        
        echo -e "${GREEN}OK${NC}"
        ;;
        
    *)
        echo -e "${RED}ERROR: Invalid deployment method: $DEPLOYMENT_METHOD${NC}"
        echo "Use: app-runner, beanstalk, or ecs"
        exit 1
        ;;
esac

echo -e "\n${GREEN}======================================${NC}"
echo -e "${GREEN}Deployment preparation complete!${NC}"
echo -e "${GREEN}======================================${NC}"
