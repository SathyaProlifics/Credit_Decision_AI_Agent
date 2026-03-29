################################################################################
# OrchestrateAI – Credit Decision Agent
# Terraform: RDS MySQL (public) + security group + table init
################################################################################

terraform {
  required_version = ">= 1.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    null = {
      source  = "hashicorp/null"
      version = "~> 3.0"
    }
    local = {
      source  = "hashicorp/local"
      version = "~> 2.0"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "OrchestrateAI"
      Environment = var.environment
      ManagedBy   = "Terraform"
    }
  }
}

################################################################################
# Data: reuse the default VPC + its public subnets
################################################################################

data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

################################################################################
# Security Group – allow MySQL from anywhere (public access)
################################################################################

resource "aws_security_group" "rds_public" {
  name        = "${var.project_name}-rds-public-sg"
  description = "Allow public MySQL access for Credit Decision Agent"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description = "MySQL from anywhere"
    from_port   = 3306
    to_port     = 3306
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project_name}-rds-public-sg"
  }
}

################################################################################
# RDS Subnet Group (uses all default subnets)
################################################################################

resource "aws_db_subnet_group" "main" {
  name       = "${var.project_name}-subnet-group"
  subnet_ids = data.aws_subnets.default.ids

  tags = {
    Name = "${var.project_name}-subnet-group"
  }
}

################################################################################
# RDS MySQL Instance – publicly accessible
################################################################################

resource "aws_db_instance" "credit_db" {
  identifier = "${var.project_name}-db"

  # Engine
  engine         = "mysql"
  engine_version = "8.0"
  instance_class = var.db_instance_class

  # Storage
  allocated_storage     = 20
  max_allocated_storage = 100
  storage_type          = "gp2"
  storage_encrypted     = false # set true for production

  # Credentials
  db_name  = var.db_name
  username = var.db_username
  password = var.db_password
  port     = 3306

  # Networking – public
  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds_public.id]
  publicly_accessible    = true
  multi_az               = false

  # Backups / maintenance
  backup_retention_period = 1
  skip_final_snapshot     = true
  deletion_protection     = false

  # Performance Insights off (saves cost for dev)
  performance_insights_enabled = false

  tags = {
    Name = "${var.project_name}-db"
  }
}

################################################################################
# Wait for RDS to be ready, then create the schema + table
################################################################################

resource "null_resource" "init_db" {
  depends_on = [aws_db_instance.credit_db]

  # Re-run if the RDS endpoint changes
  triggers = {
    db_endpoint = aws_db_instance.credit_db.endpoint
  }

  provisioner "local-exec" {
    interpreter = ["PowerShell", "-Command"]
    command     = <<-PS
      Write-Host "Waiting for RDS to accept connections..."
      Start-Sleep -Seconds 30

      $env:MYSQL_PWD = "${var.db_password}"
      $host = "${aws_db_instance.credit_db.address}"
      $port = "3306"
      $user = "${var.db_username}"
      $db   = "${var.db_name}"
      $sql  = Join-Path $PSScriptRoot ".." "terraform" "init_db.sql"

      # Try mysql CLI (must be on PATH)
      if (Get-Command mysql -ErrorAction SilentlyContinue) {
        mysql -h $host -P $port -u $user --password="${var.db_password}" $db < $sql
        Write-Host "Database initialised via mysql CLI."
      } else {
        Write-Warning "mysql CLI not found on PATH - skipping table creation."
        Write-Warning "Run manually:  mysql -h $host -P $port -u $user -p $db < terraform/init_db.sql"
      }
    PS
  }
}

################################################################################
# Write updated .env back to the project root
################################################################################

resource "local_file" "env_file" {
  depends_on = [aws_db_instance.credit_db]

  filename        = "${path.module}/../.env"
  file_permission = "0600"

  content = <<-ENV
# Database Configuration  (managed by Terraform – do not edit manually)
DB_HOST=${aws_db_instance.credit_db.address}
DB_PORT=3306
DB_NAME=${var.db_name}
DB_USER=${var.db_username}
DB_PASSWORD=${var.db_password}

# ==================== LLM PROVIDER CONFIGURATION ====================
# Select LLM providers and models for each agent
# Options: bedrock, openai, azure_openai

# AWS Region for Bedrock
AWS_REGION=${var.aws_region}

# Bedrock API Configuration
BEDROCK_API_KEY=

# ---- DATA COLLECTOR AGENT ----
# Fast model for data validation/completeness checks
LLM_DATA_COLLECTOR_PROVIDER=bedrock
LLM_DATA_COLLECTOR_MODEL=anthropic.claude-3-haiku-20240307-v1:0
LLM_DATA_COLLECTOR_MAX_TOKENS=1000
LLM_DATA_COLLECTOR_TEMPERATURE=0.3

# ---- RISK ASSESSOR AGENT ----
# Haiku is fast enough for structured risk scoring
LLM_RISK_ASSESSOR_PROVIDER=bedrock
LLM_RISK_ASSESSOR_MODEL=anthropic.claude-3-haiku-20240307-v1:0
LLM_RISK_ASSESSOR_MAX_TOKENS=2000
LLM_RISK_ASSESSOR_TEMPERATURE=0.3

# ---- DECISION MAKER AGENT ----
# Claude 3.5 Haiku: fast + capable for structured JSON decisions
LLM_DECISION_MAKER_PROVIDER=bedrock
LLM_DECISION_MAKER_MODEL=us.anthropic.claude-3-5-haiku-20241022-v1:0
LLM_DECISION_MAKER_MAX_TOKENS=2000
LLM_DECISION_MAKER_TEMPERATURE=0.2

# ---- AUDITOR AGENT ----
# Haiku sufficient for compliance box-checking
LLM_AUDITOR_PROVIDER=bedrock
LLM_AUDITOR_MODEL=anthropic.claude-3-haiku-20240307-v1:0
LLM_AUDITOR_MAX_TOKENS=4096
LLM_AUDITOR_TEMPERATURE=0.2

# ==================== OPENAI CONFIGURATION (Optional) ====================
# Uncomment and set these to use OpenAI models
# OPENAI_API_KEY=sk-your-key-here
ENV
}
