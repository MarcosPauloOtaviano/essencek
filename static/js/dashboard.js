// Jane Miranda — Dashboard JS

document.addEventListener('DOMContentLoaded', () => {
  // Sidebar toggle (mobile)
  const toggle = document.getElementById('sidebarToggle');
  const sidebar = document.getElementById('dashSidebar');
  const overlay = document.getElementById('dashSidebarOverlay');

  function setSidebar(open) {
    sidebar?.classList.toggle('open', open);
    overlay?.classList.toggle('open', open);
    document.body.classList.toggle('dashboard-menu-open', open);
    toggle?.setAttribute('aria-expanded', open ? 'true' : 'false');
    if (overlay) overlay.hidden = !open;
  }

  toggle?.addEventListener('click', () => setSidebar(!sidebar?.classList.contains('open')));
  overlay?.addEventListener('click', () => setSidebar(false));

  // Close sidebar when clicking outside on mobile
  document.addEventListener('click', e => {
    if (window.innerWidth <= 768 && sidebar?.classList.contains('open')) {
      if (!sidebar.contains(e.target) && !toggle?.contains(e.target)) {
        setSidebar(false);
      }
    }
  });

  sidebar?.querySelectorAll('a').forEach(link => {
    link.addEventListener('click', () => {
      if (window.innerWidth <= 768) setSidebar(false);
    });
  });

  // Auto-dismiss alerts after 5 seconds
  document.querySelectorAll('.dash-alert').forEach(alert => {
    setTimeout(() => {
      alert.style.opacity = '0';
      alert.style.transition = 'opacity 0.4s';
      setTimeout(() => alert.remove(), 400);
    }, 5000);
  });

  // Confirm dangerous actions
  document.querySelectorAll('[data-confirm]').forEach(el => {
    el.addEventListener('click', e => {
      if (!confirm(el.dataset.confirm)) e.preventDefault();
    });
  });
});
