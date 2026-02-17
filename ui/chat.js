let websocket = null;
let sessionId = null;
let messageCount = 0;
let lastResponseTime = 0;
let isConnected = false;

function generateSessionId() {
    return 'chat_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
}

async function connectChat() {
    if (isConnected) return;

    sessionId = generateSessionId();
    document.getElementById('sessionId').textContent = sessionId;

    try {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/chat/${sessionId}`;

        websocket = new WebSocket(wsUrl);

        websocket.onopen = function() {
            isConnected = true;
            updateConnectionStatus(true);
            addSystemMessage('Conectado al chat de prueba. ¡Escribe tu primer mensaje!');

            document.getElementById('messageInput').disabled = false;
            document.getElementById('sendBtn').disabled = false;
        };

        websocket.onmessage = function(event) {
            const data = JSON.parse(event.data);
            handleIncomingMessage(data);
        };

        websocket.onclose = function() {
            isConnected = false;
            updateConnectionStatus(false);
            addSystemMessage('Desconectado del chat');

            document.getElementById('messageInput').disabled = true;
            document.getElementById('sendBtn').disabled = true;
        };

        websocket.onerror = function(error) {
            console.error('Error WebSocket:', error);
            addSystemMessage('Error de conexión');
        };

    } catch (error) {
        console.error('Error conectando:', error);
        addSystemMessage('Error al conectar: ' + error.message);
    }
}

function disconnectChat() {
    if (websocket) {
        websocket.close();
    }
}

function sendMessage() {
    const input = document.getElementById('messageInput');
    const message = input.value.trim();

    if (!message || !isConnected) return;

    const messageData = {
        type: 'user_message',
        message: message,
        timestamp: new Date().toISOString()
    };

    websocket.send(JSON.stringify(messageData));
    input.value = '';

    addUserMessage(message);

    messageCount++;
    document.getElementById('messageCount').textContent = messageCount;
    updateLastActivity();
}

function handleIncomingMessage(data) {
    const startTime = Date.now();

    switch (data.type) {
        case 'system':
            addSystemMessage(data.message);
            break;
        case 'bot_message':
            removeBotTyping();
            addBotMessage(data.message);
            lastResponseTime = startTime - new Date(data.timestamp).getTime();
            document.getElementById('responseTime').textContent = Math.abs(lastResponseTime) + 'ms';
            break;
        case 'typing':
            showBotTyping();
            break;
        case 'user_message':
            break;
        case 'error':
            addSystemMessage('Error: ' + data.message);
            break;
    }

    updateLastActivity();
}

function addUserMessage(message) {
    const messagesContainer = document.getElementById('chatMessages');
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message user';

    const textNode = document.createTextNode(message ?? '');
    const timeDiv = document.createElement('div');
    timeDiv.className = 'message-time';
    timeDiv.textContent = new Date().toLocaleTimeString();

    messageDiv.appendChild(textNode);
    messageDiv.appendChild(timeDiv);
    messagesContainer.appendChild(messageDiv);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

function addBotMessage(message) {
    const messagesContainer = document.getElementById('chatMessages');
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message bot';

    const textNode = document.createTextNode(message ?? '');
    const timeDiv = document.createElement('div');
    timeDiv.className = 'message-time';
    timeDiv.textContent = new Date().toLocaleTimeString();

    messageDiv.appendChild(textNode);
    messageDiv.appendChild(timeDiv);
    messagesContainer.appendChild(messageDiv);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

function addSystemMessage(message) {
    const messagesContainer = document.getElementById('chatMessages');
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message system';

    const textNode = document.createTextNode(message ?? '');
    const timeDiv = document.createElement('div');
    timeDiv.className = 'message-time';
    timeDiv.textContent = new Date().toLocaleTimeString();

    messageDiv.appendChild(textNode);
    messageDiv.appendChild(timeDiv);
    messagesContainer.appendChild(messageDiv);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

function showBotTyping() {
    removeBotTyping();

    const messagesContainer = document.getElementById('chatMessages');
    const typingDiv = document.createElement('div');
    typingDiv.className = 'message typing';
    typingDiv.id = 'typing-indicator';
    const icon = document.createElement('i');
    icon.className = 'fas fa-robot';
    typingDiv.appendChild(icon);
    typingDiv.appendChild(document.createTextNode(' Escribiendo'));

    const dotsWrap = document.createElement('div');
    dotsWrap.className = 'typing-indicator';
    for (let i = 0; i < 3; i += 1) {
        const dot = document.createElement('div');
        dot.className = 'typing-dot';
        dotsWrap.appendChild(dot);
    }
    typingDiv.appendChild(dotsWrap);
    messagesContainer.appendChild(typingDiv);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

function removeBotTyping() {
    const typingIndicator = document.getElementById('typing-indicator');
    if (typingIndicator) {
        typingIndicator.remove();
    }
}

function updateConnectionStatus(connected) {
    const statusIndicator = document.getElementById('connectionStatus');
    const statusText = document.getElementById('statusText');

    if (connected) {
        statusIndicator.className = 'status-indicator status-online';
        statusText.textContent = 'Conectado';
    } else {
        statusIndicator.className = 'status-indicator status-offline';
        statusText.textContent = 'Desconectado';
    }
}

function updateLastActivity() {
    document.getElementById('lastActivity').textContent = new Date().toLocaleTimeString();
}

function clearChat() {
    document.getElementById('chatMessages').textContent = '';
    messageCount = 0;
    document.getElementById('messageCount').textContent = '0';
    if (isConnected) {
        addSystemMessage('Chat limpiado');
    }
}

function sendSampleMessage() {
    if (!isConnected) {
        addSystemMessage('Conecta primero al chat');
        return;
    }

    const sampleMessages = [
        '¡Hola! ¿Cómo están?',
        '¿Cuáles son sus horarios de atención?',
        'Me interesa conocer más sobre sus servicios',
        '¿Cuánto cuesta sus productos?',
        '¿Pueden ayudarme con información de contacto?'
    ];

    const randomMessage = sampleMessages[Math.floor(Math.random() * sampleMessages.length)];
    document.getElementById('messageInput').value = randomMessage;
    sendMessage();
}

function handleKeyPress(event) {
    if (event.key === 'Enter') {
        sendMessage();
    }
}

async function loadBusinessConfig() {
    try {
        if (!window.Api || typeof window.Api.json !== 'function') {
            throw new Error('API runtime no disponible');
        }
        const config = await window.Api.json('/api/business/config');
        const businessName = config.business_info?.name || 'Mi Negocio';
        document.getElementById('businessName').textContent = businessName;
    } catch (error) {
        console.error('Error cargando configuración:', error);
        document.getElementById('businessName').textContent = 'No configurado';
    }
}

function setupEventHandlers() {
    const connectBtn = document.getElementById('connectBtn');
    const clearBtn = document.getElementById('clearBtn');
    const sampleBtn = document.getElementById('sampleBtn');
    const disconnectBtn = document.getElementById('disconnectBtn');
    const sendBtn = document.getElementById('sendBtn');
    const messageInput = document.getElementById('messageInput');

    if (connectBtn) connectBtn.addEventListener('click', connectChat);
    if (clearBtn) clearBtn.addEventListener('click', clearChat);
    if (sampleBtn) sampleBtn.addEventListener('click', sendSampleMessage);
    if (disconnectBtn) disconnectBtn.addEventListener('click', disconnectChat);
    if (sendBtn) sendBtn.addEventListener('click', sendMessage);
    if (messageInput) messageInput.addEventListener('keypress', handleKeyPress);
}

document.addEventListener('DOMContentLoaded', function() {
    if (!window.Auth || !window.Auth.requireAuth('/ui/login.html')) {
        return;
    }

    setupEventHandlers();
    loadBusinessConfig();

    setTimeout(() => {
        addSystemMessage('Presiona "Conectar" para iniciar el chat de prueba');
    }, 500);
});
