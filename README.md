# 🛠️ TGA Tools

Sistema web para procesamiento automatizado de documentos PDF y generación de reportes Excel para TGA Auditores & Consultores.

## 📋 Características

- **Extractos Bancarios**: Extracción automatizada de datos desde extractos PDF de múltiples bancos
- **Siradig**: Procesamiento de formularios F.572 Web (AFIP/ARCA)
- **Consolidador**: Unificación de consolidados mensuales

## 🏗️ Estructura del Proyecto

```
tga-tools/
├── backend/
│   ├── app.py                 # Aplicación principal Flask
│   ├── config.py              # Configuración
│   ├── requirements.txt       # Dependencias Python
│   ├── routes/                # Endpoints de API
│   │   ├── __init__.py
│   │   ├── extractos.py
│   │   ├── siradig.py
│   │   └── consolidador.py
│   ├── services/              # Lógica de negocio
│   │   ├── __init__.py
│   │   ├── extractos_service.py
│   │   ├── siradig_service.py
│   │   └── consolidador_service.py
│   ├── uploads/               # Archivos temporales (git-ignored)
│   ├── output/                # Resultados procesados (git-ignored)
│   └── logs/                  # Logs de la aplicación (git-ignored)
└── frontend/
    ├── index.html             # Página principal
    ├── extractos.html         # Vista Extractos
    ├── siradig.html           # Vista Siradig
    ├── consolidador.html      # Vista Consolidador
    ├── css/
    │   └── style.css
    └── js/
        ├── api.js             # Cliente API
        ├── components.js      # Componentes reutilizables
        ├── main.js
        ├── extractos.js
        ├── siradig.js
        └── consolidador.js
```

## 🚀 Instalación

### Prerrequisitos

- Python 3.11+
- pip
- Git

### En Linux/Mac (opcional para camelot):
```bash
sudo apt-get update
sudo apt-get install -y ghostscript python3-tk tesseract-ocr tesseract-ocr-spa
```

### Pasos de instalación

1. **Clonar el repositorio**
```bash
git clone <tu-repositorio>
cd tga-tools
```

2. **Crear entorno virtual**
```bash
cd backend
python -m venv venv
```

3. **Activar entorno virtual**

Windows:
```bash
venv\Scripts\activate
```

Linux/Mac:
```bash
source venv/bin/activate
```

4. **Instalar dependencias**
```bash
pip install -r requirements.txt
```

5. **Configurar variables de entorno** (opcional)

Crear archivo `.env` en la carpeta `backend/`:
```env
SECRET_KEY=tu-secret-key-aqui
FLASK_DEBUG=1
PORT=5000
CORS_ORIGINS=http://localhost:5000,http://127.0.0.1:5000
```

6. **Crear carpetas necesarias**
```bash
mkdir -p uploads output logs
```

## ▶️ Ejecución

### Desarrollo

```bash
cd backend
python app.py
```

El servidor estará disponible en: **http://localhost:5000**

### Producción (con Gunicorn)

```bash
cd backend
gunicorn -w 4 -b 0.0.0.0:5000 --timeout 120 "app:create_app()"
```

## 📡 API Endpoints

### Extractos

- `POST /api/extractos/upload` - Subir archivos PDF
- `GET /api/extractos/status/<job_id>` - Consultar estado
- `GET /api/extractos/download/<job_id>` - Descargar resultado
- `GET /api/extractos/log/<job_id>` - Descargar log

### Siradig

- `POST /api/siradig/upload` - Subir formularios F.572
- `GET /api/siradig/status/<job_id>` - Consultar estado
- `GET /api/siradig/download/<job_id>` - Descargar resultado
- `GET /api/siradig/log/<job_id>` - Descargar log

### Consolidador

- `POST /api/consolidador/upload` - Subir archivos Excel
- `GET /api/consolidador/status/<job_id>` - Consultar estado
- `GET /api/consolidador/download/<job_id>` - Descargar resultado
- `GET /api/consolidador/log/<job_id>` - Descargar log

### Health Check

- `GET /api/health` - Verificar estado del servidor

## 🔧 Desarrollo

### Agregar una nueva herramienta

1. Crear route en `routes/tu_herramienta.py`
2. Crear service en `services/tu_herramienta_service.py`
3. Registrar blueprint en `app.py`
4. Crear vista HTML en `frontend/tu_herramienta.html`
5. Crear lógica JS en `frontend/js/tu_herramienta.js`

### Testing

```bash
# Ejecutar tests (cuando existan)
pytest tests/
```

## 📝 Logs

Los logs se guardan en la carpeta `logs/` y en la consola con el formato:

```
YYYY-MM-DD HH:MM:SS - nombre_modulo - NIVEL - mensaje
```

## ⚠️ Troubleshooting

### Error: "No se enviaron archivos"
- Verificar que el frontend esté enviando correctamente los archivos
- Revisar la consola del navegador (F12) para errores de CORS

### Error: "ModuleNotFoundError"
- Asegurarse de tener el entorno virtual activado
- Reinstalar dependencias: `pip install -r requirements.txt`

### El servidor no inicia
- Verificar que el puerto 5000 no esté ocupado
- Revisar los logs en consola

### Camelot no funciona
- Instalar ghostscript: `sudo apt-get install ghostscript` (Linux)
- En Windows, descargar Ghostscript desde su sitio oficial

## 🤝 Contribuir

1. Fork el proyecto
2. Crear una rama (`git checkout -b feature/nueva-funcionalidad`)
3. Commit los cambios (`git commit -m 'Agregar nueva funcionalidad'`)
4. Push a la rama (`git push origin feature/nueva-funcionalidad`)
5. Abrir un Pull Request

## 📄 Licencia

Uso interno de TGA Auditores & Consultores - Mendoza, Argentina

## 👥 Contacto

TGA Auditores & Consultores  
Mendoza, Argentina

---

**Versión:** 1.0.0  
**Última actualización:** Octubre 2025