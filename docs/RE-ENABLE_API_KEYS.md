# Cómo Re-habilitar API Keys y Usage Plans

## Estado Actual
El API Gateway está funcionando en modo simplificado **SIN API keys**. Esto es ideal para desarrollo y testing.

## ¿Cuándo necesitas API Keys?

- **Producción**: Para controlar acceso y evitar abuso
- **Hackathon**: Para distribuir keys a participantes
- **Rate Limiting**: Para limitar requests por usuario
- **Monetización**: Para cobrar por uso del API

## Pasos para Re-habilitar

### 1. Editar `modules/api-gateway/main.tf`

#### 1.1 Cambiar `api_key_required` a `true`

Busca estos 4 bloques y cambia `false` a `true`:

```terraform
# API Methods - People Count
resource "aws_api_gateway_method" "people_count" {
  # ...
  api_key_required = true  # Cambiar de false a true
}

# API Methods - Sensors
resource "aws_api_gateway_method" "sensors" {
  # ...
  api_key_required = true  # Cambiar de false a true
}

# API Methods - Bus Position (by bus_id)
resource "aws_api_gateway_method" "bus_position" {
  # ...
  api_key_required = true  # Cambiar de false a true
}

# API Methods - Bus Position (by line_id)
resource "aws_api_gateway_method" "bus_position_line" {
  # ...
  api_key_required = true  # Cambiar de false a true
}
```

#### 1.2 Descomentar recursos de API Keys

Busca el bloque que empieza con:
```terraform
# COMMENTED OUT FOR SIMPLIFIED VERSION - Add back once basic API is working
```

Y descomenta todos los recursos:
- `aws_api_gateway_api_key.participant_keys`
- `aws_api_gateway_usage_plan.hackathon`
- `aws_api_gateway_usage_plan_key.participant_keys`

**OPCIONAL**: Si necesitas el `null_resource.force_final_deployment`, descoméntalo también (pero primero añade la variable `aws_region` - ver paso 3).

### 2. Editar Outputs

#### 2.1 `modules/api-gateway/outputs.tf`

Descomenta:
```terraform
output "api_keys" {
  description = "List of API key IDs for hackathon participants"
  value       = aws_api_gateway_api_key.participant_keys[*].id
  sensitive   = true
}

output "api_key_values" {
  description = "List of API key values for hackathon participants"
  value       = aws_api_gateway_api_key.participant_keys[*].value
  sensitive   = true
}

output "usage_plan_id" {
  description = "Usage plan ID for hackathon participants"
  value       = aws_api_gateway_usage_plan.hackathon.id
}
```

#### 2.2 `outputs.tf` (root)

Descomenta los mismos outputs en el archivo raíz.

### 3. (Opcional) Añadir variable `aws_region`

Si descomentaste el `null_resource`, añade en `modules/api-gateway/variables.tf`:

```terraform
variable "aws_region" {
  description = "AWS region for API Gateway deployment"
  type        = string
  default     = "eu-west-1"
}
```

Y pásala desde `main.tf`:

```terraform
module "api_gateway" {
  source = "./modules/api-gateway"
  
  aws_region = var.aws_region  # Añadir esta línea
  
  # ... resto de variables
}
```

### 4. Aplicar Cambios

```bash
# Ver qué va a cambiar
terraform plan -target=module.api_gateway

# Aplicar cambios
terraform apply -target=module.api_gateway
```

### 5. Obtener API Keys

```bash
# Ver IDs de las keys
terraform output api_keys

# Ver valores de las keys (para distribuir)
terraform output -json api_key_values | jq -r '.[]'

# O guardar en archivo
terraform output -json api_key_values | jq -r '.[]' > api_keys.txt
```

### 6. Probar con API Key

```bash
API_ENDPOINT=$(terraform output -raw api_gateway_rest_endpoint)
API_KEY=$(terraform output -json api_key_values | jq -r '.[0]')

# Probar endpoint con API key
curl -H "x-api-key: $API_KEY" \
  "$API_ENDPOINT/people-count/STOP001?mode=latest"
```

## Configuración del Usage Plan

El usage plan actual tiene estos límites (puedes ajustarlos en `main.tf`):

```terraform
quota_settings {
  limit  = 10000    # 10,000 requests por día
  period = "DAY"
}

throttle_settings {
  burst_limit = 100  # Máximo 100 requests en burst
  rate_limit  = 50   # 50 requests por segundo sostenido
}
```

### Ajustar límites

Para cambiar los límites, edita estos valores en el recurso `aws_api_gateway_usage_plan.hackathon`.

## Número de API Keys

Por defecto se crean 12 keys (definido en `variables.tf`):

```terraform
variable "participant_count" {
  description = "Number of API keys to generate"
  type        = number
  default     = 12
}
```

Para cambiar el número:

```bash
# Opción 1: En terraform.tfvars
echo 'participant_count = 50' >> terraform.tfvars

# Opción 2: En la línea de comandos
terraform apply -var="participant_count=50" -target=module.api_gateway
```

## Troubleshooting

### Error: "Forbidden" al llamar al API

- Verifica que estás pasando el header `x-api-key`
- Verifica que la key es válida: `terraform output api_key_values`
- Verifica que la key está asociada al usage plan

### Error: "Too Many Requests" (429)

- Has excedido el rate limit
- Espera un momento o ajusta los límites del usage plan

### Las keys no funcionan después de aplicar

- Puede tomar unos segundos para que se propaguen
- Intenta hacer un nuevo deployment:
  ```bash
  aws apigateway create-deployment \
    --rest-api-id $(terraform output -raw api_gateway_rest_api_id) \
    --stage-name prod \
    --region eu-west-1
  ```

## Revertir a Modo Simplificado

Si necesitas volver al modo sin API keys:

1. Cambia `api_key_required` de `true` a `false`
2. Comenta los recursos de API keys
3. Comenta los outputs
4. Aplica: `terraform apply -target=module.api_gateway`

## Recursos Adicionales

- [AWS API Gateway API Keys](https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-api-key-source.html)
- [Usage Plans](https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-api-usage-plans.html)
- [Rate Limiting](https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-request-throttling.html)
