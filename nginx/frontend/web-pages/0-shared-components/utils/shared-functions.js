/**
 * Shared functions and utilities
 * Includes apiRequest wrapper with correlation ID tracking
 * AND cross-tab state synchronization
 */

import { sanitizeAPIResponse } from './sanitizer.js';

// ============================================
// STATE SYNCHRONIZATION SYSTEM
// ============================================

/**
 * Custom event for same-tab state changes
 * (storage event only fires for OTHER tabs)
 */
const STATE_CHANGE_EVENT = 'appStateChange';

/**
 * Dispatch a custom state change event for same-tab updates
 */
function dispatchStateChange(key, newValue) {
    const event = new CustomEvent(STATE_CHANGE_EVENT, {
        detail: { key, newValue }
    });
    window.dispatchEvent(event);
}

/**
 * Initialize storage event listener for cross-tab synchronization
 * Call this ONCE per page in DOMContentLoaded
 */
export function initStorageListener() {
    // Listen for changes from OTHER tabs
    window.addEventListener('storage', (e) => {
        if (!e.key) return; // Ignore clear() calls
        
        console.log(`[Storage Sync] Key changed in another tab: ${e.key}`);
        
        // Trigger re-render based on which key changed
        switch (e.key) {
            case 'isLoggedIn':
            case 'hasCompany':
            case 'language':
                // Trigger navigation re-render
                document.dispatchEvent(new Event('stateChange'));
                break;
        }
    });
    
    // Listen for same-tab state changes
    window.addEventListener(STATE_CHANGE_EVENT, (e) => {
        console.log(`[State Sync] Key changed in same tab: ${e.detail.key}`);
        document.dispatchEvent(new Event('stateChange'));
    });
    
    console.log('[State Sync] Storage listener initialized');
}

// ============================================
// LANGUAGE MANAGEMENT (with state sync)
// ============================================

export function getLanguage() {
    return localStorage.getItem('language') || 'es';
}

export function setLanguage(lang) {
    const oldValue = localStorage.getItem('language');
    localStorage.setItem('language', lang);
    
    // Dispatch events for both same-tab and cross-tab sync
    document.dispatchEvent(new Event('languageChange'));
    dispatchStateChange('language', lang);
    
    console.log(`[Language] Changed from ${oldValue} to ${lang}`);
}

// ============================================
// LOGIN STATE MANAGEMENT (with state sync)
// ============================================

export function getLoginState() {
    return localStorage.getItem('isLoggedIn') === 'true';
}

export function setLoginState(isLoggedIn) {
    const oldValue = getLoginState();
    localStorage.setItem('isLoggedIn', isLoggedIn.toString());
    
    // Dispatch state change event (for same-tab sync)
    dispatchStateChange('isLoggedIn', isLoggedIn);
    
    console.log(`[Auth] Login state changed: ${oldValue} → ${isLoggedIn}`);
}

export function logout() {
    localStorage.removeItem('isLoggedIn');
    localStorage.removeItem('csrfToken');
    localStorage.removeItem('hasCompany');
    
    // Dispatch state change
    dispatchStateChange('isLoggedIn', false);
    dispatchStateChange('hasCompany', false);
    
    console.log('[Auth] User logged out, state cleared');
    
    window.location.href = '/front-page/front-page.html';
}

// ============================================
// COMPANY PUBLISH STATE (with state sync)
// ============================================

export function getCompanyPublishState() {
    return localStorage.getItem('hasCompany') === 'true';
}

export function setCompanyPublishState(hasCompany) {
    const oldValue = getCompanyPublishState();
    localStorage.setItem('hasCompany', hasCompany.toString());
    
    // Dispatch state change event
    dispatchStateChange('hasCompany', hasCompany);
    
    console.log(`[Company] Publish state changed: ${oldValue} → ${hasCompany}`);
}

// ============================================
// CSRF TOKEN MANAGEMENT
// ============================================

export function getCSRFToken() {
    return localStorage.getItem('csrfToken');
}

export function setCSRFToken(token) {
    localStorage.setItem('csrfToken', token);
}

// ============================================
// AUTH STATUS CHECK (with state sync)
// ============================================

/**
 * Check authentication status by calling the backend
 * Updates local state and triggers re-render if needed
 * @returns {Promise<boolean>} True if authenticated
 */
export async function checkAuthStatus() {
    try {
        const response = await apiRequest('/api/v1/users/me', {
            credentials: 'include'
        });
        
        const isAuthenticated = response.ok;
        const currentState = getLoginState();
        
        // Update state if it changed
        if (isAuthenticated !== currentState) {
            setLoginState(isAuthenticated);
        }
        
        console.log(`[Auth Check] Status: ${isAuthenticated ? 'Authenticated' : 'Not authenticated'}`);
        return isAuthenticated;
        
    } catch (error) {
        console.error('[Auth Check] Failed:', error);
        
        // If auth check fails, assume not authenticated
        const currentState = getLoginState();
        if (currentState) {
            setLoginState(false);
        }
        
        return false;
    }
}

/**
 * Check if user has a published company
 * Updates local state and triggers re-render if needed
 * @returns {Promise<boolean>} True if user has a company
 */
export async function checkCompanyStatus() {
    try {
        const response = await apiRequest('/api/v1/companies/user/my-company', {
            credentials: 'include'
        });
        
        const hasCompany = response.ok;
        const currentState = getCompanyPublishState();
        
        // Update state if it changed
        if (hasCompany !== currentState) {
            setCompanyPublishState(hasCompany);
        }
        
        console.log(`[Company Check] Has company: ${hasCompany}`);
        return hasCompany;
        
    } catch (error) {
        console.error('[Company Check] Failed:', error);
        
        // If check fails, assume no company
        const currentState = getCompanyPublishState();
        if (currentState) {
            setCompanyPublishState(false);
        }
        
        return false;
    }
}

// ============================================
// API REQUEST WRAPPER (with correlation ID)
// ============================================

/**
 * API Request wrapper with automatic correlation ID injection
 * @param {string} url - API endpoint URL
 * @param {Object} options - Fetch options
 * @returns {Promise<Response>} Fetch response
 */
export async function apiRequest(url, options = {}) {
    const correlationId = generateCorrelationId();
    
    const headers = {
        ...options.headers,
        'X-Correlation-ID': correlationId
    };
    
    const csrfToken = getCSRFToken();
    if (csrfToken && !url.includes('/public/')) {
        headers['X-CSRF-Token'] = csrfToken;
    }
    
    console.log(`[${correlationId}] API Request: ${options.method || 'GET'} ${url}`);
    
    try {
        const response = await fetch(url, {
            ...options,
            headers
        });
        
        console.log(`[${correlationId}] Response: ${response.status} ${response.statusText}`);
        
        return response;
    } catch (error) {
        console.error(`[${correlationId}] Request failed:`, error);
        throw error;
    }
}

function generateCorrelationId() {
    const timestamp = Date.now().toString(36);
    const random = Math.random().toString(36).substring(2, 9);
    return `${timestamp}-${random}`;
}

// ============================================
// DATA FETCHING (with sanitization)
// ============================================

export async function fetchProducts() {
    try {
        const response = await apiRequest('/api/v1/products/');
        if (response.ok) {
            const data = await response.json();
            return sanitizeAPIResponse(data);
        }
        return [];
    } catch (error) {
        console.error('Error fetching products:', error);
        return [];
    }
}

export async function fetchCommunes() {
    try {
        const response = await apiRequest('/api/v1/communes/');
        if (response.ok) {
            const data = await response.json();
            return sanitizeAPIResponse(data);
        }
        return [];
    } catch (error) {
        console.error('Error fetching communes:', error);
        return [];
    }
}

export async function fetchUserCompany() {
    try {
        const response = await apiRequest('/api/v1/companies/user/my-company');
        if (response.ok) {
            const data = await response.json();
            return sanitizeAPIResponse(data);
        }
        return null;
    } catch (error) {
        console.error('Error fetching user company:', error);
        return null;
    }
}

export async function searchCompanies(filters = {}) {
    try {
        const params = new URLSearchParams();
        
        if (filters.product) params.append('product', filters.product);
        if (filters.commune) params.append('commune', filters.commune);
        if (filters.search) params.append('search', filters.search);
        
        const url = `/api/v1/companies/search?${params.toString()}`;
        const response = await apiRequest(url);
        
        if (response.ok) {
            const data = await response.json();
            return sanitizeAPIResponse(data);
        }
        return [];
    } catch (error) {
        console.error('Error searching companies:', error);
        return [];
    }
}

// ============================================
// UTILITY FUNCTIONS
// ============================================

export function formatDate(dateString, lang = 'es') {
    const date = new Date(dateString);
    const locale = lang === 'es' ? 'es-CL' : 'en-US';
    
    return date.toLocaleDateString(locale, {
        year: 'numeric',
        month: 'long',
        day: 'numeric'
    });
}

export function debounce(func, wait = 300) {
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

export function isAuthenticated() {
    return getLoginState();
}

export function requireAuth() {
    if (!isAuthenticated()) {
        window.location.href = '/log-in/log-in.html';
        return false;
    }
    return true;
}

export function showLoading(element, message = 'Cargando...') {
    element.innerHTML = `
        <div class="loading-spinner">
            <div class="spinner"></div>
            <p>${message}</p>
        </div>
    `;
}

export function showError(element, message = 'Error al cargar los datos') {
    element.innerHTML = `
        <div class="error-message">
            <p>${message}</p>
        </div>
    `;
}

export function isValidEmail(email) {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
}

export function isValidPhone(phone) {
    const phoneRegex = /^[\d\s\-\(\)\+]{8,}$/;
    return phoneRegex.test(phone);
}

export function getFileExtension(filename) {
    return filename.slice((filename.lastIndexOf('.') - 1 >>> 0) + 2);
}

export function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
}

export async function copyToClipboard(text) {
    try {
        await navigator.clipboard.writeText(text);
        return true;
    } catch (error) {
        console.error('Failed to copy to clipboard:', error);
        return false;
    }
}

export function scrollToElement(elementId) {
    const element = document.getElementById(elementId);
    if (element) {
        element.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
}

export function getQueryParam(param) {
    const urlParams = new URLSearchParams(window.location.search);
    return urlParams.get(param);
}

export function setQueryParam(param, value) {
    const url = new URL(window.location);
    url.searchParams.set(param, value);
    window.history.pushState({}, '', url);
}

// Export all functions as default object
export default {
    initStorageListener,
    getLanguage,
    setLanguage,
    getLoginState,
    setLoginState,
    getCompanyPublishState,
    setCompanyPublishState,
    logout,
    getCSRFToken,
    setCSRFToken,
    checkAuthStatus,
    checkCompanyStatus,
    apiRequest,
    fetchProducts,
    fetchCommunes,
    fetchUserCompany,
    searchCompanies,
    formatDate,
    debounce,
    isAuthenticated,
    requireAuth,
    showLoading,
    showError,
    isValidEmail,
    isValidPhone,
    getFileExtension,
    formatFileSize,
    copyToClipboard,
    scrollToElement,
    getQueryParam,
    setQueryParam
};