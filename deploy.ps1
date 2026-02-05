# AWS Deployment Helper Script for Credit Decision Agent (PowerShell)
# This script helps automate the deployment process

param(
    [string]$DeploymentMethod = "app-runner"
)

$ErrorActionPreference = "Stop"

# Configuration
$Region = "us-east-1"
$ServiceName = "credit-decision-agent"
$ECRRepositoryName = "credit-decision-agent"

Write-Host "===============================================" -ForegroundColor Green
Write-Host "AWS Deployment Helper - Credit Decision Agent" -ForegroundColor Green
Write-Host "===============================================" -ForegroundColor Green
Write-Host "Deployment Method: $DeploymentMethod"
Write-Host "Region: $Region"
Write-Host ""

# Check AWS CLI
if (-not (Get-Command aws -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: AWS CLI not found. Please install it first." -ForegroundColor Red
    exit 1
}

Write-Host "[1/4] Validating AWS credentials..." -ForegroundColor Yellow
try {
    $identity = aws sts get-caller-identity --output json | ConvertFrom-Json
    $AccountId = $identity.Account
    Write-Host "OK - Account: $AccountId" -ForegroundColor Green
} catch {
    Write-Host "ERROR: AWS credentials not configured" -ForegroundColor Red
    exit 1
}

switch ($DeploymentMethod) {
    "app-runner" {
        Write-Host ""
        Write-Host "[2/4] Preparing Docker image for App Runner..." -ForegroundColor Yellow
        
        # Create ECR repository
        Write-Host "Creating ECR repository..."
        aws ecr create-repository `
            --repository-name $ECRRepositoryName `
            --region $Region `
            --image-scanning-configuration scanOnPush=true `
            2>$null | Out-Null
        
        Write-Host "OK" -ForegroundColor Green
        
        Write-Host ""
        Write-Host "[3/4] Building and pushing Docker image..." -ForegroundColor Yellow
        
        # Login to ECR
        $LoginCmd = aws ecr get-login-password --region $Region
        $LoginCmd | docker login --username AWS --password-stdin "$AccountId.dkr.ecr.$Region.amazonaws.com" 2>$null
        
        # Build image
        Write-Host "Building Docker image..."
        docker build -t $ECRRepositoryName .
        
        # Tag image
        $ImageUri = "$AccountId.dkr.ecr.$Region.amazonaws.com/$ECRRepositoryName`:latest"
        docker tag "${ECRRepositoryName}:latest" $ImageUri
        
        # Push image
        Write-Host "Pushing image to ECR..."
        docker push $ImageUri
        
        Write-Host "OK" -ForegroundColor Green
        
        Write-Host ""
        Write-Host "[4/4] Creating AWS Secrets Manager secret..." -ForegroundColor Yellow
        
        # Create secrets
        $SecretJson = @{
            host = "sathya-database.cilmgugy4iud.us-east-1.rds.amazonaws.com"
            username = "admin"
            password = "YOUR_PASSWORD_HERE"
            database = "dev"
            port = "3306"
        } | ConvertTo-Json
        
        aws secretsmanager create-secret `
            --name credit-decision-db-secret `
            --region $Region `
            --secret-string $SecretJson `
            2>$null | Out-Null
        
        Write-Host "OK" -ForegroundColor Green
        
        Write-Host ""
        Write-Host "Deployment files ready!" -ForegroundColor Green
        Write-Host "Image URI: $ImageUri" -ForegroundColor Cyan
        Write-Host ""
        Write-Host "Next steps:" -ForegroundColor Yellow
        Write-Host "1. Go to AWS App Runner console"
        Write-Host "2. Create service with the above image URI"
        Write-Host "3. Set port to 8501"
        Write-Host "4. Add environment variables from .env file"
        Write-Host "5. Deploy and wait for service to start"
    }
    
    "beanstalk" {
        Write-Host ""
        Write-Host "[2/4] Installing Elastic Beanstalk CLI..." -ForegroundColor Yellow
        pip install awsebcli --quiet
        Write-Host "OK" -ForegroundColor Green
        
        Write-Host ""
        Write-Host "[3/4] Initializing Elastic Beanstalk..." -ForegroundColor Yellow
        
        if (-not (Test-Path ".elasticbeanstalk")) {
            eb init -p python-3.11 $ServiceName --region $Region
        }
        
        Write-Host "OK" -ForegroundColor Green
        
        Write-Host ""
        Write-Host "[4/4] Setting environment variables..." -ForegroundColor Yellow
        
        eb setenv `
            DB_HOST="sathya-database.cilmgugy4iud.us-east-1.rds.amazonaws.com" `
            DB_USER="admin" `
            DB_PASSWORD="YOUR_PASSWORD_HERE" `
            DB_NAME="dev" `
            DB_PORT="3306"
        
        Write-Host "OK" -ForegroundColor Green
        
        Write-Host ""
        Write-Host "Deployment ready!" -ForegroundColor Green
        Write-Host "To deploy, run:" -ForegroundColor Yellow
        Write-Host "eb create credit-decision-env --instance-type t3.medium"
        Write-Host "eb deploy"
    }
    
    "ecs" {
        Write-Host ""
        Write-Host "[2/4] Creating ECS cluster..." -ForegroundColor Yellow
        
        aws ecs create-cluster `
            --cluster-name "$ServiceName-cluster" `
            --region $Region `
            2>$null | Out-Null
        
        Write-Host "OK" -ForegroundColor Green
        
        Write-Host ""
        Write-Host "[3/4] Preparing Docker image..." -ForegroundColor Yellow
        
        aws ecr create-repository `
            --repository-name $ECRRepositoryName `
            --region $Region `
            2>$null | Out-Null
        
        $LoginCmd = aws ecr get-login-password --region $Region
        $LoginCmd | docker login --username AWS --password-stdin "$AccountId.dkr.ecr.$Region.amazonaws.com" 2>$null
        
        docker build -t $ECRRepositoryName .
        $ImageUri = "$AccountId.dkr.ecr.$Region.amazonaws.com/$ECRRepositoryName`:latest"
        docker tag "${ECRRepositoryName}:latest" $ImageUri
        docker push $ImageUri
        
        Write-Host "OK" -ForegroundColor Green
        
        Write-Host ""
        Write-Host "[4/4] Task definition creation..." -ForegroundColor Yellow
        Write-Host "Task definition requires manual setup. See AWS_DEPLOYMENT_GUIDE.md" -ForegroundColor Cyan
        Write-Host "OK" -ForegroundColor Green
    }
    
    default {
        Write-Host "ERROR: Invalid deployment method: $DeploymentMethod" -ForegroundColor Red
        Write-Host "Use: app-runner, beanstalk, or ecs"
        exit 1
    }
}

Write-Host ""
Write-Host "===============================================" -ForegroundColor Green
Write-Host "Deployment preparation complete!" -ForegroundColor Green
Write-Host "===============================================" -ForegroundColor Green
