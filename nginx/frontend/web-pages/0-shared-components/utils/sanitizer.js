const SAFE_ATTRS = new Set([
    'class', 'id', 'title', 'role', 'tabindex', 'lang', 'dir',
    'aria-label', 'aria-describedby', 'aria-hidden', 'aria-live',
    'aria-expanded', 'aria-selected', 'aria-checked', 'aria-disabled',
    'aria-controls', 'aria-labelledby', 'aria-haspopup', 'aria-current',
    'alt', 'loading', 'width', 'height', 'name', 'type', 'value', 'placeholder',
    'disabled', 'readonly', 'checked', 'selected', 'for'
]);

const ALLOWED_SCHEMES = new Set(['http:', 'https:', 'mailto:', 'tel:']);

export function sanitizeText(text) {
    return String(text ?? '');
}

export function setText(element, text) {
    if (!(element instanceof HTMLElement)) {
        throw new TypeError('setText requires an HTMLElement');
    }
    element.textContent = String(text ?? '');
}

export function sanitizeEmail(email) {
    if (typeof email !== 'string') return '';
    const trimmed = email.trim().toLowerCase();
    if (trimmed.length > 254) return '';
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(trimmed) ? trimmed : '';
}

export function validateEmailFormat(email) {
    if (typeof email !== 'string') return false;
    const trimmed = email.trim();
    if (trimmed.length > 254) return false;
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(trimmed);
}

export function sanitizePhone(phone) {
    if (typeof phone !== 'string') return '';
    return phone.replace(/[^\d\s\-\(\)\+]/g, '').trim();
}

export function validatePhoneFormat(phone) {
    if (typeof phone !== 'string') return false;
    const trimmed = phone.trim();
    if (trimmed.length > 30) return false;
    return /^(?=.*\d)[\d\s\-\(\)\+]{8,}$/.test(trimmed);
}

export function sanitizeURL(url) {
    if (typeof url !== 'string') return '';
    const trimmed = url.trim();
    if (!trimmed) return '';
    try {
        const parsed = new URL(trimmed, window.location.href);
        if (!ALLOWED_SCHEMES.has(parsed.protocol)) return '';
        return parsed.href;
    } catch {
        return '';
    }
}

export function setHref(element, url, options = {}) {
    if (!(element instanceof HTMLAnchorElement || element instanceof HTMLAreaElement)) {
        throw new TypeError('setHref requires an anchor or area element');
    }
    const safe = sanitizeURL(url);
    if (!safe) {
        element.removeAttribute('href');
        return;
    }
    element.setAttribute('href', safe);
    const isExternal = safe.startsWith('http') && !safe.startsWith(window.location.origin);
    if (options.forceBlank || (options.externalBlank !== false && isExternal)) {
        element.setAttribute('target', '_blank');
        element.setAttribute('rel', 'noopener noreferrer');
    }
}

export function setSrc(element, url) {
    if (!(element instanceof HTMLImageElement || element instanceof HTMLMediaElement)) {
        throw new TypeError('setSrc requires an image or media element');
    }

    const safe = sanitizeURL(url);
    if (!safe || !safe.startsWith('http')) {
        element.removeAttribute('src');
        return;
    }

    const busted = `${safe}${safe.includes('?') ? '&' : '?'}v=${Date.now()}`;
    element.setAttribute('src', busted);
}

export function setSafeAttr(element, name, value) {
    if (!(element instanceof HTMLElement)) {
        throw new TypeError('setSafeAttr requires an HTMLElement');
    }
    const lowerName = name.toLowerCase();
    if (lowerName.startsWith('on')) {
        throw new Error(`Event handler attributes are not allowed: ${name}`);
    }
    const isDataAttr = lowerName.startsWith('data-');
    const isAriaAttr = lowerName.startsWith('aria-');
    if (!isDataAttr && !isAriaAttr && !SAFE_ATTRS.has(lowerName)) {
        throw new Error(`Attribute "${name}" is not in the safe allowlist`);
    }
    element.setAttribute(name, String(value ?? ''));
}

export function setSafeAttrs(element, attrs) {
    if (!(element instanceof HTMLElement)) {
        throw new TypeError('setSafeAttrs requires an HTMLElement');
    }
    for (const [name, value] of Object.entries(attrs)) {
        setSafeAttr(element, name, value);
    }
}

export function setHTML(element, html) {
    if (!(element instanceof HTMLElement)) {
        throw new TypeError('setHTML requires an HTMLElement');
    }
    element.innerHTML = DOMPurify.sanitize(String(html ?? ''), {
        ALLOWED_TAGS: [
            'p', 'br', 'strong', 'em', 'a', 'ul', 'ol', 'li',
            'div', 'span', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
            'blockquote', 'code', 'pre'
        ],
        ALLOWED_ATTR: [
            'href', 'class', 'role', 'id', 'tabindex', 'lang', 'dir', 'aria-*'
        ],
        ALLOWED_URI_REGEXP: /^(https?:|mailto:|tel:)/i
    });
}

export function sanitizeAPIResponse(data) {
    return data;
}

export function validateFormData(formData) {
    const validated = {};
    for (const [key, value] of Object.entries(formData)) {
        if (typeof value === 'string') {
            if (key.toLowerCase().includes('email')) {
                validated[key] = sanitizeEmail(value);
            } else if (key.toLowerCase().includes('phone')) {
                validated[key] = sanitizePhone(value);
            } else if (key.toLowerCase().includes('url') || key.toLowerCase().includes('website')) {
                validated[key] = sanitizeURL(value);
            } else {
                validated[key] = value;
            }
        } else {
            validated[key] = value;
        }
    }
    return validated;
}

export function clearElement(element) {
    if (!(element instanceof HTMLElement)) {
        throw new TypeError('clearElement requires an HTMLElement');
    }
    element.textContent = '';
}

export function buildDropdownOption(value, displayText) {
    const option = document.createElement('div');
    option.className = 'dropdown-option';
    option.dataset.value = String(value ?? '');
    option.textContent = String(displayText ?? '');
    return option;
}

export function buildBusinessCard(company, lang = 'es') {
    const card = document.createElement('div');
    card.className = 'business-card';

    if (company.img_url) {
        const pictureDiv = document.createElement('div');
        pictureDiv.className = 'card-picture';
        const img = document.createElement('img');
        setSrc(img, company.img_url);
        img.alt = String(company.name || 'Company image');
        img.loading = 'lazy';
        img.onerror = function () {
            this.style.display = 'none';
        };
        pictureDiv.appendChild(img);
        card.appendChild(pictureDiv);
    }

    const detailsDiv = document.createElement('div');
    detailsDiv.className = 'card-details';

    if (company.name) {
        const nameEl = document.createElement('h3');
        nameEl.className = 'business-name';
        setText(nameEl, company.name);
        detailsDiv.appendChild(nameEl);
    }

    // For search results, use 'description' field (language already selected by backend)
    const description = company.description || (lang === 'es' ? company.description_es : company.description_en);
    if (description) {
        const descEl = document.createElement('p');
        descEl.className = 'concise-description';
        setText(descEl, description);
        detailsDiv.appendChild(descEl);
    }

    // For search results, use 'product_name' field (language already selected by backend)
    const productName = company.product_name || (lang === 'es' ? company.product_name_es : company.product_name_en);
    if (productName) {
        const productEl = document.createElement('p');
        productEl.className = 'product';
        setText(productEl, productName);
        detailsDiv.appendChild(productEl);
    }

    // Commune
    if (company.commune_name) {
        const communeEl = document.createElement('p');
        communeEl.className = 'commune';
        setText(communeEl, company.commune_name);
        detailsDiv.appendChild(communeEl);
    }

    if (company.address) {
        const addressEl = document.createElement('p');
        addressEl.className = 'location';
        setText(addressEl, company.address);
        detailsDiv.appendChild(addressEl);
    }

    if (company.phone) {
        const phoneEl = document.createElement('p');
        phoneEl.className = 'phone';
        setText(phoneEl, company.phone);
        detailsDiv.appendChild(phoneEl);
    }

    if (company.email) {
        const emailEl = document.createElement('p');
        emailEl.className = 'mail';
        setText(emailEl, company.email);
        detailsDiv.appendChild(emailEl);
    }

    card.appendChild(detailsDiv);
    return card;
}

export default {
    sanitizeText,
    setText,
    sanitizeEmail,
    validateEmailFormat,
    sanitizePhone,
    validatePhoneFormat,
    sanitizeURL,
    setHref,
    setSrc,
    setSafeAttr,
    setSafeAttrs,
    setHTML,
    sanitizeAPIResponse,
    validateFormData,
    clearElement,
    buildDropdownOption,
    buildBusinessCard
};