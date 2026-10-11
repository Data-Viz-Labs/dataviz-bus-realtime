# One access key per hackathon group, shared by the MQTT authorizer and the HTTP/MCP API.
# Only SHA-256 hashes reach the Lambdas; `make keys` prints the keys for distribution.

resource "random_password" "group_key" {
  for_each = toset(var.groups)
  length   = 32
  special  = false
}

locals {
  # {"<sha256 hex of key>": "<group name>"}
  group_key_hashes = jsonencode({ for group, key in random_password.group_key : sha256(key.result) => group })
}

output "group_keys" {
  description = "Access key per group (x-api-key header, MQTT token)"
  value       = { for group, key in random_password.group_key : group => key.result }
  sensitive   = true
}
