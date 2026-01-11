import DOMPurify from 'dompurify';

const SAFE_ATTRS = new Set([
    'class', 'id', 'title', 'role', 'tabindex', 'lang', 'dir',
    'aria-label', 'aria-describedby', 'aria-hidden', 'aria-live',
    'aria-expanded', 'aria-selected', 'aria-checked', 'aria-disabled',
    'aria-controls', 'aria-labelledby', 'aria-haspopup', 'aria-current'
]);

const ALLOWED_PROTOCOLS = new Set(['http:', 'https:', 'mailto:', 'tel:']);

const DOMPURIFY_CONFIG = {
    ALLOWED_TAGS: [
        'p', 'br', 'strong', 'em', 'a', 'ul', 'ol', 'li',
        'div', 'span', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
        'blockquote', 'code', 'pre'
    ],
    ALLOWED_ATTR: [
        'href', 'class', 'role', 'id', 'tabindex', 'lang', 'dir', 'aria-*'
    ],
    ALLOWED_URI_REGEXP: /^(https?:|mailto:|tel:)/i,
    ALLOW_DATA_ATTR: true,
    RETURN_TRUSTED_TYPE: false
};

export function setText(element, text) {
    if (!(element instanceof HTMLElement)) {
        throw new TypeError('setText requires an HTMLElement');
    }
    element.textContent = String(text ?? '');
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

export function sanitizeURL(url) {
    if (typeof url !== 'string') return '';

    const trimmed = url.trim();
    if (!trimmed) return '';

    try {
        const parsed = new URL(trimmed, window.location.href);
        if (!ALLOWED_PROTOCOLS.has(parsed.protocol)) return '';
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

    element.setAttribute('src', safe);
}

export function setHTML(element, html) {
    if (!(element instanceof HTMLElement)) {
        throw new TypeError('setHTML requires an HTMLElement');
    }
    element.innerHTML = DOMPurify.sanitize(String(html ?? ''), DOMPURIFY_CONFIG);
}

export function validateEmailFormat(email) {
    if (typeof email !== 'string') return false;
    const trimmed = email.trim();
    if (trimmed.length > 254) return false;
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(trimmed);
}

export function validatePhoneFormat(phone) {
    if (typeof phone !== 'string') return false;
    const trimmed = phone.trim();
    if (trimmed.length > 30) return false;
    return /^(?=.*\d)[\d\s\-\(\)\+]{8,}$/.test(trimmed);
}

export function buildBusinessCard(company, container) {
    if (!(container instanceof HTMLElement)) {
        throw new TypeError('buildBusinessCard requires an HTMLElement container');
    }

    const card = document.createElement('div');
    setSafeAttr(card, 'class', 'business-card');

    if (company.logo) {
        const img = document.createElement('img');
        setSrc(img, company.logo);
        setSafeAttr(img, 'alt', company.name || 'Company image');
        setSafeAttr(img, 'class', 'company-logo');
        card.appendChild(img);
    }

    if (company.name) {
        const nameEl = document.createElement('h2');
        setText(nameEl, company.name);
        card.appendChild(nameEl);
    }

    if (company.description) {
        const descEl = document.createElement('p');
        setText(descEl, company.description);
        card.appendChild(descEl);
    }

    if (company.website) {
        const link = document.createElement('a');
        setHref(link, company.website, { externalBlank: true });
        setText(link, 'Visit Website');
        card.appendChild(link);
    }

    if (company.email && validateEmailFormat(company.email)) {
        const emailLink = document.createElement('a');
        setHref(emailLink, `mailto:${company.email}`, { externalBlank: false });
        setText(emailLink, company.email);
        card.appendChild(emailLink);
    }

    if (company.phone && validatePhoneFormat(company.phone)) {
        const phoneLink = document.createElement('a');
        setHref(phoneLink, `tel:${company.phone}`, { externalBlank: false });
        setText(phoneLink, company.phone);
        card.appendChild(phoneLink);
    }

    container.appendChild(card);
    return card;
}
