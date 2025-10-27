/**
 * Main.js - Lógica para la página principal
 */

document.addEventListener('DOMContentLoaded', () => {
    // Agregar efecto hover a las cards (opcional, ya está en CSS)
    const toolCards = document.querySelectorAll('.tool-card');
    
    toolCards.forEach(card => {
        card.addEventListener('mouseenter', () => {
            // Efecto adicional si se desea
        });
    });
});
