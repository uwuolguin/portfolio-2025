/**
 * Shared functions and utilities
 *  Includes apiRequest wrapper with correlation ID tracking
 */

import { sanitizeAPIResponse } from './sanitizer.js';

// Language management
export function getLanguage() {
    return localStorage.getItem('language') || 'es';
}

export function setLanguage(lang) {
    localStorage.setItem('language', lang);
    document.dispatchEvent(new Event('languageChange'));
}

// Login state management
export function getLoginState() {
    return localStorage.getItem('isLoggedIn') === 'true';
}

export function setLoginState(isLoggedIn) {
    localStorage.setItem('isLoggedIn', isLoggedIn.toString());
}

export function logout() {
    localStorage.removeItem('isLoggedIn');
    localStorage.removeItem('csrfToken');
    window.location.href = '/front-page/front-page.html';
}

// CSRF token management
export function getCSRFToken() {
    return localStorage.getItem('csrfToken');
}

export function setCSRFToken(token) {
    localStorage.setItem('csrfToken', token);
}

/**
 *  CRITICAL: API Request wrapper with automatic correlation ID injection
 * This function wraps fetch() to add X-Correlation-ID header to every request
 * 
 * @param {string} url - API endpoint URL
 * @param {Object} options - Fetch options (method, headers, body, etc.)
 * @returns {Promise<Response>} Fetch response
 */
export async function apiRequest(url, options = {}) {
    // Generate unique correlation ID for request tracking
    const correlationId = generateCorrelationId();
    
    // Merge headers with correlation ID
    const headers = {
        ...options.headers,
        'X-Correlation-ID': correlationId
    };
    
    // Add CSRF token if available (except for public endpoints)
    const csrfToken = getCSRFToken();
    if (csrfToken && !url.includes('/public/')) {
        headers['X-CSRF-Token'] = csrfToken;
    }
    
    // Log request for debugging (can be removed in production)
    console.log(`[${correlationId}] API Request: ${options.method || 'GET'} ${url}`);
    
    try {
        const response = await fetch(url, {
            ...options,
            headers
        });
        
        // Log response status
        console.log(`[${correlationId}] Response: ${response.status} ${response.statusText}`);
        
        return response;
    } catch (error) {
        console.error(`[${correlationId}] Request failed:`, error);
        throw error;
    }
}

/**
 * Generate a unique correlation ID for request tracking
 * Format: timestamp-random
 * @returns {string} Correlation ID
 */
function generateCorrelationId() {
    const timestamp = Date.now().toString(36);
    const random = Math.random().toString(36).substring(2, 9);
    return `${timestamp}-${random}`;
}

/**
 *  UPDATED: Fetch products with automatic sanitization
 * @returns {Promise<Array>} List of products
 */
export async function fetchProducts() {
    try {
        const response = await apiRequest('/api/v1/products/');
        if (response.ok) {
            const data = await response.json();
            //  Sanitize API response
            return sanitizeAPIResponse(data);
        }
        return [];
    } catch (error) {
        console.error('Error fetching products:', error);
        return [];
    }
}

/**
 *  UPDATED: Fetch communes with automatic sanitization
 * @returns {Promise<Array>} List of communes
 */
export async function fetchCommunes() {
    try {
        const response = await apiRequest('/api/v1/communes/');
        if (response.ok) {
            const data = await response.json();
            //  Sanitize API response
            return sanitizeAPIResponse(data);
        }
        return [];
    } catch (error) {
        console.error('Error fetching communes:', error);
        return [];
    }
}

/**
 *  UPDATED: Fetch user's company with automatic sanitization
 * @returns {Promise<Object|null>} Company data or null
 */
export async function fetchUserCompany() {
    try {
        const response = await apiRequest('/api/v1/companies/user/my-company');
        if (response.ok) {
            const data = await response.json();
            //  Sanitize API response
            return sanitizeAPIResponse(data);
        }
        return null;
    } catch (error) {
        console.error('Error fetching user company:', error);
        return null;
    }
}

/**
 *  UPDATED: Search companies with automatic sanitization
 * @param {Object} filters - Search filters (product, commune, search)
 * @returns {Promise<Array>} List of companies
 */
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
            //  Sanitize API response
            return sanitizeAPIResponse(data);
        }
        return [];
    } catch (error) {
        console.error('Error searching companies:', error);
        return [];
    }
}

/**
 * Format date to locale string
 * @param {string} dateString - ISO date string
 * @param {string} lang - Language code
 * @returns {string} Formatted date
 */
export function formatDate(dateString, lang = 'es') {
    const date = new Date(dateString);
    const locale = lang === 'es' ? 'es-CL' : 'en-US';
    
    return date.toLocaleDateString(locale, {
        year: 'numeric',
        month: 'long',
        day: 'numeric'
    });
}

/**
 * Debounce function for search inputs
 * @param {Function} func - Function to debounce
 * @param {number} wait - Wait time in milliseconds
 * @returns {Function} Debounced function
 */
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

/**
 * Check if user is authenticated
 * @returns {boolean} True if user is logged in
 */
export function isAuthenticated() {
    return getLoginState();
}

/**
 * Redirect to login if not authenticated
 */
export function requireAuth() {
    if (!isAuthenticated()) {
        window.location.href = '/log-in/log-in.html';
        return false;
    }
    return true;
}

/**
 * Show loading spinner
 * @param {HTMLElement} element - Target element
 * @param {string} message - Loading message
 */
export function showLoading(element, message = 'Cargando...') {
    element.innerHTML = `
        <div class="loading-spinner">
            <div class="spinner"></div>
            <p>${message}</p>
        </div>
    `;
}

/**
 * Show error message
 * @param {HTMLElement} element - Target element
 * @param {string} message - Error message
 */
export function showError(element, message = 'Error al cargar los datos') {
    element.innerHTML = `
        <div class="error-message">
            <p>${message}</p>
        </div>
    `;
}

/**
 * Validate email format
 * @param {string} email - Email to validate
 * @returns {boolean} True if valid
 */
export function isValidEmail(email) {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
}

/**
 * Validate phone format
 * @param {string} phone - Phone to validate
 * @returns {boolean} True if valid
 */
export function isValidPhone(phone) {
    // Basic validation - adjust based on requirements
    const phoneRegex = /^[\d\s\-\(\)\+]{8,}$/;
    return phoneRegex.test(phone);
}

/**
 * Get file extension from filename
 * @param {string} filename - File name
 * @returns {string} File extension
 */
export function getFileExtension(filename) {
    return filename.slice((filename.lastIndexOf('.') - 1 >>> 0) + 2);
}

/**
 * Format file size for display
 * @param {number} bytes - File size in bytes
 * @returns {string} Formatted size
 */
export function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
}

/**
 * Copy text to clipboard
 * @param {string} text - Text to copy
 * @returns {Promise<boolean>} True if successful
 */
export async function copyToClipboard(text) {
    try {
        await navigator.clipboard.writeText(text);
        return true;
    } catch (error) {
        console.error('Failed to copy to clipboard:', error);
        return false;
    }
}

/**
 * Scroll to element smoothly
 * @param {string} elementId - ID of element to scroll to
 */
export function scrollToElement(elementId) {
    const element = document.getElementById(elementId);
    if (element) {
        element.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
}

/**
 * Get query parameter from URL
 * @param {string} param - Parameter name
 * @returns {string|null} Parameter value
 */
export function getQueryParam(param) {
    const urlParams = new URLSearchParams(window.location.search);
    return urlParams.get(param);
}

/**
 * Set query parameter in URL without reload
 * @param {string} param - Parameter name
 * @param {string} value - Parameter value
 */
export function setQueryParam(param, value) {
    const url = new URL(window.location);
    url.searchParams.set(param, value);
    window.history.pushState({}, '', url);
}

// Export all functions as default object
export default {
    getLanguage,
    setLanguage,
    getLoginState,
    setLoginState,
    logout,
    getCSRFToken,
    setCSRFToken,
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