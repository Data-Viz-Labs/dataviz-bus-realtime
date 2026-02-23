#!/bin/bash
# Script para probar el API Gateway del simulador de buses de Madrid
# Uso: ./test_api.sh

set -e

# Colores para output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Obtener el endpoint del API
API_ENDPOINT=$(terraform output -raw api_gateway_rest_endpoint 2>/dev/null)

if [ -z "$API_ENDPOINT" ]; then
    echo -e "${RED}Error: No se pudo obtener el endpoint del API${NC}"
    echo "Asegúrate de estar en el directorio terraform y que la infraestructura esté desplegada"
    exit 1
fi

echo -e "${BLUE}=== Probando API Gateway del Simulador de Buses ===${NC}"
echo -e "Endpoint: ${GREEN}$API_ENDPOINT${NC}\n"

# Test 1: People Count API
echo -e "${BLUE}1. Probando People Count API${NC}"
echo "   GET /people-count/STOP001?mode=latest"
curl -s "$API_ENDPOINT/people-count/STOP001?mode=latest" | jq .
echo ""

# Test 2: Bus Position API (by bus_id)
echo -e "${BLUE}2. Probando Bus Position API (por bus_id)${NC}"
echo "   GET /bus-position/BUS001?mode=latest"
curl -s "$API_ENDPOINT/bus-position/BUS001?mode=latest" | jq .
echo ""

# Test 3: Bus Position API (by line_id)
echo -e "${BLUE}3. Probando Bus Position API (por line_id)${NC}"
echo "   GET /bus-position/line/LINE001?mode=latest"
curl -s "$API_ENDPOINT/bus-position/line/LINE001?mode=latest" | jq .
echo ""

# Test 4: Sensors API
echo -e "${BLUE}4. Probando Sensors API${NC}"
echo "   GET /sensors/bus/BUS001?mode=latest"
curl -s "$API_ENDPOINT/sensors/bus/BUS001?mode=latest" | jq .
echo ""

# Test 5: Sensors API (stop)
echo -e "${BLUE}5. Probando Sensors API (parada)${NC}"
echo "   GET /sensors/stop/STOP001?mode=latest"
curl -s "$API_ENDPOINT/sensors/stop/STOP001?mode=latest" | jq .
echo ""

echo -e "${GREEN}=== Pruebas completadas ===${NC}"
echo -e "\n${BLUE}Nota:${NC} Los errores 'No data found' son normales si no hay datos en Timestream todavía."
echo -e "Lo importante es que el API responde correctamente con estructura JSON válida.\n"

# Mostrar WebSocket endpoint
WS_ENDPOINT=$(terraform output -raw api_gateway_websocket_endpoint 2>/dev/null)
if [ -n "$WS_ENDPOINT" ]; then
    echo -e "${BLUE}WebSocket Endpoint:${NC} ${GREEN}$WS_ENDPOINT${NC}"
    echo -e "Para probar WebSocket, usa una herramienta como wscat:"
    echo -e "  ${GREEN}wscat -c $WS_ENDPOINT${NC}\n"
fi
