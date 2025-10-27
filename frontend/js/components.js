/**
 * Components.js - Componentes reutilizables
 * Funciones compartidas entre todas las herramientas
 */

/**
 * Mostrar/Ocultar secciones
 */
function showSection(sectionId) {
    const section = document.getElementById(sectionId);
    if (section) {
        section.classList.remove('hidden');
    }
}

function hideSection(sectionId) {
    const section = document.getElementById(sectionId);
    if (section) {
        section.classList.add('hidden');
    }
}

/**
 * Mostrar alerta
 * @param {string} message - Mensaje a mostrar
 * @param {string} type - Tipo de alerta: 'success', 'error', 'warning', 'info'
 */
function showAlert(message, type = 'info') {
    const overlay = document.getElementById('alertOverlay');
    const icon = document.getElementById('alertIcon');
    const messageEl = document.getElementById('alertMessage');
    const closeBtn = document.getElementById('alertClose');
    
    // Iconos según tipo
    const icons = {
        success: '✓',
        error: '⚠',
        warning: '⚠',
        info: 'ℹ'
    };
    
    icon.textContent = icons[type] || icons.info;
    messageEl.textContent = message;
    
    overlay.classList.remove('hidden');
    
    // Cerrar al hacer clic
    closeBtn.onclick = () => {
        overlay.classList.add('hidden');
    };
    
    // Cerrar al hacer clic fuera del alert
    overlay.onclick = (e) => {
        if (e.target === overlay) {
            overlay.classList.add('hidden');
        }
    };
}

/**
 * Formatear tamaño de archivo
 * @param {number} bytes - Tamaño en bytes
 * @returns {string} - Tamaño formateado
 */
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

/**
 * Renderizar lista de archivos
 * @param {Array} files - Array de archivos
 * @param {Function} onRemove - Callback para eliminar archivo
 * @returns {string} - HTML de la lista
 */
function renderFilesList(files, onRemove) {
    return files.map((file, index) => `
        <div class="file-item">
            <div class="file-item-info">
                <div class="file-item-icon">📄</div>
                <div class="file-item-details">
                    <div class="file-item-name">${escapeHtml(file.name)}</div>
                    <div class="file-item-size">${formatFileSize(file.size)}</div>
                </div>
            </div>
            <button class="file-item-remove" data-index="${index}">
                Eliminar
            </button>
        </div>
    `).join('');
}

/**
 * Actualizar barra de progreso
 * @param {number} progress - Progreso (0-100)
 * @param {string} message - Mensaje de estado
 */
function updateProgress(progress, message = '') {
    const progressBar = document.getElementById('progressBar');
    const progressText = document.getElementById('progressText');
    
    if (progressBar) {
        progressBar.style.width = `${progress}%`;
    }
    
    if (progressText) {
        progressText.textContent = `${progress}% - ${message}`;
    }
}

/**
 * Renderizar resultados
 * @param {Object} data - Datos del resultado
 */
function renderResults(data) {
    // Actualizar estadísticas
    document.getElementById('totalFiles').textContent = data.total || 0;
    document.getElementById('successFiles').textContent = data.success || 0;
    document.getElementById('errorFiles').textContent = data.errors || 0;
    
    // Renderizar lista de resultados
    const resultsList = document.getElementById('resultsList');
    if (!resultsList) return;
    
    resultsList.innerHTML = data.results.map(result => `
        <div class="result-item">
            <div class="result-item-name">${escapeHtml(result.filename)}</div>
            <div class="result-item-status ${result.status === 'success' ? 'success' : 'error'}">
                ${result.status === 'success' 
                    ? `✓ ${result.records || 0} registros` 
                    : `✗ ${result.error || 'Error'}`
                }
            </div>
        </div>
    `).join('');
}

/**
 * Configurar drag and drop
 * @param {HTMLElement} dropZone - Zona de drop
 * @param {HTMLInputElement} fileInput - Input de archivos
 * @param {Function} onFilesSelected - Callback cuando se seleccionan archivos
 * @param {string} acceptedTypes - Tipos de archivo aceptados (opcional)
 */
function setupDragAndDrop(dropZone, fileInput, onFilesSelected, acceptedTypes = null) {
    // Click en drop zone abre selector
    dropZone.addEventListener('click', () => {
        fileInput.click();
    });
    
    // Drag over
    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('drag-over');
    });
    
    // Drag leave
    dropZone.addEventListener('dragleave', () => {
        dropZone.classList.remove('drag-over');
    });
    
    // Drop
    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('drag-over');
        
        let files = Array.from(e.dataTransfer.files);
        
        // Filtrar por tipo si se especifica
        if (acceptedTypes) {
            files = files.filter(file => {
                return acceptedTypes.split(',').some(type => {
                    type = type.trim();
                    if (type.startsWith('.')) {
                        return file.name.toLowerCase().endsWith(type);
                    }
                    return file.type === type;
                });
            });
        }
        
        if (files.length > 0) {
            onFilesSelected(files);
        } else {
            showAlert('Por favor seleccione archivos del tipo correcto', 'error');
        }
    });
    
    // Selección de archivos
    fileInput.addEventListener('change', (e) => {
        const files = Array.from(e.target.files);
        if (files.length > 0) {
            onFilesSelected(files);
        }
    });
}

/**
 * Escape HTML para prevenir XSS
 * @param {string} text - Texto a escapar
 * @returns {string} - Texto escapado
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Deshabilitar botón
 * @param {HTMLElement} button - Botón a deshabilitar
 * @param {string} text - Texto mientras está deshabilitado
 */
function disableButton(button, text = null) {
    if (!button) return;
    
    button.disabled = true;
    if (text) {
        button.setAttribute('data-original-text', button.textContent);
        button.textContent = text;
    }
}

/**
 * Habilitar botón
 * @param {HTMLElement} button - Botón a habilitar
 */
function enableButton(button) {
    if (!button) return;
    
    button.disabled = false;
    const originalText = button.getAttribute('data-original-text');
    if (originalText) {
        button.textContent = originalText;
        button.removeAttribute('data-original-text');
    }
}

/**
 * Validar archivos antes de subir
 * @param {Array} files - Archivos a validar
 * @param {Object} options - Opciones de validación
 * @returns {Object} - {valid: boolean, message: string}
 */
function validateFiles(files, options = {}) {
    const {
        maxFiles = 50,
        maxSize = 50 * 1024 * 1024, // 50MB por defecto
        allowedExtensions = []
    } = options;
    
    // Verificar cantidad
    if (files.length > maxFiles) {
        return {
            valid: false,
            message: `Máximo ${maxFiles} archivos permitidos`
        };
    }
    
    // Verificar tamaño y extensiones
    for (const file of files) {
        // Tamaño
        if (file.size > maxSize) {
            return {
                valid: false,
                message: `El archivo "${file.name}" excede el tamaño máximo permitido (${formatFileSize(maxSize)})`
            };
        }
        
        // Extensión
        if (allowedExtensions.length > 0) {
            const extension = '.' + file.name.split('.').pop().toLowerCase();
            if (!allowedExtensions.includes(extension)) {
                return {
                    valid: false,
                    message: `El archivo "${file.name}" no tiene una extensión permitida. Permitidas: ${allowedExtensions.join(', ')}`
                };
            }
        }
    }
    
    return { valid: true, message: '' };
}
