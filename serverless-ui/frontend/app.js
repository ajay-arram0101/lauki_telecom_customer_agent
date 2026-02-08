// ============================================================
// Quaki Customer Support - Frontend Application
// ============================================================

// Configuration
const CONFIG = {
    // Lambda Function URL - no API Gateway timeout limit
    API_URL: 'https://bpnsxjngngyquxzzq36kit3h7q0serqe.lambda-url.us-east-2.on.aws/',
};

// ============================================================
// State Management
// ============================================================
const state = {
    messages: [],
    isLoading: false,
    sessionId: generateSessionId(),
};

/**
 * Generate a proper UUID for session ID (must be 36+ chars for AgentCore)
 */
function generateSessionId() {
    const stored = localStorage.getItem('quaki_session_id');
    if (stored && stored.length >= 36) return stored;
    
    // Generate new UUID
    const newId = 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
        const r = Math.random() * 16 | 0;
        const v = c === 'x' ? r : (r & 0x3 | 0x8);
        return v.toString(16);
    });
    localStorage.setItem('quaki_session_id', newId);
    return newId;
}

/**
 * Start a new conversation (clears session)
 */
function newConversation() {
    const newId = 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
        const r = Math.random() * 16 | 0;
        const v = c === 'x' ? r : (r & 0x3 | 0x8);
        return v.toString(16);
    });
    localStorage.setItem('quaki_session_id', newId);
    state.sessionId = newId;
    state.messages = [];
    elements.messagesContainer.innerHTML = '';
    elements.messagesContainer.classList.remove('active');
    elements.welcomeSection.classList.remove('hidden');
    console.log('New conversation started:', newId);
}

// ============================================================
// DOM Elements
// ============================================================
const elements = {
    welcomeSection: document.getElementById('welcomeSection'),
    messagesContainer: document.getElementById('messagesContainer'),
    userInput: document.getElementById('userInput'),
    sendBtn: document.getElementById('sendBtn'),
    loadingOverlay: document.getElementById('loadingOverlay'),
};

// ============================================================
// Message Handling
// ============================================================

/**
 * Send a message to the API and display the response
 */
async function sendMessage() {
    const message = elements.userInput.value.trim();
    if (!message || state.isLoading) return;

    elements.userInput.value = '';
    hideWelcomeSection();
    addMessage('user', message);
    setLoading(true);
    const typingId = showTypingIndicator();

    try {
        const response = await fetchAgentResponse(message);
        removeTypingIndicator(typingId);
        addMessage('agent', response.answer, response.has_memory);
    } catch (error) {
        console.error('Error:', error);
        removeTypingIndicator(typingId);
        addMessage('agent', getErrorMessage(error), false, true);
    } finally {
        setLoading(false);
    }
}

/**
 * Ask a predefined question
 */
function askQuestion(question) {
    elements.userInput.value = question;
    sendMessage();
}

/**
 * Handle Enter key press
 */
function handleKeyPress(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        sendMessage();
    }
}

// ============================================================
// API Communication
// ============================================================

/**
 * Fetch response from the agent API
 */
async function fetchAgentResponse(query) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 60000);

    try {
        const response = await fetch(CONFIG.API_URL, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ 
                query,
                session_id: state.sessionId 
            }),
            signal: controller.signal,
        });

        clearTimeout(timeoutId);

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.error || `HTTP ${response.status}`);
        }

        return await response.json();
    } catch (error) {
        clearTimeout(timeoutId);
        throw error;
    }
}

// ============================================================
// UI Helpers
// ============================================================

function hideWelcomeSection() {
    elements.welcomeSection.classList.add('hidden');
    elements.messagesContainer.classList.add('active');
}

function setLoading(loading) {
    state.isLoading = loading;
    elements.sendBtn.disabled = loading;
    elements.userInput.disabled = loading;
}

function addMessage(role, content, hasMemory = false, isError = false) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role}-message${isError ? ' error-message' : ''}`;
    
    const avatar = document.createElement('div');
    avatar.className = 'message-avatar';
    avatar.textContent = role === 'user' ? '👤' : '🤖';
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    
    // Parse markdown-like formatting
    let formattedContent = content
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\n/g, '<br>')
        .replace(/\|(.+)\|/g, (match) => {
            // Simple table detection
            return `<div class="table-row">${match}</div>`;
        });
    
    contentDiv.innerHTML = formattedContent;
    
    if (hasMemory) {
        const memoryBadge = document.createElement('span');
        memoryBadge.className = 'memory-badge';
        memoryBadge.textContent = '🧠 Memory Active';
        contentDiv.appendChild(memoryBadge);
    }
    
    messageDiv.appendChild(avatar);
    messageDiv.appendChild(contentDiv);
    
    elements.messagesContainer.appendChild(messageDiv);
    elements.messagesContainer.scrollTop = elements.messagesContainer.scrollHeight;
    
    state.messages.push({ role, content });
}

function showTypingIndicator() {
    const id = 'typing-' + Date.now();
    const typingDiv = document.createElement('div');
    typingDiv.id = id;
    typingDiv.className = 'message agent-message typing-indicator';
    typingDiv.innerHTML = `
        <div class="message-avatar">🤖</div>
        <div class="message-content">
            <span class="dot"></span>
            <span class="dot"></span>
            <span class="dot"></span>
        </div>
    `;
    elements.messagesContainer.appendChild(typingDiv);
    elements.messagesContainer.scrollTop = elements.messagesContainer.scrollHeight;
    return id;
}

function removeTypingIndicator(id) {
    const indicator = document.getElementById(id);
    if (indicator) indicator.remove();
}

function getErrorMessage(error) {
    if (error.name === 'AbortError') {
        return 'Request timed out. Please try again.';
    }
    if (error.message.includes('Failed to fetch')) {
        return 'Unable to connect to the server. Please check your connection.';
    }
    return `Sorry, something went wrong: ${error.message}`;
}

// ============================================================
// Initialization
// ============================================================
document.addEventListener('DOMContentLoaded', () => {
    console.log('Quaki Support Chat initialized');
    console.log('Session ID:', state.sessionId);
    elements.userInput.focus();
});
