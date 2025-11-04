    // ============================================
    // AUTH STATE MANAGEMENT
    // ============================================

    // Check if user is logged in by calling backend
    export async function checkAuthStatus() {
        try {
            const response = await fetch('/api/v1/users/me', {
                credentials: 'include',
                headers: {
                    'X-Correlation-ID': `auth_check_${Date.now()}`
                }
            });
            
            if (response.ok) {
                const userData = await response.json();
                localStorage.setItem("isLoggedIn", "true");
                localStorage.setItem("userData", JSON.stringify(userData));
                return true;
            } else {
                localStorage.setItem("isLoggedIn", "false");
                localStorage.removeItem("userData");
                localStorage.removeItem("csrf_token");
                return false;
            }
        } catch (error) {
            console.error('Auth check failed:', error);
            localStorage.setItem("isLoggedIn", "false");
            return false;
        }
    }

    export function getLoginState() {
        const value = localStorage.getItem("isLoggedIn");
        return value === "true";
    }

    export function setLoginState(hasLogged) {
        localStorage.setItem("isLoggedIn", hasLogged.toString());
        
        if (!hasLogged) {
            localStorage.removeItem("userData");
            localStorage.removeItem("csrf_token");
            localStorage.setItem("hasPublishedCompany", "false");
        }
        
        document.dispatchEvent(new CustomEvent("userHasLogged"));
    }

    // Get stored user data
    export function getUserData() {
        const data = localStorage.getItem("userData");
        return data ? JSON.parse(data) : null;
    }

    // ============================================
    // LANGUAGE MANAGEMENT
    // ============================================

    export function getLanguage() {
        let lang = localStorage.getItem("lang");
        if (!lang) {
            localStorage.setItem("lang", "es");
            return "es";
        }
        return lang;
    }

    export function setLanguage(Lang) {
        localStorage.setItem("lang", Lang);
        document.dispatchEvent(new CustomEvent("languageChange"));
    }

    // ============================================
    // COMPANY STATE MANAGEMENT
    // ============================================

    export function getCompanyPublishState() {
        if (!getLoginState()) {
            return false;
        }
        
        const value = localStorage.getItem("hasPublishedCompany");
        if (value === null) {
            localStorage.setItem("hasPublishedCompany", "false");
            return false;
        }
        return value === "true";
    }

    export function setCompanyPublishState(hasPublished) {
        if (hasPublished && !getLoginState()) {
            return;
        }
        
        localStorage.setItem("hasPublishedCompany", hasPublished.toString());
        document.dispatchEvent(new CustomEvent("companyPublishStateChange"));
    }

    export function getCompanyData() {
        return JSON.parse(localStorage.getItem('companyData')) || null;
    }

    export function setCompanyData(data) {
        if (data === null) {
            localStorage.removeItem('companyData');
            setCompanyPublishState(false);
        } else {
            localStorage.setItem('companyData', JSON.stringify(data));
            setCompanyPublishState(true);
        }
        
        document.dispatchEvent(new CustomEvent('companyDataChange'));
    }

    // ============================================
    // CSRF TOKEN MANAGEMENT
    // ============================================

    export function getCSRFToken() {
        return localStorage.getItem('csrf_token');
    }

    export function setCSRFToken(token) {
        if (token) {
            localStorage.setItem('csrf_token', token);
        } else {
            localStorage.removeItem('csrf_token');
        }
    }

    // ============================================
    // STORAGE LISTENER
    // ============================================

    export function initStorageListener() {
        window.addEventListener("storage", (event) => {
            if (event.key === "lang" || event.key === "isLoggedIn" || event.key === "hasPublishedCompany") {
                location.reload();
            }
        });
    }

    // ============================================
    // API HELPER FUNCTIONS
    // ============================================

    // Fetch with automatic CSRF and correlation ID
    export async function apiRequest(endpoint, options = {}) {
        const headers = {
            'X-Correlation-ID': `${endpoint.split('/').pop()}_${Date.now()}`,
            ...options.headers
        };
        
        // Add CSRF token for state-changing methods
        if (['POST', 'PUT', 'DELETE', 'PATCH'].includes(options.method?.toUpperCase())) {
            const csrfToken = getCSRFToken();
            if (csrfToken) {
                headers['X-CSRF-Token'] = csrfToken;
            }
        }
        
        // Add Content-Type if body is not FormData
        if (options.body && !(options.body instanceof FormData)) {
            headers['Content-Type'] = 'application/json';
        }
        
        const response = await fetch(endpoint, {
            ...options,
            headers,
            credentials: 'include'
        });
        
        return response;
    }

    // Fetch products list (cached for dropdowns)
    let cachedProducts = null;
    export async function fetchProducts() {
        if (cachedProducts) return cachedProducts;
        
        const response = await apiRequest('/api/v1/products/');
        if (response.ok) {
            cachedProducts = await response.json();
            return cachedProducts;
        }
        return [];
    }

    // Fetch communes list (cached for dropdowns)
    let cachedCommunes = null;
    export async function fetchCommunes() {
        if (cachedCommunes) return cachedCommunes;
        
        const response = await apiRequest('/api/v1/communes/');
        if (response.ok) {
            cachedCommunes = await response.json();
            return cachedCommunes;
        }
        return [];
    }