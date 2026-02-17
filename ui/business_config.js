let currentConfig = {};
const API_BASE = '/api/business';

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

function showTab(tabName, triggerButton = null) {
    document.querySelectorAll('.tab-content').forEach(tab => {
        tab.classList.remove('active');
    });
    document.querySelectorAll('.tab').forEach(tab => {
        tab.classList.remove('active');
    });

    const tabContent = document.getElementById(tabName);
    if (tabContent) {
        tabContent.classList.add('active');
    }

    const activeButton = triggerButton || document.querySelector(`.tab[data-tab="${tabName}"]`);
    if (activeButton) {
        activeButton.classList.add('active');
    }
}

async function loadConfig() {
    showLoading(true);
    try {
        currentConfig = await apiJson(`${API_BASE}/config`);
        populateForm();
        showAlert('Configuración cargada exitosamente', 'success');
    } catch (error) {
        showAlert('Error cargando configuración: ' + error.message, 'error');
    } finally {
        showLoading(false);
    }
}

function populateForm() {
    const business = currentConfig.business_info || {};
    const objectives = currentConfig.client_objectives || {};
    const behavior = currentConfig.ai_behavior || {};

    document.getElementById('business_name').value = business.name || '';
    document.getElementById('business_description').value = business.description || '';
    document.getElementById('business_greeting').value = business.greeting || '';
    document.getElementById('primary_goal').value = objectives.primary_goal || '';
    document.getElementById('business_hours').value = business.hours || '';
    document.getElementById('contact_info').value = business.contact_info || '';
    document.getElementById('closing_message').value = business.closing || '';
    document.getElementById('tone').value = business.tone || 'profesional_amigable';

    populateList('services', business.services || []);
    populateList('personality', behavior.personality_traits || []);
    populateList('forbidden', behavior.forbidden_topics || []);
    populateList('keywords', objectives.conversion_keywords || []);
    populateList('questions', objectives.qualification_questions || []);
}

function populateList(listName, items) {
    const container = document.getElementById(`${listName}_list`);
    container.textContent = '';

    items.forEach((item) => {
        addListItem(listName, item);
    });
}

function addListItem(listName, value = '') {
    const container = document.getElementById(`${listName}_list`);
    const itemDiv = document.createElement('div');
    itemDiv.className = 'list-item';

    const input = document.createElement('input');
    input.type = 'text';
    input.value = value;
    input.placeholder = 'Escribe aquí...';

    const button = document.createElement('button');
    button.addEventListener('click', () => removeListItem(button));

    const icon = document.createElement('i');
    icon.className = 'fas fa-trash';
    button.appendChild(icon);

    itemDiv.appendChild(input);
    itemDiv.appendChild(button);

    container.appendChild(itemDiv);
}

function removeListItem(button) {
    button.parentElement.remove();
}

function getListValues(listName) {
    const container = document.getElementById(`${listName}_list`);
    const inputs = container.querySelectorAll('input');
    return Array.from(inputs).map(input => input.value.trim()).filter(val => val);
}

function collectFormData() {
    return {
        business_info: {
            name: document.getElementById('business_name').value,
            description: document.getElementById('business_description').value,
            greeting: document.getElementById('business_greeting').value,
            closing: document.getElementById('closing_message').value,
            tone: document.getElementById('tone').value,
            services: getListValues('services'),
            hours: document.getElementById('business_hours').value,
            contact_info: document.getElementById('contact_info').value
        },
        client_objectives: {
            primary_goal: document.getElementById('primary_goal').value,
            conversion_keywords: getListValues('keywords'),
            qualification_questions: getListValues('questions')
        },
        ai_behavior: {
            personality_traits: getListValues('personality'),
            forbidden_topics: getListValues('forbidden'),
            use_emojis: true,
            formality_level: document.getElementById('tone').value
        }
    };
}

async function saveConfig() {
    const formData = collectFormData();

    if (!formData.business_info.name) {
        showAlert('El nombre del negocio es requerido', 'error');
        return;
    }

    showLoading(true);
    try {
        await apiJson(`${API_BASE}/config`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(formData)
        });
        currentConfig = { ...currentConfig, ...formData };
        showAlert('Configuración guardada exitosamente', 'success');
    } catch (error) {
        showAlert('Error guardando: ' + error.message, 'error');
    } finally {
        showLoading(false);
    }
}

async function generatePreview() {
    showLoading(true);
    try {
        const preview = await apiJson(`${API_BASE}/preview`);

        document.getElementById('generated_prompt').textContent = preview.generated_prompt;
        document.getElementById('config_completeness').textContent = calculateCompleteness() + '%';
        document.getElementById('prompt_length').textContent = preview.generated_prompt.length;
        document.getElementById('services_count').textContent = (preview.services || []).length;
        document.getElementById('personality_count').textContent = (preview.personality || []).length;

        showTab('preview');
    } catch (error) {
        showAlert('Error en vista previa: ' + error.message, 'error');
    } finally {
        showLoading(false);
    }
}

function calculateCompleteness() {
    const requiredFields = [
        'business_name',
        'business_description',
        'business_greeting',
        'primary_goal'
    ];

    let completed = 0;
    requiredFields.forEach(field => {
        if (document.getElementById(field).value.trim()) {
            completed++;
        }
    });

    return Math.round((completed / requiredFields.length) * 100);
}

async function exportConfig() {
    try {
        const response = await apiRequest(`${API_BASE}/config/export`, {
            method: 'POST',
        });

        if (response.ok) {
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'business_config.json';
            a.click();
            window.URL.revokeObjectURL(url);

            showAlert('Configuración exportada exitosamente', 'success');
        } else {
            throw new Error('Error exportando configuración');
        }
    } catch (error) {
        showAlert('Error exportando: ' + error.message, 'error');
    }
}

function importConfig() {
    document.getElementById('import_file').click();
}

async function handleImport(event) {
    const file = event.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    showLoading(true);
    try {
        const response = await apiRequest(`${API_BASE}/config/import`, {
            method: 'POST',
            body: formData
        });

        if (response.ok) {
            showAlert('Configuración importada exitosamente', 'success');
            await loadConfig();
        } else {
            throw new Error('Error importando configuración');
        }
    } catch (error) {
        showAlert('Error importando: ' + error.message, 'error');
    } finally {
        showLoading(false);
    }
}

async function resetConfig() {
    if (!confirm('¿Estás seguro de que quieres reiniciar la configuración a los valores por defecto?')) {
        return;
    }

    showLoading(true);
    try {
        await apiJson(`${API_BASE}/config/reset`, {
            method: 'POST',
        });
        showAlert('Configuración reiniciada exitosamente', 'success');
        await loadConfig();
    } catch (error) {
        showAlert('Error reiniciando: ' + error.message, 'error');
    } finally {
        showLoading(false);
    }
}

function showLoading(show) {
    document.getElementById('loading').style.display = show ? 'block' : 'none';
    const content = document.querySelector('.content');
    if (content) {
        content.setAttribute('aria-busy', show ? 'true' : 'false');
    }
    document.querySelectorAll('.actions .btn').forEach((btn) => {
        btn.disabled = show;
    });
}

function showAlert(message, type) {
    if (window.showToast) {
        window.showToast({
            type: type === 'error' ? 'error' : (type === 'success' ? 'success' : 'info'),
            message,
        });
        return;
    }

    const alertsContainer = document.getElementById('alerts');
    const alert = document.createElement('div');
    alert.className = `alert alert-${type}`;

    const icon = type === 'success' ? 'check-circle' : 'exclamation-triangle';

    const iconElement = document.createElement('i');
    iconElement.className = `fas fa-${icon}`;
    const text = document.createElement('span');
    text.textContent = message;

    alert.appendChild(iconElement);
    alert.appendChild(text);

    alertsContainer.appendChild(alert);

    setTimeout(() => {
        alert.remove();
    }, 5000);
}

function setupEventHandlers() {
    document.querySelectorAll('.tab[data-tab]').forEach((button) => {
        button.addEventListener('click', () => {
            const tabName = button.getAttribute('data-tab');
            if (tabName) {
                showTab(tabName, button);
            }
        });
    });

    document.querySelectorAll('.add-item-btn[data-list]').forEach((button) => {
        button.addEventListener('click', () => {
            const listName = button.getAttribute('data-list');
            if (listName) {
                addListItem(listName);
            }
        });
    });

    const previewRefreshBtn = document.getElementById('previewRefreshBtn');
    const saveConfigBtn = document.getElementById('saveConfigBtn');
    const previewBtn = document.getElementById('previewBtn');
    const exportBtn = document.getElementById('exportBtn');
    const importBtn = document.getElementById('importBtn');
    const resetBtn = document.getElementById('resetBtn');
    const importFile = document.getElementById('import_file');

    if (previewRefreshBtn) previewRefreshBtn.addEventListener('click', generatePreview);
    if (saveConfigBtn) saveConfigBtn.addEventListener('click', saveConfig);
    if (previewBtn) previewBtn.addEventListener('click', generatePreview);
    if (exportBtn) exportBtn.addEventListener('click', exportConfig);
    if (importBtn) importBtn.addEventListener('click', importConfig);
    if (resetBtn) resetBtn.addEventListener('click', resetConfig);
    if (importFile) importFile.addEventListener('change', handleImport);
}

document.addEventListener('DOMContentLoaded', function() {
    if (!window.Auth || !window.Auth.requireAuth('/ui/login.html')) {
        return;
    }

    setupEventHandlers();
    loadConfig();
});
