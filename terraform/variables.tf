################################################################################
# Variables – override via terraform.tfvars or -var flags
################################################################################

variable "aws_region" {
  description = "AWS region to deploy resources"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Deployment environment tag"
  type        = string
  default     = "dev"
}

variable "project_name" {
  description = "Prefix applied to all resource names"
  type        = string
  default     = "orchestrateai"
}

variable "db_name" {
  description = "MySQL database (schema) name created inside the instance"
  type        = string
  default     = "dev"
}

variable "db_username" {
  description = "Master username for the RDS instance"
  type        = string
  default     = "admin"
}

variable "db_password" {
  description = "Master password for the RDS instance (min 8 chars)"
  type        = string
  sensitive   = true
  # Set via terraform.tfvars or:  export TF_VAR_db_password=<password>
}

variable "db_instance_class" {
  description = "RDS instance type"
  type        = string
  default     = "db.t3.micro"   # free-tier eligible
}
