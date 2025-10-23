/**
 * Siradig - App Logic
 */

class SiradigApp {
  constructor() {
    this.files = [];
    this.processing = false;
    this.results = null;
    this.zipFile = null;
    
    this.init();
  }

  init() {
    this.setupEventListeners();
    this.setupDragAndDrop();
  }

  setupEventListeners() {
    // File input
    const fileInput = document.getElementById('fileInput');
    fileInput?.addEventListener('change', (e) => this.handleFileSelect(e));

    // Botones principales
    document.getElementById('processBtn')?.addEventListener('click', () => this.processFiles());
    document.getElementById('clearAllBtn')?.addEventListener('click', () => this.clearAllFiles());
    document.getElementById('newProcessBtn')?.addEventListener('click', () => this.resetApp());
    document.getElementById('downloadAllBtn')?.addEventListener('click', () => this.downloadAll());
  }

  setupDragAndDrop() {
    const dropZone = document.getElementById('dropZone');
    
    if (!dropZone) return;

    // Prevenir comportamiento por defecto
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
      dropZone.addEventListener(eventName, (e) => {
        e.preventDefault();
        e.stopPropagation();
      });
    });

    // Highlight en drag
    ['dragenter', 'dragover'].forEach(eventName => {
      dropZone.addEventListener(eventName, () => {
        dropZone.classList.add('drag-over');
      });
    });

    ['dragleave', 'drop'].forEach(eventName => {
      dropZone.addEventListener(eventName, () => {
        dropZone.classList.remove('drag-over');
      });
    });

    // Handle drop
    dropZone.addEventListener('drop', (e) => {
      const files = e.dataTransfer.files;
      this.handleFiles(files);
    });

    // Click para seleccionar
    dropZone.addEventListener('click', () => {
      document.getElementById('fileInput')?.click();
    });
  }

  handleFileSelect(event) {
    const files = event.target.files;
    this.handleFiles(files);
  }

  handleFiles(files) {
    const validFiles = [];
    const invalidFiles = [];

    Array.from(files).forEach(file => {
      try {
        Utils.validateFile(file, {
          maxSize: 100 * 1024 * 1024, // 100MB
          allowedTypes: ['application/pdf'],
          allowedExtensions: ['.pdf']
        });
        validFiles.push(file);
      } catch (error) {
        invalidFiles.push({ file, error: error.message });
      }
    });

    // Agregar archivos válidos
    validFiles.forEach(file => {
      const fileObj = {
        id: Utils.generateId('file-'),
        file: file,
        name: file.name,
        size: file.size,
        status: 'pending'
      };
      this.files.push(fileObj);
    });

    // Mostrar errores de archivos inválidos
    if (invalidFiles.length > 0) {
      invalidFiles.forEach(({ file, error }) => {
        Utils.showToast(`${file.name}: ${error}`, 'error');
      });
    }

    // Mostrar éxito de archivos válidos
    if (validFiles.length > 0) {
      Utils.showToast(`${validFiles.length} archivo(s) agregado(s)`, 'success');
    }

    this.renderFiles();
  }

  renderFiles() {
    const filesList = document.getElementById('filesList');
    const filesSection = document.getElementById('filesSection');
    const filesCount = document.getElementById('filesCount');
    const processBtn = document.getElementById('processBtn');

    if (this.files.length === 0) {
      filesSection.style.display = 'none';
      return;
    }

    filesSection.style.display = 'block';
    filesCount.textContent = this.files.length;

    filesList.innerHTML = this.files.map(file => `
      <div class="file-item" data-file-id="${file.id}">
        <div class="file-icon">PDF</div>
        <div class="file-info">
          <div class="file-name">${Utils.escapeHtml(file.name)}</div>
          <div class="file-details">
            <span>${Utils.formatBytes(file.size)}</span>
            <span class="badge badge-secondary">${file.status === 'pending' ? 'Pendiente' : file.status}</span>
          </div>
        </div>
        <div class="file-actions">
          <button class="btn-icon-sm danger" onclick="siradigApp.removeFile('${file.id}')" title="Eliminar">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M18 6L6 18M6 6l12 12"/>
            </svg>
          </button>
        </div>
      </div>
    `).join('');

    // Habilitar botón de procesar
    processBtn.disabled = false;
  }

  removeFile(fileId) {
    this.files = this.files.filter(f => f.id !== fileId);
    this.renderFiles();
    Utils.showToast('Archivo eliminado', 'info');
  }

  clearAllFiles() {
    if (this.files.length === 0) return;

    Utils.confirm('¿Eliminar todos los archivos?', 'Confirmar').then(confirmed => {
      if (confirmed) {
        this.files = [];
        this.renderFiles();
        Utils.showToast('Todos los archivos eliminados', 'info');
      }
    });
  }

  async processFiles() {
    if (this.files.length === 0) {
      Utils.showToast('No hay archivos para procesar', 'warning');
      return;
    }

    if (this.processing) {
      Utils.showToast('Ya hay un proceso en curso', 'warning');
      return;
    }

    this.processing = true;
    this.showProcessingSection();

    try {
      // Crear FormData con los archivos
      const formData = new FormData();
      this.files.forEach(fileObj => {
        formData.append('files[]', fileObj.file);
      });

      // Enviar a procesar
      Utils.showSpinner('Procesando archivos...');
      
      const response = await API.siradig.upload('/upload', formData, (progress) => {
        const details = document.getElementById('processingDetails');
        if (details) {
          details.textContent = `Progreso: ${Math.round(progress)}%`;
        }
      });

      Utils.hideSpinner();

      if (response.success) {
        this.handleProcessingComplete(response);
      } else {
        throw new Error(response.error || 'Error al procesar archivos');
      }

    } catch (error) {
      console.error('Error processing files:', error);
      Utils.hideSpinner();
      Utils.showToast(`Error: ${error.message}`, 'error');
      this.processing = false;
      
      // Volver a mostrar archivos
      document.getElementById('processingSection').style.display = 'none';
      document.getElementById('filesSection').style.display = 'block';
    }
  }

  showProcessingSection() {
    // Ocultar sección de archivos
    document.getElementById('filesSection').style.display = 'none';
    
    // Mostrar sección de procesamiento
    const processingSection = document.getElementById('processingSection');
    processingSection.style.display = 'block';
  }

  handleProcessingComplete(response) {
    this.results = response;
    this.zipFile = response.zip_file;
    
    Utils.showToast('Procesamiento completado', 'success');
    
    // Ocultar procesamiento
    document.getElementById('processingSection').style.display = 'none';
    
    // Mostrar resultados
    this.showResults();
    
    this.processing = false;
  }

  showResults() {
    const resultsSection = document.getElementById('resultsSection');
    const resultsList = document.getElementById('resultsList');
    const resultsSummary = document.getElementById('resultsSummary');
    
    resultsSection.style.display = 'block';

    // Calcular estadísticas
    const total = this.results.total_archivos || 0;
    const success = this.results.resultados?.filter(r => r.estado === 'OK').length || 0;
    const errors = this.results.resultados?.filter(r => r.estado !== 'OK').length || 0;
    const totalRecords = this.results.total_registros || 0;

    // Actualizar resumen
    resultsSummary.textContent = `Se procesaron ${total} archivo(s) con ${totalRecords} registros totales`;

    // Actualizar stats
    document.getElementById('successCount').textContent = success;
    document.getElementById('errorCount').textContent = errors;
    document.getElementById('totalRecords').textContent = totalRecords;

    // Renderizar lista de resultados
    resultsList.innerHTML = this.results.resultados?.map(result => {
      const isSuccess = result.estado === 'OK';
      const isWarning = result.estado === 'SIN DATOS';
      const iconSymbol = isSuccess ? '✓' : (isWarning ? '!' : '✕');
      const statusClass = isSuccess ? 'success' : (isWarning ? 'warning' : 'error');
      
      return `
        <div class="result-item ${statusClass}">
          <div class="result-icon">${iconSymbol}</div>
          <div class="result-info">
            <div class="result-name">${Utils.escapeHtml(result.archivo)}</div>
            <div class="result-details">
              ${isSuccess 
                ? `${result.registros} registros extraídos` 
                : (isWarning ? 'Sin datos extraídos' : `Error: ${result.estado}`)
              }
            </div>
          </div>
        </div>
      `;
    }).join('') || '<p class="text-center text-muted">No hay resultados para mostrar</p>';
  }

  async downloadAll() {
    if (!this.zipFile) {
      Utils.showToast('No hay archivos para descargar', 'warning');
      return;
    }

    try {
      await API.siradig.download(`/download/${this.zipFile}`, this.zipFile);
      Utils.showToast('Descarga iniciada', 'success');
    } catch (error) {
      console.error('Error downloading ZIP:', error);
      Utils.showToast('Error al descargar ZIP', 'error');
    }
  }

  resetApp() {
    this.files = [];
    this.processing = false;
    this.results = null;
    this.zipFile = null;

    // Ocultar secciones
    document.getElementById('filesSection').style.display = 'none';
    document.getElementById('processingSection').style.display = 'none';
    document.getElementById('resultsSection').style.display = 'none';

    // Limpiar input
    const fileInput = document.getElementById('fileInput');
    if (fileInput) fileInput.value = '';

    Utils.showToast('Listo para procesar nuevos archivos', 'info');
  }
}

// Inicializar app
let siradigApp;
document.addEventListener('DOMContentLoaded', () => {
  siradigApp = new SiradigApp();
});