let currentPeriod = 24;
let conversationsChart = null;
let apiUsageChart = null;
let realtimeInterval = null;

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

function configureCharts() {
    if (!window.Chart) {
        return;
    }
    Chart.defaults.font.family = "'Segoe UI', Tahoma, Geneva, Verdana, sans-serif";
    Chart.defaults.color = '#6c757d';
}

function changePeriod(hours, button) {
    currentPeriod = hours;

    document.querySelectorAll('.time-btn').forEach((btn) => {
        btn.classList.remove('active');
    });

    if (button) {
        button.classList.add('active');
    }

    loadAllData();
}

async function loadAllData() {
    showLoading(true);
    try {
        await Promise.all([
            loadDashboardMetrics(),
            loadTimeSeriesData(),
            loadApiProviders(),
            loadRealtimeData(),
        ]);
    } finally {
        showLoading(false);
    }
}

async function loadDashboardMetrics() {
    try {
        const data = await apiJson(`/api/analytics/dashboard?hours=${currentPeriod}`);

        document.getElementById('totalConversations').textContent = data.conversations?.total || 0;
        document.getElementById('avgMessages').textContent = data.conversations?.avg_messages || 0;

        const totalApiCalls = data.api_usage?.reduce((sum, api) => sum + (api.requests || 0), 0) || 0;
        document.getElementById('apiCalls').textContent = totalApiCalls;

        const errorRate = data.quality?.total_errors || 0;
        document.getElementById('errorRate').textContent = `${errorRate}%`;

        updateChanges(data);
    } catch (error) {
        console.error('Error cargando métricas:', error);
    }
}

async function loadTimeSeriesData() {
    try {
        const [conversationsData, apiData] = await Promise.all([
            apiJson(`/api/analytics/timeseries?metric=conversations&hours=${currentPeriod}`),
            apiJson(`/api/analytics/timeseries?metric=api_calls&hours=${currentPeriod}`),
        ]);

        updateConversationsChart(conversationsData);
        updateApiUsageChart(apiData);
    } catch (error) {
        console.error('Error cargando series temporales:', error);
    }
}

function updateConversationsChart(data) {
    const ctx = document.getElementById('conversationsChart').getContext('2d');

    if (conversationsChart) {
        conversationsChart.destroy();
    }

    const labels = data.map((d) => new Date(d.timestamp).toLocaleTimeString());
    const values = data.map((d) => d.value);

    conversationsChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels,
            datasets: [
                {
                    label: 'Conversaciones',
                    data: values,
                    borderColor: '#4facfe',
                    backgroundColor: 'rgba(79, 172, 254, 0.1)',
                    tension: 0.4,
                    fill: true,
                },
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true,
                },
            },
            plugins: {
                legend: {
                    display: false,
                },
            },
        },
    });
}

function updateApiUsageChart(data) {
    const ctx = document.getElementById('apiUsageChart').getContext('2d');

    if (apiUsageChart) {
        apiUsageChart.destroy();
    }

    const providers = ['Gemini', 'OpenAI', 'Grok', 'Claude', 'Ollama'];
    const colors = ['#4285F4', '#00A96E', '#FF6B35', '#8B5CF6', '#06B6D4'];
    const providerUsage = data?.provider_usage || {};
    const apiData = providers.map((provider, index) => ({
        label: provider,
        data: Number(providerUsage[provider]) || 0,
        backgroundColor: colors[index],
    }));

    apiUsageChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: providers,
            datasets: [
                {
                    data: apiData.map((d) => d.data),
                    backgroundColor: colors,
                },
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                },
            },
        },
    });
}

async function loadApiProviders() {
    try {
        const data = await apiJson('/api/llm/providers');

        const container = document.getElementById('apiProviders');
        container.textContent = '';

        if (data.providers) {
            data.providers.forEach((provider) => {
                const providerElement = createApiProviderElement(provider);
                container.appendChild(providerElement);
            });
            return;
        }

        const mockProviders = [
            { name: 'Gemini Pro', status: 'active', requests: 245, avgResponse: 1200, errors: 2 },
            { name: 'OpenAI GPT-4', status: 'active', requests: 189, avgResponse: 1800, errors: 0 },
            { name: 'Grok xAI', status: 'active', requests: 76, avgResponse: 2100, errors: 1 },
            { name: 'Claude Sonnet', status: 'active', requests: 45, avgResponse: 1650, errors: 0 },
            { name: 'Ollama Local', status: 'error', requests: 0, avgResponse: 0, errors: 5 },
        ];

        mockProviders.forEach((provider) => {
            const providerElement = createApiProviderElement(provider);
            container.appendChild(providerElement);
        });
    } catch (error) {
        console.error('Error cargando proveedores:', error);
    }
}

function createApiProviderElement(provider) {
    const div = document.createElement('div');
    div.className = 'api-provider';

    const apiInfo = document.createElement('div');
    apiInfo.className = 'api-info';

    const status = document.createElement('div');
    status.className = `api-status ${provider.status}`;

    const nameWrap = document.createElement('div');
    const strongName = document.createElement('strong');
    strongName.textContent = provider.name || 'Unknown';
    nameWrap.appendChild(strongName);

    apiInfo.appendChild(status);
    apiInfo.appendChild(nameWrap);

    const metrics = document.createElement('div');
    metrics.className = 'api-metrics';

    const req = document.createElement('span');
    req.textContent = `${provider.requests || 0} requests`;
    const avg = document.createElement('span');
    avg.textContent = `${provider.avgResponse || 0}ms avg`;
    const err = document.createElement('span');
    err.textContent = `${provider.errors || 0} errors`;

    metrics.appendChild(req);
    metrics.appendChild(avg);
    metrics.appendChild(err);

    div.appendChild(apiInfo);
    div.appendChild(metrics);
    return div;
}

async function loadRealtimeData() {
    try {
        const data = await apiJson('/api/analytics/realtime');

        if (data.last_5_minutes) {
            document.getElementById('realtimeConversations').textContent = data.last_5_minutes.new_conversations || 0;
            document.getElementById('realtimeApiCalls').textContent = data.last_5_minutes.api_calls || 0;
            document.getElementById('realtimeErrors').textContent = data.last_5_minutes.errors || 0;
        }
    } catch (error) {
        console.error('Error cargando datos en tiempo real:', error);
        document.getElementById('realtimeConversations').textContent = 'N/A';
        document.getElementById('realtimeApiCalls').textContent = 'N/A';
        document.getElementById('realtimeErrors').textContent = 'N/A';
    }
}

function updateChanges(data) {
    const delta = data?.changes || {};
    const formatPct = (value) => (typeof value === 'number' ? `${value >= 0 ? '+' : ''}${value}%` : 'N/A');

    document.getElementById('conversationsChange').textContent = formatPct(delta.conversations);
    document.getElementById('messagesChange').textContent = formatPct(delta.messages);
    document.getElementById('apiChange').textContent = formatPct(delta.api_calls);
    document.getElementById('errorChange').textContent = formatPct(delta.errors);
}

function showLoading(show) {
    const overlay = document.getElementById('loadingOverlay');
    if (!overlay) {
        return;
    }
    overlay.classList.toggle('hidden', !show);
}

function bindEvents() {
    document.querySelectorAll('.time-btn').forEach((btn) => {
        btn.addEventListener('click', () => {
            const hours = Number(btn.dataset.hours || 24);
            changePeriod(hours, btn);
        });
    });

    const refreshBtn = document.getElementById('refreshRealtimeBtn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', () => {
            loadRealtimeData();
        });
    }
}

document.addEventListener('DOMContentLoaded', () => {
    if (!window.Auth || !window.Auth.requireAuth('/ui/login.html')) {
        return;
    }

    configureCharts();
    bindEvents();
    loadAllData();

    realtimeInterval = setInterval(loadRealtimeData, 30000);
});

window.addEventListener('beforeunload', () => {
    if (realtimeInterval) {
        clearInterval(realtimeInterval);
        realtimeInterval = null;
    }
});
