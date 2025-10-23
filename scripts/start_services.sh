#!/bin/bash
# ================================================================
# TGA-TOOLS - Start Services
# Inicia todos los servicios
# ================================================================

set -e

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"

# Cargar variables de entorno
if [ -f "$PROJECT_ROOT/config/.env" ]; then
    source "$PROJECT_ROOT/config/.env"
fi

echo "======================================"
echo "TGA-TOOLS - Starting Services"
echo "======================================"

# ================================================================
# INICIAR REDIS
# ================================================================
echo ""
echo -e "${YELLOW}🔴 Iniciando Redis...${NC}"

if command -v systemctl &> /dev/null; then
    sudo systemctl start redis-server || sudo systemctl start redis
    echo -e "${GREEN}✓ Redis iniciado${NC}"
else
    redis-server --daemonize yes
    echo -e "${GREEN}✓ Redis iniciado (daemon)${NC}"
fi

# ================================================================
# INICIAR NGINX
# ================================================================
echo ""
echo -e "${YELLOW}🌐 Iniciando Nginx...${NC}"

if command -v systemctl &> /dev/null; then
    sudo systemctl start nginx
    echo -e "${GREEN}✓ Nginx iniciado${NC}"
else
    sudo nginx
    echo -e "${GREEN}✓ Nginx iniciado${NC}"
fi

# ================================================================
# INICIAR BACKEND - EXTRACTOS
# ================================================================
echo ""
echo -e "${YELLOW}📦 Iniciando Extractos Backend...${NC}"

cd "$BACKEND_DIR/extractos"

# Flask
source venv/bin/activate
nohup waitress-serve \
    --host=127.0.0.1 \
    --port=${EXTRACTOS_PORT:-5001} \
    --threads=8 \
    app:app > "$PROJECT_ROOT/logs/extractos-flask.log" 2>&1 &
echo $! > "$PROJECT_ROOT/logs/extractos-flask.pid"
deactivate

echo -e "${GREEN}  ✓ Flask en puerto ${EXTRACTOS_PORT:-5001}${NC}"

# Celery Worker
source venv/bin/activate
nohup celery -A celery_worker worker \
    --loglevel=info \
    --concurrency=4 \
    --pool=solo > "$PROJECT_ROOT/logs/extractos-celery.log" 2>&1 &
echo $! > "$PROJECT_ROOT/logs/extractos-celery.pid"
deactivate

echo -e "${GREEN}  ✓ Celery Worker${NC}"

# ================================================================
# INICIAR BACKEND - SIRADIG
# ================================================================
echo ""
echo -e "${YELLOW}🏠 Iniciando Siradig Backend...${NC}"

cd "$BACKEND_DIR/siradig"

source venv/bin/activate
nohup waitress-serve \
    --host=127.0.0.1 \
    --port=${SIRADIG_PORT:-5002} \
    --threads=8 \
    app:app > "$PROJECT_ROOT/logs/siradig-flask.log" 2>&1 &
echo $! > "$PROJECT_ROOT/logs/siradig-flask.pid"
deactivate

echo -e "${GREEN}  ✓ Flask en puerto ${SIRADIG_PORT:-5002}${NC}"

# ================================================================
# INICIAR BACKEND - CONSOLIDADO (si existe)
# ================================================================
if [ -f "$BACKEND_DIR/consolidado/app.py" ]; then
    echo ""
    echo -e "${YELLOW}📊 Iniciando Consolidado Backend...${NC}"
    
    cd "$BACKEND_DIR/consolidado"
    
    source venv/bin/activate
    nohup waitress-serve \
        --host=127.0.0.1 \
        --port=${CONSOLIDADO_PORT:-5003} \
        --threads=8 \
        app:app > "$PROJECT_ROOT/logs/consolidado-flask.log" 2>&1 &
    echo $! > "$PROJECT_ROOT/logs/consolidado-flask.pid"
    deactivate
    
    echo -e "${GREEN}  ✓ Flask en puerto ${CONSOLIDADO_PORT:-5003}${NC}"
fi

# ================================================================
# VERIFICAR SERVICIOS
# ================================================================
echo ""
echo -e "${YELLOW}🔍 Verificando servicios...${NC}"

sleep 3

# Verificar Redis
if redis-cli ping > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Redis${NC}"
else
    echo -e "${RED}✗ Redis${NC}"
fi

# Verificar Nginx
if curl -s http://localhost/health > /dev/null; then
    echo -e "${GREEN}✓ Nginx${NC}"
else
    echo -e "${RED}✗ Nginx${NC}"
fi

# Verificar Extractos
if curl -s http://localhost:${EXTRACTOS_PORT:-5001}/api/health > /dev/null; then
    echo -e "${GREEN}✓ Extractos${NC}"
else
    echo -e "${RED}✗ Extractos${NC}"
fi

# Verificar Siradig
if curl -s http://localhost:${SIRADIG_PORT:-5002}/api/health > /dev/null; then
    echo -e "${GREEN}✓ Siradig${NC}"
else
    echo -e "${RED}✗ Siradig${NC}"
fi

# ================================================================
# RESUMEN
# ================================================================
echo ""
echo "======================================"
echo -e "${GREEN}✓ SERVICIOS INICIADOS${NC}"
echo "======================================"
echo ""
echo "URLs:"
echo "  Dashboard:  http://localhost"
echo "  Extractos:  http://localhost/apps/extractos"
echo "  Siradig:    http://localhost/apps/siradig"
echo ""
echo "Logs en: $PROJECT_ROOT/logs/"
echo ""
echo "Para detener: ./scripts/stop_services.sh"
echo ""