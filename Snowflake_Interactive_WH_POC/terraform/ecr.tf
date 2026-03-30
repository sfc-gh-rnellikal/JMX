resource "aws_ecr_repository" "jmeter" {
  name                 = var.ecr_repo_name
  image_tag_mutability = "MUTABLE"
  force_delete         = true

  image_scanning_configuration {
    scan_on_push = false
  }

  tags = {
    Name = "${var.cluster_name}-jmeter-ecr"
  }
}
