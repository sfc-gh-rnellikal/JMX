variable "aws_region" {
  description = "AWS region for the EKS cluster"
  type        = string
  default     = "us-west-2"
}

variable "cluster_name" {
  description = "Name of the EKS cluster"
  type        = string
  default     = "jmeter-load-test"
}

variable "kubernetes_version" {
  description = "Kubernetes version for EKS"
  type        = string
  default     = "1.31"
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "node_instance_type" {
  description = "EC2 instance type for EKS worker nodes"
  type        = string
  default     = "m5.xlarge"
}

variable "node_desired_size" {
  description = "Desired number of worker nodes"
  type        = number
  default     = 8
}

variable "node_min_size" {
  description = "Minimum number of worker nodes"
  type        = number
  default     = 8
}

variable "node_max_size" {
  description = "Maximum number of worker nodes"
  type        = number
  default     = 10
}

variable "ecr_repo_name" {
  description = "Name of the ECR repository for JMeter image"
  type        = string
  default     = "jmeter-snowflake"
}
