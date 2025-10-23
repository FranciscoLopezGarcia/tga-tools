/**
 * Extractos Bancarios - App Logic
 */

class ExtractosApp {
  constructor() {
    this.files = [];
    this.processing = false;
    this.results = [];
    this.taskId = null;
    
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
          <button class="btn-icon-sm danger" onclick="extractosApp.removeFile('${file.id}')" title="Eliminar">
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
      Utils.showSpinner('Subiendo archivos...');
      
      const response = await API.extractos.upload('/upload', formData, (progress) => {
        Utils.showSpinner(`Subiendo archivos... ${Math.round(progress)}%`);
      });

      Utils.hideSpinner();

      if (response.success) {
        this.taskId = response.task_id || response.zip_file;
        
        // Si hay task_id, es async (Celery)
        if (response.task_id) {
          this.pollTaskStatus(response.task_id);
        } else {
          // Procesamiento síncrono completado
          this.handleProcessingComplete(response);
        }
      } else {
        throw new Error(response.error || 'Error al procesar archivos');
      }

    } catch (error) {
      console.error('Error processing files:', error);
      Utils.hideSpinner();
      Utils.showToast(`Error: ${error.message}`, 'error');
      this.processing = false;
    }
  }

  showProcessingSection() {
    // Ocultar sección de archivos
    document.getElementById('filesSection').style.display = 'none';
    
    // Mostrar sección de procesamiento
    const processingSection = document.getElementById('processingSection');
    processingSection.style.display = 'block';

    // Renderizar archivos en procesamiento
    const processingList = document.getElementById('processingList');
    processingList.innerHTML = this.files.map(file => `
      <div class="processing-item" data-file-id="${file.id}">
        <div class="processing-header">
          <span class="processing-file-name">${Utils.escapeHtml(file.name)}</span>
          <span class="processing-status">
            <div class="processing-spinner"></div>
            <span>Procesando...</span>
          </span>
        </div>
        <div class="progress processing-progress">
          <div class="progress-bar progress-bar-striped" style="width: 0%"></div>
        </div>
        <div class="processing-message">Esperando...</div>
      </div>
    `).join('');

    // Actualizar resumen
    document.getElementById('totalFiles').textContent = this.files.length;
    document.getElementById('completedFiles').textContent = '0';
    document.getElementById('errorFiles').textContent = '0';
  }

  async pollTaskStatus(taskId) {
    const pollInterval = 2000; // 2 segundos
    
    const poll = async () => {
      try {
        const status = await API.extractos.get(`/status/${taskId}`);
        
        this.updateProcessingStatus(status);

        if (status.state === 'SUCCESS') {
          this.handleProcessingComplete(status.result);
          this.processing = false;
        } else if (status.state === 'FAILURE') {
          throw new Error(status.error || 'Error en el procesamiento');
        } else {
          // Continuar polling
          setTimeout(poll, pollInterval);
        }

      } catch (error) {
        console.error('Error polling status:', error);
        Utils.showToast(`Error: ${error.message}`, 'error');
        this.processing = false;
      }
    };

    poll();
  }

  updateProcessingStatus(status) {
    // Actualizar progreso de cada archivo
    if (status.current && status.total) {
      const progress = (status.current / status.total) * 100;
      
      const progressBars = document.querySelectorAll('.processing-progress .progress-bar');
      progressBars.forEach(bar => {
        bar.style.width = `${progress}%`;
      });
      
      document.getElementById('completedFiles').textContent = status.current;
    }

    // Actualizar mensaje
    if (status.status) {
      const messages = document.querySelectorAll('.processing-message');
      messages.forEach(msg => {
        msg.textContent = status.status;
      });
    }
  }

  handleProcessingComplete(result) {
    this.results = result.resultados || [];
    this.zipFile = result.zip_file;
    
    Utils.showToast('Procesamiento completado', 'success');
    
    // Ocultar procesamiento
    document.getElementById('processingSection').style.display = 'none';
    
    // Mostrar resultados
    this.showResults();
  }

  showResults() {
    const resultsSection = document.getElementById('resultsSection');
    const resultsList = document.getElementById('resultsList');
    
    resultsSection.style.display = 'block';

    resultsList.innerHTML = this.results.map(result => {
      const isSuccess = result.estado === 'OK';
      const iconSymbol = isSuccess ? '✓' : '✕';
      const statusClass = isSuccess ? 'success' : 'error';
      
      return `
        <div class="result-item ${statusClass}">
          <div class="result-icon">${iconSymbol}</div>
          <div class="result-info">
            <div class="result-name">${Utils.escapeHtml(result.archivo)}</div>
            <div class="result-details">
              ${isSuccess 
                ? `${result.registros} registros extraídos` 
                : `Error: ${result.estado}`
              }
            </div>
          </div>
          ${isSuccess ? `
            <div class="result-actions">
              <button class="btn btn-sm btn-primary" onclick="extractosApp.downloadFile('${result.archivo}')">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3"/>
                </svg>
                Descargar
              </button>
            </div>
          ` : ''}
        </div>
      `;
    }).join('');
  }

  async downloadFile(filename) {
    try {
      const xlsxFilename = filename.replace('.pdf', '.xlsx');
      await API.extractos.download(`/download/${xlsxFilename}`, xlsxFilename);
      Utils.showToast('Descarga iniciada', 'success');
    } catch (error) {
      console.error('Error downloading file:', error);
      Utils.showToast('Error al descargar archivo', 'error');
    }
  }

  async downloadAll() {
    if (!this.zipFile) {
      Utils.showToast('No hay archivos para descargar', 'warning');
      return;
    }

    try {
      await API.extractos.download(`/download/${this.zipFile}`, this.zipFile);
      Utils.showToast('Descarga iniciada', 'success');
    } catch (error) {
      console.error('Error downloading ZIP:', error);
      Utils.showToast('Error al descargar ZIP', 'error');
    }
  }

  resetApp() {
    this.files = [];
    this.processing = false;
    this.results = [];
    this.taskId = null;
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
let extractosApp;
document.addEventListener('DOMContentLoaded', () => {
  extractosApp = new ExtractosApp();
});