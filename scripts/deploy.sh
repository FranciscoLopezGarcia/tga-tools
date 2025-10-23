#!/bin/bash
# ================================================================
# TGA-TOOLS - Deploy Script
# Deploy a producción (pull desde Git + restart)
# ================================================================

set -e

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "======================================"
echo "TGA-TOOLS - Deploy"
echo "======================================"

# ================================================================
# GIT PULL
# ================================================================
echo ""
echo -e "${YELLOW}📥 Actualizando código desde Git...${NC}"

cd "$PROJECT_ROOT"
git pull origin main

echo -e "${GREEN}✓ Código actualizado${NC}"

# ================================================================
# ACTUALIZAR DEPENDENCIAS
# ================================================================
echo ""
echo -e "${YELLOW}📦 Actualizando dependencias...${NC}"

# Extractos
cd "$PROJECT_ROOT/backend/extractos"
source venv/bin/activate
pip install -r requirements.txt --upgrade
deactivate

# Siradig
cd "$PROJECT_ROOT/backend/siradig"
source venv/bin/activate
pip install -r requirements.txt --upgrade
deactivate

echo -e "${GREEN}✓ Dependencias actualizadas${NC}"

# ================================================================
# REINICIAR SERVICIOS
# ================================================================
echo ""
echo -e "${YELLOW}🔄 Reiniciando servicios...${NC}"

"$PROJECT_ROOT/scripts/stop_services.sh"
sleep 2
"$PROJECT_ROOT/scripts/start_services.sh"

echo ""
echo "======================================"
echo -e "${GREEN}✓ DEPLOY COMPLETADO${NC}"
echo "======================================"
echo ""