const API_BASE = '';
let currentProvider = null;
let calendarStatus = {};

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

async function loadCalendarStatus() {
    try {
        calendarStatus = await apiJson(`${API_BASE}/api/calendar/status`);
        updateStatusUI();
    } catch (error) {
        console.error('Error loading calendar status:', error);
    }
}

async function loadCurrentConfig() {
    try {
        const config = await apiJson(`${API_BASE}/api/calendar/config`);
        applyConfigToUI(config);
    } catch (error) {
        console.error('Error loading config:', error);
    }
}

function applyConfigToUI(config) {
    if (!config) return;

    if (config.provider) {
        selectProvider(config.provider);
    }

    const days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'];
    const workingHours = config.working_hours || {};

    days.forEach(day => {
        const dayConfig = workingHours[day] || {};
        if (dayConfig.start) document.getElementById(`${day}_start`).value = dayConfig.start;
        if (dayConfig.end) document.getElementById(`${day}_end`).value = dayConfig.end;
        document.getElementById(`${day}_closed`).checked = dayConfig.closed || false;
    });

    if (config.default_duration_minutes) {
        document.getElementById('defaultDuration').value = config.default_duration_minutes;
    }
    if (config.buffer_between_appointments !== undefined) {
        document.getElementById('bufferTime').value = config.buffer_between_appointments;
    }

    document.getElementById('appointmentsEnabled').checked = config.enabled || false;

    if (config.google_calendar) {
        document.getElementById('googleCalendarId').value = config.google_calendar.calendar_id || 'primary';
        document.getElementById('googleNotifications').checked = config.google_calendar.send_notifications !== false;
        document.getElementById('googleMeet').checked = config.google_calendar.add_google_meet !== false;
    }

    if (config.outlook) {
        document.getElementById('outlookClientId').value = config.outlook.client_id || '';
        document.getElementById('outlookTenantId').value = config.outlook.tenant_id || 'common';
        document.getElementById('outlookTeams').checked = config.outlook.add_teams_meeting !== false;
    }
}

function updateStatusUI() {
    const banner = document.getElementById('statusBanner');

    if (calendarStatus.is_ready) {
        banner.className = 'status-banner status-connected';
        SafeDOM.setHTML(banner, `
            <i class="fas fa-check-circle status-icon-large"></i>
            <div>
                <strong>✅ Calendario conectado</strong>
                <p>Proveedor activo: ${calendarStatus.active_provider}</p>
            </div>
        `);

        if (calendarStatus.active_provider === 'google_calendar') {
            document.getElementById('googleCard').classList.add('connected');
            document.getElementById('googleStatus').textContent = '✅ Conectado';
            document.getElementById('googleStatus').classList.add('connected');
        } else if (calendarStatus.active_provider === 'outlook') {
            document.getElementById('outlookCard').classList.add('connected');
            document.getElementById('outlookStatus').textContent = '✅ Conectado';
            document.getElementById('outlookStatus').classList.add('connected');
        }
    }
}

function selectProvider(provider) {
    currentProvider = provider;

    document.querySelectorAll('.provider-card').forEach(card => {
        card.classList.remove('selected');
    });

    const googleSetup = document.getElementById('googleSetup');
    const outlookSetup = document.getElementById('outlookSetup');

    if (provider === 'google_calendar') {
        document.getElementById('googleCard').classList.add('selected');
        googleSetup.classList.remove('hidden');
        outlookSetup.classList.add('hidden');
    } else if (provider === 'outlook') {
        document.getElementById('outlookCard').classList.add('selected');
        outlookSetup.classList.remove('hidden');
        googleSetup.classList.add('hidden');
    }
}

function setupFileUpload() {
    const uploadArea = document.getElementById('googleCredentialsUpload');
    const fileInput = document.getElementById('googleCredentialsFile');

    uploadArea.addEventListener('click', () => fileInput.click());

    uploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadArea.classList.add('dragover');
    });

    uploadArea.addEventListener('dragleave', () => {
        uploadArea.classList.remove('dragover');
    });

    uploadArea.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadArea.classList.remove('dragover');
        const file = e.dataTransfer.files[0];
        if (file) handleGoogleCredentialsFile(file);
    });

    fileInput.addEventListener('change', (e) => {
        if (e.target.files[0]) handleGoogleCredentialsFile(e.target.files[0]);
    });
}

async function handleGoogleCredentialsFile(file) {
    const formData = new FormData();
    formData.append('credentials', file);

    try {
        const response = await apiRequest(`${API_BASE}/api/calendar/google/credentials`, {
            method: 'POST',
            body: formData
        });

        if (response.ok) {
            await response.json();
            alert('✅ Credenciales cargadas correctamente. Ahora haz clic en "Autorizar Acceso".');
            SafeDOM.setHTML(document.getElementById('googleCredentialsUpload'), `
                <i class="fas fa-check-circle icon-success"></i>
                <p>✅ Archivo cargado: ${file.name}</p>
            `);
        } else {
            const error = await response.json();
            alert('❌ Error: ' + (error.detail || 'No se pudo cargar el archivo'));
        }
    } catch (error) {
        alert('❌ Error de conexión: ' + error.message);
    }
}

async function authorizeGoogle() {
    try {
        const data = await apiJson(`${API_BASE}/api/calendar/oauth/google/authorize`);
        window.open(data.authorization_url, 'GoogleAuth', 'width=600,height=700');
        alert('Se abrió una ventana para autorizar el acceso a Google Calendar. Completa el proceso y luego regresa aquí.');
    } catch (error) {
        alert('❌ Error: ' + error.message);
    }
}

async function authorizeOutlook() {
    await saveOutlookConfig();

    try {
        const data = await apiJson(`${API_BASE}/api/calendar/oauth/outlook/authorize`);
        window.open(data.authorization_url, 'OutlookAuth', 'width=600,height=700');
        alert('Se abrió una ventana para autorizar el acceso a Outlook. Completa el proceso y luego regresa aquí.');
    } catch (error) {
        alert('❌ Error: ' + error.message);
    }
}

async function saveGoogleConfig() {
    const config = {
        provider: 'google_calendar',
        google_calendar: {
            calendar_id: document.getElementById('googleCalendarId').value || 'primary',
            send_notifications: document.getElementById('googleNotifications').checked,
            add_google_meet: document.getElementById('googleMeet').checked
        }
    };

    await saveConfig(config);
}

async function saveOutlookConfig() {
    const config = {
        provider: 'outlook',
        outlook: {
            client_id: document.getElementById('outlookClientId').value,
            client_secret: document.getElementById('outlookClientSecret').value,
            tenant_id: document.getElementById('outlookTenantId').value || 'common',
            add_teams_meeting: document.getElementById('outlookTeams').checked
        }
    };

    await saveConfig(config);
}

async function saveWorkingHours() {
    const days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'];
    const working_hours = {};

    days.forEach(day => {
        const closed = document.getElementById(`${day}_closed`).checked;
        if (closed) {
            working_hours[day] = { closed: true };
        } else {
            working_hours[day] = {
                start: document.getElementById(`${day}_start`).value,
                end: document.getElementById(`${day}_end`).value
            };
        }
    });

    const config = {
        working_hours,
        default_duration_minutes: parseInt(document.getElementById('defaultDuration').value),
        buffer_between_appointments: parseInt(document.getElementById('bufferTime').value)
    };

    await saveConfig(config);
}

async function toggleAppointments() {
    const config = {
        enabled: document.getElementById('appointmentsEnabled').checked
    };

    await saveConfig(config);
}

async function saveConfig(config) {
    try {
        await apiJson(`${API_BASE}/api/calendar/config`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config)
        });

        alert('✅ Configuración guardada correctamente');
        await loadCalendarStatus();
    } catch (error) {
        alert('❌ Error de conexión: ' + error.message);
    }
}

function connectGoogle() {
    selectProvider('google_calendar');
}

function connectOutlook() {
    selectProvider('outlook');
}

function setupEventHandlers() {
    document.querySelectorAll('.provider-card[data-provider]').forEach((card) => {
        card.addEventListener('click', () => {
            const provider = card.getAttribute('data-provider');
            if (provider) {
                selectProvider(provider);
            }
        });
    });

    const connectGoogleBtn = document.getElementById('connectGoogleBtn');
    const connectOutlookBtn = document.getElementById('connectOutlookBtn');
    const saveGoogleConfigBtn = document.getElementById('saveGoogleConfigBtn');
    const authorizeGoogleBtn = document.getElementById('authorizeGoogleBtn');
    const saveOutlookConfigBtn = document.getElementById('saveOutlookConfigBtn');
    const authorizeOutlookBtn = document.getElementById('authorizeOutlookBtn');
    const saveWorkingHoursBtn = document.getElementById('saveWorkingHoursBtn');
    const toggleAppointmentsBtn = document.getElementById('toggleAppointmentsBtn');

    if (connectGoogleBtn) {
        connectGoogleBtn.addEventListener('click', (event) => {
            event.stopPropagation();
            connectGoogle();
        });
    }
    if (connectOutlookBtn) {
        connectOutlookBtn.addEventListener('click', (event) => {
            event.stopPropagation();
            connectOutlook();
        });
    }
    if (saveGoogleConfigBtn) saveGoogleConfigBtn.addEventListener('click', saveGoogleConfig);
    if (authorizeGoogleBtn) authorizeGoogleBtn.addEventListener('click', authorizeGoogle);
    if (saveOutlookConfigBtn) saveOutlookConfigBtn.addEventListener('click', saveOutlookConfig);
    if (authorizeOutlookBtn) authorizeOutlookBtn.addEventListener('click', authorizeOutlook);
    if (saveWorkingHoursBtn) saveWorkingHoursBtn.addEventListener('click', saveWorkingHours);
    if (toggleAppointmentsBtn) toggleAppointmentsBtn.addEventListener('click', toggleAppointments);
}

document.addEventListener('DOMContentLoaded', async function() {
    if (!window.Auth || !window.Auth.requireAuth('/ui/login.html')) {
        return;
    }

    setupEventHandlers();
    await loadCalendarStatus();
    await loadCurrentConfig();
    setupFileUpload();
});
