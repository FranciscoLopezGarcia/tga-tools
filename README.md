# TGA-Tools

Sistema unificado de herramientas administrativas con frontend moderno y backend modular.

## 🚀 Características

- **Dashboard Central**: Landing page con acceso a todas las herramientas
- **Extractos Bancarios**: Procesamiento async con Celery de PDFs bancarios a Excel
- **Siradig**: Sistema de registro y análisis digital
- **Frontend Unificado**: React-like con diseño consistente
- **Backend Modular**: Flask apps independientes con código compartido

## 📋 Requisitos

- Python 3.8+
- Redis
- Nginx
- Tesseract OCR
- Poppler utils

## 🛠️ Instalación

### 1. Clonar repositorio
```bash
git clone https://github.com/TU-USUARIO/tga-tools.git
cd tga-tools
```

### 2. Ejecutar setup
```bash
chmod +x scripts/*.sh
./scripts/setup.sh
```

### 3. Configurar variables de entorno
```bash
cp config/.env.example config/.env
nano config/.env  # Editar con tus valores
```

### 4. Iniciar servicios
```bash
./scripts/start_services.sh
```

## 🌐 URLs

- **Dashboard**: http://localhost
- **Extractos**: http://localhost/apps/extractos
- **Siradig**: http://localhost/apps/siradig

## 📁 Estructura
```
tga-tools/
├── frontend/           # Frontend unificado
│   ├── dashboard/     # Landing page
│   ├── shared/        # CSS, JS compartido
│   └── apps/          # Apps específicas
├── backend/           # Backend modular
│   ├── shared/        # Código compartido
│   ├── extractos/     # Backend extractos
│   └── siradig/       # Backend siradig
├── config/            # Configuraciones
└── scripts/           # Scripts de deployment
```

## 🔧 Comandos
```bash
# Iniciar servicios
./scripts/start_services.sh

# Detener servicios
./scripts/stop_services.sh

# Deploy (actualizar desde Git)
./scripts/deploy.sh

# Ver logs
tail -f logs/extractos-flask.log
tail -f logs/siradig-flask.log
```

## 🐛 Troubleshooting

### Redis no conecta
```bash
sudo systemctl status redis
sudo systemctl restart redis
```

### Nginx error
```bash
sudo nginx -t  # Verificar config
sudo systemctl restart nginx
```

### Backend no responde
```bash
# Ver logs
tail -f logs/extractos-flask.log

# Reiniciar
./scripts/stop_services.sh
./scripts/start_services.sh
```

## 🔐 Cloudflare Tunnel

### Instalación
```bash
# Descargar cloudflared
wget https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64
sudo mv cloudflared-linux-amd64 /usr/local/bin/cloudflared
sudo chmod +x /usr/local/bin/cloudflared

# Login
cloudflared tunnel login

# Crear tunnel
cloudflared tunnel create tga-tools

# Configurar
cat > ~/.cloudflared/config.yml << EOF
tunnel: TU-TUNNEL-ID
credentials-file: /home/USER/.cloudflared/TU-TUNNEL-ID.json

ingress:
  - hostname: tga-tools.tudominio.com
    service: http://localhost:80
  - service: http_status:404
EOF

# Crear ruta DNS
cloudflared tunnel route dns tga-tools tga-tools.tudominio.com

# Instalar como servicio
sudo cloudflared service install
sudo systemctl start cloudflared
sudo systemctl enable cloudflared
```

## 📝 Licencia

MIT

## 👤 Autor

Tu Nombre