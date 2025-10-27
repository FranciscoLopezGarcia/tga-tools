# TGA Herramientas - Frontend

Sistema de herramientas web para procesamiento de archivos PDF y Excel.

## 📁 Estructura del Proyecto

```
/
├── index.html              # Página principal (home)
├── extractos.html          # Herramienta de Extractos
├── siradig.html            # Herramienta de Siradig
├── consolidador.html       # Herramienta de Consolidador
├── css/
│   └── style.css           # Estilos unificados
└── js/
    ├── main.js             # JavaScript para home
    ├── api.js              # Conexión con backend
    ├── components.js       # Componentes reutilizables
    ├── extractos.js        # Lógica de Extractos
    ├── siradig.js          # Lógica de Siradig
    └── consolidador.js     # Lógica de Consolidador
```

## 🚀 Características

### Diseño
- **Minimalista y profesional**: Basado en la identidad de TGA Consultora
- **Responsive**: Optimizado para escritorio
- **Componentes reutilizables**: CSS y JS modular
- **Colores corporativos**: Azul #1e3a8a, grises profesionales

### Funcionalidades
- ✅ Drag & Drop para subir archivos
- ✅ Validación de archivos (tipo, tamaño)
- ✅ Barra de progreso real conectada al backend
- ✅ Sistema de alertas centradas
- ✅ Descarga de resultados (ZIP/Excel)
- ✅ Descarga de logs completos
- ✅ Listado de éxitos y errores separados

## 🔧 Configuración del Backend

### Endpoints esperados

El archivo `js/api.js` espera los siguientes endpoints por herramienta:

#### Extractos
```
POST   /api/extractos/upload            # Subir archivos, retorna {job_id}
GET    /api/extractos/status/{jobId}    # Consultar estado
GET    /api/extractos/download/{jobId}  # Descargar ZIP
GET    /api/extractos/log/{jobId}       # Descargar log
```

#### Siradig
```
POST   /api/siradig/upload
GET    /api/siradig/status/{jobId}
GET    /api/siradig/download/{jobId}
GET    /api/siradig/log/{jobId}
```

#### Consolidador
```
POST   /api/consolidador/upload
GET    /api/consolidador/status/{jobId}
GET    /api/consolidador/download/{jobId}
GET    /api/consolidador/log/{jobId}
```

### Formato de respuesta esperado

#### POST /upload
```json
{
  "job_id": "abc123..."
}
```

#### GET /status/{jobId}
```json
{
  "state": "PROGRESS",           // PENDING | PROGRESS | SUCCESS | FAILURE
  "progress": 45,                // 0-100
  "status": "Procesando archivo 3 de 10...",
  "results": {                   // Solo cuando state === SUCCESS
    "total": 10,
    "success": 8,
    "errors": 2,
    "results": [
      {
        "filename": "archivo1.pdf",
        "status": "success",
        "records": 150
      },
      {
        "filename": "archivo2.pdf",
        "status": "error",
        "error": "Formato inválido"
      }
    ]
  }
}
```

#### GET /download/{jobId}
- Retorna un archivo binario (ZIP o Excel)
- Content-Type: application/zip o application/vnd.openxmlformats-officedocument.spreadsheetml.sheet

#### GET /log/{jobId}
- Retorna un archivo de texto con el log completo
- Content-Type: text/plain

## 📝 Personalización

### Cambiar URL base del API
Edita `js/api.js`:
```javascript
const API_BASE_URL = '/api'; // Cambiar según tu backend
```

### Ajustar validaciones
Edita los archivos `js/extractos.js`, `js/siradig.js`, `js/consolidador.js`:
```javascript
const validation = validateFiles(newFiles, {
    maxFiles: 50,                    // Máximo de archivos
    maxSize: 50 * 1024 * 1024,      // Tamaño máximo (bytes)
    allowedExtensions: ['.pdf']      // Extensiones permitidas
});
```

### Modificar colores
Edita `css/style.css`:
```css
:root {
    --primary: #1e3a8a;        /* Azul principal */
    --primary-dark: #1e40af;   /* Azul oscuro */
    --success: #059669;        /* Verde éxito */
    --error: #dc2626;          /* Rojo error */
}
```

## 🎨 Componentes Reutilizables

### Mostrar alerta
```javascript
showAlert('Mensaje de éxito', 'success');
showAlert('Error al procesar', 'error');
showAlert('Advertencia', 'warning');
showAlert('Información', 'info');
```

### Actualizar progreso
```javascript
updateProgress(75, 'Procesando archivo 7 de 10...');
```

### Mostrar/Ocultar secciones
```javascript
showSection('progressSection');
hideSection('uploadSection');
```

### Formatear tamaño de archivo
```javascript
formatFileSize(1024);        // "1 KB"
formatFileSize(5242880);     // "5 MB"
```

## 🔄 Flujo de Usuario

1. **Home** → Usuario selecciona una herramienta
2. **Drag & Drop** → Usuario arrastra/selecciona archivos
3. **Validación** → Sistema valida tipo y tamaño
4. **Lista de archivos** → Usuario ve archivos y puede eliminar
5. **Procesar** → Sistema sube archivos al backend
6. **Polling** → Frontend consulta estado cada 2 segundos
7. **Progreso** → Barra se actualiza en tiempo real
8. **Resultados** → Muestra estadísticas y detalle
9. **Descarga** → Usuario descarga ZIP/Excel y log

## 🛠️ Desarrollo

### Levantar servidor local
```bash
# Con Python
python -m http.server 8000

# Con Node.js
npx http-server

# Con PHP
php -S localhost:8000
```

Abrir: `http://localhost:8000`

## 📱 Navegadores soportados
- Chrome/Edge (últimas versiones)
- Firefox (últimas versiones)
- Safari (últimas versiones)

## 📄 Notas

- **Sin login**: Por el momento no hay autenticación
- **Desktop only**: Optimizado para escritorio
- **Vanilla JS**: Sin frameworks, máxima velocidad
- **Modular**: Fácil de extender con nuevas herramientas

## 🐛 Troubleshooting

### Los archivos no se suben
- Verificar que el backend esté corriendo
- Revisar la URL en `js/api.js`
- Verificar CORS en el backend

### La barra de progreso no se mueve
- Verificar que el endpoint `/status/{jobId}` retorne el formato correcto
- Revisar consola del navegador (F12)

### Error al descargar
- Verificar que el endpoint `/download/{jobId}` retorne un blob
- Revisar headers de Content-Type

## 📞 Soporte

Para dudas o modificaciones, contactar al equipo de desarrollo.

---

**TGA Consultora** - Mendoza, Argentina © 2025
