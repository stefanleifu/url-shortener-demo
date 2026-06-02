output "load_balancer_url" {
  description = "Public URL for the URL shortener service."
  value       = "http://${aws_lb.app.dns_name}"
}

output "ecs_cluster_name" {
  description = "ECS cluster name."
  value       = aws_ecs_cluster.app.name
}

output "efs_file_system_id" {
  description = "EFS file system used for demo SQLite persistence."
  value       = aws_efs_file_system.data.id
}
