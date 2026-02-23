# API Gateway Simplification Notes

## Fecha: 2026-02-23

## Problema Original
El API Gateway no estaba funcionando correctamente debido a:
1. Configuración compleja con API Keys obligatorias
2. Usage Plans con rate limiting
3. `null_resource` con `local-exec` que podía fallar
4. Variable `aws_region` faltante en el módulo

## Solución Implementada

### Cambios Realizados

1. **Eliminación de API Keys (temporalmente)**
   - Cambiado `api_key_required = true` a `false` en todos los métodos
   - Comentados recursos: `aws_api_gateway_api_key`, `aws_api_gateway_usage_plan`, `aws_api_gateway_usage_plan_key`
   - Comentado `null_resource.force_final_deployment` que usaba `local-exec`

2. **Outputs Actualizados**
   - Comentados outputs relacionados con API keys en:
     - `modules/api-gateway/outputs.tf`
     - `outputs.tf` (root)

3. **Resultado**
   - API Gateway REST funcionando correctamente
   - Todos los endpoints responden sin necesidad de API key
   - Integración Lambda funcionando perfectamente

### Endpoints Probados y Funcionando

```bash
# People Count API
curl "https://0w08yrrx1a.execute-api.eu-west-1.amazonaws.com/prod/people-count/STOP001?mode=latest"

# Bus Position API (by bus_id)
curl "https://0w08yrrx1a.execute-api.eu-west-1.amazonaws.com/prod/bus-position/BUS001?mode=latest"

# Sensors API
curl "https://0w08yrrx1a.execute-api.eu-west-1.amazonaws.com/prod/sensors/bus/BUS001?mode=latest"

# Bus Position API (by line_id)
curl "https://0w08yrrx1a.execute-api.eu-west-1.amazonaws.com/prod/bus-position/line/LINE001?mode=latest"
```

### Próximos Pasos (Cuando se necesite)

Para re-habilitar API Keys y Usage Plans:

1. **Descomentar en `modules/api-gateway/main.tf`:**
   - Recursos de API Keys
   - Usage Plan
   - Usage Plan Keys
   - (Opcional) null_resource si es necesario

2. **Cambiar `api_key_required`:**
   - De `false` a `true` en todos los métodos

3. **Descomentar outputs:**
   - En `modules/api-gateway/outputs.tf`
   - En `outputs.tf` (root)

4. **Añadir variable `aws_region`:**
   - En `modules/api-gateway/variables.tf` si se necesita el null_resource

5. **Aplicar cambios:**
   ```bash
   terraform plan -target=module.api_gateway
   terraform apply -target=module.api_gateway
   ```

### Notas Importantes

- La versión simplificada es perfecta para desarrollo y testing
- Para producción, se recomienda añadir:
  - API Keys para control de acceso
  - Usage Plans para rate limiting
  - WAF para protección adicional
  - Cognito para autenticación de usuarios

## Estado Actual

✅ API Gateway REST funcionando
✅ Todos los endpoints accesibles sin API key
✅ Integración Lambda correcta
✅ WebSocket API funcionando
✅ CloudWatch logs habilitados
✅ CORS configurado

## Comandos Útiles

```bash
# Ver endpoint
terraform output api_gateway_rest_endpoint

# Probar API
curl "$(terraform output -raw api_gateway_rest_endpoint)/people-count/STOP001?mode=latest"

# Ver logs de Lambda
aws logs tail /aws/lambda/bus-simulator-people-count --follow --region eu-west-1

# Ver deployment actual
aws apigateway get-rest-api --rest-api-id 0w08yrrx1a --region eu-west-1
```
