(function () {
  function clear(el) {
    if (!el) return;
    el.replaceChildren();
  }

  function setText(el, text) {
    if (!el) return;
    el.textContent = text ?? '';
  }

  function setHTML(el, html) {
    if (!el) return;
    if (window.DOMPurify) {
      el.innerHTML = window.DOMPurify.sanitize(String(html || ''), {
        ALLOWED_TAGS: ['div', 'span', 'strong', 'b', 'i', 'p', 'ul', 'ol', 'li', 'br', 'small', 'button', 'h2', 'h3', 'h4'],
        ALLOWED_ATTR: ['class', 'style', 'data-*']
      });
      return;
    }

    // Fallback: text-only when DOMPurify is unavailable
    el.textContent = String(html || '');
  }

  window.SafeDOM = { clear, setText, setHTML };
})();