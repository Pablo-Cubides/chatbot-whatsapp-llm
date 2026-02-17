(function () {
  function ensureSharedUiScript(src) {
    if (!document || !document.head) return;
    if (document.querySelector(`script[src="${src}"]`)) return;
    const script = document.createElement('script');
    script.src = src;
    script.defer = true;
    document.head.appendChild(script);
  }

  const isUiPage = (window.location.pathname || '').includes('/ui/');
  if (isUiPage) {
    ensureSharedUiScript('/ui/toast.js');
    ensureSharedUiScript('/ui/nav.js');
  }

  const rawFetch = window.__authRawFetch || window.fetch.bind(window);
  window.__authRawFetch = rawFetch;
  const LAST_ACTIVITY_KEY = 'auth:lastActivityAt';
  const DEFAULT_IDLE_TIMEOUT_MS = 30 * 60 * 1000;
  const REMEMBER_IDLE_TIMEOUT_MS = 8 * 60 * 60 * 1000;

  class FrontendAuth {
    constructor() {
      this._idleInterval = null;
      this._activityBound = false;
      this._loggingOut = false;
    }

    getToken() {
      return sessionStorage.getItem('token') || '';
    }

    setToken(token) {
      if (!token) {
        sessionStorage.removeItem('token');
        return;
      }
      sessionStorage.setItem('token', token);
    }

    clearSession() {
      sessionStorage.removeItem('token');
      sessionStorage.removeItem('username');
      sessionStorage.removeItem('remember');
      sessionStorage.removeItem(LAST_ACTIVITY_KEY);
    }

    getIdleTimeoutMs() {
      const remember = sessionStorage.getItem('remember') === 'true';
      const configured = Number(window.AUTH_IDLE_TIMEOUT_MS || 0);
      if (Number.isFinite(configured) && configured > 0) {
        return configured;
      }
      return remember ? REMEMBER_IDLE_TIMEOUT_MS : DEFAULT_IDLE_TIMEOUT_MS;
    }

    touchActivity() {
      if (!this.getToken()) {
        return;
      }
      sessionStorage.setItem(LAST_ACTIVITY_KEY, String(Date.now()));
    }

    isIdleExpired() {
      if (!this.getToken()) {
        return false;
      }
      const raw = sessionStorage.getItem(LAST_ACTIVITY_KEY);
      const lastActivity = Number(raw || 0);
      if (!Number.isFinite(lastActivity) || lastActivity <= 0) {
        this.touchActivity();
        return false;
      }
      return Date.now() - lastActivity > this.getIdleTimeoutMs();
    }

    authHeaders(extra) {
      const token = this.getToken();
      if (!token) return { ...(extra || {}) };
      return { ...(extra || {}), Authorization: `Bearer ${token}` };
    }

    async refreshAccessToken() {
      const response = await rawFetch('/api/auth/refresh', {
        method: 'POST',
        credentials: 'include',
      });

      if (!response.ok) {
        this.clearSession();
        return false;
      }

      const data = await response.json();
      if (!data.access_token) {
        this.clearSession();
        return false;
      }

      this.setToken(data.access_token);
      return true;
    }

    async fetchWithAuth(url, options) {
      if (this.isIdleExpired()) {
        await this.logout('/ui/login.html');
        throw new Error('Session expired due to inactivity');
      }

      const requestOptions = { ...(options || {}) };
      requestOptions.headers = this.authHeaders(requestOptions.headers);
      requestOptions.credentials = 'include';

      let response = await rawFetch(url, requestOptions);
      if (response.ok) {
        this.touchActivity();
      }
      if (response.status !== 401) {
        return response;
      }

      const refreshed = await this.refreshAccessToken();
      if (!refreshed) {
        return response;
      }

      const retryOptions = { ...(options || {}) };
      retryOptions.headers = this.authHeaders(retryOptions.headers);
      retryOptions.credentials = 'include';
      response = await rawFetch(url, retryOptions);
      if (response.ok) {
        this.touchActivity();
      }
      return response;
    }

    requireAuth(redirectTo) {
      if (!this.getToken() || this.isIdleExpired()) {
        this.clearSession();
        window.location.href = redirectTo || '/ui/login.html';
        return false;
      }
      this.touchActivity();
      return true;
    }

    async logout(redirectTo) {
      if (this._loggingOut) {
        return;
      }
      this._loggingOut = true;
      try {
        const token = this.getToken();
        await rawFetch('/api/auth/logout', {
          method: 'POST',
          credentials: 'include',
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        });
      } catch (e) {
        // ignore network errors on logout
      } finally {
        this.clearSession();
        this._loggingOut = false;
        if (redirectTo) {
          window.location.href = redirectTo;
        }
      }
    }

    startSessionGuard(redirectTo) {
      if (this._activityBound) {
        return;
      }

      const events = ['click', 'keydown', 'mousemove', 'touchstart', 'scroll'];
      const onActivity = () => this.touchActivity();
      events.forEach((eventName) => {
        window.addEventListener(eventName, onActivity, { passive: true });
      });

      this._idleInterval = window.setInterval(() => {
        if (this.isIdleExpired()) {
          this.logout(redirectTo || '/ui/login.html');
        }
      }, 15000);

      this._activityBound = true;
      this.touchActivity();
    }
  }

  const auth = new FrontendAuth();

  function shouldInterceptApiCall(input) {
    const url = typeof input === 'string' ? input : (input && input.url ? input.url : '');
    if (!url) return false;
    if (!url.startsWith('/api/')) return false;
    if (url.startsWith('/api/auth/login') || url.startsWith('/api/auth/refresh')) return false;
    return true;
  }

  if (!window.__authApiInterceptorInstalled) {
    window.fetch = async function (input, init) {
      if (shouldInterceptApiCall(input)) {
        return auth.fetchWithAuth(input, init);
      }
      return rawFetch(input, init);
    };
    window.__authApiInterceptorInstalled = true;
  }

  const currentPath = window.location.pathname || '';
  const isLoginPage = currentPath.endsWith('/login.html') || currentPath === '/ui/login.html';
  if (!isLoginPage) {
    auth.startSessionGuard('/ui/login.html');
  }

  window.Auth = {
    getToken: auth.getToken.bind(auth),
    authHeaders: auth.authHeaders.bind(auth),
    requireAuth: auth.requireAuth.bind(auth),
    refreshAccessToken: auth.refreshAccessToken.bind(auth),
    fetchWithAuth: auth.fetchWithAuth.bind(auth),
    logout: auth.logout.bind(auth),
    clearSession: auth.clearSession.bind(auth),
    setToken: auth.setToken.bind(auth),
    isIdleExpired: auth.isIdleExpired.bind(auth),
    touchActivity: auth.touchActivity.bind(auth),
    startSessionGuard: auth.startSessionGuard.bind(auth),
  };
})();