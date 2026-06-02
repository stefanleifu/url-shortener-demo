variable "aws_region" {
  description = "AWS region to deploy into."
  type        = string
  default     = "us-east-1"
}

variable "name" {
  description = "Name prefix for URL shortener resources."
  type        = string
  default     = "url-shortener-demo"
}

variable "container_image" {
  description = "Container image URI for the URL shortener service."
  type        = string
}

variable "vpc_id" {
  description = "Existing VPC ID."
  type        = string
}

variable "public_subnet_ids" {
  description = "Public subnet IDs for the application load balancer."
  type        = list(string)
}

variable "private_subnet_ids" {
  description = "Private subnet IDs for ECS tasks and EFS mount targets."
  type        = list(string)
}

variable "task_cpu" {
  description = "Fargate task CPU units."
  type        = number
  default     = 256
}

variable "task_memory" {
  description = "Fargate task memory in MiB."
  type        = number
  default     = 512
}

variable "tags" {
  description = "Additional tags to attach to AWS resources."
  type        = map(string)
  default     = {}
}
