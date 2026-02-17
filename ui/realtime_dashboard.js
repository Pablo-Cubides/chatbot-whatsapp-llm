let ws = null;
let reconnectInterval = null;
let pingInterval = null;

async function getMetricsWsToken() {
    if (!window.Api || !window.Auth) {
        return '';
    }

    const accessToken = window.Auth.getToken();
    if (!accessToken) {
        const refreshed = await window.Auth.refreshAccessToken();
        if (!refreshed) {
            return '';
        }
    }

    try {
        const payload = await window.Api.json('/api/auth/ws-token', {
            method: 'POST',
        });
        return payload.ws_token || '';
    } catch {
        return '';
    }
}

function setVisibility(elementId, show) {
    const element = document.getElementById(elementId);
    if (!element) {
        return;
    }
    element.classList.toggle('hidden', !show);
}

async function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host || 'localhost:8003';
    const token = await getMetricsWsToken();

    if (!token) {
        updateConnectionStatus(false);
        setVisibility('loadingMsg', true);
        const loadingMsg = document.getElementById('loadingMsg');
        if (loadingMsg) {
            loadingMsg.textContent = 'Sesión requerida. Inicia sesión para ver métricas.';
        }
        return;
    }

    ws = new WebSocket(`${protocol}//${host}/ws/metrics`);

    ws.onopen = () => {
        ws.send(JSON.stringify({
            type: 'auth',
            token,
        }));

        console.log('✅ WebSocket conectado');
        updateConnectionStatus(true);
        setVisibility('loadingMsg', false);
        setVisibility('metricsContent', true);

        if (reconnectInterval) {
            clearInterval(reconnectInterval);
            reconnectInterval = null;
        }

        if (pingInterval) {
            clearInterval(pingInterval);
            pingInterval = null;
        }

        pingInterval = setInterval(() => {
            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send('ping');
            }
        }, 30000);
    };

    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);

        if (data.type === 'snapshot' || data.type === 'update') {
            updateMetrics(data.data);
            updateLastUpdate(data.timestamp);
        } else if (data.type === 'metrics') {
            const queuePendingEl = document.getElementById('queuePending');
            if (queuePendingEl) {
                queuePendingEl.textContent = String(data.queue_pending ?? 0);
            }
            updateLastUpdate(data.timestamp);
        }
    };

    ws.onerror = (error) => {
        console.error('❌ Error WebSocket:', error);
        updateConnectionStatus(false);
    };

    ws.onclose = () => {
        console.log('🔌 WebSocket desconectado');
        updateConnectionStatus(false);

        if (pingInterval) {
            clearInterval(pingInterval);
            pingInterval = null;
        }

        if (!reconnectInterval) {
            reconnectInterval = setInterval(() => {
                console.log('🔄 Intentando reconectar...');
                connectWebSocket();
            }, 5000);
        }
    };
}

function updateConnectionStatus(connected) {
    const indicator = document.getElementById('statusIndicator');
    const text = document.getElementById('statusText');

    if (!indicator || !text) {
        return;
    }

    if (connected) {
        indicator.className = 'status-indicator connected';
        text.textContent = 'Conectado';
    } else {
        indicator.className = 'status-indicator disconnected';
        text.textContent = 'Desconectado';
    }
}

function updateMetrics(data) {
    const overview = data.overview || {};
    document.getElementById('conversationsLastHour').textContent = overview.conversations_last_hour || 0;
    document.getElementById('messagesLastHour').textContent = overview.messages_last_hour || 0;
    document.getElementById('avgResponseTime').textContent = `${overview.avg_response_time || 0}s`;
    document.getElementById('errorsLastHour').textContent = overview.errors_last_hour || 0;

    if (data.charts) {
        updateBarChart('conversationsChart', data.charts.hourly_conversations || []);
        updateBarChart('messagesChart', data.charts.hourly_messages || []);
    }

    if (data.llm_usage) {
        updateLLMUsage(data.llm_usage);
    }

    if (data.humanization_events) {
        updateHumanizationEvents(data.humanization_events);
    }

    if (data.response_times_distribution) {
        updateResponseTimesChart(data.response_times_distribution);
    }
}

function updateBarChart(elementId, data) {
    const container = document.getElementById(elementId);
    if (!container) {
        return;
    }

    container.textContent = '';
    const maxValue = Math.max(...data.map((d) => d.count), 1);

    data.forEach((item) => {
        const bar = document.createElement('div');
        bar.className = 'bar';
        const heightPercent = (item.count / maxValue) * 100;
        bar.style.setProperty('--bar-height', `${heightPercent}%`);

        const label = document.createElement('div');
        label.className = 'bar-label';
        label.textContent = item.hour;
        bar.appendChild(label);

        if (item.count > 0) {
            const value = document.createElement('div');
            value.className = 'bar-value';
            value.textContent = item.count;
            bar.appendChild(value);
        }

        container.appendChild(bar);
    });
}

function updateLLMUsage(usage) {
    const container = document.getElementById('llmUsageGrid');
    if (!container) {
        return;
    }

    container.textContent = '';
    const entries = Object.entries(usage);

    if (entries.length === 0) {
        const card = document.createElement('div');
        card.className = 'llm-card';
        const name = document.createElement('div');
        name.className = 'llm-name';
        name.textContent = 'Sin datos';
        const count = document.createElement('div');
        count.className = 'llm-count';
        count.textContent = '0';
        card.appendChild(name);
        card.appendChild(count);
        container.appendChild(card);
        return;
    }

    entries.forEach(([provider, count]) => {
        const card = document.createElement('div');
        card.className = 'llm-card';
        const name = document.createElement('div');
        name.className = 'llm-name';
        name.textContent = provider;
        const value = document.createElement('div');
        value.className = 'llm-count';
        value.textContent = String(count);
        card.appendChild(name);
        card.appendChild(value);
        container.appendChild(card);
    });
}

function updateHumanizationEvents(events) {
    const container = document.getElementById('humanizationEvents');
    if (!container) {
        return;
    }

    container.textContent = '';
    const entries = Object.entries(events);

    if (entries.length === 0) {
        const span = document.createElement('span');
        span.className = 'muted-text';
        span.textContent = 'Sin eventos';
        container.appendChild(span);
        return;
    }

    entries.forEach(([eventType, count]) => {
        const badge = document.createElement('div');
        badge.className = 'event-badge';
        badge.textContent = `${eventType}: ${count}`;
        container.appendChild(badge);
    });
}

function updateResponseTimesChart(distribution) {
    const container = document.getElementById('responseTimesChart');
    if (!container) {
        return;
    }

    const data = Object.entries(distribution).map(([range, count]) => ({
        hour: range,
        count,
    }));

    updateBarChart('responseTimesChart', data);
}

function updateLastUpdate(timestamp) {
    const lastUpdate = document.getElementById('lastUpdate');
    if (!lastUpdate) {
        return;
    }

    const date = new Date(timestamp);
    lastUpdate.textContent = `Última actualización: ${date.toLocaleTimeString('es-ES')}`;
}

document.addEventListener('DOMContentLoaded', () => {
    if (window.Auth && window.Auth.requireAuth('/ui/login.html')) {
        connectWebSocket();
    }
});

window.addEventListener('beforeunload', () => {
    if (reconnectInterval) {
        clearInterval(reconnectInterval);
        reconnectInterval = null;
    }
    if (pingInterval) {
        clearInterval(pingInterval);
        pingInterval = null;
    }
});
