# AWS Deployment Checklist

## Pre-Deployment (Do These First)

- [ ] Read `DEPLOYMENT_SUMMARY.md` (5 min)
- [ ] Create GitHub account if not already done
- [ ] Install AWS CLI: `pip install awscli`
- [ ] Install Docker: https://www.docker.com/products/docker-desktop/
- [ ] Run `aws configure` with your AWS credentials

## Files Created & Updated ✅

- [x] `Dockerfile` - Container specification
- [x] `.dockerignore` - Exclude unnecessary files
- [x] `requirements.txt` - Updated with all dependencies
- [x] `Procfile` - Elastic Beanstalk config
- [x] `.ebextensions/python.config` - EB settings
- [x] `.streamlit/config.toml` - Streamlit production config
- [x] `.gitignore` - Prevent secret leaks
- [x] `credit_decision_ui.py` - Updated to load env vars
- [x] `deploy.sh` - Bash deployment script
- [x] `deploy.ps1` - PowerShell deployment script
- [x] `AWS_DEPLOYMENT_GUIDE.md` - Full 200+ line guide
- [x] `AWS_QUICK_REFERENCE.md` - Quick command reference
- [x] `DEPLOYMENT_SUMMARY.md` - This summary

## Choose Your Deployment Method

### Option A: App Runner ⭐ **RECOMMENDED (Start here)**
**Time: ~45 minutes | Cost: $37-100/month | Difficulty: Easy**

```bash
# Step 1: Push to GitHub (5 min)
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR_USERNAME/credit-decision-agent.git
git push -u origin main

# Step 2: Create Secrets (5 min)
aws secretsmanager create-secret --name credit-decision-db-secret --secret-string '{...}'

# Step 3: Build & Push Docker (10 min)
aws ecr create-repository --repository-name credit-decision-agent
aws ecr get-login-password | docker login --username AWS --password-stdin $ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com
docker build -t credit-decision-agent .
docker tag credit-decision-agent:latest $ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/credit-decision-agent:latest
docker push $ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/credit-decision-agent:latest

# Step 4: Deploy via AWS Console (10 min)
# Go to App Runner console > Create Service > Use image URI above
```

### Option B: Elastic Beanstalk
**Time: 1 hour | Cost: $50-200/month | Difficulty: Medium**

```bash
pip install awsebcli
eb init -p python-3.11 credit-decision-agent --region us-east-1
eb setenv DB_HOST=... DB_USER=... DB_PASSWORD=... DB_NAME=dev DB_PORT=3306
eb create credit-decision-env --instance-type t3.medium
eb deploy
```

### Option C: ECS Fargate
**Time: 2+ hours | Cost: $30-200/month | Difficulty: Hard**
See `AWS_DEPLOYMENT_GUIDE.md` for detailed steps

---

## Deployment Walkthrough (App Runner)

### Before You Start
- [ ] AWS Account setup complete
- [ ] AWS CLI configured (`aws configure`)
- [ ] Docker installed and running
- [ ] Have your DB password: `za*~[VF7v>rgCMg6mCWc_S9JS*ZG`

### Step 1: Prepare Code
```bash
cd your-project-directory

# Verify requirements.txt is updated
cat requirements.txt | grep streamlit

# Verify Docker builds locally
docker build -t test-app .
docker run -p 8501:8501 -e DB_HOST=sathya-database.cilmgugy4iud.us-east-1.rds.amazonaws.com -e DB_USER=admin -e DB_PASSWORD=your_password test-app
# Should see "Streamlit app is running"
```
**Time: 5 min | Checkpoints: ✓ Docker builds locally**

### Step 2: Set Up AWS Secrets Manager
```bash
# Get your AWS Account ID
aws sts get-caller-identity --query Account --output text

# Create secret (replace PASSWORD)
aws secretsmanager create-secret \
    --name credit-decision-db-secret \
    --secret-string '{
        "host": "sathya-database.cilmgugy4iud.us-east-1.rds.amazonaws.com",
        "username": "admin",
        "password": "za*~[VF7v>rgCMg6mCWc_S9JS*ZG",
        "database": "dev",
        "port": "3306"
    '

# Verify secret was created
aws secretsmanager list-secrets
```
**Time: 5 min | Checkpoints: ✓ Secret created**

### Step 3: Build & Push Docker Image
```bash
# Get account ID
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REGION="us-east-1"

# Create ECR repository
aws ecr create-repository --repository-name credit-decision-agent --region $REGION

# Login to ECR
aws ecr get-login-password --region $REGION | \
    docker login --username AWS --password-stdin $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com

# Build the image
docker build -t credit-decision-agent .

# Tag it
docker tag credit-decision-agent:latest $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/credit-decision-agent:latest

# Push to ECR (this may take 2-5 minutes)
docker push $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/credit-decision-agent:latest

# Verify push succeeded
aws ecr describe-images --repository-name credit-decision-agent
```
**Time: 10 min | Checkpoints: ✓ Image in ECR**

### Step 4: Deploy to App Runner
**Via AWS Console (easier):**
1. Go to https://console.aws.amazon.com/apprunner/
2. Click **"Create service"**
3. **Source**: Select **"Container registry"**
4. **Provider**: Select **"Amazon ECR"**
5. **Repository**: Select your region, then `credit-decision-agent`
6. **Image tag**: `latest`
7. Click **"Next"**
8. **Service name**: `credit-decision-agent`
9. **Port**: `8501`
10. **CPU**: `0.5 vCPU` (fine for light usage)
11. **Memory**: `1 GB`
12. **Environment variables** - Add these:
    - `STREAMLIT_SERVER_HEADLESS` = `true`
    - `STREAMLIT_SERVER_PORT` = `8501`
    - `STREAMLIT_SERVER_ENABLECORS` = `false`
    - `STREAMLIT_CLIENT_TOOLBARMODE` = `minimal`
13. Click **"Next"** → **"Create & Deploy"**
14. Wait 3-5 minutes for deployment to complete

**Time: 10 min | Checkpoints: ✓ Service created and running**

### Step 5: Test Your Deployment
1. Copy the **"Service URL"** from App Runner console
2. Open it in browser
3. You should see the credit decision form
4. Fill in test data and submit
5. Verify it processes and shows results

**Time: 5 min | Checkpoints: ✓ App works in browser**

---

## Verify Everything Works

### Checklist
- [ ] App is accessible at the public URL
- [ ] Sidebar form is visible and responsive
- [ ] Can enter applicant information
- [ ] Can click "Process Application"
- [ ] Application is inserted into database
- [ ] Agent processes the request
- [ ] Results display in tabs
- [ ] No error messages on screen

### If Something's Wrong

**App won't load?**
```bash
# Check logs
aws logs tail /aws/apprunner/credit-decision-agent/default_stream --follow
```

**Forms not working?**
```bash
# Check it works locally first
docker run -p 8501:8501 credit-decision-agent
# Visit http://localhost:8501
```

**Database errors?**
```bash
# Test connection
mysql -h sathya-database.cilmgugy4iud.us-east-1.rds.amazonaws.com -u admin -p dev
# Check credentials in Secrets Manager
aws secretsmanager get-secret-value --secret-id credit-decision-db-secret
```

---

## Cost Check

### Estimated Monthly Cost
```
App Runner (minimal traffic):        $37
ECR Storage:                         $5
RDS (current):                       $50
CloudWatch Logs:                     $5
Data Transfer:                       $2
─────────────────────────────────────────
TOTAL:                               ~$99/month
```

*Scale up if needed - costs scale with usage*

---

## Maintenance Checklist

### Weekly
- [ ] Monitor CloudWatch logs for errors
- [ ] Check App Runner CPU/memory usage

### Monthly
- [ ] Review costs in AWS Billing
- [ ] Back up database (`aws rds create-db-snapshot`)
- [ ] Check for security updates

### Quarterly
- [ ] Review performance metrics
- [ ] Consider scaling (if needed)
- [ ] Update dependencies in requirements.txt

---

## Helpful Commands Reference

```bash
# View deployment logs
aws logs tail /aws/apprunner/credit-decision-agent/default_stream --follow

# Get app URL
aws apprunner list-services | grep ServiceUrl

# Stop service temporarily
aws apprunner pause-service --connection-arn <arn>

# Resume service
aws apprunner resume-service --connection-arn <arn>

# View image in ECR
aws ecr describe-images --repository-name credit-decision-agent

# Delete service (careful!)
aws apprunner delete-service --service-arn <arn>
```

---

## Success Markers

✅ **You're successfully deployed if:**
- [ ] Public URL is accessible
- [ ] Form displays and works
- [ ] Database operations succeed
- [ ] Agent processes complete
- [ ] Results show on screen
- [ ] CloudWatch logs are clean (no errors)
- [ ] Response time is <10 seconds

---

## Next Steps (After Deployment Works)

1. **Add Custom Domain**
   - Buy domain (Route 53, GoDaddy, etc.)
   - Point to CloudFront/App Runner

2. **Set Up Monitoring**
   - CloudWatch Alarms
   - Error tracking (optional)
   - Performance dashboards

3. **Enable HTTPS**
   - AWS Certificate Manager (ACM)
   - CloudFront distribution

4. **Scale for Production**
   - Multiple App Runner replicas
   - RDS Multi-AZ
   - Caching layer

---

## Support

- **AWS Documentation**: https://docs.aws.amazon.com
- **Streamlit Docs**: https://docs.streamlit.io
- **This Project**: Check the markdown files in the project root

---

**Status**: ✅ Ready to deploy!

**Next Action**: Start with **Step 1** above.
