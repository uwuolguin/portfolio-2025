/**
 * XSS Protection Sanitizer Module
 * Provides comprehensive sanitization functions for user input
 *  Prevents XSS attacks across the application
 */

/**
 * Sanitize plain text by removing HTML tags and dangerous characters
 * @param {string} text - Input text to sanitize
 * @returns {string} Sanitized text safe for display
 */
export function sanitizeText(text) {
    if (typeof text !== 'string') {
        return '';
    }
    
    // Remove HTML tags
    let sanitized = text.replace(/<[^>]*>/g, '');
    
    // Escape special HTML characters
    const entityMap = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;',
        '/': '&#x2F;',
        '`': '&#x60;',
        '=': '&#x3D;'
    };
    
    sanitized = sanitized.replace(/[&<>"'`=\/]/g, (char) => entityMap[char]);
    
    return sanitized;
}

/**
 * Sanitize and validate email addresses
 * @param {string} email - Email address to sanitize
 * @returns {string} Sanitized email or empty string if invalid
 */
export function sanitizeEmail(email) {
    if (typeof email !== 'string') {
        return '';
    }
    
    // Basic email validation regex
    const emailRegex = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;
    
    // Remove whitespace and convert to lowercase
    const cleaned = email.trim().toLowerCase();
    
    // Validate format
    if (!emailRegex.test(cleaned)) {
        return '';
    }
    
    // Additional sanitization - remove any HTML entities
    return sanitizeText(cleaned);
}

/**
 * Sanitize phone numbers
 * @param {string} phone - Phone number to sanitize
 * @returns {string} Sanitized phone number
 */
export function sanitizePhone(phone) {
    if (typeof phone !== 'string') {
        return '';
    }
    
    // Remove HTML tags first
    let sanitized = sanitizeText(phone);
    
    // Allow only numbers, spaces, parentheses, hyphens, and plus sign
    sanitized = sanitized.replace(/[^0-9\s\-\(\)\+]/g, '');
    
    return sanitized.trim();
}

/**
 * Sanitize URLs and validate them
 * @param {string} url - URL to sanitize
 * @returns {string} Sanitized URL or empty string if invalid
 */
export function sanitizeURL(url) {
    if (typeof url !== 'string') {
        return '';
    }
    
    // Remove whitespace
    const cleaned = url.trim();
    
    // Only allow http, https, and mailto protocols
    const allowedProtocols = /^(https?:\/\/|mailto:)/i;
    
    if (!allowedProtocols.test(cleaned)) {
        return '';
    }
    
    // Block javascript: and data: URIs
    if (/^(javascript|data):/i.test(cleaned)) {
        return '';
    }
    
    return cleaned;
}

/**
 * Sanitize HTML content using DOMPurify
 * ⚠️ Use only when HTML rendering is absolutely necessary
 * @param {string} html - HTML content to sanitize
 * @returns {string} Sanitized HTML
 */
export function sanitizeHTML(html) {
    if (typeof html !== 'string') {
        return '';
    }
    
    // Check if DOMPurify is available
    if (typeof DOMPurify !== 'undefined') {
        return DOMPurify.sanitize(html, {
            ALLOWED_TAGS: ['b', 'i', 'em', 'strong', 'p', 'br', 'ul', 'ol', 'li', 'a'],
            ALLOWED_ATTR: ['href', 'target'],
            ALLOW_DATA_ATTR: false
        });
    }
    
    // Fallback: strip all HTML if DOMPurify not available
    return sanitizeText(html);
}

/**
 * Sanitize API response data recursively
 * @param {any} data - Data from API response
 * @returns {any} Sanitized data
 */
export function sanitizeAPIResponse(data) {
    if (data === null || data === undefined) {
        return data;
    }
    
    if (typeof data === 'string') {
        return sanitizeText(data);
    }
    
    if (Array.isArray(data)) {
        return data.map(item => sanitizeAPIResponse(item));
    }
    
    if (typeof data === 'object') {
        const sanitized = {};
        for (const key in data) {
            if (data.hasOwnProperty(key)) {
                // Special handling for specific fields
                if (key === 'email') {
                    sanitized[key] = sanitizeEmail(data[key]);
                } else if (key === 'phone') {
                    sanitized[key] = sanitizePhone(data[key]);
                } else if (key.includes('url') || key.includes('link')) {
                    sanitized[key] = sanitizeURL(data[key]);
                } else {
                    sanitized[key] = sanitizeAPIResponse(data[key]);
                }
            }
        }
        return sanitized;
    }
    
    // Numbers, booleans, etc. pass through
    return data;
}

/**
 *  NEW: Validate and sanitize form data comprehensively
 * @param {Object} formData - Object containing form fields
 * @returns {Object} Validated and sanitized form data
 * @throws {Error} If validation fails
 */
export function validateFormData(formData) {
    const validated = {};
    
    for (const [key, value] of Object.entries(formData)) {
        switch (key) {
            case 'email':
                validated[key] = sanitizeEmail(value);
                if (!validated[key]) {
                    throw new Error('Invalid email format');
                }
                break;
                
            case 'phone':
                validated[key] = sanitizePhone(value);
                if (!validated[key]) {
                    throw new Error('Invalid phone number');
                }
                break;
                
            case 'name':
            case 'address':
            case 'description':
            case 'companyName':
                validated[key] = sanitizeText(value);
                if (!validated[key] || validated[key].length === 0) {
                    throw new Error(`${key} cannot be empty`);
                }
                break;
                
            default:
                // Default sanitization for other text fields
                validated[key] = sanitizeText(value);
        }
    }
    
    return validated;
}

/**
 *  NEW: Build safe dropdown option element
 * @param {string} value - Option value
 * @param {string} text - Option display text
 * @returns {HTMLElement} Safe dropdown option element
 */
export function buildDropdownOption(value, text) {
    const option = document.createElement('div');
    option.className = 'dropdown-option';
    option.dataset.value = sanitizeText(value);
    option.textContent = sanitizeText(text); // textContent is XSS-safe
    return option;
}

/**
 *  NEW: Build safe business card element
 * @param {Object} company - Company data object
 * @returns {HTMLElement} Safe business card element
 */
export function buildBusinessCard(company) {
    const card = document.createElement('div');
    card.className = 'business-card';
    
    // Image (if exists)
    if (company.image_url) {
        const img = document.createElement('img');
        img.className = 'business-image';
        img.src = sanitizeURL(company.image_url);
        img.alt = sanitizeText(company.name);
        img.loading = 'lazy';
        card.appendChild(img);
    }
    
    // Company name
    const name = document.createElement('h3');
    name.className = 'business-name';
    name.textContent = sanitizeText(company.name);
    card.appendChild(name);
    
    // Product
    const product = document.createElement('p');
    product.className = 'business-product';
    product.textContent = sanitizeText(company.product);
    card.appendChild(product);
    
    // Commune
    const commune = document.createElement('p');
    commune.className = 'business-commune';
    commune.textContent = sanitizeText(company.commune);
    card.appendChild(commune);
    
    // Email
    const email = document.createElement('p');
    email.className = 'business-email';
    const emailLink = document.createElement('a');
    emailLink.href = `mailto:${sanitizeEmail(company.email)}`;
    emailLink.textContent = sanitizeEmail(company.email);
    email.appendChild(emailLink);
    card.appendChild(email);
    
    // Phone
    const phone = document.createElement('p');
    phone.className = 'business-phone';
    phone.textContent = sanitizePhone(company.phone);
    card.appendChild(phone);
    
    return card;
}

/**
 * Create a safe text node (always XSS-safe)
 * @param {string} text - Text content
 * @returns {Text} Text node
 */
export function createSafeTextNode(text) {
    return document.createTextNode(sanitizeText(text));
}

/**
 * Set element text content safely
 * @param {HTMLElement} element - Target element
 * @param {string} text - Text to set
 */
export function setSafeText(element, text) {
    element.textContent = sanitizeText(text);
}

/**
 * Set element HTML safely (uses DOMPurify)
 * @param {HTMLElement} element - Target element
 * @param {string} html - HTML to set
 */
export function setSafeHTML(element, html) {
    element.innerHTML = sanitizeHTML(html);
}

// Export all functions as default object as well
export default {
    sanitizeText,
    sanitizeEmail,
    sanitizePhone,
    sanitizeURL,
    sanitizeHTML,
    sanitizeAPIResponse,
    validateFormData,
    buildDropdownOption,
    buildBusinessCard,
    createSafeTextNode,
    setSafeText,
    setSafeHTML
};