let currentAlertId = null;
let refreshInterval = null;

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

function bindEvents() {
    const applyBtn = document.getElementById('applyFiltersBtn');
    if (applyBtn) {
        applyBtn.addEventListener('click', () => {
            loadAlerts();
        });
    }

    const cancelAssignBtn = document.getElementById('cancelAssignBtn');
    if (cancelAssignBtn) {
        cancelAssignBtn.addEventListener('click', () => {
            closeModal('assignModal');
        });
    }

    const confirmAssignBtn = document.getElementById('confirmAssignBtn');
    if (confirmAssignBtn) {
        confirmAssignBtn.addEventListener('click', () => {
            confirmAssign();
        });
    }

    const cancelResolveBtn = document.getElementById('cancelResolveBtn');
    if (cancelResolveBtn) {
        cancelResolveBtn.addEventListener('click', () => {
            closeModal('resolveModal');
        });
    }

    const confirmResolveBtn = document.getElementById('confirmResolveBtn');
    if (confirmResolveBtn) {
        confirmResolveBtn.addEventListener('click', () => {
            confirmResolve();
        });
    }
}

async function loadStats() {
    try {
        const alerts = await apiJson('/api/alerts?limit=1000');

        const total = alerts.length;
        const open = alerts.filter((a) => a.status === 'open').length;
        const assigned = alerts.filter((a) => a.status === 'assigned').length;

        const today = new Date().toISOString().split('T')[0];
        const resolvedToday = alerts.filter(
            (a) => a.status === 'resolved' && a.resolved_at && a.resolved_at.startsWith(today),
        ).length;

        document.getElementById('totalAlerts').textContent = total;
        document.getElementById('openAlerts').textContent = open;
        document.getElementById('assignedAlerts').textContent = assigned;
        document.getElementById('resolvedToday').textContent = resolvedToday;
    } catch (error) {
        console.error('Error loading stats:', error);
    }
}

function renderEmptyState(messageTitle, messageText, addRetry = false) {
    const container = document.getElementById('alertsContainer');
    SafeDOM.clear(container);

    const wrapper = document.createElement('div');
    wrapper.className = 'empty-state';

    const title = document.createElement('h2');
    title.textContent = messageTitle;
    const text = document.createElement('p');
    text.textContent = messageText;

    wrapper.appendChild(title);
    wrapper.appendChild(text);

    if (addRetry) {
        const retryBtn = document.createElement('button');
        retryBtn.className = 'btn btn-primary';
        retryBtn.type = 'button';
        retryBtn.textContent = 'Reintentar';
        retryBtn.addEventListener('click', () => {
            loadAlerts();
        });
        wrapper.appendChild(retryBtn);
    }

    container.appendChild(wrapper);
}

async function loadAlerts() {
    const container = document.getElementById('alertsContainer');
    SafeDOM.setHTML(container, '<div class="loading">Cargando alertas...</div>');

    try {
        const params = new URLSearchParams();
        const status = document.getElementById('filterStatus').value;
        const severity = document.getElementById('filterSeverity').value;
        const chatId = document.getElementById('filterChatId').value;

        if (status) {
            params.append('status', status);
        }
        if (severity) {
            params.append('severity', severity);
        }
        if (chatId) {
            params.append('chat_id', chatId);
        }
        params.append('limit', '100');

        const alerts = await apiJson(`/api/alerts?${params.toString()}`);

        if (alerts.length === 0) {
            renderEmptyState('No hay alertas', 'No se encontraron alertas con los filtros seleccionados.');
            return;
        }

        SafeDOM.clear(container);
        const grid = document.createElement('div');
        grid.className = 'alerts-grid';
        alerts.forEach((alert) => {
            grid.appendChild(createAlertCard(alert));
        });
        container.appendChild(grid);
    } catch (error) {
        console.error('Error:', error);
        renderEmptyState('Error al cargar alertas', error.message, true);
    }
}

function createAlertCard(alert) {
    const severityClass = alert.severity || 'low';
    const statusClass = alert.status || 'open';

    const card = document.createElement('div');
    card.className = `alert-card ${severityClass}`;

    const header = document.createElement('div');
    header.className = 'alert-header';

    const alertId = document.createElement('span');
    alertId.className = 'alert-id';
    alertId.textContent = String(alert.alert_id || '-');

    const badgesWrap = document.createElement('div');
    const sevBadge = document.createElement('span');
    sevBadge.className = `severity-badge ${severityClass}`;
    sevBadge.textContent = String(alert.severity || 'low');
    const statusBadge = document.createElement('span');
    statusBadge.className = `status-badge ${statusClass}`;
    statusBadge.textContent = translateStatus(alert.status);
    badgesWrap.appendChild(sevBadge);
    badgesWrap.appendChild(statusBadge);

    header.appendChild(alertId);
    header.appendChild(badgesWrap);
    card.appendChild(header);

    const message = document.createElement('div');
    message.className = 'alert-message';
    message.textContent = String(alert.message_text || 'Sin mensaje');
    card.appendChild(message);

    const meta = document.createElement('div');
    meta.className = 'alert-meta';
    const addMetaItem = (label, value) => {
        const item = document.createElement('div');
        item.className = 'alert-meta-item';
        const labelEl = document.createElement('span');
        labelEl.className = 'alert-meta-label';
        labelEl.textContent = label;
        const valueEl = document.createElement('span');
        valueEl.textContent = String(value || '-');
        item.appendChild(labelEl);
        item.appendChild(valueEl);
        meta.appendChild(item);
    };

    addMetaItem('Chat ID', alert.chat_id);
    addMetaItem('Creada', formatDate(alert.created_at));
    if (alert.assigned_to) {
        addMetaItem('Asignada a', alert.assigned_to);
    }
    if (alert.resolved_at) {
        addMetaItem('Resuelta', formatDate(alert.resolved_at));
    }
    card.appendChild(meta);

    if (alert.resolved_notes) {
        const notes = document.createElement('div');
        notes.className = 'alert-message resolved-notes';

        const title = document.createElement('strong');
        title.textContent = 'Notas de resolución:';
        const br = document.createElement('br');
        const text = document.createTextNode(String(alert.resolved_notes));
        notes.appendChild(title);
        notes.appendChild(br);
        notes.appendChild(text);
        card.appendChild(notes);
    }

    const actions = document.createElement('div');
    actions.className = 'alert-actions';

    if (alert.status === 'open' || alert.status === 'assigned') {
        const assignBtn = document.createElement('button');
        assignBtn.className = 'btn btn-primary btn-sm';
        assignBtn.type = 'button';
        assignBtn.textContent = '👤 Asignar';
        assignBtn.addEventListener('click', () => openAssignModal(String(alert.alert_id || '')));
        actions.appendChild(assignBtn);

        const resolveBtn = document.createElement('button');
        resolveBtn.className = 'btn btn-success btn-sm';
        resolveBtn.type = 'button';
        resolveBtn.textContent = '✓ Resolver';
        resolveBtn.addEventListener('click', () => openResolveModal(String(alert.alert_id || '')));
        actions.appendChild(resolveBtn);
    }

    const viewBtn = document.createElement('button');
    viewBtn.className = 'btn btn-sm';
    viewBtn.type = 'button';
    viewBtn.textContent = '💬 Ver Chat';
    viewBtn.addEventListener('click', () => viewChat(String(alert.chat_id || '')));
    actions.appendChild(viewBtn);

    card.appendChild(actions);
    return card;
}

function translateStatus(status) {
    const translations = {
        open: 'Abierta',
        assigned: 'Asignada',
        resolved: 'Resuelta',
    };
    return translations[status] || status;
}

function formatDate(dateStr) {
    if (!dateStr) {
        return '-';
    }

    const date = new Date(dateStr);
    return date.toLocaleString('es-ES', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
    });
}

function openAssignModal(alertId) {
    currentAlertId = alertId;
    document.getElementById('assignModal').classList.add('active');
}

function openResolveModal(alertId) {
    currentAlertId = alertId;
    document.getElementById('resolveModal').classList.add('active');
}

function closeModal(modalId) {
    document.getElementById(modalId).classList.remove('active');
    currentAlertId = null;
}

async function confirmAssign() {
    const assignTo = document.getElementById('assignTo').value.trim();

    if (!assignTo) {
        alert('Por favor ingresa un usuario');
        return;
    }

    try {
        await apiJson(`/api/alerts/${currentAlertId}/assign`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ assigned_to: assignTo }),
        });

        alert('Alerta asignada exitosamente');
        closeModal('assignModal');
        loadAlerts();
        loadStats();
    } catch (error) {
        alert(`Error: ${error.message}`);
    }
}

async function confirmResolve() {
    const notes = document.getElementById('resolveNotes').value.trim();

    if (!notes) {
        alert('Por favor ingresa notas de resolución');
        return;
    }

    try {
        await apiJson(`/api/alerts/${currentAlertId}/resolve`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ notes }),
        });

        alert('Alerta resuelta exitosamente');
        closeModal('resolveModal');
        loadAlerts();
        loadStats();
    } catch (error) {
        alert(`Error: ${error.message}`);
    }
}

function viewChat(chatId) {
    window.location.href = `chat.html?chat_id=${chatId}`;
}

document.addEventListener('DOMContentLoaded', () => {
    if (!window.Auth || !window.Auth.requireAuth('/ui/login.html')) {
        return;
    }

    bindEvents();
    loadAlerts();
    loadStats();

    refreshInterval = setInterval(() => {
        loadAlerts();
        loadStats();
    }, 30000);
});

window.addEventListener('beforeunload', () => {
    if (refreshInterval) {
        clearInterval(refreshInterval);
        refreshInterval = null;
    }
});
