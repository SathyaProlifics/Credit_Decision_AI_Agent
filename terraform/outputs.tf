################################################################################
# Outputs – shown after `terraform apply`, also used by local_file .env writer
################################################################################

output "db_host" {
  description = "RDS instance endpoint hostname"
  value       = aws_db_instance.credit_db.address
}

output "db_port" {
  description = "RDS instance port"
  value       = aws_db_instance.credit_db.port
}

output "db_name" {
  description = "Database (schema) name"
  value       = var.db_name
}

output "db_username" {
  description = "Master database username"
  value       = var.db_username
}

output "db_endpoint_full" {
  description = "Full RDS endpoint (host:port)"
  value       = aws_db_instance.credit_db.endpoint
}

output "security_group_id" {
  description = "ID of the RDS public security group"
  value       = aws_security_group.rds_public.id
}

output "env_file_updated" {
  description = "Path of the .env file that was updated"
  value       = local_file.env_file.filename
}
