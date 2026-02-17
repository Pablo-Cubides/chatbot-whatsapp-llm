(function () {
  async function request(url, options) {
    const opts = { ...(options || {}) };
    if (window.Auth && typeof window.Auth.fetchWithAuth === 'function') {
      const response = await window.Auth.fetchWithAuth(url, opts);
      return response;
    }

    opts.headers = window.Auth ? window.Auth.authHeaders(opts.headers || {}) : (opts.headers || {});
    const response = await fetch(url, opts);
    return response;
  }

  async function json(url, options) {
    const response = await request(url, options);
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      const detail = data?.detail || data?.message || `HTTP ${response.status}`;
      throw new Error(detail);
    }
    return data;
  }

  window.Api = { request, json };
})();