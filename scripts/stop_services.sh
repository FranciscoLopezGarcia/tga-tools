#!/bin/bash
# ================================================================
# TGA-TOOLS - Stop Services
# Detiene todos los servicios
# ================================================================

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "======================================"
echo "TGA-TOOLS - Stopping Services"
echo "======================================"

# ================================================================
# DETENER BACKENDS
# ================================================================
echo ""
echo -e "${YELLOW}🛑 Deteniendo backends...${NC}"

# Extractos Flask
if [ -f "$PROJECT_ROOT/logs/extractos-flask.pid" ]; then
    kill $(cat "$PROJECT_ROOT/logs/extractos-flask.pid") 2>/dev/null
    rm "$PROJECT_ROOT/logs/extractos-flask.pid"
    echo -e "${GREEN}  ✓ Extractos Flask detenido${NC}"
fi

# Extractos Celery
if [ -f "$PROJECT_ROOT/logs/extractos-celery.pid" ]; then
    kill $(cat "$PROJECT_ROOT/logs/extractos-celery.pid") 2>/dev/null
    rm "$PROJECT_ROOT/logs/extractos-celery.pid"
    echo -e "${GREEN}  ✓ Extractos Celery detenido${NC}"
fi

# Siradig Flask
if [ -f "$PROJECT_ROOT/logs/siradig-flask.pid" ]; then
    kill $(cat "$PROJECT_ROOT/logs/siradig-flask.pid") 2>/dev/null
    rm "$PROJECT_ROOT/logs/siradig-flask.pid"
    echo -e "${GREEN}  ✓ Siradig Flask detenido${NC}"
fi

# Consolidado Flask
if [ -f "$PROJECT_ROOT/logs/consolidado-flask.pid" ]; then
    kill $(cat "$PROJECT_ROOT/logs/consolidado-flask.pid") 2>/dev/null
    rm "$PROJECT_ROOT/logs/consolidado-flask.pid"
    echo -e "${GREEN}  ✓ Consolidado Flask detenido${NC}"
fi

# ================================================================
# DETENER NGINX
# ================================================================
echo ""
echo -e "${YELLOW}🌐 Deteniendo Nginx...${NC}"

if command -v systemctl &> /dev/null; then
    sudo systemctl stop nginx
else
    sudo nginx -s stop
fi

echo -e "${GREEN}✓ Nginx detenido${NC}"

# ================================================================
# DETENER REDIS (opcional)
# ================================================================
echo ""
echo -e "${YELLOW}🔴 Detener Redis? (y/N)${NC}"
read -r response

if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
    if command -v systemctl &> /dev/null; then
        sudo systemctl stop redis-server || sudo systemctl stop redis
    else
        redis-cli shutdown
    fi
    echo -e "${GREEN}✓ Redis detenido${NC}"
fi

# ================================================================
# RESUMEN
# ================================================================
echo ""
echo "======================================"
echo -e "${GREEN}✓ SERVICIOS DETENIDOS${NC}"
echo "======================================"
echo ""