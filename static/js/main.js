// Jane Miranda — Main JS

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

  // Add to cart AJAX
  document.querySelectorAll('.add-to-cart-form').forEach(form => {
    form.addEventListener('submit', async e => {
      e.preventDefault();
      const btn = form.querySelector('button[type="submit"]');
      const originalText = btn.innerHTML;
      btn.disabled = true;
      btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
      try {
        const fd = new FormData(form);
        const res = await fetch(form.action, {
          method: 'POST', body: fd,
          headers: { 'X-Requested-With': 'XMLHttpRequest' }
        });
        const data = await res.json();
        if (data.success) {
          // Update cart badge
          const badge = document.querySelector('.cart-badge');
          if (badge) { badge.textContent = data.cart_count; }
          else {
            const cartBtn = document.querySelector('.cart-btn');
            if (cartBtn) {
              const span = document.createElement('span');
              span.className = 'cart-badge';
              span.textContent = data.cart_count;
              cartBtn.appendChild(span);
            }
          }
          btn.innerHTML = '<i class="fas fa-check"></i> Adicionado!';
          btn.classList.add('btn-success-flash');
          setTimeout(() => {
            btn.innerHTML = originalText;
            btn.disabled = false;
            btn.classList.remove('btn-success-flash');
          }, 1800);
          showToast(data.message || 'Produto adicionado ao carrinho!', 'success');
        } else {
          btn.innerHTML = originalText;
          btn.disabled = false;
          showToast(data.error || 'Erro ao adicionar.', 'error');
        }
      } catch {
        btn.innerHTML = originalText;
        btn.disabled = false;
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
