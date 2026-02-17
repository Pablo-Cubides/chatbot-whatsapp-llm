document.addEventListener('DOMContentLoaded', () => {
  const copyrightYear = document.getElementById('copyrightYear');
  if (copyrightYear) {
    copyrightYear.textContent = new Date().getFullYear();
  }

  const forgotLink = document.getElementById('forgotPasswordLink');
  const modal = document.getElementById('contactAdminModal');
  const closeBtn = document.getElementById('closeContactAdminModal');

  if (forgotLink && modal && closeBtn) {
    function closeModal() {
      modal.classList.remove('is-open');
      modal.setAttribute('aria-hidden', 'true');
      forgotLink.focus();
    }

    forgotLink.addEventListener('click', (event) => {
      event.preventDefault();
      modal.classList.add('is-open');
      modal.setAttribute('aria-hidden', 'false');
      closeBtn.focus();
    });

    closeBtn.addEventListener('click', closeModal);
    modal.addEventListener('click', (event) => {
      if (event.target === modal) closeModal();
    });

    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape' && modal.getAttribute('aria-hidden') === 'false') {
        closeModal();
      }
    });
  }

  const token = sessionStorage.getItem('token');
  if (token) {
    window.Auth.fetchWithAuth('/api/verify')
      .then((r) => {
        if (r.ok) {
          checkSetupStatus();
        }
      })
      .catch(() => {
        sessionStorage.removeItem('token');
      });
  }

  const loginForm = document.getElementById('loginForm');
  if (loginForm) {
    loginForm.addEventListener('submit', handleLogin);
  }
});

async function checkSetupStatus() {
  try {
    const response = await window.Auth.fetchWithAuth('/api/business/config');

    if (response.ok) {
      const config = await response.json();
      if (!config.business_info?.name || config.business_info?.name === 'Mi Negocio') {
        window.location.href = '/ui/setup.html';
      } else {
        window.location.href = '/ui/index.html';
      }
    } else {
      window.location.href = '/ui/index.html';
    }
  } catch {
    window.location.href = '/ui/index.html';
  }
}

window.handleLogin = async function handleLogin(event) {
  event.preventDefault();

  const username = document.getElementById('username').value;
  const password = document.getElementById('password').value;
  const usernameInput = document.getElementById('username');
  const passwordInput = document.getElementById('password');
  const loginBtn = document.getElementById('loginBtn');
  const errorMessage = document.getElementById('errorMessage');
  const errorText = document.getElementById('errorText');

  errorMessage.classList.remove('show');
  usernameInput.setAttribute('aria-invalid', 'false');
  passwordInput.setAttribute('aria-invalid', 'false');

  loginBtn.classList.add('loading');
  loginBtn.disabled = true;
  document.getElementById('loginForm').setAttribute('aria-busy', 'true');

  try {
    const response = await fetch('/api/auth/login', {
      method: 'POST',
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ username, password })
    });

    const data = await response.json();

    if (response.ok && data.access_token) {
      sessionStorage.setItem('token', data.access_token);
      sessionStorage.setItem('username', username);

      if (document.getElementById('rememberMe').checked) {
        sessionStorage.setItem('remember', 'true');
      }

      await checkSetupStatus();
    } else {
      errorText.textContent = data.detail || 'Credenciales incorrectas';
      usernameInput.setAttribute('aria-invalid', 'true');
      passwordInput.setAttribute('aria-invalid', 'true');
      errorMessage.classList.add('show');
      errorMessage.focus();
    }
  } catch {
    errorText.textContent = 'Error de conexión. Verifica que el servidor esté activo.';
    usernameInput.setAttribute('aria-invalid', 'true');
    passwordInput.setAttribute('aria-invalid', 'true');
    errorMessage.classList.add('show');
    errorMessage.focus();
  } finally {
    loginBtn.classList.remove('loading');
    loginBtn.disabled = false;
    document.getElementById('loginForm').setAttribute('aria-busy', 'false');
  }
};
