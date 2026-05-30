# =============================================================================
# Terraform - MediCare Enterprise PRO
# Infraestructura de alta disponibilidad multi-tenant
# =============================================================================

terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# ═══════════════════════════════════════════════════════════════════
# VARIABLES
# ═══════════════════════════════════════════════════════════════════

variable "aws_region" {
  description = "Region AWS"
  default     = "us-east-1"
}

variable "environment" {
  description = "Entorno (prod/staging)"
  default     = "prod"
}

variable "tenants" {
  description = "Lista de tenants a desplegar"
  type        = list(string)
  default     = ["default", "avalian", "sancor"]
}

variable "instance_type" {
  description = "Tipo de instancia para los nodos de computo"
  default     = "t3.medium"
}

variable "db_instance_class" {
  description = "Clase de instancia RDS"
  default     = "db.t3.small"
}

# ═══════════════════════════════════════════════════════════════════
# RED Y SEGURIDAD
# ═══════════════════════════════════════════════════════════════════

resource "aws_vpc" "medicare" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name        = "medicare-${var.environment}-vpc"
    Environment = var.environment
  }
}

resource "aws_subnet" "public" {
  count                   = 2
  vpc_id                  = aws_vpc.medicare.id
  cidr_block              = "10.0.${count.index}.0/24"
  availability_zone       = data.aws_availability_zones.available.names[count.index]
  map_public_ip_on_launch = true

  tags = {
    Name = "medicare-${var.environment}-public-${count.index}"
  }
}

resource "aws_subnet" "private" {
  count             = 2
  vpc_id            = aws_vpc.medicare.id
  cidr_block        = "10.0.${count.index + 10}.0/24"
  availability_zone = data.aws_availability_zones.available.names[count.index]

  tags = {
    Name = "medicare-${var.environment}-private-${count.index}"
  }
}

data "aws_availability_zones" "available" {
  state = "available"
}

# ═══════════════════════════════════════════════════════════════════
# BALANCEADOR DE CARGA (ALB)
# ═══════════════════════════════════════════════════════════════════

resource "aws_lb" "medicare" {
  name               = "medicare-${var.environment}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = aws_subnet.public[*].id

  tags = {
    Name = "medicare-${var.environment}-alb"
  }
}

resource "aws_lb_target_group" "medicare" {
  name        = "medicare-${var.environment}-tg"
  port        = 8501
  protocol    = "HTTP"
  target_type = "ip"
  vpc_id      = aws_vpc.medicare.id

  health_check {
    path                = "/healthz"
    port                = "8501"
    protocol            = "HTTP"
    healthy_threshold   = 2
    unhealthy_threshold = 3
    interval            = 30
    timeout             = 10
  }

  stickiness {
    type            = "lb_cookie"
    cookie_duration = 86400
  }
}

resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.medicare.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = var.certificate_arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.medicare.arn
  }
}

# ═══════════════════════════════════════════════════════════════════
# BASE DE DATOS POSTGRESQL POR TENANT
# ═══════════════════════════════════════════════════════════════════

resource "aws_db_instance" "medicare" {
  for_each = toset(var.tenants)

  identifier     = "medicare-${var.environment}-${each.key}"
  engine         = "postgres"
  engine_version = "16.3"
  instance_class = var.db_instance_class

  db_name  = "medicare_${each.key}"
  username = "medicare_admin"
  password = random_password.db_password[each.key].result

  storage_type          = "gp3"
  allocated_storage     = 100
  max_allocated_storage = 500

  vpc_security_group_ids = [aws_security_group.database.id]
  db_subnet_group_name   = aws_db_subnet_group.medicare.name

  backup_retention_period = 30
  backup_window          = "03:00-04:00"
  maintenance_window     = "sun:04:00-05:00"

  deletion_protection = true
  skip_final_snapshot = false

  tags = {
    Name    = "medicare-${var.environment}-${each.key}"
    Tenant  = each.key
  }
}

resource "random_password" "db_password" {
  for_each = toset(var.tenants)
  length   = 32
  special  = false
}

resource "aws_db_subnet_group" "medicare" {
  name       = "medicare-${var.environment}-subnet-group"
  subnet_ids = aws_subnet.private[*].id
}

# ═══════════════════════════════════════════════════════════════════
# ALMACENAMIENTO S3 PARA ESTUDIOS
# ═══════════════════════════════════════════════════════════════════

resource "aws_s3_bucket" "estudios" {
  for_each = toset(var.tenants)
  bucket   = "medicare-${var.environment}-estudios-${each.key}"

  tags = {
    Tenant = each.key
  }
}

resource "aws_s3_bucket_versioning" "estudios" {
  for_each = toset(var.tenants)
  bucket   = aws_s3_bucket_estudios[each.key].id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "estudios" {
  for_each = toset(var.tenants)
  bucket   = aws_s3_bucket_estudios[each.key].id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "estudios" {
  for_each = toset(var.tenants)
  bucket   = aws_s3_bucket_estudios[each.key].id
  rule {
    id     = "expire_old"
    status = "Enabled"
    expiration {
      days = 365  # Retener estudios 1 ano
    }
  }
}

# ═══════════════════════════════════════════════════════════════════
# ALMACENAMIENTO FRIO PARA AUDIT LOGS
# ═══════════════════════════════════════════════════════════════════

resource "aws_s3_bucket" "cold_storage" {
  bucket = "medicare-${var.environment}-cold-storage"
  object_lock_enabled = true

  tags = {
    Environment = var.environment
  }
}

resource "aws_s3_bucket_object_lock_configuration" "cold_storage" {
  bucket = aws_s3_bucket.cold_storage.id
  rule {
    default_retention {
      mode = "COMPLIANCE"
      days = 365  # Inmodificable por 1 ano
    }
  }
}

# ═══════════════════════════════════════════════════════════════════
# GRUPOS DE SEGURIDAD
# ═══════════════════════════════════════════════════════════════════

resource "aws_security_group" "alb" {
  name        = "medicare-${var.environment}-alb-sg"
  description = "ALB security group"
  vpc_id      = aws_vpc.medicare.id

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 8501
    to_port     = 8501
    protocol    = "tcp"
    cidr_blocks = ["10.0.0.0/16"]
  }
}

resource "aws_security_group" "app" {
  name        = "medicare-${var.environment}-app-sg"
  description = "App security group"
  vpc_id      = aws_vpc.medicare.id

  ingress {
    from_port       = 8501
    to_port         = 8501
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "database" {
  name        = "medicare-${var.environment}-database-sg"
  description = "Database security group"
  vpc_id      = aws_vpc.medicare.id

  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.app.id]
  }
}

# ═══════════════════════════════════════════════════════════════════
# OUTPUTS
# ═══════════════════════════════════════════════════════════════════

output "alb_dns" {
  value = aws_lb.medicare.dns_name
}

output "db_endpoints" {
  value = { for k, db in aws_db_instance.medicare : k => db.endpoint }
}

output "s3_buckets" {
  value = { for k, b in aws_s3_bucket.estudios : k => b.bucket }
}
