(function () {
  if (window.__sharedNavInstalled) {
    return;
  }
  window.__sharedNavInstalled = true;

  const NAV_ITEMS = [
    { href: '/ui/index.html', icon: '🏠', label: 'Dashboard' },
    { href: '/ui/chat.html', icon: '💬', label: 'Chat' },
    { href: '/ui/realtime_dashboard.html', icon: '📈', label: 'Realtime' },
    { href: '/ui/analytics.html', icon: '📊', label: 'Analytics' },
    { href: '/ui/business_config.html', icon: '🧩', label: 'Negocio' },
    { href: '/ui/calendar_config.html', icon: '📅', label: 'Calendario' },
    { href: '/ui/alerts.html', icon: '🚨', label: 'Alertas' },
    { href: '/ui/setup.html', icon: '⚙️', label: 'Setup' }
  ];

  function isUiPage() {
    return (window.location.pathname || '').includes('/ui/');
  }

  function addSkipLink() {
    if (document.querySelector('.skip-link')) return;
    const link = document.createElement('a');
    link.className = 'skip-link';
    link.href = '#main-content';
    link.textContent = 'Skip to content';
    document.body.prepend(link);
  }

  function ensureMainLandmark() {
    let main = document.getElementById('main-content');
    if (!main) {
      main = document.querySelector('main') || document.querySelector('.container') || document.body.firstElementChild;
      if (main) {
        main.id = 'main-content';
      }
    }
    if (main) {
      main.setAttribute('role', 'main');
      if (main.tagName.toLowerCase() !== 'main') {
        main.setAttribute('tabindex', '-1');
      }
    }
  }

  function ensureHeaderLandmark() {
    const header = document.querySelector('header') || document.querySelector('.header');
    if (header) header.setAttribute('role', 'banner');
  }

  function renderNav() {
    const path = window.location.pathname || '';
    if (path.endsWith('/login.html')) return;
    if (document.getElementById('sharedNav')) return;

    const anchor = document.querySelector('#main-content') || document.querySelector('.container');
    if (!anchor) return;

    const nav = document.createElement('nav');
    nav.id = 'sharedNav';
    nav.className = 'shared-nav';
    nav.setAttribute('role', 'navigation');
    nav.setAttribute('aria-label', 'Navegación principal');

    const ul = document.createElement('ul');
    NAV_ITEMS.forEach((item) => {
      const li = document.createElement('li');
      const a = document.createElement('a');
      a.href = item.href;
      a.textContent = `${item.icon} ${item.label}`;
      if (path.endsWith(item.href.replace('/ui/', '/')) || path.endsWith(item.href)) {
        a.setAttribute('aria-current', 'page');
      }
      li.appendChild(a);
      ul.appendChild(li);
    });

    nav.appendChild(ul);
    anchor.prepend(nav);
  }

  function enhanceInteractiveCards() {
    if (!(window.location.pathname || '').endsWith('/index.html')) return;
    const cards = document.querySelectorAll('.card');
    cards.forEach((card) => {
      const firstAction = card.querySelector('a.card-button,button.card-button');
      if (!firstAction) return;
      card.setAttribute('role', 'button');
      card.setAttribute('tabindex', '0');
      card.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          firstAction.click();
        }
      });
    });
  }

  function ensureLiveRegions() {
    const chatMessages = document.getElementById('chatMessages');
    if (chatMessages) {
      chatMessages.setAttribute('aria-live', 'polite');
      chatMessages.setAttribute('aria-relevant', 'additions text');
    }

    const metricsContent = document.getElementById('metricsContent');
    if (metricsContent) {
      metricsContent.setAttribute('aria-live', 'polite');
      metricsContent.setAttribute('aria-relevant', 'text');
    }
  }

  function ensureLabelsForInputs() {
    const labels = document.querySelectorAll('label:not([for])');
    labels.forEach((label, index) => {
      const control = label.querySelector('input,select,textarea') || label.parentElement?.querySelector('input,select,textarea');
      if (!control) return;
      if (!control.id) {
        control.id = `auto-field-${index + 1}`;
      }
      label.setAttribute('for', control.id);
    });
  }

  function trapModalFocus(modal) {
    if (!modal || modal.__focusTrapInstalled) return;
    modal.__focusTrapInstalled = true;
    let previousFocus = null;

    const focusableSelector = 'a[href],button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])';

    const onKeyDown = (event) => {
      if (event.key === 'Escape') {
        modal.classList.remove('active');
        modal.setAttribute('aria-hidden', 'true');
        if (previousFocus && typeof previousFocus.focus === 'function') previousFocus.focus();
        return;
      }

      if (event.key !== 'Tab') return;
      const focusable = modal.querySelectorAll(focusableSelector);
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];

      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };

    const observer = new MutationObserver(() => {
      const active = modal.classList.contains('active') || modal.getAttribute('aria-hidden') === 'false';
      if (active) {
        previousFocus = document.activeElement;
        modal.setAttribute('role', 'dialog');
        modal.setAttribute('aria-modal', 'true');
        modal.setAttribute('aria-hidden', 'false');
        const first = modal.querySelector(focusableSelector);
        if (first) first.focus();
        modal.addEventListener('keydown', onKeyDown);
      } else {
        modal.setAttribute('aria-hidden', 'true');
        modal.removeEventListener('keydown', onKeyDown);
      }
    });

    observer.observe(modal, { attributes: true, attributeFilter: ['class', 'aria-hidden', 'style'] });
  }

  function setupModalAccessibility() {
    const modals = document.querySelectorAll('.modal, [data-modal]');
    modals.forEach((m) => trapModalFocus(m));
  }

  function setupFormLoadingStates() {
    document.querySelectorAll('form').forEach((form) => {
      if (form.__loadingEnhancementInstalled) return;
      form.__loadingEnhancementInstalled = true;

      form.addEventListener('submit', () => {
        form.setAttribute('aria-busy', 'true');
        const submitButtons = form.querySelectorAll('button[type="submit"],input[type="submit"]');
        submitButtons.forEach((btn) => {
          btn.dataset.originalText = btn.tagName === 'BUTTON' ? btn.innerHTML : btn.value;
          btn.disabled = true;
          if (btn.tagName === 'BUTTON') {
            btn.innerHTML = '<span class="spinner" aria-hidden="true"></span> Procesando...';
          } else {
            btn.value = 'Procesando...';
          }
        });

        window.setTimeout(() => {
          form.setAttribute('aria-busy', 'false');
          submitButtons.forEach((btn) => {
            btn.disabled = false;
            if (btn.dataset.originalText) {
              if (btn.tagName === 'BUTTON') {
                btn.innerHTML = btn.dataset.originalText;
              } else {
                btn.value = btn.dataset.originalText;
              }
            }
          });
        }, 12000);
      });
    });
  }

  function init() {
    if (!isUiPage()) return;
    addSkipLink();
    ensureMainLandmark();
    ensureHeaderLandmark();
    renderNav();
    ensureLabelsForInputs();
    ensureLiveRegions();
    enhanceInteractiveCards();
    setupModalAccessibility();
    setupFormLoadingStates();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  window.renderNav = renderNav;
})();
