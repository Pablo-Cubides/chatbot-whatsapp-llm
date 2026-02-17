document.getElementById('copyrightYear').textContent = new Date().getFullYear();

let statusInterval = null;

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

function closeModalById(id) {
    const modal = document.getElementById(id);
    if (modal) {
        modal.setAttribute('aria-hidden', 'true');
        modal.remove();
    }
}

function escapeAttr(value) {
    return String(value).replace(/"/g, '&quot;');
}

async function showApiManagement() {
    const modal = document.createElement('div');
    modal.id = 'apiModal';
    modal.className = 'modal active';
    modal.setAttribute('aria-hidden', 'false');

    SafeDOM.setHTML(modal, `
        <div class="ui-modal-overlay">
            <div role="dialog" aria-modal="true" aria-labelledby="apiModalTitle" class="ui-modal-dialog ui-modal-md">
                <h2 id="apiModalTitle" class="ui-modal-title">🤖 Gestión de APIs de IA</h2>

                <div id="apiContent">
                    <p>Cargando configuración...</p>
                </div>

                <hr class="ui-modal-separator">

                <h3>Agregar Proveedor Personalizado</h3>
                <form id="addProviderForm" class="ui-form-grid">
                    <input type="text" id="providerName" placeholder="Nombre (ej: Mi OpenAI)" required class="ui-input">
                    <select id="providerType" required class="ui-input">
                        <option value="">Seleccionar tipo...</option>
                        <option value="openai">OpenAI (GPT)</option>
                        <option value="gemini">Google Gemini</option>
                        <option value="claude">Anthropic Claude</option>
                        <option value="xai">xAI Grok</option>
                    </select>
                    <input type="password" id="providerApiKey" placeholder="API Key" required class="ui-input">
                    <input type="text" id="providerModel" placeholder="Modelo (ej: gpt-4o-mini)" required class="ui-input">
                    <button type="submit" class="ui-btn ui-btn-success">
                        ➕ Agregar Proveedor
                    </button>
                </form>

                <button type="button" data-action="close-api-modal" class="ui-btn ui-btn-secondary ui-btn-top-gap">
                    Cerrar
                </button>
            </div>
        </div>
    `);

    modal.addEventListener('click', async (event) => {
        const target = event.target;
        if (!(target instanceof HTMLElement)) return;

        if (target.dataset.action === 'close-api-modal') {
            closeModalById('apiModal');
            return;
        }

        if (target.dataset.action === 'delete-provider') {
            const name = target.dataset.providerName || '';
            await deleteProvider(name);
        }
    });

    document.body.appendChild(modal);

    try {
        const config = await apiJson('/api/ai-models/config');
        let html = '<div class="ui-mb-20">';
        html += `<p><strong>Proveedor por defecto:</strong> ${config.default_provider || 'auto'}</p>`;

        if (config.custom_providers && config.custom_providers.length > 0) {
            html += '<h4>Proveedores personalizados:</h4><ul>';
            config.custom_providers.forEach((p) => {
                html += `<li>${p.name} (${p.provider_type}) - ${p.model}
                    <button type="button" data-action="delete-provider" data-provider-name="${escapeAttr(p.name)}" class="ui-btn-delete-mini">❌</button>
                </li>`;
            });
            html += '</ul>';
        } else {
            html += '<p class="ui-text-muted">No hay proveedores personalizados configurados.</p>';
        }

        html += '</div>';
        SafeDOM.setHTML(document.getElementById('apiContent'), html);
    } catch (error) {
        SafeDOM.setHTML(document.getElementById('apiContent'), `<p class="ui-text-danger">Error: ${error.message}</p>`);
    }

    document.getElementById('addProviderForm').addEventListener('submit', async (e) => {
        e.preventDefault();

        const data = {
            name: document.getElementById('providerName').value,
            provider_type: document.getElementById('providerType').value,
            api_key: document.getElementById('providerApiKey').value,
            model: document.getElementById('providerModel').value,
            active: true,
        };

        try {
            const result = await apiJson('/api/ai-models/custom-provider', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(data),
            });
            if (result.success) {
                showToast({ type: 'success', message: '✅ Proveedor agregado exitosamente' });
                closeModalById('apiModal');
                showApiManagement();
            } else {
                showToast({ type: 'error', message: '❌ Error: ' + result.detail });
            }
        } catch (error) {
            showToast({ type: 'error', message: '❌ Error: ' + error.message });
        }
    });
}

async function deleteProvider(name) {
    if (!confirm(`¿Eliminar proveedor "${name}"?`)) return;

    try {
        const result = await apiJson(`/api/ai-models/custom-provider/${encodeURIComponent(name)}`, {
            method: 'DELETE',
        });
        if (result.success) {
            showToast({ type: 'success', message: '✅ Proveedor eliminado' });
            closeModalById('apiModal');
            showApiManagement();
        } else {
            showToast({ type: 'error', message: '❌ Error: ' + result.detail });
        }
    } catch (error) {
        showToast({ type: 'error', message: '❌ Error: ' + error.message });
    }
}

function startWhatsAppBot() {
    if (confirm('¿Iniciar el bot de WhatsApp? Asegúrate de tener la configuración de negocio completa.')) {
        apiJson('/api/whatsapp/start', {
            method: 'POST',
        })
            .then((data) => {
                if (data.success) {
                    showToast({ type: 'success', message: '✅ Bot de WhatsApp iniciado exitosamente' });
                    location.reload();
                } else {
                    showToast({ type: 'error', message: '❌ Error: ' + (data.message || 'No se pudo iniciar el bot') });
                }
            })
            .catch((error) => {
                showToast({ type: 'error', message: '❌ Error de conexión: ' + error.message });
            });
    }
}

function testApis() {
    showToast({ type: 'info', message: 'Probando conexión con todas las APIs...' });

    apiJson('/api/test-apis', {
        method: 'POST',
    })
        .then((data) => {
            const results = data.results || {};
            let message = 'Resultados de las pruebas:\n\n';

            Object.keys(results).forEach((api) => {
                const status = results[api] ? '✅' : '❌';
                message += `${status} ${api}: ${results[api] ? 'OK' : 'Error'}\n`;
            });

            showToast({ type: 'info', message });
        })
        .catch((error) => {
            showToast({ type: 'error', message: '❌ Error probando APIs: ' + error.message });
        });
}

function viewLogs() {
    window.open('/api/logs', '_blank');
}

async function showCampaigns() {
    const modal = document.createElement('div');
    modal.id = 'campaignModal';

    SafeDOM.setHTML(modal, `
        <div class="ui-modal-overlay">
            <div class="ui-modal-dialog ui-modal-lg">
                <h2 class="ui-modal-title">📢 Campañas Masivas</h2>

                <div id="campaignsList" class="ui-mb-20">
                    <p>Cargando campañas...</p>
                </div>

                <hr class="ui-modal-separator">

                <h3>➕ Crear Nueva Campaña</h3>
                <form id="createCampaignForm" class="ui-form-grid">
                    <input type="text" id="campaignName" placeholder="Nombre de la campaña" required class="ui-input">

                    <textarea id="campaignTemplate" placeholder="Mensaje template (usa {nombre} para personalizar)" required rows="4" class="ui-input ui-textarea">¡Hola {nombre}! 👋

Tenemos una promoción especial para ti. ¿Te gustaría conocer más detalles?</textarea>

                    <textarea id="campaignContacts" placeholder="Números de teléfono (uno por línea, ej: +57123456789)" required rows="4" class="ui-input ui-textarea ui-font-mono"></textarea>

                    <div class="ui-row-gap">
                        <input type="number" id="campaignDelay" value="5" min="1" max="60" class="ui-input ui-flex-1">
                        <span class="ui-align-center">segundos entre mensajes</span>
                    </div>

                    <button type="submit" class="ui-btn ui-btn-success ui-btn-lg">
                        🚀 Crear Campaña
                    </button>
                </form>

                <button type="button" data-action="close-campaign-modal" class="ui-btn ui-btn-secondary ui-btn-top-gap">
                    Cerrar
                </button>
            </div>
        </div>
    `);

    modal.addEventListener('click', async (event) => {
        const target = event.target;
        if (!(target instanceof HTMLElement)) return;

        if (target.dataset.action === 'close-campaign-modal') {
            closeModalById('campaignModal');
            return;
        }

        if (target.dataset.action === 'pause-campaign') {
            await pauseCampaign(target.dataset.campaignId || '');
            return;
        }

        if (target.dataset.action === 'resume-campaign') {
            await resumeCampaign(target.dataset.campaignId || '');
        }
    });

    document.body.appendChild(modal);

    try {
        const campaigns = await apiJson('/api/campaigns');
        let html = '';

        if (!campaigns || campaigns.length === 0) {
            html = '<p class="ui-text-muted">No hay campañas activas. Crea una nueva a continuación.</p>';
        } else {
            html = '<div class="ui-grid-gap">';
            campaigns.forEach((c) => {
                const statusClass = c.status === 'running'
                    ? 'campaign-status-running'
                    : c.status === 'completed'
                        ? 'campaign-status-completed'
                        : c.status === 'paused'
                            ? 'campaign-status-paused'
                            : 'campaign-status-default';
                html += `
                    <div class="campaign-item ${statusClass}">
                        <div class="campaign-item-head">
                            <strong>${c.name || 'Sin nombre'}</strong>
                            <span class="campaign-item-status">${c.status?.toUpperCase() || 'UNKNOWN'}</span>
                        </div>
                        <div class="campaign-item-meta">
                            Enviados: ${c.sent_count || 0}/${c.total_messages || 0}
                            | Creada: ${c.created_at ? new Date(c.created_at).toLocaleDateString() : 'N/A'}
                        </div>
                        ${c.status === 'running' ? `<button type="button" data-action="pause-campaign" data-campaign-id="${escapeAttr(c.id || '')}" class="ui-btn ui-btn-warning ui-btn-sm ui-btn-top-gap-sm">⏸️ Pausar</button>` : ''}
                        ${c.status === 'paused' ? `<button type="button" data-action="resume-campaign" data-campaign-id="${escapeAttr(c.id || '')}" class="ui-btn ui-btn-success ui-btn-sm ui-btn-top-gap-sm">▶️ Reanudar</button>` : ''}
                    </div>
                `;
            });
            html += '</div>';
        }

        SafeDOM.setHTML(document.getElementById('campaignsList'), html);
    } catch (error) {
        SafeDOM.setHTML(document.getElementById('campaignsList'), `<p class="ui-text-danger">Error: ${error.message}</p>`);
    }

    document.getElementById('createCampaignForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        const contacts = document
            .getElementById('campaignContacts')
            .value.split('\n')
            .map((c) => c.trim())
            .filter((c) => c.length > 0);

        if (contacts.length === 0) {
            showToast({ type: 'warning', message: '❌ Agrega al menos un número de contacto' });
            return;
        }

        const data = {
            name: document.getElementById('campaignName').value,
            template: document.getElementById('campaignTemplate').value,
            contacts,
            delay_between_messages: parseInt(document.getElementById('campaignDelay').value, 10) || 5,
        };

        try {
            const result = await apiJson('/api/campaigns', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(data),
            });
            if (result.success) {
                showToast({ type: 'success', message: `✅ ${result.message}` });
                closeModalById('campaignModal');
                showCampaigns();
            } else {
                showToast({ type: 'error', message: '❌ Error: ' + (result.detail || result.message) });
            }
        } catch (error) {
            showToast({ type: 'error', message: '❌ Error: ' + error.message });
        }
    });
}

async function pauseCampaign(campaignId) {
    try {
        const result = await apiJson(`/api/campaigns/${campaignId}/pause`, {
            method: 'POST',
        });
        if (result.success) {
            showToast({ type: 'success', message: '✅ Campaña pausada' });
            closeModalById('campaignModal');
            showCampaigns();
        }
    } catch (error) {
        showToast({ type: 'error', message: '❌ Error: ' + error.message });
    }
}

async function resumeCampaign(campaignId) {
    try {
        const result = await apiJson(`/api/campaigns/${campaignId}/resume`, {
            method: 'POST',
        });
        if (result.success) {
            showToast({ type: 'success', message: '✅ Campaña reanudada' });
            closeModalById('campaignModal');
            showCampaigns();
        }
    } catch (error) {
        showToast({ type: 'error', message: '❌ Error: ' + error.message });
    }
}

async function showScheduler() {
    try {
        const messages = await apiJson('/api/queue/pending');

        let message = '🕒 MENSAJES PROGRAMADOS\n\n';

        if (messages.length === 0) {
            message += 'No hay mensajes en la cola.\n\n';
        } else {
            const scheduled = messages.filter((m) => m.scheduled_at);

            message += `Total en cola: ${messages.length}\n`;
            message += `Programados: ${scheduled.length}\n\n`;

            scheduled.slice(0, 5).forEach((m) => {
                message += `📱 ${m.phone}\n`;
                message += `   Programado: ${new Date(m.scheduled_at).toLocaleString()}\n`;
                message += `   Prioridad: ${m.priority || 'normal'}\n\n`;
            });

            if (scheduled.length > 5) {
                message += `... y ${scheduled.length - 5} más\n`;
            }
        }

        message += '\n💡 Usa /api/queue/enqueue para agregar mensajes';
        showToast({ type: 'info', message });
    } catch (error) {
        showToast({ type: 'error', message: '❌ Error: ' + error.message });
    }
}

async function showWhatsAppProvider() {
    const modal = document.createElement('div');
    modal.id = 'waModal';

    SafeDOM.setHTML(modal, `
        <div class="ui-modal-overlay">
            <div class="ui-modal-dialog ui-modal-md">
                <h2 class="ui-modal-title">📱 Configuración WhatsApp Provider</h2>

                <div id="waStatus">
                    <p>Cargando estado...</p>
                </div>

                <hr class="ui-modal-separator">

                <h3>Cambiar Modo de Provider</h3>
                <div class="ui-row-gap ui-mb-20">
                    <button type="button" data-action="set-provider-mode" data-mode="web" class="ui-provider-mode-btn">
                        <strong>🌐 Web</strong><br>
                        <small>WhatsApp Web (Playwright)</small>
                    </button>
                    <button type="button" data-action="set-provider-mode" data-mode="cloud" class="ui-provider-mode-btn">
                        <strong>☁️ Cloud</strong><br>
                        <small>API Oficial de Meta</small>
                    </button>
                    <button type="button" data-action="set-provider-mode" data-mode="both" class="ui-provider-mode-btn">
                        <strong>🔄 Dual</strong><br>
                        <small>Ambos con fallback</small>
                    </button>
                </div>

                <hr class="ui-modal-separator">

                <h3>☁️ Credenciales Cloud API</h3>
                <form id="cloudCredentialsForm" class="ui-form-grid">
                    <input type="text" id="cloudPhoneId" placeholder="Phone Number ID" class="ui-input">
                    <input type="password" id="cloudToken" placeholder="Access Token" class="ui-input">
                    <input type="text" id="cloudVerifyToken" placeholder="Verify Token (para webhook)" class="ui-input">
                    <input type="text" id="cloudBusinessId" placeholder="Business Account ID (opcional)" class="ui-input">
                    <button type="submit" class="ui-btn ui-btn-success">
                        💾 Guardar Credenciales
                    </button>
                </form>

                <button type="button" data-action="close-wa-modal" class="ui-btn ui-btn-secondary ui-btn-top-gap">
                    Cerrar
                </button>
            </div>
        </div>
    `);

    modal.addEventListener('click', async (event) => {
        const target = event.target;
        if (!(target instanceof HTMLElement)) return;

        if (target.dataset.action === 'close-wa-modal') {
            closeModalById('waModal');
            return;
        }

        if (target.dataset.action === 'set-provider-mode') {
            await setProviderMode(target.dataset.mode || 'web');
        }
    });

    document.body.appendChild(modal);

    try {
        const config = await apiJson('/api/whatsapp/provider/config');
        let html = `<div class="wa-status-box">`;
        html += `<p><strong>Modo actual:</strong> <span class="wa-status-mode">${config.mode?.toUpperCase() || 'WEB'}</span></p>`;

        if (config.cloud_api?.phone_number_id) {
            html += `<p><strong>Phone ID configurado:</strong> ${config.cloud_api.phone_number_id}</p>`;
        }
        if (config.cloud_api?.access_token_masked) {
            html += `<p><strong>Token:</strong> ${config.cloud_api.access_token_masked}</p>`;
        }
        html += `</div>`;
        SafeDOM.setHTML(document.getElementById('waStatus'), html);

        if (config.cloud_api) {
            document.getElementById('cloudPhoneId').value = config.cloud_api.phone_number_id || '';
            document.getElementById('cloudVerifyToken').value = config.cloud_api.verify_token || '';
            document.getElementById('cloudBusinessId').value = config.cloud_api.business_account_id || '';
        }
    } catch (error) {
        SafeDOM.setHTML(document.getElementById('waStatus'), `<p class="ui-text-danger">Error: ${error.message}</p>`);
    }

    document.getElementById('cloudCredentialsForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        const data = {
            access_token: document.getElementById('cloudToken').value,
            phone_number_id: document.getElementById('cloudPhoneId').value,
            verify_token: document.getElementById('cloudVerifyToken').value,
            business_account_id: document.getElementById('cloudBusinessId').value,
        };

        try {
            const result = await apiJson('/api/whatsapp/cloud/credentials', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(data),
            });
            if (result.success) {
                showToast({ type: 'success', message: '✅ Credenciales guardadas exitosamente' });
                closeModalById('waModal');
                showWhatsAppProvider();
            } else {
                showToast({ type: 'error', message: '❌ Error: ' + (result.detail || result.message) });
            }
        } catch (error) {
            showToast({ type: 'error', message: '❌ Error: ' + error.message });
        }
    });
}

async function setProviderMode(mode) {
    try {
        const result = await apiJson('/api/whatsapp/provider/config', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ mode }),
        });
        if (result.success) {
            showToast({ type: 'success', message: `✅ Modo cambiado a: ${mode.toUpperCase()}` });
            closeModalById('waModal');
            showWhatsAppProvider();
        } else {
            showToast({ type: 'error', message: '❌ Error: ' + (result.detail || result.message) });
        }
    } catch (error) {
        showToast({ type: 'error', message: '❌ Error: ' + error.message });
    }
}

function logout() {
    if (window.Auth && typeof window.Auth.logout === 'function') {
        window.Auth.logout('/ui/login.html');
        return;
    }

    sessionStorage.removeItem('token');
    sessionStorage.removeItem('username');
    sessionStorage.removeItem('remember');
    window.location.href = '/ui/login.html';
}

async function updateChecklist() {
    try {
        try {
            const config = await apiJson('/api/business/config');
            const businessItem = document.getElementById('checkBusiness');

            if (config.business_info?.name && config.business_info.name !== 'Mi Negocio') {
                businessItem.className = 'checklist-item completed';
                const iconEl = businessItem.querySelector('.checklist-icon');
                iconEl.textContent = '';
                const i = document.createElement('i');
                i.className = 'fas fa-check';
                iconEl.appendChild(i);
            } else {
                businessItem.className = 'checklist-item pending';
            }
        } catch {
            // ignore
        }

        try {
            const waConfig = await apiJson('/api/whatsapp/provider/config');
            const waItem = document.getElementById('checkWhatsApp');

            if (waConfig.mode) {
                waItem.className = 'checklist-item completed';
                const iconEl = waItem.querySelector('.checklist-icon');
                iconEl.textContent = '';
                const i = document.createElement('i');
                i.className = 'fas fa-check';
                iconEl.appendChild(i);
            }
        } catch {
            // ignore
        }

        try {
            const aiConfig = await apiJson('/api/ai-models/config');
            const aiItem = document.getElementById('checkAI');

            if (aiConfig.default_provider || (aiConfig.custom_providers && aiConfig.custom_providers.length > 0)) {
                aiItem.className = 'checklist-item completed';
                const iconEl = aiItem.querySelector('.checklist-icon');
                iconEl.textContent = '';
                const i = document.createElement('i');
                i.className = 'fas fa-check';
                iconEl.appendChild(i);
            }
        } catch {
            // ignore
        }
    } catch (error) {
        console.error('Error updating checklist:', error);
    }
}

function updateBotStatus(status) {
    const botItem = document.getElementById('checkBot');
    if (status && status.bot_running) {
        botItem.className = 'checklist-item completed';
        const iconEl = botItem.querySelector('.checklist-icon');
        iconEl.textContent = '';
        const i = document.createElement('i');
        i.className = 'fas fa-check';
        iconEl.appendChild(i);
    } else {
        botItem.className = 'checklist-item pending';
    }
}

function bindDashboardActions() {
    document.getElementById('logoutBtn')?.addEventListener('click', logout);
    document.getElementById('apiManagementBtn')?.addEventListener('click', showApiManagement);
    document.getElementById('campaignsBtn')?.addEventListener('click', showCampaigns);
    document.getElementById('schedulerBtn')?.addEventListener('click', showScheduler);
    document.getElementById('providerBtn')?.addEventListener('click', showWhatsAppProvider);
    document.getElementById('startBotBtn')?.addEventListener('click', startWhatsAppBot);
    document.getElementById('testApisBtn')?.addEventListener('click', testApis);
    document.getElementById('viewLogsBtn')?.addEventListener('click', viewLogs);
}

statusInterval = setInterval(() => {
    apiJson('/api/status')
        .then((data) => {
            console.log('Estado actualizado:', data);
            updateBotStatus(data);
        })
        .catch((error) => console.log('Error actualizando estado:', error));
}, 30000);

window.addEventListener('beforeunload', () => {
    if (statusInterval) {
        clearInterval(statusInterval);
        statusInterval = null;
    }
});

document.addEventListener('DOMContentLoaded', async function () {
    if (!window.Auth || !window.Auth.requireAuth('/ui/login.html')) {
        return;
    }

    bindDashboardActions();

    const username = sessionStorage.getItem('username') || 'Usuario';
    document.getElementById('usernameDisplay').textContent = username;

    await updateChecklist();

    if (!sessionStorage.getItem('welcomed_v2')) {
        setTimeout(() => {
            const businessCheck = document.getElementById('checkBusiness');
            if (businessCheck && businessCheck.classList.contains('not-started')) {
                if (confirm('🎉 ¡Bienvenido!\n\nParece que es tu primera vez. ¿Quieres ir al asistente de configuración para empezar?')) {
                    window.location.href = '/ui/setup.html';
                }
            }
            sessionStorage.setItem('welcomed_v2', 'true');
        }, 1000);
    }
});

window.showApiManagement = showApiManagement;
window.showCampaigns = showCampaigns;
window.showScheduler = showScheduler;
window.showWhatsAppProvider = showWhatsAppProvider;
window.startWhatsAppBot = startWhatsAppBot;
window.testApis = testApis;
window.viewLogs = viewLogs;
window.deleteProvider = deleteProvider;
window.pauseCampaign = pauseCampaign;
window.resumeCampaign = resumeCampaign;
window.setProviderMode = setProviderMode;
window.logout = logout;
