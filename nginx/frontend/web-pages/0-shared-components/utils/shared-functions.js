// ===========================
// SHARED UTILITY FUNCTIONS
// ===========================

//  CRITICAL ADDITION: Import sanitizer
import { sanitizeAPIResponse } from './sanitizer.js';

// Language Management
export function getLanguage() {
    return localStorage.getItem('language') || 'es';
}

export function setLanguage(lang) {
    if (lang !== 'es' && lang !== 'en') {
        console.warn('Invalid language, defaulting to es');
        lang = 'es';
    }
    localStorage.setItem('language', lang);
    document.documentElement.lang = lang;
    
    // Dispatch event for components to react
    const event = new CustomEvent('languageChange', { detail: { language: lang } });
    document.dispatchEvent(event);
}

// Login State Management
export function getLoginState() {
    return localStorage.getItem('isLoggedIn') === 'true';
}

export function setLoginState(isLoggedIn) {
    localStorage.setItem('isLoggedIn', isLoggedIn.toString());
    
    // Dispatch event
    const event = new CustomEvent('loginStateChange', { detail: { isLoggedIn } });
    document.dispatchEvent(event);
}

// CSRF Token Management
export function getCSRFToken() {
    return localStorage.getItem('csrf_token') || '';
}

export function setCSRFToken(token) {
    localStorage.setItem('csrf_token', token);
}

//  CRITICAL FIX: API Request with automatic sanitization
export async function apiRequest(endpoint, options = {}) {
    const token = getCSRFToken();
    const headers = {
        ...options.headers
    };

    // Add CSRF token for state-changing operations
    if (token && ['POST', 'PUT', 'DELETE', 'PATCH'].includes(options.method?.toUpperCase())) {
        headers['X-CSRF-Token'] = token;
    }

    // Add correlation ID for tracing
    if (!headers['X-Correlation-ID']) {
        headers['X-Correlation-ID'] = `req_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    }

    const response = await fetch(endpoint, {
        ...options,
        headers,
        credentials: 'include' // Always include cookies
    });

    //  CRITICAL SECURITY: Auto-sanitize all JSON responses
    if (response.ok && options.method !== 'DELETE') {
        const originalJson = response.json.bind(response);
        response.json = async () => {
            const data = await originalJson();
            return sanitizeAPIResponse(data);
        };
    }

    // Handle 401 Unauthorized
    if (response.status === 401) {
        setLoginState(false);
        if (window.location.pathname !== '/log-in' && window.location.pathname !== '/sign-up') {
            window.location.href = '/log-in';
        }
    }

    return response;
}

// Fetch Products (for dropdowns)
export async function fetchProducts() {
    try {
        const lang = getLanguage();
        const response = await fetch(`/api/v1/products?lang=${lang}`, {
            credentials: 'include'
        });
        
        if (!response.ok) {
            throw new Error('Failed to fetch products');
        }
        
        const data = await response.json();
        //  Data will be auto-sanitized by apiRequest if using that, but we're using fetch directly here
        return sanitizeAPIResponse(data);
    } catch (error) {
        console.error('Error fetching products:', error);
        return [];
    }
}

// Fetch Communes (for dropdowns)
export async function fetchCommunes() {
    try {
        const lang = getLanguage();
        const response = await fetch(`/api/v1/communes?lang=${lang}`, {
            credentials: 'include'
        });
        
        if (!response.ok) {
            throw new Error('Failed to fetch communes');
        }
        
        const data = await response.json();
        //  Sanitize response data
        return sanitizeAPIResponse(data);
    } catch (error) {
        console.error('Error fetching communes:', error);
        return [];
    }
}

// Re-export commonly used sanitizer functions for convenience
export { sanitizeText, sanitizeEmail } from './sanitizer.js';

// Navigation Helpers
export function navigateTo(path) {
    window.location.href = path;
}

// URL Parameter Helper
export function getQueryParam(param) {
    const urlParams = new URLSearchParams(window.location.search);
    return urlParams.get(param);
}

// Debounce Helper (for search inputs)
export function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Format Date Helper
export function formatDate(dateString, lang = 'es') {
    const date = new Date(dateString);
    const options = {
        year: 'numeric',
        month: 'long',
        day: 'numeric'
    };
    
    return new Intl.DateTimeFormat(lang, options).format(date);
}

// Validation Helpers
export function isValidEmail(email) {
    const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return re.test(email);
}

export function isValidPhone(phone) {
    // Chilean phone format: +56 9 XXXX XXXX or 9 XXXX XXXX
    const re = /^(\+?56)?[\s]?[9]\s?\d{4}\s?\d{4}$/;
    return re.test(phone.replace(/\s+/g, ''));
}

// Loading State Helper
export function setLoadingState(element, isLoading, loadingText = 'Loading...') {
    if (isLoading) {
        element.disabled = true;
        element.dataset.originalText = element.textContent;
        element.textContent = loadingText;
    } else {
        element.disabled = false;
        element.textContent = element.dataset.originalText || element.textContent;
    }
}

// Error Display Helper
export function showError(message, container) {
    const errorDiv = document.createElement('div');
    errorDiv.className = 'error-message';
    errorDiv.textContent = message;
    errorDiv.style.cssText = `
        background-color: #fee;
        border: 1px solid #fcc;
        color: #c33;
        padding: 10px;
        margin: 10px 0;
        border-radius: 4px;
    `;
    
    container.appendChild(errorDiv);
    
    // Auto-remove after 5 seconds
    setTimeout(() => {
        errorDiv.remove();
    }, 5000);
}

// Success Display Helper
export function showSuccess(message, container) {
    const successDiv = document.createElement('div');
    successDiv.className = 'success-message';
    successDiv.textContent = message;
    successDiv.style.cssText = `
        background-color: #efe;
        border: 1px solid #cfc;
        color: #3c3;
        padding: 10px;
        margin: 10px 0;
        border-radius: 4px;
    `;
    
    container.appendChild(successDiv);
    
    // Auto-remove after 5 seconds
    setTimeout(() => {
        successDiv.remove();
    }, 5000);
}

// Initialize app on DOMContentLoaded
document.addEventListener('DOMContentLoaded', () => {
    // Set initial language if not set
    if (!localStorage.getItem('language')) {
        setLanguage('es');
    }
    
    // Check login state on protected pages
    const protectedPages = ['/profile-view', '/profile-edit', '/publish'];
    const currentPath = window.location.pathname;
    
    if (protectedPages.includes(currentPath) && !getLoginState()) {
        navigateTo('/log-in');
    }
});