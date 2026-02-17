let currentStep = 1;
const totalSteps = 4;
let selectedMode = 'web';

async function apiRequest(url, options = {}) {
  if (window.Api && typeof window.Api.request === 'function') {
    return window.Api.request(url, options);
  }
  return fetch(url, options);
}

async function apiJson(url, options = {}) {
  if (window.Api && typeof window.Api.json === 'function') {
    return window.Api.json(url, options);
  }

  const response = await fetch(url, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data?.detail || data?.message || `HTTP ${response.status}`);
  }
  return data;
}

async function loadExistingConfig() {
  try {
    const config = await apiJson('/api/business/config');
    if (config.business_info) {
      document.getElementById('businessName').value = config.business_info.name || '';
      document.getElementById('businessDesc').value = config.business_info.description || '';
      document.getElementById('businessPhone').value = config.business_info.contact_phone || '';
      document.getElementById('businessHours').value = config.business_info.hours || '';
    }
  } catch {
    console.log('No existing config');
  }
}

function updateProgress() {
  const fill = document.getElementById('progressFill');
  const percentage = ((currentStep - 1) / (totalSteps - 1)) * 100;
  fill.style.width = `${percentage}%`;

  document.querySelectorAll('.step-indicator').forEach((indicator, index) => {
    indicator.classList.remove('active', 'completed');
    if (index + 1 < currentStep) {
      indicator.classList.add('completed');
    } else if (index + 1 === currentStep) {
      indicator.classList.add('active');
    }
  });

  const prevBtn = document.getElementById('prevBtn');
  prevBtn.style.visibility = currentStep === 1 ? 'hidden' : 'visible';

  const nextBtn = document.getElementById('nextBtn');
  nextBtn.textContent = '';

  if (currentStep === totalSteps) {
    const icon = document.createElement('i');
    icon.className = 'fas fa-rocket';
    nextBtn.appendChild(icon);
    nextBtn.appendChild(document.createTextNode(' Ir al Panel'));
  } else {
    nextBtn.appendChild(document.createTextNode('Siguiente '));
    const icon = document.createElement('i');
    icon.className = 'fas fa-arrow-right';
    nextBtn.appendChild(icon);
  }
}

function showStep(step) {
  document.querySelectorAll('.step-content').forEach((content) => {
    content.classList.remove('active');
  });
  const target = document.querySelector(`.step-content[data-step="${step}"]`);
  if (target) {
    target.classList.add('active');
  }

  if (step === 3) {
    const name = document.getElementById('businessName').value || 'tu negocio';
    document.getElementById('previewName').textContent = name;
  }

  updateProgress();
}

async function saveBusinessConfig() {
  try {
    let config = {};
    try {
      config = await apiJson('/api/business/config');
    } catch {
      config = {};
    }

    config.business_info = {
      ...config.business_info,
      name: document.getElementById('businessName').value,
      description: document.getElementById('businessDesc').value,
      contact_phone: document.getElementById('businessPhone').value,
      hours: document.getElementById('businessHours').value
    };

    await apiJson('/api/business/config', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(config)
    });
  } catch (e) {
    console.error('Error saving config:', e);
  }
}

async function saveWhatsAppConfig() {
  try {
    const config = { mode: selectedMode };

    if (selectedMode === 'cloud' || selectedMode === 'both') {
      config.cloud_api = {
        phone_number_id: document.getElementById('phoneNumberId').value,
        access_token: document.getElementById('accessToken').value
      };
    }

    await apiJson('/api/whatsapp/provider/config', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(config)
    });
  } catch (e) {
    console.error('Error saving WhatsApp config:', e);
  }
}

async function nextStep() {
  const nextBtn = document.getElementById('nextBtn');
  const wizard = document.querySelector('.wizard-content');
  if (nextBtn.disabled) {
    return;
  }

  nextBtn.disabled = true;
  const originalHtml = nextBtn.innerHTML;
  nextBtn.innerHTML = '<span class="spinner" aria-hidden="true"></span> Guardando...';
  if (wizard) {
    wizard.setAttribute('aria-busy', 'true');
  }

  if (currentStep === 1) {
    const name = document.getElementById('businessName').value.trim();
    if (!name) {
      alert('Por favor ingresa el nombre de tu negocio');
      nextBtn.disabled = false;
      nextBtn.innerHTML = originalHtml;
      if (wizard) wizard.setAttribute('aria-busy', 'false');
      return;
    }
    await saveBusinessConfig();
  } else if (currentStep === 2) {
    await saveWhatsAppConfig();
  }

  if (currentStep < totalSteps) {
    currentStep++;
    showStep(currentStep);
  } else {
    window.location.href = '/ui/index.html';
  }

  nextBtn.disabled = false;
  nextBtn.innerHTML = originalHtml;
  if (wizard) {
    wizard.setAttribute('aria-busy', 'false');
  }
}

function prevStep() {
  if (currentStep > 1) {
    currentStep--;
    showStep(currentStep);
  }
}

function createChatMessage(roleClass, speaker, text) {
  const div = document.createElement('div');
  div.className = `chat-message ${roleClass}`;

  const strong = document.createElement('strong');
  strong.textContent = `${speaker}:`;
  div.appendChild(strong);
  div.appendChild(document.createTextNode(` ${text}`));

  return div;
}

async function sendTestMessage() {
  const input = document.getElementById('testMessage');
  const message = input.value.trim();
  if (!message) return;

  const preview = document.getElementById('chatPreview');
  preview.appendChild(createChatMessage('user', 'Tú', message));
  input.value = '';

  const typingMessage = document.createElement('div');
  typingMessage.className = 'chat-message bot';
  const spinner = document.createElement('i');
  spinner.className = 'fas fa-spinner fa-spin';
  typingMessage.appendChild(spinner);
  typingMessage.appendChild(document.createTextNode(' Escribiendo...'));
  preview.appendChild(typingMessage);
  preview.scrollTop = preview.scrollHeight;

  try {
    const data = await apiJson('/api/chat/test', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ message })
    });

    const messages = preview.querySelectorAll('.chat-message');
    messages[messages.length - 1].remove();

    const botMessage = data.response || data.message || 'Respuesta del bot aquí...';
    preview.appendChild(createChatMessage('bot', 'Bot', botMessage));
    preview.scrollTop = preview.scrollHeight;
  } catch {
    const messages = preview.querySelectorAll('.chat-message');
    const fallback = messages[messages.length - 1];
    fallback.textContent = '';
    const strong = document.createElement('strong');
    strong.textContent = 'Bot:';
    fallback.appendChild(strong);
    fallback.appendChild(document.createTextNode(' (Error de conexión - esto funcionará cuando el bot esté activo)'));
  }
}

function bindSetupEvents() {
  document.querySelectorAll('.mode-card').forEach((card) => {
    card.addEventListener('click', () => {
      document.querySelectorAll('.mode-card').forEach((c) => c.classList.remove('selected'));
      card.classList.add('selected');
      selectedMode = card.dataset.mode;

      const cloudCreds = document.getElementById('cloudCredentials');
      cloudCreds.style.display = (selectedMode === 'cloud' || selectedMode === 'both') ? 'block' : 'none';
    });
  });

  const prevBtn = document.getElementById('prevBtn');
  const nextBtn = document.getElementById('nextBtn');
  const testSendBtn = document.getElementById('testSendBtn');
  const testMessageInput = document.getElementById('testMessage');

  if (prevBtn) prevBtn.addEventListener('click', prevStep);
  if (nextBtn) nextBtn.addEventListener('click', nextStep);
  if (testSendBtn) testSendBtn.addEventListener('click', sendTestMessage);
  if (testMessageInput) {
    testMessageInput.addEventListener('keypress', (e) => {
      if (e.key === 'Enter') sendTestMessage();
    });
  }
}

document.addEventListener('DOMContentLoaded', async () => {
  if (!window.Auth || !window.Auth.requireAuth('/ui/login.html')) {
    return;
  }

  bindSetupEvents();
  updateProgress();
  await loadExistingConfig();
});

window.nextStep = nextStep;
window.prevStep = prevStep;
window.sendTestMessage = sendTestMessage;
