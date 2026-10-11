# Historical dataset: Parquet in a private data bucket, Glue tables with partition projection,
# an Athena workgroup with a scan limit. The simulator writes history/ and private/.

resource "aws_s3_bucket" "data" {
  bucket_prefix = "${local.name}-data-"
  force_destroy = true
}

resource "aws_s3_bucket_public_access_block" "data" {
  bucket                  = aws_s3_bucket.data.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "data" {
  bucket = aws_s3_bucket.data.id

  rule {
    id     = "athena-results"
    status = "Enabled"
    filter {
      prefix = "athena-results/"
    }
    expiration {
      days = 1
    }
  }
}

locals {
  history_schema = jsondecode(file("${path.module}/history_schema.json"))
  glue_database  = "${replace(local.name, "-", "_")}_history"
  # Projection ranges: generous bounds, Athena only lists partitions that exist in S3 paths.
  projection = {
    month = {
      "projection.month.type"          = "date"
      "projection.month.format"        = "yyyy-MM"
      "projection.month.range"         = "2015-01,NOW"
      "projection.month.interval"      = "1"
      "projection.month.interval.unit" = "MONTHS"
    }
    dt = {
      "projection.dt.type"          = "date"
      "projection.dt.format"        = "yyyy-MM-dd"
      "projection.dt.range"         = "2015-01-01,NOW"
      "projection.dt.interval"      = "1"
      "projection.dt.interval.unit" = "DAYS"
    }
  }
}

resource "aws_glue_catalog_database" "history" {
  name        = local.glue_database
  description = "Simulated EMT Madrid bus history"
}

resource "aws_glue_catalog_table" "history" {
  for_each      = local.history_schema
  name          = each.key
  database_name = aws_glue_catalog_database.history.name
  table_type    = "EXTERNAL_TABLE"

  parameters = merge(
    {
      EXTERNAL                    = "TRUE"
      "classification"            = "parquet"
      "parquet.compression"       = "ZSTD"
      "projection.enabled"        = "true"
      "storage.location.template" = "s3://${aws_s3_bucket.data.id}/history/${each.key}/${each.value.partition}=$${${each.value.partition}}/"
    },
    local.projection[each.value.partition],
  )

  partition_keys {
    name = each.value.partition
    type = "string"
  }

  storage_descriptor {
    location      = "s3://${aws_s3_bucket.data.id}/history/${each.key}/"
    input_format  = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat"
    output_format = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat"

    ser_de_info {
      serialization_library = "org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe"
    }

    dynamic "columns" {
      for_each = each.value.columns
      content {
        name    = columns.value.name
        type    = columns.value.type
        comment = columns.value.comment
      }
    }
  }
}

resource "aws_athena_workgroup" "history" {
  name          = "${local.name}-history"
  force_destroy = true

  configuration {
    enforce_workgroup_configuration    = true
    bytes_scanned_cutoff_per_query     = 2147483648 # 2 GiB
    publish_cloudwatch_metrics_enabled = true

    result_configuration {
      output_location = "s3://${aws_s3_bucket.data.id}/athena-results/"
    }
  }
}

output "data_bucket" {
  value = aws_s3_bucket.data.id
}

output "athena_workgroup" {
  value = aws_athena_workgroup.history.name
}

output "glue_database" {
  value = aws_glue_catalog_database.history.name
}
