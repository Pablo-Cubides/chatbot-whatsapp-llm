(function () {
  if (window.showToast) {
    return;
  }

  function ensureStack() {
    let stack = document.getElementById('toastStack');
    if (!stack) {
      stack = document.createElement('div');
      stack.id = 'toastStack';
      stack.className = 'toast-stack';
      stack.setAttribute('aria-live', 'polite');
      stack.setAttribute('aria-atomic', 'false');
      document.body.appendChild(stack);
    }
    return stack;
  }

  function showToast(options) {
    const opts = typeof options === 'string' ? { message: options } : (options || {});
    const type = opts.type || 'info';
    const message = opts.message || '';
    const timeoutMs = Number.isFinite(Number(opts.timeout)) ? Number(opts.timeout) : 5000;

    const stack = ensureStack();
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.setAttribute('role', 'status');

    const msg = document.createElement('div');
    msg.textContent = message;

    const closeBtn = document.createElement('button');
    closeBtn.setAttribute('type', 'button');
    closeBtn.setAttribute('aria-label', 'Cerrar notificación');
    closeBtn.textContent = '×';
    closeBtn.addEventListener('click', () => toast.remove());

    toast.appendChild(msg);
    toast.appendChild(closeBtn);
    stack.appendChild(toast);

    window.setTimeout(() => {
      toast.remove();
    }, timeoutMs);
  }

  const nativeAlert = window.alert.bind(window);
  window.showToast = showToast;
  window.alert = function patchedAlert(message) {
    if (document && document.body) {
      showToast({ type: 'info', message: String(message || '') });
      return;
    }
    nativeAlert(message);
  };
})();
