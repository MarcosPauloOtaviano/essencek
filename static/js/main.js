// Jane Miranda — Main JS

function updateCartBadge(count) {
  const normalizedCount = Math.max(0, Number(count) || 0);
  const cartBtn = document.querySelector('.cart-btn[href*="carrinho"]');
  if (!cartBtn) return;

  let badge = cartBtn.querySelector('.cart-badge');
  if (normalizedCount === 0) {
    badge?.remove();
  } else {
    if (!badge) {
      badge = document.createElement('span');
      badge.className = 'cart-badge';
      cartBtn.appendChild(badge);
    }
    badge.textContent = normalizedCount;
  }

  const itemLabel = normalizedCount === 1 ? 'item' : 'itens';
  cartBtn.setAttribute(
    'aria-label',
    normalizedCount ? `Abrir carrinho, ${normalizedCount} ${itemLabel}` : 'Abrir carrinho'
  );
}

document.addEventListener('DOMContentLoaded', () => {
  // Mobile nav toggle
  const toggle = document.getElementById('navToggle');
  const navList = document.getElementById('navList');
  toggle?.addEventListener('click', () => {
    navList.classList.toggle('open');
    toggle.setAttribute('aria-expanded', navList.classList.contains('open') ? 'true' : 'false');
  });
  navList?.querySelectorAll('a').forEach(link => {
    link.addEventListener('click', () => {
      if (window.innerWidth <= 768) {
        navList.classList.remove('open');
        toggle?.setAttribute('aria-expanded', 'false');
      }
    });
  });

  const socialFloat = document.querySelector('.social-float');
  const quickNav = document.querySelector('.quick-nav-section');
  if (socialFloat && quickNav && 'IntersectionObserver' in window) {
    const quickNavObserver = new IntersectionObserver(entries => {
      const quickNavIsVisible = entries.some(entry => entry.isIntersecting);
      socialFloat.classList.toggle(
        'social-float--away-from-quick-nav',
        quickNavIsVisible && window.matchMedia('(max-width: 768px)').matches
      );
    }, { threshold: 0.1 });
    quickNavObserver.observe(quickNav);
  }

  // Showcase banner carousel
  const slides = document.querySelectorAll('.showcase-slide');
  const dots = document.querySelectorAll('.showcase-dot');
  if (slides.length > 1) {
    let cur = 0;
    const goTo = (i) => {
      slides[cur].classList.remove('showcase-slide--active');
      dots[cur]?.classList.remove('showcase-dot--active');
      cur = i;
      slides[cur].classList.add('showcase-slide--active');
      dots[cur]?.classList.add('showcase-dot--active');
    };
    let timer = setInterval(() => goTo((cur + 1) % slides.length), 4000);
    dots.forEach(d => d.addEventListener('click', () => {
      clearInterval(timer);
      goTo(Number(d.dataset.slide));
      timer = setInterval(() => goTo((cur + 1) % slides.length), 4000);
    }));
  }

  const setAddControlBusy = (control, busy, originalText) => {
    if ('disabled' in control) control.disabled = busy;
    control.setAttribute('aria-disabled', busy ? 'true' : 'false');
    control.classList.toggle('is-busy', busy);
    control.innerHTML = busy ? '<i class="fas fa-spinner fa-spin"></i>' : originalText;
  };

  const showAddSuccess = (control, originalText, data) => {
    updateCartBadge(data.cart_count);
    control.innerHTML = '<i class="fas fa-check"></i> Adicionado!';
    control.classList.add('btn-success-flash');
    setTimeout(() => {
      setAddControlBusy(control, false, originalText);
      control.classList.remove('btn-success-flash');
    }, 1800);
    showToast(data.message || 'Produto adicionado ao carrinho!', 'success');
  };

  const readJsonResponse = async (response) => {
    const contentType = response.headers.get('content-type') || '';
    if (!contentType.includes('application/json')) {
      throw new Error('Resposta inesperada do servidor.');
    }
    return response.json();
  };

  // Product pages keep their regular POST forms as a non-JavaScript fallback.
  document.querySelectorAll('form.add-to-cart-form').forEach(form => {
    form.addEventListener('submit', async e => {
      e.preventDefault();
      const btn = form.querySelector('button[type="submit"]');
      const originalText = btn.innerHTML;
      setAddControlBusy(btn, true, originalText);
      try {
        const fd = new FormData(form);
        const res = await fetch(form.action, {
          method: 'POST', body: fd,
          headers: { 'X-Requested-With': 'XMLHttpRequest' }
        });
        const data = await readJsonResponse(res);
        if (res.ok && data.success) {
          showAddSuccess(btn, originalText, data);
        } else {
          setAddControlBusy(btn, false, originalText);
          showToast(data.error || 'Erro ao adicionar.', 'error');
        }
      } catch {
        setAddControlBusy(btn, false, originalText);
        showToast('Não foi possível adicionar o produto. Tente novamente.', 'error');
      }
    });
  });

  // Catalog cards request CSRF only when quick-add is used, keeping public HTML cacheable.
  let csrfTokenPromise;
  const getCartCsrfToken = async () => {
    if (!csrfTokenPromise) {
      const csrfUrl = document.body.dataset.cartCsrfUrl;
      csrfTokenPromise = fetch(csrfUrl, {
        credentials: 'same-origin',
        headers: { 'Accept': 'application/json' }
      }).then(async response => {
        const data = await readJsonResponse(response);
        if (!response.ok || !data.csrf_token) throw new Error('Token CSRF indisponível.');
        return data.csrf_token;
      }).catch(error => {
        csrfTokenPromise = null;
        throw error;
      });
    }
    return csrfTokenPromise;
  };

  const warmCartCsrfToken = () => {
    if (!document.querySelector('.quick-add-cart')) return;
    getCartCsrfToken().catch(() => {});
  };

  if ('requestIdleCallback' in window) {
    window.requestIdleCallback(warmCartCsrfToken, { timeout: 1200 });
  } else {
    window.setTimeout(warmCartCsrfToken, 250);
  }

  document.querySelectorAll('.quick-add-cart').forEach(link => {
    link.addEventListener('click', async event => {
      event.preventDefault();
      if (link.getAttribute('aria-disabled') === 'true') return;
      const originalText = link.innerHTML;
      setAddControlBusy(link, true, originalText);
      try {
        const csrfToken = await getCartCsrfToken();
        const body = new FormData();
        body.append('quantity', '1');
        const response = await fetch(link.dataset.cartAddUrl, {
          method: 'POST',
          body,
          credentials: 'same-origin',
          headers: {
            'X-CSRFToken': csrfToken,
            'X-Requested-With': 'XMLHttpRequest'
          }
        });
        const data = await readJsonResponse(response);
        if (response.ok && data.success) {
          showAddSuccess(link, originalText, data);
        } else {
          setAddControlBusy(link, false, originalText);
          showToast(data.error || 'Erro ao adicionar.', 'error');
        }
      } catch {
        setAddControlBusy(link, false, originalText);
        showToast('Não foi possível adicionar o produto. Tente novamente.', 'error');
      }
    });
  });

  // CEP formatting
  document.querySelectorAll('input[name="cep"], #checkoutCep').forEach(input => {
    input.addEventListener('input', function () {
      let v = this.value.replace(/\D/g, '');
      if (v.length > 5) v = v.slice(0, 5) + '-' + v.slice(5, 8);
      this.value = v;
    });
  });

  // Phone number formatting
  document.querySelectorAll('input[name="customer_whatsapp"], input[name="whatsapp"]').forEach(input => {
    input.addEventListener('input', function () {
      let v = this.value.replace(/\D/g, '');
      if (v.length <= 2) v = v;
      else if (v.length <= 6) v = `(${v.slice(0,2)}) ${v.slice(2)}`;
      else if (v.length <= 10) v = `(${v.slice(0,2)}) ${v.slice(2,6)}-${v.slice(6)}`;
      else v = `(${v.slice(0,2)}) ${v.slice(2,7)}-${v.slice(7,11)}`;
      this.value = v;
    });
  });

  // CPF formatting
  document.querySelectorAll('input[name="cpf"]').forEach(input => {
    input.addEventListener('input', function () {
      let v = this.value.replace(/\D/g, '').slice(0, 11);
      if (v.length > 9) v = `${v.slice(0,3)}.${v.slice(3,6)}.${v.slice(6,9)}-${v.slice(9)}`;
      else if (v.length > 6) v = `${v.slice(0,3)}.${v.slice(3,6)}.${v.slice(6)}`;
      else if (v.length > 3) v = `${v.slice(0,3)}.${v.slice(3)}`;
      this.value = v;
    });
  });
});

// Toast notification
function showToast(message, type = 'success') {
  const existing = document.querySelector('.toast-notification');
  if (existing) existing.remove();
  const toast = document.createElement('div');
  toast.className = `toast-notification toast-${type}`;
  const icon = document.createElement('i');
  icon.className = `fas fa-${type === 'success' ? 'check-circle' : 'exclamation-circle'}`;
  const text = document.createElement('span');
  text.textContent = message;
  toast.append(icon, text);
  document.body.appendChild(toast);
  setTimeout(() => toast.classList.add('toast-show'), 10);
  setTimeout(() => { toast.classList.remove('toast-show'); setTimeout(() => toast.remove(), 300); }, 3000);
}

// Inline toast styles
const style = document.createElement('style');
style.textContent = `
.toast-notification { position: fixed; bottom: 100px; right: 28px; background: #2B1A14; color: #FFF9F5; padding: 14px 20px; border-radius: 10px; font-family: 'Jost', sans-serif; font-size: 14px; display: flex; align-items: center; gap: 10px; z-index: 9999; transform: translateY(20px); opacity: 0; transition: all 0.3s ease; box-shadow: 0 8px 24px rgba(43,26,20,0.3); max-width: 320px; }
.toast-notification.toast-show { transform: translateY(0); opacity: 1; }
.toast-success i { color: #66BB6A; }
.toast-error { background: #c62828; }
.btn-success-flash { background: #2e7d32 !important; border-color: #2e7d32 !important; color: white !important; }
@media (max-width: 480px) { .toast-notification { right: 16px; left: 16px; bottom: 80px; } }
`;
document.head.appendChild(style);
