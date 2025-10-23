/**
 * Cliente API Unificado - TGA-Tools
 * Maneja todas las peticiones HTTP a los diferentes backends
 */

class APIClient {
  constructor(baseURL = '') {
    this.baseURL = baseURL;
    this.token = this.getStoredToken();
  }

  /**
   * Obtener token almacenado
   */
  getStoredToken() {
    return localStorage.getItem('tga_token');
  }

  /**
   * Guardar token
   */
  setToken(token) {
    this.token = token;
    localStorage.setItem('tga_token', token);
  }

  /**
   * Obtener token actual
   */
  getToken() {
    return this.token || this.getStoredToken();
  }

  /**
   * Limpiar token
   */
  clearToken() {
    this.token = null;
    localStorage.removeItem('tga_token');
  }

  /**
   * Petición HTTP genérica
   */
  async request(endpoint, options = {}) {
    const url = `${this.baseURL}${endpoint}`;
    
    const headers = {
      ...options.headers,
    };

    // Agregar token si existe y no se especifica skipAuth
    if (this.token && !options.skipAuth) {
      headers['Authorization'] = `Bearer ${this.token}`;
    }

    // Si no es FormData, agregar Content-Type JSON
    if (!(options.body instanceof FormData)) {
      headers['Content-Type'] = 'application/json';
    }

    const config = {
      ...options,
      headers,
    };

    // Serializar body si no es FormData
    if (options.body && !(options.body instanceof FormData)) {
      config.body = JSON.stringify(options.body);
    }

    try {
      const response = await fetch(url, config);
      
      // Manejar 401 (no autorizado)
      if (response.status === 401) {
        this.clearToken();
        window.location.href = '/';
        throw new Error('No autorizado');
      }

      // Intentar parsear como JSON
      let data;
      const contentType = response.headers.get('content-type');
      
      if (contentType && contentType.includes('application/json')) {
        data = await response.json();
      } else {
        data = await response.text();
      }
      
      // Si la respuesta no es ok, lanzar error
      if (!response.ok) {
        const errorMsg = typeof data === 'object' ? (data.error || data.message) : data;
        throw new Error(errorMsg || `Error ${response.status}`);
      }

      return data;
      
    } catch (error) {
      console.error('API Error:', error);
      throw error;
    }
  }

  /**
   * GET request
   */
  get(endpoint, options = {}) {
    return this.request(endpoint, { ...options, method: 'GET' });
  }

  /**
   * POST request
   */
  post(endpoint, body, options = {}) {
    return this.request(endpoint, { ...options, method: 'POST', body });
  }

  /**
   * PUT request
   */
  put(endpoint, body, options = {}) {
    return this.request(endpoint, { ...options, method: 'PUT', body });
  }

  /**
   * DELETE request
   */
  delete(endpoint, options = {}) {
    return this.request(endpoint, { ...options, method: 'DELETE' });
  }

  /**
   * PATCH request
   */
  patch(endpoint, body, options = {}) {
    return this.request(endpoint, { ...options, method: 'PATCH', body });
  }

  /**
   * Upload con progreso
   */
  async upload(endpoint, formData, onProgress) {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      
      // Evento de progreso
      if (onProgress) {
        xhr.upload.addEventListener('progress', (e) => {
          if (e.lengthComputable) {
            const progress = (e.loaded / e.total) * 100;
            onProgress(progress);
          }
        });
      }

      // Evento de carga completada
      xhr.addEventListener('load', () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          try {
            const data = JSON.parse(xhr.responseText);
            resolve(data);
          } catch (e) {
            resolve(xhr.responseText);
          }
        } else {
          try {
            const error = JSON.parse(xhr.responseText);
            reject(new Error(error.error || error.message || xhr.statusText));
          } catch (e) {
            reject(new Error(xhr.statusText));
          }
        }
      });

      // Evento de error
      xhr.addEventListener('error', () => {
        reject(new Error('Error de red'));
      });

      // Evento de timeout
      xhr.addEventListener('timeout', () => {
        reject(new Error('Tiempo de espera agotado'));
      });

      // Configurar y enviar
      xhr.open('POST', `${this.baseURL}${endpoint}`);
      
      if (this.token) {
        xhr.setRequestHeader('Authorization', `Bearer ${this.token}`);
      }

      xhr.send(formData);
    });
  }

  /**
   * Descargar archivo
   */
  async download(endpoint, filename) {
    try {
      const response = await fetch(`${this.baseURL}${endpoint}`, {
        headers: this.token ? { 'Authorization': `Bearer ${this.token}` } : {}
      });

      if (!response.ok) {
        throw new Error('Error al descargar archivo');
      }

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename || 'download';
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);

      return true;
    } catch (error) {
      console.error('Download error:', error);
      throw error;
    }
  }

  /**
   * Health check
   */
  async health() {
    try {
      await fetch(`${this.baseURL}/health`, { method: 'HEAD' });
      return true;
    } catch {
      return false;
    }
  }
}

// Crear instancias por servicio
window.API = {
  auth: new APIClient('/api'),
  extractos: new APIClient('/extractos/api'),
  siradig: new APIClient('/siradig/api'),
  consolidado: new APIClient('/consolidado/api'),
};

// Exportar para módulos
if (typeof module !== 'undefined' && module.exports) {
  module.exports = APIClient;
}