# Positions of the tracked lines' buses: latest + 30 days of history. Accuracy-based filtering
# with no accuracy sent keeps every update (the default time-based filter drops updates closer
# than 30 s, which would lose stop calls).
resource "aws_location_tracker" "buses" {
  tracker_name       = "${local.name}-buses"
  description        = "Simulated EMT Madrid buses"
  position_filtering = "AccuracyBased"
}

# One circular geofence per stop, created by the simulator at start-up.
resource "aws_location_geofence_collection" "stops" {
  count           = var.stop_geofences ? 1 : 0
  collection_name = "${local.name}-stops"
  description     = "Bus stops"
}

resource "aws_location_tracker_association" "stops" {
  count        = var.stop_geofences ? 1 : 0
  tracker_name = aws_location_tracker.buses.tracker_name
  consumer_arn = aws_location_geofence_collection.stops[0].collection_arn
}

# Browser key for Amazon Location Maps v2, limited to map tiles and to the site's domain.
resource "aws_cloudcontrolapi_resource" "map_key" {
  type_name = "AWS::Location::APIKey"
  desired_state = jsonencode({
    KeyName  = "${local.name}-map"
    NoExpiry = true
    Restrictions = {
      AllowActions   = ["geo-maps:GetTile", "geo-maps:GetStaticMap"]
      AllowResources = ["arn:aws:geo-maps:${var.aws_region}::provider/default"]
      AllowReferers  = ["https://${aws_cloudfront_distribution.site.domain_name}/*"]
    }
  })
}

# Stop ENTER/EXIT events, kept in CloudWatch Logs for analysis.
resource "aws_cloudwatch_log_group" "geofence_events" {
  count             = var.stop_geofences ? 1 : 0
  name              = "/aws/events/${local.name}-geofence"
  retention_in_days = 7
}

resource "aws_cloudwatch_event_rule" "geofence" {
  count       = var.stop_geofences ? 1 : 0
  name        = "${local.name}-geofence"
  description = "Buses entering and leaving stops"
  event_pattern = jsonencode({
    source        = ["aws.geo"]
    "detail-type" = ["Location Geofence Event"]
    resources     = [aws_location_geofence_collection.stops[0].collection_arn]
  })
}

resource "aws_cloudwatch_event_target" "geofence_logs" {
  count = var.stop_geofences ? 1 : 0
  rule  = aws_cloudwatch_event_rule.geofence[0].name
  arn   = aws_cloudwatch_log_group.geofence_events[0].arn
}

data "aws_iam_policy_document" "events_to_logs" {
  count = var.stop_geofences ? 1 : 0
  statement {
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${aws_cloudwatch_log_group.geofence_events[0].arn}:*"]
    principals {
      type        = "Service"
      identifiers = ["events.amazonaws.com", "delivery.logs.amazonaws.com"]
    }
  }
}

resource "aws_cloudwatch_log_resource_policy" "events_to_logs" {
  count           = var.stop_geofences ? 1 : 0
  policy_name     = "${local.name}-geofence-events"
  policy_document = data.aws_iam_policy_document.events_to_logs[0].json
}
