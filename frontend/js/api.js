/**
 * API.js - Módulo de conexión con el backend
 * Centraliza todas las peticiones HTTP a los diferentes endpoints
 */

const API_BASE_URL = '/api'; // Ajustar según tu backend

/**
 * Configuración de endpoints por herramienta
 */
const ENDPOINTS = {
    extractos: {
        upload: `${API_BASE_URL}/extractos/upload`,
        status: (jobId) => `${API_BASE_URL}/extractos/status/${jobId}`,
        download: (jobId) => `${API_BASE_URL}/extractos/download/${jobId}`,
        downloadLog: (jobId) => `${API_BASE_URL}/extractos/log/${jobId}`
    },
    siradig: {
        upload: `${API_BASE_URL}/siradig/upload`,
        status: (jobId) => `${API_BASE_URL}/siradig/status/${jobId}`,
        download: (jobId) => `${API_BASE_URL}/siradig/download/${jobId}`,
        downloadLog: (jobId) => `${API_BASE_URL}/siradig/log/${jobId}`
    },
    consolidador: {
        upload: `${API_BASE_URL}/consolidador/upload`,
        status: (jobId) => `${API_BASE_URL}/consolidador/status/${jobId}`,
        download: (jobId) => `${API_BASE_URL}/consolidador/download/${jobId}`,
        downloadLog: (jobId) => `${API_BASE_URL}/consolidador/log/${jobId}`
    }
};

/**
 * Subir archivos y obtener job ID
 * @param {string} tool - Nombre de la herramienta (extractos, siradig, consolidador)
 * @param {FileList|Array} files - Archivos a subir
 * @returns {Promise<{job_id: string}>}
 */
async function uploadFiles(tool, files) {
    const formData = new FormData();
    
    // Agregar archivos al FormData
    Array.from(files).forEach(file => {
        formData.append('files', file);
    });
    
    try {
        const response = await fetch(ENDPOINTS[tool].upload, {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.message || `Error HTTP ${response.status}`);
        }
        
        return await response.json();
    } catch (error) {
        console.error('Error en uploadFiles:', error);
        throw error;
    }
}

/**
 * Consultar estado del procesamiento
 * @param {string} tool - Nombre de la herramienta
 * @param {string} jobId - ID del job
 * @returns {Promise<{state: string, progress: number, status: string}>}
 */
async function checkStatus(tool, jobId) {
    try {
        const response = await fetch(ENDPOINTS[tool].status(jobId), {
            method: 'GET'
        });
        
        if (!response.ok) {
            throw new Error(`Error HTTP ${response.status}`);
        }
        
        return await response.json();
    } catch (error) {
        console.error('Error en checkStatus:', error);
        throw error;
    }
}

/**
 * Descargar resultado (ZIP o Excel)
 * @param {string} tool - Nombre de la herramienta
 * @param {string} jobId - ID del job
 * @returns {Promise<Blob>}
 */
async function downloadResult(tool, jobId) {
    try {
        const response = await fetch(ENDPOINTS[tool].download(jobId), {
            method: 'GET'
        });
        
        if (!response.ok) {
            throw new Error(`Error HTTP ${response.status}`);
        }
        
        return await response.blob();
    } catch (error) {
        console.error('Error en downloadResult:', error);
        throw error;
    }
}

/**
 * Descargar log completo
 * @param {string} tool - Nombre de la herramienta
 * @param {string} jobId - ID del job
 * @returns {Promise<Blob>}
 */
async function downloadLog(tool, jobId) {
    try {
        const response = await fetch(ENDPOINTS[tool].downloadLog(jobId), {
            method: 'GET'
        });
        
        if (!response.ok) {
            throw new Error(`Error HTTP ${response.status}`);
        }
        
        return await response.blob();
    } catch (error) {
        console.error('Error en downloadLog:', error);
        throw error;
    }
}

/**
 * Iniciar polling para monitorear progreso
 * @param {string} tool - Nombre de la herramienta
 * @param {string} jobId - ID del job
 * @param {Function} onProgress - Callback para actualizar progreso
 * @param {Function} onComplete - Callback cuando se completa
 * @param {Function} onError - Callback en caso de error
 * @returns {Function} Función para detener el polling
 */
function startPolling(tool, jobId, onProgress, onComplete, onError) {
    let pollingInterval;
    
    const poll = async () => {
        try {
            const status = await checkStatus(tool, jobId);
            
            // Actualizar progreso
            if (status.state === 'PROGRESS' || status.state === 'PENDING') {
                onProgress(status);
            }
            // Completado exitosamente
            else if (status.state === 'SUCCESS') {
                clearInterval(pollingInterval);
                onComplete(status);
            }
            // Error en el procesamiento
            else if (status.state === 'FAILURE') {
                clearInterval(pollingInterval);
                onError(new Error(status.status || 'Error en el procesamiento'));
            }
        } catch (error) {
            clearInterval(pollingInterval);
            onError(error);
        }
    };
    
    // Iniciar polling cada 2 segundos
    pollingInterval = setInterval(poll, 2000);
    
    // Ejecutar primera vez inmediatamente
    poll();
    
    // Retornar función para detener polling
    return () => clearInterval(pollingInterval);
}

/**
 * Descargar archivo blob
 * @param {Blob} blob - Blob a descargar
 * @param {string} filename - Nombre del archivo
 */
function downloadBlob(blob, filename) {
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
}
