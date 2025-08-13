/* ----------------------------------------------------
   Funciones base del sitio
   - Scroll suave para enlaces internos (#anclas)
   - Aviso “Próximas actualizaciones” si el ancla no existe
   - Año del footer actualizado automáticamente
   - Envío del formulario de contacto (validación mínima + simulación)
-----------------------------------------------------*/
(() => {
  'use strict';

  // ---------- Scroll suave + aviso si falta la sección ----------
  document.addEventListener('click', (e) => {
    const link = e.target.closest('a[href^="#"]');
    if (!link) return;

    const href = link.getAttribute('href');
    if (!href || href === '#') return; // Enlaces vacíos: no hacemos nada

    const id = href.slice(1);
    const target = document.getElementById(id);

    e.preventDefault();

    if (target) {
      const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      target.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'start' });
    } else {
      notify('Disponible en futuras actualizaciones');
    }
  });

  // ---------- Actualiza el año del footer ----------
  (function updateFooterYear() {
    const p = document.querySelector('footer p');
    if (!p) return;
    p.innerHTML = p.innerHTML.replace(/\b\d{4}\b/, String(new Date().getFullYear()));
  })();

  // ---------- Toast minimalista para avisos ----------
  let toastTimeout;
  function notify(message) {
    injectToastStyles();

    let toast = document.querySelector('.toast-min');
    if (!toast) {
      toast = document.createElement('div');
      toast.className = 'toast-min';
      document.body.appendChild(toast);
    }

    toast.textContent = message;

    // Reinicia animación si ya estaba visible
    toast.classList.remove('show');
    // Forzar reflow para reiniciar transición
    void toast.offsetWidth;
    toast.classList.add('show');

    clearTimeout(toastTimeout);
    toastTimeout = setTimeout(() => {
      toast.classList.remove('show');
    }, 1800);
  }

  function injectToastStyles() {
    if (document.getElementById('toast-min-styles')) return;
    const style = document.createElement('style');
    style.id = 'toast-min-styles';
    style.textContent = `
      .toast-min {
        position: fixed;
        left: 50%;
        bottom: 24px;
        transform: translateX(-50%);
        padding: 12px 16px;
        background: #333;
        color: #fff;
        border-radius: 10px;
        box-shadow: 0 8px 24px rgba(0,0,0,.18);
        font-weight: 600;
        letter-spacing: .2px;
        opacity: 0;
        pointer-events: none;
        transition: opacity .25s ease;
        z-index: 9999;
      }
      .toast-min.show { opacity: 1; }
    `;
    document.head.appendChild(style);
  }

  // ---------- Envío del formulario de contacto (simulado) ----------
  (function handleContactForm(){
    const form = document.getElementById('contact-form');
    if (!form) return;

    form.addEventListener('submit', (e) => {
      e.preventDefault();

      const email = form.email?.value.trim();
      const servicio = form.servicio?.value;
      const canal = form.canal?.value;
      const mensaje = form.mensaje?.value.trim();
      const consent = document.getElementById('consent')?.checked;

      // Validación mínima
      if (!email || !servicio || !canal || !mensaje || !consent) {
        notify('Completá los campos obligatorios');
        return;
      }

      // Simulación de envío (a integrar con bot de Telegram)
      const payload = {
        nombre: form.nombre?.value.trim() || '',
        email, servicio, canal, mensaje, consent
      };
      console.log('Formulario listo para enviar:', payload);

      notify('Formulario enviado. Te contactaremos pronto.');
      form.reset();
    });
  })();

})();
