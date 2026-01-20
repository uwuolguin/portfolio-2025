/**
 * Shared functions and utilities
 * Includes apiRequest wrapper with correlation ID tracking
 * AND cross-tab state synchronization
 */

// ============================================
// STATE SYNCHRONIZATION SYSTEM
// ============================================

/**
 * Dispatches a 'stateChange' event on document
 * This notifies all components that app state has changed
 */
function notifyStateChange(key) {
    console.log(`[State Sync] ${key} changed, notifying components`);
    document.dispatchEvent(new Event('stateChange'));
}

/**
 * Initialize storage listeners for cross-tab synchronization
 * Call this once in each page's main JS file
 */
export function initStorageListener() {
    // Listen for changes from OTHER tabs (storage event only fires cross-tab)
    window.addEventListener('storage', (e) => {
        if (!e.key) return;
        
        console.log(`[Storage Sync] Key changed in another tab: ${e.key}`);
        
        // Only react to our tracked keys
        switch (e.key) {
            case 'isLoggedIn':
            case 'hasCompany':
            case 'language':
                notifyStateChange(e.key);
                break;
        }
    });
    
    console.log('[State Sync] Storage listener initialized');
}

// ============================================
// LANGUAGE MANAGEMENT
// ============================================

export function getLanguage() {
    return localStorage.getItem('language') || 'es';
}

export function setLanguage(lang) {
    const oldValue = localStorage.getItem('language');
    localStorage.setItem('language', lang);
    
    // Notify THIS tab immediately (storage event won't fire for same tab)
    notifyStateChange('language');
    
    console.log(`[Language] Changed from ${oldValue} to ${lang}`);
}

// ============================================
// LOGIN STATE MANAGEMENT
// ============================================

export function getLoginState() {
    return localStorage.getItem('isLoggedIn') === 'true';
}

export function setLoginState(isLoggedIn) {
    const oldValue = getLoginState();
    localStorage.setItem('isLoggedIn', isLoggedIn.toString());
    
    // Notify THIS tab immediately (storage event won't fire for same tab)
    notifyStateChange('isLoggedIn');
    
    console.log(`[Auth] Login state changed: ${oldValue} → ${isLoggedIn}`);
}

export function logout() {
    localStorage.removeItem('isLoggedIn');
    localStorage.removeItem('hasCompany');
    
    // Notify THIS tab immediately
    notifyStateChange('isLoggedIn');

    
    console.log('[Auth] User logged out, state cleared');
    window.location.href = '/front-page/front-page.html';
}

// ============================================
// COMPANY PUBLISH STATE
// ============================================

export function getCompanyPublishState() {
    return localStorage.getItem('hasCompany') === 'true';
}

export function setCompanyPublishState(hasCompany) {
    const oldValue = getCompanyPublishState();
    localStorage.setItem('hasCompany', hasCompany.toString());
    
    // Notify THIS tab immediately (storage event won't fire for same tab)
    notifyStateChange('hasCompany');
    
    console.log(`[Company] Publish state changed: ${oldValue} → ${hasCompany}`);
}

// ============================================
// CSRF TOKEN MANAGEMENT
// ============================================

export function getCSRFToken() {
    const match = document.cookie.match(/csrf_token=([^;]+)/);
    return match ? match[1] : null;
}

// ============================================
// CORRELATION ID GENERATION
// ============================================

function generateCorrelationId() {
    const timestamp = Date.now().toString(36);
    const random = Math.random().toString(36).substring(2, 9);
    return `fe_${timestamp}_${random}`;
}

// ============================================
// API REQUEST WRAPPER
// ============================================

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
    
    console.log(`[${correlationId}] API Request: ${options.method || 'GET'} ${url}`);
    
    try {
        const response = await fetch(url, {
            ...options,
            headers,
            credentials: 'include'
        });
        
        console.log(`[${correlationId}] Response: ${response.status} ${response.statusText}`);
        
        return response;
    } catch (error) {
        console.error(`[${correlationId}] Request failed:`, error);
        throw error;
    }
}

// ============================================
// AUTH STATUS CHECK
// ============================================

export async function checkAuthStatus() {
    try {
        const response = await apiRequest('/api/v1/users/me');
        
        const isAuthenticated = response.ok;
        const currentState = getLoginState();
        
        if (isAuthenticated !== currentState) {
            setLoginState(isAuthenticated);
        }
        
        console.log(`[Auth Check] Status: ${isAuthenticated ? 'Authenticated' : 'Not authenticated'}`);
        return isAuthenticated;
        
    } catch (error) {
        console.error('[Auth Check] Failed:', error);
        
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
        
        console.log(`[Company Check] Has company: ${hasCompany}`);
        return hasCompany;
        
    } catch (error) {
        console.error('[Company Check] Failed:', error);
        
        const currentState = getCompanyPublishState();
        if (currentState) {
            setCompanyPublishState(false);
        }
        
        return false;
    }
}

// ============================================
// DATA FETCHING
// ============================================

export async function fetchProducts() {
    try {
        const response = await apiRequest('/api/v1/products/');
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
        const response = await apiRequest('/api/v1/communes/');
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

// ============================================
// UTILITY FUNCTIONS
// ============================================

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

// ============================================
// DEFAULT EXPORT
// ============================================

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