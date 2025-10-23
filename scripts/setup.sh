#!/bin/bash
# ================================================================
# TGA-TOOLS - Setup Script
# Instala dependencias y configura el entorno
# ================================================================

set -e

echo "======================================"
echo "TGA-TOOLS - Setup"
echo "======================================"

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Variables
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"
FRONTEND_DIR="$PROJECT_ROOT/frontend"

echo -e "${GREEN}📂 Proyecto: $PROJECT_ROOT${NC}"

# ================================================================
# VERIFICAR SISTEMA OPERATIVO
# ================================================================
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    OS="linux"
    echo -e "${GREEN}✓ Sistema: Linux${NC}"
elif [[ "$OSTYPE" == "darwin"* ]]; then
    OS="mac"
    echo -e "${GREEN}✓ Sistema: macOS${NC}"
else
    echo -e "${RED}✗ Sistema no soportado: $OSTYPE${NC}"
    exit 1
fi

# ================================================================
# INSTALAR DEPENDENCIAS DEL SISTEMA
# ================================================================
echo ""
echo -e "${YELLOW}📦 Instalando dependencias del sistema...${NC}"

if [ "$OS" == "linux" ]; then
    # Ubuntu/Debian
    if command -v apt-get &> /dev/null; then
        sudo apt-get update
        sudo apt-get install -y \
            python3 \
            python3-pip \
            python3-venv \
            redis-server \
            nginx \
            tesseract-ocr \
            tesseract-ocr-spa \
            poppler-utils \
            git
    
    # RedHat/CentOS/Fedora
    elif command -v yum &> /dev/null; then
        sudo yum update -y
        sudo yum install -y \
            python3 \
            python3-pip \
            redis \
            nginx \
            tesseract \
            poppler-utils \
            git
    fi

elif [ "$OS" == "mac" ]; then
    # macOS con Homebrew
    if ! command -v brew &> /dev/null; then
        echo -e "${RED}✗ Homebrew no está instalado${NC}"
        echo "Instala Homebrew desde: https://brew.sh"
        exit 1
    fi
    
    brew install python redis nginx tesseract tesseract-lang poppler
fi

echo -e "${GREEN}✓ Dependencias del sistema instaladas${NC}"

# ================================================================
# CREAR ENTORNOS VIRTUALES
# ================================================================
echo ""
echo -e "${YELLOW}🐍 Creando entornos virtuales...${NC}"

# Extractos
echo "  → Extractos..."
cd "$BACKEND_DIR/extractos"
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
deactivate
echo -e "${GREEN}  ✓ Extractos${NC}"

# Siradig
echo "  → Siradig..."
cd "$BACKEND_DIR/siradig"
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
deactivate
echo -e "${GREEN}  ✓ Siradig${NC}"

# Consolidado (si existe)
if [ -f "$BACKEND_DIR/consolidado/requirements.txt" ]; then
    echo "  → Consolidado..."
    cd "$BACKEND_DIR/consolidado"
    python3 -m venv venv
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
    deactivate
    echo -e "${GREEN}  ✓ Consolidado${NC}"
fi

# ================================================================
# CONFIGURAR VARIABLES DE ENTORNO
# ================================================================
echo ""
echo -e "${YELLOW}⚙️  Configurando variables de entorno...${NC}"

cd "$PROJECT_ROOT"

if [ ! -f "config/.env" ]; then
    cp config/.env.example config/.env
    echo -e "${YELLOW}  ⚠️  Archivo .env creado. Edítalo con tus configuraciones.${NC}"
else
    echo -e "${GREEN}  ✓ Archivo .env ya existe${NC}"
fi

# ================================================================
# CREAR DIRECTORIOS NECESARIOS
# ================================================================
echo ""
echo -e "${YELLOW}📁 Creando directorios...${NC}"

mkdir -p "$BACKEND_DIR/extractos/uploads"
mkdir -p "$BACKEND_DIR/extractos/output"
mkdir -p "$BACKEND_DIR/siradig/uploads"
mkdir -p "$BACKEND_DIR/siradig/output"
mkdir -p "$BACKEND_DIR/consolidado/uploads"
mkdir -p "$BACKEND_DIR/consolidado/output"
mkdir -p logs

echo -e "${GREEN}✓ Directorios creados${NC}"

# ================================================================
# CONFIGURAR NGINX
# ================================================================
echo ""
echo -e "${YELLOW}🌐 Configurando Nginx...${NC}"

# Backup de configuración existente
if [ -f "/etc/nginx/nginx.conf" ]; then
    sudo cp /etc/nginx/nginx.conf /etc/nginx/nginx.conf.backup.$(date +%Y%m%d_%H%M%S)
    echo -e "${GREEN}  ✓ Backup de nginx.conf creado${NC}"
fi

# Copiar nueva configuración
sudo cp "$PROJECT_ROOT/config/nginx.conf" /etc/nginx/nginx.conf

# Actualizar paths en nginx.conf
sudo sed -i "s|/var/www/tga-tools|$PROJECT_ROOT|g" /etc/nginx/nginx.conf

# Verificar configuración
if sudo nginx -t; then
    echo -e "${GREEN}  ✓ Configuración de Nginx válida${NC}"
else
    echo -e "${RED}  ✗ Error en configuración de Nginx${NC}"
    exit 1
fi

# ================================================================
# CONFIGURAR REDIS
# ================================================================
echo ""
echo -e "${YELLOW}🔴 Configurando Redis...${NC}"

if command -v systemctl &> /dev/null; then
    sudo systemctl enable redis-server || sudo systemctl enable redis
    sudo systemctl start redis-server || sudo systemctl start redis
    echo -e "${GREEN}  ✓ Redis habilitado y iniciado${NC}"
else
    echo -e "${YELLOW}  ⚠️  Inicia Redis manualmente${NC}"
fi

# ================================================================
# PERMISOS
# ================================================================
echo ""
echo -e "${YELLOW}🔐 Configurando permisos...${NC}"

chmod +x "$PROJECT_ROOT/scripts/"*.sh
chown -R $USER:$USER "$PROJECT_ROOT"

echo -e "${GREEN}✓ Permisos configurados${NC}"

# ================================================================
# RESUMEN
# ================================================================
echo ""
echo "======================================"
echo -e "${GREEN}✓ SETUP COMPLETADO${NC}"
echo "======================================"
echo ""
echo "Siguiente paso:"
echo "  1. Edita config/.env con tus configuraciones"
echo "  2. Ejecuta: ./scripts/start_services.sh"
echo ""
echo "URLs:"
echo "  Dashboard:  http://localhost"
echo "  Extractos:  http://localhost/apps/extractos"
echo "  Siradig:    http://localhost/apps/siradig"
echo ""