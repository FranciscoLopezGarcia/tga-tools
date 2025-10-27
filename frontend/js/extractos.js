/**
 * Extractos.js - Lógica para la herramienta de Extractos
 */

const TOOL_NAME = 'extractos';
let selectedFiles = [];
let currentJobId = null;
let stopPolling = null;

// Elementos del DOM
const dropZone = document.getElementById('dropZone');
const fileInput = document.getElementById('fileInput');
const filesList = document.getElementById('filesList');
const fileCount = document.getElementById('fileCount');
const processBtn = document.getElementById('processBtn');
const downloadBtn = document.getElementById('downloadBtn');
const downloadLogBtn = document.getElementById('downloadLogBtn');

// Inicializar
document.addEventListener('DOMContentLoaded', () => {
    setupDragAndDrop(dropZone, fileInput, handleFilesSelected, '.pdf');

    // Event listeners
    processBtn.addEventListener('click', handleProcess);
    downloadBtn.addEventListener('click', handleDownload);
    downloadLogBtn.addEventListener('click', handleDownloadLog);
});

/**
 * Manejar archivos seleccionados
 */
function handleFilesSelected(newFiles) {
    // Validar archivos
    const validation = validateFiles(newFiles, {
        maxFiles: 50,
        maxSize: 50 * 1024 * 1024, // 50MB
        allowedExtensions: ['.pdf']
    });

    if (!validation.valid) {
        showAlert(validation.message, 'error');
        return;
    }

    // Agregar archivos (evitar duplicados)
    newFiles.forEach(file => {
        const isDuplicate = selectedFiles.some(
            f => f.name === file.name && f.size === file.size
        );
        if (!isDuplicate) {
            selectedFiles.push(file);
        }
    });

    updateFilesList();
    updateUI();
}

/**
 * Actualizar lista de archivos en UI
 */
function updateFilesList() {
    if (selectedFiles.length === 0) {
        hideSection('filesSection');
        hideSection('actionSection');
        return;
    }

    showSection('filesSection');
    showSection('actionSection');

    fileCount.textContent = selectedFiles.length;
    filesList.innerHTML = renderFilesList(selectedFiles, removeFile);

    // Agregar event listeners a botones de eliminar
    document.querySelectorAll('.file-item-remove').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const index = parseInt(e.target.getAttribute('data-index'));
            removeFile(index);
        });
    });
}

/**
 * Eliminar archivo de la lista
 */
function removeFile(index) {
    selectedFiles.splice(index, 1);
    updateFilesList();
    updateUI();
}

/**
 * Actualizar UI según estado
 */
function updateUI() {
    processBtn.disabled = selectedFiles.length === 0;
}

/**
 * Procesar archivos
 */
async function handleProcess() {
    if (selectedFiles.length === 0) return;

    try {
        // Deshabilitar UI
        disableButton(processBtn, 'Iniciando...');
        hideSection('uploadSection');
        hideSection('filesSection');
        hideSection('actionSection');
        showSection('progressSection');
        updateProgress(0, 'Iniciando procesamiento...');

        // Subir archivos
        const response = await uploadFiles(TOOL_NAME, selectedFiles);
        currentJobId = response.job_id;

        // Iniciar polling
        stopPolling = startPolling(
            TOOL_NAME,
            currentJobId,
            handleProgress,
            handleComplete,
            handleError
        );

    } catch (error) {
        console.error('Error al procesar:', error);
        handleError(error);
    }
}

/**
 * Manejar progreso
 */
function handleProgress(status) {
    const progress = status.progress || 0;
    const message = status.message || 'Procesando...';
    updateProgress(progress, message);
}

/**
 * Manejar completado
 */
async function handleComplete(status) {
    updateProgress(100, 'Completado ✅');

    // Mostrar mensaje de éxito
    showAlert('¡Procesamiento completado exitosamente!', 'success');

    // Mostrar sección de resultados
    hideSection('progressSection');
    showSection('resultsSection');

    // Intentar descarga automática del ZIP
    try {
        const downloadUrl = `/api/${TOOL_NAME}/download/${currentJobId}`;
        console.log("📦 Descargando automáticamente desde:", downloadUrl);
        window.location.href = downloadUrl; // dispara la descarga directa
    } catch (error) {
        console.error('Error en descarga automática:', error);
        showAlert('Error al descargar el resultado automáticamente.', 'error');
    }
}

/**
 * Manejar error
 */
function handleError(error) {
    hideSection('progressSection');
    showSection('uploadSection');
    showSection('filesSection');
    showSection('actionSection');
    enableButton(processBtn);

    const msg = error?.message || 'Error desconocido en el procesamiento.';
    showAlert(`Error en el procesamiento: ${msg}`, 'error');
}

/**
 * Descargar resultado manualmente
 */
async function handleDownload() {
    if (!currentJobId) return;

    try {
        disableButton(downloadBtn, 'Descargando...');

        const blob = await downloadResult(TOOL_NAME, currentJobId);
        downloadBlob(blob, 'extractos_resultado.zip');

        enableButton(downloadBtn);
    } catch (error) {
        console.error('Error al descargar:', error);
        showAlert(`Error al descargar: ${error.message}`, 'error');
        enableButton(downloadBtn);
    }
}

/**
 * Descargar log
 */
async function handleDownloadLog() {
    if (!currentJobId) return;

    try {
        disableButton(downloadLogBtn, 'Descargando...');

        const blob = await downloadLog(TOOL_NAME, currentJobId);
        downloadBlob(blob, 'extractos_log.txt');

        enableButton(downloadLogBtn);
    } catch (error) {
        console.error('Error al descargar log:', error);
        showAlert(`Error al descargar log: ${error.message}`, 'error');
        enableButton(downloadLogBtn);
    }
}
