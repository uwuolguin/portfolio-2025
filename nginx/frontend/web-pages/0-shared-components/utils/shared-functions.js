/**
 * Shared functions and utilities
 * Includes apiRequest wrapper with correlation ID tracking
 * AND cross-tab state synchronization
 */

export const BASE_URL = window.location.origin;

export function getInternalUrl(path) {
    return `${BASE_URL}${path.startsWith('/') ? '' : '/'}${path}`;
}

function notifyStateChange(key) {
    document.dispatchEvent(new Event('stateChange'));
}

export function initStorageListener() {
    window.addEventListener('storage', (e) => {
        if (!e.key) return;
        switch (e.key) {
            case 'isLoggedIn':
            case 'hasCompany':
            case 'language':
                notifyStateChange(e.key);
                break;
        }
    });
}

export function getLanguage() {
    return localStorage.getItem('language') || 'es';
}

export function setLanguage(lang) {
    localStorage.setItem('language', lang);
    notifyStateChange('language');
}

export function getLoginState() {
    return localStorage.getItem('isLoggedIn') === 'true';
}

export function setLoginState(isLoggedIn) {
    localStorage.setItem('isLoggedIn', isLoggedIn.toString());
    notifyStateChange('isLoggedIn');
}

export function logout() {
    localStorage.removeItem('isLoggedIn');
    localStorage.removeItem('hasCompany');
    notifyStateChange('isLoggedIn');
    window.location.href = '/front-page/front-page.html';
}

export function getCompanyPublishState() {
    return localStorage.getItem('hasCompany') === 'true';
}

export function setCompanyPublishState(hasCompany) {
    localStorage.setItem('hasCompany', hasCompany.toString());
    notifyStateChange('hasCompany');
}

export function getCSRFToken() {
    const match = document.cookie.match(/csrf_token=([^;]+)/);
    return match ? match[1] : null;
}

function generateCorrelationId() {
    const timestamp = Date.now().toString(36);
    const random = Math.random().toString(36).substring(2, 9);
    return `fe_${timestamp}_${random}`;
}

export async function apiRequest(url, options = {}) {
    const correlationId = generateCorrelationId();

    const headers = {
        ...options.headers,
        'X-Correlation-ID': correlationId
    };

    const csrfToken = getCSRFToken();
    if (csrfToken) {
        headers['X-CSRF-Token'] = csrfToken;
    }

    try {
        const response = await fetch(url, {
            ...options,
            headers,
            credentials: 'include'
        });
        return response;
    } catch (error) {
        throw error;
    }
}

export async function checkAuthStatus() {
    try {
        const response = await apiRequest('/api/v1/users/me');
        const isAuthenticated = response.ok;
        const currentState = getLoginState();
        if (isAuthenticated !== currentState) {
            setLoginState(isAuthenticated);
        }
        return isAuthenticated;
    } catch (error) {
        const currentState = getLoginState();
        if (currentState) {
            setLoginState(false);
        }
        return false;
    }
}

export async function checkCompanyStatus() {
    try {
        const response = await apiRequest('/api/v1/companies/user/my-company');
        const hasCompany = response.ok;
        const currentState = getCompanyPublishState();
        if (hasCompany !== currentState) {
            setCompanyPublishState(hasCompany);
        }
        return hasCompany;
    } catch (error) {
        const currentState = getCompanyPublishState();
        if (currentState) {
            setCompanyPublishState(false);
        }
        return false;
    }
}

export async function fetchProducts() {
    try {
        const response = await apiRequest('/api/v1/products');
        if (response.ok) {
            return await response.json();
        }
        return [];
    } catch (error) {
        console.error('Error fetching products:', error);
        return [];
    }
}

export async function fetchCommunes() {
    try {
        const response = await apiRequest('/api/v1/communes');
        if (response.ok) {
            return await response.json();
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
            return await response.json();
        }
        return null;
    } catch (error) {
        console.error('Error fetching user company:', error);
        return null;
    }
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
    checkAuthStatus,
    checkCompanyStatus,
    apiRequest,
    fetchProducts,
    fetchCommunes,
    fetchUserCompany,
    debounce
};
