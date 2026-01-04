/**
 * XSS Protection Sanitizer Module
 * Provides comprehensive sanitization functions for user input
 * Prevents XSS attacks across the application
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
    
    // Return cleaned email (no HTML escaping needed for valid emails)
    return cleaned;
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
    
    // Allow only numbers, spaces, parentheses, hyphens, and plus sign
    let sanitized = phone.replace(/[^0-9\s\-\(\)\+]/g, '');
    
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
    
    // Also allow relative URLs starting with /
    if (cleaned.startsWith('/')) {
        // Block javascript: and data: in relative URLs
        if (/^\/.*?(javascript|data):/i.test(cleaned)) {
            return '';
        }
        return cleaned;
    }
    
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
            if (Object.prototype.hasOwnProperty.call(data, key)) {
                // Special handling for specific fields
                if (key === 'email' || key === 'user_email' || key === 'company_email') {
                    sanitized[key] = sanitizeEmail(data[key]);
                } else if (key === 'phone') {
                    sanitized[key] = sanitizePhone(data[key]);
                } else if (key.includes('url') || key.includes('link') || key === 'img_url' || key === 'image_url') {
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
 * Validate and sanitize form data comprehensively
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
                if (!validated[key] && value) {
                    throw new Error('Invalid email format');
                }
                break;
                
            case 'phone':
                validated[key] = sanitizePhone(value);
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
                validated[key] = typeof value === 'string' ? sanitizeText(value) : value;
        }
    }
    
    return validated;
}

/**
 * Build safe dropdown option element
 * @param {string} value - Option value
 * @param {string} text - Option display text
 * @returns {HTMLElement} Safe dropdown option element
 */
export function buildDropdownOption(value, text) {
    const option = document.createElement('div');
    option.className = 'dropdown-option';
    option.dataset.value = sanitizeText(String(value || ''));
    option.textContent = sanitizeText(String(text || '')); // textContent is XSS-safe
    return option;
}

/**
 * Build safe business card element for search results
 * Matches the API response structure from /api/v1/companies/search
 * @param {Object} company - Company data object from search API
 * @param {string} lang - Language ('es' or 'en')
 * @returns {HTMLElement} Safe business card element
 */
export function buildBusinessCard(company, lang = 'es') {
    const card = document.createElement('div');
    card.className = 'business-card';
    
    // Image section
    const pictureDiv = document.createElement('div');
    pictureDiv.className = 'card-picture';
    
    const imgUrl = company.img_url || company.image_url;
    if (imgUrl) {
        const img = document.createElement('img');
        img.src = sanitizeURL(imgUrl);
        img.alt = sanitizeText(company.name || 'Company image');
        img.loading = 'lazy';
        img.onerror = function() {
            this.style.display = 'none';
        };
        pictureDiv.appendChild(img);
    }
    card.appendChild(pictureDiv);
    
    // Details section
    const detailsDiv = document.createElement('div');
    detailsDiv.className = 'card-details';
    
    // Company name
    const name = document.createElement('h3');
    name.className = 'business-name';
    name.textContent = sanitizeText(company.name || '');
    detailsDiv.appendChild(name);
    
    // Description
    const description = document.createElement('p');
    description.className = 'concise-description';
    description.textContent = sanitizeText(company.description || '');
    detailsDiv.appendChild(description);
    
    // Product
    if (company.product_name) {
        const product = document.createElement('p');
        product.className = 'product';
        product.textContent = sanitizeText(company.product_name);
        detailsDiv.appendChild(product);
    }
    
    // Location/Commune
    if (company.commune_name) {
        const location = document.createElement('p');
        location.className = 'location';
        location.textContent = sanitizeText(company.commune_name);
        detailsDiv.appendChild(location);
    }
    
    // Address
    if (company.address) {
        const address = document.createElement('p');
        address.className = 'location';
        address.textContent = sanitizeText(company.address);
        detailsDiv.appendChild(address);
    }
    
    // Phone
    if (company.phone) {
        const phone = document.createElement('p');
        phone.className = 'phone';
        phone.textContent = sanitizePhone(company.phone);
        detailsDiv.appendChild(phone);
    }
    
    // Email
    if (company.email) {
        const emailP = document.createElement('p');
        emailP.className = 'mail';
        
        const emailLink = document.createElement('a');
        const sanitizedEmail = sanitizeEmail(company.email);
        if (sanitizedEmail) {
            emailLink.href = `mailto:${sanitizedEmail}`;
            emailLink.textContent = sanitizedEmail;
        } else {
            emailLink.textContent = sanitizeText(company.email);
        }
        emailP.appendChild(emailLink);
        detailsDiv.appendChild(emailP);
    }
    
    card.appendChild(detailsDiv);
    
    return card;
}

/**
 * Create a safe text node (always XSS-safe)
 * @param {string} text - Text content
 * @returns {Text} Text node
 */
export function createSafeTextNode(text) {
    return document.createTextNode(String(text || ''));
}

/**
 * Set element text content safely
 * @param {HTMLElement} element - Target element
 * @param {string} text - Text to set
 */
export function setSafeText(element, text) {
    element.textContent = String(text || '');
}

/**
 * Set element HTML safely (uses DOMPurify)
 * @param {HTMLElement} element - Target element
 * @param {string} html - HTML to set
 */
export function setSafeHTML(element, html) {
    element.innerHTML = sanitizeHTML(html);
}

/**
 * Clear element content safely
 * @param {HTMLElement} element - Target element
 */
export function clearElement(element) {
    element.textContent = '';
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
    setSafeHTML,
    clearElement
};