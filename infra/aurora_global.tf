# =============================================================================
# Terraform - Aurora Serverless v2 Multi-Region Global Database
# Para MediCare Enterprise PRO - Failover automatico, escalado dinamico
# =============================================================================

provider "aws" {
  alias  = "primary"
  region = "us-east-1"
}

provider "aws" {
  alias  = "secondary"
  region = "sa-east-1"  # Brasil/Argentina para latencia Sudamerica
}

# ═══════════════════════════════════════════════════════════════════════════════
# KMS - LLAVES MAESTRAS POR REGION
# ═══════════════════════════════════════════════════════════════════════════════

resource "aws_kms_key" "aurora_primary" {
  provider                = aws.primary
  description             = "Medicare PRO - Aurora primary encryption key"
  deletion_window_in_days = 30
  enable_key_rotation     = true
  multi_region            = true

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid    = "Enable IAM User Permissions"
      Effect = "Allow"
      Principal = {
        AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
      }
      Action   = "kms:*"
      Resource = "*"
    }]
  })
}

resource "aws_kms_key" "aurora_secondary" {
  provider                = aws.secondary
  description             = "Medicare PRO - Aurora replica encryption key"
  deletion_window_in_days = 30
  enable_key_rotation     = true
  multi_region            = true

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid    = "Enable IAM User Permissions"
      Effect = "Allow"
      Principal = {
        AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
      }
      Action   = "kms:*"
      Resource = "*"
    }]
  })
}

# ═══════════════════════════════════════════════════════════════════════════════
# AURORA SERVERLESS V2 - CLUSTER GLOBAL
# ═══════════════════════════════════════════════════════════════════════════════

resource "aws_rds_global_cluster" "medicare" {
  provider                    = aws.primary
  global_cluster_identifier   = "medicare-${var.environment}-global"
  engine                      = "aurora-postgresql"
  engine_version              = "16.3"
  database_name               = "medicare_global"
  storage_encrypted           = true
  kms_key_id                  = aws_kms_key.aurora_primary.arn
  deletion_protection         = true
  # Failover prioritario: si primary cae, secondary asume automaticamente
  # Tiempo de failover tipico: 60-120 segundos
}

# ── Cluster Primario (us-east-1) ─────────────────────────────────

resource "aws_rds_cluster" "primary" {
  provider                   = aws.primary
  cluster_identifier         = "medicare-${var.environment}-primary"
  global_cluster_identifier  = aws_rds_global_cluster.medicare.id
  engine                     = "aurora-postgresql"
  engine_version             = "16.3"
  master_username            = "medicare_admin"
  master_password            = random_password.aurora_master.result
  storage_encrypted          = true
  kms_key_id                 = aws_kms_key.aurora_primary.arn
  backup_retention_period    = 35
  preferred_backup_window    = "02:00-03:00"
  preferred_maintenance_window = "sun:04:00-05:00"
  deletion_protection        = true

  # Serverless v2: escala de 0.5 ACU a 128 ACU segun demanda
  serverlessv2_scaling_configuration {
    min_capacity = 0.5   # ~0.5 ACU en horas de minima actividad
    max_capacity = 128   # Picos de emergencia masiva
  }
}

# ── Instancia primaria (writer) ──────────────────────────────────

resource "aws_rds_cluster_instance" "primary_writer" {
  provider                    = aws.primary
  identifier                  = "medicare-${var.environment}-primary-writer"
  cluster_identifier          = aws_rds_cluster.primary.id
  instance_class              = "db.serverless"
  engine                      = "aurora-postgresql"
  engine_version              = "16.3"
  auto_minor_version_upgrade  = true
  monitoring_role_arn         = aws_iam_role.rds_monitoring.arn
  monitoring_interval         = 15
}

# ── Replicas de lectura primarias (hasta 15) ─────────────────────

resource "aws_rds_cluster_instance" "primary_readers" {
  provider                    = aws.primary
  count                       = 2  # 2 replicas de lectura en primary
  identifier                  = "medicare-${var.environment}-primary-reader-${count.index}"
  cluster_identifier          = aws_rds_cluster.primary.id
  instance_class              = "db.serverless"
  engine                      = "aurora-postgresql"
  engine_version              = "16.3"
  promotion_tier             = count.index + 1
}

# ── Cluster Secundario (sa-east-1) ───────────────────────────────

resource "aws_rds_cluster" "secondary" {
  provider                   = aws.secondary
  cluster_identifier         = "medicare-${var.environment}-secondary"
  global_cluster_identifier  = aws_rds_global_cluster.medicare.id
  engine                     = "aurora-postgresql"
  engine_version             = "16.3"
  master_username            = "medicare_admin"
  master_password            = random_password.aurora_master.result
  storage_encrypted          = true
  kms_key_id                 = aws_kms_key.aurora_secondary.arn
  source_region              = "us-east-1"
  deletion_protection        = true

  serverlessv2_scaling_configuration {
    min_capacity = 0.5
    max_capacity = 64
  }
}

resource "aws_rds_cluster_instance" "secondary_reader" {
  provider           = aws.secondary
  identifier         = "medicare-${var.environment}-secondary-reader"
  cluster_identifier = aws_rds_cluster.secondary.id
  instance_class     = "db.serverless"
  engine             = "aurora-postgresql"
  engine_version     = "16.3"
}

# ═══════════════════════════════════════════════════════════════════════════════
# SECRET MANAGER - CREDENCIALES ROTADAS AUTOMATICAMENTE
# ═══════════════════════════════════════════════════════════════════════════════

resource "random_password" "aurora_master" {
  length  = 32
  special = false
}

resource "aws_secretsmanager_secret" "aurora_credentials" {
  provider    = aws.primary
  name        = "medicare-${var.environment}-aurora-credentials"
  description = "Rotated automatically every 90 days"
  kms_key_id  = aws_kms_key.aurora_primary.arn

  rotation_rules {
    automatically_after_days = 90
  }
}

resource "aws_secretsmanager_secret_version" "aurora_credentials" {
  provider    = aws.primary
  secret_id   = aws_secretsmanager_secret.aurora_credentials.id
  secret_string = jsonencode({
    username = aws_rds_cluster.primary.master_username
    password = random_password.aurora_master.result
    engine   = "postgres"
    host     = aws_rds_cluster.primary.endpoint
    port     = 5432
    dbname   = "medicare_global"
  })
}

# ═══════════════════════════════════════════════════════════════════════════════
# IAM ROLE PARA MONITOREO
# ═══════════════════════════════════════════════════════════════════════════════

resource "aws_iam_role" "rds_monitoring" {
  provider = aws.primary
  name     = "medicare-${var.environment}-rds-monitoring"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid    = ""
      Effect = "Allow"
      Principal = {
        Service = "monitoring.rds.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "rds_monitoring" {
  provider   = aws.primary
  role       = aws_iam_role.rds_monitoring.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonRDSEnhancedMonitoringRole"
}

# ═══════════════════════════════════════════════════════════════════════════════
# OUTPUTS
# ═══════════════════════════════════════════════════════════════════════════════

output "global_cluster_id" {
  value = aws_rds_global_cluster.medicare.id
}

output "primary_endpoint" {
  value = aws_rds_cluster.primary.endpoint
}

output "secondary_endpoint" {
  value = aws_rds_cluster.secondary.endpoint
}

output "reader_endpoints" {
  value = aws_rds_cluster_instance.primary_readers[*].endpoint
}

output "secret_arn" {
  value = aws_secretsmanager_secret.aurora_credentials.arn
}
