# Guía de API Keys para Hackathon

## Resumen de Cambios

### 1. Redespliegue Automático
El API Gateway ahora se redespliegue automáticamente cuando cambias cualquier recurso, método o integración. Usa un hash SHA256 de todos los recursos relevantes como trigger.

**No necesitas hacer nada especial** - simplemente ejecuta `terraform apply` y el API se redespliegará si hay cambios.

### 2. API Keys sin Cuota
Se han configurado API keys sin límites de rate ni quota para los participantes del hackathon.

## Obtener las API Keys

Después de ejecutar `terraform apply`, obtén las API keys con:

```bash
# Ver los IDs de las API keys
terraform output api_keys

# Ver los valores de las API keys (para distribuir a participantes)
terraform output -json api_key_values | jq -r '.[]'
```

## Usar las API Keys

Los participantes deben incluir la API key en el header `x-api-key`:

```bash
curl -H "x-api-key: TU_API_KEY_AQUI" \
  https://tu-api-endpoint.execute-api.eu-west-1.amazonaws.com/prod/sensors/bus/123
```

## Configuración

El número de API keys se controla con la variable `participant_count` en `terraform/variables.tf` (por defecto: 12).

Para cambiar el número:

```hcl
variable "participant_count" {
  description = "Number of API keys to generate for hackathon participants"
  type        = number
  default     = 20  # Cambia este valor
}
```

## Características

- **Sin límites de rate**: Los participantes pueden hacer tantas peticiones como necesiten
- **Sin cuota**: No hay límite en el número total de peticiones
- **Redespliegue automático**: Cualquier cambio en el API se despliega automáticamente
- **API keys individuales**: Cada participante tiene su propia key para tracking

## Endpoints Protegidos

Todos los endpoints REST requieren API key:
- `GET /people-count/{stop_id}`
- `GET /sensors/{entity_type}/{entity_id}`
- `GET /bus-position/{bus_id}`
- `GET /bus-position/line/{line_id}`

El WebSocket API no requiere API key.
