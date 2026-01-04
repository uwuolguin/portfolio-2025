/**
 * XSS Protection Utilities - PRODUCTION GRADE
 * 
 * Security Principles:
 * 1. Prefer textContent over innerHTML (no HTML parsing)
 * 2. Use DOMPurify ONLY when HTML is absolutely needed
 * 3. Validate URLs strictly (no javascript:, data:, etc)
 * 4. Default to stripping, not escaping
 */

// Lazy-load DOMPurify (only when needed)
let DOMPurify = null;

async function ensureDOMPurify() {
    if (DOMPurify) return DOMPurify;
    
    if (typeof window.DOMPurify !== 'undefined') {
        DOMPurify = window.DOMPurify;
        return DOMPurify;
    }
    
    throw new Error('DOMPurify not loaded. Include purify.min.js in <head>');
}

/**
 * SAFE: Use textContent (no HTML interpretation)
 * This is the DEFAULT for user input
 */
export function sanitizeText(input) {
    if (input === null || input === undefined) return '';
    if (typeof input !== 'string') return String(input);
    
    // Remove null bytes (potential bypass)
    return input.replace(/\x00/g, '').trim();
}

/**
 * UNSAFE BUT SOMETIMES NEEDED: Allow limited HTML
 * Only use when you NEED to preserve formatting
 */
export function sanitizeHTML(html) {
    if (!html) return '';
    
    if (!DOMPurify) {
        console.error('DOMPurify not loaded - falling back to text only');
        return sanitizeText(html);
    }
    
    // STRICT: Only allow minimal formatting tags
    return DOMPurify.sanitize(html, {
        ALLOWED_TAGS: ['b', 'i', 'u', 'strong', 'em', 'br', 'p'],
        ALLOWED_ATTR: [],  // NO attributes allowed
        KEEP_CONTENT: true,
        RETURN_DOM: false,
        RETURN_DOM_FRAGMENT: false,
    });
}

/**
 * URL Sanitizer - STRICT validation
 * Only allows http/https, blocks javascript:, data:, etc
 */
export function sanitizeURL(url) {
    if (!url || typeof url !== 'string') return '';
    
    url = url.replace(/\x00/g, '').trim();
    
    // Block dangerous URL protocols immediately
    if (/^(javascript|data|vbscript|file|about):/i.test(url)) {
        console.warn('Blocked dangerous URL protocol:', url.substring(0, 50));
        return '';
    }
    
    // Validate URL structure
    try {
        const parsed = new URL(url, window.location.origin);
        
        // ONLY allow http/https
        if (!['http:', 'https:'].includes(parsed.protocol)) {
            console.warn('Blocked non-HTTP protocol:', parsed.protocol);
            return '';
        }
        
        return parsed.href;
    } catch (e) {
        console.warn('Invalid URL:', url.substring(0, 50));
        return '';
    }
}

/**
 * Email Sanitizer - Strict validation
 */
export function sanitizeEmail(email) {
    if (!email || typeof email !== 'string') return '';
    
    email = sanitizeText(email);
    
    const emailRegex = /^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$/;
    
    if (!emailRegex.test(email)) {
        console.warn('Invalid email format:', email);
        return '';
    }
    
    return email;
}

/**
 * Phone Sanitizer
 */
export function sanitizePhone(phone) {
    if (!phone || typeof phone !== 'string') return '';
    return phone.replace(/[^0-9+\s\-()]/g, '').trim();
}

/**
 * PREFERRED: Create DOM elements safely using textContent
 * NO HTML parsing - completely XSS-proof
 */
export function createSafeElement(tag, text = '', attrs = {}) {
    const element = document.createElement(tag);
    
    // textContent is XSS-safe (no HTML interpretation)
    element.textContent = sanitizeText(text);
    
    // Set attributes safely
    for (const [key, value] of Object.entries(attrs)) {
        if (key === 'href' || key === 'src') {
            const safeURL = sanitizeURL(value);
            if (safeURL) {
                element.setAttribute(key, safeURL);
            }
        } else if (key === 'class') {
            element.className = sanitizeText(value);
        } else if (key === 'id') {
            element.id = sanitizeText(value);
        } else if (!key.startsWith('on')) {  // Block event handlers
            element.setAttribute(key, sanitizeText(value));
        }
    }
    
    return element;
}

// Initialize DOMPurify on module load
if (typeof window !== 'undefined') {
    ensureDOMPurify().catch(err => {
        console.error('Failed to initialize DOMPurify:', err);
    });
}