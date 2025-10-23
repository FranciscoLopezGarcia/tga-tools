/**
 * Utilidades compartidas - TGA-Tools
 */

const Utils = {
  /**
   * Mostrar toast notification
   */
  showToast(message, type = 'info', duration = 3000) {
    const toast = document.getElementById('toast') || this.createToastElement();
    
    // Limpiar clases previas
    toast.className = 'toast';
    
    // Agregar clase de tipo
    const typeClass = `toast-${type}`;
    toast.classList.add(typeClass, 'show');
    
    // Agregar icono según tipo
    const icon = this.getToastIcon(type);
    toast.innerHTML = `${icon} <span>${message}</span>`;
    
    // Ocultar después del tiempo especificado
    setTimeout(() => {
      toast.classList.remove('show');
    }, duration);
  },

  /**
   * Crear elemento toast si no existe
   */
  createToastElement() {
    const toast = document.createElement('div');
    toast.id = 'toast';
    toast.className = 'toast';
    document.body.appendChild(toast);
    return toast;
  },

  /**
   * Obtener icono según tipo de toast
   */
  getToastIcon(type) {
    const icons = {
      success: '✓',
      error: '✕',
      warning: '⚠',
      info: 'ℹ'
    };
    return icons[type] || icons.info;
  },

  /**
   * Formatear bytes a tamaño legible
   */
  formatBytes(bytes, decimals = 2) {
    if (bytes === 0) return '0 Bytes';
    
    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    
    return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
  },

  /**
   * Validar archivo
   */
  validateFile(file, options = {}) {
    const {
      maxSize = 100 * 1024 * 1024, // 100MB por defecto
      allowedTypes = ['application/pdf'],
      allowedExtensions = ['.pdf']
    } = options;

    // Validar tamaño
    if (file.size > maxSize) {
      throw new Error(`Archivo muy grande. Máximo ${this.formatBytes(maxSize)}`);
    }

    // Validar tipo MIME
    if (allowedTypes.length && !allowedTypes.includes(file.type)) {
      throw new Error(`Tipo de archivo no permitido. Tipos aceptados: ${allowedTypes.join(', ')}`);
    }

    // Validar extensión
    if (allowedExtensions.length) {
      const extension = '.' + file.name.split('.').pop().toLowerCase();
      if (!allowedExtensions.includes(extension)) {
        throw new Error(`Extensión no permitida. Extensiones aceptadas: ${allowedExtensions.join(', ')}`);
      }
    }

    return true;
  },

  /**
   * Validar múltiples archivos
   */
  validateFiles(files, options = {}) {
    const results = {
      valid: [],
      invalid: []
    };

    Array.from(files).forEach(file => {
      try {
        this.validateFile(file, options);
        results.valid.push(file);
      } catch (error) {
        results.invalid.push({ file, error: error.message });
      }
    });

    return results;
  },

  /**
   * Descargar archivo blob
   */
  downloadBlob(blob, filename) {
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
  },

  /**
   * Copiar al portapapeles
   */
  async copyToClipboard(text) {
    try {
      await navigator.clipboard.writeText(text);
      this.showToast('Copiado al portapapeles', 'success');
      return true;
    } catch (err) {
      console.error('Error al copiar:', err);
      this.showToast('Error al copiar', 'error');
      return false;
    }
  },

  /**
   * Debounce function
   */
  debounce(func, wait = 300) {
    let timeout;
    return function executedFunction(...args) {
      const later = () => {
        clearTimeout(timeout);
        func(...args);
      };
      clearTimeout(timeout);
      timeout = setTimeout(later, wait);
    };
  },

  /**
   * Throttle function
   */
  throttle(func, limit = 300) {
    let inThrottle;
    return function(...args) {
      if (!inThrottle) {
        func.apply(this, args);
        inThrottle = true;
        setTimeout(() => inThrottle = false, limit);
      }
    };
  },

  /**
   * Formatear fecha
   */
  formatDate(date, format = 'DD/MM/YYYY HH:mm') {
    const d = new Date(date);
    
    const pad = (n) => n.toString().padStart(2, '0');
    
    const tokens = {
      'YYYY': d.getFullYear(),
      'MM': pad(d.getMonth() + 1),
      'DD': pad(d.getDate()),
      'HH': pad(d.getHours()),
      'mm': pad(d.getMinutes()),
      'ss': pad(d.getSeconds())
    };

    let result = format;
    Object.keys(tokens).forEach(token => {
      result = result.replace(token, tokens[token]);
    });

    return result;
  },

  /**
   * Generar ID único
   */
  generateId(prefix = '') {
    const timestamp = Date.now().toString(36);
    const random = Math.random().toString(36).substr(2, 5);
    return `${prefix}${timestamp}${random}`;
  },

  /**
   * Sanitizar string para usar como nombre de archivo
   */
  sanitizeFilename(filename) {
    return filename
      .replace(/[^a-z0-9_\-\.]/gi, '_')
      .replace(/_{2,}/g, '_')
      .toLowerCase();
  },

  /**
   * Obtener extensión de archivo
   */
  getFileExtension(filename) {
    return filename.slice((filename.lastIndexOf('.') - 1 >>> 0) + 2);
  },

  /**
   * Validar email
   */
  validateEmail(email) {
    const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return re.test(email);
  },

  /**
   * Mostrar/ocultar elemento
   */
  toggleElement(element, show) {
    if (typeof element === 'string') {
      element = document.querySelector(element);
    }
    
    if (!element) return;
    
    if (show === undefined) {
      element.classList.toggle('d-none');
    } else {
      element.classList.toggle('d-none', !show);
    }
  },

  /**
   * Mostrar spinner de carga
   */
  showSpinner(message = 'Cargando...') {
    let overlay = document.getElementById('spinner-overlay');
    
    if (!overlay) {
      overlay = document.createElement('div');
      overlay.id = 'spinner-overlay';
      overlay.className = 'spinner-overlay';
      overlay.innerHTML = `
        <div style="text-align: center;">
          <div class="spinner spinner-lg"></div>
          <p id="spinner-message" style="margin-top: 1rem; color: var(--gray-700);">${message}</p>
        </div>
      `;
      document.body.appendChild(overlay);
    } else {
      const messageEl = overlay.querySelector('#spinner-message');
      if (messageEl) messageEl.textContent = message;
      overlay.style.display = 'flex';
    }
  },

  /**
   * Ocultar spinner
   */
  hideSpinner() {
    const overlay = document.getElementById('spinner-overlay');
    if (overlay) {
      overlay.style.display = 'none';
    }
  },

  /**
   * Confirmar acción
   */
  async confirm(message, title = '¿Estás seguro?') {
    return new Promise((resolve) => {
      const modal = this.createConfirmModal(message, title, resolve);
      document.body.appendChild(modal);
      modal.classList.add('show');
    });
  },

  /**
   * Crear modal de confirmación
   */
  createConfirmModal(message, title, callback) {
    const modal = document.createElement('div');
    modal.className = 'modal';
    modal.innerHTML = `
      <div class="modal-content" style="max-width: 400px;">
        <div class="modal-header">
          <h3 class="modal-title">${title}</h3>
        </div>
        <div class="modal-body">
          <p>${message}</p>
        </div>
        <div class="modal-footer">
          <button class="btn btn-secondary" onclick="this.closest('.modal').remove(); (${callback})(false)">
            Cancelar
          </button>
          <button class="btn btn-danger" onclick="this.closest('.modal').remove(); (${callback})(true)">
            Confirmar
          </button>
        </div>
      </div>
    `;
    
    // Cerrar al hacer click fuera
    modal.addEventListener('click', (e) => {
      if (e.target === modal) {
        modal.remove();
        callback(false);
      }
    });
    
    return modal;
  },

  /**
   * Escapar HTML
   */
  escapeHtml(text) {
    const map = {
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '"': '&quot;',
      "'": '&#039;'
    };
    return text.replace(/[&<>"']/g, m => map[m]);
  },

  /**
   * Detectar dispositivo móvil
   */
  isMobile() {
    return /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
  },

  /**
   * Scroll smooth a elemento
   */
  scrollTo(element, offset = 0) {
    if (typeof element === 'string') {
      element = document.querySelector(element);
    }
    
    if (!element) return;
    
    const y = element.getBoundingClientRect().top + window.pageYOffset + offset;
    window.scrollTo({ top: y, behavior: 'smooth' });
  },

  /**
   * Local Storage helpers
   */
  storage: {
    set(key, value) {
      try {
        localStorage.setItem(key, JSON.stringify(value));
        return true;
      } catch (e) {
        console.error('Error saving to localStorage:', e);
        return false;
      }
    },
    
    get(key, defaultValue = null) {
      try {
        const item = localStorage.getItem(key);
        return item ? JSON.parse(item) : defaultValue;
      } catch (e) {
        console.error('Error reading from localStorage:', e);
        return defaultValue;
      }
    },
    
    remove(key) {
      try {
        localStorage.removeItem(key);
        return true;
      } catch (e) {
        console.error('Error removing from localStorage:', e);
        return false;
      }
    },
    
    clear() {
      try {
        localStorage.clear();
        return true;
      } catch (e) {
        console.error('Error clearing localStorage:', e);
        return false;
      }
    }
  }
};

// Exponer globalmente
window.Utils = Utils;

// Exportar para módulos
if (typeof module !== 'undefined' && module.exports) {
  module.exports = Utils;
}