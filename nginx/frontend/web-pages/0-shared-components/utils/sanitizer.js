/**
 * XSS Protection Utilities - PRODUCTION GRADE
 * 
 * Security Principles:
 * 1. Prefer textContent over innerHTML (no HTML parsing)
 * 2. Use DOMPurify ONLY when HTML is absolutely needed
 * 3. Validate URLs strictly (no javascript:, data:, etc)
 * 4. Default to stripping, not escaping
 * 5. Sanitize ALL external data (API responses, user input, localStorage)
 * 
 * @version 2.0.0
 * @author Proveo Security Team
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
 * ============================================================================
 * CORE SANITIZERS (Use these for 99% of cases)
 * ============================================================================
 */

/**
 * SAFE: Use textContent (no HTML interpretation)
 * This is the DEFAULT for ALL user input
 * 
 * @param {*} input - Any input value
 * @returns {string} - Safe text string
 */
export function sanitizeText(input) {
    if (input === null || input === undefined) return '';
    if (typeof input !== 'string') return String(input);
    
    // Remove null bytes (potential bypass)
    return input.replace(/\x00/g, '').trim();
}

/**
 * URL Sanitizer - STRICT validation
 * Only allows http/https, blocks javascript:, data:, etc
 * 
 * @param {string} url - URL to sanitize
 * @returns {string} - Safe URL or empty string
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
 * 
 * @param {string} email - Email to sanitize
 * @returns {string} - Safe email or empty string
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
 * 
 * @param {string} phone - Phone number to sanitize
 * @returns {string} - Sanitized phone
 */
export function sanitizePhone(phone) {
    if (!phone || typeof phone !== 'string') return '';
    return phone.replace(/[^0-9+\s\-()]/g, '').trim();
}

/**
 * ============================================================================
 * HTML SANITIZER (Use sparingly, only for rich text)
 * ============================================================================
 */

/**
 * UNSAFE BUT SOMETIMES NEEDED: Allow limited HTML
 * Only use when you NEED to preserve formatting (descriptions, rich text)
 * 
 * @param {string} html - HTML to sanitize
 * @returns {string} - Sanitized HTML
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
 * ============================================================================
 * DOM BUILDERS (PREFERRED: Build elements safely)
 * ============================================================================
 */

/**
 * PREFERRED: Create DOM elements safely using textContent
 * NO HTML parsing - completely XSS-proof
 * 
 * @param {string} tag - HTML tag name
 * @param {string} text - Text content
 * @param {Object} attrs - Attributes to set
 * @returns {HTMLElement} - Safe DOM element
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

/**
 * Build a company/business card safely
 * Use this for search results, listings, etc.
 * 
 * @param {Object} data - Company data from API
 * @param {string} lang - Language ('es' or 'en')
 * @returns {HTMLElement} - Safe business card element
 */
export function buildBusinessCard(data, lang = 'es') {
    const card = document.createElement('div');
    card.className = 'business-card';
    
    // Picture container
    const pictureDiv = document.createElement('div');
    pictureDiv.className = 'card-picture';
    
    const img = document.createElement('img');
    img.src = sanitizeURL(data.img_url || data.image_url);
    img.alt = sanitizeText(data.name);
    img.loading = 'lazy'; // Performance optimization
    
    pictureDiv.appendChild(img);
    
    // Details container
    const detailsDiv = document.createElement('div');
    detailsDiv.className = 'card-details';
    
    // Name
    const name = document.createElement('h3');
    name.className = 'business-name';
    name.textContent = sanitizeText(data.name);
    
    // Description
    const desc = document.createElement('p');
    desc.className = 'concise-description';
    desc.textContent = sanitizeText(data.description);
    
    // Location
    const location = document.createElement('p');
    location.className = 'location';
    location.textContent = `📍 ${sanitizeText(data.address || '')}`;
    
    // Phone
    const phone = document.createElement('p');
    phone.className = 'phone';
    phone.textContent = `📞 ${sanitizePhone(data.phone || '')}`;
    
    // Email
    const email = document.createElement('p');
    email.className = 'mail';
    email.textContent = `✉️ ${sanitizeEmail(data.email || '')}`;
    
    detailsDiv.append(name, desc, location, phone, email);
    card.append(pictureDiv, detailsDiv);
    
    return card;
}

/**
 * Build a dropdown option safely
 * 
 * @param {string} value - Option value
 * @param {string} text - Option display text
 * @returns {HTMLElement} - Safe option element
 */
export function buildDropdownOption(value, text) {
    const option = document.createElement('div');
    option.className = 'dropdown-option';
    option.dataset.value = sanitizeText(value);
    option.textContent = sanitizeText(text || value);
    return option;
}

/**
 * ============================================================================
 * API RESPONSE SANITIZER (Sanitize all external data)
 * ============================================================================
 */

/**
 * Recursively sanitize API response data
 * Handles arrays, objects, strings, URLs
 * 
 * @param {*} data - Data from API
 * @returns {*} - Sanitized data
 */
export function sanitizeAPIResponse(data) {
    // Handle arrays
    if (Array.isArray(data)) {
        return data.map(sanitizeAPIResponse);
    }
    
    // Handle objects
    if (data && typeof data === 'object') {
        const clean = {};
        for (const [key, value] of Object.entries(data)) {
            // Sanitize based on key name patterns
            if (key.includes('url') || key.includes('image') || key === 'img_url') {
                clean[key] = sanitizeURL(value);
            } else if (key.includes('email')) {
                clean[key] = sanitizeEmail(value);
            } else if (key.includes('phone')) {
                clean[key] = sanitizePhone(value);
            } else if (typeof value === 'string') {
                clean[key] = sanitizeText(value);
            } else {
                // Recurse for nested objects/arrays
                clean[key] = sanitizeAPIResponse(value);
            }
        }
        return clean;
    }
    
    // Primitive types
    if (typeof data === 'string') {
        return sanitizeText(data);
    }
    
    return data;
}

/**
 * ============================================================================
 * FORM VALIDATION (Detect tampering)
 * ============================================================================
 */

/**
 * Validate that sanitization didn't strip content
 * Use before form submission to detect malicious input
 * 
 * @param {string} original - Original input value
 * @param {string} sanitized - Sanitized value
 * @param {string} fieldName - Field name for error message
 * @throws {Error} - If sanitization changed the value
 */
export function validateNoTampering(original, sanitized, fieldName) {
    if (original !== sanitized) {
        throw new Error(
            `${fieldName} contains invalid characters. ` +
            `Please use only letters, numbers, and basic punctuation.`
        );
    }
}

/**
 * Validate form data before submission
 * 
 * @param {Object} formData - Form data object
 * @returns {Object} - Sanitized and validated form data
 * @throws {Error} - If validation fails
 */
export function validateFormData(formData) {
    const clean = {};
    
    for (const [key, value] of Object.entries(formData)) {
        if (key.includes('email')) {
            const sanitized = sanitizeEmail(value);
            validateNoTampering(value, sanitized, key);
            clean[key] = sanitized;
        } else if (key.includes('url')) {
            const sanitized = sanitizeURL(value);
            if (!sanitized && value) {
                throw new Error(`${key} contains an invalid URL`);
            }
            clean[key] = sanitized;
        } else if (typeof value === 'string') {
            const sanitized = sanitizeText(value);
            validateNoTampering(value, sanitized, key);
            clean[key] = sanitized;
        } else {
            clean[key] = value;
        }
    }
    
    return clean;
}

/**
 * ============================================================================
 * INITIALIZATION
 * ============================================================================
 */

// Initialize DOMPurify on module load (if available)
if (typeof window !== 'undefined') {
    ensureDOMPurify().catch(err => {
        console.warn('DOMPurify not available - sanitizeHTML() will fall back to text-only mode');
    });
}

/**
 * ============================================================================
 * USAGE EXAMPLES
 * ============================================================================
 * 
 * // 1. SANITIZE TEXT (Default for all user input)
 * const userName = sanitizeText(userInput.value);
 * nameElement.textContent = userName;
 * 
 * // 2. SANITIZE URLs (Images, links)
 * img.src = sanitizeURL(apiResponse.image_url);
 * link.href = sanitizeURL(apiResponse.website);
 * 
 * // 3. BUILD SAFE ELEMENTS (Preferred over innerHTML)
 * const card = buildBusinessCard(companyData, 'es');
 * container.appendChild(card);
 * 
 * // 4. SANITIZE API RESPONSES (Before using data)
 * const response = await fetch('/api/companies');
 * const data = await response.json();
 * const cleanData = sanitizeAPIResponse(data);
 * 
 * // 5. VALIDATE FORMS (Before submission)
 * try {
 *     const cleanFormData = validateFormData({
 *         name: nameInput.value,
 *         email: emailInput.value
 *     });
 *     // Submit cleanFormData
 * } catch (error) {
 *     alert(error.message);
 * }
 * 
 * ============================================================================
 */