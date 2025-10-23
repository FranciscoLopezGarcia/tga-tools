// Dashboard principal

function openApp(appName) {
  const routes = {
    extractos: '/apps/extractos',
    siradig: '/apps/siradig',
    consolidado: '/apps/consolidado'
  };
  
  const route = routes[appName];
  if (route) {
    Utils.showToast(`Abriendo ${appName}...`, 'info');
    setTimeout(() => {
      window.location.href = route;
    }, 300);
  }
}

// Verificar estado de servicios
async function checkSystemStatus() {
  try {
    // Verificar cada servicio
    const services = ['extractos', 'siradig', 'consolidado'];
    
    for (const service of services) {
      try {
        await fetch(`/${service}/api/health`, { method: 'HEAD' });
      } catch (error) {
        console.warn(`Service ${service} not responding`);
      }
    }
  } catch (error) {
    console.error('Error checking system status:', error);
  }
}

// Atajos de teclado
document.addEventListener('keydown', (e) => {
  if (e.ctrlKey || e.metaKey) {
    switch(e.key) {
      case '1':
        e.preventDefault();
        openApp('extractos');
        break;
      case '2':
        e.preventDefault();
        openApp('siradig');
        break;
      case '3':
        e.preventDefault();
        openApp('consolidado');
        break;
    }
  }
});

// Inicialización
document.addEventListener('DOMContentLoaded', () => {
  checkSystemStatus();
  
  // Animar cards al cargar
  const cards = document.querySelectorAll('.tool-card');
  cards.forEach((card, index) => {
    card.style.opacity = '0';
    card.style.transform = 'translateY(20px)';
    
    setTimeout(() => {
      card.style.transition = 'all 0.5s ease-out';
      card.style.opacity = '1';
      card.style.transform = 'translateY(0)';
    }, index * 100);
  });
  
  Utils.showToast('Bienvenido a TGA-Tools', 'success');
});