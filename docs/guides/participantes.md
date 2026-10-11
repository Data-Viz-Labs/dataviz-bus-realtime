# Guía para participantes

La organización te dará **una clave de grupo** y estas direcciones:

| Qué | Dónde |
|---|---|
| Mapa en vivo | `https://<sitio>/` |
| Documentación interactiva (REST y MQTT) | `https://<sitio>/docs.html` |
| API HTTP | `https://<api>` (cabecera `x-api-key: <clave>`) |
| Servidor MCP | `https://<api>/mcp` (misma cabecera) |
| MQTT (tiempo real) | `wss://<endpoint>/mqtt` (autorizador `madrid-bus-groups`, tu clave como `token`) |

## Qué hay

Una simulación de 40 líneas reales de EMT Madrid (1.723 paradas, 712 autobuses) que corre en
tiempo real, con **años de histórico** detrás. Los datos cuentan cosas que pasaron en Madrid:
búscalas en los datos, no en el código.

- **Tiempo real**: posiciones, ocupación y espera en paradas cada 5 s por MQTT
  (`madrid/lines/{línea}/state`) y cada llegada a parada con subidas y bajadas
  (`madrid/lines/{línea}/calls`). Contrato: [api/asyncapi.yaml](../api/asyncapi.yaml).
- **Histórico**: tablas horarias por línea y por parada para todo el periodo; llegadas a parada
  y posiciones para los últimos días. Diccionario: [api/datasets.md](../api/datasets.md).
- **API**: red, estado en vivo, histórico, SQL y descarga de ficheros Parquet.
  Contrato: [api/openapi.yaml](../api/openapi.yaml).
- **MCP**: las mismas consultas como herramientas para agentes de IA. Guía: [api/mcp.md](../api/mcp.md).

## Empezar en 5 minutos

```bash
export API_URL=https://<api>  API_KEY=<clave>

# Red y estado en vivo
curl -s -H "x-api-key: $API_KEY" "$API_URL/v1/lines" | head -c 400
curl -s -H "x-api-key: $API_KEY" "$API_URL/v1/live/lines/27"

# Histórico horario de una línea
curl -s -H "x-api-key: $API_KEY" "$API_URL/v1/history/lines/27/hourly?from=2025-10-01&to=2025-10-31"

# SQL (filtra siempre por la partición: month o dt)
curl -s -H "x-api-key: $API_KEY" -H "content-type: application/json" "$API_URL/v1/sql" \
  -d '{"query": "SELECT date, sum(boardings) AS viajeros FROM line_hourly WHERE month = '\''2025-10'\'' GROUP BY date ORDER BY date"}'

# Ficheros Parquet para pandas, DuckDB, Spark...
curl -s -H "x-api-key: $API_KEY" "$API_URL/v1/datasets/line_hourly/files?from=2025-01-01&to=2025-12-31"
```

Ejemplos completos en [examples/](../../examples/):

- `api_client.py`: API con la biblioteca estándar.
- `mqtt_subscribe.py`: tiempo real; necesita `pip install paho-mqtt`.
- `mcp_config.json`: configuración del cliente MCP.

Con Claude Code: `claude mcp add --transport http madrid-bus https://<api>/mcp --header "x-api-key: <clave>"`.

## Ideas para empezar a contar historias

- ¿Qué líneas van más llenas en hora punta? ¿Dependen de lo cerca que estén del centro?
- ¿Hay alguna línea que vaya siempre por encima de su capacidad?
- ¿Qué días no hubo servicio? ¿Qué pasó antes y después?
- ¿Dónde y cuándo aparecen aglomeraciones por la tarde-noche? ¿Se repiten los domingos? ¿Y en verano?
- ¿Cómo cambian los tiempos de viaje entre periodo escolar y vacaciones?
- ¿Qué ocurre en el centro ciertos sábados de verano?

## Límites

- Cada consulta SQL escanea como máximo 2 GiB y devuelve como máximo 10.000 filas.
- `stop-calls`: como mucho 7 días por petición; `positions`: 1 día.
- Las horas de servicio son de 06:00 a 23:59, hora local de Madrid.
