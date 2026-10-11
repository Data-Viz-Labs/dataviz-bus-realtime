# Public map: static files plus the live/ snapshot the simulator writes every few seconds,
# all in one private bucket behind CloudFront. state/ stays private.

resource "aws_s3_bucket" "site" {
  bucket_prefix = "${local.name}-site-"
  force_destroy = true
}

resource "aws_s3_bucket_public_access_block" "site" {
  bucket                  = aws_s3_bucket.site.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

locals {
  # published key => [source file, content type]
  site_files = {
    "index.html"         = ["web/index.html", "text/html; charset=utf-8"]
    "docs.html"          = ["web/docs.html", "text/html; charset=utf-8"]
    "network.json"       = ["web/network.json", "application/json"]
    "docs/openapi.yaml"  = ["docs/api/openapi.yaml", "application/yaml"]
    "docs/asyncapi.yaml" = ["docs/api/asyncapi.yaml", "application/yaml"]
  }
}

# First publication; afterwards the deploy-web workflow updates the same objects.
resource "aws_s3_object" "site" {
  for_each      = local.site_files
  bucket        = aws_s3_bucket.site.id
  key           = each.key
  source        = "${local.repo_root}/${each.value[0]}"
  etag          = filemd5("${local.repo_root}/${each.value[0]}")
  content_type  = each.value[1]
  cache_control = "public, max-age=300"
}

resource "aws_cloudfront_origin_access_control" "s3" {
  name                              = "${local.name}-s3"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

locals {
  # AWS managed cache policy that honours the object's Cache-Control (5 s for live/snapshot.json).
  caching_optimized = "658327ea-f89d-4fab-a63d-7e88639e58f6"
}

resource "aws_cloudfront_distribution" "site" {
  enabled             = true
  comment             = "Madrid bus live map"
  default_root_object = "index.html"
  price_class         = "PriceClass_100"

  origin {
    origin_id                = "site"
    domain_name              = aws_s3_bucket.site.bucket_regional_domain_name
    origin_access_control_id = aws_cloudfront_origin_access_control.s3.id
  }

  default_cache_behavior {
    target_origin_id       = "site"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    cache_policy_id        = local.caching_optimized
    compress               = true
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }
}

data "aws_iam_policy_document" "site_bucket" {
  statement {
    actions = ["s3:GetObject"]
    resources = concat(
      [for key in keys(local.site_files) : "${aws_s3_bucket.site.arn}/${key}"],
      ["${aws_s3_bucket.site.arn}/live/*"],
    )
    principals {
      type        = "Service"
      identifiers = ["cloudfront.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "AWS:SourceArn"
      values   = [aws_cloudfront_distribution.site.arn]
    }
  }
}

resource "aws_s3_bucket_policy" "site" {
  bucket = aws_s3_bucket.site.id
  policy = data.aws_iam_policy_document.site_bucket.json
}
